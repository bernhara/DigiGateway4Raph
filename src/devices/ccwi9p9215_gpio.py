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

# Imports
import digihw
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from samples.sample import Sample
from common.shutdown import SHUTDOWN_WAIT
import threading
import digitime

#Main class
class ModuleGPIOs(DeviceBase, threading.Thread):
    """
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.

    """
    
    #Class vars
    gpios = {}
    gpios_ind = {}
    setting_gpio=False
    for i in xrange (0,32):
        gpios["GPIO_"+str(i)]=0        
    for i in xrange (0,32):
        gpios_ind["GPIO_"+str(i)]=i
    
    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        self.setting_gpio = False
        
        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)
        
        ## Settings Table Definition:
        settings_list = [           
            Setting(
                name='input_gpios', type=list, required=True),
            Setting(
                name='output_gpios', type=list, required=True),
            Setting(                
                name='update_rate', type=float, required=False, 
                default_value=0.1,verify_function=lambda x: x > 0.0)
        ]
        
        ## Declare the GPIOs channels
        property_list = [        
            ChannelSourceDeviceProperty(name="GPIO_0",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_0",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_1",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_1",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_2",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_2",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_3",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_3",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_4",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_4",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_5",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_5",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_6",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_6",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_7",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_7",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_8",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_8",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_9",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_9",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_10",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_10",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_11",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_11",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_12",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_12",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_13",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_13",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_14",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_14",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_15",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_15",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_16",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_16",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_17",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_17",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_18",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_18",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_19",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_19",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_20",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_20",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_21",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_21",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_22",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_22",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_23",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_23",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_24",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_24",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_25",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_25",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_26",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_26",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_27",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_27",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_28",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_28",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_29",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_29",
                                                      sample=sample)),
            ChannelSourceDeviceProperty(name="GPIO_30",
                  type=bool,initial=Sample(0, False),                  
                  perms_mask=DPROP_PERM_GET|DPROP_PERM_SET,
                  options=DPROP_OPT_AUTOTIMESTAMP,
                  set_cb=lambda sample: self.set_gpio(gpio="GPIO_30",
                                                      sample=sample))
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
    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        if len(rejected) or len(not_found):
            self.__tracer.error("Settings rejected/not found: %s %s", 
                                rejected, not_found)

        if (('update_rate' in accepted) and 
            (accepted['update_rate'] > SHUTDOWN_WAIT)):
            self.__tracer.warning("Long update_rate setting may " + 
                                  "interfere with shutdown of DIA")
            
        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        threading.Thread.start(self)
        return True

    def stop(self):
        self.__stopevent.set()
        return True        

    # Threading related functions:
    def run(self):
        
        #Get the device properties
        time_sleep = SettingsBase.get_setting(self,"update_rate")

        self.input_gpios = SettingsBase.get_setting(self,"input_gpios")
        self.output_gpios = SettingsBase.get_setting(self,"output_gpios")
        
        #Call the GPIOs initializer method
        self.initialize_gpios()
        
        #Start the refresh thread
        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break

            try:
                while self.setting_gpio:
                    pass
                self.get_GPIOs()
            except Exception, e:
                self.__tracer.error("Unable to update values: %s", str(e))
            
            #Sleep the time configured in settings (in seconds)
            digitime.sleep(time_sleep)

    def set_gpio(self,gpio,sample):
        
        self.setting_gpio = True
        #Update the channel and the module GPIO
        if sample.value==True:            
            self.property_set(gpio,Sample(digitime.time(), True))
            digihw.gpio_set_value(self.gpios_ind[gpio], 1)
        else:
            self.property_set(gpio,Sample(digitime.time(), False))
            digihw.gpio_set_value(self.gpios_ind[gpio], 0)
        self.setting_gpio = False

    def get_GPIOs(self):
        
        for gpio in self.input_gpios:
            val = digihw.gpio_get_value(gpio)
            #If the GPIO value has changed, update its channel
            if self.gpios["GPIO_"+str(gpio)]!=val:
                self.gpios["GPIO_"+str(gpio)]=val            
                if val==0 :
                    self.property_set("GPIO_"+str(gpio),
                        Sample(digitime.time(), False))
                else:
                    self.property_set("GPIO_"+str(gpio),
                        Sample(digitime.time(), True))
    
    def initialize_gpios(self):
        
        for gpio in self.output_gpios:
            digihw.gpio_set_value(gpio,0)
        for gpio in self.input_gpios:
            digihw.gpio_set_input(gpio)
            
# Internal functions & classes
