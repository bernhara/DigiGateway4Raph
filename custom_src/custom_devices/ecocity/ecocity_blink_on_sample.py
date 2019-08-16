# $Id: ecocity_blink_on_sample.py 1344 2014-11-26 13:45:57Z orba6563 $

# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import * #@UnusedImport

from custom_lib.runtimeutils import on_digi_board
if on_digi_board():
    import digihw #@UnresolvedImport
    import digicli #@UnresolvedImport

from custom_lib.commons.pangoolib import init_module_logger, check_debug_level_setting, update_logging_level 

class EcocityBlinkOnSampleDevice(DeviceBase, threading.Thread):
    
    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        
        self.__logger = init_module_logger(logger_name=name, max_backups=1)        

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='update_rate', type=float, required=False, default_value=5.0,
                  verify_function=lambda x: x > 0.0),
                         
            Setting(name='blinks', type=int, required=False, default_value=20, verify_function=lambda x: (x > 0 and x < 50)),
            Setting(name='blink_speed', type=float, required=False, default_value=0.25, verify_function=lambda x: (x > 0.0 and x < 5.0)),
            Setting(name='cli_command', type=str, required=False, default_value=''),
            
            Setting(name='command_channel', type=str, required=True),
            
            Setting(name='log_level', type=str, required=False, default_value='DEBUG', verify_function=check_debug_level_setting),
                   
        ]

        ## Channel Properties Definition:
        property_list = [
        ]
                                            
        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)
        
    ## Functions which must be implemented to conform to the PresentationBase
    ## interface:
    def apply_settings(self):
        """
            Apply settings as they are defined by the configuration file.
        """
        
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        if len(rejected) or len(not_found):
            self.__logger.error("Settings rejected/not found: %s %s", rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        update_logging_level (self.__logger, SettingsBase.get_setting(self, 'log_level')) 
        
        return (accepted, rejected, not_found)        


    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def start(self):
        
        cm = self.__core.get_service("channel_manager")        

        # subscribe to all the channels that drive our logic
        cp = cm.channel_publisher_get()
        channel_name = SettingsBase.get_setting(self, 'command_channel')
        self.__logger.info("Subscribing to command channel: %s" % channel_name)        
        cp.subscribe(channel_name, self.__new_ecocity_command)

        threading.Thread.start(self)

        return True

    def stop(self):
        self.__stopevent.set()
        return True
        
        
    ## Locally defined functions:
        
    def __do_blink(self):
        
        blinks = SettingsBase.get_setting(self,"blinks")
        blink_speed = SettingsBase.get_setting(self,"blink_speed")
        
        self.__logger.debug ("Start blinking")
        for _ in range (1,blinks):
            # Turn on user LED's
            self.__logger.info ("Led ON")
            if on_digi_board():
                digihw.user_led_set(1, 1)
            digitime.sleep(blink_speed)
            
            # Turn off the LED's
            self.__logger.info ("Led OFF")            
            if on_digi_board():
                digihw.user_led_set(0, 1)
            digitime.sleep(blink_speed)

        self.__logger.debug ("End blinking")
        # Turn off to prevent any strange behavior
        self.__logger.info ("Force led OFF")            
        if on_digi_board():
            digihw.user_led_set(0, 1)
            
        cli_command = SettingsBase.get_setting(self,"cli_command")
        self.__logger.info ("Issue the command: %s" % cli_command)
        if (on_digi_board() and len(cli_command)>0):
            self.__logger.debug('Calling digicli...')
            status, output = digicli.digicli(cli_command)
            if status:
                for line in output:
                    self.__logger.info ('Command result: %s' % line)
            else:
                self.__logger.error ('Error while executing command: %d, %s' % (status, output))
 
    def __new_ecocity_command(self, command_channel):
        command_sample = command_channel.get()
        self.__logger.info ("received command %s\n" % command_sample.value)
        self.__do_blink()
      
 
    # Threading related functions:
    def run(self):
        
        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break

            # increment counter property:
            digitime.sleep(SettingsBase.get_setting(self,"update_rate"))


# internal functions & classes
