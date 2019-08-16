# $Id: diasampleinjector.py 1348 2014-11-26 14:53:59Z orba6563 $
"""
    TBD: document the DD
"""

_VERSION_NUMBER = '$LastChangedRevision: 1348 $'[22:-2]

# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import ChannelSourceDeviceProperty, Sample, DPROP_PERM_GET, DPROP_PERM_SET, DPROP_OPT_AUTOTIMESTAMP

import threading
import digitime

from custom_lib.commons.pangoolib import init_module_logger, check_debug_level_setting, update_logging_level


# constants

_SLEEP_TIME_IN_MAINLOOP = 30.0

# exception classes

# interface functions

# classes

class DIASampleInjector(DeviceBase, threading.Thread):
    """
    TBD: document class
    """

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        
        self.__logger = init_module_logger(name)        

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='log_level', type=str, required=False, default_value='DEBUG', verify_function=check_debug_level_setting),                  
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties

            ChannelSourceDeviceProperty(name="raw_out", type=str,
                initial=Sample(timestamp=0, value=""),  
                perms_mask=DPROP_PERM_GET, 
                options=DPROP_OPT_AUTOTIMESTAMP),        

            # settable properties
            ChannelSourceDeviceProperty(name="raw_in", type=str,
                initial=Sample(timestamp=0, value='__INITIAL_SAMPLE__'), 
                perms_mask=DPROP_PERM_SET,
                set_cb=self.__prop_set_raw_in
            ),
                         
            ChannelSourceDeviceProperty(name='software_version', type=str,
                initial=Sample(timestamp=0, value=_VERSION_NUMBER),
                perms_mask= DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),                                             

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
            self.__logger.error("Settings rejected/not found: %s %s", 
                                rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        if ('log_level' in accepted):
            update_logging_level (self.__logger, SettingsBase.get_setting(self, 'log_level'))

        return (accepted, rejected, not_found)    

    def start(self):

        threading.Thread.start(self)

        return True

    def stop(self):
        self.__stopevent.set()
        return True
        
       
    ## Locally defined functions:
    # Property callback functions:
    def __prop_set_raw_in(self, in_sample):
        injected_raw_data = in_sample.value
        self.__logger.debug('Received a new raw input sample. String value=\"%s\". Hex value=\"%s\"' % (injected_raw_data, ''.join('0x%02X'%ord(x) for x in injected_raw_data)))
        self.property_set("raw_out", Sample(0, injected_raw_data))

    # Threading related functions:
    def run(self):

        self.__logger.info ("Starting DIA module %s" % self.__name)
        initial_sample = self.property_get("raw_in")
        print initial_sample.value;
        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break
                # NOT REACHED
            digitime.sleep(_SLEEP_TIME_IN_MAINLOOP)
        self.__logger.info ("Terminating DIA module %s" % self.__name)        

