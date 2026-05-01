# LCTS-Sensing-V4

## Purpose
The project in this repo is used to control a LabJack T7 data acquisition device. Our uses require analog pins for measuring signals from RVDTs, thermocouples, etc. and digital pins for controlling a servo using PWM.

## Set Up
Using the scripts requires the LabJack drivers (https://support.labjack.com/docs/ljm-software-installer-downloads-t4-t7-t8-digit).

The Python implementation also requires Python 3.9 or newer.

## Python Implementation

### Environment
Create a virtual environment using `python -m venv sensing` to create an environment called `sensing`. Do this in the directory where this repo exists. Once the environment is created it does not need to be created again unless it gets deleted. You may have to re-enter the environment when you open a new terminal/command prompt though.

Enter the environment:
- For Windows: `sensing\Scripts\activate`
- For Linux/macOS: `source sensing/bin/activate`

Run `pip install -r calibrate_py/requirements.txt` to install dependencies. This also only has to be done once after creating and entering the environment for the first time.

### Running

Two entry points are available. They share the same hardware code, so anything you can do from one you can do from the other.

**GUI (recommended).** Run `python run_gui.py` to launch the desktop application. The window has two tabs:

- **Setup** — pick the position pin, thermocouple pins, PWM DIO, and CJC source; connect to the device; choose a mode (Take data, Interactive, Timed sequence, or CSV import) and configure it.
- **Live data** — shows the live plot, current angle, CJC temperature, sample count, and the CSV file name. Start / Stop controls live here. Up / Down hold-to-move buttons appear in Interactive mode; a Continue button appears in CSV mode for stepping past pause-between-step prompts. Arrow keys also drive the servo in Interactive mode when the window has focus.

The GUI auto-switches to the Live data tab when capture starts so the plot is immediately visible. Switching back to Setup mid-run does not stop the capture.

**CLI.** Run `python run_calibrate.py` for a text-based interface that walks through the same modes via prompts. Useful on machines without a desktop environment, or for scripted runs.

### Cross-platform notes

The GUI uses [PySide6](https://pypi.org/project/PySide6/) and the CLI uses [pynput](https://pypi.org/project/pynput/) for keyboard input. Both are cross-platform but each has small caveats:

- **macOS:** the first time the CLI runs, you'll need to grant your terminal application "Input Monitoring" / "Accessibility" permission in System Settings, otherwise hold-to-move arrow-key detection will silently fail. The GUI doesn't need this since it captures arrow keys through Qt.
- **Linux:** the CLI's interactive arrow-key mode requires an X server (or a uinput-capable backend). On a headless box, use the GUI's Interactive mode (it works wherever Qt runs) or the timed/CSV modes.
- **Windows:** both work out of the box.

### CSV step format (CSV import mode)
One step per line, two columns:

```
up,2.5
down,2.5
zero,1.0
135,3.0
```

The first field is either a direction keyword (`up`, `down`, `zero`) or an explicit integer angle. The second field is the duration in seconds. Between steps the script pauses with the servo disabled until you press Continue (GUI) or Enter (CLI), or Esc to abort.

### Cold-junction compensation (CJC)
When more than one input pin is configured, the script treats the first pin as the position sensor and any remaining pins as K-type thermocouples, converting their voltages to degrees Celsius using NIST ITS-90 polynomials.

The cold-junction temperature is read **live** from the T7 by default (`TEMPERATURE_DEVICE_K`). A -3 C offset is applied to match the screw-terminal temperature, since the T7's internal sensor reads a few degrees warmer than the terminals during steady-state operation. The CJC source can be changed in the GUI (Setup → Device configuration) or in the `Config` block of `calibrate.py`:

- `"device"` (default): T7 internal sensor. Best for thermocouples wired to AIN0-AIN3 directly.
- `"air"`: T7 ambient estimate. Best for thermocouples wired to a CB37 expansion board.
- a fixed float (e.g. `25.0`): static CJC value in degrees C.

When thermocouple conversion is enabled, the output CSV gains a `CJC_C` column so the cold-junction temperature can be checked offline.

### Project layout

```
LCTS-Sensing-V4/
├── run_gui.py                  GUI runner
├── run_calibrate.py            CLI runner
├── requirements.txt
├── calibrate_py/
│   ├── calibrate.py            CLI orchestration
│   ├── data_acquisition.py     Sampling, CJC, CSV logging
│   ├── labjack_device.py       Device open / close / per-pin range & resolution
│   ├── servo_calibration.py    PWM math for servo control
│   ├── thermocouples.py        K-type ITS-90 conversion
│   ├── live_plot.py            Standalone live CSV plotter (used by the CLI)
│   └── gui/                    PySide6 GUI
│       ├── main_window.py      Window, state machine, mode dispatch
│       ├── live_plot_widget.py Embedded matplotlib canvas
│       ├── step_table.py       Angle and direction step tables; CSV parser
│       └── constants.py        Shared defaults (sample period, etc.)
```

## C# Implementation (archive)
The C# implementation is the original attempt for interfacing with the LabJack. While it works reliably, it is harder to add features in C# and isn't immediately compatible with Mac. Further implementations are in Python.

### Implementation
The project contains a `Device` namespace containing helpers for various control of the device:

#### `LabJackDevice`
This contains helpers for establishing a connection with the device, configuring pins for analog reading, disposing of the device, etc.

#### `DataAcquisition`
This contains helpers for reading + printing data, creating output files, etc.

#### `ServoCalibration`
This contains helpers for controlling a servo connected to the T7. It produces PWM signals that can be used to control a servo.