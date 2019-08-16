############################################################################
#                                                                          #
# Copyright (c)2008, 2009, Digi International (Digi). All Rights Reserved. #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,  and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. Contact Product Management, Digi International, Inc., 11001 Bren   #
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

"""
Console Serial Server
"""

# imports
from lib.serial import Serial, EIGHTBITS, PARITY_NONE, STOPBITS_ONE
from presentations.console.console_interface import ConsoleInterface
import digitime

# constants

# exception classes

# interface functions

# classes
class QuitSerial(Serial):
    """File-like object to arrange for presentation exit on shutdown

    A bit of a hack, but required so that we plumb into the bottom of
    I/O operations and insert a means to communicate shutdown events
    as EOF occurring on the object

    """
    
    def __init__(self,
                 port = None,           #number of device, numbering starts at
                                        #zero. if everything fails, the user
                                        #can specify a device string, note
                                        #that this isn't portable anymore
                                        #port will be opened if one is specified
                 baudrate=9600,         #baudrate
                 bytesize=EIGHTBITS,    #number of databits
                 parity=PARITY_NONE,    #enable parity checking
                 stopbits=STOPBITS_ONE, #number of stopbits
                 timeout=None,          #set a timeout value, None to wait forever
                 xonxoff=0,             #enable software flow control
                 rtscts=0,              #enable RTS/CTS flow control
                 writeTimeout=None,     #set a timeout for writes
                 dsrdtr=None,           #None: use rtscts setting, dsrdtr
                                        #override if true or false
                 interCharTimeout=None,  #Inter-character timeout, None
                                        #to disable
                 stopevent=None 
                 ):

        self.stopevent = stopevent

        # Intercept timeout and reconfigure to provide internal
        # polling properties

        if stopevent:
            self.quit_timeout = 1.0
            if timeout != None:
                self.quit_timeout = min(timeout, self.quit_timeout)
        else:
            self.quit_timeout = timeout # Behave just like normal

        self.external_timeout = timeout

        Serial.__init__(self, port, baudrate, bytesize, parity,
                        stopbits, self.quit_timeout, xonxoff, rtscts,
                        writeTimeout, dsrdtr, interCharTimeout)


    def read(self, bufsize):
        exit_time = None
        if self.external_timeout:
            exit_time = digitime.real_clock() + self.external_timeout
        
        while 1:
            # check shutdown status
            if self.stopevent and self.stopevent.isSet():
                buf = ''
                break

            buf = Serial.read(self, bufsize)
            # Empty string is not EOF from Serial, but it will be
            # above if we return it.
            if len(buf) > 0 or (exit_time and digitime.real_clock() > exit_time):
                break

        return buf

class ConsoleSerialServer:

    def __init__(self, device, baudrate, core, stopevent=None):
        self.__device = device
        self.__baudrate = baudrate
        self.__core = core
        self.__stopevent = stopevent

    def get_core(self):
        return self.__core

    def handle_request(self):
        ser = QuitSerial(port = self.__device, baudrate =
                         self.__baudrate, stopevent=self.__stopevent)
        
        cli = ConsoleInterface(input=ser, output=ser, core=self.__core)
        try:
            cli.cmdloop()
        finally:
            ser.close()
        
 
# internal functions & classes

