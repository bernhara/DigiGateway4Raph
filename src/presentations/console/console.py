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
Console Presentation
"""

# imports
from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase
import threading
from presentations.console.console_tcp_server \
    import ConsoleTcpServer, ConsoleTcpRequestHandler

from select import select
import digitime

# constants

# exception classes

# interface functions

# classes

class Console(PresentationBase, threading.Thread):
    
    """
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.
    """

    def __init__(self, name, core_services):

        self.__name = name
        self.__core = core_services
        
        # Settings:
        #
        # type: must be set to either "tcp" or "serial" (default value: "tcp")
        # port: if type is set to "tcp", 'port' is an integer which specifies 
        #     the TCP port number that the console will start upon (default 
        #     value: 4146).
        # device: if type is set to "serial", this is the serial port device 
        #     name that will be used. (default value: "/com/0").
        # baudrate: if type is set to "serial", this is the baud rate that will
        #     be used. (default value: 115200).
        
        settings_list = [
            Setting(
                name='type', type=str, required=False, default_value="tcp"),
            Setting(
                name='port', type=int, required=False, default_value=4146),
            Setting(
                name='device', type=str, required=False, default_value="/com/0"),
            Setting(
                name='baudrate', type=int, required=False, default_value=115200),
        ]

        ## Initialize settings:
        PresentationBase.__init__(self, name=name,
                                    settings_list=settings_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    def start(self):
        self.apply_settings()
        threading.Thread.start(self)
        return True

    def stop(self):
        self.__stopevent.set()
        return True

    def run(self):
        type = SettingsBase.get_setting(self, "type")
        if type == "serial":
            from presentations.console.console_serial_server import \
                 ConsoleSerialServer
            server = ConsoleSerialServer(
                                    SettingsBase.get_setting(self, "device"),
                                    SettingsBase.get_setting(self, "baudrate"),
                                    self.__core,
                                    self.__stopevent
                )
        else:
            server = ConsoleTcpServer(('', 
                                    SettingsBase.get_setting(self, "port")),
                                    ConsoleTcpRequestHandler, self.__core,
                                    self.__stopevent)
        while 1:
            if self.__stopevent.isSet():
                break

            if isinstance(server, ConsoleTcpServer):
                r, w, e = select([server.socket], [], [], 1.0)
            else:
                r = True # Serial ports are always ready

            if r:
                # Spawns a thread for TCP, blocks for Serial
                server.handle_request()

        while hasattr(server, "handlers") and len(server.handlers):
            # Wait for handlers to exit
            digitime.sleep(1.0)

# internal functions & classes
