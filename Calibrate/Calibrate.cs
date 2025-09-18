//-----------------------------------------------------------------------------
// Calibrate.cs
//
// Generate a series of PWM signals for controlling a servo.
// This will be used for calibration purposes.
//-----------------------------------------------------------------------------
using System;
using System.Threading;
using LabJack;
using Device;


namespace DioEFConfigPwm
{
    class DioEFConfigPwm
    {

        static void Main(string[] args)
        {
            try
            {
                using (var device = new LabJackDevice())
                {
                    device.Open();
                    int devType = device.DevType;
                    int coreFrequency = 0;
                    int pwmDIO = 0;
                    switch (devType)
                    {
                        case LJM.CONSTANTS.dtT4:
                            pwmDIO = 6;
                            coreFrequency = 80000000;
                            break;
                        case LJM.CONSTANTS.dtT7:
                            pwmDIO = 2;
                            coreFrequency = 80000000;
                            break;
                        case LJM.CONSTANTS.dtT8:
                            pwmDIO = 2;
                            coreFrequency = 100000000;
                            break;
                    }
                    int clockDivisor = 1;
                    int desiredFrequency = 50;
                    var servo = new ServoCalibration(device, devType, coreFrequency, pwmDIO, clockDivisor, desiredFrequency);

                    int[] calibrationPositions = new int[] { 0, 45, 90, 135, 180 };
                    foreach (int position in calibrationPositions)
                    {
                        Console.WriteLine($"Press enter to go to angle {position} degrees");
                        Console.ReadLine();
                        servo.SetServoAngle(position);
                        Console.WriteLine($"Servo set to go to angle {position} degrees. Press enter to continue.");
                        Console.ReadLine();
                    }

                    // Turn off Clock and PWM output
                    string[] aNames = new string[]
                    {
                        "DIO_EF_CLOCK0_ENABLE",
                        $"DIO{pwmDIO}_EF_ENABLE"
                    };
                    double[] aValues = new double[] { 0, 0 };
                    int numFrames = aNames.Length;
                    int errorAddress = -1;
                    LabJack.LJM.eWriteNames(device.Handle, numFrames, aNames, aValues, ref errorAddress);
                }
            }
            catch (LJM.LJMException e)
            {
                Console.Out.WriteLine("LJMException: " + e.ToString());
                Console.Out.WriteLine(e.StackTrace);
            }

            Console.WriteLine("\nDone.\nPress the enter key to exit.");
            Console.ReadLine();
        }

    }
}
