"""Main calibration CLI translated from Calibrate.cs (simplified interactive controls).

Modes supported: 1) Timed sequence  2) Take data loop  3) Import steps from CSV
"""

import os
import sys
import time
import ctypes
import subprocess
import traceback
from calibrate_py.labjack_device import LabJackDevice
from calibrate_py.servo_calibration import ServoCalibration
from calibrate_py.data_acquisition import DataAcquisition


def launch_live_plot(latest_file: str, cols=None):
    # Prefer local calibrate_py live_plot, then workspace Calibrate/live_plot.py, then cwd
    candidates = [
        os.path.join(os.path.dirname(__file__), "live_plot.py"),
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "Calibrate", "live_plot.py"
        ),
        os.path.join(os.getcwd(), "live_plot.py"),
    ]
    script_path = None
    for c in candidates:
        if os.path.exists(c):
            script_path = c
            break

    if script_path is None:
        print("No live_plot.py found to launch.")
        return

    try:
        args = [sys.executable, script_path, "--file", latest_file]
        if cols:
            if isinstance(cols, (list, tuple)):
                cols_arg = ",".join(cols)
            else:
                cols_arg = str(cols)
            args += ["--cols", cols_arg]
        proc = subprocess.Popen(args)
        print(f"Started live plot for {latest_file} using {script_path}")
        return proc
    except Exception as e:
        print(f"Could not start live plot: {e}")
        return None


def main():
    desired_frequency = 50
    position_zero = 90
    position_up = 135
    position_down = 45
    core_frequency = 80000000
    clock_divisor = 1
    pwm_dio = 2

    plot_proc = None
    device = None
    servo = None
    daq = None

    try:
        print(
            "Select operation:\n1) Calibration (timed / CSV)\n2) Take data (print + live-plot specified AIN pins)"
        )
        primary_mode = input("Enter 1 or 2: ").strip()

        if primary_mode == "2":
            raw = input("Enter input pin(s) comma-separated Example: AIN0: ").strip()
            if not raw:
                raw = "AIN0"
            input_pins = [p.strip() for p in raw.split(",")]

            device = LabJackDevice(input_pins)
            device.open()
            device.configure_pins()

            servo = ServoCalibration(
                device, core_frequency, pwm_dio, clock_divisor, desired_frequency
            )
            daq = DataAcquisition(device, servo)
            daq.create_output_file()

            # Launch live_plot for the CSV file we just created (shows live data by default)
            if daq.file_path:
                plot_proc = launch_live_plot(
                    os.path.join(os.getcwd(), daq.file_path), cols=input_pins
                )

            print("Capturing data. Press Ctrl-C to stop.")
            try:
                while True:
                    daq.read_and_save(position_zero)
                    daq.print_data(position_zero)
                    time.sleep(0.2)
            except KeyboardInterrupt:
                print("Stopping capture...")
                if servo:
                    servo.turn_off_pwm()
                # ensure plot is closed
                try:
                    if plot_proc and plot_proc.poll() is None:
                        plot_proc.terminate()
                except Exception:
                    pass
                if device:
                    device.close()
                print("Press Enter to acknowledge and exit.")
                input()
                return

        # Calibration path
        raw = input("Enter input pin(s) comma-separated Example: AIN0:").strip()
        if not raw:
            raw = "AIN0"
        input_pins = [p.strip() for p in raw.split(",")]
        rpm = input("Enter PWM DIO pin number (default 2):").strip()
        if rpm:
            try:
                pwm_dio = int(rpm)
            except Exception:
                pwm_dio = 2

        device = LabJackDevice(input_pins)
        device.open()
        device.configure_pins()

        servo = ServoCalibration(
            device, core_frequency, pwm_dio, clock_divisor, desired_frequency
        )
        daq = DataAcquisition(device, servo)
        daq.create_output_file()
        # Launch live_plot for the CSV file we just created (shows live data by default)
        if daq.file_path:
            plot_proc = launch_live_plot(
                os.path.join(os.getcwd(), daq.file_path), cols=input_pins
            )

        print(
            "Choose mode:\n1) Timed sequence (run steps for given durations)\n2) Interactive (hold Up/Down arrows)\n3) Import steps from CSV."
        )
        mode = input("Enter 1, 2 or 3: ").strip()

        if mode == "1":
            try:
                steps = int(input("Number of steps: ").strip())
            except Exception:
                print("Invalid number; exiting.")
                return
            angles = []
            durations = []
            for i in range(steps):
                d = input(f"Step {i+1} direction (up/down/zero): ").strip().lower()
                if d in ("up", "u"):
                    angles.append(position_up)
                elif d in ("down", "d"):
                    angles.append(position_down)
                else:
                    angles.append(position_zero)
                try:
                    dur = float(input(f"Step {i+1} duration (seconds): ").strip())
                except Exception:
                    dur = 1.0
                durations.append(dur)

            for i in range(steps):
                print(
                    f"Starting step {i+1}/{steps}: angle {angles[i]}, duration {durations[i]}s."
                )
                servo.set_servo_angle(angles[i])
                t0 = time.time()
                try:
                    while time.time() - t0 < durations[i]:
                        daq.read_and_save(None)
                        daq.print_data(angles[i])
                        time.sleep(0.05)
                except KeyboardInterrupt:
                    print("Aborted by user.")
                    break
                servo.turn_off_pwm()

        elif mode == "3":
            csv_path = input("Enter CSV file path: ").strip()
            if not csv_path or not os.path.exists(csv_path):
                print("File not found or invalid path. Exiting CSV mode.")
                return
            lines = []
            with open(csv_path, "r", encoding="utf-8") as f:
                for raw in f:
                    s = raw.strip()
                    if not s:
                        continue
                    parts = [p.strip() for p in s.split(",")]
                    if len(parts) < 2:
                        continue
                    a_part, d_part = parts[0], parts[1]
                    try:
                        duration = float(d_part)
                    except Exception:
                        continue
                    if a_part.isdigit() or (
                        a_part.startswith("-") and a_part[1:].isdigit()
                    ):
                        angle = int(a_part)
                    else:
                        a = a_part.lower()
                        if a in ("up", "u"):
                            angle = position_up
                        elif a in ("down", "d"):
                            angle = position_down
                        else:
                            angle = position_zero
                    lines.append((angle, duration))

            for angle, duration in lines:
                print(f"Running CSV step: angle {angle}, duration {duration}")
                servo.set_servo_angle(angle)
                t0 = time.time()
                try:
                    while time.time() - t0 < duration:
                        daq.read_and_save(None)
                        daq.print_data(angle)
                        time.sleep(0.05)
                except KeyboardInterrupt:
                    print("Aborted by user.")
                    break
                servo.turn_off_pwm()

        elif mode == "2":
            # Interactive: hold Up/Down arrows to move servo, Esc to exit
            VK_UP = 0x26
            VK_DOWN = 0x28
            VK_ESCAPE = 0x1B

            current_angle = position_zero
            servo.set_servo_angle(current_angle)
            print("Interactive mode: hold Up/Down to move servo; press Esc to exit.")
            try:
                while True:
                    if (ctypes.windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0:
                        print("Escape pressed — exiting interactive mode.")
                        break

                    if (ctypes.windll.user32.GetAsyncKeyState(VK_UP) & 0x8000) != 0:
                        current_angle = position_up
                    elif (ctypes.windll.user32.GetAsyncKeyState(VK_DOWN) & 0x8000) != 0:
                        current_angle = position_down
                    else:
                        current_angle = position_zero

                    servo.set_servo_angle(current_angle)
                    daq.read_and_save(None)
                    daq.print_data(current_angle)
                    time.sleep(0.05)
            except KeyboardInterrupt:
                print("Interactive aborted by user.")
            finally:
                if servo:
                    servo.turn_off_pwm()
                # close plot if running
                try:
                    if plot_proc and plot_proc.poll() is None:
                        plot_proc.terminate()
                except Exception:
                    pass
                print("Press Enter to acknowledge and exit.")
                input()
                return

    except Exception as e:
        # Descriptive error handling: print traceback and clean up
        print("An error occurred:")
        traceback.print_exception(type(e), e, e.__traceback__)
        try:
            if plot_proc and plot_proc.poll() is None:
                plot_proc.terminate()
        except Exception:
            pass
        try:
            if device:
                device.close()
        except Exception:
            pass
        print("Press Enter to acknowledge the error and exit.")
        input()
        sys.exit(1)

    # Normal cleanup
    try:
        if servo:
            servo.turn_off_pwm()
    except Exception:
        pass
    try:
        if device:
            device.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
