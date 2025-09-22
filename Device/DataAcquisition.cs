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
                File.AppendAllText(this.filePath, "Timestamp,Channel,Value" + Environment.NewLine);
            }
            Console.WriteLine($"Output file path created: {this.filePath}");
        }

        public void ReadAndSave()
        {
            if (!File.Exists(this.filePath))
            {
                double[] aValues = [0, 0];
                int numFrames = device.inputPins.Length;
                int errorAddress = -1;
                LJM.eReadNames(device.Handle, numFrames, device.inputPins, aValues, ref errorAddress);
                var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
                for (int i = 0; i < numFrames; i++)
                {
                    Console.Write(" " + device.inputPins[i] + " = " + aValues[i].ToString("F4") + ", ");
                    File.AppendAllText(this.filePath, $"{timestamp},{device.inputPins[i]},{aValues[i]:F4}" + Environment.NewLine);
                }
            }
            else
            {
                Console.WriteLine("File does not exist. Creating file");
                CreateOutputFile();
                }
        }
    }
}
