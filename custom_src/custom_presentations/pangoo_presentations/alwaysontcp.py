# $Id: alwaysontcp.py 8130 2013-01-08 16:37:29Z orba6563 $
"""\
The AlwaysOn over TCP Presentation.

Maintains a tcp connection with the Always On Server.  This driver will receive
and send packets to the server.  When a message is received it will convert it
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
    
    server_port
        Set to the Always On Server socket port number(default value: 9990).
    
    server_address
        Set to the Always On Server socket IP address(default value: localhost).
        gateway_id
    keep_alive_interval
        Set to the desired AlwaysON Keep Alive interval in minutes(default:10).
        If set to 0 (or negative), the AlwaysON Keep Alive is disabled. 
        
    gateway_id
        Set to the desired Always On gateway ID(default value:+33687531574)
        
    ao_msg_size_on_7_bits
        If true, AlwaysOn sizes (eg. message size) are code on 7 bits bytes
        
    activate_tcp_keepalive
        If true, the TCP_ALIVE flag will be set on the socket to the AlwaysON server
        This may allow faster socket failure detection (see also Digi socket configuration)
        
    log_level
        Defines the log level, with a string value compliant to the std logger package (ie. DEBUG, ERROR, ...)
"""
from custom_lib.runtimeutils import on_digi_board

import sys
import traceback

if on_digi_board():
    # import Digi board specific libraries
    import digicli #@UnresolvedImport
    import digiwdog #@UnresolvedImport
    
# imports
import threading
import logging
import Queue
import socket
import time

from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase
from samples.sample import Sample
from channels.channel_source_device_property import *

from custom_lib import logutils

# constants
# =========

VERSION_NUMBER = '$LastChangedRevision: 8130 $'[22:-2]
TYPE_OF_GATEWAY = "Digi Gateway"

#--- DYNDNS configuration parameters

DYNDNS_USERNAME     = 's-diam-msi-pangoo'
DYNDNS_PASSWORD     = 'pangoo'
DYNDNS_HOSTNAME_PATTERN =   '%s-pangoogw.dyndns.org'

#--- Pangoo AO common definitions
from custom_lib.commons.pangoolib import * 

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



# exception classes

# interface functions

# classes

class AlwaysOnTCP(PresentationBase, threading.Thread):
    """The Always On Presentation Driver class
    """
    def __init__(self, name, core_services):
        """Performs startup initializations.  It verifies and loads the settings list."""
        
        self.logger = init_module_logger(name)
                
        self.__name = name
        self.__core = core_services

        self.gateway_id = None
        self.server_conn_handle = None
        self.keep_alive_timer = 0
        self.waiting_for_reply = False
        self.ao_msg_size_on_7_bits = True
        self.write_channel_name = None
        self.write_channe = None
        self.read_channel_name = None
         
        # watchdogs
        self.mainloop_made_a_pause = None
        self.mainloop_made_one_loop = None
        


        settings_list = [
            Setting(
                name='write_channel', type=str, required=True),
            Setting(
                name='read_channel', type=str, required=True),
           Setting(
                name='server_port', type=int, required=True, default_value=9990),
            Setting(
                name='server_address', type=str, required=True, default_value="localhost"),
            Setting(
                name='keep_alive_interval', type=int, required=False, default_value=10),
            Setting(
                name='gateway_id', type=str, required=True),
            Setting(
                name='ao_msg_size_on_7_bits', type=bool, required=False, default_value=False),
            Setting(
                name='activate_tcp_keepalive', type=bool, required=False, default_value=True),
            Setting(
                name='log_level', type=str, required=False, default_value='DEBUG', verify_function=check_debug_level_setting),                  
        ]
        
        ## Initialize settings:
        PresentationBase.__init__(self,
                                  name=name,
                                  settings_list=settings_list)
        
        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    def apply_settings(self):
        """If settings are changed this is the final step before the settings are available to use"""
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        
        if len(rejected) or len(not_found):
            self.logger.error ("Settings rejected/not found: %s %s" % (rejected, not_found))

        SettingsBase.commit_settings(self, accepted)
        
        # reset class variables according to new values
        need_to_reset_alwayon_connection = False
        
        # get gateway id
        
        previous_gateway_id = self.gateway_id
        
        gateway_id_setting = SettingsBase.get_setting(self,'gateway_id') # gateway_id setting is mandatory, so the get_setting will return a valid string
        if (gateway_id_setting.lower() == '@sim'):
            phone_number = self.retreive_phone_number_from_sim(max_tries = 30, retry_delay = 1)
            if (phone_number):
                self.gateway_id = phone_number
            else:
                self.gateway_id = gateway_id_setting                
        else:
            self.gateway_id = gateway_id_setting
        self.logger.debug ('Got gateway id: %s' % self.gateway_id)
        # need to reset alwayson connection if gateway id was previously defined and changed
        if (previous_gateway_id):
            if (previous_gateway_id != self.gateway_id):
                need_to_reset_alwayon_connection = True

        # other parameter
        self.write_channel_name = SettingsBase.get_setting(self, 'write_channel')
        self.read_channel_name = SettingsBase.get_setting(self, 'read_channel')
        self.ao_msg_size_on_7_bits = SettingsBase.get_setting(self, 'ao_msg_size_on_7_bits')
        self.server_port = SettingsBase.get_setting(self, 'server_port')
        self.server_address = SettingsBase.get_setting(self, 'server_address')
        self.activate_tcp_keepalive = SettingsBase.get_setting(self, 'activate_tcp_keepalive')
        
        update_logging_level (self.logger, SettingsBase.get_setting(self, 'log_level'))
            
        if (need_to_reset_alwayon_connection):
            self.logger.info ('Some parameter change need a AlwaysON connection reset')
            self.close_tcp_connection()
            
        # check if channel must be changed
        if 'write_channel' in accepted:
            # reinitialization will be done at first message send
            self.write_channel = None            
        
        return (accepted, rejected, not_found)

    def start(self):
        """Subscribes to the response channels for each device driver listed in the destinations setting.
        Also kicks off the main thread that maintains a TCP connection with the server."""
        
        self.logger.info("========== Starting up ==========")
         
        threading.Thread.start(self)
        
        return True

    def stop(self):
        """Stop the this presentation driver.  Returns bool."""
        self.__stopevent.set()
        return True

    def run(self):
        """This is the main loop of the thread in this driver.  This function will never exit. It manages the
        sending of keep alive packets and will occasionally check for data coming from the server.
        """ 
        
        self.logger.info("Run, init")
        
        self.init_hardware_board_system_config()
        

        # Get settings to initialize local class variables
        
        keep_alive_interval = SettingsBase.get_setting(self, 'keep_alive_interval')
        keep_alive_interval_timer_total_blinks = keep_alive_interval*60*(1.0/BLINK_TIME_BASE_SLEEP)
        
        ao_server_connexion_timer_total_blinks = WAIT_TIME_BETWEEN_SUCCESSIVE_FAILD_SERVER_CONNECT*(1.0/BLINK_TIME_BASE_SLEEP)

        self.open_tcp_connection()
        
        #subscribe to the response channels
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()

        self.logger.info("Setting up channels")
        self.logger.info("Subscribing to channel: %s"%self.read_channel_name)
        cp.subscribe(self.read_channel_name, self.receive_response_cb)
        
        # Creating the "software_version" channel
        # Since this module is not declared as a "DeviceDriver", it should not have "publication channels"
        # Make a workaround by adding specifically the "software_version" channel (which is commonly done in the "__init__" function

        self.logger.info("Setting up the \"software_version\" channel")        
        channel_db =  cm.channel_database_get()
        channel_name = "%s.%s" % (self.__name, 'software_version')
        prop = ChannelSourceDeviceProperty(name='software_version', type=str, initial=Sample(timestamp=digitime.time(),
                                                                                                                                        value=VERSION_NUMBER),
                                                                                                                                        perms_mask= DPROP_PERM_GET,
                                                                                                                                        options=DPROP_OPT_AUTOTIMESTAMP)
        channel_db.channel_add(channel_name, prop)
        
        #===============================================================
        #
        # Loop body
        #
      
        
        conn_cnt = 0
        
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
                blink_cnt = 0
                self.logger.debug('Blink (Nb pauses: %d)' % mainloop_made_a_pause_strike_cnt)
                mainloop_made_a_pause_strike_cnt = 0
        
            if (self.server_conn_handle):
                
                # Connected to AO server: we can process datas
                

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
                
                if (keep_alive_interval > 0):
                    self.keep_alive_timer += 1
                    if (self.keep_alive_timer >= keep_alive_interval_timer_total_blinks):
                        self.send_keep_alive()

            else:
                
                # Not connected to AO server: try first to connect to it
                
                take_a_delay_in_next_loop_iteration = True
                
                conn_cnt += 1
                if (conn_cnt > ao_server_connexion_timer_total_blinks):
                    
                    self.logger.info('Retry to open TCP connection')
                    
                    conn_cnt = 0
                    #open our server connection
                    self.open_tcp_connection()
            
    def receive_response_cb(self, channel):
        """A new sample has arrived on one of the response channels
        we are monitoring, send message to server"""
        sample = channel.get()
        pangoo_hexstr_payload = sample.value

        self.logger.debug('Received the following new sample from channel %s: %s' % (channel.name(), ao_bin_to_hexstr (pangoo_hexstr_payload, True)))
        
        sz = len(pangoo_hexstr_payload)
        hdr = PG_CMD_MSG +  encode_ao_size (sz, self.ao_msg_size_on_7_bits)

        # and finally send it to the server
        ao_packet = hdr + pangoo_hexstr_payload

        try:
            self.logger.debug("Return answer to AO server")
            self.server_conn_handle.sendall(ao_packet)
        except Exception, msg:
            self.logger.error('Exception raised during send to AO server. Exception was: %s'%(msg))
            self.close_tcp_connection()

        self.keep_alive_timer = 0 # Reset our keep alive timer

    #-------------------------------------
    def init_hardware_board_system_config(self):
        """ Change system board configuration that depends on current runtime configuration
        Form example, borad name depends on SIM card number"""
        
        if (on_digi_board()):
            
            # set DynDNS configuration
            try:
            
                # gateway_id is supposed to be set (mandatory Setting) and should be a phone number "+33..." 
                if (self.gateway_id[0] == '+'):
                    # If the ID starts with '+' as expected, remove the '+' to build the hostname
                    ddhostname=DYNDNS_HOSTNAME_PATTERN%self.gateway_id[1:]
                else:
                    ddhostname=DYNDNS_HOSTNAME_PATTERN%self.gateway_id

                ddns_cli_command_arg='ddsystem=dyndns ' + \
                    'ddusername=%s '%DYNDNS_USERNAME + \
                    'ddpassword=%s '%DYNDNS_PASSWORD + \
                    'ddhostname=%s '%ddhostname + \
                    'service=dyndnsorg'
                    
                cli_command='set ddns ' + ddns_cli_command_arg
                self.logger.debug ('Board system config will execute CLI command: %s'%cli_command)
    
                digicli.digicli(cli_command)
                
                # Arm watchdogs
                self.mainloop_made_one_loop = digiwdog.Watchdog(MAIN_LOOP_STILL_LOOPING_WATCHOG_DELAY, self.get_name() + " main loop no more looping. Force reset")
                self.mainloop_made_a_pause = digiwdog.Watchdog(MAIN_LOOP_IS_NOT_INSTANTANEOUS_WATCHDOG_DELAY, self.get_name() + " main is looping instantaneously. Force reset")
                
            except Exception, msg: 
                self.logger.error('Board system config: Error during DynDNs config setup. Error was: %s'% msg)   
            
        else:
            self.logger.error('No board system configuration necessary')
        
  
            
    def close_tcp_connection(self):
        """Close the tcp connection to the server"""
        if self.server_conn_handle:
            self.server_conn_handle.close()
            self.server_conn_handle = None

    def open_tcp_connection(self):
        """Establish the tcp connection to the server"""
        ip = self.server_address
        port = self.server_port
        self.logger.info("Opening the TCP connection %s:%d"%(ip,port))

        self.server_conn_handle = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.server_conn_handle.settimeout(TIMEOUT_SERVER_CONNNECT)
            
            if (self.activate_tcp_keepalive):
                self.logger.info('IP: activate TCK_KEEP_ALIVE on socket')
                self.server_conn_handle.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            else:
                self.logger.info('IP: disable TCK_KEEP_ALIVE on socket')
                self.server_conn_handle.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 0)
           
            # connect to the server
            self.server_conn_handle.connect((ip, port))
            
            # send AlwaysON id packet
            self.send_id_pkt()
            
            self.logger.info('IP connect successfull to %s:%d'%(ip, port))
        except Exception, msg:
            self.logger.critical('IP connect failed to %s:%d. Error was: %s. Will retry in %d seconds'%(ip, port, msg, WAIT_TIME_BETWEEN_SUCCESSIVE_FAILD_SERVER_CONNECT))
            
            # In some cases for SocketException, the msg is formated as a tuple, so that it contains an error code as first field.
            # We get the first element and compare it to known errors
            error_code = msg[0]
            if (error_code == -6):      
                self.logger.info('    Socket error "-6": this is a transient DNS resolution problem (may be no connection to DNS server?).')
                self.logger.info('    The connection will probably succeed later...')
            self.server_conn_handle.close()
            self.server_conn_handle = None
        
    def send_keep_alive(self):
        """Sends a keep alive message over the TCP connection"""
        self.keep_alive_timer = 0
        try:
            self.logger.info('Sends a keep alive command')
    
            self.server_conn_handle.sendall(PG_CMD_KALIVE)

        except Exception, msg:
            self.logger.error('Send keep alive socket error. Error was: %s'%(msg))
            self.close_tcp_connection()

    def aos_poll(self):
        ''' Poll for data from the server and WP DD to process.
        When no data has been processed, return False
        Return True in any data (from AO server or DD) has been processed
        '''
        
        # Give priority to DD response message.
        # So, before checking for now messages from AO server,
        # check (and process ALL) messages from DD
        
        any_data_has_been_processed = False

       
        # handle socket requests from server
        ao_packet = self.receive_ao_message(TIMEOUT_INSTANTANEOUS)
        if (ao_packet):
            any_data_has_been_processed = True
            self.process_ao_received_message(ao_packet)
            
        return any_data_has_been_processed

    #-------------------------------------
    def receive_ao_message(self, timeout):
        """ Wait for a packet from the server, with timeout.  This function checks the header of the packet
        and verifies that it is correct."""

        # wait for header: MSG, LEN_MSB, LEN_LSB byte.
        
        try:
            self.server_conn_handle.settimeout(timeout)
            header = self.server_conn_handle.recv(3)
        except socket.timeout:
            header = ""
        except Exception, msg:
            self.logger.error('Exception raised during during message reception for server: %s'%(msg))
            self.close_tcp_connection()
            return None
            
        if len(header) == 0:
            #nothing to read, so don't complain
            if (timeout != TIMEOUT_INSTANTANEOUS):
                self.logger.critical("No receive data from AO server, %f timeout", timeout)
            return None
        if len(header) != 3:
            self.logger.critical("Incomplete AO HDR")
            return None

        ao_command = header[0]
        #if command != PG_CMD_MSG:
        if not ao_command in [PG_CMD_MSG, PG_CMD_TRANS]:
            self.logger.critical("Unexpected AO Command")
            return None

        ao_pkt_length = decode_ao_size(header[1], header[2], self.ao_msg_size_on_7_bits)
        self.logger.debug("AO pkt len reveived from server:%02x" % ao_pkt_length)

        # wait for rest of packet based on hdr length
        try:
            self.server_conn_handle.settimeout(TIMEOUT_ALWAYS_ON_PACKET_BODY)
            ao_payload = self.server_conn_handle.recv(ao_pkt_length)
        except socket.timeout:
            ao_payload = ""
        except Exception, msg:
            self.logger.error('Exception raised during during message reception for AO server: %s'% msg)
            self.close_tcp_connection()
            return None

        if len(ao_payload) == 0:
            self.logger.critical("Incomplete AO msg BODY")
            return None

        # We have a validated packet.
        self.logger.debug("Receive new AO message from server over socket")
        self.logger.debug("    Command data hex (byte 0): %02x" % ord(ao_command))        
        self.logger.debug("    Length data hex (byte 1 & 2): %02x %02x = %d int decoded value" % (ord(header[1]), ord(header[2]), ao_pkt_length))        
        self.logger.debug("    Payload data (bytes 3 and after): size %d , hex content %s" % (len(ao_payload), ''.join('%02X '%ord(x) for x in ao_payload)))        
        return (ao_command, ao_payload)


    def process_ao_received_message(self, msg):
        """ This function is called after the message is received to actually act upon the data.
        It also performs some final verification that message is not corrupt. """
        
        ao_command, ao_payload = msg
        
        if (not self.write_channel):
            # channel has not yet been retrieved
            cm = self.__core.get_service("channel_manager")
            cd = cm.channel_database_get()
            
            # test if a channel with that name exists
            if (cd.channel_exists(self.write_channel_name)):
                self.write_channel = cd.channel_get(self.write_channel_name)
            else:
                self.logger.error('Could not retreive DIA channel named: %s' % self.write_channel_name)
                return

        try:
            self.write_channel.set(Sample(timestamp=0, value=ao_payload))
        except Exception, msg:
                self.logger.error('Could not send message to channel: %s' % ao_bin_to_hexstr(msg, True))
       

    #=============================    
    def send_id_pkt(self):
        """ Send a ID Packet up to AO Server """

        try:
            (ip_addr, tcp_port) = self.server_conn_handle.getsockname()
            ip_id_string = ' ('+ip_addr+')'
        except Exception, msg:
            self.logger.error('Could not obtain IP address: %s'%(msg))
            ip_id_string = ''
                         
        version_string = 'V' + VERSION_NUMBER + ip_id_string + ' ' + TYPE_OF_GATEWAY
        
        self.logger.info('Gateway AlwaysON initial connexion. AO Id: "%s" / AO welcome string: "%s"' % (self.gateway_id, version_string))

        sz = len(version_string)
        msg =  ao_bin_to_hexstr(chr(sz + 1) + version_string)

        sz_id  = len(self.gateway_id)
        sz_msg = len(msg)
     
        pkt = PG_CMD_ID  + encode_ao_size(sz_id, self.ao_msg_size_on_7_bits) + self.gateway_id + \
              PG_CMD_MSG + encode_ao_size(sz_msg, self.ao_msg_size_on_7_bits) + msg
              
        self.logger.debug('Initial Id packet:%s'%''.join('%02X '%ord(x) for x in pkt))

        try:
            self.server_conn_handle.sendall(pkt)
        except Exception, msg:
            self.logger.error('Exception raised during send to ID packet. Exception was: %s'%(msg))
            self.close_tcp_connection()
            
        self.kalive_timer = 0 # Reset our keep alive timer
        
    #=============================
    def retreive_phone_number_from_sim (self, max_tries = 1, retry_delay = 2):    
        '''Executed a CLI command to get the phone number the Digi board retrieved from the SIM card
        Return a string containing the phone number if found
        Else return None'''
        
        display_mobile_cli_command = 'display mobile'
        phone_number_line_start_string = 'Phone Number'
        
        if (on_digi_board()):
            
            done_tries = 0
            
            while (done_tries < max_tries):
                self.logger.info ('Executing CLI command: %s'% display_mobile_cli_command)
                cli_command_ok, cli_command_output_list = digicli.digicli(display_mobile_cli_command)
            
                if (not cli_command_ok):
                    self.logger.error ("CLI command and error: %s" % cli_command_output_list)
                    return None
                
                # search for phone number
                for line in cli_command_output_list:
                    self.logger.debug ('Test line for phone number: %s' % line)
                    # remove leading spaces
                    lineStrippedContent = line.lstrip()
                    if (lineStrippedContent.startswith (phone_number_line_start_string)):
                        self.logger.debug ('Found phone number line: %s' % line)
                        # retrieve fields separated by ':'
                        line_fields = lineStrippedContent.split(':')
                        phoneField = line_fields[1]
                        # remove leading a training spaces
                        phone_number = phoneField.strip()
                        
                        if (phone_number != 'N/A'):
                            self.logger.info ('Found mobile phone number: "%s"' % phone_number)
                            return (phone_number)
                        else:
                            self.logger.info ('Mobile phone number not yet available')
                
                # Did not find the phone number
                done_tries += 1
                time.sleep(retry_delay)
                    
            # After all tries, could not retrieve the phone number
            self.logger.error ('Could not get mobile phone number')
            return None
        else:
            self.logger.error('No board system configuration necessary')
            return None

#=============================

def main():
    pass

if __name__ == '__main__':
    status = main()
    sys.exit(status)



