//-----------------------------------------------------------------------------
// Calibrate.cs
//
// Generate a series of PWM signals for controlling a servo.
// This will be used for calibration purposes.
//-----------------------------------------------------------------------------
using System;
using System.IO;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using System.Diagnostics;
using System.Linq;
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
            string[] inputPin = null;
            int coreFrequency = 80000000;  // Device core clock frequency
            int clockDivisor = 1;
            int pwmDIO = 2;
            LabJackDevice device = null;
            ServoCalibration servoCal = null;
            DataAcquisition DAQ = null;

            // Ask whether user wants to run a calibration or just take data
            Console.WriteLine("Select operation:\n1) Calibration (timed / interactive / CSV)\n2) Take data (print + live-plot specified AIN pins)");
            Console.Write("Enter 1 or 2: ");
            string primaryMode = Console.ReadLine()?.Trim();

            Process plotProc = null;

            if (primaryMode == "2")
            {
                // Taking data flow: ask for pins, confirm, then capture and plot
                Console.Write("Enter input pin(s) comma-separated Example: AIN0: ");
                string inputPinRaw = Console.ReadLine()?.Trim();
                if (string.IsNullOrEmpty(inputPinRaw)) inputPinRaw = "AIN0";
                var inputPinParts = inputPinRaw.Split(new char[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
                for (int i = 0; i < inputPinParts.Length; ++i) inputPinParts[i] = inputPinParts[i].Trim();
                inputPin = inputPinParts;

                Console.WriteLine($"Selected pins: {string.Join(", ", inputPin)}");
                Console.WriteLine("Type 'cancel' to abort or press Enter to start capturing and live-plotting.");
                string confirm = Console.ReadLine();
                if (string.Equals(confirm, "cancel", StringComparison.OrdinalIgnoreCase))
                {
                    Console.WriteLine("Cancelled.");
                    return;
                }

                // Use default PWM pin (not prompted) since we're only taking data
                pwmDIO = 2;

                // Open device and configure
                device = new(inputPin);
                device.Open();
                device.ConfigurePins();

                servoCal = new(device, coreFrequency, pwmDIO, clockDivisor, desiredFrequency);
                DAQ = new(device, servoCal);
                DAQ.CreateOutputFile();

                // Launch live_plot.py for the newest calibration CSV
                try
                {
                    string scriptPath = Path.Combine(Directory.GetCurrentDirectory(), "live_plot.py");
                    if (File.Exists(scriptPath))
                    {
                        var files = Directory.GetFiles(Directory.GetCurrentDirectory(), "calibration*.csv");
                        if (files.Length > 0)
                        {
                            var newest = files.OrderByDescending(f => File.GetLastWriteTimeUtc(f)).First();
                            var psi = new ProcessStartInfo
                            {
                                FileName = "python",
                                Arguments = $"\"{scriptPath}\" --file \"{newest}\"",
                                UseShellExecute = false,
                                CreateNoWindow = false
                            };
                            plotProc = Process.Start(psi);
                        }
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Could not start live plot: {ex.Message}");
                }

                Console.WriteLine("Capturing data. Press Esc to stop.");
                while (true)
                {
                    DAQ.ReadAndSave(positionZero);
                    try
                    {
                        var files = Directory.GetFiles(Directory.GetCurrentDirectory(), "calibration*.csv");
                        if (files.Length > 0)
                        {
                            var newest = files.OrderByDescending(f => File.GetLastWriteTimeUtc(f)).First();
                            var allLines = File.ReadAllLines(newest);
                            if (allLines.Length >= 2)
                            {
                                var header = allLines[0].Split(',').Select(h => h.Trim()).ToArray();
                                var lastLine = allLines[allLines.Length - 1].Split(',');
                                // For each requested pin, find column index and print value
                                foreach (var pin in inputPin)
                                {
                                    var idx = Array.IndexOf(header, pin);
                                    if (idx >= 0 && idx < lastLine.Length)
                                    {
                                        if (double.TryParse(lastLine[idx], out double v))
                                            Console.WriteLine($"{pin} = {v:F3}");
                                        else
                                            Console.WriteLine($"{pin} = {lastLine[idx]}");
                                    }
                                    else
                                    {
                                        Console.WriteLine($"{pin} = <not found>");
                                    }
                                }
                            }
                        }
                    }
                    catch { }

                    if ((GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0) break;
                    Thread.Sleep(200);
                }

                servoCal.TurnOffPWM();
                device.Dispose();
                try { if (plotProc != null && !plotProc.HasExited) plotProc.Kill(); } catch { }
                Console.WriteLine("Done capturing. Press Enter to exit.");
                Console.ReadLine();
                return;
            }

            // Calibration path: ask which pins and which calibration mode
            Console.Write("Enter input pin(s) comma-separated Example: AIN0:");
            string calInputPinRaw = Console.ReadLine()?.Trim();
            if (string.IsNullOrEmpty(calInputPinRaw)) calInputPinRaw = "AIN0";
            var calInputPinParts = calInputPinRaw.Split(new char[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            for (int i = 0; i < calInputPinParts.Length; ++i) calInputPinParts[i] = calInputPinParts[i].Trim();
            inputPin = calInputPinParts;

            Console.Write("Enter PWM DIO pin number. Example: FIO2:");
            string calPwmInput = Console.ReadLine()?.Trim();
            pwmDIO = 2;
            if (!string.IsNullOrEmpty(calPwmInput))
            {
                if (!int.TryParse(calPwmInput, out pwmDIO))
                {
                    Console.WriteLine("Invalid PWM pin input; using default FIO2AN.");
                    pwmDIO = 2;
                }
            }

            device = new(inputPin);
            device.Open();
            device.ConfigurePins();

            // --- Configure Clock and PWM ---

            servoCal = new(device, coreFrequency, pwmDIO, clockDivisor, desiredFrequency);
            DAQ = new(device, servoCal);
            DAQ.CreateOutputFile();

            // Launch live_plot.py to show AIN0 for the newest calibration CSV (non-blocking)
            try
            {
                string scriptPath = Path.Combine(Directory.GetCurrentDirectory(), "live_plot.py");
                if (File.Exists(scriptPath))
                {
                    var files = Directory.GetFiles(Directory.GetCurrentDirectory(), "calibration*.csv");
                    if (files.Length > 0)
                    {
                        var newest = files.OrderByDescending(f => File.GetLastWriteTimeUtc(f)).First();
                        var psi = new ProcessStartInfo
                        {
                            FileName = "python",
                            Arguments = $"\"{scriptPath}\" --file \"{newest}\"",
                            UseShellExecute = false,
                            CreateNoWindow = false
                        };
                        plotProc = Process.Start(psi);
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Could not start live plot: {ex.Message}");
            }

            // Initial position
            int currentAngle = positionZero;
            servoCal.SetServoAngle(currentAngle);

            // Mode selection: timed sequence, interactive, or import from CSV
            Console.WriteLine("Choose mode:\n1) Timed sequence (run steps for given durations)\n2) Interactive (hold Up/Down arrows)\n3) Import steps from CSV.");
            Console.WriteLine("Enter 1, 2, or 3:");
            string modeInput = Console.ReadLine()?.Trim();

            if (modeInput == "1")
            {
                Console.WriteLine("Timed sequence mode selected.");
                Console.Write("Number of steps: ");
                if (!int.TryParse(Console.ReadLine(), out int steps) || steps <= 0)
                {
                    Console.WriteLine("Invalid number of steps.");
                    Console.WriteLine("Exiting timed mode.");
                }
                else
                {
                    var angles = new int[steps];
                    var durations = new double[steps];
                    for (int i = 0; i < steps; ++i)
                    {
                        Console.Write($"Step {i + 1} direction (up/down/zero): ");
                        string dirInput = Console.ReadLine()?.Trim().ToLower();
                        if (dirInput == "up" || dirInput == "u")
                        {
                            angles[i] = positionUp;
                        }
                        else if (dirInput == "down" || dirInput == "d")
                        {
                            angles[i] = positionDown;
                        }
                        else
                        {
                            angles[i] = positionZero;
                        }

                        Console.Write($"Step {i + 1} duration (seconds): ");
                        if (!double.TryParse(Console.ReadLine(), out durations[i]) || durations[i] < 0) durations[i] = 1.0;
                    }

                    for (int i = 0; i < steps; ++i)
                    {
                        Console.WriteLine($"\nStarting step {i + 1}/{steps}: angle {angles[i]}, duration {durations[i]}s. Press Esc to abort.");
                        servoCal.SetServoAngle(angles[i]);

                        var sw = Stopwatch.StartNew();
                        bool aborted = false;
                        while (sw.Elapsed.TotalSeconds < durations[i])
                        {
                            if ((GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0)
                            {
                                aborted = true;
                                break;
                            }
                            DAQ.ReadAndSave(angles[i]);
                            Thread.Sleep(50);
                        }

                        sw.Stop();
                        // stop and release servo between steps
                        servoCal.TurnOffPWM();
                        Console.WriteLine($"Step {i + 1} complete. Press Enter to continue to next step, Esc to abort.");

                        bool waiting = true;
                        while (waiting)
                        {
                            if ((GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0)
                            {
                                aborted = true;
                                break;
                            }

                            if (Console.KeyAvailable)
                            {
                                var k = Console.ReadKey(true);
                                if (k.Key == ConsoleKey.Enter) break;
                                if (k.Key == ConsoleKey.Escape)
                                {
                                    aborted = true;
                                    break;
                                }
                            }

                            DAQ.ReadAndSave(angles[i]);
                            Thread.Sleep(50);
                        }

                        if (aborted)
                        {
                            Console.WriteLine("Aborted by user.");
                            break;
                        }
                    }
                }
            }
            else if (modeInput == "3")
            {
                Console.WriteLine("CSV import mode selected.");
                Console.Write("Enter CSV file path: ");
                string csvPath = Console.ReadLine()?.Trim();
                if (string.IsNullOrEmpty(csvPath) || !File.Exists(csvPath))
                {
                    Console.WriteLine("File not found or invalid path. Exiting CSV mode.");
                }
                else
                {
                    var anglesList = new List<int>();
                    var durationsList = new List<double>();

                    try
                    {
                        var rawLines = File.ReadAllLines(csvPath);
                        foreach (var raw in rawLines)
                        {
                            if (string.IsNullOrWhiteSpace(raw)) continue;
                            var line = raw.Trim();
                            // Support CSV lines like: direction,duration  OR  angle,duration
                            var parts = line.Split(',');
                            if (parts.Length < 2) continue;
                            var aPart = parts[0].Trim();
                            var dPart = parts[1].Trim();

                            if (!double.TryParse(dPart, out double duration) || duration < 0) continue;

                            if (int.TryParse(aPart, out int parsedAngle))
                            {
                                anglesList.Add(parsedAngle);
                                durationsList.Add(duration);
                            }
                            else
                            {
                                var d = aPart.ToLower();
                                if (d == "up" || d == "u") anglesList.Add(positionUp);
                                else if (d == "down" || d == "d") anglesList.Add(positionDown);
                                else anglesList.Add(positionZero);
                                durationsList.Add(duration);
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"Error reading CSV: {ex.Message}");
                    }

                    int steps = Math.Min(anglesList.Count, durationsList.Count);
                    if (steps == 0)
                    {
                        Console.WriteLine("No valid steps parsed from CSV.");
                    }
                    else
                    {
                        for (int i = 0; i < steps; ++i)
                        {
                            Console.WriteLine($"\nStarting step {i + 1}/{steps}: angle {anglesList[i]}, duration {durationsList[i]}s. Press Esc to abort.");
                            servoCal.SetServoAngle(anglesList[i]);

                            var sw = Stopwatch.StartNew();
                            bool aborted = false;
                            while (sw.Elapsed.TotalSeconds < durationsList[i])
                            {
                                if ((GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0)
                                {
                                    aborted = true;
                                    break;
                                }
                                DAQ.ReadAndSave(anglesList[i]);
                                Thread.Sleep(50);
                            }

                            sw.Stop();
                            servoCal.TurnOffPWM();
                            Console.WriteLine($"Step {i + 1} complete. Press Enter to continue to next step, Esc to abort.");

                            bool waitingCsv = true;
                            while (waitingCsv)
                            {
                                if ((GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0)
                                {
                                    aborted = true;
                                    break;
                                }

                                if (Console.KeyAvailable)
                                {
                                    var k = Console.ReadKey(true);
                                    if (k.Key == ConsoleKey.Enter) break;
                                    if (k.Key == ConsoleKey.Escape)
                                    {
                                        aborted = true;
                                        break;
                                    }
                                }

                                DAQ.ReadAndSave(anglesList[i]);
                                Thread.Sleep(50);
                            }

                            if (aborted)
                            {
                                Console.WriteLine("Aborted by user.");
                                break;
                            }
                        }
                    }
                }
            }
            else
            {
                Console.WriteLine("Interactive mode: Hold Up/Down arrows to move servo. Press Esc to exit.");

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
            }

            servoCal.TurnOffPWM();
            device.Dispose();

            // Ensure the live-plot process is terminated when we're done
            try
            {
                if (plotProc != null && !plotProc.HasExited)
                {
                    plotProc.Kill();
                }
            }
            catch (Exception) { }

            Console.WriteLine("\nDone. Press the enter key to exit.");
            Console.ReadLine();
        }
    }
}
