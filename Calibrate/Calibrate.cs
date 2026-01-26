//-----------------------------------------------------------------------------
// Calibrate.cs
//
// Generate a series of PWM signals for controlling a servo.
// This will be used for calibration purposes.
//-----------------------------------------------------------------------------
using System;
using System.Runtime.InteropServices;
using System.Threading;
using Device;

namespace Calibrate
{
    class Calibrate
    {
        [DllImport("user32.dll")]
        private static extern short GetAsyncKeyState(int vKey);

        const int VK_UP = 0x26;
        const int VK_DOWN = 0x28;
        const int VK_ESCAPE = 0x1B;

        static void Main(string[] args)
        {
            Calibrate pwm = new();
            pwm.ConfigurePWM();
        }

        public void ConfigurePWM()
        {
            // ------------- USER INPUT VALUES -------------
            int desiredFrequency = 50;  // PWM Frequency in Hz
            int positionZero = 90;       // angle when no key is pressed - stops 360 servo
            int positionUp = 135;       // angle while Up arrow is held - clockwise rotation
            int positionDown = 45;      // angle while Down arrow is held - counterclockwise rotation
            string[] inputPin = ["AIN0"]; // Set this to the appropriate pin name or value

            LabJackDevice device = new(inputPin);
            device.Open();
            device.ConfigurePins();

            // --- Configure Clock and PWM ---
            int pwmDIO = 2;  // DIO Pin that will generate the PWM signal
            int coreFrequency = 80000000;  // Device core clock frequency
            int clockDivisor = 1;

            ServoCalibration servoCal = new(device, coreFrequency, pwmDIO, clockDivisor, desiredFrequency);
            DataAcquisition DAQ = new(device, servoCal);
            DAQ.CreateOutputFile();

            // Initial position
            int currentAngle = positionZero;
            servoCal.SetServoAngle(currentAngle);

            Console.WriteLine("Hold Up/Down arrows to move servo. Script assumes sensor is connected to AIN0. Press Esc to exit.");

            bool lastUp = false;
            bool lastDown = false;
            bool running = true;

            while (running)
            {
                bool upPressed = (GetAsyncKeyState(VK_UP) & 0x8000) != 0;
                bool downPressed = (GetAsyncKeyState(VK_DOWN) & 0x8000) != 0;

                if (upPressed && !lastUp)
                {
                    currentAngle = positionUp;
                    servoCal.SetServoAngle(currentAngle);
                    Console.WriteLine($"Up pressed -> angle {currentAngle}");
                }
                else if (downPressed && !lastDown)
                {
                    currentAngle = positionDown;
                    servoCal.SetServoAngle(currentAngle);
                    Console.WriteLine($"Down pressed -> angle {currentAngle}");
                }
                else if (!upPressed && lastUp)
                {
                    currentAngle = positionZero;
                    servoCal.SetServoAngle(currentAngle);
                    Console.WriteLine($"Up released -> angle {currentAngle}");
                }
                else if (!downPressed && lastDown)
                {
                    currentAngle = positionZero;
                    servoCal.SetServoAngle(currentAngle);
                    Console.WriteLine($"Down released -> angle {currentAngle}");
                }

                // Read sensors and save the current angle label with each sample
                DAQ.ReadAndSave(currentAngle);

                lastUp = upPressed;
                lastDown = downPressed;

                if ((GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0)
                {
                    running = false;
                }

                Thread.Sleep(50); // polling interval
            }

            servoCal.TurnOffPWM();
            device.Dispose();
            Console.WriteLine("\nDone. Press the enter key to exit.");
            Console.ReadLine();
        }
    }
}
