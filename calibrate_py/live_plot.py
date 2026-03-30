import argparse
import multiprocessing
import pandas as pd
import matplotlib.pyplot as plt


def create_anim(path, interval_ms, cols=None, stop_event=None, cmd_queue=None):
    plt.ion()
    fig, (ax_pos, ax_therm) = plt.subplots(2, 1, sharex=True, figsize=(8, 6))
    stop = {"stop": False}

    def _on_key(event):
        key = event.key
        # forward key to caller via queue if provided
        if cmd_queue is not None:
            try:
                cmd_queue.put(key)
            except Exception:
                pass

        if key in ("q", "escape", "esc"):
            if stop_event is not None:
                try:
                    stop_event.set()
                except Exception:
                    pass
            else:
                stop["stop"] = True
            try:
                plt.close(fig)
            except Exception:
                pass

    fig.canvas.mpl_connect("key_press_event", _on_key)

    try:
        while True:
            try:
                df = pd.read_csv(path)
            except Exception as e:
                ax_pos.clear()
                ax_therm.clear()
                ax_pos.text(0.5, 0.5, f"Error reading file:\n{e}", ha="center")
                plt.draw()
                plt.pause(max(0.1, interval_ms / 1000.0))
                continue

            if df.empty:
                ax_pos.clear()
                ax_therm.clear()
                ax_pos.text(0.5, 0.5, "No data yet", ha="center")
                plt.draw()
                plt.pause(max(0.1, interval_ms / 1000.0))
                continue

            # Determine columns to plot and split into position vs thermocouples
            if cols:
                matched = [
                    c
                    for c in cols
                    if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
                ]
            else:
                matched = [
                    c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])
                ]

            if not matched:
                ax_pos.clear()
                ax_therm.clear()
                ax_pos.text(0.5, 0.5, "No numeric columns to plot", ha="center")
                plt.draw()
                plt.pause(max(0.1, interval_ms / 1000.0))
                continue

            pos_col = matched[0] if len(matched) >= 1 else None
            therm_cols = matched[1:] if len(matched) > 1 else []

            # Plot position sensor on top axis
            ax_pos.clear()
            if pos_col and pos_col in df.columns:
                ax_pos.plot(df.index, df[pos_col], label=pos_col, color="tab:blue")
                ax_pos.set_ylabel(pos_col)
            else:
                ax_pos.text(0.5, 0.5, "No position column", ha="center")

            # Plot thermocouples on bottom axis
            ax_therm.clear()
            if therm_cols:
                for col in therm_cols:
                    ax_therm.plot(df.index, df[col], label=col)
                ax_therm.set_ylabel("Thermocouples")
                ax_therm.legend(loc="upper right")
            else:
                ax_therm.text(0.5, 0.5, "No thermocouple columns", ha="center")

            ax_therm.set_xlabel("index")
            ax_pos.relim()
            ax_pos.autoscale_view()
            ax_therm.relim()
            ax_therm.autoscale_view()
            plt.tight_layout()
            plt.draw()
            plt.pause(max(0.1, interval_ms / 1000.0))

            if stop_event is not None:
                try:
                    if stop_event.is_set():
                        break
                except Exception:
                    pass
            else:
                if stop["stop"]:
                    break
    except KeyboardInterrupt:
        plt.ioff()
        plt.show()


def main():
    p = argparse.ArgumentParser(description="Live-plot a growing CSV file")
    p.add_argument("--file", "-f", required=True, help="Path to CSV file")
    p.add_argument(
        "--interval",
        "-i",
        type=int,
        default=100,
        help="Refresh interval in ms (default 100)",
    )
    p.add_argument(
        "--cols",
        "-c",
        default=None,
        help="Comma-separated column names to plot (default: first numeric column)",
    )
    args = p.parse_args()

    cols = None
    if args.cols:
        cols = [c.strip() for c in args.cols.split(",") if c.strip()]

    try:
        create_anim(args.file, args.interval, cols=cols)
    except KeyboardInterrupt:
        print("Exiting")


def start_live_plot(path, cols=None, interval=100, cmd_queue=None):
    """Start the live plot in a background process and return (Process, Event).

    The returned `Event` is set by the plot process when the user presses
    `q` (or Escape). Callers can monitor the event to exit their loops.
    """
    evt = multiprocessing.Event()
    p = multiprocessing.Process(
        target=create_anim, args=(path, interval, cols, evt, cmd_queue)
    )
    p.daemon = True
    p.start()
    return p, evt


if __name__ == "__main__":
    main()
