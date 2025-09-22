//-----------------------------------------------------------------------------
// Calibrate.cs
//
// Generate a series of PWM signals for controlling a servo.
// This will be used for calibration purposes.
//-----------------------------------------------------------------------------
using System;
using System.Threading;
using Device;
using LabJack;


namespace Calibrate
{
    class Calibrate
    {
        static void Main(string[] args)
        {
            Calibrate pwm = new();
            pwm.ConfigurePWM();
        }

        public void ConfigurePWM()
        {
            // ------------- USER INPUT VALUES -------------
            int desiredFrequency = 50;  // Set this value to your desired PWM Frequency Hz. 
            int desiredDutyCycle = 50;     // Set this value to your desired PWM Duty Cycle percentage. Default 50%

            int positionZero = 0;
            int positionOne = 1;
            int positionTwo = 2;
            int positionThree = 3;
            int positionFour = 4;
            string[] inputPins = [];

            LabJackDevice device = new(inputPins);

            int[] calibrationPositions = [positionZero, positionOne, positionTwo, positionThree, positionFour];
            // ---------------------------------------------

            // --- Configure Clock and PWM ---
            int errorAddress = -1;
            int pwmDIO = 2;  // DIO Pin that will generate the PWM signal, set based on device type below. 
            int coreFrequency = 80000000;  // Device Specific Core Clock Frequency, used to calculate Clock Roll Value.
            int clockDivisor = 1;  // Clock Divisor to use in configuration.
            string[] aNames;
            double[] aValues;
            int numFrames = 0;

            ServoCalibration servoCal = new(device, coreFrequency, pwmDIO, clockDivisor, desiredFrequency);


            

                foreach (int position in calibrationPositions)
                {
                    Console.WriteLine($"Press enter to go to angle {position} degrees");
                    Console.ReadLine();
                servoCal.SetServoAngle(position);
                    Console.WriteLine($"Servo set to go to angle {position} degrees. Press enter to go to continue.");
                    Console.ReadLine();
                }


                // Turn off Clock and PWM output.
                aNames = new string[]
                {
                    "DIO_EF_CLOCK0_ENABLE",
                    String.Format("DIO{0}_EF_ENABLE", pwmDIO),
                };

                aValues = new double[] { 0, 0 };
                numFrames = aNames.Length;
                LJM.eWriteNames(handle, numFrames, aNames, aValues, ref errorAddress);


                LJM.CloseAll(); // Close all handles

                Console.WriteLine("\nDone.\nPress the enter key to exit.");
                Console.ReadLine(); // Pause for user
            }
            catch (LJM.LJMException e)
            {
                // An Error has occurred.
                showErrorMessage(e);
            }
        }
    }
}
