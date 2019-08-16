# $Id: setInitBoardConfigParams.py 7869 2012-10-29 16:36:49Z orba6563 $

import sys

if sys.platform.startswith('digi'):
    on_digi_board = True
    # import Digi board specific libraries
    import rci
else:
    on_digi_board = False
    import urllib
    from optparse import OptionParser
    
traceFlagSet = False

def trace (msg):
    if (traceFlagSet):
        print msg
 
rci_get_command_all_settings = \
    """<rci_request version="1.1">
            <query_setting/>
        </rci_request>"""
        
rci_set_command_header = \
"""
<rci_request version="1.1">
   <set_setting>
"""
rci_set_command_trailer = \
"""
    </set_setting>
</rci_request>
"""

rci_settings_default_gw_config = \
"""
<profile>
    <profile_type>custom</profile_type>
</profile>
<serial>
    <baud>9600</baud>
    <databits>8</databits>
    <stopbits>1</stopbits>
    <parity>none</parity>
    <flowcontrol>none</flowcontrol>
    <sigsonopen>rtsdtr</sigsonopen>
    <altpin>off</altpin>
    <desc>Waveport</desc>
    <rtsflow>off</rtsflow>
    <predelay>0</predelay>
    <postdelay>0</postdelay>
    <rciserial>off</rciserial>
    <bitgap>10</bitgap>
    <xbreak>off</xbreak>
    <ctsflow>off</ctsflow>
    <dtrflow>off</dtrflow>
    <dsrflow>off</dsrflow>
    <dcdflow>off</dcdflow>
    <riflow>off</riflow>
    <closewait>forever</closewait>
    <ixon>off</ixon>
    <ixoff>off</ixoff>
</serial>

<term>
    <state>off</state>
</term>

<tcpkeepalive>
    <garbage_byte>on</garbage_byte>
    <override_dhcp>off</override_dhcp>
    <probe_count>5</probe_count>
    <probe_interval>10</probe_interval>
    <idle>180</idle>
</tcpkeepalive>

<host>
    <name>digi-pangoogw</name>
</host>

<mobile>
    <mobile_provider>orange</mobile_provider>
    <mobile_failed_orig_to_reset_system>50</mobile_failed_orig_to_reset_system>
    <mobile_failed_orig_to_reset_module>3</mobile_failed_orig_to_reset_module>
    <mobile_surelink_onoff>0</mobile_surelink_onoff>
    <mobile_data_only_mode>0</mobile_data_only_mode>
    <mobile_gsm_band>0</mobile_gsm_band>
    <mobile_connect_attempts>3</mobile_connect_attempts>
    <mobile_register_time>30</mobile_register_time>
</mobile>

<mobileppp>
    <enabled>enabled</enabled>
    <address_remote>0.0.0.0</address_remote>
    <address_local>0.0.0.0</address_local>
    <address_mask>255.255.255.255</address_mask>
    <chap_id>orange</chap_id>
    <pap_id>orange</pap_id>
    <ipcp_dns_enabled>on</ipcp_dns_enabled>
</mobileppp>

<python index="1">
    <state>off</state>
    <command>PangooDiaGW.py dia-pangoo5071.yml</command>
    <onexit>none</onexit>
</python>
<python index="2">
    <state>off</state>
    <command>PangooDiaGW.py dia-pangoo5072.yml</command>
    <onexit>none</onexit>
</python>

<smscell>
    <state>on</state>
    <ack_rcvd_cmds>off</ack_rcvd_cmds>
    <verbose_event_log>on</verbose_event_log>
    <def_rcvr>python</def_rcvr>
    <py_state>on</py_state>
</smscell>

<router>
    <ipForwardingEnabled>on</ipForwardingEnabled>
    <natInstance index="1">
        <natEnabled>on</natEnabled>
        <natMaxEntries>256</natMaxEntries>
        <natIfName>mobile0</natIfName>
        <dmzEnabled>off</dmzEnabled>
        <portXlateArray index="1">
            <portXlateEnabled>on</portXlateEnabled>
            <portXlateProto>tcp</portXlateProto>
            <portXlatePortCount>1</portXlatePortCount>
            <portXlateExternalPort>10080</portXlateExternalPort>
            <portXlateInternalPort>80</portXlateInternalPort>
            <portXlateInternalIpAddress>127.0.0.1</portXlateInternalIpAddress>
        </portXlateArray>
        <portXlateArray index="2">
            <portXlateEnabled>on</portXlateEnabled>
            <portXlateProto>tcp</portXlateProto>
            <portXlatePortCount>1</portXlatePortCount>
            <portXlateExternalPort>10023</portXlateExternalPort>
            <portXlateInternalPort>23</portXlateInternalPort>
            <portXlateInternalIpAddress>127.0.0.1</portXlateInternalIpAddress>
        </portXlateArray>
        <portXlateArray index="3">
            <portXlateEnabled>on</portXlateEnabled>
            <portXlateProto>tcp</portXlateProto>
            <portXlatePortCount>1</portXlatePortCount>
            <portXlateExternalPort>443</portXlateExternalPort>
            <portXlateInternalPort>22</portXlateInternalPort>
            <portXlateInternalIpAddress>127.0.0.1</portXlateInternalIpAddress>
        </portXlateArray>
    </natInstance>
</router>

<realport>
    <state>off</state>
</realport>

<secure_realport>
    <state>off</state>
</secure_realport>

<telnet_server>
    <state>off</state>
</telnet_server>

<tcp_server>
    <state>off</state>
</tcp_server>

<udp_server>
    <state>off</state>
</udp_server>

<ssh_server>
    <state>on</state>
</ssh_server>

<securesocket>
    <state>off</state>
</securesocket>

<camera>
    <state>off</state>
</camera>

<snmp_service>
	<state>off</state>
</snmp_service>

<system>
	<contact>Orange LABS Sophia Antipolis</contact>
	<description>Pangoo Wavenis iDigiDIA Gateway</description>
</system>

<mgmtnetwork>
    <networkType>modemPPP</networkType>
    <connectMethod>mt</connectMethod>
    <mtRxKeepAlive>60</mtRxKeepAlive>
    <mtTxKeepAlive>90</mtTxKeepAlive>
    <mtWaitCount>3</mtWaitCount>
    <mdhRxKeepAlive>60</mdhRxKeepAlive>
    <mdhTxKeepAlive>90</mdhTxKeepAlive>
    <mdhWaitCount>3</mdhWaitCount>
</mgmtnetwork>

<mgmtconnection>
    <connectionType>client</connectionType>
    <connectionEnabled>on</connectionEnabled>
    <lastKnownAddressUpdateEnabled>on</lastKnownAddressUpdateEnabled>
    <clientConnectionReconnectTimeout>60</clientConnectionReconnectTimeout>
    <pagedConnectionOverrideEnabled>off</pagedConnectionOverrideEnabled>
    <serverArray index="1">
        <serverAddress>en://my.idigi.co.uk</serverAddress>
        <securitySettingsIndex>0</securitySettingsIndex>
    </serverArray>
</mgmtconnection>
"""

# APN configuration
# -----------------

# List of all possible APNs (first id the default)
apnTuple = ["orange.m2m", "internet-entreprise"]

def build_rci_settings_apn_config (apn):
    rci_command = """
<ppp index="5">
    <enabled>enabled</enabled>
    <address_remote>0.0.0.0</address_remote>
    <address_local>0.0.0.0</address_local>
    <address_mask>255.255.255.255</address_mask>
    <chap_id>orange</chap_id>
    <pap_id>orange</pap_id>
    <ipcp_dns_enabled>on</ipcp_dns_enabled>
    <init_script>&apos;&apos; AT&amp;F\\134Q3+cgdcont=1,\\042IP\\042,\\042""" \
    + apn + \
    """\\042;\\136sgauth=3 OK \\c</init_script>
</ppp>
"""
    return rci_command

def performRciCall (rci_command, rci_url = None, proxies = {}):
    
    if (on_digi_board):
        response = rci.process_request (rci_command)
        
    else:
        opener = urllib.FancyURLopener(proxies)
        f = opener.open(rci_url, rci_command)
        
        try:
            for line in f:
                print line
        finally:
            f.close()
        
        opener.close()
        
if __name__ == '__main__':
    
    if (on_digi_board):
        skipPangooConfig = False
        skipApnConfig = False
        apn = apnTuple[0]
        rci_url = None
        proxies = {}
        traceFlagSet = False
        
    else:
    
        parser = OptionParser()
        parser.add_option("--host", dest="host", type="string", default="192.168.1.1",
                          help="RCI target hostname")
        parser.add_option("--port", dest="port", type="int", default=80,
                          help="RCI target port number")
        
        parser.add_option("--useProxy", action="store_true", dest="useProxy",
                          help="if set, uses the HTTP proxy configuration")    
        
        parser.add_option("--proxyUrl", dest="proxyUrl", type="string", default="http://proxy.rd.francetelecom.fr:3128",
                          help="Url of HTTP proxy to use")
        
        parser.add_option("--apn", dest="apn", type="choice", choices=apnTuple, default=apnTuple[0],
                          help="Default APN (" + "|".join(map(str, apnTuple)) + ")")    
    
        parser.add_option("--skipPangooConfig", action="store_true", dest="skipPangooConfig",
                          help="if set, skip application of Pangoo parameter family")    
    
        parser.add_option("--skipApnConfig", action="store_true", dest="skipApnConfig",
                          help="if set, skip application of APN parameter family")    
    
        parser.add_option("--debug", action="store_true", dest="debugFlag",
                          help="if set, activate traces")    
    
        (options, args) = parser.parse_args()
        
        if (len(args) != 0):
            parser.print_help()
            sys.exit (1)
        
        traceFlagSet = (options.debugFlag == True)
        
        trace (options)
        trace (args)
        
        # retrieve proxy configuration
        proxies = {}
        if (options.useProxy):
            proxies = {'http': options.proxyUrl}
        
        digiGwHostname = options.host
        digiGwPortnum = options.port
        skipPangooConfig = (options.skipPangooConfig == True) # may be None or True
        skipApnConfig = (options.skipApnConfig == True) # may be None or True
        apn = options.apn
        
        rci_url = 'http://' + digiGwHostname + ':' + str(digiGwPortnum) + '/UE/rci'
        print "Gateway to configure is at address: " + rci_url
        if (options.useProxy):
            print "\tusing HTTP proxy: " + options.proxyUrl
        else:
            print "\tusing a direct connection (no HTTP proxy)"
              
    #
    # Main Pangoo parameters
    # options may be None or True
    #
    
    if (not skipPangooConfig):

        trace ("Apply Pangoo config")

        rci_command_pangoo_config = \
            rci_set_command_header + \
            rci_settings_default_gw_config + \
            rci_set_command_trailer
    
        #! print "Dump current config"
        #! performHttpRciCall (rci_url, rci_get_command_all_settings, proxies)
        
        trace ("Apply pangoo default config")
        performRciCall (rci_command_pangoo_config, rci_url, proxies)

    #
    # APN part
    # options may be None or True
    #    
    if (not skipApnConfig):
        
        trace ("Apply APN config: %s" % apn)
    
        performRciCall ("""<rci_request version="1.1">
                <query_setting>
                    <ppp index="5"/>
                </query_setting>
            </rci_request>""",
            rci_url,
            proxies)
        rci_settings_apn_config = rci_set_command_header + build_rci_settings_apn_config(apn) + rci_set_command_trailer 
        performRciCall (rci_settings_apn_config, rci_url, proxies)
     
        performRciCall ("""<rci_request version="1.1">
                <query_setting>
                    <ppp index="5">
                    </ppp>
                </query_setting>
            </rci_request>""",
            rci_url,
            proxies)

    if (traceFlagSet):
        performRciCall (rci_get_command_all_settings, rci_url, proxies)
            
    trace ("Configuration done")
