# $Id: orbcomm.py 8064 2013-01-03 09:55:41Z orba6563 $
"""\
The Orbcomm Presentation.

This driver will receive and send packets to the server.  
When a message is received it will convert it into a packet for the waveport radio,
and then place it in the request channel for the radio.  It will subscribe to the 
response channel of the radio and when the channel is updated it will package the 
response and send it to the orbcomm.

Settings:

    destinations
        A list of dictionaries.  Each dictionary has two values 'value'
        and 'device_driver_name'.  The 'value' corresponds to the routing value at the
        beginning of each Orbcomm message.  A 'value' of 0 corresponds to a waveport
        packet.  So the 'device_driver_name' should map to the name of your waveport
        driver instance, normally 'waveport'.
        
    gateway_v1_backward_compatibility
        If true, supports initial wavecard frame format (used in first generation gateways)
    
    msg_size_on_7_bits
        If true, sizes (eg. message size) are code on 7 bits bytes
        
    do_waveport_initialization
        If true, send a sequence of initialization strings to the waveport at startup
        
    log_level
        Defines the log level, with a string value compliant to the std logger package (ie. DEBUG, ERROR, ...)
    
    port_num
        Defines the name of the serial port to open.
    
    baudrate
        Defines the baudrate of the serial port to open.

    desired_gateway
        Defines the ID of the desired gateway parameter for the m10 device.
        
    def_polled
        Defines the polling mode parameter for the m10 device.
    
    def_ack_level
        Defines the Ack level mode parameter for the m10 device.
        
    def_rep_or_ind
        Defines the default report OR parameter for the m10 device (default destination for repports).
    
    def_msg_or_ind
        Defines the default message OR parameter for the m10 device (default destination fo messages).
    
    def_priority
        Defines the default priority level parameter for the m10 device.
        
    def_msg_body_type
        Defines the default body type parameter for the m10 device.
        
    def_serv_type
        Defines service type the parameter for the m10 device (mix of ack level and priority cf. documentation).
        
    gwy_search_mode
        Defines the gateway search mode parameter for the m10 device.
"""

from custom_lib.runtimeutils import on_digi_board

from custom_lib.orbcomm_lib.m10_sc_api import SC_TERMMSG_PKT_TYPE, STATUS_PKT_TYPE, LLA_PKT_TYPE, UNKNOWN_PKT_TYPE

import sys
import traceback
import re

if on_digi_board():
    # import Digi board specific libraries
    import digicli #@UnresolvedImport
    import digiwdog #@UnresolvedImport
    
# imports
import threading
import logging
import Queue
import time

from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase
from samples.sample import Sample

# TODO: http://s-polarion-pangoov4/polarion/redirect/project/PangooDiaGW/workitem?id=DiaGW-33
from custom_lib import logutils
from custom_lib.orbcomm_lib import m10_sc_api
from symbol import argument

#--- Pangoo common definitions
from custom_lib.commons.pangoolib import * 

from custom_devices.pangoo_devices.coronis.waveport import REQ_READ_RADIO_PARAM, REQ_WRITE_RADIO_PARAM

# constants

#--- Pangoo Gateway cmd byte values
PG_CMD_ID = '\x7a'
PG_CMD_MSG = '\x7b'
PG_CMD_KALIVE = '\x7c'
PG_CMD_TRANS = '\x55'

#--- Pangoo Gateway routing byte values:
PG_ROUTE_WP = 0 # route to waveport

#--- As header part of existing Query Endpoint reply packet:
QUERY_RESULT_REPLY = '\x21'  # happens to be same as waveport RES_SEND_FRAME

VERSION_NUMBER = '$LastChangedRevision: 8064 $'[22:-2]

TYPE_OF_GATEWAY = "Digi Gateway"

TIMEOUT_INSTANTANEOUS = 0.1

# Watchdog timeouts
# unit are seconds
MAIN_LOOP_STILL_LOOPING_WATCHOG_DELAY = 60 * 5
MAIN_LOOP_IS_NOT_INSTANTANEOUS_WATCHDOG_DELAY = 60 * 30

# Max delay to wait for an answer from the waveport device driver
TIMEOUT_WAVEPORT_DEVICE_DRIVER_RESPONSE = 20.0

TIMEOUT_LOCAL_HOST_ADAPTER_REQUEST = 5.0

BLINK_TIME_BASE_SLEEP = 0.5

MSG_TUPLE_COMMAND = 0
MSG_TUPLE_LENGTH = 1
MSG_TUPLE_MESSAGE = 2
# exception classes

# interface functions

# classes

class Orbcomm(PresentationBase, threading.Thread):
    """The Orbcomm Presentation Driver class
    """
    def __init__(self, name, core_services):
        """Performs startup initializations.  It verifies and loads the settings list."""
        
        self.logger = init_module_logger(name)
               
        self.__name = name
        self.__core = core_services        
        
        self.destinations = []
        self.request_channel_to_wp0_dd = None

        self.server_conn_handle = None
        self.keep_alive_timer = 0
        self.waiting_for_reply = False
        self.gateway_v1_backward_compatibility = False
        self.msg_size_on_7_bits = True
        self.radio_responses = Queue.Queue(8)
        
        # watchdogs
        self.mainloop_made_a_pause = None
        self.mainloop_made_one_loop = None
        
 
        #initialisation of the modem handler
        self.m10_handler = m10_sc_api.m10_sc_api(self.logger)
        
        settings_list = [
            Setting(
                name='destinations', type=list, required=False, default_value=[{'value':0, 'device_driver_name':'waveport'}]),
            Setting(
                name='gateway_v1_backward_compatibility', type=bool, required=False, default_value=True),
            Setting(
                name='msg_size_on_7_bits', type=bool, required=False, default_value=True),
            Setting(
                name='do_waveport_initialization', type=bool, required=False, default_value=False),
            Setting(
                name='port_num', type=int, required=True),
            Setting(
                name='baudrate', type=int, required=False, default_value=4800,
                    verify_function=lambda x: x > 0),
            Setting(
                name='log_level', type=str, required=False, default_value='DEBUG',
                 verify_function=check_debug_level_setting),
                         
            Setting(
                name='desired_gateway', type=str, required=False, default_value='GATEWAY_EUROPE',
                 verify_function=lambda key: verify_if_configuration_command_value_is_valid(m10_sc_api.DESIRED_GATEWAY_VALUES, key)),
            Setting(
                name='def_polled', type=str, required=False, default_value='SC_POLL_MODE_IMMEDIATE',
                 verify_function=lambda key: verify_if_configuration_command_value_is_valid(m10_sc_api.SC_POLL_MODE_VALUES, key)),
            Setting(
                name='def_ack_level', type=str, required=False, default_value='ACK_LEVEL_DELIVERY_ORBCOMM',
                 verify_function=lambda key: verify_if_configuration_command_value_is_valid(m10_sc_api.ACK_LEVEL_VALUES, key)),
                         
            Setting(
                name='def_rep_or_ind', type=str, required=False, default_value=m10_sc_api.DEFAULT_OR_IND_REPORTS),
            Setting(
                name='def_msg_or_ind', type=str, required=False, default_value=m10_sc_api.DEFAULT_OR_IND_MES),
                         
            Setting(
                name='def_priority', type=str, required=False, default_value='PRIORITY_LVL_NORMAL',
                 verify_function=lambda key: verify_if_configuration_command_value_is_valid(m10_sc_api.PRIORITY_LVL, key)),
            Setting(
                name='def_msg_body_type', type=str, required=False, default_value='MSG_BODY_TYPE_ASCII',
                 verify_function=lambda key: verify_if_configuration_command_value_is_valid(m10_sc_api.MSG_BODY_TYPE_VALUES, key)),
            Setting(
                name='def_serv_type', type=str, required=False, default_value='REPORTS_SERVICE_TYPE_NORMAL_PRIORITY_DELIVERY_ORBCOMM',
                 verify_function=lambda key: verify_if_configuration_command_value_is_valid(m10_sc_api.REPORTS_SERVICE_TYPE_VALUES, key)),
            Setting(
                name='gwy_search_mode', type=str, required=False, default_value='GWY_SEARCH_MODE_0',
                 verify_function=lambda key: verify_if_configuration_command_value_is_valid(m10_sc_api.GWY_SEARCH_MODE_VALUES, key))       
        ]

        ## Initialize settings:
        PresentationBase.__init__(self, name=name,
                                    settings_list=settings_list)
        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    def apply_settings(self):
        """If settings are changed this is the final step before the settings are available to use"""
        self.logger.info("apply_settings")
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        
        if len(rejected) or len(not_found):
            self.logger.error ("Settings rejected/not found: %s %s" % (rejected, not_found))

        SettingsBase.commit_settings(self, accepted)
        
        # other parameter
        self.gateway_v1_backward_compatibility = SettingsBase.get_setting(self, 'gateway_v1_backward_compatibility')
        self.destinations = SettingsBase.get_setting(self, 'destinations')
        self.msg_size_on_7_bits = SettingsBase.get_setting(self, 'msg_size_on_7_bits')
   
        update_logging_level (self.logger, SettingsBase.get_setting(self, 'log_level'))

        #configuration of the modem handler   
        self.m10_handler.SC_Set_Library_Default_Settings(
                                         desired_gateway=m10_sc_api.DESIRED_GATEWAY_VALUES[SettingsBase.get_setting(self, 'desired_gateway')],
                                         def_polled=m10_sc_api.SC_POLL_MODE_VALUES[SettingsBase.get_setting(self, 'def_polled')],
                                         def_ack_level=m10_sc_api.ACK_LEVEL_VALUES[SettingsBase.get_setting(self, 'def_ack_level')],
                                         def_rep_or_ind=transform_in_usable_OR(SettingsBase.get_setting(self, 'def_rep_or_ind')),
                                         def_msg_or_ind=transform_in_usable_OR(SettingsBase.get_setting(self, 'def_msg_or_ind')),
                                         def_priority=m10_sc_api.PRIORITY_LVL[SettingsBase.get_setting(self, 'def_priority')],
                                         def_msg_body_type=m10_sc_api.MSG_BODY_TYPE_VALUES[SettingsBase.get_setting(self, 'def_msg_body_type')],
                                         def_serv_type=m10_sc_api.REPORTS_SERVICE_TYPE_VALUES[SettingsBase.get_setting(self, 'def_serv_type')],
                                         gwy_search_mode=m10_sc_api.GWY_SEARCH_MODE_VALUES[SettingsBase.get_setting(self, 'gwy_search_mode')]
                                         )
        if self.m10_handler.serial_is_open():
            #we send the configuration to the modem
            self.m10_handler.SC_Write_to_modem_Library_Default_Settings()
        return (accepted, rejected, not_found)

    def start(self):
        """Subscribes to the response channels for each device driver listed in the destinations setting."""
        
        self.logger.info("========== Starting up ==========")
             
        #subscribe to the response channels for all destinations, typically just waveport,00
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        
        self.logger.info("Setting up channels")
        for destination in self.destinations:
            channel_name = destination['device_driver_name'] + '.response'
            self.logger.info("Subscribing to channel:%s" % channel_name)
            cp.subscribe(channel_name, self.receive_response_cb)
        threading.Thread.start(self)
        
        return True

    def stop(self):
        """Stop the this presentation driver.  Returns bool."""
        self.__stopevent.set()
        return True

    def run(self):
        """This is the main loop of the thread in this driver.  This function will never exit.""" 
        
        self.logger.info("Run, init")     
        # apply waveport system configuration, if requested
        if (SettingsBase.get_setting(self, 'do_waveport_initialization')):
            self.init_waveport_config()

        # log current waveport system configuration
        self.log_waveport_config()

        # opening the serial connection with the modem 
        self.m10_handler.SC_COM_connect(SettingsBase.get_setting(self, 'port_num'),
                                        SettingsBase.get_setting(self, 'baudrate'))
        # hard reboot of the modem 
        self.m10_handler.SC_Reboot_m10()  
        # we send the configuration to the modem                       
        self.m10_handler.SC_Write_to_modem_Library_Default_Settings()
        # deleting message queues Inbound and Outbound
        self.m10_handler.SC_Clear_Message_Queues()
        
        blink_cnt = 0
        show_mainloop_made_a_pause_in_blink = False
        
        take_a_delay_in_next_loop_iteration = False
        
        while(True):
            
            if (take_a_delay_in_next_loop_iteration):
                # take a rest
                time.sleep(BLINK_TIME_BASE_SLEEP)
                
                # WARNING: infinite active loop risk here
                # To prevent this, we use a watchdog to check that to insure that this code
                # is executed some times
                if (self.mainloop_made_a_pause):
                    self.mainloop_made_a_pause.stroke()
                show_mainloop_made_a_pause_in_blink = True
            
            # Notify the watchdog that we are still looping
            if (self.mainloop_made_one_loop):
                self.mainloop_made_one_loop.stroke()

            blink_cnt += 1
            if (blink_cnt > 30):
                # Every blink we send a Status request to get an idea of
                # the current satellite coverage and messages queues state.
                self.m10_handler.SC_sndSatusRequest()
                self.logger.debug("StatusRequest sent")
                
                blink_cnt = 0
                self.logger.debug('Blink')
                if (show_mainloop_made_a_pause_in_blink):
                    self.logger.debug('mainloop_made_a_pause has been stroken')
                    show_mainloop_made_a_pause_in_blink = False
        
                # WARNING: this may introduce an infinite loop
                # The loop ends only if no more data are available for processing
                #
                # The watchdog is of this loop so that if this loop lasts to much time,
                # the watchdog resets everything
                
            # poll for work 
            data_has_been_processed = self.orbcomm_poll()
            if (data_has_been_processed):
                take_a_delay_in_next_loop_iteration = False
            else:
                take_a_delay_in_next_loop_iteration = True
    #-------------------------------------               
    def receive_response_cb(self, channel):
        """A new sample has arrived on one of the response channels
        we are monitoring, send message to server"""
        sample = channel.get()
        channel_name = channel.name()
        channel = channel_name.split('.')[0]
        value = -1
        for destination in SettingsBase.get_setting(self, 'destinations'):
            if destination['device_driver_name'] == channel:
                value = destination['value']
        if value == -1:
            self.logger.error("Unknown device driver")
            return

        self.logger.debug('Received the following new sample:%s' % ''.join('%02X ' % ord(x) for x in sample.value))

        if (not self.radio_responses.full()):
            self.radio_responses.put(sample.value)
        else:
            self.logger.critical("Response queue full")
#-------------------------------------
    def init_hardware_board_system_config(self):
        """ Change system board configuration that depends on current runtime configuration"""        
        if (on_digi_board()):
            # Arm watchdogs
            self.mainloop_made_one_loop = digiwdog.Watchdog(MAIN_LOOP_STILL_LOOPING_WATCHOG_DELAY, "Orbcomm Presentation main loop no more looping. Force reset")
            self.mainloop_made_a_pause = digiwdog.Watchdog(MAIN_LOOP_IS_NOT_INSTANTANEOUS_WATCHDOG_DELAY, "Orbcomm Presentation main loop no more looping. Force reset")
        else:
            self.logger.error('No board system configuration necessary')
    #-------------------------------------
    def init_waveport_config(self):
        """ Waveport configuration initialization"""
        
        self.logger.info('Initialize waveport')
        
        setting_OK_response = '\x00\x00\x05\x41\x00\x03\x66'
        
        init_command_list = []
        
        init_command_list.append(('AWAKENING_PERIOD', '\x00', '\x0a'))
        init_command_list.append(('WAKEUP_TYPE', '\x01', '\x00'))
        init_command_list.append(('WAVECARD_POLLING_GROUP', '\x03', '\x00'))
        init_command_list.append(('RADIO_ACKNOWLEDGE', '\x04', '\x01'))
        init_command_list.append(('RELAY_ROUTE_STATUS', '\x06', '\x01'))
        init_command_list.append(('RADIO_USER_TIMEOUT', '\x0C', '\x19'))
        init_command_list.append(('EXCHANGE_STATUS', '\x0E', '\x03'))
        init_command_list.append(('SWITCH_MODE_STATUS', '\x10', '\x01'))
        init_command_list.append(('WAVECARD_MULTICAST_GROUP', '\x16', '\xFF'))
        init_command_list.append(('BCST_RECEPTION_TIMEOUT', '\x17', '\x3C'))
        
        TimeoutForConfigurationCommand = 5.0

        for config_param in init_command_list:
            (command_description, command, argument) = config_param
            
            self.logger.info('Waveport init: apply %s with value %s' % (command_description, ''.join('%02X ' % ord(x) for x in argument)))
            frame = '\x00\x00' + REQ_WRITE_RADIO_PARAM + command + argument
            response = self.waveport_driver_request (frame, TimeoutForConfigurationCommand)
            if (response):
          
                self.logger.info('Waveport init: got response: %s' % ''.join('%02X ' % ord(x) for x in response))
                if (response == setting_OK_response):
                    self.logger.info('Waveport init: setting application OK')
                else:
                    self.logger.critical ('Waveport init: ERROR while applying the on waveport initial configuration parameter')
            else:
                self.logger.error('Waveport init: Error while waiting an response to the initialization command.')
                break
    #-------------------------------------
    def log_waveport_config(self):
        """ Logs the waveport current configuration"""
        
        self.logger.info('Waveport log config')
        
        req_read_OK_response_header = '\x00\x00\x0B\x51\x00'
        req_read_OK_response_header_length = len(req_read_OK_response_header)
        
        dump_config_command_list = []
        
        dump_config_command_list.append(('RADIO_ADDRESS', '\x05'))
        
        TimeoutForConfigurationCommand = 5.0

        for dump_param in dump_config_command_list:
            (command_description, command) = dump_param
            
            self.logger.info('Waveport log config: get %s' % command_description)
            frame = '\x00\x00' + REQ_READ_RADIO_PARAM + command
            response = self.waveport_driver_request (frame, TimeoutForConfigurationCommand)
            if (response):
          
                self.logger.info('Waveport log config: got response: %s' % ''.join('%02X ' % ord(x) for x in response))
                if (response[:req_read_OK_response_header_length] != req_read_OK_response_header):
                    self.logger.error ('Waveport log config: ERROR while reading the waveport configuration parameter %s' % command_description)
            else:
                self.logger.error('Waveport log config: Error while waiting an response to the read command.')
                break       
    #-------------------------------------
    def orbcomm_poll(self):
        ''' Poll for data from the server and WP DD to process.
        When no data has been processed, return False
        Return True in any data has been processed
        '''
        
        # Give priority to DD response message.
        # So, before checking for now messages from the m10,
        # check (and process ALL) messages from DD
        
        any_data_has_been_processed = False

        # Check first for unsolicited WP datas to empty response queue
        # handle ALL unsolicited packets from waveport
        unsolicitedWPPacket = self.receive_dd_message(TIMEOUT_INSTANTANEOUS)
        while (unsolicitedWPPacket):
                any_data_has_been_processed = True
                self.process_unsolicited_waveport_packet(unsolicitedWPPacket)
                unsolicitedWPPacket = self.receive_dd_message (TIMEOUT_INSTANTANEOUS)
       
        # Read the serial port and parse the result
        # If there is a result, reaction depends on the packet type
        orbcomm_tuple = self.m10_handler.Rcv_structured_message(TIMEOUT_INSTANTANEOUS)
        if not orbcomm_tuple:
            # there is nothing to read
            return any_data_has_been_processed  
        
        orbcomm_pkt_type = orbcomm_tuple[0]
        orbcomm_message = orbcomm_tuple[1]
        
        if(orbcomm_pkt_type == SC_TERMMSG_PKT_TYPE):
            self.process_orbcomm_received_message(orbcomm_message[0])
            any_data_has_been_processed = True
            
        elif(orbcomm_pkt_type == STATUS_PKT_TYPE):
            for line in orbcomm_message:
                self.logger.debug(line)
            any_data_has_been_processed = True   
                     
        elif(orbcomm_pkt_type == LLA_PKT_TYPE):
            any_data_has_been_processed = True
        
        elif(orbcomm_pkt_type == UNKNOWN_PKT_TYPE):
            any_data_has_been_processed = True
            
        return any_data_has_been_processed
    #-------------------------------------
    def process_orbcomm_received_message(self, msg):
        """ This function is called after the message is received to actually act upon the data.
        It also performs some final verification that message is not corrupt. """
        
        try:
            # following data is in hexstr format, convert to binary.
            # parse the routing byte, this is an index where 0=WP Radio., 1=Local, 2=SMS, etc
            binstr = ao_hexstr_to_bin(msg[:2])
            if (len(binstr) < 1):
                self.logger.critical("Bad hexstr 1")
                return
            pangoo_route = ord(binstr)
    
            self.logger.debug("Pangoo_route:%02X" % pangoo_route)
            # Wavenis WavePort pangoo_route
    
            # we handle one packet type, which is to query a remote radio endpt
            # for a parameter.  It's a complex one where repeater addressing
            # may be needed.
    
            # first the server sends it in a hex ascii format we must
            # translate to a binary string closer to WP packet.
    
            pangoo_bin_pkt = ao_hexstr_to_bin(msg[2:])
            if (len(binstr) < 1):
                self.logger.critical("Bad hexstr 2")
                return
    
            if pangoo_route == PG_ROUTE_WP:
                self.ha_process_radio_pkt(pangoo_bin_pkt)
            else:
                self.generic_radio_pkt(pangoo_bin_pkt, pangoo_route)

        except Exception:
            
            # Some unexpected exception has been raised (it may by a syntax error, a runtime error, ...)
            # catch and log it to prevent a code crash
            
            traceback_string = traceback.format_exc ()
            self.logger.critical ('Caught a critical unexpected exception: %s' % traceback_string)
                    
    #-------------------------------------
    def receive_dd_message(self, timeout):
        """ Wait for a device driver message with timeout.
        Return None if no message is available."""

        try:
            dd_message = self.radio_responses.get (True, timeout)
            return dd_message
        except Queue.Empty:
            # not more messages available in queue
            return None

    #-------------------------------------
    def generic_radio_pkt(self, bin_pkt, route):
        """Put messages in receive channel of any non-waveport interface"""
        # send the message via DIA channel
        cm = self.__core.get_service("channel_manager")
        cd = cm.channel_database_get()
        for destination in self.destinations:
            if destination['value'] == route:
                channel_name = destination['device_driver_name'] + '.request'
                our_channel = cd.channel_get(channel_name)
                self.logger.debug('Req set:%s' % ''.join('%02X ' % ord(x) for x in bin_pkt))
                our_channel.set(Sample(value=bin_pkt))

    #-------------------------------------
    def waveport_driver_request(self, req_pkt, timeout):
        ''' 
        Once a packet is fully unpacked and processed this function will send the data into
        a device drivers request channel.
        Returns the response packet receiver before the timeout occurs
        Retruns None if no answer has been receiver
        '''
    
        if (self.request_channel_to_wp0_dd):
            pass
        else:
            cm = self.__core.get_service("channel_manager")
            cd = cm.channel_database_get()
            for destination in self.destinations:
                if destination['value'] == 0:
                    channel_name = destination['device_driver_name'] + '.request'
                    self.request_channel_to_wp0_dd = cd.channel_get(channel_name)
            

        # send the message via DIA channel
        self.logger.debug('Req set:%s' % ''.join('%02X ' % ord(x) for x in req_pkt))
        self.request_channel_to_wp0_dd.set(Sample(value=req_pkt))
        
        # Wait for an answer, bounded by timeout
        response = self.receive_dd_message(timeout)
        if (response):
            self.logger.debug("Received a response to driver request")
            return (response)
        else:
            self.logger.critical("Timeout waiting for Request reply %f", timeout)
            return (None)
        
    #-------------------------------------
    def update_repeater_table(self, num_repeaters, list_of_repeaters):
        """ Send host adapter a list of repeaters to use """
        WP_REQ_WRITE_RADIO_PARAM = '\x40'
        WP_PARAM_RELAY_ROUTE = '\x07'

        self.logger.debug("Write Rep.Table")
        cmd_data = WP_REQ_WRITE_RADIO_PARAM + WP_PARAM_RELAY_ROUTE + \
                chr(num_repeaters) + list_of_repeaters

        # add waveport driver header
        ch_cmd = "\x00" # normal waveport request
        ch_flags = "\x00" # basic waveport request response handling.

        response = self.waveport_driver_request(ch_cmd + ch_flags + cmd_data, TIMEOUT_LOCAL_HOST_ADAPTER_REQUEST)
        if (not response):
            self.logger.critical ("Timeout on waiting for RES to repeater table update: %f s." % TIMEOUT_WAVEPORT_DEVICE_DRIVER_RESPONSE)
            return False

        pkt = response[2:]
     
        if len(pkt) < 5:
            self.logger.critical("RES for RECEIVED_FRAME too small!")
            return False
        self.logger.debug("OK updating repeater table")
        return True
    
    #-------------------------------------
    def get_request_tag(self, payload):
        '''
        Tries to extract a request ID from the wavenis frame which has been artificially extended by an ID
        '''
        payload_length = len(payload)
            
        self.logger.debug('Get_request_tag. Received the payload of len %d: %s' % (len(payload), ''.join('%02X ' % ord(x) for x in payload)))

        # We got a valid frame size
        wavenis_frame_length = ord(payload[0])
        if (wavenis_frame_length < payload_length):
            # The payload should contain only a full wavenis frame
            # Since the length of the wavenis frame is not equal to the size of the AO payload,
            # it means that a tag is added at the end of the wavenis frame
            real_wavenis_frame = payload[:wavenis_frame_length]
            tag_string = payload[wavenis_frame_length:]
            self.logger.debug('Get_request_tag. Found wavenis frame on length %d with tag %s: %s' % (wavenis_frame_length, ''.join('%02X ' % ord(x) for x in tag_string), ''.join('%02X ' % ord(x) for x in real_wavenis_frame)))
        else:
            # The payload contains a single wavenis frame.
            # No tag is appended to the wavenis frame
            real_wavenis_frame = payload
            tag_string = ""
        return (real_wavenis_frame, tag_string)          
    #-------------------------------------
    def set_reply_tag(self, orbcomm_bin_pkt, tag_string):
        '''
        Rebuilds a pangoo frame having a tag added to the wavenis frame
        '''
        pangoo_frame = orbcomm_bin_pkt + tag_string
        return (pangoo_frame)
    #-------------------------------------
    def ha_process_radio_pkt(self, orbcomm_bin_pkt):
        ''' 
        Given a query MSG packet from server, parse it, send it to the right handler,
        gather response, send it back to server.
        '''
        # try to extract the tag appendend to the orbcomm_bin_pkt
        tag_tuple = self.get_request_tag (orbcomm_bin_pkt)
        # the new wavenis bon pkt without tag is the first element of the tuple 
        orbcomm_bin_pkt = tag_tuple[0]
        # the tag is the second elemen (tag size + tag)
        pangoo_ReqRes_tag_string = tag_tuple[1]
        
        # Process the payload received from orbcomm
         
        # The smallest packet contains at least 3 bytes, in case of gateway commands   
        if (len(orbcomm_bin_pkt) < 3):
            self.logger.critical("packet smaller than 3 bytes")
            return # get out of here
        
        if (orbcomm_bin_pkt[1] == '\xFF'): 
            # It's a command destinated to the gateway 
            self.logger.debug ("Received a GW command request")
            gateway_command = orbcomm_bin_pkt[2:]
            answer_bin_pkt = self.process_gateway_command_pkt(gateway_command)
            
        else:
            # by default, we consider it is a wavenis frame
            answer_bin_pkt = self.process_wavenis_pkt(orbcomm_bin_pkt)
            
        if (not answer_bin_pkt):
            # We found some error and could not build an answer
            self.logger.error('Received no answer from DD to a radio request, while in Req/Res exchange')
            return
 
        # Now, we have an answer to send back to the alwasyOn server
        
        # Add the tag string at the end of the wavenis frame
        # If the request has not been tagged, the tag_string is empty
        
        pangoo_new_frame = self.set_reply_tag(answer_bin_pkt, pangoo_ReqRes_tag_string)
        # convert formed reply to hexstr format
        pangoo_hexstr_payload = ao_bin_to_hexstr(pangoo_new_frame)
        
        # and finally send it to the modem with a SC-O message structure
        self.logger.debug("sending a SC_ORIG_PKT ha_process_radio_pkt: %s" % pangoo_hexstr_payload)
        self.m10_handler.SC_sndMessage(pangoo_hexstr_payload)    

        self.keep_alive_timer = 0 # Reset our keep alive timer
        
    #-------------------------------------
    def process_gateway_command_pkt(self, gw_command):
        
        GET_VERSION_COMMAND = '\x56'
        CLI_COMMAND_PREFIX = '#cli '
        
        response_str = 'INVALID'
        
        if (gw_command == GET_VERSION_COMMAND):
            self.logger.debug ('Received the GET_VERSION gateway command.')
            response_str = GET_VERSION_COMMAND + VERSION_NUMBER
            
        elif (gw_command.startswith(CLI_COMMAND_PREFIX)):
            self.logger.debug ('Received a CLI gateway command: %s' % gw_command)
            if (on_digi_board()):
                cli_command = gw_command.strip(CLI_COMMAND_PREFIX)
                cli_command_ok, cli_command_output = digicli.digicli(cli_command)
                cli_command_output_str = str(cli_command_output)
                if (not cli_command_ok):
                    self.logger.error ("CLI command \"%s\" return and error: %s" % (cli_command, cli_command_output_str))
                response_str = CLI_COMMAND_PREFIX + cli_command_output_str
                
            else:
                response_str = "CLI command not supported on this platform"
            
        else:
            self.logger.error('Invalid gateway command: %s' % ''.join('%02X ' % ord(x) for x in gw_command))
            response_str = 'unimplemented gateway command'
            
        self.logger.debug ('Command answer is: ' + response_str)
        
        command_answer = '\xFF' + response_str
        
        command_answer_max_len = 255
        sz = len(command_answer)
        if (sz >= command_answer_max_len):
            # invalid answer size
            self.logger.critical('Gateway command answer exceeds max len (strip response): %s' % ''.join('%02X ' % ord(x) for x in command_answer))
            command_answer = command_answer[:command_answer_max_len - 1]
            sz = command_answer_max_len - 1
            
        answer_pkt_len = chr (sz + 1)
        answer_pkt = answer_pkt_len + command_answer
        
        return (answer_pkt)
        
    #-------------------------------------
    def process_wavenis_pkt(self, wavenis_bin_pkt):
        ''' 
        Given a wavenis MSG packet from server (wavenis_bin_pkt), parse it, send it off to the
        host adapter, gather response, return the asnwer or None in case of failure.
        '''
        
        sz = len(wavenis_bin_pkt)
        if (sz < 10):
            self.logger.critical("Invalid query endpoint msg len")
            return None # get out of here

        embedded_length = ord(wavenis_bin_pkt[0])
        cmd = wavenis_bin_pkt[1]  # cmd issued to host adapter

        # next byte relay_info,  0=is for no repeaters, !=0 is for repeater.
        relay_info = wavenis_bin_pkt[2]
        id_of_dev = wavenis_bin_pkt[3:9] # 6 byte address of endpoint we query

        # todo: do more validation, error out if no good.
        if (relay_info == '\x00'):
            self.logger.debug("No repeater table update")
            param_req = wavenis_bin_pkt[9:] # simple short form, no repeater table write
            self.logger.debug("QUERY: no repeater form, em_len:%02x cmd:%02x relay_info:%02x" % \
                      (embedded_length, ord(cmd), ord(relay_info))) 

            rep_addr_list = ''
            const_for_rep = ''
        else:
            const_for_rep = ord(wavenis_bin_pkt[9]) # hmmm..., passed back to server for long case

            num_repeaters = ord(wavenis_bin_pkt[10])
            self.logger.debug("""QUERY: repeater form, em_len:%02x cmd:%02x relay_info:%02x const:%02x num_rep:%02x """ % \
                      (embedded_length, ord(cmd), ord(relay_info), const_for_rep, num_repeaters))
            if (sz < 12 + (num_repeaters * 6)) or num_repeaters > 3:
                self.logger.critical("Invalid msg len:%02x or num_rep:%d" % (sz, num_repeaters))
                return None # get out of here

            eol = 11 + (num_repeaters * 6)
            rep_addr_list = wavenis_bin_pkt[11:eol]
            param_req = wavenis_bin_pkt[eol:]

            # first, write the repeater addresses table to the host adapter
            #   a list of 0 to 3 repeater addresses.
          
            if not self.update_repeater_table(num_repeaters, rep_addr_list):
                self.logger.critical("Give up, rep-table err")
                return None

        # now issue the command to the radio host adapter.
        # this is a type that has the endpoint send a message back RECEIVE_FRAME
        # so we set the wp.TRANS_FLAG_REQ_RESP_RECIEVE_PACKET to tell the waveport driver to perform this
        # additional function.

        cmd_data = id_of_dev + param_req

        # add waveport driver header
        ch_cmd = "\x00" # normal waveport request
        ch_flags = "\x01" # wait and return waveport receive pkt after response.

        cmd_plus_data = ch_cmd + ch_flags + cmd + cmd_data
        self.logger.debug('Pkt to WP:%s' % ''.join('%02X ' % ord(x) for x in cmd_plus_data))

        fullpkt = self.waveport_driver_request(cmd_plus_data, TIMEOUT_WAVEPORT_DEVICE_DRIVER_RESPONSE)
        if (not fullpkt):
            self.logger.critical ("Timeout on waiting for RES in process_wavenis_pkt: %f s." % TIMEOUT_WAVEPORT_DEVICE_DRIVER_RESPONSE)
            return None
        
        self.logger.debug('Fullpkt:%s' % ''.join('%02X ' % ord(x) for x in fullpkt))

        pkt = fullpkt[2:]
        if len(pkt) < 5:
            self.logger.critical("RES for RECEIVED_FRAME too small!")
            return None

        hdr = fullpkt[0:2]
        if (ord(hdr[1]) & 0x80):
            # the 80H bit is set for unsolicited alarm packets.
            self.logger.critical("Unexpected alarm packet during req res.")
            # we will send this back to the server even though it may not
            #  be able to diferentiate between this and a request/response.
            self.process_unsolicited_waveport_packet(fullpkt)
            
            # breadk the control flow and don't consider this as a Request/Response transaction
            return None

        cmd = pkt[1]
        sz = len(pkt)
        
        if self.gateway_v1_backward_compatibility:
            sub_frame = self.reformat_wavenis_frame_to_v1(pkt)
        else:
            sub_frame = pkt

        new_frame = chr(len(sub_frame) + 1) + sub_frame
        
        return (new_frame)
    #=============================
    def reformat_wavenis_frame_to_v1 (self, post_v1_wavenis_frame):   
    
            # Currently, Pangoo only knows about older version of Waveport/Wavecard.
            # Since the frame format has chaned between the current Waverport version and older ones, with must
            # transform the frames for backward compatibility
       
            self.logger.debug('Waveport frame:%s' % ''.join('%02X ' % ord(x) for x in post_v1_wavenis_frame))
            
            #
            # Starting from raw frame received from the Waveport, 
            # reformat the frame to make it backward compatible with old version of Wavevard 
            #
   
            # test various cases and rebuild old_pangoo_gateway_payload
            if (post_v1_wavenis_frame[1] == '\x35'):
                self.logger.debug('Coronis backward compatibility \\x35 case -> rebuild frame')
                # remove length byte
                # WITH repeater mode => replace "\x35" by "\x35\x01"
                # remove CRC
                old_pangoo_gateway_payload = "\x35\x01" + post_v1_wavenis_frame[2:-2]
            elif (post_v1_wavenis_frame[1] == '\x30'):
                self.logger.debug('Coronis backward compatibility \\x30 case -> rebuild frame')
                # remove length byte
                # NON repeater mode => replace "\x30" by "\x30\x00"
                # remove CRC
                old_pangoo_gateway_payload = "\x30\x00" + post_v1_wavenis_frame[2:-2]
            else:
                # no change has to be made, remove only length and CRC
                self.logger.debug('Coronis backward compatibility no rebuild necessary')
                old_pangoo_gateway_payload = post_v1_wavenis_frame[1:-2]
                
            self.logger.debug('Coronis backward compatibility - rebuilt frame:%s' % ''.join('%02X ' % ord(x) for x in old_pangoo_gateway_payload))
            return (old_pangoo_gateway_payload)
        
    #=============================
    def process_unsolicited_waveport_packet(self, packet):
        """ Send an unsolicited alarm waveport packet up to Orbcomm """

        self.logger.info("Process unsolicited WP Packet")
        
        try:
            # start a global exception catcher bloc to catch any exception that can occur in the body
        
            if (not packet):
                self.logger.critical ("Called process_unsolicited_waveport_packet with an empty packet")
                return
    
            header = packet[0:2]
    
            if (ord(header[1]) != 0x80):
                # This is not an unsolicited packet but it is treated by process_unsolicited_waveport_packet
                # => desynchronization
                self.logger.info ('Function process_unsolicited_waveport_packet is treating a non unsolicited packet => possible desynchonization')
                self.logger.info ('Return packet as an unsolicited one')
    
            waveport_frame = packet[2:]
    
            if self.gateway_v1_backward_compatibility:
                payload_to_send = self.reformat_wavenis_frame_to_v1(waveport_frame)
            else:
                payload_to_send = waveport_frame
            
            payload_to_send = chr(len(payload_to_send) + 1) + payload_to_send
            # convert formed reply to hexstr format
            hexstr_payload = ao_bin_to_hexstr(payload_to_send)
            # and send it to the modem with a SC-O message structure
            self.logger.debug("sending a SC_ORIG_PKT process_unsolicited_waveport_packet: %s" % hexstr_payload)
            self.m10_handler.SC_sndMessage(hexstr_payload)
            
        except Exception:
            
            # Some unexpected exception has been raised (it may by a syntax error, a runtime error, ...)
            # catch log it to prevent a code crash
            
            traceback_string = traceback.format_exc ()
            self.logger.critical ('Caught a critical unexpected exception: %s' % traceback_string)

#---------------------
def is_a_well_formed_mail_adress(adress):
    return re.match("[\w\-]+(\.[\w\-]+)*@[\w\-]+(\.[\w\-]+)", adress)
#---------------------
def verify_if_configuration_command_value_is_valid (dictionnary, settings_value):
    """"Verifies if the given value is contained in the given dictionnary"""
    if (settings_value in dictionnary):
        return True
    else:
        return False
#---------------------
def transform_in_usable_OR(raw_setting):
    if is_a_well_formed_mail_adress(raw_setting):
        return raw_setting
    else:
        if re.match('[0-9]', raw_setting):
            return chr(int(raw_setting))
    return m10_sc_api.DEFAULT_OR_IND_MES
#---------------------
def main():
    pass
#---------------------
if __name__ == '__main__':
    status = main()
    sys.exit(status)



