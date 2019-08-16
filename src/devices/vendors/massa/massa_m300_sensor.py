############################################################################
#                                                                          #
# Copyright (c)2008-2010, Digi International (Digi). All Rights Reserved.  #
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
Massa M-300 Sensor Utilities

Usage/Wiring information:
    M-300 Brown --> RS-485 Port B (+)
    M-300 Green --> RS-485 Port A (-)
    M-300 Black --> Signal ground (GND)
    M-300 Red   --> Power (+12VDC or +24VDC)
    M-300 White --> Not Connected (0-10v output)

To use multi-drop, the sensor "ID Tag" must be set correctly before field
installation. This value defaults to one (1), so to have 4 M300 on the same
multi-drop you must set their ID Tags to 1, 2, 3, and 4 respectively.
This is done using the Massa M300 software tool before field installation.
"""

# imports

# constants

# exception classes

# interface functions

# classes
class MassaM300_Sensor(object):

    STRENGTH_TABLE = { 0x00:0, 0x10:25, 0x20:50, 0x30:75, 0x40:100 }

    CHAN_ERR = 0
    CHAN_STRN = 1
    CHAN_EFLG = 2
    CHAN_RNG = 3
    CHAN_TMP = 4

    MODE_SINGLE = 0
    MODE_MULTIDROP = 1

    def __init__(self, id_tag=1, name=None):
        self.set_id_tag(id_tag)
        self.chan_name = None
        self.set_name(name)

        ## local variables, save these requests to avoid memory thrashing
        self.__req1 = None
        self.__req3 = None

        ## allow simple offset calibration
        self.__range_offset = 0.0
        self.__temperature_offset = 0.0

        self.__mode = self.MODE_SINGLE

        return

    def calc_bcc(self, data):
        '''calc or check the BCC'''
        if len(data) >= 5 and len(data) <= 6:
            # then is valid length
            return (ord(data[0]) + ord(data[1]) + ord(data[2]) + ord(data[3]) + \
                    ord(data[4])) & 0xFF
        # else return error of None
        return None

    def get_id_tag(self):
        return self.__id

    def get_id_tag_for_requests(self):
        if self.__mode == self.MODE_MULTIDROP:
            return self.__id
        else: # for single, just 'broadcast'
            return 0

    def set_id_tag(self, id_tag):
        if id_tag < 0 or id_tag > 32:
            raise ValueError, 'Massa M300 ID tag out of range 1-32'
        self.__id = id_tag
        return

    def set_mode_multidrop(self, mdrop=False):

        # save the names to avoid thrashing strings
        if self.chan_name is not None: del self.chan_name

        if mdrop:
            # then multi-drop is true
            self.__mode = self.MODE_MULTIDROP
            self.chan_name = ['%s_error' % self.__name, '%s_strength' % self.__name, \
                   '%s_sensor_error' % self.__name, '%s_range' % self.__name, \
                   '%s_temperature' % self.__name]

        else: # is single device
            self.__mode = self.MODE_SINGLE
            self.chan_name = ['error', 'strength', 'sensor_error', 'range',
                    'temperature']
        return

    def get_name(self):
        return self.__name

    def set_name(self, name=None):

        if name is None:
            # if no name, use digits like 01, 02, 03
            self.__name = '%02d' % self.__id
        else:
            self.__name = name

        return

    ## create the requests to send
    def req_software_trigger_1(self):
        '''Return the Software Trigger request(#1)'''
        id = self.get_id_tag_for_requests()
        if self.__req1 is None:
            self.__req1 = '\xAA' + chr(id) + '\x01\x00\x00' + \
                           chr((171 + id) % 256)
        return self.__req1

    def req_status_3(self):
        '''Return the Status request(#3)'''
        id = self.get_id_tag_for_requests()
        if self.__req3 is None:
            self.__req3 = '\xAA' + chr(id) + '\x03\x00\x00' + \
                           chr((173 + id) % 256)
        return self.__req3

    def req_write_103(self, offset, data):
        '''Create the correct data write request(#103)'''
        # we don't save this one - create always

        # offset should be between 21 and 104

        # data is any byte
        id = self.get_id_tag_for_requests()
        req103 = '\xAA' + chr(id) + '\x67' +\
                chr(offset) + chr(data)
        req103 += chr(self.calc_bcc(req103))
        return req103

    def req_read_104(self, offset):
        '''Create the correct data read request(#104)'''
        # we don't save this one - create always

        # offset should be between 21 and 104
        id = self.get_id_tag_for_requests()
        req104 = '\xAA' + chr(id) + '\x68' +\
                chr(offset) + '\x00'
        req104 += chr(self.calc_bcc(req104))
        return req104

    def req_reboot_119(self):
        '''Return the Reboot request(#119)'''
        id = self.get_id_tag_for_requests()
        req119 = '\xAA' + chr(id) +\
                '\x77\x00\x00' + chr((0x21 + id) % 256)
        return req119

    def req_read_error(self):
        '''Create the correct data read request(#104) to read error'''
        return self.req_read_104(104)

    ## process the indications received
    def check_ind(self, data, use_id=0):

        # check the response length, must be 6
        if len(data) != 6:
            return { 'error':
                     'F1: Invalid response length of %d bytes' %\
                     len(data) }

        # check the sensor id tag, if use_id != 0
        if use_id != 0:
            if use_id == -1:
                # then use 'my id'
                use_id = self.__id
            # else use the id passed in

            if use_id != ord(data[0]):
                return { 'error':
                         'F2: Unexpected ID Tag, expect %d, saw %d' % \
                         (ord(data[0]), use_id) }
            # else were asked to NOT check this

        # check the BCC
        bcc = self.calc_bcc(data)
        if bcc != ord(data[5]):
            return { 'error':
                     'Bad Checksum, calc %02X, saw %02X' % \
                     (bcc, ord(data[5])) }
        # else BCC is as expected

        return {}

    # def ind_software_trigger_1(self, data): - there is NO response

    def ind_status_3(self, data, use_id=-1):

        # confirm the form and BCC is correct
        dct = self.check_ind(data, use_id)
        if dct.has_key('error'):
            return dct

        ## Parse the Response Code
        #  Strength as 0-100%
        x = ord(data[1])
        strength = self.STRENGTH_TABLE.get((x & 0xf0), None)
        if strength is None:
            return { 'error':'I1: Malformed Response Code'}

        range = ((ord(data[3])<<8) | ord(data[2])) / 128.0
        if self.__range_offset:
            range += self.__range_offset

        temperature = (ord(data[4]) * 0.48876) - 50.0
        if self.__temperature_offset:
            temperature += self.__temperature_offset

        dct.update({'strength':strength,
                    'target_detected':bool(x & 0x08),
                    'sensor_error':bool(x & 0x01),
                    'range':round(range,2),
                    'temperature':round(temperature, 2),
                    })

        return dct

    # def ind_write_103(self, data): - there is NO response

    def ind_read_104(self, data, use_id=-1):

        # confirm the form and BCC is correct
        # confirm the form and BCC is correct
        dct = self.check_ind(data, use_id)
        if dct.has_key('error'):
            return dct

        # confirm Read Response Code
        if data[1] != 0x80:
            print '%s Invalid response code' % (self.__name)
            return False

        val = ord(data[3])
        dct = { 'offset':ord(data[2]), 'byte':val,
                'word':val + (ord(data[4])<<8) }

        print '%s Read memory %d was %d (0x%02X)' % \
              (self.__name, dct['offset'], val, val)
        return dct

    def chn_name_error(self):
        return self.chan_name[self.CHAN_ERR]

    def chn_name_strength(self):
        return self.chan_name[self.CHAN_STRN]

    def chn_name_error_flag(self):
        return self.chan_name[self.CHAN_EFLG]

    def chn_name_range(self):
        return self.chan_name[self.CHAN_RNG]

    def chn_name_temperature(self):
        return self.chan_name[self.CHAN_TMP]
