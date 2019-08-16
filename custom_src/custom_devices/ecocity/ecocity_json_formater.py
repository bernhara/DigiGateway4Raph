# -*- coding: utf8 -*-
# $Id: ecocity_json_formater.py 1427 2014-12-23 12:24:36Z orba6563 $

"""
    Custom iDigi Dia 'EcocityJsonFormater' device driver
    
    Accepted JSON commands
        {
            "publicKey": "_ ecocity key of device which should execute the command _",
            "name": "_ the name of the command _",
            "parameters": "_ a table (optionally of size null) of parameters _"
        }
        
        Acceptable command names for a gateway:
        
            "REBOOT": issue a reboot of the gateway. Parameters are ignored
                ex: {"publickKey":"gw_ec_K1", "name":"REBOOT", "parameters":{}}
            
            "DIGI_CLI": executes as a "command line" the instructions in parameter table
                Parameter table must be of the form { "cli_command": "_ a base 64 encoded string compliant to DG cli interpreter _"
                ex: {"publickKey":"gw_ec_K1", "name":"DIGI_CLI", "parameters" : {"cli_command_b64": "_ base64(boot a=r) _"}}
                
            "FORWARD": sends to the sensor identified by publicKey the frame specified in the parameter
                Parameter table must be of form {"frame_b64": "..."}} where the value us base64 encoded
                {"publickKey":"sensor_ec_K1", "name":"FORWARD", "parameters" : {"frame_b64": "..."}}

"""
__version__ = "$LastChangedRevision: 1427 $"
VERSION_NUMBER = '$LastChangedRevision: 1427 $'[22:-2]


# imports

import string
import digitime #@UnusedImport
import digicli
import traceback
import common.digi_device_info
from common.utils import wild_match


#--- Pangoo common definitions
from custom_lib.commons.pangoolib import check_debug_level_setting, update_logging_level, init_module_logger

import threading #@UnusedImport

from settings.settings_base import SettingsBase, Setting
from devices.device_base import DeviceBase
from channels.channel_source_device_property import \
    DPROP_OPT_AUTOTIMESTAMP, \
    DPROP_PERM_GET, \
    Sample, \
    ChannelSourceDeviceProperty

import custom_lib.json.simplejson as json #@UnresolvedImport

import base64

# constants

_PUSHJSON_TEMPLATE = string.Template("""
{
    "source": {
        "member": {"a":"$device", "d":"$adapter", "ts": $timestamp},
        "accessPoint":{"a":"$accessPoint", "d":"$adapter", "ts": $timestamp}
    },
    "events": [ {
        "source": [
            {"a":"$device", "d":"$adapter", "ts": $timestamp},
            {"a":"$accessPoint", "d":"$adapter", "ts": $timestamp}
        ],
        "status":{"$sensor":"$value"},
        "trigger":"change"
    } ]
}
""")

# exception classes

# interface functions

# classes
class EcocityJsonFormater(DeviceBase, threading.Thread):

    def __init__(self, name, core_services):
        
        
        ## Initialize and declare class variables
        self.__name = name
        self.__core = core_services
        self.__cm = self.__core.get_service("channel_manager")
        self.__cp = self.__cm.channel_publisher_get()
        self.__cdb = self.__cm.channel_database_get()
        self._ec_key_to_dia_command_channel_name_cache = {}
        
        self._logger = init_module_logger(name)
        self._subscribed_channels = []
        
        self._ec_access_point_pub_key_setting = None
        self._dia_module_name_to_ec_device_public_key_setting_map = None
        self._sensor_channel_list_to_subscribe_to_setting = None
        self._incoming_command_channel_setting = None
        
        # semaphores and synchronization variables
        self._receive_sensor_data_callback_lock = threading.Lock()
        
        # will be appended to a DIA module name to get the name of the
        # channel to be used to send received commands
        self._sensor_channel_name_where_to_forward_commands = "command"
        
        settings_list = [
            Setting(name='ec_access_point_pub_key', type=str, required=False),
            Setting(name='channels', type=list, required=True, default_value=[]),
            Setting(name='exclude', type=list, required=False, default_value=[]),
            Setting(name='dia_channel_to_ec_sensor', type=dict, required=False, default_value={}),
            Setting(name='dia_module_to_ec_pub_key', type=dict, required=False, default_value={}),
            Setting(name='incoming_command_channel', type=str, required=False, default_value=''),

            Setting(name='log_level', type=str, required=False, default_value='DEBUG', verify_function=check_debug_level_setting),

        ]
        
        # Channel Properties Definition:
        
        property_list = [
                         
            #  properties
            
            ChannelSourceDeviceProperty(name='json_data', type=str,
                initial=Sample(timestamp=digitime.time(), value=""),
                perms_mask= DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP), 
                         
            ChannelSourceDeviceProperty(name='software_version', type=str,
                initial=Sample(timestamp=digitime.time(), value=VERSION_NUMBER),
                perms_mask= DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),                         

        ]        
        
        
        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                        settings_list, property_list)
        
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
            self._logger.error("Settings rejected/not found: %s %s", rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        update_logging_level (self._logger, SettingsBase.get_setting(self, 'log_level')) 
        
        self._dia_channel_name_to_ec_sensor_name_setting_map = SettingsBase.get_setting(self, 'dia_channel_to_ec_sensor')  
        self._dia_module_name_to_ec_device_public_key_setting_map = SettingsBase.get_setting(self, 'dia_module_to_ec_pub_key')
        self._sensor_channel_list_to_subscribe_to_setting = SettingsBase.get_setting(self, 'channels')       
        self._ec_access_point_pub_key_setting = SettingsBase.get_setting(self, 'ec_access_point_pub_key')
        self._incoming_command_channel_setting = SettingsBase.get_setting(self, 'incoming_command_channel')
        
        return (accepted, rejected, not_found)

    def start(self):
        """
            Start the presentation object.
        """
        
        self.__cp.subscribe_new_channels(self._add_new_channel)
        channels = self.__cdb.channel_list()
        for channel in channels:
            self._add_new_channel(channel)
            
        # subscribe to command channel
        if (len (self._incoming_command_channel_setting) > 0):
            self._logger.info("Subscribing to command channel: %s" % self._incoming_command_channel_setting)        
            self.__cp.subscribe(self._incoming_command_channel_setting, self._new_ecocity_command_callback)            
                 
        self._logger.info("Started.")
        
        threading.Thread.start(self)            

        return True

    def stop(self):
        """
            Stop the presentation object.
        """
        
        return True

# Internal functions & classes

    def _valid_value_for_json_attribute (self, current_str_value, can_be_empty_string=False):
        
        
        if current_str_value:
            # not None
            if can_be_empty_string:
                return current_str_value
                # NOT REACHED
            elif len(current_str_value) > 0:
                return current_str_value
                # NOT REACHED
                
        return "_UNDEFINED_"

    def _build_json_data (self, ec_device_public_key, adapterId, float_ts, ec_accespoint_pub_key, ecn_sensor_name, value_object):
        
        # check each argument to prevent generating wrong Json
        json_ec_device_public_key = self._valid_value_for_json_attribute(ec_device_public_key)
        json_adapterId = self._valid_value_for_json_attribute(adapterId)
        # currently, timestamps with millisecond accuracy are not supported by Ecocity
        # round the timestamp to the second
        json_ts = self._valid_value_for_json_attribute(str(int(float_ts)))
        json_ec_accespoint_pub_key = self._valid_value_for_json_attribute(ec_accespoint_pub_key)
        json_ecn_sensor_name = self._valid_value_for_json_attribute(ecn_sensor_name)
        
        value_object_type = type(value_object)
        if (value_object_type == 'str'):
            str_value_object = value_object
        else :
            str_value_object = str(value_object)
        json_cv = self._valid_value_for_json_attribute(str_value_object)

        values = {
            'accessPoint' : json_ec_accespoint_pub_key,
            'device': json_ec_device_public_key,
            'adapter': json_adapterId,
            'timestamp': json_ts,
            'sensor': json_ecn_sensor_name,
            'value': json_cv
        }

        json_data = _PUSHJSON_TEMPLATE.substitute(values)

        return json_data
       
    # Called whenever there is a new sample
    # Keyword arguments:
    # channel -- the channel with the new sample
    #
    # This function handles reentrance, since sensors uploading data are acting in parallel.
    # Indeed, the callback is called asynchronously
    # 
    def _receive_sensor_data_callback_synchronized(self, channel):
        
        try:
            # critical section start
            self._receive_sensor_data_callback_lock.acquire()
            
            try:
                sample = channel.get()
                # timestamp value
                ts = sample.timestamp
                self._logger.debug('sample timestamps : %s' %(ts))
                # channel name (temperature, light, ...)
                dia_module_name, dia_channel_name = channel.name().split ('.')
                self._logger.debug('DIA channel name: %s' % dia_channel_name)
                 
                # Compute the EC sensor name
                # map dia channel name to ec sensor name
                if self._dia_channel_name_to_ec_sensor_name_setting_map.has_key(dia_channel_name):
                    ecn_sensor_name = self._dia_channel_name_to_ec_sensor_name_setting_map.get(dia_channel_name)
                else:
                    ecn_sensor_name = dia_channel_name
                self._logger.debug('EC corresponding sensor name: %s' % ecn_sensor_name)
                
                # Compute the EC device public key
                # map the dia module name to a key
                if self._dia_module_name_to_ec_device_public_key_setting_map.has_key(dia_module_name):
                    ecn_device_public_key = self._dia_module_name_to_ec_device_public_key_setting_map.get(dia_module_name)
                else:
                    # the key is the module mame          
                    ecn_device_public_key = dia_module_name
                self._logger.debug('EC device public key: %s' % ecn_device_public_key)
                
                # channel value
                cv = sample.value
                
                ec_accespoint_pub_key = self._get_gw_id_for_ecn()
                self._logger.info('EC access point public key: %s' %(ec_accespoint_pub_key))
                # domainId
                dId = 'SBI_ECN'
    
                json_data = self._build_json_data (ecn_device_public_key, dId, ts, ec_accespoint_pub_key, ecn_sensor_name, cv)
                self._logger.info('json_data is : %s' %(json_data))
                
                self.property_set("json_data", Sample(0, json_data))
                
            except :
                self._logger.error('Unexpected error !!!')
                self._logger.error(traceback.format_exc())
                return
            
        finally:
            # critical section end 
            self._receive_sensor_data_callback_lock.release()
            
    #################################################################################################
    def _new_ecocity_command_callback(self, command_channel):
        """
        This callback is called when new samples are received from the "command" DIA channel
        """                
        command_sample = command_channel.get()
        
        json_ecocity_command = command_sample.value
        self._logger.debug ("received a ecocity command %s\n" % json_ecocity_command)
        
        # decode the ecocity command
        # command example: {"publickKey":"K_raph_1","name":"REBOOT","parameters":{}}
        try:
            json_object = json.loads(json_ecocity_command)
        except ValueError, ve:
            self._logger.error ("Decode error of Json string: %s." % json_ecocity_command)
            self._logger.error ("Error was: %s" % ve)
            return False   
        
        # FIXME: correct syntax error in "publicKey"
        command_destination_public_key = json_object.get (u'publickKey')
        command_name = json_object.get (u'name')
        command_parameter_dict = json_object.get (u'parameters')
        
        # All fields are mandatory
        if (not command_destination_public_key or not command_channel or not command_parameter_dict):
            # FIXME: called event with good values
            self._logger.error ("Received Json ecocity command does not contain mandatory fields: %s" % json_ecocity_command)   
                
        self._route_ecocity_command(command_destination_public_key, command_name, command_parameter_dict)
        
    def _route_ecocity_command (self, command_destination_public_key, command_name, command_parameter_dict = None):
        """
        Route the received Ecocity commands, choosing between local execution or forwarding to attached device
        Keyword arguments:
        command_destination_public_key -- Ecocity unique key which identifies the Ecocity device
        command_name -- one of the predefined commands
        command_parameter_dict -- optional command parameters
        """                
        # check is the command is for the gateway itself
        if (command_destination_public_key == self._ec_access_point_pub_key_setting):
            self._route_locally_ecocity_command (command_name, command_parameter_dict)
        else:
            self._route_forward_command (command_destination_public_key, command_name, command_parameter_dict)
            
    def _route_locally_ecocity_command (self, ecocity_command_name, command_parameter_dict = None):
        """
        Handle locally (on the GW) the command received from the Ecocity, which means evaluate the command
        Keyword arguments:
        ecocity_command_name -- the command as defined by Ecocity
        command_parameters -- optional command parameters
        """        
        self._logger.info ('Gateway asked to execute an Ecocity command: %s' % ecocity_command_name)
        
        # Recognize the command
        case_not_matched = True
        
        # REBOOT command
        if (case_not_matched and 'REBOOT' == ecocity_command_name):
            case_not_matched = False
                        
            self._logger.debug ('Recognized a "REBOOT" ecocity command')
            
            cli_command = 'boot a=r'
            self._issue_cli_command(cli_command)

        # DIGI_CLI command            
        elif (case_not_matched and 'DIGI_CLI' == ecocity_command_name):
            case_not_matched = False 
                       
            self._logger.debug ('Recognized a "DIGI_CLI" ecocity command with python dict argument:  %s' % str(command_parameter_dict))
            
            # FIXME: parse argument to get what to execute
            cli_command_b64 = command_parameter_dict.get(u'cli_command_b64')
            cli_command = base64.b64decode (cli_command_b64)
            if (cli_command):   
                self._issue_cli_command(cli_command)
            else:
                self._logger.error ('Could not find the "cli_command" argument for Ecocity CLI command. No command executed.')
                
        else:
            self._logger.error ('Unrecognized (and ignored) Ecocity command received by the gateway: %s' % ecocity_command_name)

    def _issue_cli_command (self, cli_command):
        """
        Call digicli
        Keyword arguments:
        cli_command -- the command string as expected by cli interpreter
        """ 
        self._logger.info ('Gateway will issue cli command: %s' % cli_command)
        cli_command_ok, cli_command_output = digicli.digicli(cli_command)
        cli_command_output_str = str(cli_command_output)
        if (not cli_command_ok):
            self._logger.error ("CLI command \"%s\" return and error: %s" % (cli_command, cli_command_output_str))   
            
        return (cli_command_ok, cli_command_output)                            
        
    """
    TBD
    TODO: document
    """
    def _route_forward_command (self, command_destination_public_key, command_name, command_parameters):
        
        # Recognize the command
        case_not_matched = True
        
        if case_not_matched and 'FORWARD' == command_name:
            case_not_matched = False
            
            #
            # decode parameters
            #
            
            frame_b64 = command_parameters.get('frame_b64')
            if not frame_b64:
                self._logger.error ('Missing argument to FORWARD command received by the gateway: %s' % command_name)
                return False
            
            decoded_frame = base64.b64decode(frame_b64)
                

            #
            # Search for DIA channel to write to
            # ----------------------------------
            #
            
            # If we previously received a command for this public key and get the corresponding DIA channel,
            # the DIA channel is already in the cache
            dia_command_channel = None
            
            if (self._ec_key_to_dia_command_channel_name_cache.has_key(command_destination_public_key)):
                dia_command_channel = self._ec_key_to_dia_command_channel_name_cache.get(command_destination_public_key)
                self._logger.debug ("Retrieved from cash the channel where we have to write the command for ecocity key \"%s\": %s" % (command_destination_public_key, dia_command_channel.name()))
                
            else:
                # We have to find that channel which will be used to forward the commands
            
                # Check if public key is know and identify the DIA module having that key
                command_destination_dia_module_name = None
                for dia_module_name, known_ec_public_key in self._dia_module_name_to_ec_device_public_key_setting_map.items():
                    if command_destination_public_key == known_ec_public_key:
                        command_destination_dia_module_name = dia_module_name
                        break
                
                if (not command_destination_dia_module_name):
                    self._logger.error ('No destination DIA channel for public key \"%s\" found.' % command_destination_public_key)
                    return False
                    # NOT REACHED
                
                # The Ecocity public key could be matched to a known DIA module
                # The variable command_destination_dia_module_name contains the name of the
                # DIA module with have to send the command
                
                
                command_destination_dia_channel_name = command_destination_dia_module_name + '.' + self._sensor_channel_name_where_to_forward_commands
                
                # check if channel exists in channel database
                if (self.__cdb.channel_exists(command_destination_dia_channel_name)):
                    # get that channel
                    dia_command_channel = self.__cdb.channel_get(command_destination_dia_channel_name)
                    # and store found channel into cache
                    self._ec_key_to_dia_command_channel_name_cache[command_destination_public_key] = dia_command_channel
                    self._logger.debug ("Got the channel where we have to write the command for ecocity key \"%s\": %s" % (command_destination_public_key, dia_command_channel.name()))
                else:
                    self._logger.error('Could not retrieve DIA channel named: %s' % command_destination_dia_channel_name)
                    return False
                    # NOT REACHED
                    
                    
            # Variable dia_command_channel contains now the channel to write to
    
            #
            # Send the command to that channel
            #
            command_sample = Sample(timestamp=0, value=decoded_frame)
            try:
                dia_command_channel.set(command_sample)
            except Exception, msg:
                self._logger.error('Could not send message to channel: %s' % command_destination_dia_channel_name)
                self._logger.error('Error was: %s' % msg)
                return False
                    
            return True

        else:
            self._logger.error ('Unrecognized (and ignored) Ecocity command received by the gateway: %s' % command_name)
 
    #
    # --
    #        

    def _get_gw_id_for_ecn (self):
        """
        Return the gateway ECN id as expected by ECN to identify uniquely the gateway
        When the setting is not defined, returns Digi's device ID
        """
        
        ecn_id ="__unknown__"

        if (self._ec_access_point_pub_key_setting):
            # provided as a setting
            ecn_id = self._ec_access_point_pub_key_setting
        else:
            # not provided
            if common.digi_device_info.rci_available():
                cpx_id = common.digi_device_info.get_device_id()
                ecn_id = self._cpx_id_to_ecn_id(cpx_id)
            else:
                self._logger.error ("No access point EC public key set and could not get the gateway id")
                
        self._logger.debug ("Got ECN id: %s" % ecn_id)
                
        return ecn_id
    
    #
    # --
    #    
    
    def _cpx_id_to_ecn_id (self, cpx_id):
        
        # check if the cpx id is of form "0x000000000000000000409dffff510935"
        
        cpx_id_hex_representation=cpx_id.lower()
    
        try:
            id_as_int=int(cpx_id_hex_representation, 0)
        except:
            # no match: return cpx_id without any change
            return cpx_id
            
        # check the numerical representation
        int_id_as_hex_string="0x%032x" % id_as_int
        long_hex_str="%032x" % id_as_int
    
        if int_id_as_hex_string == cpx_id_hex_representation:
            #the cpx id is in the GW form
            #transform the cpx id into the ecn id 
            ecn_id="%s-%s-%s-%s" % (long_hex_str[0:8], long_hex_str[8:16], long_hex_str[16:24], long_hex_str[24:32])
            # ECN ids for GW are the GW if in *UPPERCASE* (to easy cut&paste from the GUI)           
            ecn_id = ecn_id.upper()
            
            return ecn_id
        else:
            #the cpx id is not in the GW form: return cpx_id without any change
            return cpx_id

    
    #
    # --
    #
    def _add_new_channel(self, channel_name):
        '''
        Callback for newly registered channels.
        We check if they should be tracked and if so, add them.
        '''
        self._logger.debug ("New channel available: %s" % channel_name)

        channel_list = self._sensor_channel_list_to_subscribe_to_setting
        # channel_list != Node: mandatory setting
        
        # search first for exact match
        self._logger.debug ("Checking if channel matches one of %s" % str(channel_list))
        if (channel_name in channel_list):
            self._logger.debug('Subscribing to channel: %s' % channel_name)
            self._subscribe(channel_name)
            
            return
            # NOT REACHED
        else:
            # check for wildcards
            wild_list = [x for x in channel_list if (x.find('*') != -1) or (x.find('?') != -1)]
            for i in wild_list:
                if wild_match(i, channel_name):
                    self._logger.debug('Channel name matches pattern %s.' % i)
                    self._logger.debug('Subscribing to channel %s.' % channel_name)
                    self._subscribe(channel_name)

                    return
                    # NOT REACHED
                    
            
        # otherwise, ignore the new channel
        self._logger.debug('Channel %s not matched in %s.' % (channel_name, str(channel_list)))

    def _subscribe(self, channel, new_sample_callback=None):
        '''
        subscribe to a channel

        If fname=None, defaults to listening for new samples
        and is added to the registry.
        '''
        if new_sample_callback == None:
            new_sample_callback = self._receive_sensor_data_callback_synchronized
            
        if channel not in self._subscribed_channels:
            self._logger.info('Adding to channel manager subscription for channel %s.' % channel)
            self.__cp.subscribe(channel, new_sample_callback)
            self._subscribed_channels.append(channel)
        else:
            self._logger.error('Channel %s already subscribed.' % (channel))
     
    def run(self):

        self._logger.debug("starting to run.")
        
        while not self.__stopevent.isSet():
            digitime.sleep (60)
            
        self._logger.info("Out of run loop.  Shutting down...")

        # Clean up channel registration
        self.__cp.unsubscribe_from_all(self._receive_sensor_data_callback_synchronized)
