############################################################################
#                                                                          #
# Copyright (c)2008-2011, Digi International (Digi). All Rights Reserved.  #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,  and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. ContactProduct Management, Digi International, Inc., 11001 Bren    #
# Road East, Minnetonka, MN, +1 952-912-3444, for commercial licensing     #
# opportunities for non-Digi products.                                     #
#                                                                          #
# DIGI SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED   #
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A          #
# PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, #
# PROVIDED HEREUNDER IS PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND. #
# DIGI HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES,         #
# ENHANCEMENTS, OR MODIFICATIONS.                                          #
#                                                                          #
# IN NO EVENT SHALL DIGI BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,      #
# SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS,   #
# ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF   #
# DIGI HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.                #
#                                                                          #
############################################################################

"""\
  General purpose serial port library for Python & NDS. Instance declaration
  requires the essential serial port settings:

    serial_device:    ID of the serial port to use:
                            0 -> /com/0 (default)
                            1 -> /com/1
                            2 -> /com/2
                            3 -> /com/3
                            4 -> /com/4
                            5 -> /com/5
                            (continued from 6 to 20, as /com/6 to /com/20)
                            (Note: FTDI or other USB serial often = /com/11)
                            gps -> /gps/0

    baud_rate:        Comunication speed:
                            1200
                            2400
                            4800
                            9600
                            19200
                            38400 (default)
                            57600
                            115200
                            230400

    stop_bits:        Number of stop bits:
                            1 (default)
                            2

    data_bits:        Number of data bits:
                            5
                            6
                            7
                            8 (default)

    parity:           Data parity:
                            'N' -> None (default)
                            'E' -> Even
                            'O' -> Odd

    flow_control:     Communication protocol:
                            'N' -> None (default)
                            'H' -> Hardware

  Serial port methods:

    read_cb_set():    It sets the data read callback. When any data is read
                      this method will be called giving the read data as
                      parameter.

    open_port():      Configure and open the serial port.

    close_port():     Close the serial port.

    read():           Read data from the serial port. Notice that you should
                      have configured the read callback method before
                      performing a read, otherwise you'll receive the data
                      read.

    write():          Write given data into the serial port.

    start_read():     Initialize a reading thread that will be constantly
                      reading incoming data and executing the configured
                      callback method.

    get_name():       Return the name of the configured serial port.

    get_settings():   Retrun a dictionary with the serial port settings.

"""

# Imports
import os
import termios
import threading
from select import select

# Constants
TERMIOS_BAUD_MAP = {
    1200: termios.B1200,
    2400: termios.B2400,
    4800: termios.B4800,
    9600: termios.B9600,
    19200: termios.B19200,
    38400: termios.B38400,
}
if "B57600" in termios.__dict__:
    TERMIOS_BAUD_MAP[57600] = termios.B57600
if "B115200" in termios.__dict__:
    TERMIOS_BAUD_MAP[115200] = termios.B115200
if "B230400" in termios.__dict__:
    TERMIOS_BAUD_MAP[230400] = termios.B230400

SERIAL_DEVICE_MAP = {
    0: '/com/0',
    1: '/com/1',
    2: '/com/2',
    3: '/com/3',
    4: '/com/4',
    5: '/com/5',
    6: '/com/6',
    7: '/com/7',
    8: '/com/8',
    9: '/com/9',
    10: '/com/10',
    11: '/com/11',
    12: '/com/12',
    13: '/com/13',
    14: '/com/14',
    15: '/com/15',
    16: '/com/16',
    17: '/com/17',
    18: '/com/18',
    19: '/com/19',
    20: '/com/20',
    'gps': '/gps/0'
}

DATA_BITS_MAP = {
    5: termios.CS5,
    6: termios.CS6,
    7: termios.CS7,
    8: termios.CS8,
}

STOP_BITS_MAP = {
    2: termios.CSTOPB
}

PARITY_MAP = {
    'E': termios.PARENB,
    'O': termios.PARODD
}

FLOW_CONTROL_MAP = {
    'H': termios.CRTSCTS
}

class SerialPort:
    def __init__(self, serial_device=0, baud_rate=38400,
                 stop_bits=1, data_bits=8, parity='N',
                 flow_control='N'):
        """
            SerialPort class initialization method.
        """

        # Variables
        self.__serialfd = None
        self.__reader = None
        self.__read_cb = None
        self.__rlist = []
        self.__wlist = []
        self.__xlist = []

        # Serial port variables
        self.__serial_device = serial_device
        self.__baud_rate = baud_rate
        self.__stop_bits = stop_bits
        self.__data_bits = data_bits
        self.__parity = parity
        self.__flow_control = flow_control

    def open_port(self):
        """
            Configure and open the serial port.
        """

        # Obtain the serial port name
        if self.__serial_device in SERIAL_DEVICE_MAP:
            self.__serial_device = SERIAL_DEVICE_MAP[self.__serial_device]

        # Try to open the port
        try:
            self.__serialfd = os.open(self.__serial_device, os.O_RDWR |
                                      os.O_NONBLOCK)

            # Get Serial port attributes
            tcattrs = termios.tcgetattr(self.__serialfd)

            # Configure serial port basic settings
            attr_cfg = 0
            if self.__stop_bits in STOP_BITS_MAP:
                attr_cfg |= STOP_BITS_MAP[self.__stop_bits]
            if self.__data_bits in DATA_BITS_MAP:
                attr_cfg |= DATA_BITS_MAP[self.__data_bits]
            if self.__parity in PARITY_MAP:
                attr_cfg |= PARITY_MAP[self.__parity]
            if self.__flow_control in FLOW_CONTROL_MAP:
                attr_cfg |= FLOW_CONTROL_MAP[self.__flow_control]

            tcattrs[2] = attr_cfg

            # Obtain the baud rate
            baud_rate = TERMIOS_BAUD_MAP[self.__baud_rate]
            # Configure the baud rate
            tcattrs[4:6] = (baud_rate, baud_rate)

            # Set serial port attributes
            termios.tcsetattr(self.__serialfd, termios.TCSANOW, tcattrs)

            # Add the serial port instance to the read and write lists
            if not self.__serialfd in self.__rlist:
                self.__rlist.append(self.__serialfd)
            if not self.__serialfd in self.__wlist:
                self.__wlist.append(self.__serialfd)

            return True

        except:
           return False

    def close_port(self):
        """
            Close the serial port.
        """

        try:
            if self.__reader:
                self.__reader = None
            return os.close(self.__serialfd)
        except:
            return None

    def read_cb_set(self, method):
        """
            Define which method will get called back upon the serial port
            data reading.

            The callback will be performed with the following arguments:

                cb(serial_data)

            Where:

                serial_data is the data read from the serial port.
        """

        # Set the read callback method
        self.__read_cb = method

    def read(self, max_size=1024, timeout=None):
        """
            Call the read callback with read data as parameter. Use
            specified timeout into the select method.
        """

        # Check if there is a timeout to call the select method with or
        # without it
        if timeout:
            ready = select(self.__rlist, [], [], timeout)
        else:
            ready = select(self.__rlist, [], [])

        # If the serial port has any data, read it and call the read
        # callback method. If callback isn't set, return the data
        if self.__serialfd in ready[0]:
            data = None
            try:
                data = os.read(self.__serialfd, max_size)
                if self.__read_cb:
                    self.__read_cb(data)
                else:
                    return data
            except:
                return data

    def get_name(self):
        """
            Return the name of the configured serial port.
        """

        # Obtain the serial port name
        if self.__serial_device in SERIAL_DEVICE_MAP:
            return SERIAL_DEVICE_MAP[self.__serial_device]
        else:
            return self.__serial_device

    def get_settings(self):
        """
            Return a dictionary with the serial port settings.
        """

        settings = {'serial_device': self.__serial_device,
                    'baud_rate': self.__baud_rate,
                    'data_bits': self.__data_bits,
                    'stop_bits': self.__stop_bits,
                    'parity': self.__parity,
                    'flow_control': self.__flow_control}

        return settings

    def write(self, data):
        """
            Write given data into the serial port.
        """

        # Variables
        bytes_written = 0

        # Try to write the data
        try:
            bytes_written = os.write(self.__serialfd, data)
        except:
            return None

        # Return written bytes number
        return bytes_written

    def start_read(self, max_size=1024, timeout=None):
        """
            Generate a reader instance and start it to  start reading data
            from serial port.
        """

        if self.__reader:
            self.__reader = None
        self.__reader = self.__Reader(self.read, max_size, timeout)
        self.__reader.start()

    class __Reader(threading.Thread):
        """
            Class designed to read constantly from the serial port calling
            the given read method.
        """

        def __init__(self, read_method, max_size, timeout):
            self.read_method = read_method
            self.max_size = max_size
            self.timeout = timeout

            threading.Thread.__init__(self)
            threading.Thread.setDaemon(self, True)

        def run(self):
            while 1:
                self.read_method(self.max_size, self.timeout)
