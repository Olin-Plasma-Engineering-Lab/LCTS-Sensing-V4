import argparse
import time
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation


def create_anim(path, interval_ms):
    # Use an interactive loop with plt.pause() to re-read the CSV file
    # continuously. This avoids FuncAnimation stopping after a fixed
    # number of frames on some platforms.
    plt.ion()
    fig, ax = plt.subplots()
    stop = {"stop": False}

    def _on_key(event):
        if event.key == "q":
            stop["stop"] = True
            try:
                plt.close(fig)
            except Exception:
                pass

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

            # Always plot 'AIN0' against the DataFrame index. If not present,
            # fall back to the first numeric column.
            if "AIN0" in df.columns and pd.api.types.is_numeric_dtype(df["AIN0"]):
                y = df["AIN0"]
                col_label = "AIN0"
            else:
                numeric_cols = [
                    c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])
                ]
                if not numeric_cols:
                    ax.clear()
                    ax.text(0.5, 0.5, "No numeric columns to plot", ha="center")
                    plt.draw()
                    plt.pause(max(0.1, interval_ms / 1000.0))
                    continue
                y = df[numeric_cols[0]]
                col_label = numeric_cols[0]

            x = df.index
            ax.clear()
            ax.plot(x, y, label=col_label)
            ax.set_xlabel("index")
            ax.set_ylabel(col_label)
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
        help="Refresh interval in ms (default 1000)",
    )
    args = p.parse_args()

    try:
        create_anim(args.file, args.interval)
    except KeyboardInterrupt:
        print("Exiting")


if __name__ == "__main__":
    main()
