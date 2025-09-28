// DataAcquisition.cs
// Handles reading and saving data to CSV
using LabJack;

namespace Device
{
    public class DataAcquisition
    {
        private LabJackDevice device;
        private string filePath = "";

        private bool isCalibrating;

        // Make calibration optional by using a nullable parameter with default value
        public DataAcquisition(LabJackDevice device, ServoCalibration? calibration = null)
        {
            this.device = device;
            isCalibrating = calibration != null;
        }
        public void CreateOutputFile()
        {
            if (!isCalibrating)
            {
                var fileTimestamp = DateTime.Now.ToString("yyyy-MM-dd HH-mm-ss.fff");
                filePath = fileTimestamp + ".csv";
                // Write CSV header if file does not exist
                if (!File.Exists(filePath))
                {
                    // Header: Timestamp,<pin1>,<pin2>,...
                    string header = "Timestamp," + string.Join(",", device.inputPins);
                    File.AppendAllText(filePath, header + Environment.NewLine);
                }
                Console.WriteLine($"Output file path created: {this.filePath}");
            }
            else
            {
                var fileTimestamp = DateTime.Now.ToString("calibration: yyyy-MM-dd HH-mm-ss.fff");
                filePath = fileTimestamp + ".csv";
                // Write CSV header if file does not exist
                if (!File.Exists(filePath))
                {
                    // Header: Timestamp,<pin1>,<pin2>,...
                    string header = "Timestamp, Angle," + string.Join(",", device.inputPins);
                    File.AppendAllText(filePath, header + Environment.NewLine);
                }
                Console.WriteLine($"Output file path created: {this.filePath}");
                
            }
        }

        // Reads data from the device and returns the values (does not print or save)
        public double[] ReadData()
        {
            double[] aValues = new double[device.inputPins.Length];
            int numFrames = device.inputPins.Length;
            int errorAddress = -1;
            LJM.eReadNames(device.Handle, numFrames, device.inputPins, aValues, ref errorAddress);
            return aValues;
        }

        private void PrintValues(double[] aValues)
        {
            for (int i = 0; i < device.inputPins.Length; i++)
            {
                Console.WriteLine($"{device.inputPins[i]} = {aValues[i]:F4}");
            }
            Console.WriteLine("All values: " + string.Join(", ", aValues.Select(v => v.ToString("F4"))));
        }

        // Prints the current data to the console (does not save)
        public void PrintData()
        {
            double[] aValues = ReadData();
            PrintValues(aValues);
        }

        // Reads data and saves it to the CSV file (also prints to console)
        public void ReadAndSave(int? angle = null)
        {
            if (!File.Exists(filePath))
            {
                Console.WriteLine("File does not exist. Creating file");
                CreateOutputFile();
            }

            if (isCalibrating & angle != null)
            {
                double[] aValues = ReadData();
                var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
                // Write one row: Timestamp,<val1>,<val2>,...
                string row = timestamp + "," + (angle.ToString() ?? "") + "," + string.Join(",", aValues.Select(v => v.ToString("F4")));
                File.AppendAllText(filePath, row + Environment.NewLine);
                PrintValues(aValues);
            }
            else
            {
                double[] aValues = ReadData();
                var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
                // Write one row: Timestamp,<val1>,<val2>,...
                string row = timestamp + "," + string.Join(",", aValues.Select(v => v.ToString("F4")));
                File.AppendAllText(this.filePath, row + Environment.NewLine);
                PrintValues(aValues);
            }
        }
    }
}
