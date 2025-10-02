// ServoCalibration.cs
// Handles servo PWM control and calibration logic
using LabJack;

namespace Device
{
    public class ServoCalibration
    {
        private LabJackDevice device;
        private int coreFrequency;
        private int pwmDIO;
        private int clockDivisor = 1;
        private int desiredFrequency;
        
        public ServoCalibration(LabJackDevice device, int coreFrequency, int pwmDIO, int clockDivisor = 1, int desiredFrequency = 50)
        {
            this.device = device;
            this.coreFrequency = coreFrequency;
            this.pwmDIO = pwmDIO;
            this.clockDivisor = clockDivisor;
            this.desiredFrequency = desiredFrequency;
        }



        public float CalculateDutyCycle(float angle)
        {
            // 0 deg = 1ms, 180 deg = 2ms, 50Hz (20ms period)
            // duty_cycle = 5 + (angle / 36)
            // Determined using common servo control data
            return 5 + (angle / 36);
        }

        public void SetServoAngle(float angle)
        {
            try
            {
                Console.WriteLine(angle);
                float dutyCycle = CalculateDutyCycle(angle);
                Console.WriteLine(dutyCycle);
                int clockTickRate = coreFrequency / clockDivisor;
                int clockRollValue = clockTickRate / desiredFrequency;
                
                 // --- Calculate PWM Values ---
                // Calculate the clock tick value where the line will transition from high to low based on user defined duty cycle percentage, rounded to the nearest integer.
                int pwmConfigA = (int)(clockRollValue * ((double)dutyCycle / 100));

                // --- Configure and write values to connected device ---
                // Configure Clock Registers, use 32-bit Clock0 for this example.
                LJM.eWriteName((Int32)device.Handle, "DIO_EF_CLOCK0_DIVISOR", (double)clockDivisor);   // Set Clock Divisor.
                LJM.eWriteName(device.Handle, "DIO_EF_CLOCK0_ROLL_VALUE", clockRollValue); // Set calculated Clock Roll Value.

                // Configure PWM Registers
                LJM.eWriteName(device.Handle, String.Format("DIO{0}_EF_INDEX", pwmDIO), 0);              // Set DIO#_EF_INDEX to 0 - PWM Out.
                LJM.eWriteName(device.Handle, String.Format("DIO{0}_EF_CLOCK_SOURCE", pwmDIO), 0);       // Set DIO#_EF to use clock 0. Formerly DIO#_EF_OPTIONS, you may need to switch to this name on older LJM versions.
                LJM.eWriteName(device.Handle, String.Format("DIO{0}_EF_CONFIG_A", pwmDIO), pwmConfigA);  // Set DIO#_EF_CONFIG_A to the calculated value.
                LJM.eWriteName(device.Handle, String.Format("DIO{0}_EF_ENABLE", pwmDIO), 1);             // Enable the DIO#_EF Mode, PWM signal will not start until DIO_EF and CLOCK are enabled.

                // Configure High-Speed Counter Registers
                LJM.eWriteName(device.Handle, String.Format("DIO{0}_EF_INDEX", device.counterDIO), 7);          // Set DIO#_EF_INDEX to 7 - High-Speed Counter.
                LJM.eWriteName(device.Handle, String.Format("DIO{0}_EF_ENABLE", device.counterDIO), 1);         // Enable the High-Speed Counter.

                LJM.eWriteName(device.Handle, "DIO_EF_CLOCK0_ENABLE", 1);   // Enable Clock0, this will start the PWM signal.

            }
            catch (LJM.LJMException e)
            {
                device.showErrorMessage(e);
                device.Dispose();
                Console.WriteLine("Error occurred. Press enter to exit.");
                Console.ReadLine();
                Environment.Exit(-1);
            }
        }

        public void TurnOffPWM()
        {
            // Turn off PWM output and counter
                string[] aNames = 
                {
                    "DIO_EF_CLOCK0_ENABLE",
                    String.Format("DIO{0}_EF_ENABLE", pwmDIO),
                    String.Format("DIO{0}_EF_ENABLE", device.counterDIO),
                };

                double[] aValues = new double[device.inputPins.Length]; 
                int numFrames = aNames.Length;
            int errorAddress = -1;
                LJM.eWriteNames(device.Handle, numFrames, aNames, aValues, ref errorAddress);
        }
    }
}
