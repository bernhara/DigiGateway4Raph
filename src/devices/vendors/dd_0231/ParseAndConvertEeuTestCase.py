'''
Created on Feb 21, 2011

@author: thom
'''
import unittest
import WirelessPacketParser

class Test(unittest.TestCase):

    def runTest(self):
        parser = WirelessPacketParser.WirelessPacketParser()
        #test converting a straight number(should do nothing)
        val1 = 42
        val2 = parser.parseAndConvertEeu(val1)
        assert val1 == val2, 'Failed to convert with number only'
        #test converting degress Celsius
        val1 = "42,63"
        val2 = parser.parseAndConvertEeu(val1)
        assert 1416 == val2, 'Failed to convert engineering units:' + str(val2)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()