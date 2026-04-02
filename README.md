# LCTS-Sensing-V4
## Purpose
The project in this repo is used to control a LabJack T7 data acquisition device. Our uses require analog pins for measuring signals from RVDTs, thermocouples, etc. and digital pins for controlling a servo using PWM.

## Set Up
Using the scripts requires the LabJack drivers (https://support.labjack.com/docs/ljm-software-installer-downloads-t4-t7-t8-digit).

## Python Implementation
Create an environment `pip -m venv sensing`to create an environment called `sensing`

Run `pip install -r requirements.txt` to install dependencies

Run `python run_calibration.py` to execute the script


## C# Implementation
The C# implementation is the original attempt for interfacing with the LabJack. While it works reliably, it is harder to add features in C# and isn't immediately compatible with Mac. Further implementations are in Python.

### Implementation
The project contains a `Device` namespace containing helpers for various control of the device:

#### `LabJackDevice`
This contains helpers for establishing a connection with the device, configuring pins for analog reading, disposing of the device, etc

#### `DataAcquisition`
This contains helpers for reading + printing data, creating output files, etc.

#### `ServoCalibration`
This contains helpers for controlling a servo connected to the T7. It produces PWM signals that can be used to control a servo. 
