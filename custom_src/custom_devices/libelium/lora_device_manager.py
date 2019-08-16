# $Id: lora_device_manager.py 1482 2015-12-30 09:24:54Z orba6563 $

"""
    Custom DIA 'LoraGateway' from Libelium Device

"""

__version__ = "$LastChangedRevision: 1482 $"
VERSION_NUMBER = '$LastChangedRevision: 1482 $'[22:-2]

# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property \
    import \
        DPROP_OPT_AUTOTIMESTAMP, \
        DPROP_PERM_GET, \
        Sample, \
        ChannelSourceDeviceProperty
        
import threading
import digitime
import serial

from custom_lib.commons.pangoolib \
    import \
        init_module_logger, \
        check_debug_level_setting, \
        update_logging_level

# Constants below are copied from FrameHandler.java 
# (project https://github.com/Orange-OpenSource/iot-libelium-lora-gateway) 
BYTE_SOH = 0x01;
BYTE_CR  = 0x0D;
BYTE_LF  = 0x0A;
BYTE_EOT = 0x04;

LETTER_HASH = '#';
LETTER_LT = '<';
LETTER_EQUAL = '=';
LETTER_GT = '>';

# Automaton states.
STATE_WAIT_SOH_OR_LT = 1
STATE_WAIT_PAYLOAD = 2
STATE_WAIT_LF = 3 
STATE_WAIT_CRC1 = 4
STATE_WAIT_CRC2 = 5
STATE_WAIT_CRC3 = 6
STATE_WAIT_CRC4 = 7
STATE_WAIT_EOT = 8
# States for waspmote frames.
STATE_WAIT_EQUAL = 9
STATE_WAIT_GT = 10
STATE_WAIT_TYPE = 11
# States for waspmote ASCII frames.
# Note: an ASCII frame ends with an undocumented 0x0D 0x0A.
STATE_WAIT_NB_FIELDS = 12
STATE_WAIT_FIRST_FIELD = 13
STATE_WAIT_FINAL_HASH = 14
STATE_WAIT_FINAL_CR = 15
STATE_WAIT_FINAL_LF = 16
# States for waspmote binary frames.
STATE_WAIT_NB_BYTES = 17
STATE_WAIT_LAST_BYTE = 18

# exception classes

# interface functions

# classes
class LoraDeviceManager(DeviceBase, threading.Thread):
    
    def __init__(self, name, core_services):
        ## Initialize and declare class variables
        self.__name = name
        self.__core = core_services
        
        self.__logger = init_module_logger(name)

        ## Settings Table Definition:
        settings_list = [
            Setting(
                    name='baudrate', type=int, required=False, default_value=38400,
                    verify_function=lambda x: x > 0),
            Setting(
                    name='port', type=str, required=False, default_value='11'),
            Setting(
                    name='mainloop_serial_read_timeout', type=int, required=False, default_value=30),                         
            Setting(
                name='log_level', type=str, required=False, default_value='DEBUG', verify_function=check_debug_level_setting),
        ]

        ## Channel Properties Definition:
        property_list = [
            ChannelSourceDeviceProperty(name='software_version', type=str,
                initial=Sample(timestamp=digitime.time(), value=VERSION_NUMBER),
                perms_mask= DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
                                                  
            ChannelSourceDeviceProperty(
                name="LoRaPlugAndSenseFrame",
                type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP
                ),
        ]

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)


    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:
    def apply_settings(self):
        """
            Apply settings as they are defined by the configuration file.
        """
        
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        if len(rejected) or len(not_found):
            print "Settings rejected/not found: %s %s" % (rejected, not_found)

        SettingsBase.commit_settings(self, accepted)
        
        update_logging_level (self.__logger, SettingsBase.get_setting(self, 'log_level'))        

        return (accepted, rejected, not_found)

    def start(self):
        """
            Start the device object.
        """
        
        self.__logger.info(VERSION_NUMBER)
        # Start the thread
        threading.Thread.start(self)

        return True

    def stop(self):
        """
            Stop the device object.
        """
        
        self.__stopevent.set()

        return True

    ## Threading related functions:
    def run(self):

        # Try to open virtual serial port on USB.        
        try:
            self.__lora = serial.Serial(port=SettingsBase.get_setting(self, 'port'), baudrate=SettingsBase.get_setting(self, 'baudrate'))
            self.__logger.info('Serial port opened')
        except:
            self.__logger.fatal('Unable to open serial port %s at baudrate %d, aborting...' % (SettingsBase.get_setting(self, 'port'), SettingsBase.get_setting(self, 'baudrate')))
            return
        
        # Flush remaining serial input
        self.__logger.debug ("Start flushing serial buffer...")
        self.__lora.setTimeout(10)
        self.__lora.read(1024)
        self.__lora.setTimeout(SettingsBase.get_setting(self, 'mainloop_serial_read_timeout'))
        self.__logger.debug ("...serial buffer flushed")           
        
        # Initialize our internal state.
        # Receive buffer.
        self.__recBuffer = []
        # CRC buffer.
        self.__crcHex = []
        # Current automaton state.
        self.__currentAssemblyState = STATE_WAIT_SOH_OR_LT
        # Number of fields or number of bytes.
        self.__nbData = 0
        # Number of hash characters already received.
        self.__nbHash = 0
        
        # read current configuration
        lora_get_info_frame = '\x01READ\x0D\x0A2A31\x04'
        self.__lora.write(lora_get_info_frame)
        
        # At this stage, we have been able to open the virtual serial port.
        while True:
            
            if self.__stopevent.isSet():
                # Stop request received.
                self.__stopevent.clear()
                # Close virtual serial link.
                self.__lora.close()
                self.__logger.info('serial port closed')
                # And exit.
                break
            
            recByte = self.__lora.read(size=1)
            if recByte and len(recByte) > 0:
                recFrame = self.frameAssembler(recByte)
                if (recFrame != None):
                    # Convert to string after having removed first five characters.
                    recStr = ''.join(recFrame)
                    cleanedStr = recStr[5:]
                    self.__logger.debug('Received a frame: ' + cleanedStr)
                    self.property_set("LoRaPlugAndSenseFrame", Sample(digitime.time(), cleanedStr))
            else:
                self.__logger.debug('no data')
            
    # Internal functions & classes
    
    # Assembles a new frame using byte passed in input parameter. Returns payload when a whole frame is
    # assembled, null otherwise.
    # 
    # Two types of frames may be received:
    # - gateway frames (delimited by SOH and EOT), as answer to frames sent by this program
    # - waspmote frames (starting with <=>)
    # As no frame is sent by this program, first type should never be received. If one is received,
    # it is ignored.
    # 
    # Parameters:
    #   b byte to be processed. If -1, assembly processing is reset. If CRC is wrong, assembly processing
    #     is reset.
    # Returned Value:
    #   null until a new frame is received, otherwise frame payload
    def frameAssembler(self, b):
        """ Returns either a received frame or None. """
        payload = None
        if (self.__currentAssemblyState == STATE_WAIT_SOH_OR_LT):
            if (ord(b) == BYTE_SOH):
                self.__recBuffer = []
                self.__currentAssemblyState = STATE_WAIT_PAYLOAD
            elif (b == LETTER_LT):
                self.__recBuffer = []
                self.__recBuffer.append(LETTER_LT)
                self.__currentAssemblyState = STATE_WAIT_EQUAL
            else:
                self.__logger.error('Incorrect byte received: ' + hex(ord(b)))
        elif (self.__currentAssemblyState == STATE_WAIT_PAYLOAD):
            # Gateway frame
            if (ord(b) == BYTE_CR):
                self.__currentAssemblyState = STATE_WAIT_LF
            else:
                # Not a CR, part of payload.
                self.__recBuffer.append(b)
        elif (self.__currentAssemblyState == STATE_WAIT_LF):
            if (ord(b) != BYTE_LF):
                # Error. Reset assembly.
                self.__logger.debug('!= LF received: ' + hex(ord(b)))
                self.__currentAssemblyState = STATE_WAIT_SOH_OR_LT
            else:
                # LF received
                self.__currentAssemblyState = STATE_WAIT_CRC1
        elif (self.__currentAssemblyState == STATE_WAIT_CRC1):
            self.__crcHex = []
            self.__crcHex.append(b)
            self.__currentAssemblyState = STATE_WAIT_CRC2
        elif (self.__currentAssemblyState == STATE_WAIT_CRC2):
            self.__crcHex.append(b)
            self.__currentAssemblyState = STATE_WAIT_CRC3
        elif (self.__currentAssemblyState == STATE_WAIT_CRC3):
            self.__crcHex.append(b)
            self.__currentAssemblyState = STATE_WAIT_CRC4
        elif (self.__currentAssemblyState == STATE_WAIT_CRC4):
            # Checksum should be checked here. Ignored in this version.
            self.__currentAssemblyState = STATE_WAIT_EOT
        elif (self.__currentAssemblyState == STATE_WAIT_EOT):
            if (ord(b) != BYTE_EOT):
                # Error. Reset assembly.
                self.__logger.debug('!= EOT received: ' + hex(ord(b)))
                self.__currentAssemblyState = STATE_WAIT_SOH_OR_LT
            else:
                # EOT received.
                payload = self.__recBuffer
                self.__currentAssemblyState = STATE_WAIT_SOH_OR_LT
        elif (self.__currentAssemblyState == STATE_WAIT_EQUAL):
            # Waspmote frame.
            if (b != LETTER_EQUAL):
                # Error. Reset assembly.
                self.__logger.debug('!= = received: ' + hex(ord(b)))
                self.__currentAssemblyState = STATE_WAIT_SOH_OR_LT
            else:
                self.__recBuffer.append(LETTER_EQUAL)
                self.__currentAssemblyState = STATE_WAIT_GT
        elif (self.__currentAssemblyState == STATE_WAIT_GT):
            if (b != LETTER_GT):
                # Error. Reset assembly.
                self.__logger.debug('!= > received: ' + hex(ord(b)))
                self.__currentAssemblyState = STATE_WAIT_SOH_OR_LT
            else:
                self.__recBuffer.append(LETTER_GT)
                self.__currentAssemblyState = STATE_WAIT_TYPE
        elif (self.__currentAssemblyState == STATE_WAIT_TYPE):
            if ((ord(b) & 0x80) != 0):
                # ASCII frame.
                self.__recBuffer.append(b)
                self.__currentAssemblyState = STATE_WAIT_NB_FIELDS
            else:
                # Binary frame.
                self.__recBuffer.append(b)
                self.__currentAssemblyState = STATE_WAIT_NB_BYTES
        elif (self.__currentAssemblyState == STATE_WAIT_NB_FIELDS):
            # Waspmote ASCII Frame.
            self.__recBuffer.append(b)
            self.__nbData = ord(b)
            self.__nbHash = 0
            self.__currentAssemblyState = STATE_WAIT_FIRST_FIELD
        elif (self.__currentAssemblyState == STATE_WAIT_FIRST_FIELD):
            # We have to wait for 4 hash characters. Then we will have first field.
            self.__recBuffer.append(b)
            if (b == LETTER_HASH):
                self.__nbHash = self.__nbHash + 1
                if (self.__nbHash >= 4):
                    self.__nbHash = 0
                    self.__currentAssemblyState = STATE_WAIT_FINAL_HASH
        elif (self.__currentAssemblyState == STATE_WAIT_FINAL_HASH):
            # We have to wait for as many hash characters as number of fields (nbData).
            self.__recBuffer.append(b)
            if (b == LETTER_HASH):
                self.__nbHash = self.__nbHash + 1
                if (self.__nbHash >= self.__nbData):
                    self.__currentAssemblyState = STATE_WAIT_FINAL_CR
        elif (self.__currentAssemblyState == STATE_WAIT_FINAL_CR):
            # Undocumented trailing CR.
            if (ord(b) != BYTE_CR):
                self.__logger.debug('!= CR received: ' + hex(ord(b)))
                self.__currentAssemblyState = STATE_WAIT_SOH_OR_LT
            else:
                self.__currentAssemblyState = STATE_WAIT_FINAL_LF
        elif (self.__currentAssemblyState == STATE_WAIT_FINAL_LF):
            # Undocumented trailing LF.
            if (ord(b) != BYTE_LF):
                self.__logger.debug('!= LF received: ' + hex(ord(b)))
                self.__currentAssemblyState = STATE_WAIT_SOH_OR_LT
            else:
                payload = self.__recBuffer
                self.__currentAssemblyState = STATE_WAIT_SOH_OR_LT
        elif (self.__currentAssemblyState == STATE_WAIT_NB_BYTES):
            # Waspmote binary frame. TODO.
            self.__logger.error('Binary frame decoding not implemented yet, ignoring frame')
            self.__currentAssemblyState = STATE_WAIT_SOH_OR_LT
        else:
            self.__logger.fatal('Unknown state for frame assembler')
            self.__currentAssemblyState = STATE_WAIT_SOH_OR_LT
        return payload
