# $Id: waspmote_device.py 1483 2015-12-30 09:27:00Z orba6563 $

"""
    iDigi Dia 'Waspmote' Device Driver
    Custom driver for Waspmote from Libelium

Settings

	xbee_device_manager: must be set to the name of an XBeeDeviceManager  instance.
	extended_address: the extended address of the XBee Sensor device you would like to monitor.

Advanced settings:
 
     drop_commands_preceding_running_indication: if False, send forward commands to the XBee device,
         even if gateway did no receive a running indication

"""
#
# std packages
#
import traceback

import digitime #@UnusedImport

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
class Waspmote(XBeeBase):
    '''
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.
    '''
 
    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [bindpoints.SERIAL, bindpoints.SAMPLE]

    # The list of supported products that this driver supports.

    # (I'm cheating here... any digi product should work!)
    SUPPORTED_PRODUCTS = range(0x1a)
  

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        
        self._logger = init_module_logger(name)        

        ## Local State Variables:
        self.__xbee_manager = None
        self._end_device_attached = False # becomes True once the device is attached to the GW (see RunningIndication)
        
        self._extended_address_setting = None
        self._drop_commands_preceding_running_indication_setting = None
        
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
                name='drop_commands_preceding_running_indication', type=bool, required=False, default_value=True),                    

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
        

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

    ## Functions which must be implemented to conform to the XBeeBase
    ## interface:

    @staticmethod
    def probe():
        #   Collect important information about the driver.
        #
        #   .. Note::
        #
        #       This method is a static method.  As such, all data returned
        #       must be accessible from the class without having a instance
        #       of the device created.
        #
        #   Returns a dictionary that must contain the following 2 keys:
        #           1) address_table:
        #              A list of XBee address tuples with the first part of the
        #              address removed that this device might send data to.
        #              For example: [ 0xe8, 0xc105, 0x95 ]
        #           2) supported_products:
        #              A list of product values that this driver supports.
        #              Generally, this will consist of Product Types that
        #              can be found in 'devices/xbee/common/prodid.py'

        probe_data = XBeeBase.probe()

        for address in Waspmote.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in Waspmote.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

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
        
        self._drop_commands_preceding_for_running_setting = SettingsBase.get_setting(self, 'drop_commands_preceding_running_indication')

        update_logging_level (self._logger, SettingsBase.get_setting(self, 'log_level'))
        
        # Get the extended address of the device:
        self._extended_address_setting = SettingsBase.get_setting(self, "extended_address")

            
        return (accepted, rejected, not_found)

    def start(self):

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self,
                                                     "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)


        # Create a callback specification for our device address
        self.__xbee_manager.register_serial_listener(self,
                                                 self._extended_address_setting,
                                                 self.__read_callback)
        # Create a callback specification that calls back this driver when
        # our device has left the configuring state and has transitioned
        # to the running state:
        xbdm_running_event_spec = XBeeDeviceManagerRunningEventSpec()
        xbdm_running_event_spec.cb_set(self._running_indication)
        self.__xbee_manager.xbee_device_event_spec_add(self, xbdm_running_event_spec)

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(self._extended_address_setting) #@UnusedVariable

        
        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        return True

    def stop(self):

        if self.__xbee_manager is not None:
            # Unregister ourselves with the XBee Device Manager instance:
            self.__xbee_manager.xbee_device_unregister(self)

        return True

    ## Locally defined functions:
    def time_of_last_data(self):
        return self._last_timestamp

    def _running_indication(self):
        # request initial status here.
        self._logger.info("Running indication")
      
        # this is a flawed design - if the gateway has just rebooted,
        # and the Xbee sensor sleeps (which it should), then an actual
        # GET_DDO will be issued, which causes Dia to freeze here and
        # almost certainly throw exception and put the device off line.
        
        try:
            dd_value = self.__xbee_manager.xbee_device_ddo_get_param(self._extended_address_setting, 'DD', use_cache=True)
        except:
            self._logger.info('Using default DD')
            dd_value = 0x0003000E

        module_id, product_id = parse_dd(dd_value)
        self._logger.info('DD info (module_id, product_id) (0x%04x, 0x%04x)' % (module_id, product_id))
        
        # Consider now that the device is attached
        self._end_device_attached = True
        
       
    

    def __read_callback(self, data, addr):
        
        try:
            
            self._logger.debug('Got %d bytes from profile 0xc105 cluster 17 %s' % (len(data), str (addr)))
            self._logger.debug('Data content: %s' % data)
            self._logger.debug('\tbinary dump: %s' % ''.join('\\x%02X ' % ord(x) for x in data))

            self._send_data_to_dia_channel(data, addr)

        except:   
            self._logger.critical('Encountered unexpected error while treating received xbee message!!!')
            self._logger.critical(traceback.format_exc())
            
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
                
