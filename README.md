# LCTS-Sensing-V4
## Purpose
The project in this repo is used to control a LabJack T7 data acquisition device. Our uses require analog pins for measuring signals from RVDTs, thermocouples, etc. and digital pins for controlling a servo using PWM.

## `Implementation`
The project contains a `Device` namespace containing helpers for various control of the device:

### `LabJackDevice`
This contains helpers for establishing a connection with the device, configuring pins for analog reading, disposing of the device, etc

### `DataAcquisition`
This contains helpers for reading + printing data, creating output files, etc.

### `ServoCalibration`
This contains helpers for controlling a servo connected to the T7. It produces PWM signals that can be used to control a servo. 
