//-----------------------------------------------------------------------------
// Calibrate.cs
//
// Generate a series of PWM signals for controlling a servo.
// This will be used for calibration purposes.
//-----------------------------------------------------------------------------
using System.Data;
using Device;
using LabJack;


namespace Calibrate
{
    class Calibrate
    {
        // // Parameterless constructor
        // public Calibrate()
        // {
        // }

        static void Main(string[] args)
        {
            Calibrate pwm = new();
            pwm.ConfigurePWM();
        }

        public void ConfigurePWM()
        {
            // ------------- USER INPUT VALUES -------------
            int desiredFrequency = 50;  // Set this value to your desired PWM Frequency Hz. 
            int positionZero = 0;
            int positionOne = 1;
            int positionTwo = 2;
            int positionThree = 3;
            int positionFour = 4;
            string[] inputPin = []; // Set this to the appropriate pin name or value

            LabJackDevice device = new(inputPin);
            device.Open();

            int[] calibrationPositions = [positionZero, positionOne, positionTwo, positionThree, positionFour];
            // ---------------------------------------------

            // --- Configure Clock and PWM ---
            int pwmDIO = 2;  // DIO Pin that will generate the PWM signal, set based on device type below. 
            int coreFrequency = 80000000;  // Device Specific Core Clock Frequency, used to calculate Clock Roll Value.
            int clockDivisor = 1;  // Clock Divisor to use in configuration.
            
            ServoCalibration servoCal = new(device, coreFrequency, pwmDIO, clockDivisor, desiredFrequency);

            DataAcquisition DAQ = new(device, servoCal);

            foreach (int position in calibrationPositions)
            {
                Console.WriteLine($"Press enter to go to angle {position} degrees");
                Console.ReadLine();
                Console.WriteLine($"Servo set to angle {position} degrees. Data is being recorded. Press enter to continue.");
                while (!Console.KeyAvailable)
                {
                    DAQ.ReadAndSave(position);
                }
                Console.ReadLine();
            }

            servoCal.TurnOffPWM();

            device.Dispose();
            Console.WriteLine("\nDone.\nPress the enter key to exit.");
            Console.ReadLine(); // Pause for user
            }
        }
    }
