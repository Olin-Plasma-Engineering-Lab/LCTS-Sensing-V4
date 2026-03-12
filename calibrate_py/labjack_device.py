"""Wrapper for the LabJack device using the provided Python LJM library."""

from typing import List
import os
import sys

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


class LabJackDevice:
    def __init__(self, input_pins: List[str]):
        self.input_pins = input_pins
        self._handle = None
        self._dev_info = None
        self._counter_dio = 18

    @property
    def handle(self):
        return self._handle

    @property
    def counter_dio(self):
        return self._counter_dio

    def open(
        self,
        device_type: str = "T7",
        connection_type: str = "ANY",
        identifier: str = "ANY",
    ):
        try:
            # openS expects string device type
            self._handle = ljm.openS(device_type, connection_type, identifier)
            self._dev_info = ljm.getHandleInfo(self._handle)
            print(f"Opened LabJack handle {self._handle}; info={self._dev_info}")
        except LJMError as e:
            self.show_error_message(e)
            raise

    def configure_pins(self):
        if self._handle is None:
            raise RuntimeError("Device not opened")
        try:
            # Configure each requested AIN pin as single-ended with auto settling
            for pin in self.input_pins:
                # Example name conventions from C# code: "AIN0_NEGATIVE_CH", "AIN0_SETTLING_US"
                names = [f"{pin}_NEGATIVE_CH", f"{pin}_SETTLING_US"]
                values = [199.0, 0.0]
                ljm.eWriteNames(self._handle, len(names), names, values)
            print(f"Configured pins: {self.input_pins}")
        except LJMError as e:
            self.show_error_message(e)
            raise

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
