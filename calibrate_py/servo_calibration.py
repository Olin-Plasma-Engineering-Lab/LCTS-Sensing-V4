"""Servo PWM control translated from ServoCalibration.cs."""

from typing import Optional
import math
from labjack.ljm import ljm


class ServoCalibration:
    def __init__(
        self,
        device,
        core_frequency: int,
        pwm_dio: int,
        clock_divisor: int = 1,
        desired_frequency: int = 50,
    ):
        self.device = device
        self.core_frequency = core_frequency
        self.pwm_dio = pwm_dio
        self.clock_divisor = clock_divisor
        self.desired_frequency = desired_frequency

    def calculate_duty_cycle(self, angle: float) -> float:
        return 5.0 + (angle / 36.0)

    def set_servo_angle(self, angle: float):
        try:
            duty_cycle = self.calculate_duty_cycle(angle)
            clock_tick_rate = int(self.core_frequency / self.clock_divisor)
            clock_roll_value = int(clock_tick_rate / self.desired_frequency)
            pwm_config_a = int(round(clock_roll_value * (duty_cycle / 100.0)))

            # Write clock and PWM configuration
            ljm.eWriteName(
                self.device.handle, "DIO_EF_CLOCK0_DIVISOR", float(self.clock_divisor)
            )
            ljm.eWriteName(
                self.device.handle, "DIO_EF_CLOCK0_ROLL_VALUE", float(clock_roll_value)
            )

            ljm.eWriteName(self.device.handle, f"DIO{self.pwm_dio}_EF_ENABLE", 0.0)
            ljm.eWriteName(self.device.handle, f"DIO{self.pwm_dio}_EF_INDEX", 0.0)
            ljm.eWriteName(
                self.device.handle, f"DIO{self.pwm_dio}_EF_CLOCK_SOURCE", 0.0
            )
            ljm.eWriteName(
                self.device.handle,
                f"DIO{self.pwm_dio}_EF_CONFIG_A",
                float(pwm_config_a),
            )
            ljm.eWriteName(self.device.handle, f"DIO{self.pwm_dio}_EF_ENABLE", 1.0)

            # Configure counter
            ljm.eWriteName(
                self.device.handle, f"DIO{self.device.counter_dio}_EF_ENABLE", 0.0
            )
            ljm.eWriteName(
                self.device.handle, f"DIO{self.device.counter_dio}_EF_INDEX", 7.0
            )
            ljm.eWriteName(
                self.device.handle, f"DIO{self.device.counter_dio}_EF_ENABLE", 1.0
            )

            ljm.eWriteName(self.device.handle, "DIO_EF_CLOCK0_ENABLE", 1.0)
        except Exception as e:
            self.device.show_error_message(e)
            self.device.close()
            raise

    def turn_off_pwm(self):
        names = [
            "DIO_EF_CLOCK0_ENABLE",
            f"DIO{self.pwm_dio}_EF_ENABLE",
            f"DIO{self.device.counter_dio}_EF_ENABLE",
        ]
        values = [0.0, 0.0, 0.0]
        ljm.eWriteNames(self.device.handle, len(names), names, values)
