# $Id: xbee_waveport.py 6741 2011-09-27 11:32:37Z vmpx4526 $

"""
Waveport radio over XBEE RS232 adpater - Dia Driver

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

* for serial line settings, see settings applicable to the XBeeSerial device driver (baudrate, ...)
    
* **log_level:** Defines the log level, with a string value compliant
    to the std logger package (ie. DEBUG, ERROR, ...)
    (default value: DEBUG)
"""

from custom_lib.runtimeutils import on_digi_board, setup_runtime_env
setup_runtime_env ()

import time
import threading
import Queue
import struct
import logging

import sys

if on_digi_board():
    # import Digi board specific libraries
    import digiwdog #@UnresolvedImport

from custom_lib import logutils

from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

from devices.xbee.xbee_devices.xbee_serial import XBeeSerial
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo import XBeeConfigBlockDDO

# timeout values in seconds
TIMEOUT_INSTANTANEOUS = 0.1
TIMEOUT_ACK = 1.900

BLINK_TIME_BASE_SLEEP = 0.5

# Watchdog timeouts
# unit are seconds
MAIN_LOOP_STILL_LOOPING_WATCHOG_DELAY = 60 * 5
MAIN_LOOP_IS_NOT_INSTANTANEOUS_WATCHDOG_DELAY = 60 * 30

#    Timeout after which Waveport is considered not to deliver any response to the current request
#    this timeout should never happen is Waveport is connect and working
TIMEOUT_WAVEPORT_RESPONSE = 20.000

TIMEOUT_ENPT_QUERY = 15.000
TIMEOUT_WAVEPORT_STX_LEN = 0.5
TIMEOUT_WAVEPORT_BODY = 0.500

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

REQ_SEND_SERVICE = '\x80'
RES_SEND_SERVICE = '\x81'

REQ_FIRMWARE_VERSION = '\xa0'
RES_FIRMWARE_VERSION = '\xa1'

MODE_TEST = '\xb0'


# for making human readable, CHR to NAME
wp_cmds = { \
 SERIAL_ACK : "SERIAL_ACK-06", \
 REQ_SEND_FRAME : "REQ_SEND_FRAME-20", \
 RECEIVED_FRAME : "RECEIVED_FRAME-30", \
 RECEPTION_ERROR : "RECEPTION_ERROR-31", \
 REQ_WRITE_RADIO_PARAM : "REQ_WRITE_RADIO_PARAM-40", \
 REQ_READ_RADIO_PARAM : "REQ_READ_RADIO_PARAM-50", \
 REQ_SEND_SERVICE : "REQ_SEND_SERVICE-80", \
 REQ_FIRMWARE_VERSION : "REQ_FIRMWARE_VERSION-A0", \

 RES_SEND_FRAME : "RES_SEND_FRAME-21", \
 RES_WRITE_RADIO_PARAM : "RES_WRITE_RADIO_PARAM-41", \
 RES_READ_RADIO_PARAM : "RES_READ_RADIO_PARAM-51", \
 RES_SEND_SERVICE : "RES_SEND_SERVICE-81", \
 RES_FIRMWARE_VERSION : "RES_FIRMWARE_VERSION-A1", \

 REQ_SELECT_CHANNEL : "REQ_SELECT_CHANNEL-60", \
 RES_SELECT_CHANNEL : "RES_SELECT_CHANNEL-61", \

 REQ_READ_CHANNEL : "REQ_READ_CHANNEL-62", \
 RES_READ_CHANNEL : "RES_READ_CHANNEL-63", \

 REQ_SELECT_PHYCONFIG : "REQ_SELECT_PHYCONFIG-64", \
 RES_SELECT_PHYCONFIG : "RES_SELECT_PHYCONFIG-65", \

 REQ_READ_PHYCONFIG : "REQ_READ_PHYCONFIG-66", \
 RES_READ_PHYCONFIG : "RES_READ_PHYCONFIG-67", \


 REQ_CHANGE_TX_POWER : "REQ_CHANGE_TX_POWER-44", \
 RES_CHANGE_TX_POWER : "RES_CHANGE_TX_POWER-45", \

 REQ_WRITE_AUTOCORR_STATE : "REQ_WRITE_AUTOCORR_STATE-46", \
 RES_WRITE_AUTOCORR_STATE : "RES_WRITE_AUTOCORR_STATE-47", \

 REQ_READ_RADIO_PARAM : "REQ_READ_RADIO_PARAM-50", \
 RES_READ_RADIO_PARAM : "RES_READ_RADIO_PARAM-51", \

 REQ_READ_TX_POWER : "REQ_READ_TX_POWER-54", \
 RES_READ_TX_POWER : "RES_READ_TX_POWER-55", \

 REQ_READ_AUTOCORR_STATE : "REQ_READ_AUTOCORR_STATE-5a", \
 RES_READ_AUTOCORR_STATE : "RES_READ_AUTOCORR_STATE-5b", \

          }

SERIAL_ACK_FRAME = WP_SYNC + WP_STX + '\x04' + SERIAL_ACK + '\x56' + '\x02' + WP_ETX

MSG_TUPLE_COMMAND = 0
MSG_TUPLE_LENGTH = 1
MSG_TUPLE_MESSAGE = 2

class XBeeWaveportDevice(XBeeSerial, threading.Thread):
    """The XBee Waveport Device Driver class
    """
    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        self.radio_requests_from_presentation_queue = Queue.Queue(8)
        self.radio_message_from_waveport_queue = Queue.Queue(1024)
    
        
        self.init_module_logger()
    
        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='log_level', type=str, required=False, default_value='DEBUG', verify_function=self.check_debug_level_setting),
        ]
    
        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="response", type=str,
                initial=Sample(timestamp=0, value="stres"),
                perms_mask=DPROP_PERM_GET | DPROP_PERM_SET,
                options=DPROP_OPT_AUTOTIMESTAMP),
    
            # settable properties
            ChannelSourceDeviceProperty(name="request", type=str,
                initial=Sample(timestamp=0, value="streq"),
                perms_mask=DPROP_PERM_GET | DPROP_PERM_SET,
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.request_channel_cb),
        ]
                                                
        ## Local State Variables:
        self.__xbee_manager = None
        
        ## Initialize the XBeeSerial interface:
        self.logger.debug ("Initialize XBeeSerial")
        XBeeSerial.__init__(self, self.__name, self.__core,
                                settings_list, property_list)
        
        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

        # Arm watchdogs
        if (on_digi_board()):
            self.mainloop_made_one_loop = digiwdog.Watchdog(MAIN_LOOP_STILL_LOOPING_WATCHOG_DELAY, "AO Presentation main loop no more looping. Force reset")
            self.mainloop_made_a_pause = digiwdog.Watchdog(MAIN_LOOP_IS_NOT_INSTANTANEOUS_WATCHDOG_DELAY, "AO Presentation main loop no more looping. Force reset")
        else:
            self.mainloop_made_one_loop = None
            self.mainloop_made_a_pause = None


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
            self.logger.error ('Setting change error for log_level: should be DEBUG, ERROR, ...')        
    
        return (accepted, rejected, not_found)
    
    def start(self):
        """Start the device driver.  Returns bool."""
        
        self.logger.info("========== Starting up ==========")

        self.apply_settings()

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self, "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        # Get the extended address of the device:
        extended_address = SettingsBase.get_setting(self, "extended_address")

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)

        # Call the XBeeSerial function to add the initial set up of our device.
        # This will set up the destination address of the devide, and also set
        # the default baud rate, parity, stop bits and flow control.
        XBeeSerial.initialize_xbee_serial(self, xbee_ddo_cfg)

        # Register this configuration block with the XBee Device Manager:
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        threading.Thread.start(self)
        return True
    
    def stop(self):
        
        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)

        """Stop the device driver.  Returns bool."""
        self.__stopevent.set()
        
        return True
        
    ## Locally defined functions:
    # Property callback functions:
    def request_channel_cb(self, the_sample):
        self.property_set('request', the_sample)
        self.logger.info('Got request:%s' % ''.join('%02X ' % ord(x) for x in the_sample.value))
        
        try:
            self.radio_requests_from_presentation_queue.put(the_sample.value, False)
        except Exception, msg:
            self.logger.critical('Exception while putting new sample to radio_requests_from_presentation_queue queue: %s' % msg)

    
    # Threading related functions:
    def run(self):
        """ Waveport host adapter main loop """

        blink_after_amount_of_loops = 100
        blink_cnt = 0
        show_mainloop_made_a_pause_in_blink = False
       
        take_a_delay_in_next_loop_iteration = False
        
        while(True):
            
            if (take_a_delay_in_next_loop_iteration):
                # take a rest
                time.sleep(BLINK_TIME_BASE_SLEEP)  # take a rest

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
            if (blink_cnt > blink_after_amount_of_loops):
                blink_cnt = 0
                self.logger.debug('Blink')
                if (show_mainloop_made_a_pause_in_blink):
                    self.logger.debug('mainloop_made_a_pause has been stroken')
                    show_mainloop_made_a_pause_in_blink = False
                    
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
            self.process_unsolicited_recv_pkt(pkt_tuple)
            pkt_tuple = self.read_packet_from_waveport(TIMEOUT_INSTANTANEOUS)

        # handle any request response packets
        packet = self.receive_presentation_message(TIMEOUT_INSTANTANEOUS)
        if (packet):
            any_data_has_been_processed = True
            self.exchange_waveport_request_response(packet)
            
        return (any_data_has_been_processed)
            
    #-------------------------------------
    def receive_presentation_message(self, timeout):
        """ Wait for a presentation message with timeout.
        Return None if no message is available."""
        
        try:
            presentation_message = self.radio_requests_from_presentation_queue.get (True, timeout)
            return presentation_message
        except Queue.Empty:
            # not mode messages available in queue
            return None

    #-------------------------------------
    def read_packet_from_waveport(self, timeout):
        """ Wait for a packet in comm rx-data, with timeout """

        # see wp.py::wp_wait_pkt() for previous handler.
        # Example: SERIAL_ACK_FRAME =  SYNC ETX LEN CMD.... CRC1 CRC2 ETX =
        # WP_SYNC + WP_STX + '\x04' + SERIAL_ACK + '\x56' + '\x02' + WP_ETX
        
        try:
            
            # wait for header: SYNC current_byte.
            current_byte = self.radio_message_from_waveport_queue.get(True, timeout)
            
        except Queue.Empty:
            # tried read data, but none are available
            return None

        try:
            self.logger.debug(self.ms_tstamp() + "rx SYNC")
    
            # wait for rest of header: STX, LEN bytes
            current_byte = self.radio_message_from_waveport_queue.get(True, TIMEOUT_WAVEPORT_STX_LEN)
            if (current_byte != WP_STX):
                self.logger.critical("Expected STX")
                
                # Make following into flush routine
                while (not self.radio_message_from_waveport_queue.empty()):
                    self.radio_message_from_waveport_queue.get_nowait()
               
                return None
            self.logger.debug(self.ms_tstamp() + "STX,LEN")
    
            length_byte = self.radio_message_from_waveport_queue.get(True, TIMEOUT_WAVEPORT_STX_LEN)
            pkt_length = ord(length_byte)
            self.logger.debug ('Packet length: %d' % pkt_length)
    
            # wait for rest of packet based on hdr length: CMD,DATA,CRC1,CRC2,ETX
            payload = ''
            read_bytes = 0
            while (read_bytes < pkt_length):
                current_byte = self.radio_message_from_waveport_queue.get(True, TIMEOUT_WAVEPORT_BODY)
                payload += current_byte
                read_bytes += 1

        except Queue.Empty:
            self.logger.critical('Timeout during read of packet from waveport')
            self.logger.debug('read queue size: %d' % self.radio_message_from_waveport_queue.qsize())
            return None
        
        # We got a complete message

        message = length_byte + payload # want Len included

        self.logger.debug(self.ms_tstamp() + "RX")

        # now validate the CRC, include LEN, CMD to end of data
        crc_calc = self.wp_crc(message[:pkt_length - 2])

        crc_in_pkt = struct.unpack('<H', message[pkt_length - 2:pkt_length])[0]

        if (crc_calc != crc_in_pkt):
            self.logger.critical("BAD CRC rx-crc:%04x calc:%04x" % (crc_in_pkt, crc_calc))
            return None

        if (message[pkt_length] != WP_ETX):
            self.logger.critical("Expected ETX")
            return None

        # We have a validated packet.
        self.logger.debug(self.ms_tstamp() + "RX Valid Message:%s" % ''.join('%02X ' % ord(x) for x in message))

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

            ret = self.write_to_xbee_serial(pkt)
            if ret == False:
                self.logger.critical('Failed to write to XBee serial device')
                return False
            
            if acked:
                self.logger.debug("Tx to Host, expect ack")
                reply = self.read_packet_from_waveport(TIMEOUT_ACK)
                if reply:
                    if reply[MSG_TUPLE_COMMAND] == SERIAL_ACK:
                        self.logger.debug("Received Serial Ack")
                        return True
                attempts += 1
    
        return False

    #-------------------------------------
    def exchange_waveport_request_response(self, cmd_data):
        """ Perform a request response packet exchange with Waveport
        the host adapter.  This is the most common transaction
        where a request(REQ_x) is issued and a response(RES_x) is
        expected back.
        """
        if (len(cmd_data) < 3):
            self.logger.critical("Invalid msg size")
            return False

        ch_command = cmd_data[0]
        ch_flags = ord(cmd_data[1])
        command = cmd_data[2]
    
        self.logger.info("Starting Req/Res to waveport: %s" % self.wp_cmd_human(command))
        self.logger.debug(self.msec_str() + "Req/Res started")
    
        # send pkt to host adapter, wait for a serial ack
        if not self.tx_to_host_adapter(cmd_data[2:]):
            self.logger.critical(self.msec_str() + "No ACK sending REQ")
            return False
    
        # wait for response
        self.logger.debug (self.msec_str() + "wait for response")
        response = self.read_packet_from_waveport(TIMEOUT_WAVEPORT_RESPONSE)
        if response:
            self.logger.debug(self.msec_str() + "Packet returned")
            # the command RES is always REQ+1
            # if expected_cmd removed, make sure to filter out SERIAL ACK,NAK, ERROR
            expected_cmd = chr((ord(command) + 1))
            if (response[MSG_TUPLE_COMMAND] == expected_cmd):
                self.logger.debug(self.msec_str() + "RESponse obtained, sending ACK")
                self.logger.debug("TX:%s" % ''.join('%02X ' % ord(x) for x in SERIAL_ACK_FRAME))
                self.logger.debug(self.ms_tstamp() + "TX")
                ret = self.write_to_xbee_serial(SERIAL_ACK_FRAME)
                if ret == False:
                    self.logger.critical('Failed to write to XBee serial device')
                    return False
                if (len(response[MSG_TUPLE_MESSAGE]) > 1):
                    self.logger.debug(self.ms_tstamp() + "Resp")

                if (ch_flags & 1):
                    # do not return response, wait for rlogger.debug(self.ms_tstamp() +                    self.logger_msdebug("WP:Return REC_FRAME")
                    response = self.read_packet_from_waveport(TIMEOUT_ENPT_QUERY)
                    if response:
                        self.logger.debug(self.ms_tstamp() + "rec_frame obtained, sending ACK")
                        ret = self.write_to_xbee_serial(SERIAL_ACK_FRAME)
                        if ret == False:
                            self.logger.critical('Failed to write to XBee serial device')
                            return False

                        if (len(response[MSG_TUPLE_MESSAGE]) > 1):
                            self.logger.debug(self.ms_tstamp() + "WPa: RF ")
                            #logger.debug(self.msec_str() + "WPa: RF DATA:%s"%''.join('%02X '%ord(x) for x in response[MSG_TUPLE_MESSAGE]))

                        self.logger.info("Return RESPONSE to Req/Res")
                        self.property_set('response', Sample(value=ch_command + chr(ch_flags) + response[MSG_TUPLE_MESSAGE]))
                    else:
                        self.logger.critical("Timeout or Error waiting for receive frame")
                else:
                    self.logger.info("Return RESPONSE to Req/Res")
                    self.property_set('response', Sample(value=ch_command + chr(ch_flags) + response[MSG_TUPLE_MESSAGE]))
                    return True
            else:
                self.logger.critical("Unexpected RES got:%02x wanted:%02x" % (ord(response[MSG_TUPLE_COMMAND]), ord(expected_cmd)))
                return False
        else:
            self.logger.critical(self.msec_str() + "Timeout or Error waiting for response")
    
        return False

    #-------------------------------------
    def process_unsolicited_recv_pkt(self, msg):
        """ Process an unsolicited receive packet from WP host adapter """
    
        packet_length = len(msg)
        if packet_length < 1:
            self.logger.error("Unsolicited message too short to process")
            return False
        packet_command = msg[MSG_TUPLE_COMMAND]
    
        self.logger.info("Unsolicited pkt, pktlen:%02x cmd:%02x" % (packet_length, ord(packet_command)))
    
        # send the serial ACK to the WavePort host adapter, but
        #  avoid the error case of acking and ACK or NAK or ERROR.
        #  We should generally not receive one of these.
        if ((packet_command != SERIAL_ACK) and (packet_command != SERIAL_NAK)
                         and (packet_command != SERIAL_ERROR)):
            self.logger.debug(self.ms_tstamp() + "Send ACK")
            ret = self.write_to_xbee_serial(SERIAL_ACK_FRAME)
            if ret == False:
                self.logger.critical('Failed to write to XBee serial device')
                return False
            self.logger.debug("TX:%s" % ''.join('%02X ' % ord(x) for x in SERIAL_ACK_FRAME))
        else:
            self.logger.critical("Unsolicited SERIAL ACK,NAK or ERROR, ignore")
            return False
    
        # Pack up unsolicited message from wave port host adapter
        # and send it upstream
    
        # pass it back upstream
        response = msg[MSG_TUPLE_MESSAGE]
        ch_command = "\x00" # waveport packet
        ch_flags = "\x80" # unsolicited flag
        self.property_set('response', Sample(value=ch_command + ch_flags + response))

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
        if (on_digi_board()):
            t = time.clock()
        else:
            t = time.time()
        ms = (int(t * 1000) % 1000)
        return "%03d: " % ms

    #=============================
    def ms_tstamp(self):
        ''' millisecond timestamp suitable for logging '''

        if (on_digi_board()):
            # digi returns only 1 second granularity on time.time()
            t = time.clock()
        else:
            t = time.time()
        ms = (int(t * 1000) % 1000)
        sec = (int(t) % 60)
        min = (int(t / 60.0) % 60)
        return "%02d:%02d:%03d " % (min, sec, ms)

    #=============================
    def wp_cmd_human(self, cmd):
        ''' given a WavePort cmd char, return a human readable string suitable
            for logging '''
        if (wp_cmds.has_key(cmd)):
            return "%s" % wp_cmds[cmd]
        return "cmd?:%02x" % ord(cmd)
    
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
        if (on_digi_board()):
            logging_file_prefix = 'WEB/python/'
        else:
            logging_file_prefix = ''
        
        self.logger = logging.getLogger("XBWP_dd")
        fmt = logging.Formatter("%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s", "%Y-%m-%d %H:%M:%S")
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)
        
        
        handler = logutils.SmartHandler(filename=logging_file_prefix + 'log_XBWP_dd.txt', buffer_size=50, flush_level=logging.INFO, flush_window=0)
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)

    #=============================
    # Simulation and test functions        

    def simulate_alarm_caronis_frame_receipt_from_waweport (self):
        '''for debugging purpose, simulates the receipt of an alarm, sent by "sensor_source_address" wavenis device'''
  
        sensor_source_address = '\x0B\x22\x09\x30\x01\xF7'

        wawelog_alarm_simulation_frame = '\x17\x30' + sensor_source_address + '\x40\x02\x1A\x0B\x0A\x05\x0B\x17\x01\x00\x01\x06\x52\xB7\x9E'

        ch_command = "\x00" # waveport packet
        ch_flags = "\x80" # unsolicited flag
        self.property_set('response', Sample(value=ch_command + ch_flags + wawelog_alarm_simulation_frame))
        
    #============================
    # XBee adaptation
    
    def read_callback(self, buf):
        ''' callback called by mother class XBeeSerial each time new data are available on serial line '''
        
        # insert each byte into the queue
        for byte in buf:
            
            if (self.radio_message_from_waveport_queue.full()):
                self.logger.critical ("read_callback could not add received bytes to queue because the queue is full")
                return
            
            self.radio_message_from_waveport_queue.put(byte)
            
    def write_to_xbee_serial (self, bytes):
        ''' writes data to the XBee serial adapter by calling the inherited XBeeSerial.write method'''
        
        ret = self.write(bytes)
        if ret == False:
            self.logger.critical('Failed to write to XBee serial device')
            return False
        else:
            return True
   

#=============================
      

# internal functions & classes

def main():
    pass

if __name__ == '__main__':
    import sys
    status = main()
    sys.exit(status)
