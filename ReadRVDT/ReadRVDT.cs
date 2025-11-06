//-----------------------------------------------------------------------------
// ReadRVDT.cs
//
// Read the values from pins on a T7 and write the data to a CSV
//-----------------------------------------------------------------------------
using LabJack;
using Device;


namespace ReadRVDT
{
    class ReadRVDT
    {
        static void Main(string[] args)
        {
            ReadRVDT readRVDT = new();
            readRVDT.performActions();
        }

        public void performActions()
        {
            int intervalHandle = 1;
            int skippedIntervals = 0;
            

            Console.WriteLine("Hello OPEL! Press enter to begin.");
            Console.ReadLine();

            int numSensors = 0;
            Console.Write("Enter the number of sensors connected (positive integer): ");
            while (true)
            {
                string? input = Console.ReadLine();
                if (int.TryParse(input, out numSensors) && numSensors > 0)
                {
                    break;
                }
                Console.Write("Please enter a positive integer for the number of sensors: ");
            }

            string[] inputPins = new string[numSensors];
            for (int i = 0; i < numSensors; i++)
            {
                inputPins[i] = "AIN" + i;
            }

            Console.WriteLine($"Configured {numSensors} sensor(s): {string.Join(", ", inputPins)}");

            LabJackDevice device = new(inputPins);
            device.Open();



            Console.Write("Ready to take data? Pressing any key while data is being collected");
            Console.WriteLine(" will cause the script to exit. BE CAREFUL! Type 'yes' and press enter to acknowledge.");

            if (Console.ReadLine() != "yes")
            {
                Console.WriteLine("Incorrect response. Exiting program. Bye!");
                Console.ReadLine();
                Environment.Exit(0);
            }

            LJM.StartInterval(intervalHandle, 100000);

            Console.WriteLine("\nStarting read loop.  Press any key to stop.");

            DataAcquisition daq = new(device);
            daq.CreateOutputFile();

            while (!Console.KeyAvailable)
            {

                daq.ReadAndSave();

                //Wait for next 0.1 second interval
                LJM.WaitForNextInterval(intervalHandle, ref skippedIntervals);
                if (skippedIntervals > 0)
                {
                    Console.WriteLine("SkippedIntervals: " + skippedIntervals);
                }
            }
            
            

            Console.ReadLine();
            //Close interval and device handles
            LJM.CleanInterval(intervalHandle);
            device.Dispose();
            Console.WriteLine("\nDone.\nPress the enter key to exit.");
            Console.ReadLine();  //Pause for user
        }
    }
}
