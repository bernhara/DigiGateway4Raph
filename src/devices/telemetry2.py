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
from channels.channel_source_device_property import *

import digihw
import threading

#channel_type is an empty list that will be filled with either 
#'in' or 'out' in order to decide channels' direction when
#the telemetry2 driver runs. 
channel_type = ['in','in','in','in']
#analog_mode is an empty list that will be filled with either
#'tx' or 'rx' depending on users' setting and it will be used
#as a way to figure out which analog channel is set as a receiver. 
analog_mode = ['rx','rx','rx','rx']
ma_division = 10000.00
MAX_MA = 20

class TelemetryTwoDriver(DeviceBase, threading.Thread):

    channel_array = {}
    #create an array of channel1 through channel4 output
    for i in xrange (4):
        channel_array["channel%d_output" % (i + 1)] = i

    def __init__(self, name, core_services, settings = None):
        self.__name = name
        self.__core = core_services
        
        #Setting table definition
        settings_list = [
            Setting(                
                name = 'analog1_mode', type = str, required = False,
                default_value = 'Receiver'),
            Setting(                
                name = 'analog2_mode', type = str, required = False,
                default_value = 'Receiver'),
            Setting(                
                name = 'analog3_mode', type = str, required = False,
                default_value = 'Receiver'),
            Setting(                
                name = 'analog4_mode', type = str, required = False,
                default_value = 'Receiver'),
            Setting(
                name = 'channel1_dir', type = str, required = False,
                default_value = 'in'),
            Setting(
                name = 'channel2_dir', type = str, required = False,
                default_value = 'in'),
            Setting(
                name = 'channel3_dir', type = str, required = False,
                default_value = 'in'),
            Setting(
                name = 'channel4_dir', type = str, required = False,
                default_value = 'in'),
            Setting(
                name = 'channel1_source', type = str, required = False),
            Setting(
                name = 'channel2_source', type = str, required = False),
            Setting(
                name = 'channel3_source', type = str, required = False),
            Setting(
                name = 'channel4_source', type = str, required = False),
            Setting(
                name = 'sample_rate_ms', type = float, required = False, 
                    default_value = 10000.0,
                        verify_function = lambda x: x > 0.0),
        ]             
                  
        #Properties are added dynamically based on configuration.
        property_list = [
        ]
        
        #Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    def start(self): 
        self._tracer.info("Telemetry Two driver starts!")
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        cdb = cm.channel_database_get()   
              
        #This for loop will iterate only for the channel insertion.       
        for index in range(4):
            #Define digital I/O direction. 
            dir = SettingsBase.get_setting(self, 'channel%d_dir' %(index + 1))
            if dir == 'in':
                self.add_property(
                    ChannelSourceDeviceProperty(
                        name='channel%d_input' %(index + 1), type=bool, 
                        initial=Sample(timestamp=0, value=False),
                        perms_mask=(DPROP_PERM_GET|DPROP_PERM_REFRESH),
                        options=DPROP_OPT_AUTOTIMESTAMP,
                    )
                )
                channel_type[index] = 'in'
            elif dir == 'out':
                sebcb_co = (lambda i: lambda sample: self.channel_update(
                    ch = 'channel%d_output' %(i+1), sample = sample))(int(index))
                self.add_property(
                    ChannelSourceDeviceProperty(
                        name='channel%d_output' %(index + 1), type=bool, 
                        initial=Sample(timestamp=0, value=False),
                        perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                        options=DPROP_OPT_AUTOTIMESTAMP,
                        set_cb = sebcb_co)
                )
                channel_type[index] = 'out'

        #This for loop will iterate for defining only for analog channels. 
        for index_2 in range(4):
            #Define analog I/O direction.
            analog_dir = SettingsBase.get_setting(self, \
                'analog%d_mode' %(index_2 + 1))
            if analog_dir == 'Transmitter':
                #set as a Transmitter 
                digihw.aio_set_tx_loop(index_2, 'on')
                digihw.aio_set_rx_loop(index_2, 'off')

                setcb_ma = (lambda i: lambda sample: self.update_analog_transmitter(
                    index = i, sample = sample))(int(index_2))
                self.add_property(
                    ChannelSourceDeviceProperty(
                        name='analog%d_transmitter_ma' %(index_2 + 1), 
                        type=float,
                        initial=Sample(timestamp=0, value = 0.0),
                        perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                        options=DPROP_OPT_AUTOTIMESTAMP,
                        set_cb = setcb_ma)
                )   

                analog_mode[index_2] = 'tx'

            elif analog_dir == 'Receiver':
                #set as a Receiver
                digihw.aio_set_rx_loop(index_2, 'on')  
                digihw.aio_set_tx_loop(index_2, 'off')

                self.add_property(
                    ChannelSourceDeviceProperty(
                        name='analog%d_receiver' %(index_2 + 1), type=float,
                        initial=Sample(timestamp=0, value=0.0, unit="mA"),
                        perms_mask = (DPROP_PERM_GET|DPROP_PERM_REFRESH),
                        options = DPROP_OPT_AUTOTIMESTAMP)
                )

                analog_mode[index_2] = 'rx'

        channel_src = []
        idx = 1

        for type in channel_type:
            #Need to separate channels that are set as an output.
            if type == 'out':
                channel_src.append('channel%d_source' %(idx))
            elif type == 'in' and SettingsBase.get_setting(self, \
                "channel%d_source" %(idx)) != None:
            #If something is in the channel source which is set as an input,
            #display error message that channel setting is available only if the
            #channel is set as an output.
                self._tracer.error('Unable to use channel%d_source. \
                    This is an input channel' %(idx))
            idx += 1 

        src_path = [SettingsBase.get_setting(self, channel) 
                for channel in channel_src]
                    
        pos_index = 0
        for ch_name in src_path:
            if ch_name != None:
                channel_to = "channel%d_output" % (pos_index + 1)
                cp.subscribe(ch_name, lambda src_ch, dest_name = 
                                channel_to: self.sub_cb(src_ch, dest_name))
            pos_index += 1  

        threading.Thread.start(self)
        return True

    def stop(self):
        self.__stopevent.set()
        return True

    def run(self):
        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break        
            for index, ch_type in enumerate(channel_type):
                #If found an input channel, and get a value and update it
                if ch_type == 'in':
                    currrent_digital_in_status = digihw.gpio_get_value(index)
                    self.property_set('channel%d_input' %(index + 1), 
                        Sample(0, bool(currrent_digital_in_status)))
            for idx in range(4):
                if analog_mode[idx] == 'rx':
                    val = digihw.aio_get_value(idx) / ma_division
                    self.property_set("analog%d_receiver" %(idx + 1), 
                        Sample(0, val))

            digitime.sleep(
                SettingsBase.get_setting(self, "sample_rate_ms") / 1000)

        return True

    def stop(self):
        self.__stopevent.set()
        return True

    def sub_cb(self, src_ch, dest_name):
        value = Sample(0, src_ch.get().value)        
        self.channel_update(dest_name, value)
      
    def channel_update(self, ch, sample):
        if sample.value:
            self.property_set(ch, Sample(0, True))
            digihw.gpio_set_value(self.channel_array[ch], 1)
        else:
            self.property_set(ch, Sample(0, False))
            digihw.gpio_set_value(self.channel_array[ch], 0)    

    def update_analog_transmitter(self, index, sample):
        if sample.value > MAX_MA:
            raise ValueError("mA value must be less than 20!")

        digihw.aio_set_ma(index, str(sample.value))
        self.property_set('analog%d_transmitter_ma' 
                            %(index+1), Sample(0, sample.value))
        
