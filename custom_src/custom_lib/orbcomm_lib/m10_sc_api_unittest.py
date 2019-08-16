'''
$Id: m10_sc_api_unittest.py 6490 2011-09-15 13:14:38Z vmpx4526 $
'''

import m10_sc_api 
import unittest

class TestSequenceFunctions(unittest.TestCase):


    def setUp(self):
        pass


    def tearDown(self):
        pass
    
    def _encode_decode (self, int_size, str_size):
        """ Checks if the str_size is the encoded version of int_size.
        """
        str_result = m10_sc_api.encode_size (int_size)
        self.assertEqual (str_result, str_size)
        
        int_result = m10_sc_api.decode_size(str_size[0], str_size[1])
        self.assertEqual (int_result, int_size)        

    def test_encode_decode_0(self):
        self._encode_decode(0, '\x00\x00')
        
    def test_encode_decode_1(self):
        self._encode_decode(1, '\x01\x00')
        
    def test_encode_decode_255(self):
        self._encode_decode(255, '\xFF\x00')
        
    def test_encode_decode_256(self):
        self._encode_decode(256, '\x00\x01')
        
    def test_parse_SC_TERMMSG_PKT_TYPE(self):
        packet = ['\x05', '\x0C', '\x2A', '\x00',
                  '\x00', '\x78', '\x01', '\x00',
                  '\x01', '\x01', '\x6D', '\x79',
                  '\x5F', '\x73', '\x75', '\x62',
                  '\x6A', '\x65', '\x63', '\x74',
                  '\x00', '\x05', '\x31', '\x37',
                  '\x74', '\x65', '\x73', '\x74',
                  '\x5F', '\x6D', '\x73', '\x67',
                  '\x5F', '\x62', '\x6F', '\x64',
                  '\x79', '\x0D', '\x0A', '\x0A',
                  '\x88', '\x8C']
        string_packet = ''.join(packet)
        m10 = m10_sc_api.m10_sc_api('COM1')
        #FIXME:remove the port arg in m10_sc_api creation
        m10.parse_SC_TERMMSG_PKT_TYPE(string_packet)
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()

