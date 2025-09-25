// DataAcquisition.cs
// Handles reading and saving data to CSV
using System;
using System.IO;
using LabJack;

namespace Device
{
    public class DataAcquisition
    {
        private LabJackDevice device;
        private string filePath = "";

        public DataAcquisition(LabJackDevice device)
        {
            this.device = device;
        }

        public void CreateOutputFile()
        {
            var fileTimestamp = DateTime.Now.ToString("yyyy-MM-dd HH-mm-ss.fff");
            this.filePath = fileTimestamp + ".csv";
            // Write CSV header if file does not exist
            if (!File.Exists(this.filePath))
            {
                // Header: Timestamp,<pin1>,<pin2>,...
                string header = "Timestamp," + string.Join(",", device.inputPins);
                File.AppendAllText(this.filePath, header + Environment.NewLine);
            }
            Console.WriteLine($"Output file path created: {this.filePath}");
        }

        public void ReadAndSave()
        {
            if (File.Exists(this.filePath))
            {
                double[] aValues = new double[device.inputPins.Length];
                int numFrames = device.inputPins.Length;
                int errorAddress = -1;
                LJM.eReadNames(device.Handle, numFrames, device.inputPins, aValues, ref errorAddress);
                var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
                // Write one row: Timestamp,<val1>,<val2>,...
                string row = timestamp + "," + string.Join(",", aValues.Select(v => v.ToString("F4")));
                File.AppendAllText(this.filePath, row + Environment.NewLine);
                // Print all values
                for (int i = 0; i < numFrames; i++)
                {
                    Console.WriteLine($"{device.inputPins[i]} = {aValues[i]:F4}");
                }
                Console.WriteLine("All values: " + string.Join(", ", aValues.Select(v => v.ToString("F4"))));
            }
            else
            {
                Console.WriteLine("File does not exist. Creating file");
                CreateOutputFile();
            }
        }
    }
}
