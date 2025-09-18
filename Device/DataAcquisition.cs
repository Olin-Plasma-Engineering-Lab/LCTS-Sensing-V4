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
        private string filePath;

        public DataAcquisition(LabJackDevice device, string filePath)
        {
            this.device = device;
            this.filePath = filePath;
        }

        public void WriteHeaderIfNeeded()
        {
            if (!File.Exists(filePath))
            {
                File.AppendAllText(filePath, "Timestamp,Channel,Value" + Environment.NewLine);
            }
        }

        public void ReadAndSave()
        {
            string[] aNames = new string[] { "AIN0", "FIO2" };
            double[] aValues = new double[] { 0, 0 };
            int numFrames = aNames.Length;
            int errorAddress = -1;
            LJM.eReadNames(device.Handle, numFrames, aNames, aValues, ref errorAddress);
            var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
            for (int i = 0; i < numFrames; i++)
            {
                File.AppendAllText(filePath, $"{timestamp},{aNames[i]},{aValues[i]:F4}" + Environment.NewLine);
            }
        }
    }
}
