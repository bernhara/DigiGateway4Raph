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
from device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import * 
from core import *

import digihw

IN_PORT = 0

class TelemetryOneDriver(DeviceBase, threading.Thread):
    channel_dict = {}
    
    #create an array of channel1 through channel4 output
    for i in xrange (4):
        channel_dict["channel%d_output" % (i + 1)] = i
    
    
    #Declare variables for channel sources
    def __init__(self, name, core_services, settings=None):
        self.__name = name
        self.__core = core_services
        
        settings_list = [
            Setting(
                name='channel1_source', type=str, required=False),
            Setting(
                name='channel2_source', type=str, required=False),
            Setting(
                name='channel3_source', type=str, required=False),
            Setting(
                name='channel4_source', type=str, required=False),           
            Setting(
                name='sample_rate_ms', type=float, required=False, 
                        default_value = 10000.0,
                        verify_function = lambda x: x > 0.0),
        ]             
                                           
        #Channel properties definition, initially all ports are off
        #Can switch on by deploying a prop_set_port function
        property_list = [
           ChannelSourceDeviceProperty(name="channel1_input", type=bool,
               initial=Sample(timestamp=0, value=False), 
               perms_mask=DPROP_PERM_GET|DPROP_PERM_REFRESH,
               options=DPROP_OPT_AUTOTIMESTAMP,
               refresh_cb=self.refresh_channel_one_input),
                         
           ChannelSourceDeviceProperty(name="channel1_output", type=bool,
               initial=Sample(timestamp=0, value=False), 
               perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
               options=DPROP_OPT_AUTOTIMESTAMP,
               set_cb=lambda sample: self.channel_update(ch="channel1_output", 
                                                         sample=sample)),
                         
           ChannelSourceDeviceProperty(name="channel2_output", type=bool,
               initial=Sample(timestamp=0, value=False), 
               perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
               options=DPROP_OPT_AUTOTIMESTAMP,
               set_cb=lambda sample: self.channel_update(ch="channel2_output", 
                                                         sample=sample)),
                         
           ChannelSourceDeviceProperty(name="channel3_output", type=bool,
               initial=Sample(timestamp=0, value=False), 
               perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
               options=DPROP_OPT_AUTOTIMESTAMP,
               set_cb=lambda sample: self.channel_update(ch="channel3_output", 
                                                         sample=sample)),
                         
           ChannelSourceDeviceProperty(name="channel4_output", type=bool,
               initial=Sample(timestamp=0, value=False), 
               perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
               options=DPROP_OPT_AUTOTIMESTAMP,
               set_cb=lambda sample: self.channel_update(ch="channel4_output", 
                                                         sample=sample)),
                         
           ChannelSourceDeviceProperty(name="relay", type=bool,
               initial=Sample(timestamp=0, value=False),
               perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
               options=DPROP_OPT_AUTOTIMESTAMP,
               set_cb=lambda sample: self.relay_update(ch="relay", 
                                                       sample=sample)),
                         
           # ChannelSourceDeviceProperty(name="temperature", type=int,
           #     initial=Sample(timestamp=0, value=0),
           #     perms_mask=DPROP_PERM_GET|DPROP_PERM_REFRESH,
           #     options=DPROP_OPT_AUTOTIMESTAMP,
           #     refresh_cb=self.refresh_temperature),   
         
           # ChannelSourceDeviceProperty(name="voltage", type=float,
           #     initial=Sample(timestamp=0, value=0.0),
           #     perms_mask=DPROP_PERM_GET|DPROP_PERM_REFRESH,
           #     options=DPROP_OPT_AUTOTIMESTAMP,
           #     refresh_cb=self.refresh_voltage),
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
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()      
        channel_src = ['channel1_source', 
                       'channel2_source', 
                       'channel3_source', 
                       'channel4_source']
        src_path = [SettingsBase.get_setting(self, channel) 
                    for channel in channel_src]
        
        pos_index = 0

        for ch_name in src_path:
            if ch_name != None:
                channel_to = "channel%d_output" % (pos_index+1)
                cp.subscribe(ch_name, lambda src_ch, dest_name = 
                                    channel_to: self.sub_cb(src_ch, dest_name))
            pos_index += 1                                                

        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break     
            
            current_channel1_input_status = bool(digihw.get_din(IN_PORT))
            # current_temperature = digihw.temperature()
            # current_voltage = digihw.voltage_monitor()
            
            #While thread is running, set those channels' value concurrently
            # self.property_set("temperature", 
            #                   Sample(0, int(current_temperature)))
            # self.property_set("voltage", Sample(0, current_voltage))
            self.property_set("channel1_input", 
                              Sample(0, current_channel1_input_status))
            
            digitime.sleep(SettingsBase.get_setting(self, "sample_rate_ms") / 1000)

        
    def refresh_channel_one_input(self):
        self.property_set("channel1_input", 
                          Sample(0, digihw.get_din(IN_PORT)))
    
    # def refresh_temperature(self):
    #     self.property_set("temperature", Sample(0, digihw.temperature()))
    
    # def refresh_voltage(self):
    #     self.property_set("voltage", Sample(0, digihw.voltage_monitor()))
          
    #A callback function         
    def sub_cb(self, src_ch, dest_name):
        value = Sample(0, src_ch.get().value)        
        self.channel_update(dest_name, value)           
        
    #Simply modify current channel output status
    def channel_update(self, ch, sample):
        if sample.value:
            self.property_set(ch, Sample(0, True))
            digihw.set_dout(self.channel_dict[ch], 1)
        else:
            self.property_set(ch, Sample(0, False))
            digihw.set_dout(self.channel_dict[ch], 0)
            
    #update relay port     
    def relay_update(self, ch, sample):             
        if sample.value:
            self.property_set(ch, Sample(0, True))
            digihw.set_relay(0, 1)
        else:
            self.property_set(ch, Sample(0, False))
            digihw.set_relay(0, 0)
