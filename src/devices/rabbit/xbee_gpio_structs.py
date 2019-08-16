"""Rabbit XBee GPIO Struct Module"""
from struct import pack, unpack, calcsize

from xbee_gpio_types import *

# --- Module Constants ---
GPIO_MAX_SERVERS = 10
"""Sets the maximum number of GPIO servers the client will work with (max.  10)"""
GPIO_MAX_SIGNALS = 200
"""Sets the maximum number of signals on any GPIO server"""

GPIO_TIMEOUT     = 1250 #750 # ConnectPort Python rounds down
""" Sets the number of milliseconds that query_gpio_node allows for response
of each server request before a timeout error is returned"""

XBEE_ENDPOINT_GPIO         = 0xDB
"""GPIO endpoint for requests"""
XBEE_ENDPOINT_RESPONSE	   = 0xDA
"""GPIO endpoint for responses"""

# XB_PROFILE_DIGI from xbee_api.lib
XB_PROFILE_DIGI            = 0xC105

# Clusters for the GPIO endpoint
XBEE_GPIO_CLUST_INFO       = 0x40   
"""get general device info"""
XBEE_GPIO_CLUST_NAME       = 0x41   
"""get types and names of I/O signals"""
XBEE_GPIO_CLUST_ANA_RANGE  = 0x42   
"""get range info for analog input"""
XBEE_GPIO_CLUST_READ       = 0x43   
"""read states of I/O signals"""
XBEE_GPIO_CLUST_WRITE      = 0x44
"""change states of outputs"""

# I/O Types and their setting size (size is 1 octet unless otherwise specified)
# Data Type for I/O Type as __doc__

XBEE_GPIO_TYPE_DISABLED     = 0x00
"""Null (0 octets)"""
XBEE_GPIO_TYPE_INVALID      = 0xFF
"""Null (0 octets)"""

# Data Type for I/O Type
XBEE_GPIO_TYPE_DISABLED     = 0x00    
"""Null (0 octets)"""
XBEE_GPIO_TYPE_INVALID      = 0xFF    
"""Null (0 octets)"""

# Output types
XBEE_GPIO_TYPE_DIGITAL_OUT  = 0x01    
"""Boolean (0/low, 1/high)"""
XBEE_GPIO_TYPE_LED_OUT      = 0x02    
"""Boolean (0/off, 1/on)"""

XBEE_GPIO_TYPE_SINK_OUT     = 0x10    
"""Enum (0/sink, 2/tristate)"""
XBEE_GPIO_TYPE_SOURCE_OUT   = 0x11    
"""Enum (1/source, 2/tristate)"""
XBEE_GPIO_TYPE_TRISTATE_OUT = 0x12    
"""Enum (0/sink, 1/source, 2/tristate)"""

XBEE_GPIO_TYPE_ANALOG_OUT   = 0x20    
"""Float (4 octets, IEEE float)"""

# Input types
XBEE_GPIO_TYPE_DIGITAL_IN   = 0x81    
"""Boolean (0/low, 1/high)"""
XBEE_GPIO_TYPE_SWITCH_IN    = 0x82    
"""Boolean (0/open, 1/closed)"""

XBEE_GPIO_TYPE_ANALOG_IN    = 0xA3    
"""Float (4 octets, IEEE float)"""

IO_Types = {
    0x00: None,
    0xFF: None,
    # Output types
    #XBEE_GPIO_TYPE_DIGITAL_OUT  
    0x01: HighLow, #bool,  # 0/low, 1/high
    #XBEE_GPIO_TYPE_LED_OUT      
    0x02: OnOff, #bool,  # 0/off, 1/on
                                               
    #XBEE_GPIO_TYPE_SINK_OUT     
    0x10: SinkSourceTristate, #int, # 0/sink, 2/tristate
    #XBEE_GPIO_TYPE_SOURCE_OUT   
    0x11: SinkSourceTristate, #int, # 1/source, 2/tristate
    #XBEE_GPIO_TYPE_TRISTATE_OUT 
    0x12: SinkSourceTristate, #int, # 0/sink, 1/source, 2/tristate
                                               
    #XBEE_GPIO_TYPE_ANALOG_OUT   
    0x20: gpioFloat, # 4 octets, IEEE float
                                               
    # Input types                              
    #XBEE_GPIO_TYPE_DIGITAL_IN   
    0x81: HighLow, #bool,  # 0/low, 1/high
    #XBEE_GPIO_TYPE_SWITCH_IN    
    0x82: OpenClosed, #bool,  # 0/open, 1/closed
                                               
    #XBEE_GPIO_TYPE_ANALOG_IN    
    0xA3: gpioFloat,  # 4 octets, IEEE float
}


# masks for various types
XBEE_GPIO_MASK_TYPE_INPUT   = 0x80
"""Bit flag indicating input channel"""
XBEE_GPIO_MASK_TYPE_ANALOG  = 0x20
"""Bit flag indicating analog"""

# settings for outputs
XBEE_GPIO_OUTPUT_LOW        = 0
XBEE_GPIO_OUTPUT_HIGH       = 1
XBEE_GPIO_OUTPUT_OFF        = 0
XBEE_GPIO_OUTPUT_ON         = 1
XBEE_GPIO_OUTPUT_SINK       = 0
XBEE_GPIO_OUTPUT_SOURCE     = 1
XBEE_GPIO_OUTPUT_TRISTATE   = 2

# settings for inputs
XBEE_GPIO_INPUT_LOW         = 0
XBEE_GPIO_INPUT_HIGH        = 1
XBEE_GPIO_INPUT_OPEN        = 0
XBEE_GPIO_INPUT_CLOSED      = 1

# GPIO states
CLIENT_STATE_IDLE           = 0      # Client state idle must be zero
CLIENT_STATE_REQ_INFO       = 1
CLIENT_STATE_PARSE_INFO     = 2
CLIENT_STATE_NEW_NAME       = 3
CLIENT_STATE_REQ_NAME       = 4
CLIENT_STATE_PARSE_NAME     = 5
CLIENT_STATE_REQ_ANARANGE   = 6
CLIENT_STATE_PARSE_ANARANGE = 7
CLIENT_STATE_REQ_READ       = 8
CLIENT_STATE_PARSE_READ     = 9
CLIENT_STATE_PARSE_WRITE    = 10

# status bytes for XBEE_GPIO_CLUST_WRITE responses
XBEE_GPIO_STATUS_SUCCESS            = 0x00
XBEE_GPIO_STATUS_DISABLED           = 0xF0
XBEE_GPIO_STATUS_BAD_TYPE           = 0xF1
XBEE_GPIO_STATUS_OUT_OF_RANGE       = 0xF2
XBEE_GPIO_STATUS_INVALID            = 0xFF

# Main function states
ZB_IDLE = 0
ZB_NODE_OPEN = 1
ZB_EXIT = 2

# Command parsing states
PARSE_CMD = 0       # Parse command component
PARSE_SIGNAL = 1    # Parse signal ID component
PARSE_VALUE = 2     # Parse value component
PARSE_DONE = 3      # Parse complete, execute command and exit
PARSE_ERROR = 4     # Error, print message and exit (keep below PARSE_DONE)
PARSE_EXIT = 5      # Exit parsing function         (keep below PARSE_DONE)

# Signal commands
SIGNAL_GET = 0      # Get value(s) from one or all signal sources
SIGNAL_SET = 1      # Set value to output signal

class xbee_frame_gpio_info_t:
    """\
Implements the C structure xbee_frame_gpio_info_t

Frame format for Device Info (XBEE_GPIO_CLUST_INFO cluster) Response

Payload contains an 8-bit cluster version, an 8-bit count of I/O signals on
the device, a 16-bit device manufacturer, a 16-bit device type, and a 16-bit
firmware version.

The firmware version is stored in BCD and can be printed as::

    ("%u.%02x", firmware_ver >> 8, firmware_ver & 0x00FF))

For example, v1.23 is stored as 0x0123.

Code::

    typedef struct {
        byte     protocol_ver;        // version of the GPIO Endpoint
                                        // protocol used
        byte     io_count;            // # of I/O signals on device (0-254)
        // the remaining elements can be used to identify a
        // manufacturer-specific version of this structure, with
        // additional fields following firmware_ver
        word     manufacturer;        // for this sample, set to 0x101e (Digi)
        word     device_type;         // unique code to identify the device
        word     firmware_ver;        // BCD (0x0123 = v1.23)
    } xbee_frame_gpio_info_t;

* Calling ``<object>.pack_()`` returns a string with PACK_LEN bytes.  
* Calling ``xbee_frame_gpio_info_t(protocol_ver, io_count, manufacturer,
  device_type, firmware_ver)`` creates a new instance.  
* Calling ``xbee_frame_gpio_info_t.unpack_(data)`` creates an instance 
  based on the packed data.

    """

    PACK_FMT = '<2B3H'
    PACK_LEN = calcsize(PACK_FMT)
    
    def __init__(self, protocol_ver, io_count, manufacturer, device_type, \
            firmware_ver):
        self.protocol_ver = protocol_ver
        self.io_count = io_count
        self.manufacturer = manufacturer
        self.device_type = device_type
        self.firmware_ver = firmware_ver
    
    def pack_(self):
        return pack(self.PACK_FMT, self.protocol_ver, self.io_count, \
            self.manufacturer, self.device_type, self.firmware_ver)
    
    @staticmethod
    def unpack_(frame):
        x = xbee_frame_gpio_info_t # shortcut to long-named class
        return unpack(x.PACK_FMT, frame[:x.PACK_LEN])

    @staticmethod
    def len(name=""):
        return xbee_frame_gpio_info_t.PACK_LEN

class xbee_gpio_cluster_request_t:
    """\
Frame format for GPIO Name (XBEE_GPIO_CLUST_NAME cluster) Request

Payload is variable-length, and is simply a series of 8-bit I/O signal
numbers.

Example to retrieve the names of the first 8 I/O signals::

    0x00 0x01 0x02 0x03 0x04 0x05 0x06 0x07

Valid I/O signal numbers are 0x00 through 0xFE, 0xFF is reserved for future
use.  If the server receives a request with an 0xFF, it should ignore the
0xFF byte and all bytes that follow.
    """
    # This is just a series of bytes, nothing special to handle it.
    pass

class xbee_gpio_rec_name_resp_t:
    """\
Implements the C structure.

Code::

    typedef struct {
        byte  signal;
        byte  type;
        byte  namelen;
        char  name[20];            // 0 to 20 character name, not terminated
    } xbee_gpio_rec_name_resp_t;

with the caveat that namelen+name is represented as the string 'name'
in the class, and the a pascal string in the packed class.
    """

    PACK_FMT = '<2B%dp'
    PACK_LEN = calcsize(PACK_FMT % 0)
    
    def __init__(self, signal, type_, name):
        """Create an object: parameters signal, type, name"""
        self.signal = signal
        self.type = type_
        self.name = name
		
		# from core.tracing import get_tracer
		# self.__tracer = get_tracer("xbee_gpio_structs.xbee_gpio_rec_name_resp_t")
    
    def pack_(self):
        """Return the structure as an octet string"""
        x = xbee_gpio_rec_name_resp_t # shortcut to class with long name
        fmt = x.PACK_FMT % (len(self.name)+1)
        #self.__tracer.info('fmt: ', fmt)
        return pack(fmt, self.signal, self.type, self.name)
    
    @staticmethod
    def unpack_(frame):
        """Given an octet string, interpret it as a structure"""
        x = xbee_gpio_rec_name_resp_t # shortcut to class with long name
        fmt = x.PACK_FMT % (len(frame) - x.PACK_LEN)
        #self.__tracer.info('fmt: ', fmt)
        return unpack(fmt, frame)
    
    @staticmethod
    def len(name):
        return xbee_gpio_rec_name_resp_t.PACK_LEN + len(name) + 1 

#   """
#   Frame format for GPIO Name (XBEE_GPIO_CLUST_NAME cluster) Response
#   ------------------------------------------------------------------
#   Payload is variable-length, with a record for each I/O signal requested.
#   Each record starts with the 8-bit I/O number and an 8-bit type.  If the
#   type is not 0xFF, an 8-bit length for its name follows (or 0x00 if it is
#   unnamed), and <length> bytes of printable characters for the name.
#
#   Maximum length for an I/O Signal Name is 20 characters.
#
#   Example response to the request example above (with extra line-breaks and
#   comments for readability:
#      0x00 0x81 0x04 'D' 'I' 'N' '0'      ; I/O #0, digital input, "DIN0"
#      0x01 0x81 0x04 'D' 'I' 'N' '1'      ; I/O #1, digital input, "DIN1"
#      0x02 0xA3 0x04 'A' 'I' 'N' '0'      ; I/O #2, analog input, "AIN0"
#      0x03 0xA3 0x04 'A' 'I' 'N' '1'      ; I/O #3, analog input, "AIN1"
#      0x04 0x01 0x05 'D' 'O' 'U' 'T' '0'  ; I/O #4, digital output, "DOUT0"
#      0x05 0x01 0x05 'D' 'O' 'U' 'T' '1'  ; I/O #5, digital output, "DOUT1"
#      0x06 0x02 0x04 'L' 'E' 'D' '0'      ; I/O #6, LED/Light, "LED0"
#      0x07 0xFF                           ; I/O #7 is not a valid I/O signal
#
#   Names are sent in the order requested.
#
#   If there isn't enough room to fit all of the names in the frame, the
#   requestor will have to send an updated request asking for the missing
#   I/O numbers from the first request.
#   """

class xbee_gpio_rec_ar_resp_units_t:
    """\

Code::

    typedef struct {
        byte  signal;
        byte  length;
        char  units[15];
    } xbee_gpio_rec_ar_resp_units_t;

    """
    PACK_FMT = '<B%dp'
    PACK_LEN = calcsize(PACK_FMT % 0)

    def __init__(self, signal, units):
        """Create an object: parameters signal, units"""
        self.signal = signal
        self.units = units
		
		# from core.tracing import get_tracer
		# self.__tracer = get_tracer("xbee_gpio_structs.xbee_gpio_rec_ar_resp_units_t")
    
    def pack_(self):
        """Return the structure as an octet string"""
        x = xbee_gpio_rec_ar_resp_units_t # shortcut to class with long name
        fmt = x.PACK_FMT % (len(self.units)+1)
        #self.__tracer.info('fmt: ', fmt)
        return pack(fmt, self.signal, self.units)
    
    @staticmethod
    def unpack_(frame):
        """Given an octet string, interpret it as a structure"""
        x = xbee_gpio_rec_ar_resp_units_t # shortcut to class with long name
        fmt = x.PACK_FMT % (len(frame) - x.PACK_LEN)
        #self.__tracer.info('fmt: ', fmt)
        return unpack(fmt, frame)
    
    @staticmethod
    def len(units):
        return xbee_gpio_rec_ar_resp_units_t.PACK_LEN + len(units) + 1 



class xbee_gpio_rec_ar_resp_range_t:
    """\

Code::

    typedef struct {
        float lower, upper;
    } xbee_gpio_rec_ar_resp_range_t;

    """

    PACK_FMT = '<2f'
    PACK_LEN = calcsize(PACK_FMT)

    def __init__(self, lower, upper):
        """Create an object: parameters lower, upper"""
        self.lower = lower
        self.upper = upper
		
		# from core.tracing import get_tracer
		# self.__tracer = get_tracer(xbee_gpio_structs.xbee_gpio_rec_ar_resp_range_t)
    
    def pack_(self):
        """Return the structure as an octet string"""
        fmt = xbee_gpio_rec_ar_resp_range_t.PACK_FMT
        #self.__tracer.info('fmt: ', fmt)
        return pack(fmt, self.lower, self.upper)
    
    @staticmethod
    def unpack_(frame):
        """Given an octet string, interpret it as a structure"""
        fmt = xbee_gpio_rec_ar_resp_range_t.PACK_FMT 
        len_ = xbee_gpio_rec_ar_resp_range_t.PACK_LEN
        return unpack(fmt, frame[:len_])
    
    @staticmethod
    def len(name=""):
        return xbee_gpio_rec_ar_resp_range_t.PACK_LEN


class gpio_device_t:
    """\

Code::

    // Main control structure for communicating with GPIO servers
    typedef struct {
    int      state;          // State of request/response operation
    int      ep_count;       // End point counter for processing I/O groups
    int      last_ep;        // Last end point to be read
    int      node_index;     // ZigBee Node Index of this GPIO server
    byte     io_count;       // Count of I/O end points on this GPIO server
    word     device_type;    // Device type code from GPIO server
    byte     last_request;   // Last request sent to this GPIO server
    unsigned long request_sent; // Timestamp of when last_request was sent
    } gpio_device_t;

    """

    PACK_FMT = '<hhhhBHBL'
    PACK_LEN = calcsize(PACK_FMT)

    def __init__(self, state, ep_count, last_ep, node_index, io_count,
            device_type, last_request, request_sent):
        """Create an object: state, ep_count, last_ep, node_index, io_count,
            device_type, last_request, request_sent"""
        self.state = state
        self.ep_count = ep_count
        self.last_ep = last_ep
        self.node_index = node_index
        self.io_count = io_count
        self.device_type = device_type
        self.last_request = last_request
        self.request_sent = request_sent

        from core.tracing import get_tracer
        self.__tracer = get_tracer("gpio_device_t")
    
    def pack_(self):
        """Return the structure as an octet string"""
        fmt = gpio_device_t.PACK_FMT
        #self.__tracer.info('fmt: ', fmt)
        return pack(fmt, self.state, self.ep_count, self.last_ep,
                self.node_index, self.io_count, self.device_type,
                self.last_request, self.request_sent)
    
    @staticmethod
    def unpack_(frame):
        """Given an octet string, interpret it as a structure"""
        return unpack(gpio_device_t.PACK_FMT, frame)
    
    @staticmethod
    def len(name=""):
        return gpio_device_t.PACK_LEN


