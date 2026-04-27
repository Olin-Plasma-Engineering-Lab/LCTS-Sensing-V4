"""Data acquisition for LabJack T7 with optional live CJC and thermocouple
conversion.

The original C# / first-pass Python implementation made two LJM reads per
loop iteration (one for printing, one for saving) and used a hard-coded
25 °C cold-junction temperature. This version:

  * Performs a single LJM `eReadNames` call per sample, including the CJC
    register if thermocouple conversion is enabled.
  * Reads the cold-junction temperature live from the T7 by default, with
    a configurable offset to reflect the screw-terminal vs. on-board sensor
    delta noted in LabJack's documentation.
  * Caches the latest sample so `print_data` and `read_and_save` (or the
    convenience `sample_print_save`) operate on the same reading instead
    of triggering two separate LJM transactions.
"""

from __future__ import annotations

import datetime
import os
from dataclasses import dataclass, field
from typing import List, Optional, Union

import numpy as np
from labjack.ljm import ljm

from .thermocouples import ktype_with_cjc


# Modbus register names exposed by the T7 LJM library.
# https://support.labjack.com/docs/18-0-internal-temp-sensor-t-series-datasheet
_TEMP_DEVICE_K = "TEMPERATURE_DEVICE_K"   # internal sensor, near AIN0-3 terminals
_TEMP_AIR_K = "TEMPERATURE_AIR_K"          # estimated ambient, good for CB37


@dataclass
class Sample:
    """One snapshot of the device, returned by DataAcquisition.sample()."""
    timestamp: datetime.datetime
    raw_values: List[float]                 # raw AIN readings, in volts
    converted_values: List[float]           # same length; TC channels converted to °C if enabled
    cjc_temp_c: Optional[float] = None      # cold-junction temperature in °C, if measured
    pin_names: List[str] = field(default_factory=list)


class DataAcquisition:
    """Manages reads from a LabJackDevice plus CSV logging.

    Convention: the first pin in `device.input_pins` is the position sensor
    (an RVDT in the original setup); any remaining pins are K-type
    thermocouples, converted to °C when `enable_thermocouple_conversion`
    has been called.
    """

    def __init__(self, device, calibration: Optional[object] = None):
        self.device = device
        self.is_calibrating = calibration is not None
        self.file_path = ""

        # Thermocouple conversion settings.
        self.convert_thermocouples = False
        self._cjc_source: Union[str, float] = _TEMP_DEVICE_K  # register name or fixed °C
        self._cjc_offset_c = -3.0  # screw-terminal vs. internal sensor (per LabJack docs)
        self._tc_input_units = "v"

        # Cache of the most recently read CJC value (°C). Useful for logging
        # and for the rare case where read_data() runs without conversion enabled
        # but a caller still wants the last CJC reading.
        self._last_cjc_temp_c: Optional[float] = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def enable_thermocouple_conversion(
        self,
        cjc_source: Union[str, float] = "device",
        cjc_offset_c: float = -3.0,
        input_units: str = "V",
    ) -> None:
        """Enable K-type thermocouple voltage -> °C conversion.

        Parameters
        ----------
        cjc_source :
            * "device" (default): read TEMPERATURE_DEVICE_K live from the T7.
              Best when thermocouples are on the T7's built-in AIN0-3 terminals.
            * "air": read TEMPERATURE_AIR_K. Best when thermocouples are on a CB37.
            * a float (e.g. 25.0): use a fixed CJC temperature in degrees Celsius.
        cjc_offset_c :
            Offset added to the CJC reading after Kelvin->Celsius conversion. The
            T7 internal sensor is reported to read about 3 °C warmer than the
            screw terminals during steady-state operation (LabJack T7 datasheet
            Section 18.0), so the default is -3.0 °C. Set to 0.0 to disable.
            Ignored when `cjc_source` is a fixed float.
        input_units :
            Units of the raw thermocouple AIN readings. The LJM `eReadNames`
            call returns volts; pass "V" (default) or "mV" to match.
        """
        self.convert_thermocouples = True

        if isinstance(cjc_source, str):
            key = cjc_source.lower()
            if key in ("device", "internal", "temperature_device_k"):
                self._cjc_source = _TEMP_DEVICE_K
            elif key in ("air", "ambient", "temperature_air_k"):
                self._cjc_source = _TEMP_AIR_K
            else:
                # treat as raw register name passed through verbatim
                self._cjc_source = cjc_source
        else:
            # fixed temperature in °C
            self._cjc_source = float(cjc_source)

        self._cjc_offset_c = float(cjc_offset_c)
        self._tc_input_units = str(input_units).lower()

    # ------------------------------------------------------------------
    # File output
    # ------------------------------------------------------------------
    def create_output_file(self) -> None:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S.%f")[:-3]
        self.file_path = f"calibration - {ts}.csv"
        if not os.path.exists(self.file_path):
            cols = ["Timestamp"] + list(self.device.input_pins)
            if self.convert_thermocouples:
                cols.append("CJC_C")
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(",".join(cols) + os.linesep)
        print(f"Output file path created: {self.file_path}")

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------
    def sample(self) -> Sample:
        """Perform one LJM read and return a Sample.

        Reads all input pins (and the CJC register if conversion is enabled)
        in a single `eReadNames` call to minimize bus traffic.
        """
        names = list(self.device.input_pins)
        cjc_register: Optional[str] = None
        cjc_fixed_c: Optional[float] = None

        if self.convert_thermocouples:
            if isinstance(self._cjc_source, str):
                cjc_register = self._cjc_source
                names.append(cjc_register)
            else:
                cjc_fixed_c = float(self._cjc_source)

        vals = ljm.eReadNames(self.device.handle, len(names), names)

        # Split the response: device pins first, then optional CJC reading.
        if cjc_register is not None:
            raw_pin_values = list(vals[:-1])
            cjc_temp_k = float(vals[-1])
            cjc_temp_c = cjc_temp_k - 273.15 + self._cjc_offset_c
        else:
            raw_pin_values = list(vals)
            cjc_temp_c = cjc_fixed_c  # may be None if conversion not enabled

        self._last_cjc_temp_c = cjc_temp_c

        # Build converted values: position pin passed through, TC pins -> °C.
        converted = list(raw_pin_values)
        if self.convert_thermocouples and len(raw_pin_values) > 1 and cjc_temp_c is not None:
            tc_volts = np.asarray(raw_pin_values[1:], dtype=float)
            if self._tc_input_units in ("v", "volt", "volts"):
                tc_mv = tc_volts * 1000.0
            else:
                tc_mv = tc_volts
            temps_c = ktype_with_cjc(tc_mv, cjc_temp_c)
            temps_c = np.atleast_1d(temps_c)
            for i, t in enumerate(temps_c):
                converted[1 + i] = float(t)

        return Sample(
            timestamp=datetime.datetime.now(),
            raw_values=raw_pin_values,
            converted_values=converted,
            cjc_temp_c=cjc_temp_c,
            pin_names=list(self.device.input_pins),
        )

    # ------------------------------------------------------------------
    # Backward-compatible read interface (no I/O reduction here, but kept
    # so existing callers still work)
    # ------------------------------------------------------------------
    def read_data(self) -> List[float]:
        """Return the converted values from a fresh sample.

        Kept for backward compatibility. New code should call `sample()`
        directly to also receive the timestamp and CJC temperature.
        """
        return self.sample().converted_values

    # ------------------------------------------------------------------
    # Console / file output
    # ------------------------------------------------------------------
    def _print_values(self, sample: Sample, position: Optional[int]) -> None:
        # `position` (the servo angle) is intentionally ignored here. It's already
        # announced once per step ("Starting step 1/3: angle 135 ...") so prefixing
        # every printed sample with it just creates noise. The parameter stays in
        # the signature for backward compatibility.
        del position

        parts: List[str] = []
        for i, (pin, value) in enumerate(zip(sample.pin_names, sample.converted_values)):
            parts.append(f"{pin} = {value:>10.6f}")
            # Place CJC right after the position pin (index 0) so the columns are:
            # position, CJC, then thermocouples.
            if i == 0 and self.convert_thermocouples and sample.cjc_temp_c is not None:
                parts.append(f"CJC = {sample.cjc_temp_c:>7.3f} C")
        print("   ".join(parts))

    def print_data(self, angle: Optional[int] = None, sample: Optional[Sample] = None) -> None:
        """Print the latest reading. If `sample` is given, no new LJM read is performed."""
        if sample is None:
            sample = self.sample()
        self._print_values(sample, angle)

    def read_and_save(
        self,
        angle: Optional[int] = None,  # kept for signature compatibility; not written to CSV
        sample: Optional[Sample] = None,
    ) -> Sample:
        """Save the latest reading to the CSV file. Returns the Sample used."""
        if not self.file_path or not os.path.exists(self.file_path):
            print("File does not exist. Creating file")
            self.create_output_file()

        if sample is None:
            sample = self.sample()

        ts_str = sample.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        fields = [ts_str] + [f"{v:.6f}" for v in sample.converted_values]
        if self.convert_thermocouples:
            cjc = sample.cjc_temp_c if sample.cjc_temp_c is not None else float("nan")
            fields.append(f"{cjc:.3f}")
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(",".join(fields) + os.linesep)
        return sample

    def sample_print_save(self, angle: Optional[int] = None) -> Sample:
        """Take one reading, print it, and append it to the CSV (single LJM read)."""
        sample = self.sample()
        self.read_and_save(angle, sample=sample)
        self._print_values(sample, angle)
        return sample
