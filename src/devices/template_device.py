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

# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

import threading
import digitime

# constants

# exception classes

# interface functions

# classes

class TemplateDevice(DeviceBase, threading.Thread):
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

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='count_init', type=int, required=False, default_value=0,
                  verify_function=lambda x: x >= 0),
            Setting(
                name='update_rate', type=float, required=False, default_value=1.0,
                  verify_function=lambda x: x > 0.0),
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="counter", type=int,
                initial=Sample(timestamp=0, value=0),
                perms_mask=DPROP_PERM_GET|DPROP_PERM_REFRESH, 
                options=DPROP_OPT_AUTOTIMESTAMP,
                refresh_cb = self.refresh_counter),

            ChannelSourceDeviceProperty(name="adder_total", type=float,
                initial=Sample(timestamp=0, value=0.0),
                perms_mask=DPROP_PERM_GET, 
                options=DPROP_OPT_AUTOTIMESTAMP),        

            # settable properties
            ChannelSourceDeviceProperty(name="counter_reset", type=int,
                perms_mask=DPROP_PERM_SET,
                set_cb=self.prop_set_counter_reset),

            ChannelSourceDeviceProperty(name="global_reset", type=int,
                perms_mask=DPROP_PERM_SET,
                set_cb=self.prop_set_global_reset),

            # gettable & settable properties
            ChannelSourceDeviceProperty(name="adder_reg1", type=float,
                initial=Sample(timestamp=0, value=0.0),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=lambda x: self.prop_set_adder("adder_reg1", x)),

            ChannelSourceDeviceProperty(name="adder_reg2", type=float,
                initial=Sample(timestamp=0, value=0.0),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=lambda x: self.prop_set_adder("adder_reg2", x)),

        ]
                                            
        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)


    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def start(self):

        threading.Thread.start(self)

        return True

    def stop(self):
        self.__stopevent.set()
        return True
        
    def refresh_counter(self):

        counter_value = self.property_get("counter").value
        self.property_set("counter", Sample(0, counter_value + 1000))
        return
        
    ## Locally defined functions:
    # Property callback functions:
    def prop_set_counter_reset(self, ignored_sample):
        self.property_set("counter",
            Sample(0, SettingsBase.get_setting(self, "count_init")))

    def prop_set_global_reset(self, ignored_sample):
        self.prop_set_counter_reset(ignored_sample=0)
        self.property_set("adder_total", Sample(0, 0.0))
        self.property_set("adder_reg1", Sample(0, 0.0))
        self.property_set("adder_reg2", Sample(0, 0.0))

    def prop_set_adder(self, register_name, float_sample):
        self.property_set(register_name, float_sample)
        # update total:
        adder_reg1 = self.property_get("adder_reg1").value
        adder_reg2 = self.property_get("adder_reg2").value
        self.property_set("adder_total", Sample(0, adder_reg1 + adder_reg2))

    # Threading related functions:
    def run(self):

        self.prop_set_global_reset(0)

        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break

            # increment counter property:
            counter_value = self.property_get("counter").value
            self.property_set("counter",
                Sample(0, counter_value + 1))
            digitime.sleep(SettingsBase.get_setting(self,"update_rate"))


# internal functions & classes
