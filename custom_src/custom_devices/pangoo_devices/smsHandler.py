#!/usr/bin/python
# $Id: smsHandler.py 7436 2012-01-09 15:49:39Z orba6563 $
"""This driver waits for an SMS and processes the message"""

from custom_lib.runtimeutils import on_digi_board

import logging
import sys

if (on_digi_board()):
    import digisms #@UnresolvedImport
    import digicli #@UnresolvedImport
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

from custom_lib import logutils

class SMSHandler(DeviceBase):

    def __init__(self, name, core_services):
        """Basic initialization of members in class"""
        self.__name = name
        self.__core = core_services
        self.cb_handle = None

        self.init_module_logger()
    
        ## Settings Table Definition:
        settings_list = [
            Setting(
                    name='reboot_msg', type=str, required=False, default_value='REBOOT54321',
                    verify_function=lambda x: type(x) == str),
            Setting(
                name='log_level', type=str, required=False, default_value='DEBUG', verify_function=self.check_debug_level_setting),
        ]
    
        ## Channel Properties Definition:
        property_list = []
                                                
        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)
    
        ## Thread initialization:
        self.__stopevent = threading.Event()
        
    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:    
    def apply_settings(self):
        """Called when new configuration settings are available.
       
        Must return tuple of three dictionaries: a dictionary of
        accepted settings, a dictionary of rejected settings,
        and a dictionary of required settings that were not
        found.
        """
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        if len(rejected) or len(not_found):
            self.logger.warn("%s(%s): settings rejected/not found: %s/%s" % 
                    (self.__class__.__name__, self.__name, rejected, not_found))
    
        SettingsBase.commit_settings(self, accepted)
        
        new_level_string = SettingsBase.get_setting(self, 'log_level')
        try:
            # The syntax of the setting has already been verified
            new_level = eval ('logging.' + new_level_string)
            self.logger.setLevel (new_level)
        except Exception:
            # new_level_string is not an attribube of the logging package
            self.logger.error ('SmsHandler setting change error for log_level: should be DEBUG, ERROR, ...')        
   
        return (accepted, rejected, not_found)
    
    def start(self):
        """Start the device driver.  Registers callback for SMS messages.  Returns bool."""
        if (on_digi_board()):
            self.cb_handle = digisms.Callback(self.receiveSMS)
            if self.cb_handle == None:
                self.logger.error('SMS callback not handled')
                return False
            else:
                self.logger.info('SMS callback hooked up %s' % self.cb_handle)
        else:
            self.logger.info ('SMS drv: not on a digi board -> cannot register SMS handler')
     
        return True
    
    def stop(self):
        """Stop the device driver.  Returns bool."""
        self.__stopevent.set()
        
        return True
        
## Locally defined functions:
    def receiveSMS(self, msg):
        """This is the callback function when a message is received.  It simply checks the message for a
        reboot string and then reboots."""
        self.logger.info('SMS drv receivedSMS:%s' % msg)
        reboot_str = SettingsBase.get_setting(self, 'reboot_msg')
        if msg.message.startswith(reboot_str):
            self.logger.info('SMS reboot request: perform immediate reboot action')
            digicli.digicli('boot action=reset')

    #---------------------
    def check_debug_level_setting(self, new_level_string):
        
            setting_syntax_valid = True
    
            try:
                new_level = eval ('logging.' + new_level_string)
                int(new_level) # raise an eception in we did not get an integer value
                setting_syntax_valid = True
            except Exception:
                setting_syntax_valid = False
                
            return setting_syntax_valid
    
    #---------------------
    def init_module_logger(self):
        
        # TODO: switch to std logging with config file / http://g-polarion-pangoov4/polarion/redirect/project/PANGOO_PF_DEV/workitem?id=PF-91
        # ... logging.config.fileConfig(logging_config_file)
    
        # logging setup
        if sys.platform.startswith('digi'):
            logging_file_prefix = 'WEB/python/'
        else:
            logging_file_prefix = ''
        
        self.logger = logging.getLogger("SMSh_dd")
        fmt = logging.Formatter("%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s", "%Y-%m-%d %H:%M:%S")
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)
        
        
        handler = logutils.SmartHandler(filename=logging_file_prefix + 'log_SMSh_dd.txt', buffer_size=10, flush_level=logging.INFO, flush_window=300)
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)
    
#=============================
def main():
    print "test"

#------------------------
if __name__ == '__main__':
    main()


