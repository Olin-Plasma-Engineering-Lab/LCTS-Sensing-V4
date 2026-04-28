"""Main window for the LabJack T7 calibration GUI.

Holds the top-level state machine (IDLE -> CONNECTED -> CAPTURING) and
orchestrates the embedded plot widget, step table widgets, and hardware
modules. All hardware I/O happens here through `LabJackDevice`,
`ServoCalibration`, and `DataAcquisition` from the parent package.
"""

from __future__ import annotations

import os
import time
import traceback
from collections import deque
from enum import Enum, auto
from typing import Deque, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..data_acquisition import DataAcquisition, Sample
from ..labjack_device import LabJackDevice
from ..servo_calibration import ServoCalibration

from .constants import (
    DEFAULT_CLOCK_DIVISOR,
    DEFAULT_CORE_FREQ_HZ,
    DEFAULT_POSITION_DOWN,
    DEFAULT_POSITION_UP,
    DEFAULT_POSITION_ZERO,
    DEFAULT_PWM_DIO,
    DEFAULT_PWM_FREQ_HZ,
    PLOT_BUFFER_SAMPLES,
    SAMPLE_PERIOD_MS,
)
from .live_plot_widget import LivePlotWidget
from .step_table import AngleStepTable, DirectionStepTable, parse_steps_csv


# --------------------------------------------------------------------------
# Application state machine
# --------------------------------------------------------------------------
class State(Enum):
    IDLE = auto()         # no device open
    CONNECTED = auto()    # device open but not sampling
    CAPTURING = auto()    # sampling active


# --------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------
class CalibrateMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LabJack T7 Calibration")
        self.resize(1400, 1000)

        # Hardware handles
        self._device: Optional[LabJackDevice] = None
        self._servo: Optional[ServoCalibration] = None
        self._daq: Optional[DataAcquisition] = None
        self._state = State.IDLE
        self._last_servo_angle: Optional[int] = None

        # Plot ring buffers
        self._buf_pos: Deque[float] = deque(maxlen=PLOT_BUFFER_SAMPLES)
        self._buf_therm: dict = {}
        self._buf_cjc: Deque[float] = deque(maxlen=PLOT_BUFFER_SAMPLES)
        self._sample_counter = 0

        # Timed / CSV iteration state
        self._timed_steps: List[Tuple[int, float]] = []
        self._timed_idx = 0
        self._timed_step_started_at: Optional[float] = None
        self._timed_paused_for_enter = False
        self._capture_mode: Optional[str] = None

        # Sampling timer
        self._sample_timer = QTimer(self)
        self._sample_timer.setInterval(SAMPLE_PERIOD_MS)
        self._sample_timer.timeout.connect(self._on_sample_tick)

        self._build_ui()
        self._update_button_enables()

    # ==================================================================
    # UI construction
    # ==================================================================
    # Mode codes used internally by the capture lifecycle. Kept as an
    # ordered list so the picker dropdown shows them in a stable order.
    _MODES = (
        ("take_data",   "Take data"),
        ("interactive", "Interactive"),
        ("timed",       "Timed sequence"),
        ("csv",         "CSV import"),
    )

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        self._top_tabs = QTabWidget()
        self._top_tabs.addTab(self._build_setup_tab(), "Setup")
        self._top_tabs.addTab(self._build_live_tab(), "Live data")
        root.addWidget(self._top_tabs, stretch=1)

        self.setStatusBar(QStatusBar(self))

    # ==================================================================
    # Setup tab
    # ==================================================================
    def _build_setup_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(self._build_config_box())
        layout.addWidget(self._build_mode_picker_box(), stretch=1)
        layout.addStretch()
        return w

    def _build_config_box(self) -> QWidget:
        box = QGroupBox("Device configuration")
        layout = QGridLayout(box)

        layout.addWidget(QLabel("Position pin:"), 0, 0)
        self._cmb_pos = QComboBox()
        self._cmb_pos.addItems([f"AIN{i}" for i in range(14)])
        self._cmb_pos.setCurrentText("AIN0")
        layout.addWidget(self._cmb_pos, 0, 1)

        layout.addWidget(QLabel("Thermocouple pins:"), 0, 2)
        self._txt_tcs = QLineEdit("AIN1,AIN2")
        self._txt_tcs.setPlaceholderText("comma-separated, blank = no TCs")
        self._txt_tcs.setToolTip(
            "Comma-separated list of AIN names, e.g. 'AIN1,AIN2'. "
            "Leave blank if no thermocouples are connected."
        )
        layout.addWidget(self._txt_tcs, 0, 3)

        layout.addWidget(QLabel("PWM DIO:"), 1, 0)
        self._spin_pwm_dio = QSpinBox()
        self._spin_pwm_dio.setRange(0, 22)
        self._spin_pwm_dio.setValue(DEFAULT_PWM_DIO)
        layout.addWidget(self._spin_pwm_dio, 1, 1)

        layout.addWidget(QLabel("CJC source:"), 1, 2)
        self._cmb_cjc = QComboBox()
        self._cmb_cjc.addItem("device (T7 internal sensor)", "device")
        self._cmb_cjc.addItem("air (ambient estimate)", "air")
        self._cmb_cjc.addItem("fixed 25 C", 25.0)
        layout.addWidget(self._cmb_cjc, 1, 3)

        self._btn_connect = QPushButton("Connect")
        self._btn_disconnect = QPushButton("Disconnect")
        layout.addWidget(self._btn_connect, 0, 4)
        layout.addWidget(self._btn_disconnect, 1, 4)
        self._btn_connect.clicked.connect(self._on_connect)
        self._btn_disconnect.clicked.connect(self._on_disconnect)

        return box

    def _build_mode_picker_box(self) -> QWidget:
        """Mode picker + per-mode configuration stack.

        The Live tab reads the picker to know what `_start_capture()` should
        do, so this widget owns all the per-mode state (angles, step tables,
        file path) but never directly starts a capture itself.
        """
        box = QGroupBox("Mode")
        outer = QVBoxLayout(box)

        picker_row = QHBoxLayout()
        picker_row.addWidget(QLabel("Active mode:"))
        self._cmb_mode = QComboBox()
        for code, label in self._MODES:
            self._cmb_mode.addItem(label, code)
        picker_row.addWidget(self._cmb_mode)
        picker_row.addStretch()
        outer.addLayout(picker_row)

        # QStackedWidget swaps in mode-specific configuration.
        self._mode_stack = QStackedWidget()
        # Build pages in the same order as _MODES so combo box index lines
        # up with stack index.
        self._mode_stack.addWidget(self._build_take_data_page())
        self._mode_stack.addWidget(self._build_interactive_page())
        self._mode_stack.addWidget(self._build_timed_page())
        self._mode_stack.addWidget(self._build_csv_page())
        outer.addWidget(self._mode_stack, stretch=1)

        self._cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        return box

    def _build_take_data_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel(
            "Continuously sample and log the configured AIN pins. "
            "No servo motion. Press Start on the Live data tab to begin."
        ))
        layout.addStretch()
        return w

    def _build_interactive_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        controls = QGridLayout()
        controls.addWidget(QLabel("Zero angle:"), 0, 0)
        self._spin_zero = QSpinBox()
        self._spin_zero.setRange(0, 180)
        self._spin_zero.setValue(DEFAULT_POSITION_ZERO)
        controls.addWidget(self._spin_zero, 0, 1)

        controls.addWidget(QLabel("Up angle:"), 0, 2)
        self._spin_up = QSpinBox()
        self._spin_up.setRange(0, 180)
        self._spin_up.setValue(DEFAULT_POSITION_UP)
        controls.addWidget(self._spin_up, 0, 3)

        controls.addWidget(QLabel("Down angle:"), 0, 4)
        self._spin_down = QSpinBox()
        self._spin_down.setRange(0, 180)
        self._spin_down.setValue(DEFAULT_POSITION_DOWN)
        controls.addWidget(self._spin_down, 0, 5)
        layout.addLayout(controls)

        layout.addWidget(QLabel(
            "While capturing, hold the Up/Down buttons on the Live data tab "
            "(or arrow keys with the window focused) to drive the servo."
        ))
        layout.addStretch()
        return w

    def _build_timed_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel(
            "Direction-based step list. Each row runs for the given duration. "
            "Directions resolve to the Up / Zero / Down angles set on the "
            "Interactive page."
        ))

        self._timed_table = DirectionStepTable()
        self._timed_table.add_row("up", 2.0)
        self._timed_table.add_row("zero", 1.0)
        self._timed_table.add_row("down", 2.0)
        layout.addWidget(self._timed_table, stretch=1)
        return w

    def _build_csv_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        file_row = QHBoxLayout()
        self._lbl_csv_path = QLabel("(no file loaded)")
        self._btn_browse_csv = QPushButton("Load CSV...")
        file_row.addWidget(self._btn_browse_csv)
        file_row.addWidget(self._lbl_csv_path, stretch=1)
        layout.addLayout(file_row)

        self._csv_table = AngleStepTable()
        layout.addWidget(self._csv_table, stretch=1)

        self._chk_pause = QCheckBox("Pause for confirmation between steps")
        self._chk_pause.setChecked(True)
        layout.addWidget(self._chk_pause)

        self._btn_browse_csv.clicked.connect(self._on_browse_csv)
        return w

    # ==================================================================
    # Live data tab
    # ==================================================================
    def _build_live_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self._plot = LivePlotWidget()
        layout.addWidget(self._plot, stretch=1)

        layout.addLayout(self._build_status_row())
        layout.addLayout(self._build_live_controls_row())
        return w

    def _build_status_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._lbl_angle = QLabel("Angle: -")
        self._lbl_cjc = QLabel("CJC: -")
        self._lbl_count = QLabel("Samples: 0")
        self._lbl_file = QLabel("File: -")
        self._lbl_file.setMinimumWidth(360)
        for w in (self._lbl_angle, self._lbl_cjc, self._lbl_count, self._lbl_file):
            w.setStyleSheet("padding: 4px 12px;")
            row.addWidget(w)
        row.addStretch()
        return row

    def _build_live_controls_row(self) -> QHBoxLayout:
        row = QHBoxLayout()

        self._lbl_active_mode = QLabel("Mode: Take data")
        self._lbl_active_mode.setStyleSheet("padding: 4px 12px; font-weight: bold;")
        row.addWidget(self._lbl_active_mode)
        row.addStretch()

        # Up / Down buttons live next to Start so users have everything
        # they need on the Live tab during interactive runs. They're hidden
        # except when interactive mode is active.
        self._btn_down = QPushButton("Down (press & hold)")
        self._btn_up = QPushButton("Up (press & hold)")
        row.addWidget(self._btn_down)
        row.addWidget(self._btn_up)

        self._btn_start = QPushButton("Start")
        self._btn_stop = QPushButton("Stop")
        self._btn_continue = QPushButton("Continue")
        self._btn_continue.setEnabled(False)
        row.addWidget(self._btn_start)
        row.addWidget(self._btn_stop)
        row.addWidget(self._btn_continue)

        self._btn_start.clicked.connect(self._on_start_clicked)
        self._btn_stop.clicked.connect(self._stop_capture)
        self._btn_continue.clicked.connect(self._on_csv_continue)
        self._btn_up.pressed.connect(lambda: self._set_interactive_direction("up"))
        self._btn_up.released.connect(lambda: self._set_interactive_direction("zero"))
        self._btn_down.pressed.connect(lambda: self._set_interactive_direction("down"))
        self._btn_down.released.connect(lambda: self._set_interactive_direction("zero"))
        return row

    # ==================================================================
    # Mode-picker glue
    # ==================================================================
    def _current_mode(self) -> str:
        return self._cmb_mode.currentData() or "take_data"

    def _on_mode_changed(self, index: int) -> None:
        self._mode_stack.setCurrentIndex(index)
        # Update the Live tab's mode label so the user sees what Start does.
        label = self._cmb_mode.currentText()
        self._lbl_active_mode.setText(f"Mode: {label}")
        self._update_button_enables()

    def _on_start_clicked(self) -> None:
        self._start_capture(self._current_mode())

    # ==================================================================
    # Connect / disconnect
    # ==================================================================
    def _input_pins(self) -> List[str]:
        pos = self._cmb_pos.currentText().strip()
        tc_raw = self._txt_tcs.text().strip()
        tcs = [p.strip() for p in tc_raw.split(",") if p.strip()] if tc_raw else []
        return [pos] + tcs

    def _cjc_source(self):
        return self._cmb_cjc.currentData()

    def _on_connect(self) -> None:
        if self._state != State.IDLE:
            return
        pins = self._input_pins()
        if len(pins) != len(set(pins)):
            self._error("Pin list contains duplicates.")
            return
        try:
            self._device = LabJackDevice(pins)
            self._device.open()
            self._device.configure_pins()
            self._servo = ServoCalibration(
                self._device,
                DEFAULT_CORE_FREQ_HZ,
                self._spin_pwm_dio.value(),
                DEFAULT_CLOCK_DIVISOR,
                DEFAULT_PWM_FREQ_HZ,
            )
            self._daq = DataAcquisition(self._device, self._servo)
            if len(pins) > 1:
                self._daq.enable_thermocouple_conversion(cjc_source=self._cjc_source())
            self._daq.create_output_file()
        except Exception as e:
            traceback.print_exc()
            self._error(f"Connect failed: {e}")
            self._cleanup_hardware()
            return

        self._state = State.CONNECTED
        show_cjc = self._daq.convert_thermocouples
        self._plot.configure_channels(pins, show_cjc=show_cjc)
        self._reset_buffers(pins, show_cjc)
        self._lbl_file.setText(f"File: {os.path.basename(self._daq.file_path)}")
        self.statusBar().showMessage("Connected.")
        self._update_button_enables()

    def _on_disconnect(self) -> None:
        self._stop_capture()
        self._cleanup_hardware()
        self._state = State.IDLE
        self.statusBar().showMessage("Disconnected.")
        self._lbl_file.setText("File: -")
        self._update_button_enables()

    def _cleanup_hardware(self) -> None:
        if self._servo is not None:
            try:
                self._servo.turn_off_pwm()
            except Exception:
                pass
            self._servo = None
        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None
        self._daq = None
        self._last_servo_angle = None

    # ==================================================================
    # Capture lifecycle
    # ==================================================================
    def _start_capture(self, mode: str) -> None:
        if self._state == State.IDLE:
            self._error("Connect to the device first.")
            return
        if self._state == State.CAPTURING:
            return

        if mode == "timed":
            direction_steps = self._timed_table.steps()
            if not direction_steps:
                self._error("Timed sequence is empty.")
                return
            self._timed_steps = [
                (self._resolve_direction(d), dur) for d, dur in direction_steps
            ]
            self._timed_idx = 0
            self._timed_step_started_at = None
        elif mode == "csv":
            self._timed_steps = self._csv_table.steps()
            if not self._timed_steps:
                self._error("CSV step table is empty. Load a CSV first.")
                return
            self._timed_idx = 0
            self._timed_step_started_at = None
            self._timed_paused_for_enter = False
            self._btn_continue.setEnabled(False)
        elif mode == "interactive":
            try:
                self._servo.set_servo_angle(self._spin_zero.value())
                self._last_servo_angle = self._spin_zero.value()
            except Exception as e:
                self._error(f"Servo error: {e}")
                return

        self._capture_mode = mode
        self._state = State.CAPTURING
        self._sample_timer.start()
        self.statusBar().showMessage(f"Capturing ({mode})...")
        # Auto-switch to the Live tab so the user sees the plot immediately.
        # Index 1 is the Live data tab (Setup is 0).
        self._top_tabs.setCurrentIndex(1)
        self._update_button_enables()

    def _stop_capture(self) -> None:
        if self._state != State.CAPTURING:
            return
        self._sample_timer.stop()
        if self._servo is not None:
            try:
                self._servo.turn_off_pwm()
            except Exception:
                pass
        self._last_servo_angle = None
        self._state = State.CONNECTED
        self._timed_paused_for_enter = False
        self._btn_continue.setEnabled(False)
        self.statusBar().showMessage("Stopped.")
        self._update_button_enables()

    # ==================================================================
    # Sampling tick
    # ==================================================================
    def _on_sample_tick(self) -> None:
        if self._daq is None:
            self._stop_capture()
            return
        try:
            sample = self._daq.sample_print_save()
        except Exception as e:
            traceback.print_exc()
            self._error(f"Sample failed: {e}")
            self._stop_capture()
            return

        self._append_sample(sample)
        self._update_status_labels(sample)
        self._refresh_plot()

        if self._capture_mode == "timed":
            self._tick_timed_sequence()
        elif self._capture_mode == "csv":
            self._tick_csv_sequence()

    def _append_sample(self, sample: Sample) -> None:
        self._sample_counter += 1
        if not sample.pin_names:
            return
        self._buf_pos.append(float(sample.converted_values[0]))
        for i, pin in enumerate(sample.pin_names[1:], start=1):
            buf = self._buf_therm.setdefault(pin, deque(maxlen=PLOT_BUFFER_SAMPLES))
            buf.append(float(sample.converted_values[i]))
        if sample.cjc_temp_c is not None:
            self._buf_cjc.append(float(sample.cjc_temp_c))

    def _refresh_plot(self) -> None:
        n = len(self._buf_pos)
        if n == 0:
            return
        x = np.arange(n, dtype=float)
        pos = np.array(self._buf_pos, dtype=float)
        therm = {pin: np.array(buf, dtype=float) for pin, buf in self._buf_therm.items()}
        cjc = np.array(self._buf_cjc, dtype=float) if self._buf_cjc else None
        self._plot.update_data(x, pos, therm, cjc)

    def _update_status_labels(self, sample: Sample) -> None:
        if self._last_servo_angle is not None:
            self._lbl_angle.setText(f"Angle: {self._last_servo_angle}")
        else:
            self._lbl_angle.setText("Angle: -")
        if sample.cjc_temp_c is not None:
            self._lbl_cjc.setText(f"CJC: {sample.cjc_temp_c:.2f} C")
        else:
            self._lbl_cjc.setText("CJC: -")
        self._lbl_count.setText(f"Samples: {self._sample_counter}")

    def _reset_buffers(self, pins: List[str], show_cjc: bool) -> None:
        self._buf_pos.clear()
        self._buf_therm = {pin: deque(maxlen=PLOT_BUFFER_SAMPLES) for pin in pins[1:]}
        if show_cjc:
            self._buf_cjc = deque(maxlen=PLOT_BUFFER_SAMPLES)
        else:
            self._buf_cjc = deque(maxlen=0)
        self._sample_counter = 0

    # ==================================================================
    # Interactive mode
    # ==================================================================
    def _resolve_direction(self, direction: str) -> int:
        """Map 'up' / 'down' / 'zero' to the configured integer angle."""
        d = direction.lower()
        if d in ("up", "u"):
            return self._spin_up.value()
        if d in ("down", "d"):
            return self._spin_down.value()
        return self._spin_zero.value()

    def _set_interactive_direction(self, direction: str) -> None:
        if self._state != State.CAPTURING or self._capture_mode != "interactive":
            return
        target = self._resolve_direction(direction)
        if target == self._last_servo_angle:
            return
        try:
            self._servo.set_servo_angle(target)
            self._last_servo_angle = target
        except Exception as e:
            self._error(f"Servo error: {e}")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (self._state == State.CAPTURING
                and self._capture_mode == "interactive"
                and not event.isAutoRepeat()):
            if event.key() == Qt.Key_Up:
                self._set_interactive_direction("up")
                return
            if event.key() == Qt.Key_Down:
                self._set_interactive_direction("down")
                return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if (self._state == State.CAPTURING
                and self._capture_mode == "interactive"
                and not event.isAutoRepeat()):
            if event.key() in (Qt.Key_Up, Qt.Key_Down):
                self._set_interactive_direction("zero")
                return
        super().keyReleaseEvent(event)

    # ==================================================================
    # Timed / CSV sequencing
    # ==================================================================
    def _tick_timed_sequence(self) -> None:
        if self._timed_idx >= len(self._timed_steps):
            self._stop_capture()
            self.statusBar().showMessage("Timed sequence complete.")
            return
        angle, duration = self._timed_steps[self._timed_idx]
        if self._timed_step_started_at is None:
            try:
                self._servo.set_servo_angle(angle)
                self._last_servo_angle = angle
            except Exception as e:
                self._error(f"Servo error: {e}")
                self._stop_capture()
                return
            self._timed_step_started_at = time.time()
        elif time.time() - self._timed_step_started_at >= duration:
            try:
                self._servo.turn_off_pwm()
            except Exception:
                pass
            self._timed_idx += 1
            self._timed_step_started_at = None

    def _tick_csv_sequence(self) -> None:
        if self._timed_paused_for_enter:
            return
        if self._timed_idx >= len(self._timed_steps):
            self._stop_capture()
            self.statusBar().showMessage("CSV sequence complete.")
            return
        angle, duration = self._timed_steps[self._timed_idx]
        if self._timed_step_started_at is None:
            try:
                self._servo.set_servo_angle(angle)
                self._last_servo_angle = angle
            except Exception as e:
                self._error(f"Servo error: {e}")
                self._stop_capture()
                return
            self._timed_step_started_at = time.time()
        elif time.time() - self._timed_step_started_at >= duration:
            try:
                self._servo.turn_off_pwm()
            except Exception:
                pass
            self._timed_idx += 1
            self._timed_step_started_at = None
            if self._chk_pause.isChecked() and self._timed_idx < len(self._timed_steps):
                self._timed_paused_for_enter = True
                self._btn_continue.setEnabled(True)
                self.statusBar().showMessage(
                    f"Step {self._timed_idx} complete. Click Continue for next step."
                )

    def _on_csv_continue(self) -> None:
        if not self._timed_paused_for_enter:
            return
        self._timed_paused_for_enter = False
        self._btn_continue.setEnabled(False)
        self.statusBar().showMessage("Capturing (csv)...")

    def _on_browse_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open step CSV", os.getcwd(),
            "CSV files (*.csv);;All files (*)"
        )
        if not path:
            return
        try:
            steps = parse_steps_csv(
                path,
                up_angle=self._spin_up.value(),
                down_angle=self._spin_down.value(),
                zero_angle=self._spin_zero.value(),
            )
        except Exception as e:
            self._error(f"Could not read CSV: {e}")
            return
        if not steps:
            self._error("No valid steps found in that file.")
            return
        self._csv_table.load_steps(steps)
        self._lbl_csv_path.setText(path)

    # ==================================================================
    # Tab / button enable management
    # ==================================================================
    # NOTE: there is no longer an `_on_tab_changed` for the top-level Setup
    # / Live tabs — switching between them shouldn't disturb a capture in
    # progress. Mode changes via the picker also don't stop capture (the
    # picker is locked while CAPTURING in `_update_button_enables`).

    def _update_button_enables(self) -> None:
        connected = self._state in (State.CONNECTED, State.CAPTURING)
        capturing = self._state == State.CAPTURING
        mode = self._current_mode()

        self._btn_connect.setEnabled(self._state == State.IDLE)
        self._btn_disconnect.setEnabled(connected)

        # Start / Stop on the Live tab.
        self._btn_start.setEnabled(connected and not capturing)
        self._btn_stop.setEnabled(capturing)

        # Up / Down only for interactive mode while capturing. Hide
        # entirely outside interactive so they don't take screen space.
        is_interactive = (mode == "interactive")
        self._btn_up.setVisible(is_interactive)
        self._btn_down.setVisible(is_interactive)
        self._btn_up.setEnabled(capturing and is_interactive)
        self._btn_down.setEnabled(capturing and is_interactive)

        # Continue is only relevant in CSV mode.
        self._btn_continue.setVisible(mode == "csv")

        # Setup controls locked while connected (avoid changing pins
        # mid-run) and the mode picker is locked while capturing (changing
        # mode mid-capture is nonsensical; stop first).
        for w in (self._cmb_pos, self._txt_tcs, self._spin_pwm_dio, self._cmb_cjc):
            w.setEnabled(self._state == State.IDLE)
        self._cmb_mode.setEnabled(not capturing)

    # ==================================================================
    # Misc
    # ==================================================================
    def _error(self, msg: str) -> None:
        QMessageBox.warning(self, "Error", msg)
        self.statusBar().showMessage(msg)

    def closeEvent(self, event):
        self._stop_capture()
        self._cleanup_hardware()
        super().closeEvent(event)
