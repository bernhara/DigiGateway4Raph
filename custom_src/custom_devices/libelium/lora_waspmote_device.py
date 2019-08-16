# $Id: lora_waspmote_device.py 1483 2015-12-30 09:27:00Z orba6563 $

"""
    iDigi Dia 'Waspmote' Device Driver
    Custom driver for Waspmote from Libelium

Settings

	lora_device_manager: must be set to the name of a LoraDeviceManager DD instance name.
	extended_address: the extended address of the XBee Sensor device you would like to monitor.

"""
#
# std packages
#
import traceback

import digitime #@UnusedImport

from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property \
    import \
        DPROP_OPT_AUTOTIMESTAMP, \
        DPROP_PERM_GET, \
        DPROP_PERM_SET, \
        Sample, \
        ChannelSourceDeviceProperty

from devices.xbee.xbee_devices.xbee_base import XBeeBase
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import \
        XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
     import \
        XBeeDeviceManagerRunningEventSpec

import devices.xbee.common.bindpoints as bindpoints
from devices.xbee.xbee_device_manager.xbee_device_manager \
    import \
        BINDPOINTS

from devices.xbee.common.prodid \
    import \
        parse_dd

from custom_devices.libelium.utils \
    import \
        libelium_to_dia_map, \
        Convert_Str_Float, \
        Convert_Str_Integer, \
        parser, \
        decode_waspmote_frame, \
        libelium_key_to_dia_channel_name

from custom_lib.commons.pangoolib \
    import \
        init_module_logger, \
        check_debug_level_setting, \
        update_logging_level

# constants
# =========

__version__ = "$LastChangedRevision: 1483 $"
VERSION_NUMBER = '$LastChangedRevision: 1483 $'[22:-2]


# Device Driver class
class LoraWaspmote(DeviceBase):
    '''
    TBD..
    '''
    # TODO: document
 
    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        
        self._logger = init_module_logger(name)        

        ## Local State Variables:
        self.__lora_manager = None
        
        self._extended_address_setting = None
        
        # Settings
        #
        # xbee_device_manager: must be set to the name of an XBeeDeviceManager
        #                      instance.
        # extended_address: the extended address of the XBee Sensor device you
        #                   would like to monitor.
        #
        # Advanced settings:
        #
        # None

        settings_list = [
                         
            Setting(
                name='lora_device_manager', type=str, required=True),
            Setting(
                name='extended_address', type=str, required=True),                         
                  
            Setting(
                name='log_level', type=str, required=False, default_value='DEBUG', verify_function=check_debug_level_setting),                  
          
            ]

        ## Channel Properties Definition:
        property_list = [
            # getable properties
            ChannelSourceDeviceProperty(name='software_version', type=str,
                initial=Sample(timestamp=digitime.time(), value=VERSION_NUMBER),
                perms_mask= DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
                         
            # setable properties
            ChannelSourceDeviceProperty(name='simulate_xbee_frame', type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask= DPROP_PERM_SET,
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self._simulate_xbee_frame_cb),
            ChannelSourceDeviceProperty(name='command', type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask= DPROP_PERM_SET,
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self._send_command_to_sensor_cb),                         
                         
         ]
        
        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                        settings_list, property_list)
                
        

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # there were problems with settings, terminate early:
            self._logger.error("Settings rejected/not found: %s %s",
                                rejected, not_found)

        SettingsBase.commit_settings(self, accepted)
        
        update_logging_level (self._logger, SettingsBase.get_setting(self, 'log_level'))
        
        # Get the extended address of the device:
        self._extended_address_setting = SettingsBase.get_setting(self, "extended_address")

        return (accepted, rejected, not_found)

    def start(self):

        # Fetch the Lora Manager name from the Settings Manager:
        self.__lora_manager = SettingsBase.get_setting(self, "lora_device_manager")
        
        lora_rx_frame_channel_name = "%s.%s" % (self.__lora_manager, "LoRaPlugAndSenseFrame") 
        
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        cp.subscribe(lora_rx_frame_channel_name, self.__lora_rx_frame_callback)
        
        self._logger.info ("Subscribed to lora frames received on channel %s" % lora_rx_frame_channel_name)
        self._logger.info ("Listening for frame sent to address: %s" % self._extended_address_setting)
               
        self._logger.info("Started.")

        return True

    def stop(self):
        return True
  
    def __lora_rx_frame_callback (self, channel):
        
        sample = channel.get()
        
        self._logger.debug ("Got new lora frame: %s" % sample.value)        
        
        my_addr_prefix = "#%s#" % self._extended_address_setting
        received_prefix_to_check = sample.value[0:len(my_addr_prefix)]
        
        if (received_prefix_to_check != my_addr_prefix):
            self._logger.debug ("Ignore frame, because I'm not the recipient")
            return
        
        addr = self._extended_address_setting
        data = sample.value[len(my_addr_prefix):]
        
        self.__read_callback (data, addr)

    def __read_callback(self, data, addr):
        
        self._logger.debug('Got %d bytes from device with address %s' % (len(data), str (addr)))
        self._logger.debug('Data content: %s' % data)
        self._logger.debug('\tbinary dump: %s' % ''.join('\\x%02X ' % ord(x) for x in data))

        self._send_data_to_dia_channel(data, addr)

    def _simulate_xbee_frame_cb (self, xbee_frame_sample):
        
        try:
        
            simulated_xbee_frame = xbee_frame_sample.value
            
            self._logger.debug('Got a simulated xbee frame: %s' % simulated_xbee_frame)
            
            self._send_data_to_dia_channel(simulated_xbee_frame, '__dummy_addr__')

        except:   
            self._logger.critical('Encountered unexpected error while treating simulated xbee message!!!')
            self._logger.critical(traceback.format_exc())            
                 

        
    def _send_data_to_dia_channel(self, frame, addr):
              
        self._last_timestamp = digitime.time()
        io_sample=parser(decode_waspmote_frame(frame))
        
        self._logger.debug ('Found following information: %s' % str(io_sample))
          
        # route each information to its corresponding channel
        for key in io_sample.keys():
            
            if libelium_to_dia_map.has_key(key):
                channel_name, type_name, channel_unit = libelium_to_dia_map[key]
            else:
                # add this key to existing map for next loop
                                # use default values =>
                # ... the new channel has the information name
                channel_name = libelium_key_to_dia_channel_name (key)
                # ... type will be default
                type_name = str
                # ... unit will be none
                channel_unit = ''

                # extend the map (initialized in utils) with this new key                
                libelium_to_dia_map[key] = (channel_name, type_name, channel_unit)
                

            #verify the type of the value
            if type_name=='float':
                    sample_value=Convert_Str_Float(io_sample[key])
            elif type_name=='int':
                    sample_value=Convert_Str_Integer(io_sample[key])
            else:
                    sample_value=io_sample[key]
                    
            sample = Sample(self._last_timestamp, sample_value, channel_unit)
            
            #verify if the channel already exists. I not, create it. 
            if not self.property_exists(channel_name):
                # create the new channel
                self.add_property(
                   ChannelSourceDeviceProperty(channel_name,
                                               type=type(sample_value),
                                               initial=sample,
                                               perms_mask=DPROP_PERM_GET,
                                               options=DPROP_OPT_AUTOTIMESTAMP))
                self._logger.info ("Created channel \"%s\" for key \"%s\"" % (channel_name, key))
                
            # send the new sample
            self._logger.debug ('Put %s data to dia channel: %s' % (key, channel_name))
            self.property_set(channel_name, sample)                
                
    def _send_command_to_sensor_cb(self, ecocity_command_sample):
        
        try:
            ecocity_command = ecocity_command_sample.value
            
            self._logger.debug('Got an ecocity command: %s' % ecocity_command)
            
            self._write_xbee(ecocity_command)

        except:   
            self._logger.critical('Encountered unexpected error while treating simulated xbee message!!!')
            self._logger.critical(traceback.format_exc())                    
                
    def _write_xbee(self, data):
        """\
        Writes a buffer of data out the XBee if attached to the gateway

        Returns True if successful, False on failure.
        """
        
        ret = False
        
        if not self._end_device_attached:
            # device is not yet attached to coordinator
            if self._drop_commands_preceding_running_indication_setting:
                self._logger.error ('Running indication not yet received for end device. Message dropped.')
                return ret
            
            else:
                self._logger.info ('Send message to device even if no running indication has been received.')
                
        self._logger.debug("Send Data to: %s, len %d.", str(self._extended_address_setting), len(data))
        
        bindpoint = BINDPOINTS[bindpoints.SERIAL]        
        endpoint = bindpoint['endpoint']
        profile_id = bindpoint['profile_id']
        cluster_id = bindpoint['cluster_id']

        addr = (self._extended_address_setting, endpoint, profile_id, cluster_id)
        try:
            self.__xbee_manager.xbee_device_xmit(0xe8, data, addr)
            ret = True
        except:
            self._logger.error('Error while sending data')
            self._logger.error(traceback.format_exc())
            
        return ret                
                
