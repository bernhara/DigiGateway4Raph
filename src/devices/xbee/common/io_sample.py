############################################################################
#                                                                          #
# Copyright (c)2008, 2009, Digi International (Digi). All Rights Reserved. #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,  and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. Contact Product Management, Digi International, Inc., 11001 Bren   #
# Road East, Minnetonka, MN, +1 952-912-3444, for commercial licensing     #
# opportunities for non-Digi products.                                     #
#                                                                          #
# DIGI SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED   #
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A          #
# PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, #
# PROVIDED HEREUNDER IS PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND. #
# DIGI HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES,         #
# ENHANCEMENTS, OR MODIFICATIONS.                                          #
#                                                                          #
# IN NO EVENT SHALL DIGI BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,      #
# SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS,   #
# ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF   #
# DIGI HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.                #
#                                                                          #
############################################################################


"""\
    A simple parser for XBee I/O samples.

    Most XBee devices support retrieving of both Analog and Digital
    samples from the device.
    This is done by issuing the DDO 'IS' command, in which the unit
    will pack its AIO and DIO values into the response.

    This file offers a helper function to decode the response for the user.

"""

import struct

_IO_MAP = {
          'AD0':  0, 'DIO0': 0, 'D0':   0,
                          
          'AD1':  1, 'DIO1': 1, 'D1':   1,
          
          'AD2':  2, 'DIO2': 2, 'D2':   2,
          
          'AD3':  3, 'DIO3': 3, 'D3':   3, 
          
          'AD4':  4, 'DIO4': 4, 'D4':   4, 
          
          'AD5':   5, 'ASSOC': 5, 'DIO5':  5, 'D5':    5,
          
          'AD6':   6, 'RTS':   6, 'DIO6':  6, 'D6':    6,
          
          'CTS':   7, 'DIO7':  7, 'D7':    7,
          
          'DTR':   8, 'SLEEP_RQ': 8, 'DIO8':     8, 'D8':       8,
          
          'ON':    9, 'SLEEP': 9, 'DIO9':  9, 'D9':    9,
          
          'PWM0':  10, 'RSSI':  10, 'DIO10': 10, 'P0':    10,
          
          'PWM':   11, 'DIO11': 11, 'P1':    11,
          
          'DIO12': 12, 'P2':    12,

          }

def parse_is(data):
    """\
        Parse the response of the XBee DDO 'IS' command.

        Returns a dictionary of values keyed with each DIO or AD channel found.
    """

    ## We need to differentiate between series 1 and series 2 formats
    ## The series 1 format should always return a 'odd' byte count eg 7, 9, 11 or 13 bytes
    ## The series 2 format should always return a 'even' byte count eg, 8, 10, 12 or 14 bytes
    ## So we mod 2 the length, 0 is series 2, 1 is series 1. 
    
    if len(data) % 2 == 0:
        sets, datamask, analogmask = struct.unpack("!BHB", data[:4])
        data = data[4:]
        
    else:        
        sets, mask = struct.unpack("!BH", data[:3])
        data = data[3:]
        datamask = mask % 512 # Move the first 9 bits into a seperate mask
        analogmask  = mask >> 9 #Move the last 7 bits into a seperate mask
        
    retdir = {}

    if datamask:
        datavals = struct.unpack("!H", data[:2])[0]
        data = data[2:]

        currentDI = 0
        while datamask:
            if datamask & 1:
                retdir["DIO%d" % currentDI] = bool(datavals & 1)
            datamask >>= 1
            datavals >>= 1
            currentDI += 1

    currentAI = 0    
    while analogmask:
        if analogmask & 1:
            
            aval = struct.unpack("!H", data[:2])[0]
            data = data[2:]

            retdir["AD%d" % currentAI] = aval
        analogmask >>= 1
        currentAI += 1
    
    
    for key in _IO_MAP.keys():  # for every key in _IO_MAP  
        if retdir.has_key(key): # if the key is in the retdir
            for match_key in _IO_MAP.keys():  #for every OTHER key in _IO_MAP
                #If it points to the same value (pin)
                #Create a new key with the old key's value
                if _IO_MAP[match_key] == _IO_MAP[key]: 
                    retdir[match_key] = retdir[key]  
                                                     
    return retdir

def sample_to_mv(sample):
    """\
        Converts a raw A/D sample to mV (uncalibrated).

    """

    return sample * 1200.0 / 1023


# TEST code
if __name__ == "__main__":
    format = "!BHBHHHHH"
    s = struct.pack(format, 0x01, 0xfff0, 0x0f, 0xffff, 0xffff, 0xffff, 0xffff, 0xffff)    
    d = parse_is(s)
    
    keys = d.keys()
    keys.sort()
    for key in keys:
        print key, " = ", d[key]
            
