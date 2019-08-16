'''
Created on Feb 21, 2011

@author: thom
'''
import unittest
import WirelessPacketParser

class Test(unittest.TestCase):

    def runTest(self):
        parser = WirelessPacketParser.WirelessPacketParser()
        bytes = (0, 9, 74)
        val = parser.convertBytesToInt(bytes)
        assert val == 2378, 'incorrect conversion:' + str(val)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()