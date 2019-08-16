# $Id: test_ecocity_json_formater.py 1394 2014-12-03 12:51:21Z orba6563 $

#
# Small test program intended to send commands to ecocity_json_formater
# using DIA Web console.
# Sample commands are sent to the diasampleinjector DD
#

#
# Launch parameters

dia_url = 'http://localhost:7777/idigi_dia.html'

gw_ec_key = "K_raph_1"
sensor_ec_key = "K_raph_2"

#
# imports
#

import base64
import urllib
import sys
import os



def performHttpCall (url = None, proxies = {}):
    
    f = urllib.urlopen(url=url, proxies=proxies)
    return f.read()

if __name__ == '__main__':
    
    if not os.environ.has_key('totest'):
        print >> sys.stderr, "\"totest\" environment variable should be set"
        sys.exit(1)
        
    toTest = os.environ['totest'] 
    
    json_command = ''
    if 'REBOOT' == toTest:
    
        # a reboot example
        reboot_command = '''{"publickKey":"%s","name":"REBOOT","parameters":{}}''' % gw_ec_key
        
        json_command_to_send = reboot_command
        
        print "Test reboot"
        
    if 'DIGI_CLI' == toTest:
        
        # a cli example
        cli_command = "boot a=r"
        
        base64_cli_command = base64.b64encode(cli_command)
        
        json_cli_command = '''{"publickKey":"%s", "name":"DIGI_CLI", "parameters" : {"cli_command_b64": "%s"}}''' % (gw_ec_key, base64_cli_command)
        
        json_command_to_send = json_cli_command
        
        print "Test cli"
        print "Cli command: %s" % cli_command
        print "Cli command b64 encoded: %s" % base64_cli_command

    
    elif 'FORWARD' == toTest:
    
        # a forward example
        xbee_frame_for_sensor = 'toto'
    
        base64_frame=base64.b64encode(xbee_frame_for_sensor)
        forward_command = '''{"publickKey":"%s", "name":"FORWARD", "parameters" : {"frame_b64": "%s"}}''' % (sensor_ec_key, base64_frame)
        
        json_command_to_send = forward_command
        
        print "Test forward"
        print "XBee frame: %s" % xbee_frame_for_sensor
        print "XBee frame b64 encoded: %s" % base64_frame
        
    else:
        print >> sys.stderr, "no matching test command"
        sys.exit(1)
    
    ###########
    
    # Proceed test
    
    print "JSon command: %s" % json_command_to_send
    
    idigi_dia = urllib.urlencode({'injector0.raw_in': json_command_to_send})
    print "idigi_dia encoded parameter: %s" % idigi_dia
    
    full_url = dia_url + '?' + idigi_dia
    print "full url: %s" % full_url
    
    response = performHttpCall(full_url, {})
    print response