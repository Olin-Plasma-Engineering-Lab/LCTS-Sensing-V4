"""Data acquisition utilities translated from DataAcquisition.cs."""

from typing import Optional, List
import time
import datetime
import os
from labjack.ljm import ljm


class DataAcquisition:
    def __init__(self, device, calibration: Optional[object] = None):
        self.device = device
        self.is_calibrating = calibration is not None
        self.file_path = ""

    def create_output_file(self):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S.%f")[:-3]
        self.file_path = f"calibration - {ts}.csv"
        if not os.path.exists(self.file_path):
            header = "Timestamp," + ",".join(self.device.input_pins)
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(header + os.linesep)
        print(f"Output file path created: {self.file_path}")

    def read_data(self) -> List[float]:
        num = len(self.device.input_pins)
        return ljm.eReadNames(self.device.handle, num, list(self.device.input_pins))

    def _print_values(self, values: List[float], position: Optional[int]):
        if self.is_calibrating and position is not None:
            for i, pin in enumerate(self.device.input_pins):
                print(f"{position}:{pin} = {values[i]:.6f}")
        else:
            for i, pin in enumerate(self.device.input_pins):
                print(f"{pin} = {values[i]:.6f}")

    def print_data(self, angle: Optional[int] = None):
        values = self.read_data()
        self._print_values(values, angle)

    def read_and_save(self, angle: Optional[int] = None):
        if not self.file_path or not os.path.exists(self.file_path):
            print("File does not exist. Creating file")
            self.create_output_file()

        values = self.read_data()
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        row = ts + "," + ",".join([f"{v:.6f}" for v in values])
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(row + os.linesep)
