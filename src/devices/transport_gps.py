############################################################################
#                                                                          #
# Copyright (c)2008-2013, Digi International (Digi). All Rights Reserved.  #
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

from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
import channels.channel_source_device_property as csdp

import threading
import digitime
import digihw
import time

ChannelSourceDeviceProperty = csdp.ChannelSourceDeviceProperty
Sample = csdp.Sample
  
class GPS_Driver(DeviceBase, threading.Thread):
    
    #Declare variables for channel sources

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        
        #Setting table definition
        settings_list = [            
            Setting(
                name = 'sample_rate', type = float, required = False, 
                    default_value = 10.0,
                        verify_function = lambda x: x > 0.0),
        ]             
                                            
        #Channel properties definition, initially all ports are off
        #Can switch on by deploying a prop_set_port function
        property_list = [
           ChannelSourceDeviceProperty(name = "latitude", type = float,
                initial = Sample(timestamp = 0, value = 0.0), 
                perms_mask = csdp.DPROP_PERM_GET|csdp.DPROP_PERM_REFRESH,
                options = csdp.DPROP_OPT_AUTOTIMESTAMP),
                         
           ChannelSourceDeviceProperty(name = "longitude", type = float,
                initial = Sample(timestamp = 0, value = 0.0), 
                perms_mask = csdp.DPROP_PERM_GET|csdp.DPROP_PERM_REFRESH,
                options = csdp.DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name = "altitude", type = float,
                initial=Sample(timestamp = 0, value = 0.0),
                perms_mask = csdp.DPROP_PERM_GET|csdp.DPROP_PERM_REFRESH,
                options = csdp.DPROP_OPT_AUTOTIMESTAMP),
                
            ChannelSourceDeviceProperty(name = "current_time", type = int,
                initial=Sample(timestamp = 0, value = 0),
                perms_mask = csdp.DPROP_PERM_GET|csdp.DPROP_PERM_REFRESH,
                options = csdp.DPROP_OPT_AUTOTIMESTAMP),
        ]
        
        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)
        
    
    def start(self):
        threading.Thread.start(self)
        return True

    def stop(self):
        self.__stopevent.set()
        return True
  
    #Threading related functions
    def run(self):
                
        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break
            
            try:
                self._tracer.info("Reading GPS data.....")
                gps_data = digihw.gps_location()
            
                #Retrieve information from gps_location
                name = ['latitude', 'longitude', 'altitude', 'current_time']
                for index in range(len(name)):
                    self.property_set(name[index], 
                                      Sample(0, value = gps_data[index]))

            except:
                import traceback
                traceback.print_exc()
                self._tracer.info("Unable to get a GPS signal.")
                self._tracer.info("Please place the GPS antenna in another place.")

            digitime.sleep(SettingsBase.get_setting(self, "sample_rate"))

