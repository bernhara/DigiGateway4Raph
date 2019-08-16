# $Id: xbeerawout.py 8063 2013-01-03 09:42:48Z orba6563 $

from custom_lib.runtimeutils import on_digi_board

# imports
import logging
from custom_lib import logutils

from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

from socket import *

#--- Pangoo common definitions
from custom_lib.commons.pangoolib import * 

# constants
CHANNEL_NAME_INCOMING_FRAMES = 'raw_xbee_command' 

_XBEE_ADDRESS_DISPLAY_LEN=24

# exception classes

# interface functions

# classes

class XBeeRawOutDevice(DeviceBase):

    def __init__(self, name, core_services):
        
        self.logger = init_module_logger(name)

        self.__name = name
        self.__core = core_services
        


        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='log_level', type=str, required=False, default_value='DEBUG', verify_function=check_debug_level_setting),
        ]

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)
        
        ## Channel Properties Definition:
        property_list = [
            # gettable properties

 
           # gettable & settable properties
            ChannelSourceDeviceProperty(name=CHANNEL_NAME_INCOMING_FRAMES, type=str,
                initial=Sample(timestamp=0, value=""),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self._receive_raw_xbee_command_cb)                
        ]
                                            
        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()

    def apply_settings(self):
        
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        if len(rejected) or len(not_found):
            self.__tracer.error("Settings rejected/not found: %s %s", 
                                rejected, not_found)
            
        SettingsBase.commit_settings(self, accepted)
        
        update_logging_level (self.logger, SettingsBase.get_setting(self, 'log_level'))

        return (accepted, rejected, not_found)

    def start(self):

        self.logger.info ('Starting DIA Device Driver: %s' % self.__name)
        return True

    def stop(self):
        self.__stopevent.set()
        return True


    ## Locally defined functions:
    # Property callback functions:
    def _receive_raw_xbee_command_cb(self, string_sample):
        self.logger.debug ("Received new command: %s" % string_sample.value)
        
        if (len(string_sample.value) <= _XBEE_ADDRESS_DISPLAY_LEN):
            self.logger.critical ("Received sample ill-formated: too short")
            return
        
        xbee_address = string_sample.value[0:_XBEE_ADDRESS_DISPLAY_LEN]
        
        hex_string_frame = string_sample.value[_XBEE_ADDRESS_DISPLAY_LEN:]
        if (len(hex_string_frame) == 0):
            self.logger.critical ("Received sample ill-formated: no data frame provided")
            return            
            
        bin_frame=ao_hexstr_to_bin (hex_string_frame)
        if (len(bin_frame) == 0):
            self.logger.critical ("Received sample ill-formated: data frame format error")
            return            

        self._send_frame_to_xbee_address(xbee_address, bin_frame)
            
    def _send_frame_to_xbee_address (self, xbee_address, frame):
        self.logger.info ('Request to send to xbee device "%s" command: %s' % (xbee_address, ''.join('\\x%02X ' % ord(x) for x in frame)))
        
        if on_digi_board():
            
            try:
                # Create the socket, datagram mode, proprietary transport:
                sd = socket(AF_ZIGBEE, SOCK_DGRAM, ZBS_PROT_TRANSPORT)

                # Bind to endpoint 0xe8 (232):
                sd.bind(("", 0xe8, 0, 0))

                destination=(xbee_address, 0xe8, 0xc105, 0x11)
                sd.sendto(frame, 0, destination)
                
                # close socket now
                sd.close()
                
            except Exception, msg:
                self.logger.fatal ("Exception during xbee communication: %s" % msg) 
        else:
            self.logger.info ("No xbee device attached: skip action")
            
#=============================
def main():
    print "main does nothing"

#------------------------
if __name__ == '__main__':
    main()
