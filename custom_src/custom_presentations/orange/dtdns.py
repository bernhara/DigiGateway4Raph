# $Id: dtdns.py 1439 2014-12-29 09:57:35Z orba6563 $

"""
DTDNS Presentation for Dynamic DNS https://www.dtdns.com/

"""
# imports
import urllib
import traceback
import socket
import digitime
import threading

from custom_lib.runtimeutils import on_digi_board
if on_digi_board():
    # import Digi board specific libraries
    import digicli #@UnresolvedImport

from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase

#--- Ecocity common definitions
from custom_lib.commons.pangoolib import check_debug_level_setting, update_logging_level, init_module_logger

# constants

__version__ = "$LastChangedRevision: 1439 $"

# classes
class DTDNSPresentation(PresentationBase):
    
    def __init__(self, name, core_services):

        self.__name = name
        self.__core = core_services
        
        self._logger = init_module_logger(name)
        self._published_ip_address = None
             
        # Configuration Settings:

        settings_list = [
                Setting(name="hostname", type=str, required=True),
                Setting(name="domainname", type=str, required=False, default_value="dtdns.net"),

                Setting(name="dtdns_server_host", type=str, required=False, default_value="www.dtdns.com"),
                Setting(name="dtdns_server_port", type=int, required=False, default_value=80),
                Setting(name="dtdns_password", type=str, required=True),                
                Setting(name="use_proxy", type=bool, required=False, default_value=False),
                Setting(name="proxy_host", type=str, required=False, default_value="proxy"),                   
                Setting(name="proxy_port", type=int, required=False, default_value=8080),
                
                Setting(name="address_update_rate", type=int, required=False, default_value=600),
                Setting(name="check_for_valid_address_rate", type=int, required=False, default_value=30),
                Setting(name="interface", type=str, required=False, default_value='mobile0'),
                Setting(name="no_digicli", type=bool, required=False, default_value=False),

                
                Setting(name='log_level', type=str, required=False, default_value='DEBUG', verify_function=check_debug_level_setting),
        ]
                                                 
        PresentationBase.__init__(self, name=name, settings_list=settings_list)
        
        self.__stopevent = threading.Event()

        return
    
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
        
        return (accepted, rejected, not_found)
    
    def start(self):
        
        self._logger.info ('Start')

        while 1:
            
            interface = SettingsBase.get_setting(self, 'interface')
            
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break
            if on_digi_board() and (not SettingsBase.get_setting (self, "no_digicli")):
                current_ip_address = self._get_ip_address_with_digicli()
            else:
                current_ip_address = self._get_ip_address_with_socket()
            if current_ip_address:
                # we got a valid address
                if current_ip_address != self._published_ip_address:
                    # address has changed => update it
                    self._logger.debug ('Got new IP address for interface: %s' % interface)
                    if self._update_dtdns():
                        self._published_ip_address = current_ip_address
                else:
                    self._logger.debug ('IP address unchanged')
                # wait and check for new address change
                digitime.sleep (SettingsBase.get_setting(self, 'address_update_rate'))
            else:
                self._logger.debug ('No valid IP address for interface: %s' % interface)
                # wait and check for new address availability
                digitime.sleep (SettingsBase.get_setting(self, 'check_for_valid_address_rate'))
        
        self._logger.info ('Terminating')
        return True
    
    
    def stop(self):
        self.__stopevent.set()
        self._logger.debug ('Received stop event')
        return True    
 
    def _update_dtdns (self):
        
        update_result_status = False
        
        dtdns_host = SettingsBase.get_setting (self, "dtdns_server_host")   
        dtdns_port = SettingsBase.get_setting (self, "dtdns_server_port")

        dtdns_id_param = "%s.%s" % (SettingsBase.get_setting (self, "hostname"), SettingsBase.get_setting (self, "domainname"))
        dtdns_pw_param = SettingsBase.get_setting (self, "dtdns_password")
        dtdns_client_param = "iDigiDIA_%s" % self.__name
        
        params = urllib.urlencode({'id': dtdns_id_param, 'pw': dtdns_pw_param, 'client': dtdns_client_param})
        update_url = "http://%s:%d/api/autodns.cfm?%s" % (dtdns_host, dtdns_port, params)
        
        self._logger.info("Will update DTDNS for %s" % dtdns_id_param)
        self._logger.debug ("Will issue a HTTP GET on: %s" % update_url)
        
        proxies = {}
        if SettingsBase.get_setting (self, "use_proxy"):
            http_proxy_specification = 'http://%s:%d' % (SettingsBase.get_setting (self, "proxy_host"), SettingsBase.get_setting (self, "proxy_port"))
            self._logger.info ("Use HTTP proxy: %s" % http_proxy_specification)
            proxies = {'http': http_proxy_specification}

        try:            
            filehandle = urllib.urlopen(update_url, proxies=proxies)
            self._logger.info ("Update result: %s" % filehandle.read())
            self._logger.info ("Update done")
            update_result_status = True
            
        except Exception, msg:
            self._logger.error ('Exception raised during request. Exception was: %s' % msg)  
            self._logger.error(traceback.format_exc())   
            update_result_status = False
                   
        return update_result_status
    
    def _get_ip_address_with_socket (self):
        
        computed_ip_address = None
        
        if SettingsBase.get_setting (self, "use_proxy"):
            ip = SettingsBase.get_setting (self, "proxy_host")
            port = SettingsBase.get_setting (self, "proxy_port")
        else:
            ip = SettingsBase.get_setting (self, "dtdns_server_host")
            port = SettingsBase.get_setting (self, "dtdns_server_port")

        try:
            
            self._logger.debug ("Try to get IP address by setting up a connection to %s:%s" % (ip, port))
            tmp_socket_to_dtdns_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tmp_socket_to_dtdns_server.settimeout(20)
            
            # connect to the server
            connection_status = tmp_socket_to_dtdns_server.connect_ex((ip, port))
            
            if (connection_status == 0):
    
                (ip_addr, _) = tmp_socket_to_dtdns_server.getsockname()
                tmp_socket_to_dtdns_server.close()

                self._logger.debug ("Get IP address: %s" % ip_addr)
                
                computed_ip_address = ip_addr

        except Exception, msg:
            self._logger.error('Could not obtain IP address: %s' % msg)
            self._logger.error(traceback.format_exc())
            computed_ip_address = None
            
        return computed_ip_address
    
   
    def _get_ip_address_with_digicli (self):
           
           
        cli_output_example = ''' Device Table:
        
         Name     PhysAddr          Status
         mobile0  00:00:00:00:00:00 connected
         vpn4     NA                closed
         vpn3     NA                closed
         vpn2     NA                closed
         vpn1     NA                closed
         vpn0     NA                closed
         eth0     00:40:9D:51:09:35 connected
         vrrp7    NA                closed
         vrrp6    NA                closed
         vrrp5    NA                closed
         vrrp4    NA                closed
         vrrp3    NA                closed
         vrrp2    NA                closed
         vrrp1    NA                closed
         vrrp0    NA                closed
         LOOPBACK NA                connected
        
         Device Entry IP Configuration:
        
         Name     Family mHome Type   Status      IPAddress
         mobile0  IPv4   0     manual configured  90.117.242.26/30
         eth0     IPv4   0     manual configured  192.168.1.1/24
         LOOPBACK IPv4   0     manual configured  127.0.0.1/32
        '''
        
        interface = SettingsBase.get_setting (self, "interface")
        
        network_config_cli_command = "display netdevice"
        
        cli_command_ok, cli_command_output_list = digicli.digicli(network_config_cli_command)
        
        cli_command_output = ''.join(line for line in cli_command_output_list)

        if (not cli_command_ok):
            self._logger.error ("Error in CLI command: %s" % cli_command_output)
            return None
        
        
        self._logger.debug ('CLI command result: %s' % cli_command_output)
        
        # search for interface number
        split_header = 'Device Entry IP Configuration'
        header_end_index = cli_command_output.find(split_header) + len (split_header)
        if header_end_index == -1:
            return None
        device_config_sub_part = cli_command_output[header_end_index:]
        
        interface_sub_part_index = device_config_sub_part.find (interface)
        if interface_sub_part_index == -1:
            return None
        interface_sub_part = device_config_sub_part[interface_sub_part_index:]
        
        ip_address_sub_part = interface_sub_part[41:]
        ip_address_end_index = ip_address_sub_part.find('/')
        if ip_address_end_index == -1:
            return None
        
        computed_ip_address = ip_address_sub_part[:ip_address_end_index]  
        self._logger.debug ('Got IP address: %s' % computed_ip_address)      
        
          
        return computed_ip_address
    
