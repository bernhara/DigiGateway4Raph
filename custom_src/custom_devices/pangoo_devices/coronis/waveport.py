#!/usr/bin/python
# waveport.py - Wave Port Driver, Host Adapter interface.
# $Id: waveport.py 8130 2013-01-08 16:37:29Z orba6563 $
"""\
Waveport radio - Dia Driver

This device driver will interface a waveport radio into the Dia.  It connects
to the radio using the serial port of a Digi Gateway.  The driver has two
channels.  When you set the "request" channel the packet will be sent out
over the waveport radio.  Any message placed in the request channel must be a
fully qualified waveport packet.  If a response is received it will show up in
the "response" channel.  The response channel is also populated when an
unsolicited message is received.

Commonly this driver is used in conjunction with a presentation.  In that
case you will want to subscribe to the response channel, so you are notified
every time a packet comes in.

Settings:

* **baudrate:** The baudrate for the serial port.  Normally 9600.
    (default value: 9600)
* **port:** The enumeration of the serial port.  Port 0 is the real
    serial port on an X4.  Port 11 is the USB interface on an X4.
    (default value: 0)
    
* **log_level:** Defines the log level, with a string value compliant
    to the std logger package (ie. DEBUG, ERROR, ...)
    (default value: DEBUG)

    do_waveport_initialization
        If true, send a sequence of initialization strings to the waveport at startup

"""

from custom_lib.runtimeutils import on_digi_board, \
    get_time_seconds_since_epoch

from serial import serialutil
import serial

import time
import threading
import Queue
import struct
import logging

import sys
import traceback

if on_digi_board():
    # import Digi board specific libraries
    import digiwdog #@UnresolvedImport
    
from custom_lib import logutils

#--- Pangoo common definitions
from custom_lib.commons.pangoolib import * 



from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

from custom_lib.commons import PANGOO_STRING_SAMPLE_FOR_DD_ERROR

# constants
# =========

VERSION_NUMBER = '$LastChangedRevision: 8130 $'[22:-2]

# timeout values in seconds
TIMEOUT_INSTANTANEOUS = 0.1
TIMEOUT_ACK = 1.900

BLINK_TIME_BASE_SLEEP = 0.5

# delay to wait between to successive interaction with the waveport
# ex:
#   - delay between to successive writes
#   - delay between a read end and consecutive write
DEFAULT_MIN_DELAY_BETWEEN_SUCCESSIVE_EXCHANGES_WITH_WAVEPORT = 0.05

# Watchdog timeouts
# unit are seconds
MAIN_LOOP_STILL_LOOPING_WATCHOG_DELAY = 60 * 5
MAIN_LOOP_IS_NOT_INSTANTANEOUS_WATCHDOG_DELAY = 60 * 30

#    Timeout after which we consider that the Wavenis radio network will no more respond
#    this timeout should never happen if Waveport is working normally, because in case of radio errors, the Waveport should return an error
TIMEOUT_WAVENIS_RADIO_RESPONSE = 40.000

TIMEOUT_WAVEPORT_STX_LEN = 0.050
TIMEOUT_WAVEPORT_BODY = 0.200

MAX_ACK_ATTEMPTS = 3

WP_SYNC = '\xff'
WP_STX = '\x02'
WP_ETX = '\x03'

SERIAL_ACK = '\x06'
SERIAL_NAK = '\x15'
SERIAL_ERROR = '\x00'

#---------------------------------
# CMD byte values as 1 character strings(note this list may not be complete):
REQ_SEND_FRAME = '\x20'
RES_SEND_FRAME = '\x21'

REQ_SEND_POLLING = '\x26'

REQ_SEND_BROADCAST = '\x28'
REQ_SEND_BROADCAST_MESSAGE = '\x2a'

RECEIVED_FRAME = '\x30'
RECEPTION_ERROR = '\x31'
RECEIVED_FRAME_POLLING = '\x32'
RECEIVED_FRAME_RELAYED = '\x35'

REQ_WRITE_RADIO_PARAM = '\x40'
RES_WRITE_RADIO_PARAM = '\x41'

REQ_CHANGE_UART_BDRATE = '\x42'
RES_CHANGE_UART_BDRATE = '\x43'

REQ_CHANGE_TX_POWER = '\x44'
RES_CHANGE_TX_POWER = '\x45'

REQ_WRITE_AUTOCORR_STATE = '\x46'
RES_WRITE_AUTOCORR_STATE = '\x47'

REQ_READ_RADIO_PARAM = '\x50'
RES_READ_RADIO_PARAM = '\x51'

REQ_READ_TX_POWER = '\x54'
RES_READ_TX_POWER = '\x55'

REQ_READ_AUTOCORR_STATE = '\x5a'
RES_READ_AUTOCORR_STATE = '\x5b'

REQ_SELECT_CHANNEL = '\x60'
RES_SELECT_CHANNEL = '\x61'

REQ_READ_CHANNEL = '\x62'
RES_READ_CHANNEL = '\x63'

REQ_SELECT_PHYCONFIG = '\x64'
RES_SELECT_PHYCONFIG = '\x65'

REQ_READ_PHYCONFIG = '\x66'
RES_READ_PHYCONFIG = '\x67'

REQ_READ_REMOTE_RSSI = '\x68'
RES_READ_REMOTE_RSSI = '\x69'

REQ_READ_LOCAL_RSSI = '\x6a'
RES_READ_LOCAL_RSSI = '\x6b'

REQ_SELECT_SECOND_AWAKE_PHYCONFIG = '\x6c'

REQ_READ_SECOND_AWAKE_PHYCONFIG = '\x6e'

REQ_SEND_SERVICE = '\x80'
RES_SEND_SERVICE = '\x81'

REQ_FIRMWARE_VERSION = '\xa0'
RES_FIRMWARE_VERSION = '\xa1'

MODE_TEST = '\xb0'

SERIAL_ACK_FRAME = WP_SYNC + WP_STX + '\x04' + SERIAL_ACK + '\x56' + '\x02' + WP_ETX

MSG_TUPLE_COMMAND = 0
MSG_TUPLE_LENGTH = 1
MSG_TUPLE_MESSAGE = 2

# DIA Channels parameters
wavenis_frame_to_emit_channel_name = 'emit'
received_wavenis_frame_channel_name = 'received'

class WaveportDevice(DeviceBase, threading.Thread):
    """The Waveport Device Driver class
    """
    def __init__(self, name, core_services):

        self.logger = init_module_logger(name)
        
    
        # FIXME: remove debug code
        ###### add debug logger to trace strange behaviors
        self.debug_logger = init_module_logger("WP_DEBUG_dd", max_bytes=1024*64, buffer_size=50, flush_level=logging.INFO,  flush_window=5)
        self.debug_logger.setLevel(logging.DEBUG)
        self.debug_logger.info ('INFO ===============================================================================================')
        # FIXME: end
                
        self.__name = name
        self.__core = core_services
        self.radio_requests_from_presentation_queue = Queue.Queue(8)
        
        self._min_delay_between_successive_exchanges_with_waveport = None
        self._time_of_last_exchange_with_waveport = 0
        
        ## Settings Table Definition:
        settings_list = [
            Setting(
                    name='baudrate', type=int, required=False, default_value=9600,
                    verify_function=lambda x: x > 0),
            Setting(
                    name='port', type=int, required=False, default_value=11,
                    verify_function=lambda x: x >= 0),
            Setting(
                name='log_level', type=str, required=False, default_value='DEBUG', verify_function=check_debug_level_setting),
            Setting(
                 name='_min_delay_between_successive_exchanges_with_waveport',
                 type=float,
                 required=False,
                 default_value=DEFAULT_MIN_DELAY_BETWEEN_SUCCESSIVE_EXCHANGES_WITH_WAVEPORT,
                 verify_function=lambda x: x > 0.0),
            Setting(
                name='do_waveport_initialization', type=bool, required=False, default_value=False),
        ]
    
        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name=received_wavenis_frame_channel_name, type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
                         
            ChannelSourceDeviceProperty(name='software_version', type=str,
                initial=Sample(timestamp=digitime.time(), value=VERSION_NUMBER),
                perms_mask= DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),                         
                             
            # settable properties
            ChannelSourceDeviceProperty(name=wavenis_frame_to_emit_channel_name, type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=DPROP_PERM_SET,
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.request_channel_cb),
  
        ]
                                                
        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)
    
        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

        # FIXME: variable not used
        self.aoc_rxbuf = ""  # packet data, bytes

        self.waveport_handle = None
        # FIXME: variable not used
        self.request_pkt = None
        
        # Arm watchdogs
        if (on_digi_board()):
            self.mainloop_made_one_loop = digiwdog.Watchdog(MAIN_LOOP_STILL_LOOPING_WATCHOG_DELAY, self.get_name() + " main loop no more looping. Force reset")
            self.mainloop_made_a_pause = digiwdog.Watchdog(MAIN_LOOP_IS_NOT_INSTANTANEOUS_WATCHDOG_DELAY, self.get_name() + " main is looping instantaneously. Force reset")
        else:
            self.mainloop_made_one_loop = None
            self.mainloop_made_a_pause = None
            
            
    # Callback called when refreshing the version number
    def software_version_channel_refresh_cb (self):
        
        return
        
            


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
        
        update_logging_level (self.logger, SettingsBase.get_setting(self, 'log_level'))
            
        self._min_delay_between_successive_exchanges_with_waveport = SettingsBase.get_setting(self, '_min_delay_between_successive_exchanges_with_waveport')
    
        return (accepted, rejected, not_found)
    
    def start(self):
        """Start the device driver.  Returns bool."""

        self.logger.info("========== Starting up ==========")

        port_num = SettingsBase.get_setting(self, "port")
        baudrate = SettingsBase.get_setting(self, "baudrate")

        self.logger.info("Starting up on port #%s with baudrate %d" % (port_num, baudrate))
        
        try:
            self.waveport_handle = serial.Serial (
                     port=port_num,
                     baudrate=baudrate, #baudrate
                     bytesize=serial.EIGHTBITS, #number of databits
                     parity=serial.PARITY_NONE, #enable parity checking
                     stopbits=serial.STOPBITS_ONE, #number of stopbits
                     writeTimeout=10.0) # force write timeout - should not happen
        except Exception, msg: 
            self.logger.critical('Exception during serial port initialization. Error was: %s' % msg)
            return False

        # apply waveport system configuration, if requested
        if (SettingsBase.get_setting(self, 'do_waveport_initialization')):
            self.init_waveport_config()

        # log current waveport system configuration
        self.log_waveport_config()

        threading.Thread.start(self)
        return True
    
    def stop(self):
        """Stop the device driver.  Returns bool."""
        self.__stopevent.set()
        
        return True
        
    ## Locally defined functions:
    # Property callback functions:
    def request_channel_cb(self, the_sample):
        self.logger.info('Got request:%s' % ''.join('%02X ' % ord(x) for x in the_sample.value))
        
        try:
            self.debug_logger.debug('request_channel_cb. New message. Current queue size: %d' % self.radio_requests_from_presentation_queue.qsize())
            self.radio_requests_from_presentation_queue.put(the_sample.value, False)
            self.debug_logger.debug('request_channel_cb. Message appended to queue. Current queue size: %d' % self.radio_requests_from_presentation_queue.qsize())

        except Exception, msg:
            self.logger.critical('Exception while putting new sample to radio_requests_from_presentation_queue queue: %s' % msg)

    
    # Threading related functions:
    def run(self):
        """ Waveport host adapter main loop """
        
        blink_after_amount_of_loops = 50
        blink_cnt = 0
        mainloop_made_a_pause_strike_cnt = 0
      
        take_a_delay_in_next_loop_iteration = False
        
        while(True):
            
            if (take_a_delay_in_next_loop_iteration):
                # take a rest
                time.sleep(BLINK_TIME_BASE_SLEEP)  # take a rest
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
            if (blink_cnt > blink_after_amount_of_loops):
                self.logger.debug('Blink (Nb pauses: %d)' % mainloop_made_a_pause_strike_cnt)
                mainloop_made_a_pause_strike_cnt = 0
                blink_cnt = 0                
                self.debug_logger.info ('Blink')
                    
            data_has_been_processed = self.waveport_device_driver_poll()  # poll for work
            if (data_has_been_processed):
                # poll does not consume all available data
                # so, loop immediately as long as data are available
                take_a_delay_in_next_loop_iteration = False
            else:
                # poll processed no data, which means that no data is currently available.
                # so, in the next loop iteration, we tell to take a rest
                take_a_delay_in_next_loop_iteration = True


    #=============================
    def waveport_device_driver_poll(self):
        """ Poll for IO to process. """
        
        any_data_has_been_processed = False
    
        # handle any alarm/unsolicited packets from host adapter
        pkt_tuple = self.read_packet_from_waveport(TIMEOUT_INSTANTANEOUS)
        while (pkt_tuple):
            any_data_has_been_processed = True
            unsolicited_message_to_forward = self.process_unsolicited_recv_pkt(pkt_tuple)
            if unsolicited_message_to_forward:
                self.logger.info("Forward UNSOLICITED MESSAGE to response channel")
                self.property_set(received_wavenis_frame_channel_name, Sample(timestamp=0, value=unsolicited_message_to_forward))
            pkt_tuple = self.read_packet_from_waveport(TIMEOUT_INSTANTANEOUS)

        # handle any request response packets
        
        # FIXME: start debug
        debug_qsize = self.radio_requests_from_presentation_queue.qsize()
        if (debug_qsize >= 1):
                self.debug_logger.debug('waveport_device_driver_poll. Poling for incoming messages from presentation. Current queue size: %d' % debug_qsize)
                if (debug_qsize > 1):
                    self.debug_logger.critical('waveport_device_driver_poll. Queue size more than 1.')
        # FIXME: end debug
        
        presentation_message = self.receive_presentation_message(TIMEOUT_INSTANTANEOUS)
        if (presentation_message):
            # FIXME: start debug
            self.debug_logger.debug('waveport_device_driver_poll. Message available. Current queue size after message read: %d' % self.radio_requests_from_presentation_queue.qsize())
            # FIXME: end debug
            
            any_data_has_been_processed = True
            response = self.exchange_waveport_request_response(presentation_message)
            if response:
                self.logger.info("Forward Waveport VALID RESPONSE to response channel")
                self.property_set(received_wavenis_frame_channel_name, Sample(timestamp=0, value=response))
            else:
                self.logger.error("Forward DD Error RESPONSE to response channel")
                self.property_set(received_wavenis_frame_channel_name, Sample(timestamp=0, value=PANGOO_STRING_SAMPLE_FOR_DD_ERROR))
           
        return (any_data_has_been_processed)
            
    #-------------------------------------
    def receive_presentation_message(self, timeout):
        """ Wait for a presentation message with timeout.
        Return None if no message is available."""
        
        try:
            presentation_message = self.radio_requests_from_presentation_queue.get (True, timeout)
            return presentation_message
        except Queue.Empty:
            # no messages available in queue
            return None
        
    #-------------------------------------
    def read_packet_from_waveport(self, timeout):
        """ Wait for a packet in comm rx-data, with timeout """

        # see wp.py::wp_wait_pkt() for previous handler.
        # Example: SERIAL_ACK_FRAME =  SYNC ETX LEN CMD.... CRC1 CRC2 ETX =
        # WP_SYNC + WP_STX + '\x04' + SERIAL_ACK + '\x56' + '\x02' + WP_ETX

        # wait for header: SYNC byte.
        self.waveport_handle.setTimeout(timeout)
        header = self.waveport_handle.read(1)
        if len(header) == 0:
            #nothing to read, so don't complain
            if (timeout != TIMEOUT_INSTANTANEOUS):
                self.logger.critical("No receive data %f timeout" % timeout)
            return None
        if len(header) != 1:
            self.logger.critial("Unexpected Error on SYNC")
            return None

        self.logger.debug(self.ms_tstamp() + "rx SYNC")

        # wait for rest of header: STX, LEN bytes
        self.waveport_handle.setTimeout(TIMEOUT_WAVEPORT_STX_LEN)
        header = self.waveport_handle.read(2)
        if len(header) != 2:
            self.logger.critical("Incomplete Header")
            return None

        if (header[0] != WP_STX):
            self.logger.critical("Expected STX")
            
            # Make following into flush routine
            self.waveport_handle.setTimeout(TIMEOUT_INSTANTANEOUS)
            junk = self.waveport_handle.read(100)
            
            return None

        self.logger.debug(self.ms_tstamp() + "STX,LEN")

        pkt_stx = ord(header[0])
        pkt_length = ord(header[1])

        # wait for rest of packet based on hdr length: CMD,DATA,CRC1,CRC2,ETX
        self.waveport_handle.setTimeout(TIMEOUT_WAVEPORT_BODY)
        payload = self.waveport_handle.read(pkt_length)
        if len(payload) != pkt_length:
            self.logger.critical("Incomplete packet, len:%d wanted:%d" % (len(payload), pkt_length))
            return None

        message = header[1:] + payload # want Len included

        self.logger.debug(self.ms_tstamp() + "RX")

        # now validate the CRC, include LEN, CMD to end of data
        crc_calc = self.wp_crc(message[:pkt_length - 2])

        crc_in_pkt = struct.unpack('<H', message[pkt_length - 2:pkt_length])[0]

        if (crc_calc != crc_in_pkt):
            self.logger.critical("BAD CRC rx-crc:%04x calc:%04x" % (crc_in_pkt, crc_calc))
            # FIXME: should send a NACK
            return None

        if (message[pkt_length] != WP_ETX):
            self.logger.critical("Expected ETX")
            # FIXME: should send a NACK
            return None

        # We have a validated packet.
        self.logger.debug(self.ms_tstamp() + "RX Valid Message:%s" % ''.join('%02X ' % ord(x) for x in message))

        self._time_of_last_exchange_with_waveport = get_time_seconds_since_epoch()

        frame_type = message[1]         
        if (frame_type == SERIAL_ACK or frame_type == SERIAL_NAK or frame_type == SERIAL_ERROR):
            self.logger.debug(self.ms_tstamp() + "ACK, NACK or ERROR reveived. Do not reply with ACK.")
        else:
            self.logger.debug(self.ms_tstamp() + "Packet not an ACK, NACK nore ERROR. Reply with ACK.")
            self.write_coronis_frame_to_waveport_with_delay(SERIAL_ACK_FRAME)
            
        
        command = payload[0]
                           
        return (command, pkt_length, message[:-1]) # take off the ETX

    #-------------------------------------
    def tx_to_host_adapter(self, msg, acked=True):
        """ Transmit packet to host adapter with optional expected ACK.
        Normally a serial ACK packet is returned by the receiver
        to indicate proper reception.  Alternatively an NAK, ERROR
        or no-reply is returned, whereby the command transmit is retried.
        """
        max_attempts = MAX_ACK_ATTEMPTS
        # we use the general waveport(wp) packet making function
        pkt = self.wp_packet(msg)
        
        attempts = 0
        while (attempts < max_attempts):
            self.logger.debug("TX:%s" % ''.join('%02X ' % ord(x) for x in pkt))
            self.write_coronis_frame_to_waveport_with_delay(pkt)
            if acked:
                self.logger.debug("Tx to Host, expect ack")
                reply = self.read_packet_from_waveport(TIMEOUT_ACK)
                if reply:
                    if reply[MSG_TUPLE_COMMAND] == SERIAL_ACK:
                        self.logger.debug("Received Serial Ack")
                        return True
                attempts += 1
            else:
                # No ack expected. State that everything is correct.
                return True

            self.logger.error ("Failed to get ACK from waveport. Retry attempt # %d of %d." % (attempts, max_attempts))
    
        # The function did not exit with correct conditions. Reaching the end means that an error occurred.
        self.logger.critical ("Unable to get an ACK after %d write attempts to waveport for packet %s" % (max_attempts, ''.join('%02X ' % ord(x) for x in pkt)))
        return False

    #-------------------------------------
    def exchange_waveport_request_response(self, cmd_data):
        """ Perform a request response packet exchange with Waveport
        the host adapter.  This is the most common transaction
        where a request(REQ_x) is issued and a response(RES_x) is
        expected back.
        """
        
        try:
            
            if (len(cmd_data) < 3):
                self.logger.critical("Invalid msg size")
                return
    
            ch_command = cmd_data[0]
            ch_flags = ord(cmd_data[1])
            command = cmd_data[2]
        
            self.logger.info("Starting Req/Res to waveport with ch_flags %d: %s" % (ch_flags, wp_cmd_human(command)))
            self.logger.debug(self.msec_str() + "Req/Res started")
        
            # send pkt to host adapter, wait for a serial ack
            if not self.tx_to_host_adapter(cmd_data[2:]):
                self.logger.critical(self.msec_str() + "No ACK sending REQ")
                return
        
            # wait for response
            self.logger.debug (self.msec_str() + "wait for response")
            response_to_Req = self.read_packet_from_waveport(TIMEOUT_WAVENIS_RADIO_RESPONSE)
            if response_to_Req:
                self.logger.debug(self.msec_str() + "Packet returned")
                # the command RES is always REQ+1
                # if expected_cmd removed, make sure to filter out SERIAL ACK,NAK, ERROR
                expected_cmd = chr((ord(command) + 1))
                if (response_to_Req[MSG_TUPLE_COMMAND] == expected_cmd):

                    if (len(response_to_Req[MSG_TUPLE_MESSAGE]) > 1):
                        self.logger.debug(self.ms_tstamp() + "Resp")
    
                    if (ch_flags & 1):
                        # ch_flag == 1 => this is a Req/Res interaction. We have to wait for a radio answer from the Wavenis radio network 
                        response_to_ReqRes = self.read_packet_from_waveport(TIMEOUT_WAVENIS_RADIO_RESPONSE)
                        if response_to_ReqRes:
    
                            if (len(response_to_ReqRes[MSG_TUPLE_MESSAGE]) > 1):
                                self.logger.debug(self.ms_tstamp() + "WPa: RF ")
    
                            self.logger.info("Return RESPONSE to Req/Res")
                            return ch_command + chr(ch_flags) + response_to_ReqRes[MSG_TUPLE_MESSAGE]
                        else:
                            self.logger.critical("Timeout or Error waiting for a radio answer")
                    else:
                        self.logger.info("Return RESPONSE to Req")
                        return ch_command + chr(ch_flags) + response_to_Req[MSG_TUPLE_MESSAGE]

                else:
                    self.logger.critical("Unexpected RES got:%02x wanted:%02x." % (ord(response_to_Req[MSG_TUPLE_COMMAND]), ord(expected_cmd)))

            else:
                self.logger.critical(self.msec_str() + "Timeout or Error waiting for response")
        
            return
        
        except Exception:
            # Some unexpected exception has been raised (it may by a syntax error, a runtime error, ...)
            # catch and log it to prevent a code crash
            
            traceback_string = traceback.format_exc ()
            self.logger.critical ('Caught a critical unexpected exception: %s' % traceback_string)


    #-------------------------------------
    def process_unsolicited_recv_pkt(self, msg_tuple):
        """ Process an unsolicited receive packet from WP host adapter """
        
        try:
            # start a global exception catcher bloc to catch any exception that can occur in the body
    
            packet_length = len(msg_tuple)
            if packet_length < 1:
                self.logger.error("Unsolicited message too short to process")
                return None
            packet_command = msg_tuple[MSG_TUPLE_COMMAND]
        
            self.logger.info("Unsolicited pkt, cmd:%02x" % ord(packet_command))
        
            # send the serial ACK to the WavePort host adapter, but
            #  avoid the error case of acking and ACK or NAK or ERROR.
            #  We should generally not receive one of these.
            if ((packet_command == SERIAL_ACK) or (packet_command == SERIAL_NAK) or (packet_command == SERIAL_ERROR)):
                self.logger.critical("Unsolicited SERIAL ACK,NAK or ERROR, ignore")
                return None
        
            # Pack up unsolicited message from wave port host adapter
            # and send it upstream
        
            # pass it back upstream
            response = msg_tuple[MSG_TUPLE_MESSAGE]
            ch_command = "\x00" # waveport packet
            ch_flags = "\x80" # unsolicited flag
            return ch_command + ch_flags + response

        except Exception:
            # Some unexpected exception has been raised (it may by a syntax error, a runtime error, ...)
            # catch and log it to prevent a code crash
            
            traceback_string = traceback.format_exc ()
            self.logger.critical ('Caught a critical unexpected exception: %s' % traceback_string)
            return None
            
    #-------------------------------------
    def init_waveport_config(self):
        """ Waveport configuration initialization"""
        
        self.logger.info('Initialize waveport')
        
        
        init_command_list = []
        
        # RADIO params
        radio_setting_OK_response = '\x00\x00\x05\x41\x00\x03\x66'
        
        init_command_list.append( ('AWAKENING_PERIOD', REQ_WRITE_RADIO_PARAM + '\x00', '\x0A', radio_setting_OK_response) )
        init_command_list.append( ('WAKEUP_TYPE', REQ_WRITE_RADIO_PARAM + '\x01', '\x00', radio_setting_OK_response) )
        init_command_list.append( ('WAKEUP_LENGTH', REQ_WRITE_RADIO_PARAM + '\x02', '\x4c\x04', radio_setting_OK_response) )
        init_command_list.append( ('WAVECARD_POLLING_GROUP', REQ_WRITE_RADIO_PARAM + '\x03', '\x00', radio_setting_OK_response) )
        init_command_list.append( ('RADIO_ACKNOWLEDGE', REQ_WRITE_RADIO_PARAM + '\x04', '\x01', radio_setting_OK_response) )
        init_command_list.append( ('RELAY_ROUTE_STATUS', REQ_WRITE_RADIO_PARAM + '\x06', '\x01', radio_setting_OK_response) )
        init_command_list.append( ('RADIO_USER_TIMEOUT', REQ_WRITE_RADIO_PARAM + '\x0C', '\x19', radio_setting_OK_response) )
        init_command_list.append( ('EXCHANGE_STATUS', REQ_WRITE_RADIO_PARAM + '\x0e', '\x03', radio_setting_OK_response) )
        init_command_list.append( ('SWITCH_MODE_STATUS', REQ_WRITE_RADIO_PARAM + '\x10', '\x01', radio_setting_OK_response) )
        init_command_list.append( ('WAVECARD_MULTICAST_GROUP', REQ_WRITE_RADIO_PARAM + '\x16', '\xFF', radio_setting_OK_response) )
        init_command_list.append( ('BCST_RECEPTION_TIMEOUT', REQ_WRITE_RADIO_PARAM + '\x17', '\x3c', radio_setting_OK_response) )
        init_command_list.append( ('RECEPTION_STATUS', REQ_WRITE_RADIO_PARAM + '\x15', '\x01', radio_setting_OK_response) )
        
        
        # RF communication mode
        rf_setting_OK_response = '\x00\x00\x05\x65\x00\x50\x22'
        
        init_command_list.append( ('SELECT_PHYCONFIG to 869Mhz 500mW (default factory setting)', REQ_SELECT_PHYCONFIG, '\x00\xB6', rf_setting_OK_response) )
        
        init_command_list.append(('REQ_SELECT_SECOND_AWAKE_PHYCONFIG to 868Mhz freq. hopping 9600 baud', REQ_SELECT_SECOND_AWAKE_PHYCONFIG, '\x00\xA3', '\x00\x00\x05\x6D\x00\x90\xEC'))
        
        
        for config_param in init_command_list:
            (command_description, command, argument, expected_ok_answer) = config_param
            
            self.logger.info('Waveport init: apply %s with value %s' % (command_description, ''.join('%02X '%ord(x) for x in argument)))
            frame = '\x00\x00' + command + argument
            response = self.exchange_waveport_request_response (frame)
            if (response):
          
                self.logger.info('Waveport init: got response: %s' % ''.join('%02X '%ord(x) for x in response))
                if (response == expected_ok_answer):
                    self.logger.info('Waveport init: setting application OK')
                else:
                    self.logger.critical ('Waveport init: ERROR while applying the on waveport initial configuration parameter')
            else:
                self.logger.critical('Waveport init: Error while waiting an response to the initialization command.')

    #-------------------------------------
    def log_waveport_config(self):
        """ Logs the waveport current configuration"""
        
        self.logger.info('Waveport log config')
        
        dump_config_command_list = []
        
        dump_config_command_list.append( ('RADIO_ADDRESS', REQ_READ_RADIO_PARAM + '\x05') )
        dump_config_command_list.append( ('FIRMWARE_VERSION', REQ_FIRMWARE_VERSION) )
      
        for dump_param in dump_config_command_list:
            (command_description, command) = dump_param
            
            self.logger.info('Waveport log config: get %s' % command_description)
            frame = '\x00\x00' + command
            response = self.exchange_waveport_request_response (frame)
            if (response):
                self.logger.info('Waveport log config: got response: %s' % ''.join('%02X '%ord(x) for x in response))
            else:
                self.logger.error('Waveport log config: Error while waiting an response to the read command.')
                                                 
    #---------------------
    def write_coronis_frame_to_waveport_with_delay (self, frame, additional_delay = None):
        """Writes a complete coronis frame to the waveport.
           Since the waveport needs an undocummented deplay between to successive write, we check here
           if successive write are really seperated by at least min_delay_between_successive_writes_to_waveport.
           If additional delay in seconds is specified the delay is expected in addition of the previous delay."""
           
           
        if (frame[0] != WP_STX and frame[-1] != WP_ETX):
            self.logger.error ('Function write_coronis_frame_to_waveport_with_delay should only be called with full wavenis frames')

        current_time_since_epoch = get_time_seconds_since_epoch()
        
        elapsed_time_since_last_write = current_time_since_epoch - self._time_of_last_exchange_with_waveport 
        if (elapsed_time_since_last_write < self._min_delay_between_successive_exchanges_with_waveport):
            sleep_time = self._min_delay_between_successive_exchanges_with_waveport - elapsed_time_since_last_write
            self.logger.debug ('Write frame happens before min dealy of %f s. Elapsed time last write: %f. Waiting %f s.' %
                               (self._min_delay_between_successive_exchanges_with_waveport,
                                elapsed_time_since_last_write,
                                sleep_time))
            time.sleep(sleep_time)
            
        # We expected at least min_delay_between_successive_writes_to_waveport after previous write
        # Wait additional delay if needed
        if (additional_delay):
            self.logger.debug ('Write frame delay with additional delay: %f' % additional_delay)
            time.sleep(additional_delay)
        
        # Now we expected the whole required delays. We can write the frame to the waveport
        try:
            self.waveport_handle.write (frame)
            self.waveport_handle.flush()
        except serialutil.writeTimeoutError:
            # This is the only functionnal exception raised by the write function of serial utils
            self.logger.critical ('Timeout during write to waveport serial interface')
            return
        except Exception ,msg:
            # Unexpected exception
            self.logger.critical ('Unexpected exception during write to waveport serial interface: %s' % msg)
            return
        
        self._time_of_last_exchange_with_waveport = get_time_seconds_since_epoch()
            
    #---------------------
    def wp_packet(self, msg):
        """Make a WavePort Packet from the packet contents provided
           in msg string.  msg starts with CMD byte """
    
        pkt_str = msg
        pkt_len = len(pkt_str) + 3 # for 1byte len, 1byte cmd, 2bytes CRC
    
        crc = self.wp_crc(chr(pkt_len) + pkt_str)
    
        crc_msb = (crc >> 8) & 0xff
        crc_lsb = crc & 0xff
    
        pkt = WP_SYNC + \
              WP_STX + \
              chr(pkt_len) + \
              pkt_str + \
              chr(crc_lsb) + \
              chr(crc_msb) + \
              WP_ETX
        return pkt

    #---------------------
    def wp_crc(self, msg):
        """Compute the cyclic redundancy check, for a given message,
           conform to wawenis protocol """
        poly = 0x8408
        lg = len(msg)
        crc = 0
        for j in range(lg):
            byte = ord(msg[j])
            crc = crc ^ byte
            for i in range(8):
                carry = crc & 1
                crc = crc / 2
                if (carry != 0):
                    crc = crc ^ poly
        crc = crc & 0xffff
        return crc

    #=============================
    def msec_str(self):
        """ return a millisecond time stamp we can use in tracing """
        t = get_time_seconds_since_epoch ()
        ms = (int(t * 1000) % 1000)
        return "%03d: " % ms

    #=============================
    def ms_tstamp(self):
        ''' millisecond timestamp suitable for logging '''

        t = get_time_seconds_since_epoch ()
        ms = (int(t * 1000) % 1000)
        sec = (int(t) % 60)
        min = (int(t / 60.0) % 60)
        return "%02d:%02d:%03d " % (min, sec, ms)


    #=============================
    # Simulation and test functions        

    def simulate_alarm_caronis_frame_receipt_from_waweport (self):
        '''for debugging purpose, simulates the receipt of an alarm, sent by "sensor_source_address" wavenis device'''
  
        sensor_source_address = '\x0B\x22\x09\x30\x01\xF7'

        wawelog_alarm_simulation_frame = '\x17\x30' + sensor_source_address + '\x40\x02\x1A\x0B\x0A\x05\x0B\x17\x01\x00\x01\x06\x52\xB7\x9E'

        ch_command = "\x00" # waveport packet
        ch_flags = "\x80" # unsolicited flag
        self.property_set(received_wavenis_frame_channel_name, Sample(timestamp=0, value=ch_command + ch_flags + wawelog_alarm_simulation_frame))
        
#=============================
#  for making human readable, CHR to NAME

wp_cmds = {}

def add_to_wp_cmds_human_dict (wp_command_name):
    if (globals().has_key(wp_command_name)):
        wp_command_value = globals()[wp_command_name]
        wp_cmds.update ({wp_command_value: "%s-%02x" % (wp_command_name, ord(wp_command_value))})
        
add_to_wp_cmds_human_dict ('SERIAL_ACK')
add_to_wp_cmds_human_dict ('REQ_SEND_FRAME')
add_to_wp_cmds_human_dict ('RECEIVED_FRAME')
add_to_wp_cmds_human_dict ('RECEPTION_ERROR')
add_to_wp_cmds_human_dict ('REQ_WRITE_RADIO_PARAM')
add_to_wp_cmds_human_dict ('REQ_READ_RADIO_PARAM')
add_to_wp_cmds_human_dict ('REQ_SEND_SERVICE')
add_to_wp_cmds_human_dict ('REQ_FIRMWARE_VERSION')
add_to_wp_cmds_human_dict ('RES_SEND_FRAME')
add_to_wp_cmds_human_dict ('RES_WRITE_RADIO_PARAM')
add_to_wp_cmds_human_dict ('RES_READ_RADIO_PARAM')
add_to_wp_cmds_human_dict ('RES_SEND_SERVICE')
add_to_wp_cmds_human_dict ('RES_FIRMWARE_VERSION')

add_to_wp_cmds_human_dict ('REQ_SELECT_CHANNEL')
add_to_wp_cmds_human_dict ('RES_SELECT_CHANNEL')

add_to_wp_cmds_human_dict ('REQ_READ_CHANNEL')
add_to_wp_cmds_human_dict ('RES_READ_CHANNEL')

add_to_wp_cmds_human_dict ('REQ_SELECT_PHYCONFIG')
add_to_wp_cmds_human_dict ('RES_SELECT_PHYCONFIG')

add_to_wp_cmds_human_dict ('REQ_READ_PHYCONFIG')
add_to_wp_cmds_human_dict ('RES_READ_PHYCONFIG')


add_to_wp_cmds_human_dict ('REQ_CHANGE_TX_POWER')
add_to_wp_cmds_human_dict ('RES_CHANGE_TX_POWER')

add_to_wp_cmds_human_dict ('REQ_WRITE_AUTOCORR_STATE')
add_to_wp_cmds_human_dict ('RES_WRITE_AUTOCORR_STATE')

add_to_wp_cmds_human_dict ('REQ_READ_RADIO_PARAM')
add_to_wp_cmds_human_dict ('RES_READ_RADIO_PARAM')

add_to_wp_cmds_human_dict ('REQ_READ_TX_POWER')
add_to_wp_cmds_human_dict ('RES_READ_TX_POWER')

add_to_wp_cmds_human_dict ('REQ_READ_AUTOCORR_STATE')
add_to_wp_cmds_human_dict ('RES_READ_AUTOCORR_STATE')

add_to_wp_cmds_human_dict ('REQ_SELECT_SECOND_AWAKE_PHYCONFIG')

def wp_cmd_human(cmd):
        ''' given a WavePort cmd char, return a human readable string suitable
            for logging '''
        if (wp_cmds.has_key(cmd)):
            return "%s" % wp_cmds[cmd]
        return "cmd?:%02x" % ord(cmd)

#=============================
def main():
    print "test"

#------------------------
if __name__ == '__main__':
    main()


