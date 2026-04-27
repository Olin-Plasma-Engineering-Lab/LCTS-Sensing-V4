"""Live-plot a growing CSV file.

Used both as a standalone script and as a background worker spawned by
calibrate.py via start_live_plot(). The first numeric column is treated as
the position sensor and plotted on the top axis; any remaining numeric
columns are treated as thermocouples and plotted on the bottom axis.

Press 'q' or Esc in the plot window to close it. When run via
start_live_plot(), the returned multiprocessing.Event is set on close so
the parent process can detect the user's intent to stop.
"""

from __future__ import annotations

import argparse
import multiprocessing
from typing import List, Optional

import pandas as pd
import matplotlib.pyplot as plt

# Version marker so we can confirm which file is loaded if there's a
# pycache / stale-file question. Bumped any time _redraw changes meaningfully.
_LIVE_PLOT_VERSION = "2026-04-27-v3-defensive"


def _setup_close_handlers(fig, stop_flag, stop_event):
    """Register key + window-close handlers that flip the stop flag/event."""

    def _signal_stop():
        stop_flag["stop"] = True
        if stop_event is not None:
            try:
                stop_event.set()
            except Exception:
                pass

    def _on_key(event):
        if event.key in ("q", "escape", "esc"):
            _signal_stop()
            try:
                plt.close(fig)
            except Exception:
                pass

    def _on_close(_event):
        _signal_stop()

    fig.canvas.mpl_connect("key_press_event", _on_key)
    fig.canvas.mpl_connect("close_event", _on_close)


_CJC_COLUMN = "CJC_C"
_DEBUG_PRINTED = {"done": False}


def _redraw(ax_pos, ax_therm, df: pd.DataFrame, cols: Optional[List[str]]):
    """Draw the position pin on the top axis, thermocouples + CJC on the bottom.

    `cols`, if provided, is the list of input pin names supplied by the
    calibration script (e.g. ["AIN0", "AIN1", "AIN2"]). The first entry is
    the position sensor; the rest are thermocouples. The CJC_C column is
    detected by name and plotted on the thermocouple axis with a dashed
    style so it's distinguishable from real TC channels.

    When `cols` is None, every numeric column except CJC_C is treated as
    a candidate input pin, with the first being the position sensor.
    """
    ax_pos.clear()
    ax_therm.clear()

    # Always plot against a clean integer sample index. Without this reset,
    # if pandas auto-detects the Timestamp column as the index (or anything
    # else weird happens), the x-axis can end up as datetimes and the data
    # routing gets confusing in tooltips.
    df = df.reset_index(drop=True)

    # Pick the input-pin columns from the request list, falling back to
    # auto-detect for ad-hoc CSVs.
    if cols:
        input_cols = [c for c in cols
                      if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    else:
        input_cols = [c for c in df.columns
                      if c != _CJC_COLUMN and pd.api.types.is_numeric_dtype(df[c])]

    # On the first successful redraw, print diagnostics so the user can verify
    # that columns are routed correctly.
    if not _DEBUG_PRINTED["done"] and input_cols:
        import sys as _sys
        print(f"[live_plot] CSV columns: {list(df.columns)}", file=_sys.stderr)
        print(f"[live_plot] Requested cols: {cols}", file=_sys.stderr)
        print(f"[live_plot] Position pin (top axis): {input_cols[0]!r}", file=_sys.stderr)
        print(f"[live_plot] Thermocouple pins (bottom axis): {input_cols[1:]!r}", file=_sys.stderr)
        if _CJC_COLUMN in df.columns:
            print("[live_plot] CJC column found and plotted on bottom axis", file=_sys.stderr)
        _DEBUG_PRINTED["done"] = True

    if not input_cols:
        ax_pos.text(0.5, 0.5, "No numeric input columns to plot", ha="center")
        ax_therm.text(0.5, 0.5, "", ha="center")
        return

    pos_col = input_cols[0]
    therm_cols = input_cols[1:]
    has_cjc = _CJC_COLUMN in df.columns and pd.api.types.is_numeric_dtype(df[_CJC_COLUMN])

    # Use .values (numpy arrays) explicitly to avoid any chance of pandas
    # misaligning data with the x-coordinate when index quirks are present.
    x = df.index.values

    # Top axis: position sensor only (raw voltage, no conversion).
    ax_pos.plot(x, df[pos_col].values, label=pos_col, color="tab:blue")
    ax_pos.set_ylabel(f"{pos_col} [V]")
    ax_pos.legend(loc="upper right")

    # Bottom axis: thermocouples (solid) and CJC if present (dashed grey).
    if therm_cols or has_cjc:
        for col in therm_cols:
            ax_therm.plot(x, df[col].values, label=col)
        if has_cjc:
            ax_therm.plot(x, df[_CJC_COLUMN].values, label="CJC",
                          color="tab:gray", linestyle="--", linewidth=1.0)
        ax_therm.set_ylabel("Temperature [C]")
        ax_therm.legend(loc="upper right")
    else:
        ax_therm.text(0.5, 0.5, "No thermocouple columns", ha="center")

    ax_therm.set_xlabel("sample index")
    ax_pos.relim()
    ax_pos.autoscale_view()
    ax_therm.relim()
    ax_therm.autoscale_view()


def create_anim(
    path: str,
    interval_ms: int,
    cols: Optional[List[str]] = None,
    stop_event: Optional[multiprocessing.synchronize.Event] = None,
):
    import sys as _sys
    print(f"[live_plot] version={_LIVE_PLOT_VERSION}", file=_sys.stderr)
    print(f"[live_plot] reading: {path}", file=_sys.stderr)
    print(f"[live_plot] requested cols: {cols}", file=_sys.stderr)
    plt.ion()
    fig, (ax_pos, ax_therm) = plt.subplots(2, 1, sharex=True, figsize=(8, 6))
    stop_flag = {"stop": False}
    _setup_close_handlers(fig, stop_flag, stop_event)
    pause_s = max(0.1, interval_ms / 1000.0)

    try:
        while not stop_flag["stop"]:
            try:
                df = pd.read_csv(path)
            except Exception as e:
                ax_pos.clear()
                ax_therm.clear()
                ax_pos.text(0.5, 0.5, f"Error reading file:\n{e}", ha="center")
            else:
                if df.empty:
                    ax_pos.clear()
                    ax_therm.clear()
                    ax_pos.text(0.5, 0.5, "No data yet", ha="center")
                else:
                    _redraw(ax_pos, ax_therm, df, cols)

            plt.tight_layout()
            plt.draw()
            plt.pause(pause_s)

            if stop_event is not None:
                try:
                    if stop_event.is_set():
                        break
                except Exception:
                    pass
    except KeyboardInterrupt:
        pass
    finally:
        plt.ioff()
        try:
            plt.close(fig)
        except Exception:
            pass


def start_live_plot(
    path: str,
    cols: Optional[List[str]] = None,
    interval: int = 100,
):
    """Start the live plot in a background process.

    Returns (Process, Event). The Event is set when the user closes the
    plot or presses q/Esc, so the parent can treat that as "stop".
    """
    evt = multiprocessing.Event()
    p = multiprocessing.Process(
        target=create_anim,
        args=(path, interval, cols, evt),
    )
    p.daemon = True
    p.start()
    return p, evt


def main():
    parser = argparse.ArgumentParser(description="Live-plot a growing CSV file")
    parser.add_argument("--file", "-f", required=True, help="Path to CSV file")
    parser.add_argument(
        "--interval", "-i", type=int, default=100,
        help="Refresh interval in ms (default 100)",
    )
    parser.add_argument(
        "--cols", "-c", default=None,
        help="Comma-separated column names to plot (default: all numeric columns)",
    )
    args = parser.parse_args()

    cols = [c.strip() for c in args.cols.split(",") if c.strip()] if args.cols else None
    try:
        create_anim(args.file, args.interval, cols=cols)
    except KeyboardInterrupt:
        print("Exiting")


if __name__ == "__main__":
    main()
