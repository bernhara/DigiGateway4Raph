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
TCPCSV Presentation

"""

# imports
import threading
import digitime
import time
from StringIO import StringIO
from socket import *

from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase
from channels.channel import PERM_GET, OPT_DONOTDUMPDATA
from channels.channel_publisher import ChannelDoesNotExist
from common.shutdown import SHUTDOWN_WAIT

# constants
RECONNECT_DELAY = 10.0

STATE_NOTCONNECTED = 0x0
STATE_CONNECTED    = 0x1

# classes
class TCPCSV(PresentationBase, threading.Thread):
    
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
     
        self.__stopevent = threading.Event()
		
        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)
        
        # Configuration Settings:

        # server: The IP address or hostname to connect to.
        # port: The TCP port number to connect to.
        # interval: How often (in seconds) to emit CSV data 
        #    (default: 60 seconds).
        # channels: A list of channels to include in the data set. If this 
        #    setting is not given, all channels will be included.
        settings_list = [
                Setting(name="server", type=str, required=True),
                Setting(name="port", type=int, required=True),
                Setting(name='interval', type=int, required=False, default_value=60),
                Setting(name="channels", type=list, required=False, default_value=[]),
        ]
                                                 
        PresentationBase.__init__(self, name=name, settings_list=settings_list)

        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)
    
    
    def start(self):
        threading.Thread.start(self)
        return True
 
    def stop(self):
        self.__stopevent.set()
        return True

    def run(self):
        state = STATE_NOTCONNECTED
        sd = None

        last_write = 0
        while not self.__stopevent.isSet():
            if state == STATE_NOTCONNECTED:
                server = SettingsBase.get_setting(self, "server")
                port = SettingsBase.get_setting(self, "port")
                sd = socket(AF_INET, SOCK_STREAM)
                try:
                    sd.connect((server, port))
                except Exception, e:
                    self.__tracer.error("error connecting to %s:%d: %s", \
                        server, port, str(e))
                    digitime.sleep(RECONNECT_DELAY)
                    continue
                state = STATE_CONNECTED

            interval = SettingsBase.get_setting(self, "interval")
            if state == STATE_CONNECTED \
                   and digitime.real_clock() > last_write + interval:

                sio = StringIO()
                self._write_channels(sio)
                try:
                        sd.sendall(sio.getvalue())
                        last_write = digitime.real_clock()
                except:
                        try:
                                sd.close()
                        except:
                                pass
                        state = STATE_NOTCONNECTED
                        continue
                del(sio)

            digitime.sleep(min(SHUTDOWN_WAIT, interval))

    def _write_channels(self, sio):

        # 'sio' is a file-like object which reads/writes to a string
        # buffer, as seen in StringIO.py.

        cm = self.__core.get_service("channel_manager")
        cdb = cm.channel_database_get()
        channel_list = SettingsBase.get_setting(self, "channels")

        if len(channel_list) == 0:
            channel_list = cdb.channel_list()

        # Each row of the CSV data is given as:
        #     channel_name,timestamp,value,unit``
        # where timestamp is adjusted to GMT and given in the format
        # ``YYYY-mm-dd HH:MM:SS`

        for channel_name in channel_list:
            try:
                channel = cdb.channel_get(channel_name)
                if not channel.perm_mask() & PERM_GET:
                    raise Exception, "Does not have GET permission"
                elif channel.options_mask() & OPT_DONOTDUMPDATA:
                    raise Exception, "Do not dump option set on channel"
                sample = channel.get()
                row_data = (channel_name,
                            time.strftime("%Y-%m-%d %H:%M:%S",
                                    time.gmtime(sample.timestamp)),
                            sample.value,
                            sample.unit)
                row_data = map(lambda d: str(d), row_data)
                sio.write(','.join(row_data) + "\r\n")
            except Exception, e:
                self.__tracer.error("error formatting '%s': %s", \
                        channel_name, str(e))
                pass
