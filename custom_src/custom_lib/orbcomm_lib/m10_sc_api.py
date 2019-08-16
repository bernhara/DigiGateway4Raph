# $Id: m10_sc_api.py 6845 2011-10-04 07:33:53Z vmpx4526 $
import logging
import time
import sys

import serial
from custom_lib import logutils

TIMEOUT_INSTANTANEOUS = 0.001
TIMEOUT_ACK = 1.900
TIMEOUT_SERIALPORT_RESPONSE = 3.800
TIMEOUT_SERIALPORT_WRITE = 1.000
TIMEOUT_ENPT_QUERY = 12.000
TIMEOUT_SERIALPORT_MSG_LEN = 0.050
TIMEOUT_SERIALPORT_BODY = 0.200

TIME_REBOOT_DTR_LOW = 1.000
TIME_REBOOT_DTR_UP = 10.000

SC_HEADER = '\x05'
DTE_HEADER = '\x85'

SC_ACK = '\x05\x01\x07\x00\x00\xC1\x32'


""" PACKET TYPE 
"""
UNKNOWN_PKT_TYPE = 'UNKNOWN'
LLA_PKT_TYPE = '\x01'
CONFIG_PKT_TYPE = '\x02'
COM_PKT_TYPE = '\x03'
SYS_PKT_TYPE = '\x04'
STATUS_PKT_TYPE = '\x05'
SC_MSG_PKT_TYPE = '\x06'
SC_DEFMSG_PKT_TYPE = '\x07'
SC_REPORT_PKT_TYPE = '\x08'
SC_DEFREPORT_PKT_TYPE = '\x09'
SC_GGRAM_PKT_TYPE = '\x0A'
SYSREP_PKT_TYPE = '\x0B'
SC_TERMMSG_PKT_TYPE = '\x0C'
SC_TERMCMD_PKT_TYPE = '\x0D'
SC_TERMGRAM_PKT_TYPE = '\x0E'
POSDET_PKT_TYPE = '\x0F'
POSSTATUS_PKT_TYPE = '\x10'
SC_POSREPORT_PKT_TYPE = '\x11'
GETPARAM_PKT_TYPE = '\x12'
SETPARAM_PKT_TYPE = '\x13'
PARAMREP_PKT_TYPE = '\x14'


""" STATUS CODES
"""
NO_ERROR_CODE = '\x00'
BUFFER_CODE = '\x01'
CHKSUM_CODE = '\x02'
INVPARAM_CODE = '\x03'
SIZEEXC_CODE = '\x04'
ILL_CODE = '\x05'
UNKNOWN_CODE = '\x06'
DUPLICATE_CODE = '\x07'

LLA_CODE_TO_HUMAN = {
    NO_ERROR_CODE:  "No error",
    BUFFER_CODE:    "Buffer unavailable (wait 30 sec)",
    CHKSUM_CODE:    "Invalid chksum",
    INVPARAM_CODE:  "Invalid parameter",
    SIZEEXC_CODE:   "Size exceeds queue capacity",
    ILL_CODE:       "Packet ill-formed",
    UNKNOWN_CODE:   "Unrecognized packet type",
    DUPLICATE_CODE: "Duplicate packet sequence number"
    }

SATELLITE_NUM_TO_NAME = {
    '\x00' : "No satellite in view" ,
    '\x05' : "A1",
    '\x06' : "A2",
    '\x07' : "A3",
    '\x08' : "A4",
    '\x09' : "A5",
    '\x0A' : "A6",
    '\x0B' : "A7",
    '\x0C' : "A8",
    '\x0D' : "B1",
    '\x0E' : "B2",
    '\x0F' : "B3",
    '\x10' : "B4",
    '\x11' : "B5",
    '\x12' : "B6",
    '\x13' : "B7",
    '\x14' : "B8",
    '\x15' : "C1",
    '\x16' : "C2",
    '\x17' : "C3",
    '\x18' : "C4",
    '\x19' : "C5",
    '\x1B' : "C7",
    '\x1E' : "D2",
    '\x1F' : "D3",
    '\x22' : "D6",
    '\x23' : "D7",
    '\x24' : "D8",
    '\x04' : "G2"
    }

"""GATEWAYS CODE
"""
GW_EUROPE = '\x78'


""" TYPE CODE DEFINITIONS
"""
RQ_TERMINATED_MSG = '\x00'
RQ_TERMINATED_MSG_NOT150 = '\x01'
RQ_GLOBALGRAM = '\x02'
RQ_OR_INDIC_ADRESS = '\x03'
RQ_STATUS_MSG_MHA = '\x04'
RQ_STATUS_MSG_ORBCOMM = '\x05'
RQ_SUBJECTS_MSG = '\x06'
RQ_SINGLE_SUBJECT_MSG = '\x07'
DEL_SINGLE_MSG = '\x08'
RQ_REG_SAT = '\x09'
GEN_FCT_10 = '\x0A'
GEN_FCT_11 = '\x0B'
GEN_FCT_12 = '\x0C'
GEN_FCT_13 = '\x0D'
GEN_FCT_14 = '\x0E'
GEN_FCT_15 = '\x0F'
RQ_STATUS_PKT = '\x10'
CLEAR_SCO_MSGQ = '\x13'
CLEAR_SCT_MSGQ = '\x14'

""" SIZE FIELDS FOR
MESSAGES WITH CONSTANT SIZE
"""
LLA_SIZE = '\x07\x00'
CONF_SIZE = '\x14\x00'
COM_SIZE = '\x0D\x00'
DEF_REP_SIZE = '\x0E\x00'
REP_SIZE = '\x12\x00'
GETPAR_SIZE = '\x08\x00'

SC_ORIGINATED_POLLING_IMMEDIATE = '\x00'
SC_ORIGINATED_POLLING_QUEUED = '\x01'

ACKNOWLEDGMENT_LEVEL_NO_ACK = '\x00'

PRIORITY_LEVEL_NON_URGENT = '\x00'
PRIORITY_LEVEL_NORMAL = '\x01'

DEFAULT_PIN_CODE = '\x00\x00\x00\x00'
DEFAULT_DESIRED_GATEWAY = GW_EUROPE
DEFAULT_SC_POLL_MODE = '\x00'
DEFAULT_ACK_LEVEL = '\x02'
DEFAULT_OR_IND_REPORTS = '\x01'
DEFAULT_OR_IND_MES = '\x01'
DEFAULT_PRIORITY_LVL = '\x01'
DEFAULT_MSG_BODY_TYPE = '\x00'
DEFAULT_REPORTS_SERVICE_TYPE = '\x02'
DEFAULT_GWY_SEARCH_MODE = '\x00'

DESIRED_GATEWAY_VALUES = {
    'GATEWAY_EUROPE':GW_EUROPE
}
SC_POLL_MODE_VALUES = {
    'SC_POLL_MODE_IMMEDIATE': '\x00',
    'SC_POLL_MODE_QUEUED': '\x01'
}
ACK_LEVEL_VALUES = {
    'ACK_LEVEL_NO_ACK_EXPECTED' : '\x00',
    'ACK_LEVEL_ONLY_NON_DELIVERY_ORBCOMM_GWY' : '\x01',
    'ACK_LEVEL_DELIVERY_ORBCOMM' : '\x02',
    'ACK_LEVEL_ONLY_NON_DELIVERY_RECIPIENT':'\x03',
    'ACK_LEVEL_DELIVERY_TO_RECIPIENT':'\x04'
}
PRIORITY_LVL = {
    'PRIORITY_LVL_NON_URGENT': '\x00',
    'PRIORITY_LVL_NORMAL': '\x01',
    'PRIORITY_LVL_URGENT': '\x02',
    'PRIORITY_LVL_SPECIAL_DELIVERY': '\x03'
}
MSG_BODY_TYPE_VALUES = {    
    'MSG_BODY_TYPE_ASCII': '\x00'
}
REPORTS_SERVICE_TYPE_VALUES = {    
    'REPORTS_SERVICE_TYPE_NORMAL_PRIORITY_NO_ACK': '\x00',
    'REPORTS_SERVICE_TYPE_NORMAL_PRIORITY_ONLY_NON_DELIVERY_ORBCOMM_GWY': '\x01',
    'REPORTS_SERVICE_TYPE_NORMAL_PRIORITY_DELIVERY_ORBCOMM': '\x02',
    'REPORTS_SERVICE_TYPE_NORMAL_PRIORITY_ONLY_NON_DELIVERY_RECIPIENT': '\x03',
    'REPORTS_SERVICE_TYPE_NORMAL_PRIORITY_DELIVERY_TO_RECIPIENT': '\x04'
    
}
GWY_SEARCH_MODE_VALUES = {
    'GWY_SEARCH_MODE_0':'\x00'
}

""" CRC calculation and formatting
"""
def fletcher_crc(msg):
    """
    Checksum Fletcher's algorithm 
    """
    sum1 = 0
    sum2 = 0
    lg = len(msg)
    
    for j in range(lg):
        byte = ord(msg[j])
        sum1 = (sum1 + byte) % 256
        sum2 = (sum2 + sum1) % 256
        
    check1 = 256 - ((sum1 + sum2) % 256);
    check2 = 256 - ((sum1 + check1) % 256);
    
    c1 = chr(check1) #formatting decimal value to hex with correct format \x00
    c2 = chr(check2)
     
    #msgWithCrc = msg + c1 + c2
    return c1 + c2

def encode_size(size):
    """
    Return the encoded size (2 byte string) as expected by the Orbcomm serial specification
    """
        
    right_byte_value = (size >> 8) & 0xff
    left_byte_value = size & 0xff
            
    encoded_size_string = chr(left_byte_value) + chr(right_byte_value)        
        
    return encoded_size_string

def decode_size(left_byte_char, right_byte_char):
    """
    Return the decoded size as an integer as formated by the Orbcomm serial specification
    """
    return ((ord(right_byte_char) << 8) | ord(left_byte_char))

def get_pkt_hex_code(packet):
    """
    Return the hexadecimal code associated to the packet type
    """
    return packet[1]

def is_a_LLA_PKT_TYPE(final_message):
    """
    Return True if the final message is a LLA packet
    """
    if get_pkt_hex_code(final_message) != LLA_PKT_TYPE:
        return False
    else:
        return True


class m10_sc_api : 
    
    def __init__(self, logger=None):
        """
        Init takes no arguments.
        It sets the serial port parameters to the following values:
            -PARITY_NONE
            -STOPBITS_ONE
            -EIGHTBITS
            -XonXoff False
            -RtsCts False
        It sets the m10 parameters to the values defined by the DEFAULT_(parameter_name) constants.
        
        Creating an m10_sc_api object doesn't open the serial connection.
        """
        if logger:
            self.logger = logger
        else:
            self.init_module_logger()
        
        self._ser = serial.Serial()
                
        # static configuration parameters
        self._ser.setParity(serial.PARITY_NONE)
        self._ser.setStopbits(serial.STOPBITS_ONE)
        self._ser.setByteSize(serial.EIGHTBITS)
        self._ser.setXonXoff(False)
        self._ser.setRtsCts(False)
        
        # dynamic configuration parameters
        self._pin_code = DEFAULT_PIN_CODE
        self._desired_gateway = DEFAULT_DESIRED_GATEWAY
        self._def_polled = DEFAULT_SC_POLL_MODE
        self._def_ack_level = DEFAULT_ACK_LEVEL
        self._def_rep_or_ind = DEFAULT_OR_IND_REPORTS
        self._def_msg_or_ind = DEFAULT_OR_IND_MES
        self._def_priority = DEFAULT_PRIORITY_LVL
        self._def_msg_body_type = DEFAULT_MSG_BODY_TYPE
        self._def_serv_type = DEFAULT_REPORTS_SERVICE_TYPE
        self._gwy_search_mode = DEFAULT_GWY_SEARCH_MODE
        
    def serial_is_open(self):
        """
        Return True if the serial connection is open.
        """
        return self._ser.isOpen()   
    
    def SC_COM_connect(self, port_num, baudrate):
        """
        Opens the serial connection with the values passed in arguments.
        It also sets the DTR value to True.
        """
        # serial connection parameters
        port_device = serial.device(port_num)
        self.logger.debug("openning device port: %s" % port_device)
        self._ser.setPort(port_device)
        self._ser.setBaudrate(baudrate)
        # open the serial port
        self._ser.open()
        self._ser.setDTR(True)
    
    def SC_Set_Library_Default_Settings(self, desired_gateway,
                                def_polled, def_ack_level,
                                def_rep_or_ind, def_msg_or_ind,
                                def_priority, def_msg_body_type,
                                def_serv_type, gwy_search_mode):
        """
        Sets the m10 parameters to the values passed in arguments.
        """
        # Setting the dynamic configuration parameters
        self._desired_gateway = desired_gateway
        self._def_polled = def_polled
        self._def_ack_level = def_ack_level
        self._def_rep_or_ind = def_rep_or_ind
        self._def_msg_or_ind = def_msg_or_ind
        self._def_priority = def_priority
        self._def_msg_body_type = def_msg_body_type
        self._def_serv_type = def_serv_type
        self._gwy_search_mode = gwy_search_mode
        
    def SC_Write_to_modem_Library_Default_Settings(self):
        """
        Applies the stored m10 parameters on the m10 device by sending a ConfigurationCommand.
        """
        # Writing on the modem the dynamic configuration parameters            
        self.SC_sndConfigurationCommand(self._pin_code, self._desired_gateway,
                                        self._def_polled, self._def_ack_level,
                                        self._def_rep_or_ind, self._def_msg_or_ind ,
                                        self._def_priority, self._def_msg_body_type,
                                        self._def_serv_type, self._gwy_search_mode)
        
    def SC_Clear_Message_Queues(self):
        """
        Empties the inbound message queue and the outbound message queue by sending
        a CommunicationCommand for each.
        At each time, it waits for an ack of the m10.
        """
        self._clear_SCTMsg_Queue()
        test = self.Rcv_structured_message(TIMEOUT_SERIALPORT_RESPONSE)[0]
        while(test != LLA_PKT_TYPE):
            test = self.Rcv_structured_message(TIMEOUT_SERIALPORT_RESPONSE)[0]
        self._clear_SCOMsg_Queue()
        test = self.Rcv_structured_message(TIMEOUT_SERIALPORT_RESPONSE)[0]
        while(test != LLA_PKT_TYPE):
            test = self.Rcv_structured_message(TIMEOUT_SERIALPORT_RESPONSE)[0]
        return True

    def SC_Reboot_m10(self):
        """
        Hard reboot of the m10 device.
        According to the specification, it puts DTR low and up.
        The waiting time for the device to be operational again is estimated to 10 sec. 
        """
        self._ser.setDTR(False)
        time.sleep(TIME_REBOOT_DTR_LOW)
        self._ser.setDTR(True) 
        time.sleep(TIME_REBOOT_DTR_UP)
           
    def SC_Stop(self):
        """
        Stop the device driver. Returns boolean.
        """
        self._ser.setRTS(0)
        self._ser.setDTR(0)
        self.close()
    
    """
    SEND FUNCTIONS
    """    
    def _protected_serial_write(self, message):
        """
        Security function to avoid crashes when writing on the serial port.
        """
        try:
            self._ser.setWriteTimeout(TIMEOUT_SERIALPORT_WRITE)
            self._ser.write(message)
        except serial.writeTimeoutError:
            self.logger.critical("Unexpected Serial Write Timeout")  
    
    def _clear_SCTMsg_Queue(self):
        """
        Send the Communication command associated with the clearing of the inbound message queue.
        """
        self.logger.debug("Clearing the SCT-Msg Queue")
        self.SC_sndCommunicationCommand(retry_count='\x00', type_code=CLEAR_SCT_MSGQ,
                                        value_byte_0='\x00', value_byte_1='\x00',
                                        value_byte_2='\x00', value_byte_3='\x00',
                                        gwy_id=self._desired_gateway)
    def _clear_SCOMsg_Queue(self):
        """
        Send the Communication command associated with the clearing of the outbound message queue
        """
        self.logger.debug("Clearing the SCO-Msg Queue")
        self.SC_sndCommunicationCommand(retry_count='\x00', type_code=CLEAR_SCO_MSGQ,
                                        value_byte_0='\x00', value_byte_1='\x00',
                                        value_byte_2='\x00', value_byte_3='\x00',
                                        gwy_id=self._desired_gateway)    

    
    def SC_sndLinkLevelAck(self, status):
        """ 
        LLA acknowledgment message 
        """
        msgtosend = DTE_HEADER + LLA_PKT_TYPE + LLA_SIZE + status
        msgtosend = msgtosend + fletcher_crc(msgtosend)
        self._protected_serial_write(msgtosend)
        self.logger.debug("LLA acknowledgment packet sent: %s" % ''.join('%02X ' % ord(x) for x in msgtosend))
        
        ## TODO: Link level acknoledgment to SC-terminated
    
    def SC_sndConfigurationCommand(self, pin_code4, desired_gwy, def_polled, def_ack_level, def_rep_or_ind, def_msg_or_ind, def_priority, def_msg_body_type, def_serv_type, gwy_search_mode):
        """
        Send a Configuration Command that sets the m10 device Configuration parameters to the values passed in arguments.
        """
        pkt_seq_num = '\x00'
        msgtosend = DTE_HEADER + CONFIG_PKT_TYPE + CONF_SIZE + pkt_seq_num + pin_code4 + desired_gwy + def_polled + def_ack_level + def_rep_or_ind + def_msg_or_ind + def_priority + def_msg_body_type + def_serv_type + gwy_search_mode
        msgtosend = msgtosend + fletcher_crc(msgtosend)
        self._protected_serial_write(msgtosend)
        self.logger.debug("ConfigurationCommand packet sent: %s" % ''.join('%02X ' % ord(x) for x in msgtosend))
    
    def SC_sndCommunicationCommand(self, retry_count, type_code, value_byte_0 , value_byte_1 , value_byte_2 , value_byte_3, gwy_id):
        """ 
        Sends a Communication Command formed with the values passed in parameters.
        """
        msgtosend = DTE_HEADER + COM_PKT_TYPE + COM_SIZE + retry_count + type_code + value_byte_0 + value_byte_1 + value_byte_2 + value_byte_3 + gwy_id
        msgtosend = msgtosend + fletcher_crc(msgtosend)
        self._protected_serial_write(msgtosend)
        self.logger.debug("CommunicationCommand packet sent: %s" % ''.join('%02X ' % ord(x) for x in msgtosend))
    
    def SC_sndGetParameter(self, retry_count, parameter_num):
        """ 
        Sends a Get Parameter that asks for the value of a precise parameter.
        """
        msgtosend = DTE_HEADER + GETPARAM_PKT_TYPE + GETPAR_SIZE + retry_count + parameter_num
        msgtosend = msgtosend + fletcher_crc(msgtosend)
        self._protected_serial_write(msgtosend)
        self.logger.debug("GetParameter packet sent: %s" % ''.join('%02X ' % ord(x) for x in msgtosend))
        
    def SC_sndSatusRequest(self):
        """
        Asks for the Status of the m10. (See the parsing Status_pkt function for more details on the return).
        """
        self.SC_sndCommunicationCommand(retry_count='\x00', type_code=RQ_STATUS_PKT,
                                         value_byte_0='\x00', value_byte_1='\x00',
                                         value_byte_2='\x00', value_byte_3='\x00',
                                         gwy_id=GW_EUROPE)   
        
    def SC_sndDefaultReport(self, retry_count, mha_ref_num, data):
        msgtosend = DTE_HEADER + SC_DEFREPORT_PKT_TYPE + DEF_REP_SIZE + retry_count + mha_ref_num + data
        msgtosend = msgtosend + fletcher_crc(msgtosend)
        self._protected_serial_write(msgtosend)
        
    def SC_sndReport(self, retry_count, gwy_id, polled, serv_type, or_ind, mha_ref_num, data):
        msgtosend = DTE_HEADER + SC_REPORT_PKT_TYPE + REP_SIZE + retry_count + gwy_id + polled + serv_type + or_ind + mha_ref_num + data
        msgtosend = msgtosend + fletcher_crc(msgtosend)
        self._protected_serial_write(msgtosend)
    
    def SC_sndDefaultMessage(self, data, retry_count=0, mha_ref_num=1):
        """
        Sends data in a defaultMessage packet, a shorten Message using m10 configuration parameters.
        see funct : SC_sndConfigurationCommand
        """
        retry_count_byte = chr(retry_count)
        mha_ref_num_byte = chr(mha_ref_num)
        encoded_length = encode_size(8 + len(data))
        msgtosend = DTE_HEADER + SC_DEFMSG_PKT_TYPE + encoded_length + retry_count_byte + mha_ref_num_byte + data
        msgtosend = msgtosend + fletcher_crc(msgtosend)
        self.logger.debug ("Message to send: %s" % ''.join('%02X ' % ord(x) for x in msgtosend))
        self._protected_serial_write(msgtosend)
        time.sleep(0.1) #time to process the sending action   
        
    def SC_sndMessage(self,
                      message,
                      rcpnt_addr=None,
                      subject=None,
                      retry_count=0,
                      gwy_id=None,
                      polled_byte=None,
                      ack_level_byte=None,
                      priority_byte=None,
                      mha_ref_num=None,
                      LLAck_wait_timeout=None):
        """
        Sends data in a Message packet. 
        If some parameters are not given, they will be set to their default values.
        (initial values, or values set by a SC_Set_Library_Default_Settings action.
        """
        retry_count_byte = chr(retry_count)
        if not rcpnt_addr:
            rcpnt_addr_byte = self._def_msg_or_ind
        if not gwy_id:
            gwy_id_byte = self._desired_gateway
            
        if not polled_byte:
            polled_byte = self._def_polled    
        if not ack_level_byte:
            ack_level_byte = self._def_ack_level 
        if not priority_byte:
            priority_byte = self._def_priority   
            
            
        rcpnt_quan_byte = '\x01'
 
        msg_body_type_byte = '\x00'
        data_type_byte = '\x05'
        
        
        if mha_ref_num:
            mha_ref_num_byte = chr(mha_ref_num)
        else:
            mha_ref_num_byte = '\x01'
        
        
        if subject:
            subject_ind_byte = '\x01'
            encoded_subject = subject + '\x00'
        else: 
            subject_ind_byte = '\x00'
            
        message_payload = \
            retry_count_byte + \
            gwy_id_byte + \
            polled_byte + \
            ack_level_byte + \
            priority_byte + \
            msg_body_type_byte + \
            mha_ref_num_byte + \
            rcpnt_quan_byte + \
            subject_ind_byte + \
            rcpnt_addr_byte
        if subject:
            message_payload = message_payload + encoded_subject
        message_payload += data_type_byte + message

        length = 6 + len (message_payload)
        encoded_length = encode_size(length)
        
        msgtosend = DTE_HEADER + SC_MSG_PKT_TYPE + encoded_length + message_payload
        msgtosend = msgtosend + fletcher_crc(msgtosend)
        self.logger.debug ("Message to send: %s" % ''.join('%02X ' % ord(x) for x in msgtosend))
        self._protected_serial_write(msgtosend)
        
        if(LLAck_wait_timeout):
            m10_full_packet = self._Rcv_m10_full_packet(LLAck_wait_timeout)
            if(not m10_full_packet):   
                self.logger.debug ("Message sent but no LLAck")
            else:
                if(is_a_LLA_PKT_TYPE(m10_full_packet)):
                    return self._check_LLAck_statusCode(m10_full_packet)
            return False
        else:
            return True    
    
    
    """
    RECEIVE FUNCTIONS
    """     
    def Rcv_structured_message(self, timeout, do_ack=True):
        """
        Returns a tuple containing the packet type and the result of the associated parsing method.
        If there is nothing to read, returns None,None.
        """
        m10_full_packet = self._Rcv_m10_full_packet(timeout, do_ack)
        if (m10_full_packet):
            return self._bin_packet_to_structured_message(m10_full_packet)
        return None, None

    
    def _Rcv_m10_full_packet(self, timeout, do_ack=True):   
        """
        Reads the serial port and returns a packet.
        If there is nothing to read, returns None.
        """ 
        self._ser.setTimeout(timeout)
        packet_header_byte = self._ser.read(1)
        if (len(packet_header_byte) != 1):
            return None
        if(packet_header_byte != SC_HEADER):
            return None
        self._ser.setTimeout(TIMEOUT_SERIALPORT_RESPONSE)
        header_trailer = self._ser.read(3)
        if len(header_trailer) != 3:
            self.logger.critical("Incomplete header received")
            return None   
        header = packet_header_byte + header_trailer
        
        packet_size = decode_size(header[2], header[3])
        packet_trailer = self._ser.read(packet_size - 4)

        if len(packet_trailer) != (packet_size - 4):
            self.logger.critical("Incomplete packet trailer received")
            return None 
        
        final_message = header + packet_trailer
        self.logger.debug("Received packet: %s" % ''.join('%02X ' % ord(x) for x in final_message))
        if(do_ack):
            if not is_a_LLA_PKT_TYPE(final_message):
                self.SC_sndLinkLevelAck(NO_ERROR_CODE)
        return final_message     
    
    def _bin_packet_to_structured_message(self, final_message):
        """
        Transforms the packet passed in arguments and parses it with the function 
        associated to its type.
        It returns a tuple composed by the packet type and a structured response.
        If the packet type is not recognized, it returns the packet type UNKNOWN_PKT_TYPE.
        """
        packet_type = get_pkt_hex_code(final_message)
        if packet_type == LLA_PKT_TYPE :
            self.logger.debug("LLA_PKT_TYPE") 
            return LLA_PKT_TYPE, self._check_LLAck_statusCode(final_message)   
        elif packet_type == SYS_PKT_TYPE :
            self.logger.debug("SYS_PKT_TYPE")
            return SYS_PKT_TYPE, None
        elif packet_type == STATUS_PKT_TYPE :
            self.logger.debug("STATUS_PKT_TYPE")
            return STATUS_PKT_TYPE, self._parse_STATUS_PKT_TYPE(final_message)
        elif packet_type == SYSREP_PKT_TYPE :
            self.logger.debug("SYSREP_PKT_TYPE")
            return SYSREP_PKT_TYPE, None
        elif packet_type == SC_TERMMSG_PKT_TYPE :
            self.logger.debug("SC_TERMMSG_PKT_TYPE")
            self._clear_SCTMsg_Queue()
            return SC_TERMMSG_PKT_TYPE, self._parse_SC_TERMMSG_PKT_TYPE(final_message)
        elif packet_type == SC_TERMCMD_PKT_TYPE : 
            self.logger.debug("SC_TERM_USRCMD_PKT_TYPE")
            return SC_TERMCMD_PKT_TYPE, None
        elif packet_type == SC_TERMGRAM_PKT_TYPE : 
            self.logger.debug("SC_TERMGRAM_PKT_TYPE")
            return SC_TERMGRAM_PKT_TYPE, None
        elif packet_type == POSSTATUS_PKT_TYPE : 
            self.logger.debug("POSSTATUS_PKT_TYPE")
            return POSSTATUS_PKT_TYPE, None
        elif packet_type == PARAMREP_PKT_TYPE : 
            self.logger.debug("PARAMREP_PKT_TYPE")
            return PARAMREP_PKT_TYPE, None
        else:
            self.logger.critical("Unexpected packet type : %s" % packet_type)
            return UNKNOWN_PKT_TYPE, None       
    
    def _parse_STATUS_PKT_TYPE(self, packet):
        """
        Extracts informations from a Status packet.
        Returns an array of strings containing the sorted and explained informations.
        """
        #The packet is supposed to be complete      
        packet_size = decode_size(packet[2], packet[3])
        retry_count = ord(packet[4])
        sc_state = packet[5]
        sc_diag_code = packet[6]
        active_mha_msg_ref = packet[7]
        sat_in_view = packet[8]  
        sat_in_view_string = SATELLITE_NUM_TO_NAME.get(sat_in_view, "Satellite not known, please add it : %02X " % ord(sat_in_view))
      
        gwy_quan = ord(packet[9])
        i = 0
        gwy = []
        for i in range(gwy_quan):
            gwy_id = ord(packet[10 + 2 * i])
            min_pri_gwy = ord(packet[11 + 2 * i])
            gwy.append((gwy_id, min_pri_gwy))
        i = gwy_quan  #i is given back with the value gwy_quan-1
        queued_ob_msgs = ord(packet[10 + 2 * i])
        queued_ib_msgs = ord(packet[11 + 2 * i])
        
        week_bytes = []
        week_bytes.append(packet[12 + 2 * i])
        week_bytes.append(packet[13 + 2 * i])
        
        time_bytes = []
        time_bytes.append(packet[14 + 2 * i])
        time_bytes.append(packet[15 + 2 * i])
        time_bytes.append(packet[16 + 2 * i])
        
        total_sats = ord(packet[17 + 2 * i])
        stored_sats = ord(packet[18 + 2 * i])
        check_errs = ord(packet[19 + 2 * i])
        reponse = []
        reponse.append("==============================")
        reponse.append("packet_type => STATUS_PKT_TYPE")
        reponse.append("packet_size => " + str(packet_size))
        reponse.append("retry_count => " + str(retry_count))
        reponse.append("sc_state => " + '%02X' % ord(sc_state))
        reponse.append("sc_diag_code => " + '%02X' % ord(sc_diag_code))
        reponse.append("active_mha_msg_ref => " + '%02X' % ord(active_mha_msg_ref))
        reponse.append("sat_in_view => " + sat_in_view_string)
        
        reponse.append("gwy_quan => " + str(gwy_quan))
        i = 0
        for g in gwy:
            reponse.append("gwy_id_" + str(i) + " => " + str(g[0]))
            reponse.append("min_pri_gwy" + str(i) + " => " + str(g[1]))
            i += 1
        reponse.append("queued_sc_terminated_msgs => " + str(queued_ob_msgs))
        reponse.append("queued_sc_originated_msgs => " + str(queued_ib_msgs))
        
        week_byte_string = ''.join('%02X ' % ord(x) for x in week_bytes)
        reponse.append("week_bytes => " + week_byte_string)
        time_byte_string = ''.join('%02X ' % ord(x) for x in time_bytes)
        reponse.append("time_bytes => " + time_byte_string)
        
        reponse.append("total_sats => " + str(total_sats))
        reponse.append("stored_sats => " + str(stored_sats))
        reponse.append("check_errs => " + str(check_errs))
        reponse.append("==============================")    
        return reponse
    
    def _parse_SC_TERMMSG_PKT_TYPE(self, full_sct_pkt):
        """
        Extracts informations from a SC terminated message packet.
        Returns a tuple containing the message extracted and the full packet.
        """
        #The packet is supposed to be complete        
        packet_size = decode_size(full_sct_pkt[2], full_sct_pkt[3])
        retry_count = ord(full_sct_pkt[4])
        gwy_id = ord(full_sct_pkt[5])
        subject_ind = ord(full_sct_pkt[6])
        msg_body_type = ord(full_sct_pkt[7])

            #TODO: implement other types cases
        or_quan = full_sct_pkt[8]
        unknown_1 = full_sct_pkt[9]
        if or_quan != '\x01':
            self.logger.critical("OR not supported")
            return
        if unknown_1 != '\x01':
            self.logger.critical("OR not supported")
            return
            #TODO: understand the OR and its uses
        if(subject_ind == 1):
            subj_title_start_index = 10   
            subj_title_end_index = full_sct_pkt.find('\x00', 11)
            if subj_title_end_index == -1:
                self.logger.critical("subj_title is empty but announced")
                subj_title = ""
                subj_title_end_index = subj_title_start_index
            else:
                subj_title = full_sct_pkt[subj_title_start_index: subj_title_end_index]
        else:
            subj_title = "no subj_title"
            subj_title_end_index = 10
        if msg_body_type == 0:
            #msg_body_data_type_index = subj_title_end_index + 1                UNUSED
            #msg_body_data_type = ord(full_sct_pkt[msg_body_data_type_index])   FOR THE MOMENT
            msg_body_start_index = subj_title_end_index + 1
            msg_body_end_index = packet_size - 5
        if msg_body_type == 1:
            msg_body_start_index = subj_title_end_index 
            msg_body_end_index = packet_size - 2
            
        msg_body = full_sct_pkt[msg_body_start_index: msg_body_end_index]

        self.logger.debug("==============================")
        self.logger.debug("packet_type => SC_TERMMSG_PKT_TYPE")
        self.logger.debug("packet_size => " + str(packet_size))
        self.logger.debug("retry_count => " + str(retry_count))
        self.logger.debug("gwy_id => " + str(gwy_id))
        self.logger.debug("subject_ind => " + str(subject_ind))
        self.logger.debug("msg_body_type => " + str(msg_body_type))
        self.logger.debug("or_quan => " + str(or_quan))
        self.logger.debug("subj_title => " + subj_title)
        self.logger.debug("msg_body => " + msg_body)
        self.logger.debug("==============================")
        
        return msg_body, full_sct_pkt

    def _parse_PARAMREP_PKT_TYPE(self, full_sct_pkt):
        pass
            
    def _check_LLAck_statusCode(self, final_message):
        """
        Checks the Ack value.
        If it is a known Ack value, it returns the Ack Code and loggs the associated message.
        Else, it returns None and loggs an error.
        """
        if len(final_message) <= 5:
            self.logger.error("Message is not a correct LLAck")
            return None
        code = final_message[4]
        if code in LLA_CODE_TO_HUMAN:   
            self.logger.debug("Found LLAck code :%s" % LLA_CODE_TO_HUMAN[code])
            return code 
        else:
            self.logger.error("LLA code not recognized")
            return None 
    
     
            
    def init_module_logger(self):
    
        # TODO: switch to std logging with config file / http://g-polarion-pangoov4/polarion/redirect/project/PANGOO_PF_DEV/workitem?id=PF-91
        # ... logging.config.fileConfig(logging_config_file)
    
        # logging setup
        if sys.platform.startswith('digi'):
            logging_file_prefix = 'WEB/python/'
        else:
            logging_file_prefix = ''
        
        self.logger = logging.getLogger("m10_sc_api")
        fmt = logging.Formatter("%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s", "%Y-%m-%d %H:%M:%S")
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)
         
        handler = logutils.SmartHandler(filename=logging_file_prefix + 'log_m10_sc_api.txt', buffer_size=50, flush_level=logging.INFO, flush_window=300)
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)        
        
""" END OF CLASS
"""
    
if __name__ == '__main__':
    pass

