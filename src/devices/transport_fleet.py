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
import struct, time, sys

ChannelSourceDeviceProperty = csdp.ChannelSourceDeviceProperty
Sample = csdp.Sample

channel_type = ['in','in','in','in']
  
class Fleet_Driver(DeviceBase, threading.Thread):
    """
    This Fleet I/O driver has properties that moniters ignitation sense and 
    measure accelerometer values. In addition, it receives GPS data and 
    control I/O ports. 
    """
    
    #Declare variables for channel sources

    def __init__(self, name, core_services, settings=None):
        self.__name = name
        self.__core = core_services

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)
        
        #Setting table definition
        settings_list = [         
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
            # Setting(
            #     name = 'acc_threshold', type = float, required = False,
            #         default_value = 3.0),
            Setting(
                name = 'sample_rate_ms', type = float, required = False,
                    default_value = 10000.0,
                    verify_function = lambda x: x > 0.0),
        ]             
                                            
        #Channel properties definition, initially all ports are off
        #Can switch on by deploying a prop_set_port function
        #More channels will be added based on channel settings
        property_list = [
            ChannelSourceDeviceProperty(name = "ignition_status", type = bool,
                initial = Sample(timestamp = 0, value = False),
                perms_mask = csdp.DPROP_PERM_GET|csdp.DPROP_PERM_REFRESH,
                options = csdp.DPROP_OPT_AUTOTIMESTAMP,
                refresh_cb = self.refresh_ignition_status),

            # ChannelSourceDeviceProperty(name = "acceleration", type = str,
            #     initial = Sample(timestamp = 0, value = "", unit = 'G'),
            #     perms_mask = csdp.DPROP_PERM_GET|csdp.DPROP_PERM_REFRESH,
            #     options = csdp.DPROP_OPT_AUTOTIMESTAMP,
            #     refresh_cb = self.update_accelerometer_info),

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
        cm = self.__core.get_service("channel_manager")
        #Return a reference to the ChannelPublisher
        cp = cm.channel_publisher_get()
        cdb = cm.channel_database_get() 

        for index in range(4):
            #dir must be either in or out for channel usage
            dir = SettingsBase.get_setting(self, 'channel%d_dir' %(index+1))

            if dir == 'in':
                #Let user know input channel is loading and this device will set
                #as an input channel
                digihw.gpio_set_input(index)
                self.add_property(
                    ChannelSourceDeviceProperty(
                        name = 'channel%d_input' %(index+1), type = bool,
                        initial = Sample(timestamp = 0, value = False),
                        perms_mask = csdp.DPROP_PERM_GET|csdp.DPROP_PERM_REFRESH,
                        options = csdp.DPROP_OPT_AUTOTIMESTAMP,
                        set_cb = cp.subscribe('channel%d_input' %(index+1), \
                            lambda sample: self.channel_update(
                                ch = index, sample = sample))))
                channel_type[index] = 'in'

            elif dir == 'out':
                self.add_property(
                    ChannelSourceDeviceProperty(
                        name = 'channel%d_output' %(index+1), type = bool,
                        initial = Sample(timestamp=0, value=False),
                        perms_mask = csdp.DPROP_PERM_GET|csdp.DPROP_PERM_SET,
                        options = csdp.DPROP_OPT_AUTOTIMESTAMP,
                        set_cb = cp.subscribe('channel%d_output' %(index+1), \
                            lambda sample: self.channel_update( 
                                ch = index, sample=sample))))
                channel_type[index] = 'out'

        threading.Thread.start(self)
        return True

    def stop(self):
        self.__stopevent.set()
        return True
 
    def refresh_ignition_status(self):
        self.property_set('ignition_status', Sample(0, digihw.ignition_sense()))
 
    #Threading related functions
    def run(self):
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        cdb = cm.channel_database_get()     

        #threshold = SettingsBase.get_setting(self, 'acc_threshold')
        sample_rate_ms = SettingsBase.get_setting(self, 'sample_rate_ms')

        #self._tracer.info("Threshold set to %.3fG" %threshold)

        if digihw.NB_GPIO != len(channel_type):
                self._tracer.info('Invalid number of channels')

        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break

            # acceleration_value = self.update_accelerometer_info()
            # self.property_set("acceleration", Sample(0, acceleration_value))
            
            for index, ch_type in enumerate(channel_type):
                if ch_type == 'in':
                    current_status = bool(digihw.gpio_get_value(index))
                    digihw.gpio_set_input(index)
                    self.property_set('channel%d_input' %(index+1), \
                        Sample(0, current_status))
                elif ch_type == 'out':
                    status = self.property_get('channel%d_output' %(index+1)).value
                    digihw.gpio_set_value(index, status)

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

            status = digihw.ignition_sense()
            self.property_set("ignition_status", Sample(0, status))

            digitime.sleep(sample_rate_ms / 1000)

    # def accelerometer_callback(self, sample, context):
    #     """
    #     A callback function should be called when accelerate is exceeding threshold
    #     """
    #     x_axis = sample[0]
    #     y_axis = sample[1]
    #     z_axis = sample[2]
    #     threshold = SettingsBase.get_setting(self, 'acc_threshold')

    #     if x_axis >= threshold:
    #         self._tracer.info('Threshold exceeded on X axis %fG' % x_axis)

    #     if y_axis >= threshold:
    #         self._tracer.info('Threshold exceeded on y axis %fG' % y_axis)

    #     if z_axis >= threshold:
    #         self._tracer.info('Threshold exceeded on z axis %fG' % z_axis)


    #This function updates current forces measured in X, Y and Z axes 
    #read by Fleet I/O device
    # def update_accelerometer_info(self):
    #     accel = digihw.accelerometer()
    #     threshold = SettingsBase.get_setting(self, 'acc_threshold')

    #     #accel_value contains a 3-tuple representing the g-forces 
    #     accel_val = accel.sample()
    #     final_value = "X : %.3f Y : %.3f Z : %.3f" \
    #         %(accel_val[0], accel_val[1], accel_val[2])

    #     try:
    #         accel.register_threshold(threshold, self.accelerometer_callback, 0)
    #         self.property_set('acceleration', Sample(0, final_value))
    #     except ValueError:
    #         self._tracer.error("Invalid threshold value. Reset your threshold value.")
    #         self.stop()

    #     return final_value

    def channel_update(self, ch, sample):
        if sample.value:
            self.property_set('channel%d_output' %(ch+1), Sample(0, True))
            digihw.gpio_set_value(ch, 1)
        else:
            self.property_set('channel%d_output' %(ch+1), Sample(0, False))
            digihw.gpio_set_value(ch, 0)
