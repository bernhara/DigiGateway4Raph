"""File to configure the serial port location of the XBee connected to this device.
This file does not need to be uploaded to a ConnectPort."""

# rename this file to "default_xbee_config.py" and configure to local
# serial port.

import xbee
import serial

# create the serial port connection for the default XBee
xbee.default_xbee.serial = serial.Serial("COM8", 9600, rtscts = 0)


