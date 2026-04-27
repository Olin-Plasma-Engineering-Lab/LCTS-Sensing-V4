"""Calibration CLI for LabJack T7 + RVDT/thermocouples + servo control.

Modes
-----
1) Calibration
   1a) Timed sequence: run a list of (angle, duration) steps you enter manually.
   1b) Interactive: hold Up/Down arrows to move the servo, Esc to exit.
   1c) Import steps: read (angle, duration) pairs from a CSV file.
2) Take data: continuously sample and live-plot AIN pins (no servo motion).

Cross-platform keyboard input is provided by `pynput`, so the same script works
on Windows, macOS, and Linux. On macOS you may need to grant accessibility
permission to the terminal; on Linux you need an X server (or a uinput-capable
backend).
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


# --------------------------------------------------------------------------
# Package bootstrap so this file can be run as either
#   python -m calibrate_py.calibrate
# or
#   python calibrate_py/calibrate.py
# --------------------------------------------------------------------------
if __package__ is None or __package__ == "":
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)
    __package__ = "calibrate_py"

from .labjack_device import LabJackDevice
from .servo_calibration import ServoCalibration
from .data_acquisition import DataAcquisition


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
@dataclass
class Config:
    desired_frequency: int = 50         # PWM frequency (Hz)
    core_frequency: int = 80_000_000    # T7 core clock
    clock_divisor: int = 1
    pwm_dio: int = 2

    position_zero: int = 90             # angle that holds 360 servo still
    position_up: int = 135              # while Up arrow held
    position_down: int = 45             # while Down arrow held

    sample_period_s: float = 0.05       # sleep between samples
    take_data_period_s: float = 0.2     # sleep in "take data" mode

    # CJC source for thermocouple conversion. "device" reads the T7 internal
    # sensor (recommended when TCs are on AIN0-3 directly). Use "air" for a
    # CB37 setup, or a fixed float in degrees Celsius for a static CJC.
    cjc_source: object = "device"
    cjc_offset_c: float = -3.0          # screw-terminal vs. on-board sensor delta


# --------------------------------------------------------------------------
# Cross-platform keyboard handling via pynput
# --------------------------------------------------------------------------
class KeyboardMonitor:
    """Thread-safe view of currently-held keys.

    Wraps a pynput keyboard listener so the main loop can ask
        kb.is_held("up"), kb.is_held("escape"), kb.was_pressed("enter")
    without worrying about console focus or input buffering.

    `is_held()` reflects current physical key state (like Win32
    GetAsyncKeyState). `was_pressed()` consumes one-shot press events from a
    queue, which is useful for things like "press Enter to continue".
    """

    def __init__(self) -> None:
        import queue
        self._held: set = set()
        self._press_queue: "queue.Queue" = queue.Queue()
        self._listener = None
        try:
            from pynput import keyboard  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "pynput is required for keyboard input. Install with: pip install pynput"
            ) from e

        def on_press(key):
            name = self._key_name(key)
            self._held.add(name)
            try:
                self._press_queue.put_nowait(name)
            except Exception:
                pass

        def on_release(key):
            name = self._key_name(key)
            self._held.discard(name)

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()

    @staticmethod
    def _key_name(key) -> str:
        # Special keys (arrows, esc, enter, etc.) come through as keyboard.Key.<n>;
        # character keys come through as keyboard.KeyCode with a `char` attribute.
        if hasattr(key, "name"):
            return key.name.lower()
        if hasattr(key, "char") and key.char is not None:
            return key.char.lower()
        return str(key).lower()

    def is_held(self, *names: str) -> bool:
        """True if any of the given key names is currently held."""
        wanted = {n.lower() for n in names}
        return bool(wanted & self._held)

    def was_pressed(self, *names: str) -> bool:
        """True if any matching key appears in the press queue. Drains the queue."""
        import queue
        wanted = {n.lower() for n in names}
        found = False
        while True:
            try:
                k = self._press_queue.get_nowait()
            except queue.Empty:
                break
            if k in wanted:
                found = True
        return found

    def drain(self) -> None:
        """Discard any pending press events."""
        import queue
        while True:
            try:
                self._press_queue.get_nowait()
            except queue.Empty:
                break

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None


# --------------------------------------------------------------------------
# Live plot helpers (process management)
# --------------------------------------------------------------------------
@dataclass
class PlotHandle:
    process: object = None
    stop_event: Optional[object] = None


def _plot_alive(handle: Optional[PlotHandle]) -> bool:
    if handle is None or handle.process is None:
        return False
    p = handle.process
    if hasattr(p, "is_alive"):
        try:
            return p.is_alive()
        except Exception:
            return False
    if hasattr(p, "poll"):
        try:
            return p.poll() is None
        except Exception:
            return False
    return False


def _terminate_plot(handle: Optional[PlotHandle]) -> None:
    if handle is None or handle.process is None:
        return
    p = handle.process
    try:
        p.terminate()
    except Exception:
        try:
            if hasattr(p, "kill"):
                p.kill()
        except Exception:
            pass


def launch_live_plot(csv_path: str, cols: Optional[Iterable[str]] = None) -> Optional[PlotHandle]:
    """Start the live plot in a background process. Returns a PlotHandle or None."""
    try:
        from . import live_plot as lp
    except Exception as e:
        print(f"Could not import live_plot module: {e}")
        return None

    cols_arg: Optional[List[str]]
    if cols is None:
        cols_arg = None
    elif isinstance(cols, (list, tuple)):
        cols_arg = list(cols)
    else:
        cols_arg = [str(cols)]

    try:
        # start_live_plot returns (Process, Event); cmd_queue is no longer used
        # because we capture keys directly with pynput.
        proc, evt = lp.start_live_plot(csv_path, cols=cols_arg)
        print(f"Started live plot for {csv_path}")
        return PlotHandle(process=proc, stop_event=evt)
    except Exception as e:
        print(f"Could not start live plot: {e}")
        return None


def _plot_quit_requested(handle: Optional[PlotHandle]) -> bool:
    if handle is None or handle.stop_event is None:
        return False
    try:
        return bool(handle.stop_event.is_set())
    except Exception:
        return False


# --------------------------------------------------------------------------
# Sampling helpers shared by all modes
# --------------------------------------------------------------------------
def _abort_check(kb: KeyboardMonitor, plot: Optional[PlotHandle]) -> bool:
    """True if user pressed Esc or closed the plot window."""
    if kb.is_held("esc"):
        return True
    if _plot_quit_requested(plot):
        return True
    return False


def sample_for_duration(
    daq: DataAcquisition,
    duration_s: float,
    angle_label: Optional[int],
    kb: KeyboardMonitor,
    plot: Optional[PlotHandle],
    period_s: float,
) -> bool:
    """Sample (and optionally print) for `duration_s` seconds or until aborted.

    Returns True if completed normally, False if aborted by Esc/plot quit.
    """
    t0 = time.time()
    while time.time() - t0 < duration_s:
        if _abort_check(kb, plot):
            return False
        daq.sample_print_save(angle_label)
        time.sleep(period_s)
    return True


def wait_for_enter_or_esc(
    daq: DataAcquisition,
    angle_label: int,
    kb: KeyboardMonitor,
    plot: Optional[PlotHandle],
    period_s: float,
) -> bool:
    """Block until Enter (continue) or Esc/plot-quit (abort).

    Keeps sampling and printing while waiting. Returns True to continue,
    False to abort.
    """
    kb.drain()  # forget any keys pressed during the previous step
    while True:
        if _abort_check(kb, plot):
            return False
        if kb.was_pressed("enter"):
            return True
        daq.sample_print_save(angle_label)
        time.sleep(period_s)


# --------------------------------------------------------------------------
# User-input helpers
# --------------------------------------------------------------------------
def prompt_pins() -> List[str]:
    pos_pin = input("Enter position sensor pin (e.g., AIN0): ").strip() or "AIN0"
    therm_raw = input(
        "Enter thermocouple input pin(s) comma-separated (e.g., AIN1,AIN2) or leave blank: "
    ).strip()
    therm_pins = [p.strip() for p in therm_raw.split(",") if p.strip()] if therm_raw else []
    return [pos_pin] + therm_pins


def prompt_int(prompt: str, default: int) -> int:
    raw = input(prompt).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"Invalid integer; using default {default}.")
        return default


def prompt_yes_no(prompt: str, default_yes: bool = True) -> bool:
    raw = input(prompt).strip().lower()
    if not raw:
        return default_yes
    return raw not in ("n", "no")


# --------------------------------------------------------------------------
# CSV step parsing
# --------------------------------------------------------------------------
def parse_steps_csv(path: str, cfg: Config) -> List[Tuple[int, float]]:
    steps: List[Tuple[int, float]] = []
    with open(path, "r", encoding="utf-8") as f:
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
            except ValueError:
                continue
            if duration < 0:
                continue
            try:
                angle = int(a_part)
            except ValueError:
                a = a_part.lower()
                if a in ("up", "u"):
                    angle = cfg.position_up
                elif a in ("down", "d"):
                    angle = cfg.position_down
                else:
                    angle = cfg.position_zero
            steps.append((angle, duration))
    return steps


# --------------------------------------------------------------------------
# Modes
# --------------------------------------------------------------------------
def mode_take_data(cfg: Config, kb: KeyboardMonitor) -> None:
    input_pins = prompt_pins()
    show_plot = prompt_yes_no("Open live plot window? [Y/n]: ", default_yes=True)

    device = LabJackDevice(input_pins)
    plot: Optional[PlotHandle] = None
    servo: Optional[ServoCalibration] = None
    try:
        device.open()
        device.configure_pins()

        servo = ServoCalibration(
            device, cfg.core_frequency, cfg.pwm_dio, cfg.clock_divisor, cfg.desired_frequency
        )
        daq = DataAcquisition(device, servo)
        if len(input_pins) > 1:
            daq.enable_thermocouple_conversion(cjc_source=cfg.cjc_source, cjc_offset_c=cfg.cjc_offset_c)
        daq.create_output_file()

        if show_plot and daq.file_path:
            plot = launch_live_plot(os.path.join(os.getcwd(), daq.file_path), cols=input_pins)

        print("Capturing data. Press Esc (or Ctrl-C) to stop.")
        try:
            while True:
                if _abort_check(kb, plot):
                    break
                daq.sample_print_save(cfg.position_zero)
                time.sleep(cfg.take_data_period_s)
        except KeyboardInterrupt:
            pass

        print("Stopping capture...")
    finally:
        if servo is not None:
            try:
                servo.turn_off_pwm()
            except Exception:
                pass
        if plot is not None and _plot_alive(plot):
            _terminate_plot(plot)
        device.close()


def mode_calibrate(cfg: Config, kb: KeyboardMonitor) -> None:
    input_pins = prompt_pins()
    cfg.pwm_dio = prompt_int("Enter PWM DIO pin number (default 2): ", default=cfg.pwm_dio)

    device = LabJackDevice(input_pins)
    plot: Optional[PlotHandle] = None
    servo: Optional[ServoCalibration] = None
    try:
        device.open()
        device.configure_pins()

        servo = ServoCalibration(
            device, cfg.core_frequency, cfg.pwm_dio, cfg.clock_divisor, cfg.desired_frequency
        )
        daq = DataAcquisition(device, servo)
        if len(input_pins) > 1:
            daq.enable_thermocouple_conversion(cjc_source=cfg.cjc_source, cjc_offset_c=cfg.cjc_offset_c)
        daq.create_output_file()

        show_plot = prompt_yes_no("Open live plot window? [Y/n]: ", default_yes=True)

        print(
            "Choose mode:\n"
            "  1) Timed sequence (run steps for given durations)\n"
            "  2) Interactive (hold Up/Down arrows)\n"
            "  3) Import steps from CSV"
        )
        sub_mode = input("Enter 1, 2 or 3: ").strip()

        if show_plot and daq.file_path:
            plot = launch_live_plot(os.path.join(os.getcwd(), daq.file_path), cols=input_pins)

        if sub_mode == "1":
            _run_timed_sequence(cfg, daq, servo, kb, plot)
        elif sub_mode == "2":
            _run_interactive(cfg, daq, servo, kb, plot)
        elif sub_mode == "3":
            _run_csv_steps(cfg, daq, servo, kb, plot)
        else:
            print("Unknown mode; nothing to do.")
    finally:
        if servo is not None:
            try:
                servo.turn_off_pwm()
            except Exception:
                pass
        if plot is not None and _plot_alive(plot):
            _terminate_plot(plot)
        device.close()


def _run_timed_sequence(
    cfg: Config,
    daq: DataAcquisition,
    servo: ServoCalibration,
    kb: KeyboardMonitor,
    plot: Optional[PlotHandle],
) -> None:
    steps = prompt_int("Number of steps: ", default=0)
    if steps <= 0:
        print("No steps requested; exiting.")
        return

    sequence: List[Tuple[int, float]] = []
    for i in range(steps):
        d = input(f"Step {i+1} direction (up/down/zero): ").strip().lower()
        if d in ("up", "u"):
            angle = cfg.position_up
        elif d in ("down", "d"):
            angle = cfg.position_down
        else:
            angle = cfg.position_zero
        try:
            dur = float(input(f"Step {i+1} duration (seconds): ").strip())
        except ValueError:
            dur = 1.0
        sequence.append((angle, dur))

    for i, (angle, dur) in enumerate(sequence, start=1):
        print(f"Starting step {i}/{len(sequence)}: angle {angle}, duration {dur}s.")
        servo.set_servo_angle(angle)
        completed = sample_for_duration(daq, dur, angle, kb, plot, cfg.sample_period_s)
        servo.turn_off_pwm()
        if not completed:
            print("Aborted by user.")
            return


def _prompt_csv_steps(cfg: Config) -> Optional[List[Tuple[int, float]]]:
    """Prompt for a CSV file path until we get one that parses to >=1 valid step.

    Returns the parsed steps, or None if the user cancels (blank input).
    """
    while True:
        csv_path = input(
            "Enter CSV file path (or leave blank to cancel): "
        ).strip()
        if not csv_path:
            print("Cancelled CSV mode.")
            return None

        if not os.path.exists(csv_path):
            print(f"File not found: {csv_path!r}. Try again.")
            continue

        try:
            steps = parse_steps_csv(csv_path, cfg)
        except OSError as e:
            print(f"Error reading CSV: {e}. Try again.")
            continue

        if not steps:
            print("No valid steps parsed from that CSV. Try again.")
            continue

        return steps


def _run_csv_steps(
    cfg: Config,
    daq: DataAcquisition,
    servo: ServoCalibration,
    kb: KeyboardMonitor,
    plot: Optional[PlotHandle],
) -> None:
    steps = _prompt_csv_steps(cfg)
    if steps is None:
        return

    for i, (angle, dur) in enumerate(steps, start=1):
        print(f"Starting step {i}/{len(steps)}: angle {angle}, duration {dur}s. Esc to abort.")
        servo.set_servo_angle(angle)
        completed = sample_for_duration(daq, dur, angle, kb, plot, cfg.sample_period_s)
        servo.turn_off_pwm()
        if not completed:
            print("Aborted by user.")
            return

        print(f"Step {i} complete. Press Enter to continue, Esc to abort.")
        if not wait_for_enter_or_esc(daq, angle, kb, plot, cfg.sample_period_s):
            print("Aborted by user.")
            return


def _run_interactive(
    cfg: Config,
    daq: DataAcquisition,
    servo: ServoCalibration,
    kb: KeyboardMonitor,
    plot: Optional[PlotHandle],
) -> None:
    print("Interactive mode: hold Up/Down to move servo; press Esc to exit.")
    servo.set_servo_angle(cfg.position_zero)
    last_angle: Optional[int] = cfg.position_zero

    try:
        while True:
            if _abort_check(kb, plot):
                print("Exiting interactive mode.")
                break

            if kb.is_held("up"):
                current_angle = cfg.position_up
            elif kb.is_held("down"):
                current_angle = cfg.position_down
            else:
                current_angle = cfg.position_zero

            # Reconfigure PWM only when the target angle actually changes.
            # Without this guard the servo gets reset every loop iteration,
            # which is wasteful and (on the T7) can cause visible jitter.
            if current_angle != last_angle:
                servo.set_servo_angle(current_angle)
                last_angle = current_angle

            daq.sample_print_save(current_angle)
            time.sleep(cfg.sample_period_s)
    except KeyboardInterrupt:
        print("Interactive aborted by user.")
    finally:
        servo.turn_off_pwm()


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def main() -> int:
    cfg = Config()
    kb: Optional[KeyboardMonitor] = None
    try:
        kb = KeyboardMonitor()
    except RuntimeError as e:
        print(f"Keyboard input unavailable: {e}")
        return 1

    try:
        print(
            "Select operation:\n"
            "  1) Calibration (timed / interactive / CSV)\n"
            "  2) Take data (print + live-plot specified AIN pins)"
        )
        primary = input("Enter 1 or 2: ").strip()

        if primary == "2":
            mode_take_data(cfg, kb)
        elif primary == "1":
            mode_calibrate(cfg, kb)
        else:
            print("Unknown selection; exiting.")
            return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception:
        print("An error occurred:")
        traceback.print_exc()
        return 1
    finally:
        if kb is not None:
            kb.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
