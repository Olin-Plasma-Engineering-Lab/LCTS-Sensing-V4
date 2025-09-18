// ServoCalibration.cs
// Handles servo PWM control and calibration logic
using System;
using LabJack;

namespace Device
{
    public class ServoCalibration
    {
        private LabJackDevice device;
        private int coreFrequency;
        private int pwmDIO;
        private int clockDivisor;
        private int desiredFrequency;

        public ServoCalibration(LabJackDevice device, int devType, int coreFrequency, int pwmDIO, int clockDivisor = 1, int desiredFrequency = 50)
        {
            this.device = device;
            this.coreFrequency = coreFrequency;
            this.pwmDIO = pwmDIO;
            this.clockDivisor = clockDivisor;
            this.desiredFrequency = desiredFrequency;
        }

        public int CalculateDutyCycle(int angle)
        {
            // 0 deg = 1ms, 180 deg = 2ms, 50Hz (20ms period)
            // duty_cycle = 5 + (angle / 36)
            return 5 + (angle / 36);
        }

        public void SetServoAngle(int angle)
        {
            int dutyCycle = CalculateDutyCycle(angle);
            int clockTickRate = coreFrequency / clockDivisor;
            int clockRollValue = clockTickRate / desiredFrequency;
            int pwmConfigA = (int)(clockRollValue * ((double)dutyCycle / 100));
            LJM.eWriteName(device.Handle, $"DIO{pwmDIO}_EF_INDEX", 0);
            LJM.eWriteName(device.Handle, $"DIO{pwmDIO}_EF_CLOCK_SOURCE", 0);
            LJM.eWriteName(device.Handle, $"DIO{pwmDIO}_EF_ENABLE", 1);
            LJM.eWriteName(device.Handle, "DIO_EF_CLOCK0_ENABLE", 1);
            LJM.eWriteName(device.Handle, "DIO_EF_CLOCK0_DIVISOR", clockDivisor);
            LJM.eWriteName(device.Handle, "DIO_EF_CLOCK0_ROLL_VALUE", clockRollValue);
            LJM.eWriteName(device.Handle, $"DIO{pwmDIO}_EF_CONFIG_A", pwmConfigA);
        }
    }
}
