'''
$Id: m10_sc_api_main_test.py 6725 2011-09-26 13:33:16Z vmpx4526 $
'''

import m10_sc_api
import time
import logging

import serial
from custom_lib import logutils
from custom_lib.orbcomm_lib.m10_sc_api import is_a_LLA_PKT_TYPE

SC_ACK = '\x05\x01\x07\x00\x00\xC1\x32'
SERIAL_PORT = 'COM2'
BAUDRATE = '4800'
class FooClass:
       
    def _Connx(self):
        connexion = m10_sc_api.m10_sc_api()
        connexion.SC_COM_connect(SERIAL_PORT, BAUDRATE)
        return connexion
    
    def _messageLoop(self, serialCon, Msg_nb):
        for i in range(0, Msg_nb):
            time.sleep(0.1)
            serialCon.SC_sndDefaultMessage("11:08 11-08-11  message test : %c" % i)
            
            final_message = serialCon.Rcv_structured_message(2)
            if final_message == SC_ACK:
                serialCon.logger.debug('Received valid Link level acknowledgment...')
            else :
                serialCon.logger.error('not a valid ack')
                
    def _messagePoll (self, serialCon, ptimeout):
        i = 0
        while (i < ptimeout):
            i += 1
            random_pkt = serialCon.Rcv_structured_message(30)
            if random_pkt :
                serialCon.logger.debug("Received SC-Term Message: %s" % ''.join('%02X ' % ord(x) for x in random_pkt))
            else : 
                serialCon.logger.debug("timeout 30sec, loop %i " % i)
                
    
                
def test_receive_loop():
    _do_modem_reset = True
    A = FooClass()
    con = A._Connx()
    con.logger.setLevel(logging.DEBUG)

    if _do_modem_reset:
        con.logger.debug('sleep over - reseting port')
        con.SC_Reset()   
        con.logger.debug('port restarted')
    
    while (True):
        final_message = con.Rcv_m10_full_packet(120)
        if (final_message):
            if (not is_a_LLA_PKT_TYPE(final_message)):
                treated_message = con.Treat_SC_TERMMSG_PKT(final_message)
                if(treated_message):
                    con.logger.debug(treated_message)
            else:
                con.logger.debug("received a LLA_PKT_TYPE")
        else:
            con.logger.debug("received crap")
        con.logger.debug('sleep over - looping for 120 sec')
        
               
def test_send_scenario():
    _do_modem_reset = False
    
    A = FooClass()
    con = A._Connx()
    
    con.logger.setLevel(logging.DEBUG)
    
    #A._messageLoop(con, 3)
    #A._messagePoll(con, 3)
    con.SC_sndMessage("1430000116083103BA8190020000002D00000000")
#    con.SC_sndMessage("This message is a complete message. Sent at 13h52, the 12-08-11", subject= "I am trying to send the first complete message")
#    con.SC_sndGetParameter(pkt_seq_num_byte='\x00', parameter_num_byte='\x12')
#    packet_type, final_message = con.Rcv_structured_message(10)
#    con.logger.debug('sleep over - looping for 10 sec')
#    
#    con.SC_sndGetParameter(pkt_seq_num_byte='\x00', parameter_num_byte='\x14')
#    packet_type, final_message = con.Rcv_structured_message(10)
#    con.logger.debug('sleep over - looping for 10 sec')
#    
#    con.SC_sndGetParameter(pkt_seq_num_byte='\x00', parameter_num_byte='\x16')
#    packet_type, final_message = con.Rcv_structured_message(10)
#    con.logger.debug('sleep over - looping for 10 sec')
    
    if _do_modem_reset:
        con.logger.debug('sleep over - reseting port')
        con.SC_Reset()   
        con.logger.debug('port restarted')       
    con.ser.close()
        

if __name__ == "__main__": 
#    test_receive_loop()
    test_send_scenario()
