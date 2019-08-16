# $Id: waveport.py 7926 2012-11-27 08:55:40Z orba6563 $

import sys
import logging
from custom_lib.runtimeutils import on_digi_board
from custom_lib import logutils

#--- Pangoo Gateway cmd byte values
PG_CMD_ID     = '\x7a'
PG_CMD_MSG    = '\x7b'
PG_CMD_KALIVE = '\x7c'
PG_CMD_TRANS  = '\x55'
PG_CMD_GET_VERSION = '\x56'

#--- Pangoo Gateway routing byte values:
PG_ROUTE_WP  = 0 # route to waveport

#--- Alwayson route configuration
AO_ROUTE_GW_COMMAND = '\xFF' # route to gateway command interpreter
AO_ROUTE_XBEERAWOUT_DD = '\xFE' # route to xbeerawout device driver

#--- Predefined PANGOO messages
PANGOO_AO_ANSWER_FOR_GENERIC_ERROR = '\x04\x31\x04\x00'

#-- AlwaysON message organization
MSG_TUPLE_COMMAND = 0
MSG_TUPLE_LENGTH = 1
MSG_TUPLE_MESSAGE = 2

#---------------------
def ao_bin_to_hexstr(msg, withspaces = False):
    """ Convert from a raw binary string to a 2-char ascii hex string
        that the AlwaysOn server uses.  This is used on the WP binary
        packet data before sending to AO server.
    """
    
    # treat first degenerated cases  
    if (not msg or msg == ""):
        return ""

    hs = "" # ascii hex string to compose
    
    if (withspaces):
        for c in msg:
            b = ord(c)
            hs += "%02X " % b
        # remove last space char
        hs = hs[:-1]
    else:
        for c in msg:
            b = ord(c)
            hs += "%02X" % b

    return hs

#---------------------
def ao_hexstr_to_bin(msg, removespaces = False):
    """ Convert from a 2-char ascii hex string to a raw binary string
        that the AlwaysOn server uses.  This is used on the WavePort data
        coming from AO server going to WP host adapter.
        The string may contain spaces separating byte pair, to enhance string readability
    """
    if (removespaces):
        msg = msg.replace(' ', '')
    
    binary_string = "" # binary string to compose
    sz = len(msg)
    if (sz & 1):
        raise ValueError ('Expected even hexstr length')

    word_index = 0 # word index
    for i in xrange(sz/2):
        try :
            byte_pair_string = msg[word_index:word_index+2]
            b = int(byte_pair_string, 16)
        except ValueError, msg:
            raise ValueError ('Invalid hexstr chr: %s' % msg)
        binary_string += chr(b)
        word_index += 2
    return binary_string

#---------------------
def ao_cmd_human(cmd):
    ''' given a AO Server cmd char, return a human readable string suitable
        for logging '''
        
    # for human readable CMD trace logging:
    ao_cmds = { \
               PG_CMD_ID : "PG_CMD_ID", \
               PG_CMD_MSG : "PG_CMD_MSG", \
               PG_CMD_KALIVE : "PG_CMD_KALIVE", \
               PG_CMD_TRANS : "PG_CMD_TRANS" \
               }
        
    if (ao_cmds.has_key(cmd)):
        str_cmd = "%s" % ao_cmds[cmd]
    else:
        str_cmd = "cmd?:%02x" % ord(cmd)
    return str_cmd

#=============================
def encode_ao_size(size, ao_msg_size_on_7_bits):
    """ Computes the 2 bytes representing the size of a packet
        Returns a 2 byte string containing the 2 bytes """
        
    if ao_msg_size_on_7_bits:
        left_byte_value = size / 128
        right_byte_value = size % 128
    else:
        left_byte_value = (size >> 8) & 0xff
        right_byte_value = size & 0xff
        
    encoded_size_string = chr(left_byte_value) + chr(right_byte_value)
    
    return (encoded_size_string)

#=============================
def decode_ao_size(left_byte_string, right_byte_string, ao_msg_size_on_7_bits):
    """ Converts the 2 byte string representing a message length into an integer """
    
    if ao_msg_size_on_7_bits:
        return ( (ord(left_byte_string) << 7) | ord(right_byte_string))
    else:
        return ( (ord(left_byte_string) << 8) | ord(right_byte_string))
 
#=============================
#
# Logger facilities
#
#=============================    

def check_debug_level_setting(new_level_string):
    
    setting_syntax_valid = True
    
    try:
        new_level = eval ('logging.'+new_level_string)
        int(new_level) # raise an exception in we did not get an integer value
        setting_syntax_valid = True
    except Exception:
        setting_syntax_valid = False
        
    return setting_syntax_valid
    
def update_logging_level (logger, new_level_string):
        
    try:
        # The syntax of the setting has already been verified
        new_level = eval ('logging.'+new_level_string)
        logger.setLevel (new_level)
    except Exception:
        # new_level_string is not an attribute of the logging package
        logger.error ('Could not set logger level to: %s. Should be DEBUG, ERROR, ...'  % new_level_string)
    
#---------------------
def init_module_logger(logger_name, max_backups=1, max_bytes=512*2*32, buffer_size=200, flush_level=logging.INFO,  flush_window=0):
    
    # TODO: switch to std logging with config file / http://g-polarion-pangoov4/polarion/redirect/project/PANGOO_PF_DEV/workitem?id=PF-91
    # ... logging.config.fileConfig(logging_config_file)

    # logging setup
    if on_digi_board():
        logging_file_prefix='WEB/python/'
    else:
        logging_file_prefix=''
    
    logger = logging.getLogger(logger_name)
    fmt = logging.Formatter("%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s", "%Y-%m-%d %H:%M:%S")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    
    handler = logutils.SmartHandler(filename=logging_file_prefix + 'log_' + logger_name + '.txt',
                                    max_backups=max_backups,
                                    max_bytes=max_bytes,
                                    buffer_size=buffer_size,
                                    flush_level=flush_level,
                                    flush_window=flush_window)
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    
    return logger

#=============================================================================    
   
def main():

    captured_frame='7b 00 2c 30 30 31 32 32 30 30 31 30 35 31 39 31 18 30 33 30 30 35 38 37 31 39 30 31 30 37 32 35 30 41 43 30 30 42 44 43 30 31 30 33 37 34 38 36' 
    #
    # ASCI representation {.,00122001051910300587190107250AC00BDC01037486
    
    # test scenarios
    ao_ascii_frame = '7b 0e 03 FF 56 03 65 DD'
    ao_ascii_frame = captured_frame
        
    # convert to bin frame
    bin_frame = ao_hexstr_to_bin (ao_ascii_frame)
    
    # convert back to ascii frame
    ascii_frame = ao_bin_to_hexstr(bin_frame)
    ascii_frame_with_spaces = ao_bin_to_hexstr(bin_frame, True)
    
    print "Ascii frame to convert: %s" % ao_ascii_frame
    print "Back converted frame: ->%s<-" % ascii_frame
    print "Back converted frame (+ spaces): ->%s<-" % ascii_frame_with_spaces
    
    # test bogus config
    try:
        ao_hexstr_to_bin ('bad string')
    except ValueError, msg:
        print "String to convert is misformated: %s" % msg
        
    try:
        ao_hexstr_to_bin ('XXXX')
    except ValueError, msg:
        print "String to convert is misformated: %s" % msg

if __name__ == '__main__':
    status = main()
    sys.exit(status)
