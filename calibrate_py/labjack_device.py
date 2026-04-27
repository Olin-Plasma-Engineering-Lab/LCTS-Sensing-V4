"""Wrapper for the LabJack T7 / T7-Pro using the LJM library.

Configures each AIN pin according to its role in the system:

* "position" pins (e.g. an RVDT) get RANGE = +/-10 V to span the full bipolar
  swing of typical RVDT outputs.
* "tc" (thermocouple) pins get RANGE = +/-0.1 V because K-type output is at
  most ~54 mV across its full -270 to +1372 C span. Using the smallest
  appropriate range gives roughly 100x better LSB resolution than the
  default +/-10 V.

Resolution index is auto-selected: the device tries the maximum value (12,
T7-Pro 24-bit ADC) and falls back to 8 (T7 16-bit ADC) if the device
rejects it. Higher index means more averaging per sample, lower noise, and
a longer per-sample read time. At our ~50 ms loop period the slowdown is
negligible.
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional, Sequence

try:
    from labjack.ljm import ljm
    from labjack.ljm.ljm import LJMError
except Exception:
    # If the supplied Python_LJM folder isn't on sys.path, add workspace sibling
    workspace_root = os.path.dirname(os.path.dirname(__file__))
    potential = os.path.join(workspace_root, "..", "Python_LJM_2025_04_24")
    if os.path.isdir(potential):
        sys.path.insert(0, os.path.abspath(potential))
    from labjack.ljm import ljm
    from labjack.ljm.ljm import LJMError


# Per-role range and base resolution-index settings.
_ROLE_CONFIG = {
    "position": {"range_v": 10.0,  "preferred_res_index": 12, "fallback_res_index": 8},
    "tc":       {"range_v": 0.1,   "preferred_res_index": 12, "fallback_res_index": 8},
}


class LabJackDevice:
    def __init__(self, input_pins: List[str]):
        self.input_pins = input_pins
        self._handle: Optional[int] = None
        self._dev_info = None
        self._counter_dio = 18
        # Records the resolution index actually applied (for diagnostics)
        self._effective_res_index: Optional[int] = None

    @property
    def handle(self):
        return self._handle

    @property
    def counter_dio(self):
        return self._counter_dio

    @property
    def effective_resolution_index(self) -> Optional[int]:
        return self._effective_res_index

    def open(
        self,
        device_type: str = "T7",
        connection_type: str = "ANY",
        identifier: str = "ANY",
    ):
        try:
            self._handle = ljm.openS(device_type, connection_type, identifier)
            self._dev_info = ljm.getHandleInfo(self._handle)
            print(f"Opened LabJack handle {self._handle}; info={self._dev_info}")
        except LJMError as e:
            self.show_error_message(e)
            raise

    # ------------------------------------------------------------------
    # Pin configuration
    # ------------------------------------------------------------------
    def _probe_resolution_index(self) -> int:
        """Try writing RESOLUTION_INDEX = 12 to the first input pin.

        Returns 12 if the write succeeds (T7-Pro), 8 otherwise (plain T7).
        Leaves the test pin in its default state on failure.
        """
        if not self.input_pins:
            return 8
        test_pin = self.input_pins[0]
        try:
            ljm.eWriteName(self._handle, f"{test_pin}_RESOLUTION_INDEX", 12.0)
            return 12
        except LJMError:
            return 8

    def configure_pins(self, roles: Optional[Sequence[str]] = None) -> None:
        """Configure each input pin's negative channel, settling, range, and resolution.

        Parameters
        ----------
        roles : list of str, optional
            One role per pin. Each role must be a key of `_ROLE_CONFIG`
            (currently "position" or "tc"). Default convention: the first
            pin is "position" and the rest are "tc", which matches the rest
            of the calibration package.
        """
        if self._handle is None:
            raise RuntimeError("Device not opened")
        if not self.input_pins:
            print("No input pins configured.")
            return

        if roles is None:
            roles = ["position"] + ["tc"] * (len(self.input_pins) - 1)
        if len(roles) != len(self.input_pins):
            raise ValueError(
                f"roles length {len(roles)} != input_pins length {len(self.input_pins)}"
            )
        for r in roles:
            if r not in _ROLE_CONFIG:
                raise ValueError(f"Unknown pin role {r!r}; expected one of {list(_ROLE_CONFIG)}")

        # One-shot probe for the highest resolution index this hardware accepts.
        res_index = self._probe_resolution_index()
        self._effective_res_index = res_index
        print(f"Using AIN RESOLUTION_INDEX = {res_index} "
              f"({'T7-Pro 24-bit ADC' if res_index >= 9 else 'T7 16-bit ADC'})")

        try:
            for pin, role in zip(self.input_pins, roles):
                cfg = _ROLE_CONFIG[role]
                names = [
                    f"{pin}_NEGATIVE_CH",
                    f"{pin}_SETTLING_US",
                    f"{pin}_RANGE",
                    f"{pin}_RESOLUTION_INDEX",
                ]
                values = [
                    199.0,                   # single-ended
                    0.0,                     # auto settling
                    cfg["range_v"],
                    float(res_index),
                ]
                ljm.eWriteNames(self._handle, len(names), names, values)
                print(f"  {pin}: role={role}, range=+/-{cfg['range_v']:g} V, "
                      f"res_index={res_index}")
        except LJMError as e:
            self.show_error_message(e)
            raise

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    def show_error_message(self, e: Exception):
        print(f"LabJack error: {e}")

    def close(self):
        if self._handle is not None:
            try:
                ljm.close(self._handle)
            except Exception:
                pass
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
