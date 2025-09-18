//-----------------------------------------------------------------------------
// ReadRVDT.cs
//
// Read the values from an analog pin on a T7 and write the data to a CSV
//-----------------------------------------------------------------------------
using System;
using System.IO;
using System.Text;
using LabJack;


namespace WriteReadLoopWithConfig
{
    class WriteReadLoopWithConfig
    {
        static void Main(string[] args)
        {
            WriteReadLoopWithConfig wrlwc = new WriteReadLoopWithConfig();
            wrlwc.performActions();
        }

        public void showErrorMessage(LJM.LJMException e)
        {
            Console.Out.WriteLine("LJMException: " + e.ToString());
            Console.Out.WriteLine(e.StackTrace);
        }

        public void performActions()
        {
            int handle = 0;
            int devType = 0;
            int conType = 0;
            int serNum = 0;
            int ipAddr = 0;
            int port = 0;
            int maxBytesPerMB = 0;
            string ipAddrStr = "";
            int numFrames = 0;
            string[] aNames;
            double[] aValues;
            int errorAddress = -1;
            int intervalHandle = 1;
            int skippedIntervals = 0;

            Console.WriteLine("Hello OPEL!");

            try
            {

                LJM.GetHandleInfo(handle, ref devType, ref conType, ref serNum, ref ipAddr, ref port, ref maxBytesPerMB);
                LJM.NumberToIP(ipAddr, ref ipAddrStr);
                Console.WriteLine("Opened a LabJack with Device type: " + devType + ", Connection type: " + conType + ",");
                Console.WriteLine("  Serial number: " + serNum + ", IP address: " + ipAddrStr + ", Port: " + port + ",");
                Console.WriteLine("  Max bytes per MB: " + maxBytesPerMB);

                //Setup and call eWriteNames to configure AIN0 (all devices)
                //and digital I/O (T4 only)
                if (devType == LJM.CONSTANTS.dtT7)
                {
                    //LabJack T7 and T8 configuration

                    //Settling and negative channel do not apply to the T8                    
                    // Negative Channel = 199 (Single-ended)
                    // Settling = 0 (auto)
                    aNames = new string[] { "AIN0_NEGATIVE_CH",
                                            "AIN0_SETTLING_US"};
                    aValues = new double[] { 199, 0 };
                    numFrames = aNames.Length;
                    LJM.eWriteNames(handle, numFrames, aNames, aValues, ref errorAddress);


                    //AIN0:
                    //    Range = ±10V (T7) or ±11V (T8).
                    //    Resolution index = 0 (default).
                    aNames = new string[] { "AIN0_RANGE",
                                            "AIN0_RESOLUTION_INDEX"};
                    aValues = new double[] { 10, 0 };
                    numFrames = aNames.Length;
                    LJM.eWriteNames(handle, numFrames, aNames, aValues, ref errorAddress);
                }
                else
                {
                    Console.WriteLine("\n Incompatible Device. Exiting");
                    Environment.Exit(0);
                }

                Console.Write("Ready to take data? Pressing any key while data is being collected");
                Console.WriteLine("will cause the script to exit. BE CAREFUL! Type 'yes' and press enter to acknowledge.");

                if (Console.ReadLine() != "yes")
                {
                    Console.WriteLine("Incorrect response. Exiting program. Bye!");
                    Environment.Exit(0);
                }

                Console.WriteLine("\nStarting read loop.  Press a key to stop.");
                LJM.StartInterval(intervalHandle, 100000);

                var fileTimestamp = DateTime.Now.ToString("yyyy-MM-dd HH-mm-ss.fff");
                var filePath = fileTimestamp + ".csv";
                // Write CSV header if file does not exist
                if (!File.Exists(filePath))
                {
                    File.AppendAllText(filePath, "Timestamp,Channel,Value" + Environment.NewLine);
                }

                while (!Console.KeyAvailable)
                {
                    //Setup and call eReadNames to read AIN0, and FIO6 (T4) or
                    //FIO2 (T7 and other devices).

                    aNames = new string[] { "AIN0", "FIO2" };
                    aValues = new double[] { 0, 0 };
                    numFrames = aNames.Length;
                    LJM.eReadNames(handle, numFrames, aNames, aValues, ref errorAddress);
                    Console.Write("eReadNames  :");
                    var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
                    for (int i = 0; i < numFrames; i++)
                    {
                        Console.Write(" " + aNames[i] + " = " + aValues[i].ToString("F4") + ", ");
                        // Append each row to the CSV file immediately
                        File.AppendAllText(filePath, $"{timestamp},{aNames[i]},{aValues[i]:F4}" + Environment.NewLine);
                    }
                    Console.WriteLine("");

                    //Wait for next 1 second interval
                    LJM.WaitForNextInterval(intervalHandle, ref skippedIntervals);
                    if (skippedIntervals > 0)
                    {
                        Console.WriteLine("SkippedIntervals: " + skippedIntervals);
                    }
                }
                // Data is already written during the loop; nothing to do here
            }
            catch (LJM.LJMException e)
            {
                showErrorMessage(e);
            }

            //Close interval and device handles
            LJM.CleanInterval(intervalHandle);
            LJM.CloseAll();

            Console.WriteLine("\nDone.\nPress the enter key to exit.");
            Console.ReadLine();  //Pause for user
        }
    }
}
