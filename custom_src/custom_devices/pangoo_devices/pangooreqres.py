# $Id: pangooreqres.py 8130 2013-01-08 16:37:29Z orba6563 $
"""\
The PangooReqResDevice Device driver.

Waits for Pangoo AlwaysON frames.  When a message is received it will convert it
into a packet for the waveport radio, and then place it in the request channel
for the radio.  It will subscribe to the response channel of the radio and when
the channel is updated it will package the response into the always on protocol
and send it to the server

Settings:

    destinations
        A list of dictionaries.  Each dictionary has two values 'value'
        and 'device_driver_name'.  The 'value' corresponds to the routing value at the
        beginning of each AlwaysOn message.  A 'value' of 0 corresponds to a waveport
        packet.  So the 'device_driver_name' should map to the name of your waveport
        driver instance, normally 'waveport'.
    
    gateway_v1_backward_compatibility
        If true, supports initial wavecard frame format (used in first generation gateways)
    
    log_level
        Defines the log level, with a string value compliant to the std logger package (ie. DEBUG, ERROR, ...)
"""
from custom_lib.runtimeutils import on_digi_board

import sys
import traceback
from Queue import Empty

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
from devices.device_base import DeviceBase
from samples.sample import Sample
from channels.channel_source_device_property import *

# TODO: http://s-polarion-pangoov4/polarion/redirect/project/PangooDiaGW/workitem?id=DiaGW-33
from custom_lib import logutils

# Commons
from custom_lib.commons import PANGOO_STRING_SAMPLE_FOR_DD_ERROR

# constants
# =========

VERSION_NUMBER = '$LastChangedRevision: 8130 $'[22:-2]
TYPE_OF_GATEWAY = "Digi Gateway"

#--- Pangoo common definitions
from custom_lib.commons.pangoolib import * 

#--- channel names
from custom_devices.pangoo_devices.zigbee.xbeerawout import CHANNEL_NAME_INCOMING_FRAMES as CHANNEL_NAME_TO_XBEERAWOUT

#--- As header part of existing Query Endpoint reply packet:
from custom_devices.pangoo_devices.coronis.waveport import REQ_READ_RADIO_PARAM, REQ_WRITE_RADIO_PARAM
QUERY_RESULT_REPLY = '\x21'  # happens to be same as waveport RES_SEND_FRAME

TIMEOUT_INSTANTANEOUS = 0.1

# Watchdog timeouts
# unit are seconds
MAIN_LOOP_STILL_LOOPING_WATCHOG_DELAY = 60 * 5
MAIN_LOOP_IS_NOT_INSTANTANEOUS_WATCHDOG_DELAY = 60 * 30

# Max delay to wait for an answer from the waveport device driver
# When this delay is delay is reached, it means that the Waveport DD is no more answering (no NAK, ...). It may indeed be broken or disconnected.  
TIMEOUT_WAVEPORT_DEVICE_DRIVER_RESPONSE = 60.0

TIMEOUT_SERVER_CONNNECT = 10.0
WAIT_TIME_BETWEEN_SUCCESSIVE_FAILD_SERVER_CONNECT = 30.0
TIMEOUT_ALWAYS_ON_PACKET_BODY = 2.0
TIMEOUT_FOR_WAVEPORT_DD_LOCAL_REQUEST = 10.0

BLINK_TIME_BASE_SLEEP = 0.5

# classes

class PangooReqResDevice(DeviceBase, threading.Thread):
    """The Always On Presentation Driver class
    """
    def __init__(self, name, core_services):
        """Performs startup initializations.  It verifies and loads the settings list."""
        self.__name = name
        self.__core = core_services
        self.destinations = []
        self.request_channel_to_wp0_dd = None
        self.xbeerawout_channel = None
        
        self.waiting_for_reply = False
        self.gateway_v1_backward_compatibility = False
        
        self.radio_responses_queue = Queue.Queue(8)
        self.pangoo_request_queue = Queue.Queue(8)        
        
        self.logger = init_module_logger(name)

        settings_list = [
            Setting(
                name='destinations', type=list, required=False, default_value=[{'value':0,'device_driver_name':'waveport'}]),
            Setting(
                name='xbeerawout_interface', type=list, required=False, default_value=[{'device_driver_name':'rawxbeeout'}]),
           Setting(
                name='gateway_v1_backward_compatibility', type=bool, required=False, default_value=False),
            Setting(
                name='log_level', type=str, required=False, default_value='DEBUG', verify_function=check_debug_level_setting),                  
        ]
        
        ## Channel Properties Definition:
        property_list = [
            #  properties
            ChannelSourceDeviceProperty(name="pangoo_ascii_request", type=str,
                initial=Sample(timestamp=0, value=""),
                perms_mask=DPROP_PERM_SET, 
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb = self.pangoo_ascii_request_cb),

            ChannelSourceDeviceProperty(name="pangoo_bin_request", type=str,
                initial=Sample(timestamp=0, value=""),
                perms_mask=DPROP_PERM_SET, 
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb = self.pangoo_bin_request_cb),
                         
             ChannelSourceDeviceProperty(name="pangoo_response", type=str,
                initial=Sample(timestamp=0, value=""),
                perms_mask=DPROP_PERM_GET, 
                options=DPROP_OPT_AUTOTIMESTAMP),
                         
            ChannelSourceDeviceProperty(name='software_version', type=str,
                initial=Sample(timestamp=digitime.time(), value=VERSION_NUMBER),
                perms_mask= DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),                         

        ]        
        
        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                        settings_list, property_list)
        
        # Arm watchdogs
        if (on_digi_board()):
            self.mainloop_made_one_loop = digiwdog.Watchdog(MAIN_LOOP_STILL_LOOPING_WATCHOG_DELAY, self.get_name() + " main loop no more looping. Force reset")
            self.mainloop_made_a_pause = digiwdog.Watchdog(MAIN_LOOP_IS_NOT_INSTANTANEOUS_WATCHDOG_DELAY, self.get_name() + " main is looping instantaneously. Force reset")
        else:
            self.mainloop_made_one_loop = None
            self.mainloop_made_a_pause = None

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    #-------------------------------------
    def apply_settings(self):
        """If settings are changed this is the final step before the settings are available to use"""
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        
        if len(rejected) or len(not_found):
            self.logger.error ("Settings rejected/not found: %s %s" % (rejected, not_found))

        SettingsBase.commit_settings(self, accepted)
      
        # other parameter
        self.gateway_v1_backward_compatibility = SettingsBase.get_setting(self, 'gateway_v1_backward_compatibility')
        self.destinations = SettingsBase.get_setting(self, 'destinations')
        
        update_logging_level (self.logger, SettingsBase.get_setting(self, 'log_level'))
            
        # check if xbeerawout_channel must be changed
        if 'xbeerawout_interface' in accepted:
            # reinitialization will be done at first message send
            self.xbeerawout_channel = None
        
        return (accepted, rejected, not_found)

    #-------------------------------------
    def start(self):
        """Subscribes to the response channels for each device driver listed in the destinations setting.
        Also kicks off the main thread that maintains a TCP connection with the server."""
        
        #open our server connection
        self.logger.info("========== Starting up ==========")
             
        #subscribe to the response channels for all destinations, typically just waveport,00
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()

        self.logger.info("Setting up channels")
        for destination in self.destinations:
            channel_name = destination['device_driver_name']+'.received'
            self.logger.info("Subscribing to channel:%s"%channel_name)
            cp.subscribe(channel_name, self.receive_response_cb)
                    
        threading.Thread.start(self)
        
        return True

    #-------------------------------------
    def stop(self):
        """Stop the this presentation driver.  Returns bool."""
        self.__stopevent.set()
        return True

    #-------------------------------------
    def run(self):
        """This is the main loop of the thread in this driver.  This function will never exit. It manages the
        sending of keep alive packets and will occasionally check for data coming from the server.
        """ 
        
        self.logger.info("Run, init")
        
        
        # Get settings to initialize local class variables
        
        blink_cnt = 0
        mainloop_made_a_pause_strike_cnt = 0
        
        take_a_delay_in_next_loop_iteration = False
        
        while(True):
            
            if (take_a_delay_in_next_loop_iteration):
                # take a rest
                time.sleep(BLINK_TIME_BASE_SLEEP)
                mainloop_made_a_pause_strike_cnt += 1
                                
                # WARNING: infinite active loop risk here
                # To prevent this, we use a watchdog to check that to insure that this code
                # is executed some times
                if (self.mainloop_made_a_pause):
                    self.mainloop_made_a_pause.stroke()
            
            # Notify the watchdog that we are still looping
            if (self.mainloop_made_one_loop):
                self.mainloop_made_one_loop.stroke()

            blink_cnt += 1
            if (blink_cnt > 50):
                self.logger.debug('Blink (Nb pauses: %d)' % mainloop_made_a_pause_strike_cnt)
                mainloop_made_a_pause_strike_cnt = 0
                blink_cnt = 0
        

            # WARNING: this may introduce an infinite loop
            # The loop ends only if no more data are available for processing
            #
            # The watchdog is of this loop so that if this loop lasts to much time,
            # the watchdog resets everything
            
            # poll for work
            data_has_been_processed = self.aos_poll()
            if (data_has_been_processed):
                # aos_poll does not consume all available data
                # so, loop immediately as long as data are available
                take_a_delay_in_next_loop_iteration = False
            else:
                # aos_poll processed no data, which means that no data is currently available.
                # so, in the next loop iteration, we tell to take a rest
                take_a_delay_in_next_loop_iteration = True
                
    #-------------------------------------
    def _enqueue_ao_incoming_request (self, pangoo_bin_frame):
        

                
        if (self.pangoo_request_queue.full()):
            self.logger.error('Received a new sample while input queue is already full')
        else:
            self.pangoo_request_queue.put(pangoo_bin_frame)
                            
    #-------------------------------------
    def pangoo_bin_request_cb (self, pangoo_bin_sample):
        self.logger.debug('Received the following new bin sample: %s' % ao_bin_to_hexstr(pangoo_bin_sample.value, True))
        self._enqueue_ao_incoming_request (pangoo_bin_sample.value)
            
    #-------------------------------------
    def pangoo_ascii_request_cb (self, pangoo_ascii_sample):
        self.logger.debug('Received the following new human readable bin sample:%s' % pangoo_ascii_sample.value)
        try:
            pangoo_bin_frame = ao_hexstr_to_bin (msg = pangoo_ascii_sample.value, removespaces = True)

        except ValueError, msg:
            self.logger.error("Misformated input hex string: %s" % msg)
            return

        self._enqueue_ao_incoming_request (pangoo_bin_frame)
        
            
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

        self.logger.debug('Received the following new sample:%s'%''.join('%02X '%ord(x) for x in sample.value))

        try:
            self.radio_responses_queue.put(sample.value, False)
        except Exception, msg:
            self.logger.critical("Fatal error while writing new sample to radio_responses queue: %s" % msg)

  
    #-------------------------------------
    def aos_poll(self):
        ''' Poll for data from the server and WP DD to process.
        When no data has been processed, return False
        Return True in any data (from AO server or DD) has been processed
        '''
        
        # Give priority to DD response message.
        # So, before checking for now messages from AO server,
        # check (and process ALL) messages from DD
        
        any_data_has_been_processed = False

        # Check first for unsolicited WP datas to empty response queue
        # handle ALL unsolicited packets from waveport
        unsolicitedWPPacket = self.receive_dd_message(TIMEOUT_INSTANTANEOUS)
        while (unsolicitedWPPacket):
                any_data_has_been_processed = True
                self.process_unsolicited_waveport_packet(unsolicitedWPPacket)
                unsolicitedWPPacket = self.receive_dd_message (TIMEOUT_INSTANTANEOUS)
                
        # Now the DD response message queue is considered empty
            
        # handle socket requests from server
        pangoo_message = self.receive_pangoo_message(TIMEOUT_INSTANTANEOUS)
        if (pangoo_message):
            any_data_has_been_processed = True
            self.process_pangoo_received_message(pangoo_message)
            
        return any_data_has_been_processed

    #-------------------------------------
    def receive_pangoo_message(self, timeout):
        """ Checks if a packet is available in the input queue. This function checks the header of the packet
        and verifies that it is correct."""

        # wait for header: MSG, LEN_MSB, LEN_LSB byte.
        
        try:
            pangoo_message = self.pangoo_request_queue.get(True, timeout)
        except Empty:
            # No waiting message
            return None
        
        # check message integrity
        #
        # No specific action
                
        # We have a validated packet.
        self.logger.debug("Receive new Pangoo message from input channels")
        self.logger.debug("    Payload data: size %d , hex content %s" % (len(pangoo_message), ao_bin_to_hexstr (pangoo_message, True)))        
        return (pangoo_message)
    
    #-------------------------------------
    def reply_pangoo_message(self, pangoo_message):
        self.logger.debug('Reply message to pangoo: %s' % pangoo_message)
        try:
            self.property_set("pangoo_response", Sample (timestamp=0, value=pangoo_message))            
        except Exception, msg:
            self.logger.error('Exception raised during reply sending. Exception was: %s'%(msg))        
      
    #-------------------------------------
    def process_pangoo_received_message(self, pangoo_message):
        """ This function is called after the message is received to actually act upon the data.
        It also performs some final verification that message is not corrupt. """
        
        try:
            # start a global exception catcher bloc to catch any exception that can occur in the body
            

            packet_length = len(pangoo_message)
            self.logger.debug("MSG pkt, pktlen:%02x" % packet_length)
            
            # following data is in hexstr format, convert to binary.
            # parse the routing byte, this is an index where 0=WP Radio., 1=Local, 2=SMS, etc
            binstr = ao_hexstr_to_bin(pangoo_message[:2])
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
    
            pangoo_bin_pkt = ao_hexstr_to_bin(pangoo_message[2:])
            if (len(pangoo_bin_pkt) < 1):
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
            dd_message = self.radio_responses_queue.get (True, timeout)
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
                channel_name = destination['device_driver_name']+'.request'
                our_channel = cd.channel_get(channel_name)
                self.logger.debug('Req set:%s'%''.join('%02X '%ord(x) for x in bin_pkt))
                our_channel.set(Sample(timestamp=0, value=bin_pkt))

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
                    channel_name = destination['device_driver_name']+'.emit'
                    self.request_channel_to_wp0_dd = cd.channel_get(channel_name)
            

        # send the message via DIA channel
        self.logger.debug('Req set:%s'%''.join('%02X '%ord(x) for x in req_pkt))
        self.request_channel_to_wp0_dd.set(Sample(timestamp=0, value=req_pkt))
        
        # Wait for an answer, bounded by timeout
        response = self.receive_dd_message(timeout)
        if (response):
            self.logger.debug("Received a response to driver request")
            if (response == PANGOO_STRING_SAMPLE_FOR_DD_ERROR):
                self.logger.debug ("response to request is an sample signaling an error -> DD error")
                return (None)
            else:
                return (response)
        else:
            self.logger.critical("Timeout waiting for Request reply %f", timeout)
            return (None)

    #-------------------------------------
    def update_repeater_table(self, num_repeaters, list_of_repeaters):
        """ Send host adapter a list of repeaters to use """
        WP_REQ_WRITE_RADIO_PARAM = '\x40'
        WP_PARAM_RELAY_ROUTE        = '\x07'

        self.logger.debug("Write Rep.Table")
        cmd_data = WP_REQ_WRITE_RADIO_PARAM + WP_PARAM_RELAY_ROUTE + \
                chr(num_repeaters) + list_of_repeaters

        # add waveport driver header
        ch_cmd = "\x00" # normal waveport request
        ch_flags = "\x00" # basic waveport request response handling.

        response = self.waveport_driver_request(ch_cmd+ch_flags+cmd_data, TIMEOUT_FOR_WAVEPORT_DD_LOCAL_REQUEST)
        if (not response):
            self.logger.critical ("Timeout or DD error on waiting for RES to repeater table update: %f s." % TIMEOUT_FOR_WAVEPORT_DD_LOCAL_REQUEST)
            return False

        pkt = response[2:]
     
        if len(pkt) < 5:
            self.logger.critical("RES for RECEIVED_FRAME too small!")
            return False
        self.logger.debug("OK updating repeater table")
        return True
    
    #-------------------------------------
    def get_request_tag(self, ao_payload):
        '''
        Tries to extract a request ID from the wavenis frame which has been artificially extended by an ID
        '''
        ao_payload_length = len(ao_payload)
            
        self.logger.debug('Get_request_tag. Received the ao_payload of len %d: %s' % (len(ao_payload), ''.join('%02X ' % ord(x) for x in ao_payload)))

        # We got a valid AlwaysOn frame size
        wavenis_frame_length = ord(ao_payload[0])
        if (wavenis_frame_length < ao_payload_length):
            # The AO payload should contain only a full wavenis frame
            # Since the length of the wavenis frame is not equal to the size of the AO payload,
            # it means that a tag is added at the end of the wavenis frame
           
            real_wavenis_frame = ao_payload[:wavenis_frame_length]
            tag_string = ao_payload[wavenis_frame_length:]
           
            self.logger.debug('Get_request_tag. Found wavenis frame on length %d with tag %s: %s' % (wavenis_frame_length, ''.join('%02X ' % ord(x) for x in tag_string), ''.join('%02X ' % ord(x) for x in real_wavenis_frame)))
        else:
            # The AO payload contains a single wavenis frame.
            # No tag is appended to the wavenis frame

            real_wavenis_frame = ao_payload
            tag_string = ""
           
        return (real_wavenis_frame, tag_string)

            
    #-------------------------------------
    def set_reply_tag(self, pangoo_bin_pkt, tag_string):
        '''
        Rebuilds a pangoo frame having a tag added to the wavenis frame
        '''
        
        pangoo_frame = pangoo_bin_pkt + tag_string
        return (pangoo_frame)


    #-------------------------------------
    def ha_process_radio_pkt(self, pangoo_bin_pkt):
        ''' 
        Given a qeury MSG packet from server, parse it, send it to the right handler,
        gather response, send it back to server.
        '''
        
        # try to extract the tag appendend to the pangoo_bin_pkt
        tag_tuple = self.get_request_tag (pangoo_bin_pkt)
        # the new wavenis bin pkt without tag is the first element of the tuple 
        pangoo_bin_pkt = tag_tuple[0]
        # the tag is the second element (tag size + tag)
        pangoo_ReqRes_tag_string = tag_tuple[1]
        
        # Process the payload received from alwaysON
         
        # The smallest packet contains at least 3 bytes, in case of gateway commands   
        if (len(pangoo_bin_pkt) < 3):
            self.logger.critical("AlwaysON packet smaller than 3 bytes")
            return # get out of here
        
        ao_route_flag = pangoo_bin_pkt[1]
        answer_bin_pkt = None        
        
        if (ao_route_flag == AO_ROUTE_GW_COMMAND): 
            # It's a command destinated to the gateway 
            self.logger.debug ("Received a GW command request")
            gateway_command = pangoo_bin_pkt[2:]
            answer_bin_pkt = self.process_gateway_command_pkt(gateway_command)
        elif (ao_route_flag == AO_ROUTE_XBEERAWOUT_DD):
            # It's a command destinated to xbeerawout DD 
            self.logger.debug ("Received request for channel: %s" % CHANNEL_NAME_TO_XBEERAWOUT)
            dd_message = pangoo_bin_pkt[2:]
            answer_bin_pkt = self.process_xbeerawout_dd_message(dd_message)
                        
        else:
            # by default, we consider it is a wavenis frame
            answer_bin_pkt = self.process_wavenis_pkt(pangoo_bin_pkt)
            
        if (not answer_bin_pkt):
            # We found some error and could not build a valid answer
            # So, we return a generic error expected by Pangoo
            self.logger.error('Received no answer from DD to a radio request, while in Req/Res exchange')
            response_for_ao_bin_pkt = PANGOO_AO_ANSWER_FOR_GENERIC_ERROR
        else:
            response_for_ao_bin_pkt = answer_bin_pkt
 
        # Now, we have an answer to send back to the alwasyOn server
        
        # Add the tag string at the end of the wavenis frame
        # If teh request has not been tagged, the tag_string is empty
        pangoo_new_frame = self.set_reply_tag(response_for_ao_bin_pkt, pangoo_ReqRes_tag_string)

        # convert formed reply to hexstr format
        pangoo_hexstr_payload = ao_bin_to_hexstr(pangoo_new_frame)

        self.reply_pangoo_message(pangoo_hexstr_payload)
        
    #-------------------------------------
    def process_gateway_command_pkt(self, gw_command):
        
        GET_AO_SERVER_IP_ADDRESS = '\x09'
        GET_AO_SERVER_IP_PORT = '\x0A'
        CLI_COMMAND_PREFIX = '#cli '
        ERROR_BYTE_PREFIX = '\x00'
        
        response_str = 'INVALID'
        
        if (gw_command == PG_CMD_GET_VERSION):
            self.logger.debug ('Received the GET_VERSION gateway command.')
            all_dia_module_software_version = self.get_software_versions()
            response_str = PG_CMD_GET_VERSION + all_dia_module_software_version            
            
        elif (gw_command == GET_AO_SERVER_IP_ADDRESS):
            self.logger.error ('Received the AO_SERVER_IP_ADDRESS gateway command.No more implemented.')
            response_str = GET_AO_SERVER_IP_ADDRESS + 'No more implemented: AO server address'
            
        elif (gw_command == GET_AO_SERVER_IP_PORT):
            self.logger.error ('Received the AO_SERVER_IP_PORT gateway command. No more implemented.')
            response_str = GET_AO_SERVER_IP_PORT + 'No more implemented: AO server port'
            
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
                # FIXME: how to return an error in this case.
                response_str = ERROR_BYTE_PREFIX  + "CLI command not supported on this platform"
            
        else:
            self.logger.error('Invalid gateway command: %s'%''.join('%02X '%ord(x) for x in gw_command))
            response_str = ERROR_BYTE_PREFIX + 'unimplemented gateway command'
            
        self.logger.debug ('Command answer is: ' + response_str)
        
        command_answer = '\xFF' + response_str
        
        command_answer_max_len = 255
        sz = len(command_answer)
        if (sz >= command_answer_max_len):
            # invalid answer size
            self.logger.critical('Gateway command answer exceeds max len (strip response): %s'%''.join('%02X '%ord(x) for x in command_answer))
            command_answer = command_answer[:command_answer_max_len-1]
            sz = command_answer_max_len-1
            
        answer_pkt_len = chr (sz + 1)
        answer_pkt = answer_pkt_len + command_answer
        
        return (answer_pkt)
        
    #-------------------------------------
    def process_xbeerawout_dd_message(self, dd_message):
        
        # send the frame directly to the dd
        default_return_value = ''
        
        if (not self.xbeerawout_channel):
            # channel has not yet been retrieved
            cm = self.__core.get_service("channel_manager")
        
            # XBeeRawOut channel
            xbeerawout_destination_description_list = SettingsBase.get_setting(self,'xbeerawout_interface')
            xbeerawout_destination_description = xbeerawout_destination_description_list[0]
            xbeerawout_channel_name = xbeerawout_destination_description['device_driver_name'] + '.' + CHANNEL_NAME_TO_XBEERAWOUT
            cd = cm.channel_database_get()
            if (cd.channel_exists(xbeerawout_channel_name)):
                self.xbeerawout_channel = cd.channel_get(xbeerawout_channel_name)
            else:
                self.logger.error('Could not retreive DIA channel named: %s' % xbeerawout_channel_name)
                return default_return_value

        try:
            self.xbeerawout_channel.set(Sample(timestamp=0, value=dd_message))
        except Exception, msg:
                self.logger.error('Could not send xbeerawout message to channel: %s' % msg)

        # return an empty string to a non None object
        return default_return_value
    
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
                      (embedded_length, ord(cmd), ord(relay_info) ) ) 

            rep_addr_list = ''
            const_for_rep = ''
        else:
            const_for_rep = ord(wavenis_bin_pkt[9]) # hmmm..., passed back to server for long case

            num_repeaters = ord(wavenis_bin_pkt[10])
            self.logger.debug("""QUERY: repeater form, em_len:%02x cmd:%02x relay_info:%02x const:%02x num_rep:%02x """ % \
                      (embedded_length, ord(cmd), ord(relay_info), const_for_rep, num_repeaters) )
            if (sz < 12+(num_repeaters * 6)) or num_repeaters > 3:
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
        self.logger.debug('Pkt to WP:%s'%''.join('%02X '%ord(x) for x in cmd_plus_data))

        fullpkt = self.waveport_driver_request(cmd_plus_data, TIMEOUT_WAVEPORT_DEVICE_DRIVER_RESPONSE)
        if (not fullpkt):
            self.logger.critical ("Timeout or DD error on waiting for RES in process_wavenis_pkt: %f s." % TIMEOUT_WAVEPORT_DEVICE_DRIVER_RESPONSE)
            return None
        
        self.logger.debug('Fullpkt:%s'%''.join('%02X '%ord(x) for x in fullpkt))

        wavenis_frame = fullpkt[2:]
        if len(wavenis_frame) < 5:
            self.logger.critical("RES for RECEIVED_FRAME too small!")
            return None

        hdr = fullpkt[0:2]
        if (ord(hdr[1]) & 0x80):
            # the 80H bit is set for unsolicited alarm packets.
            self.logger.critical("Unexpected alarm packet during req res.")
            # we will send this back to the server even though it may not
            #  be able to diferentiate between this and a request/response.
            self.process_unsolicited_waveport_packet(fullpkt)
            
            # break the control flow and don't consider this as a Request/Response transaction
            return None

        pangoo_wavenis_packet = self.reformat_wavenis_frame_for_pangoo(wavenis_frame)
       
        return (pangoo_wavenis_packet)
    
    #=============================
    def reformat_wavenis_frame_for_pangoo (self, wavenis_frame):   
    
            # Currently, Pangoo only knows about older version of Waveport/Wavecard.
            # Since the frame format has chaned between the current Waverport version and older ones, with must
            # transform the frames for backward compatibility
            #
            # NOTE: In the current PANGOO implementation, CRCs are not returned even if the Wavenis frame is not modified by the "backward compatibility" mode

       
            self.logger.debug('Post v1 waveport frame:%s'%ao_bin_to_hexstr(wavenis_frame, True))
            
            wavenis_payload = wavenis_frame[1:-2]

            if self.gateway_v1_backward_compatibility:            
                #
                # Starting from raw frame received from the Waveport, 
                # reformat the frame to make it backward compatible with old version of Wavevard (& old verison of AlwaysON)
                #
       
                # test various cases and rebuild old_pangoo_gateway_payload
                if (wavenis_payload[0] == '\x35'):
                    self.logger.debug('Coronis backward compatibility \\x35 case -> rebuild frame')
                    # remove length byte
                    # WITH repeater mode => replace "\x35" by "\x35\x01"
                    # remove CRC
                    v1_wavenis_payload = "\x35\x01" + wavenis_payload[1:]
                elif (wavenis_payload[0] == '\x30'):
                    self.logger.debug('Coronis backward compatibility \\x30 case -> rebuild frame')
                    # remove length byte
                    # NON repeater mode => replace "\x30" by "\x30\x00"
                    # remove CRC
                    v1_wavenis_payload = "\x30\x00" + wavenis_payload[1:]
                else:
                    # no change has to be made, remove only length and CRC
                    self.logger.debug('Coronis backward compatibility no rebuild necessary')
                    v1_wavenis_payload = wavenis_payload
                    
                self.logger.debug('Coronis backward compatibility - rebuilt payload:%s' % ao_bin_to_hexstr(v1_wavenis_payload, True))
                pangoo_wavenis_payload = v1_wavenis_payload
                
            else:
                # keep payload as is
                pangoo_wavenis_payload = wavenis_payload
                                    
            # add size byte
            pangoo_wavenis_packet = chr(len(pangoo_wavenis_payload) + 1) + pangoo_wavenis_payload            
                    
            return (pangoo_wavenis_packet)
        
    #=============================       
    def get_software_versions(self):
        """
        Buids a string of all version of the DIA modules having a channel named software_version.
        These channels are expected to contain the software version of the related DIA module.
         """
        
        all_software_version_dict = {}

        cm = self.__core.get_service("channel_manager")
        cdb = cm.channel_database_get()
        channel_list = cdb.channel_list()
        for channel_name in channel_list:
            splitted_channel_name = channel_name.split (".")
            if (len (splitted_channel_name) != 2):
                # the channel name seems to be incorrect
                continue

            module_name =   splitted_channel_name[0]          
            channel_name_in_module = splitted_channel_name[1]
            
            if (channel_name_in_module == 'software_version'):
                channel = cdb.channel_get(channel_name)
                sample_val = channel.get()
                
                module_version = sample_val.value
                
                all_software_version_dict.update ({module_name: module_version})
                
        all_software_version_string = str(all_software_version_dict)
        self.logger.debug ('Got software version for all DIA modules: %s' % all_software_version_string)
        
        return all_software_version_string
         
    #=============================
    def process_unsolicited_waveport_packet(self, packet):
        """ Send an unsolicited alarm waveport packet up to AO Server """

        self.logger.info("Process unsolicited WP Packet")
        
        try:
            # start a global exception catcher bloc to catch any exception that can occur in the body
        
            if (not packet):
                self.logger.critical ("Called process_unsolicited_waveport_packet with an empty packet")
                return
            
            if (packet == PANGOO_STRING_SAMPLE_FOR_DD_ERROR):
                # the unsolicited packet is an error signaled by the DD. We ignore it
                self.logger.error ('Receiver an unsolicited message from the DD which is an error signal. Ignore it.')
                return
    
            header = packet[0:2]
    
            if (ord(header[1]) != 0x80):
                # Thhis is not an aunsolicited packet but is treated by process_unsolicited_waveport_packet
                # => desynchronization
                self.logger.error ('Function process_unsolicited_waveport_packet is treating a non unsolicited packet => possible desynchonization')
                self.logger.info ('Return packet as an unsolicited one')
    
            waveport_frame = packet[2:]
    
            pangoo_wavenis_packet = self.reformat_wavenis_frame_for_pangoo(waveport_frame)
         
            # convert formed reply to hexstr format
            hexstr_payload = ao_bin_to_hexstr(pangoo_wavenis_packet)
    
            self.reply_pangoo_message(hexstr_payload)

        except Exception:
            
            # Some unexpected exception has been raised (it may by a syntax error, a runtime error, ...)
            # catch log it to prevent a code crash
            
            traceback_string = traceback.format_exc ()
            self.logger.critical ('Caught a critical unexpected exception: %s' % traceback_string)

   
def main():
    pass

if __name__ == '__main__':
    status = main()
    sys.exit(status)



