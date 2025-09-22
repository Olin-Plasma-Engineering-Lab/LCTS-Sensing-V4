// LabJackDevice.cs
// Shared device connection and basic operations
using System;
using System.Runtime.CompilerServices;
using LabJack;

namespace Device
{
    public class LabJackDevice(string[] inputPins) : IDisposable
    {
        private int _handle = 0;
        private int _devType = 0;
        private int _conType = 0;
        private int _serNum = 0;
        private int _ipAddr = 0;
        private int _port = 0;
        private int _maxBytesPerMB = 0;
        private string _ipAddrStr = "";
        private bool _isOpen = false;

        public int Handle => _handle;
        public int DevType => _devType;
        public int ConType => _conType;
        public int SerNum => _serNum;
        public int IpAddr => _ipAddr;
        public int Port => _port;
        public int MaxBytesPerMB => _maxBytesPerMB;
        public string IpAddrStr => _ipAddrStr;
        public bool IsOpen => _isOpen;

        public string[] inputPins = inputPins;

        public void Open(string deviceType = "T7", string connectionType = "ANY", string identifier = "ANY")
        {
            try
            {
                LJM.OpenS(deviceType, connectionType, identifier, ref _handle);
                LJM.GetHandleInfo(_handle, ref _devType, ref _conType, ref _serNum, ref _ipAddr, ref _port, ref _maxBytesPerMB);
                LJM.NumberToIP(_ipAddr, ref _ipAddrStr);
                _isOpen = true;
                Console.WriteLine("Opened a LabJack with Device type: " + _devType + ", Connection type: " + _conType + ",");
                Console.WriteLine("  Serial number: " + _serNum + ", IP address: " + _ipAddrStr + ", Port: " + _port + ",");
                Console.WriteLine("  Max bytes per MB: " + _maxBytesPerMB);
            }
            catch (LJM.LJMException e)
            {
                showErrorMessage(e);
                Console.WriteLine("Error occurred. Press enter to exit.");
                Console.ReadLine();
                Environment.Exit(1);
            }
        }

        public void ConfigurePins()
        {
            if (DevType == LJM.CONSTANTS.dtT7)
            {
                foreach (string pin in inputPins)
                {

                    //LabJack T7 and T8 configuration

                    int errorAddress = -1;

                    //Settling and negative channel do not apply to the T8                    
                    // Negative Channel = 199 (Single-ended)
                    // Settling = 0 (auto)
                    string[] aNames = [$"{pin}_NEGATIVE_CH", $"{pin}_SETTLING_US"];
                    double[] aValues = [199, 0];
                    int numFrames = aNames.Length;
                    LJM.eWriteNames(Handle, numFrames, aNames, aValues, ref errorAddress);

                    //AIN0:
                    //    Range = ±10V (T7) or ±11V (T8).
                    //    Resolution index = 0 (default).
                    aNames = [$"{pin}_RANGE", $"{pin}_RESOLUTION_INDEX"];
                    aValues = [10, 0];
                    numFrames = aNames.Length;
                    LJM.eWriteNames(Handle, numFrames, aNames, aValues, ref errorAddress);

                }
            }
            else
            {
                Console.WriteLine("\n Incompatible Device. Exiting");
                Environment.Exit(1);
            }
        }

        public void showErrorMessage(LJM.LJMException e)
        {
            Console.Out.WriteLine("LJMException: " + e.ToString());
            Console.Out.WriteLine(e.StackTrace);
        }

        public void Close()
        {
            if (_isOpen && _handle != 0)
            {
                LJM.Close(_handle);
                _isOpen = false;
                _handle = 0;
            }
        }


        public void Dispose()
        {
            Close();
            GC.SuppressFinalize(this);
            
        }
    }
}

