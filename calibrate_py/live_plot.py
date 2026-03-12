import argparse
import time
import pandas as pd
import matplotlib.pyplot as plt


def create_anim(path, interval_ms, cols=None):
    plt.ion()
    fig, ax = plt.subplots()
    stop = {"stop": False}

    def _on_key(event):
        if event.key in ("q", "escape", "esc"):
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
                ax.clear()
                ax.text(0.5, 0.5, f"Error reading file:\n{e}", ha="center")
                plt.draw()
                plt.pause(max(0.1, interval_ms / 1000.0))
                continue

            if df.empty:
                ax.clear()
                ax.text(0.5, 0.5, "No data yet", ha="center")
                plt.draw()
                plt.pause(max(0.1, interval_ms / 1000.0))
                continue

            # Determine columns to plot
            if cols:
                plot_cols = [
                    c
                    for c in cols
                    if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
                ]
            else:
                plot_cols = [
                    c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])
                ]

            if not plot_cols:
                ax.clear()
                ax.text(0.5, 0.5, "No numeric columns to plot", ha="center")
                plt.draw()
                plt.pause(max(0.1, interval_ms / 1000.0))
                continue

            ax.clear()
            for col in plot_cols:
                ax.plot(df.index, df[col], label=col)

            ax.set_xlabel("index")
            ax.legend(loc="upper right")
            ax.relim()
            ax.autoscale_view()
            plt.tight_layout()
            plt.draw()
            plt.pause(max(0.1, interval_ms / 1000.0))

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


if __name__ == "__main__":
    main()
