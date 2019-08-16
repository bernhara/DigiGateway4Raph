# $Id: websocketupload.py 1446 2014-12-30 12:30:05Z orba6563 $
"""\
The WebSocket DIA Device driver.

Maintains a Websocket/tcp connection based on the Websocket protocol.  This driver will receive
and send packets to the server.
When a message is received it will by forwarded to the DIA channel named commands.
It will subscribe to the read channel and forward to the WebSorcket server all the sample values
received

Settings:

    server_port
        Set to the WebSocket Server socket port number(default value: 9990).
    
    server_address
        Set to the WebSocket Server socket IP address(default value: localhost).
    
    activate_tcp_keepalive
        If true, the TCP_ALIVE flag will be set on the socket to the Websocket server
        This may allow faster socket failure detection (see also Digi socket configuration)

    websocket_ping_interval
        Set to the desired WebSocket PING interval in seconds(default:120 = 2 minutes).
        If set to 0 (or negative), the WebSocket PING is disabled.         
        
    log_level
        Defines the log level, with a string value compliant to the std logger package (ie. DEBUG, ERROR, ...)
"""
from custom_lib.runtimeutils import on_digi_board

import sys #@UnusedImport
import traceback


if on_digi_board():
    # import Digi board specific libraries
    import digiwdog #@UnresolvedImport
    
# imports
import threading #@UnusedImport
import socket
import time
import digitime

from settings.settings_base import SettingsBase, Setting
from devices.device_base import DeviceBase
from samples.sample import Sample #@UnusedImport
from channels.channel_source_device_property import ChannelSourceDeviceProperty, DPROP_PERM_GET, DPROP_OPT_AUTOTIMESTAMP

#imports from the mod_pywebsocket library
import custom_lib.websocket #@UnusedImport

from optparse import Values
from custom_lib.websocket.mod_pywebsocket_ext_lib.example.echo_client import EchoClient #@UnresolvedImport @UnusedImport
from custom_lib.websocket.mod_pywebsocket_ext_lib.example.echo_client import ClientHandshakeProcessor #@UnresolvedImport @UnusedImport
from custom_lib.websocket.mod_pywebsocket_ext_lib.example.echo_client import ClientHandshakeProcessorHybi00 #@UnresolvedImport @UnusedImport
from custom_lib.websocket.mod_pywebsocket_ext_lib.example.echo_client import ClientRequest #@UnresolvedImport @UnusedImport

from custom_lib.websocket.mod_pywebsocket_ext_lib.mod_pywebsocket import common #@UnresolvedImport @UnusedImport
from custom_lib.websocket.mod_pywebsocket_ext_lib.mod_pywebsocket.stream import Stream #@UnresolvedImport @UnusedImport
from custom_lib.websocket.mod_pywebsocket_ext_lib.mod_pywebsocket.stream import StreamHixie75 #@UnresolvedImport @UnusedImport
from custom_lib.websocket.mod_pywebsocket_ext_lib.mod_pywebsocket.stream import StreamOptions #@UnresolvedImport @UnusedImport
from custom_lib.websocket.mod_pywebsocket_ext_lib.example.echo_client import _PROTOCOL_VERSION_HIXIE75, _PROTOCOL_VERSION_HYBI00,_PROTOCOL_VERSION_HYBI08,_PROTOCOL_VERSION_HYBI13 #@UnresolvedImport @UnusedImport

#FIXME the following imports  must be correctly changed 
from mod_pywebsocket._stream_base import ConnectionTerminatedException, BadOperationException

# constants
# =========

VERSION_NUMBER = '$LastChangedRevision: 1446 $'[22:-2]

#--- DYNDNS configuration parameters

DYNDNS_USERNAME     = 's-diam-msi-pangoo'
DYNDNS_PASSWORD     = 'pangoo'

#--- Pangoo AO common definitions
from custom_lib.commons.pangoolib import init_module_logger, check_debug_level_setting, update_logging_level

TIMEOUT_INSTANTANEOUS = 0.1

# Watchdog timeouts
# unit are seconds
MAIN_LOOP_STILL_LOOPING_WATCHOG_DELAY = 60 * 5
MAIN_LOOP_IS_NOT_INSTANTANEOUS_WATCHDOG_DELAY = 60 * 30

TIMEOUT_FOR_SERVER_TCP_SOCKET_CONNNECT = 10.0
TIMEOUT_FOR_RW_TO_CONNECTED_WEBSOCKET = 1.5
WAIT_TIME_BETWEEN_SUCCESSIVE_FAILD_SERVER_CONNECT = 30.0

BLINK_TIME_BASE_SLEEP = 0.5

# classes

class websocketupload(DeviceBase, threading.Thread):
    """The Websocket upload Driver class
    """
    def __init__(self, name, core_services):
        
        """Performs startup initializations.  It verifies and loads the settings list."""
        
        self._logger = init_module_logger(name)
        
        self.__name = name
        
        self.__core = core_services

        self._server_conn_handle = None
        self._read_channel_name = None
        
        self._keep_alive_timer = 0

        
        # stream used to communicate with websocket server
        self._websocket_stream = None
        self._resource_uri = None
        self._server_port = None
        self._server_address = None
        self._activate_tcp_keepalive = None
        self.__websocket_io_lock = threading.Lock()        
        
        # watchdogs
        self._mainloop_made_a_pause = None
        self._mainloop_made_one_loop = None
        


        settings_list = [
                         
            Setting(
                name='read_channel', type=str, required=True),
            Setting(
                name='server_port', type=int, required=True, default_value=9990),
            Setting(
                name='server_address', type=str, required=True, default_value="localhost"),
            Setting(
                name='activate_tcp_keepalive', type=bool, required=False, default_value=True),
            Setting(
                name='resource_uri', type=str, required=True),
            Setting(
                name='websocket_ping_interval', type=int, required=False, default_value=120),
            Setting(
                name='log_level', type=str, required=True, default_value='DEBUG', verify_function=check_debug_level_setting),                  
        ]
        
        ## Channel Properties Definition:
        
        property_list = [
                         
            #  properties
            
           ChannelSourceDeviceProperty(name="commands", type=str,
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
        
        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    def apply_settings(self):
        
        """If settings are changed this is the final step before the settings are available to use"""
        
        SettingsBase.merge_settings(self)
        
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        
        if len(rejected) or len(not_found):
            
            self._logger.error ("Settings rejected/not found: %s %s" % (rejected, not_found))

        SettingsBase.commit_settings(self, accepted)
        
        # reset class variables according to new values
        need_to_reset_socket_connection = False
        
        # other parameter
        self._read_channel_name = SettingsBase.get_setting(self, 'read_channel')
        self._server_port = SettingsBase.get_setting(self, 'server_port')
        self._server_address = SettingsBase.get_setting(self, 'server_address')
        self._activate_tcp_keepalive = SettingsBase.get_setting(self, 'activate_tcp_keepalive')
        self._resource_uri = SettingsBase.get_setting(self, 'resource_uri')
        
        settings_needing_connection_reset = ['server_address',
                                             'server_port',
                                             'resource_uri',
                                             'activate_tcp_keepalive']
        
        # If intersection of "accepted" list and "settings_needing_connection_reset" list is not empty.
        # we need to reset the socket connection
        if len (set(accepted) & set(settings_needing_connection_reset)) != 0:
            need_to_reset_socket_connection = True
        
        update_logging_level (self._logger, SettingsBase.get_setting(self, 'log_level'))
            
        if (need_to_reset_socket_connection):
            self._logger.info ('Some parameter change need a AlwaysON connection reset')
            self.close_websocket_connection_synchronized()
            
     
        return (accepted, rejected, not_found)

    def start(self):
        
        """Kicks off the main thread that maintains a TCP connection with the server."""
        
        self._logger.info("========== Starting up ==========")
         
        threading.Thread.start(self)
        
        return True

    def stop(self):
        """Stop the this presentation driver.  Returns bool."""
        self.__stopevent.set()
        return True

    def run(self):
        
        """
        This is the main loop of the thread in this driver.  This function will never exit.
        It checks for data coming from the server.
        """ 
        
        self._logger.info("Run, init")
        
        self._init_hardware_board_system_config()
        

        # Get settings to initialize local class variables
        
        websocket_ping_interval = SettingsBase.get_setting(self, 'websocket_ping_interval')
        websocket_ping_interval_timer_total_blinks = websocket_ping_interval*(1.0/BLINK_TIME_BASE_SLEEP)
            
        ao_server_connexion_timer_total_blinks = WAIT_TIME_BETWEEN_SUCCESSIVE_FAILD_SERVER_CONNECT*(1.0/BLINK_TIME_BASE_SLEEP)

        self._open_websocket_connection_synchronized()
        
        #subscribe to the response channels
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()

        self._logger.info("Setting up channels")
        self._logger.info("Subscribing to channel: %s"%self._read_channel_name)
        cp.subscribe(self._read_channel_name, self._receive_data_from_dia)
        
    
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
                if (self._mainloop_made_a_pause):
                    self._mainloop_made_a_pause.stroke()
            
            # Notify the watchdog that we are still looping
            if (self._mainloop_made_one_loop):
                self._mainloop_made_one_loop.stroke()

            blink_cnt += 1
            if (blink_cnt > 50):
                blink_cnt = 0
                self._logger.debug('Blink after %d iterations' % mainloop_made_a_pause_strike_cnt)
                mainloop_made_a_pause_strike_cnt = 0
                
            if (self._server_conn_handle):
                
                # Connected to AO server: we can process datas
                

                # WARNING: this may introduce an infinite loop
                # The loop ends only if no more data are available for processing
                #
                # The watchdog is of this loop so that if this loop lasts to much time,
                # the watchdog resets everything
                
                # poll for work
                data_has_been_processed = self._websocket_server_poll()
                if (data_has_been_processed):
                    # _websocket_server_poll does not consume all available data
                    # so, loop immediately as long as data are available
                    take_a_delay_in_next_loop_iteration = False
                else:
                    # _websocket_server_poll processed no data, which means that no data is currently available.
                    # so, in the next loop iteration, we tell to take a rest
                    take_a_delay_in_next_loop_iteration = True
                    
                if (websocket_ping_interval > 0):
                    self._keep_alive_timer += 1
                    if (self._keep_alive_timer >= websocket_ping_interval_timer_total_blinks):
                        self._send_keep_alive_synchronized()
                        self._keep_alive_timer = 0                 
                
            else:
                
                # Not connected to AO server: try first to connect to it
                
                take_a_delay_in_next_loop_iteration = True
                
                conn_cnt += 1
                if (conn_cnt > ao_server_connexion_timer_total_blinks):
                    
                    self._logger.info('Retry to open TCP connection')
                    
                    conn_cnt = 0
                    #open our server connection
                    self._open_websocket_connection_synchronized()
                    
    def _write_payload_to_websocket_synchronized (self, payload, binary=False):
        """Send a message to a supposed open socket connected to the WebSocket server"""

        try:
            # critical section start
            self.__websocket_io_lock.acquire()  
            
            done = False
        
            try:
                
                self._logger.debug("Write payload to socket.")
                self._server_conn_handle.settimeout(TIMEOUT_FOR_RW_TO_CONNECTED_WEBSOCKET)                
                self._websocket_stream.send_message(message=payload, binary=binary)
                done = True
                
            except Exception, msg:
                self._logger.error('Exception raised during write operation to the socket connected to WebSocket server. Exception was: %s' % msg)
                # FIXME: debug
                traceback.print_exc()
                self._release_socket_to_closed_websocket_connection()
                
            return done
        
        finally:
            # critical section end 
            self.__websocket_io_lock.release()
            
            
    def _send_keep_alive_synchronized(self):
        """Send a PING message to a supposed open socket connected to the WebSocket server"""
        
        try:
            # critical section start
            self.__websocket_io_lock.acquire()
            
            done = False       
        
            self._keep_alive_timer = 0 # reset keep_alive timer
            try:
                self._logger.debug('Sends a WebSocket PING frame')
                self._server_conn_handle.settimeout(TIMEOUT_FOR_RW_TO_CONNECTED_WEBSOCKET)                
                self._websocket_stream.send_ping()
                done = True
        
            except Exception, msg:
                self._logger.error('Exception raised during write operation to the socket connected to WebSocket server. Exception was: %s' % msg)
                # FIXME: debug
                traceback.print_exc()
                self._release_socket_to_closed_websocket_connection()
                
                return done
                
        finally:
            # critical section end 
            self.__websocket_io_lock.release()                       

            
    def _send_payload_to_websocket_server (self, payload=None, reopen_closed_websocket=True, doPing=False):
        """Send a payload to a WebSocket.
        Try to reopen it if it is closed when repoen_if_closed is set
        
        WARNING: This method is call asynchronously. Indeed, we don't know in which state the WebSocket connection is.
        """
        
        done = False
                
        # check if the WebSocket client API considers that the connection is still in an "opened" state
        # we must check that all the objects are instantiated correctly before checking there attributes
        if self._server_conn_handle and \
            self._websocket_stream and \
            self._websocket_stream._request and \
            self._websocket_stream._request.client_terminated:
            
            self._logger.info('WebSocket has been closed by peer.')
            self._release_socket_to_closed_websocket_connection()

        if not self._server_conn_handle and reopen_closed_websocket:
            # The WebScocket connection is currently closed
            self._logger.info('The WebSocket connection is currently closed. Try to reopen it right now...')
            self._open_websocket_connection_synchronized()
            # If it did no work, self._server_conn_handle value remains None

        if self._server_conn_handle:
            # if the connection to the WebSocket server is opened, try to send this new data to it
            
            self._logger.debug("Forward sample to WebSocket server.")
            if payload:
                done = self._write_payload_to_websocket_synchronized(payload)
                self._keep_alive_timer = 0 # Reset our keep alive timer because we interacted with the server
            elif doPing:
                done = self.__send_keep_alive_synchronized()
            else:
                self._logger.critical ("Bad parameters to _send_payload_to_websocket_server function")
                
        else:
            self._logger.error("WebSocket connection closed. Sample not forwarded.")    
            
        return done                
            
    def _receive_data_from_dia(self, channel):
        """A new sample has arrived on one of the response channels
        we are monitoring, send message to server"""
        
        sample = channel.get()
        payload = str(sample.value)

        self._logger.debug('Received the following new sample from channel %s: %s' % (channel.name(), payload))
        
        self._send_payload_to_websocket_server (payload, reopen_closed_websocket=True)

    #-------------------------------------
    def _init_hardware_board_system_config(self):
        """ Change system board configuration that depends on current runtime configuration
        Form example, board name depends on SIM card number"""
        
        if (on_digi_board()):
            
            
            try:

                # Arm watchdogs
                self._mainloop_made_one_loop = digiwdog.Watchdog(MAIN_LOOP_STILL_LOOPING_WATCHOG_DELAY, self.get_name() + " main loop no more looping. Force reset")
                self._mainloop_made_a_pause = digiwdog.Watchdog(MAIN_LOOP_IS_NOT_INSTANTANEOUS_WATCHDOG_DELAY, self.get_name() + " main is looping instantaneously. Force reset")
                
            except Exception, msg: 
                self._logger.error('Board system config: Error during DynDNs config setup. Error was: %s'% msg)   
            
        else:
            self._logger.error('No board system configuration necessary')
        
  
    def close_websocket_connection_synchronized(self):            
        """Close the websocket connection, when opened"""
        
        try:
            # critical section start
            self.__websocket_io_lock.acquire()  

            self._logger.info ('Request to close wWebSocket connection')                  
            if self._server_conn_handle:
                
                # FIXME: no closing handshake
                self._logger.error ('Should do closing handshake...')
                
                self._server_conn_handle.close()
                self._server_conn_handle = None
        finally:
            # critical section start
            self.__websocket_io_lock.release()                
        
            
    def _release_socket_to_closed_websocket_connection(self):            
        """Close the tcp connection to the server"""
        if self._server_conn_handle:
            try:
                self._server_conn_handle.close()
            except:
                # ignore any fault
                pass
            self._server_conn_handle = None            

    def _do_openning_handshake(self):
        
        """Run the client.

        Shake hands and then repeat sending message and receiving its echo. 
        we assume that socket is open and connected to the server
        """

   
        # TODO: check how we can integrated TLS connection 

#             if self._options.use_tls:
#                 self._server_conn_handle = _TLSSocket(
#                     self._server_conn_handle,
#                     self._options.tls_module,
#                     self._options.tls_version,
#                     self._options.disable_tls_compression)

        # TODO: add the protocol version to the setting list
        version = _PROTOCOL_VERSION_HYBI13
        
        options=Values()
        options.ensure_value("server_host", self._server_address)
        options.ensure_value("server_port", self._server_port)
        options.ensure_value("use_tls", False)
        options.ensure_value("origin", 'http://localhost')
        options.ensure_value("protocol_version", version)
        options.ensure_value("resource",self._resource_uri)
        options.ensure_value('version_header', -1)
        options.ensure_value('deflate_frame', False)
        options.ensure_value('deflate_stream', False)
         
        if (version == _PROTOCOL_VERSION_HYBI08 or
            version == _PROTOCOL_VERSION_HYBI13):
            self._handshake = ClientHandshakeProcessor(
                self._server_conn_handle, options)
        elif version == _PROTOCOL_VERSION_HYBI00:
            self._handshake = ClientHandshakeProcessorHybi00(
                self._server_conn_handle, options)
        else:
            raise ValueError('Invalid --protocol-version flag: %r' % version)
        
        self._handshake._logger = self._logger
        
        self._server_conn_handle.settimeout(TIMEOUT_FOR_RW_TO_CONNECTED_WEBSOCKET)
        self._handshake.handshake()

        self._logger.info('WebSocket connection established')

        request = ClientRequest(self._server_conn_handle)
        request._logger = self._logger

        version_map = {
            _PROTOCOL_VERSION_HYBI08: common.VERSION_HYBI08,
            _PROTOCOL_VERSION_HYBI13: common.VERSION_HYBI13,
            _PROTOCOL_VERSION_HYBI00: common.VERSION_HYBI00}
        request.ws_version = version_map[version]

        if (version == _PROTOCOL_VERSION_HYBI08 or
            version == _PROTOCOL_VERSION_HYBI13):
            stream_option = StreamOptions()
            stream_option.mask_send = True
            stream_option.unmask_receive = False

            if options.deflate_stream:
                stream_option.deflate_stream = True

            if options.deflate_frame is not False:
                processor = self._options.deflate_frame
                processor.setup_stream_options(stream_option)

            self._websocket_stream = Stream(request, stream_option)
        elif version == _PROTOCOL_VERSION_HYBI00:
            self._websocket_stream = StreamHixie75(request, True)
            
        self._websocket_stream._logger = self._logger
       

    def _open_websocket_connection_synchronized(self):
        
        """Establish the websocket connection to the server"""

        try:
            # critical section start
            self.__websocket_io_lock.acquire()
            
            ip = self._server_address
            port = self._server_port
            self._logger.info("Opening the TCP connection to %s:%d ..." % (ip,port))
            
            socket_dest_address = (ip, port)
    
            self._server_conn_handle = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
            try:
                self._server_conn_handle.settimeout(TIMEOUT_FOR_SERVER_TCP_SOCKET_CONNNECT)
                
                if (self._activate_tcp_keepalive):
                    self._logger.info('IP: activate TCK_KEEP_ALIVE on socket')
                    self._server_conn_handle.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                else:
                    self._logger.info('IP: disable TCK_KEEP_ALIVE on socket')
                    self._server_conn_handle.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 0)
               
                # connect to the server
                self._server_conn_handle.connect(socket_dest_address)
                
    
                
                self._logger.info('TCP socket successfully opened to %s:%d' % (ip, port))
                
            except Exception, msg:
                self._logger.critical('IP connect failed to %s:%d. Error was: %s. Will retry in %d seconds'%(ip, port, msg, WAIT_TIME_BETWEEN_SUCCESSIVE_FAILD_SERVER_CONNECT))
                
                # In some cases for SocketException, the msg is formated as a tuple, so that it contains an error code as first field.
                # We get the first element and compare it to known errors
                error_code = msg[0]
                if (error_code == -6):      
                    self._logger.info('    Socket error "-6": this is a transient DNS resolution problem (may be no connection to DNS server?).')
                    self._logger.info('    The connection will probably succeed later...')
                self._release_socket_to_closed_websocket_connection()
                
            if self._server_conn_handle:
                
                try:
                
                    # do WebSocket initial handshake
                    # if handshake fails, an exception is raised
                    self._do_openning_handshake()
                
                except Exception, msg:
                    self._logger.critical('Error during initial WebSocket handshake. Close socket and will retry later. Error was: %s.' % msg)
                    
                    # we close the socket for a later retry
                    stacktrace = traceback.format_exc()
                    self._logger.error('Trace: %s' % stacktrace)
                    
                    self._release_socket_to_closed_websocket_connection()
        finally:
            # critical section end 
            self.__websocket_io_lock.release()
            

    def _websocket_server_poll(self):
        ''' Poll for data from the server and WP DD to process.
        When no data has been processed, return False
        Return True in any data (from AO server or DD) has been processed
        '''
        
        # Give priority to DD response message.
        # So, before checking for now messages from AO server,
        # check (and process ALL) messages from DD
        
        any_data_has_been_processed = False

       
        # handle socket requests from server
        websocket_packet = self._receive_websocketserver_message_synchronized(TIMEOUT_INSTANTANEOUS)
        
        if (websocket_packet):
            
            any_data_has_been_processed = True
            self._process_websocketserver_received_message(websocket_packet)
            
        return any_data_has_been_processed
    
    #-------------------------------------
    def _receive_websocketserver_message_synchronized(self, timeout):
        """ Wait for a packet from the server, with timeout.
        """

        try:
            # critical section start
            self.__websocket_io_lock.acquire()
            
            received = None
            ao_command = None # FIXME: ao_command no more relevant for websocket            
            
            # check if the socket itself has not been closed asynchroneously
            if not self._server_conn_handle:
                self._logger.info('Socket has been closed (my be by peer)')
                self._release_socket_to_closed_websocket_connection()   
                return None             
                
            # check if the WebSocket client API considers that the connection is still in an "opened" state 
            if self._websocket_stream._request.client_terminated:
                self._logger.info('WebSocket has been closed by peer')
                self._release_socket_to_closed_websocket_connection()
                return None
     
            try:
                self._server_conn_handle.settimeout(timeout)
                received = self._websocket_stream.receive_message()
                
            except ConnectionTerminatedException :
                # When method receive_message runs into a timeout, ConnectionTerminatedException exception is raised
                pass
                
            except BadOperationException:
                self._logger.info('Try to read a message while WebSocket has been closed without closing handshake (broken socket?)')
                self._release_socket_to_closed_websocket_connection()  
                return None          
                
            except Exception, msg:
                self._logger.error('Exception raised during message reception for server: %s' % msg)
                # FIXME: debug
                stacktrace = traceback.format_exc()
                self._logger.error('Trace: %s' % stacktrace)
                self._release_socket_to_closed_websocket_connection()
                return None
                
            if (not received) or len(received) == 0:
                #nothing to read, so don't complain
                if (timeout != TIMEOUT_INSTANTANEOUS):
                    self._logger.critical("No receive data from websocket server, %f timeout", timeout)
                return None
            
            # Websocket returns an UNICODE type object
            # convert if to a standard string
            # CAUTION: non-ascii characters will be replaced by '?' due to the 'replace' flag
            reveived_str = received.encode('ascii', 'replace')
        
            # We have a validated packet.
            self._logger.debug("Receive new message from websocket server ")
            self._logger.debug("    Received: %s" % reveived_str)
            
            return (ao_command, reveived_str)
        
        finally:
            # critical section end 
            self.__websocket_io_lock.release()            
        

    def _process_websocketserver_received_message(self, msg):
        """ This function is called after the message is received to actually act upon the data.
        It also performs some final verification that message is not corrupt. """
        
        _, received_payload = msg
        
        self._logger.debug ('received a new command: %s' % received_payload)
        
        self.property_set("commands", Sample(0, received_payload))
        

#=============================

def main():
    pass

if __name__ == '__main__':
    status = main()
    sys.exit(status)



