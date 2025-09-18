// LabJackDevice.cs
// Shared device connection and basic operations
using System;
using LabJack;

namespace Device
{
    public class LabJackDevice : IDisposable
    {
        public int Handle { get; private set; }
        public int DevType { get; private set; }
        public int ConType { get; private set; }
        public int SerNum { get; private set; }
        public int IpAddr { get; private set; }
        public int Port { get; private set; }
        public int MaxBytesPerMB { get; private set; }
        public string IpAddrStr { get; private set; }
        public bool IsOpen { get; private set; }

        public LabJackDevice()
        {
            Handle = 0;
            DevType = 0;
            ConType = 0;
            SerNum = 0;
            IpAddr = 0;
            Port = 0;
            MaxBytesPerMB = 0;
            IpAddrStr = "";
            IsOpen = false;
        }

        public void Open(string deviceType = "T7", string connectionType = "ANY", string identifier = "ANY")
        {
            LJM.OpenS(deviceType, connectionType, identifier, ref Handle);
            LJM.GetHandleInfo(Handle, ref DevType, ref ConType, ref SerNum, ref IpAddr, ref Port, ref MaxBytesPerMB);
            LJM.NumberToIP(IpAddr, ref IpAddrStr);
            IsOpen = true;
        }

        public void Close()
        {
            if (IsOpen)
            {
                LJM.CloseAll();
                IsOpen = false;
            }
        }

        public void Dispose()
        {
            Close();
        }
    }
}
