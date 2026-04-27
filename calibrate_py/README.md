# calibrate_py

Python port of the C# `Calibrate` application for the LabJack T7. Reads RVDT
position and thermocouple voltages, saves to CSV, plots live, and (optionally)
controls a servo connected to a digital output pin for calibration sweeps.

## Modes

1. **Calibration**
   - **Timed sequence:** enter a list of `(direction, duration)` steps.
   - **Interactive:** hold Up / Down arrow keys to drive the servo, Esc to exit.
   - **CSV import:** read steps from a CSV file (one `angle,duration` per line).
2. **Take data:** continuously sample and live-plot AIN pins, no servo motion.

## Cross-platform notes

Keyboard input uses [`pynput`](https://pypi.org/project/pynput/) so the same
script runs on Windows, macOS, and Linux.

- **macOS:** the first time you run the script, you'll need to grant your
  terminal application "Input Monitoring" / "Accessibility" permission in
  System Settings. Without this, hold-to-move detection will silently fail.
- **Linux:** requires either an X server (run from a graphical session) or
  a uinput-capable backend. SSH into a headless box won't work for the
  interactive arrow-key mode; use the timed or CSV modes instead.
- **Windows:** works out of the box.

## Setup

```
pip install -r calibrate_py/requirements.txt
```

If the LabJack `Python_LJM_2025_04_24` folder is not on `PYTHONPATH`, place it
as a sibling of the `calibrate_py` folder; the package will pick it up.

## Run

From the workspace root:

```
python -m calibrate_py.calibrate
```

or directly:

```
python calibrate_py/calibrate.py
```

## CSV step format

One step per line, two columns:

```
up,2.5
down,2.5
zero,1.0
135,3.0
```

The first field is either a direction keyword (`up`, `down`, `zero`) or an
explicit integer angle. The second field is the duration in seconds. Between
steps, the script pauses with the servo disabled until you press Enter to
continue (or Esc to abort).

## Cold-junction compensation (CJC)

When more than one input pin is configured, the script treats the first pin as
the position sensor and any remaining pins as K-type thermocouples, and
converts their voltages to degrees Celsius using NIST ITS-90 polynomials.

The cold-junction temperature is read **live** from the T7 by default. The
T7's internal sensor (`TEMPERATURE_DEVICE_K`) is a few degrees warmer than
the screw terminals during steady-state operation, so a -3 C offset is
applied by default to match the screw-terminal temperature reasonably well
(per LabJack T-Series Datasheet section 18.0).

To override, edit the `Config` block in `calibrate.py`:

```python
@dataclass
class Config:
    ...
    cjc_source: object = "device"   # "device" | "air" | float (fixed C)
    cjc_offset_c: float = -3.0
```

- `"device"`: read `TEMPERATURE_DEVICE_K`. Best for thermocouples wired to
  the T7's built-in AIN0-AIN3 terminals.
- `"air"`: read `TEMPERATURE_AIR_K` (estimated ambient). Best when
  thermocouples are on a CB37 expansion board.
- a float (e.g. `25.0`): use a fixed CJC temperature in degrees C and skip
  the live read. Lowest CPU/LJM overhead, but room temperature drift will
  show up as apparent thermocouple drift.

For best accuracy, LabJack recommends adding an external LM34CAZ sensor on a
spare AIN; if you wire one up, set `cjc_source` to that AIN's name and adjust
`cjc_offset_c` accordingly (the LM34's slope/offset can be applied in
post-processing or by extending `enable_thermocouple_conversion`).

The CSV header now includes a `CJC_C` column when conversion is enabled, so
you can sanity-check the cold-junction temperature offline.

## Sampling cost

Each sampling iteration performs **one** LJM `eReadNames` call that batches
the position sensor, all thermocouples, and the CJC register together. The
result is shared between console printing and CSV logging, so doubling
sampling cost by reading twice (once for print, once for save) is no longer
a concern.
