############################################################################
#                                                                          #
# Copyright (c)2008-2012, Digi International (Digi). All Rights Reserved.  #
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

r"""\
DIA XBee Serial Terminal Driver

To Use:

        Issue web services channel_set call to send data to serial device
                 <data><channel_set name="device_name.write" value="string to send"/></data>

        Issue web services channel_get (or channel_dump) call to read serial device
                 <data><channel_get name="device_name.read"/></data>
                 or
                 <data><channel_dump/></data>

Settings:
---------

* **hexadecimal:** Optional parameter. Default is False.
  If True, assumes WRITE channel data is well-formed hexadecimal string,
  which is converted to binary for serial transmission, plus any serial
  data received is converted to a hexadecimal string before updating to
  the READ channel. If False, makes no change to READ/WRITE channel data.

  An example string is "01030000000AC5CD", which is a Modbus/RTU poll
  to Slave #1 to read 10 holding registers starting at 4x00001

  Note: attempting to upload binary data to Device Cloud with hexadecimal set to
  False will have unpredictable results.

* **eoln:** Optional parameter. Default is None
  A string which is appended to every message sent by serial, and stripped
  from the end of every message received by serial.  The 'eoln' value being
  detected will also cause an end-of-message (over-rides char_timeout)
  Only the escape sequences \r, \n and \xXX are handled, with 'XX' being
  exactly 2 hexadecimal characters only.  All other characters are left
  as is, so '<*\r' will treat the 3 bytes '<', '*' and '\r' as EOLN.

  Note: the EOLN pattern is stripped from incoming serial data. If the EOLN
  pattern is required, leave it None and use 'char_timeout' to detect
  end of message.

* **char_timeout:** Optional parameter. Default is 1.0 second
  Since incoming data will generally be 'fragmented' due to either slow human
  finger-typing or Xbee max packet sizes, this driver uses a simple idle
  timer to detect 'end-of-message'.  The value can be set to anything
  0.25 seconds or higher.  Setting to 0.0 disables this feature, causing
  the READ channel to be rewritten with every incoming data sample.

EXAMPLE YML
============
  - name: modbus
    driver: devices.xbee.xbee_devices.xbee_serial_terminal:XBeeSerialTerminal
    settings:
        xbee_device_manager: zigbee_device_manager
        extended_address: "00:13:a2:00:40:6c:ae:55!"
        baudrate: 38400
        parity: None
        hexadecimal: True

  - name: term
    driver: devices.xbee.xbee_devices.xbee_serial_terminal:XBeeSerialTerminal
    settings:
        xbee_device_manager: zigbee_device_manager
        extended_address: "00:13:a2:00:40:6c:ae:55!"
        eoln: '\r'

"""

## imports
import types
import traceback
import binascii
import threading

# this is our base/parent class
from devices.xbee.xbee_devices.xbee_serial import XBeeSerial

# we need this to add/manage settings in this device
from settings.settings_base import SettingsBase, Setting

# we need this to add/manage channels in this device
from channels.channel_source_device_property import *

# constants

# exception classes

# interface functions


# classes
class XBeeSerialTerminal(XBeeSerial):
    """\
        This class extends one of our base classes and is intended as an
        example of a concrete, example implementation, but it is not itself
        meant to be included as part of our developer API. Please consult the
        base class documentation for the API and the source code for this file
        for an example implementation.

    """

    # here are the setting defaults
    DEF_HEXDEC = False
    DEF_EOLN = None
    DEF_CHARTOUT = 2.0

    # a sanity value to prevent an infinite rcv_buffer creation
    DEF_MAX_READ = 1000

    def __init__(self, name, core_services):

        ## These will be created by XBeeSerial
        # self._name = name
        # self._core = core_services
        # self._tracer = get_tracer(name)
        # self._xbee_manager = None
        # self._extended_address = None

        # local variables used for packing of multiple rcv packets
        self.rcv_buffer = ''
        self.__chr_timer = None

        # create a resource semaphore for receiving and timeout
        self.__rcv_lock = threading.Lock()

        # local variables used for append/strip EOLN
        self.__eoln_save = None
        self._eoln = None

        ## Settings Table Definition:
        settings_list = [
            # if True, then data is converted from hexadecimal to binary
            # if False, then data is assumed ASCII (or raw)
            Setting(
                name='hexadecimal', type=bool, required=False,
                default_value=self.DEF_HEXDEC),

            # add/strip an end-of-line sequence
            # set to None to disable
            # else likely set to '\r', '\n', or '\r\n'
            # other escapes need to be of the form '\xXX', which XX is
            # exactly 2 hexadecimal bytes. Example: '\x0D' is '\r'
            Setting(
                name='eoln', type=str, required=False,
                default_value=self.DEF_EOLN),

            # character timeout to 'pack' data into a single receive
            Setting(
                name='char_timeout', type=float, required=False,
                default_value=self.DEF_CHARTOUT,
                verify_function=lambda x: x == 0.0 or x >= 0.25),
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="read", type=str,
                initial=Sample(timestamp=0, unit="", value=""),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="write", type=str,
                initial=Sample(timestamp=0, unit="", value=""),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.serial_write),
        ]

        ## Initialize the XBeeSerial interface:
        XBeeSerial.__init__(self, name, core_services,
                                settings_list, property_list)

        self._tracer.calls("XBeeSerialTerminal.__init__()")

    def read_callback(self, buf):
        # we are over-writing XBeeSerial.read_callback()
        self.serial_read(buf)

    # not using XBeeSerial.sample_indication(io_sample)

    # not using XBeeSerial.running_indication()

    # def apply_settings(): uses XBeeSerial.apply_settings()


    def start(self):

        # save the Async Scheduler for our character timeout
        self.__sched = self._core.get_service("scheduler")

        # you could add other ddo settings here

        return XBeeSerial.start(self)


    # def stop(): uses XBeeSerial.stop()


    ## Locally defined functions:

    def serial_read(self, buf):

        # this routine will run as part of the XBee manager thread

        # semaphore to prevent a receive timeout from affecting
        # self.rcv_buffer during a receive/append operation
        self.__rcv_lock.acquire()

        if self.__chr_timer is None:
            # we are starting a new buffer or have no chr-tout
            self.rcv_buffer = buf

        else:
            # else, timer is running, we are 'packing' more data
            try:
                # delete old timeout - restart below with full new time
                self.__sched.cancel(self.__chr_timer)
            except:
                # print traceback.format_exc()
                pass

            self.rcv_buffer += buf

        self.__rcv_lock.release()
        # after release, a time-out 'could' occur, but we've deleted it

        # we want the 'slow' trace output to be outside our semaphore
        if self.__chr_timer is None:
            self._tracer.debug("Start Data: %s", buf)
        else:
            self._tracer.debug("More Data: %s", buf)

        eoln = self.get_eoln()
        if eoln is not None and self.rcv_buffer.endswith(eoln):
            # then treat as end-of-message
            self._tracer.debug("EOLN pattern was seen")
            self.serial_rcv_done()

        else:
            chrtout = SettingsBase.get_setting(self, "char_timeout")
            if chrtout == 0:
                # no timeout, so assume every 'receive' event is a complete
                # message - simulate the character timeout to end the buffer and
                # update the read channel
                self.serial_rcv_done()

            elif len(self.rcv_buffer) > self.DEF_MAX_READ:
                # hit our sanity-limit, simulate end-of-message
                self._tracer.debug("Hit the MAX buffer size of %d", self.DEF_MAX_READ)
                self.serial_rcv_done()

            else:
                # restart our timer-callback, saving as self.__chr_timer
                self._tracer.debug("Start char_tout for %0.2f sec", chrtout)
                self.__chr_timer = self.__sched.schedule_after(chrtout,
                                                self.serial_rcv_done)

        return

    def serial_rcv_done(self):

        # if the timeout occured, this routine will run as part of the
        # ASync manager thread

        # semaphore to prevent data receive from affecting
        # self.rcv_buffer during a receive-done operation
        self.__rcv_lock.acquire()

        # this local var is either None already,
        # or we want it None because the timer called this routine
        self.__chr_timer = None

        # without the lock, data could (in theory) be appended to
        # self.rcv_buffer in between these 2 lines
        data = self.rcv_buffer
        self.rcv_buffer = ''

        self.__rcv_lock.release()
        # after release, new data will be treated as new buffer

        eoln = self.get_eoln()
        if eoln is not None and data.endswith(eoln):
            # then strip off the EOLN
            data = data[:-len(eoln)]

        if SettingsBase.get_setting(self, "hexadecimal"):
            # then convert from binary to hexadecimal
            data = binascii.hexlify(data)

        self._tracer.info("Read Data: %s", data)

        # Update DIA channel
        self.property_set("read", Sample(0, value=data, unit=""))


    def serial_write(self, data):

        # this routine will run as part of whatever method/thread was used
        # to SET the channel

        # Note: the SET action to a channel does NOT automatically
        # update the channel data.
        # If desired, the callback needs to do that manually
        self.property_set("write", data)

        if SettingsBase.get_setting(self, "hexadecimal"):
            # then convert from hexadecimal to binary
            data = binascii.unhexlify(data.value)
        else:
            # else for ASCII, handle as-is
            data = data.value

        self._tracer.info("Write Data: %s", data)

        eoln = self.get_eoln()
        if eoln is not None:
            # then append our desired EOLN
            data += eoln

        try:
            ret = self.write(data)
            if ret == False:
                raise Exception, "write failed"
        except:
            self._tracer.warning("Error writing data")


# internal functions & classes

    def get_eoln(self):
        eoln = SettingsBase.get_setting(self, "eoln")
        if eoln is None:
            return None

        if eoln != self.__eoln_save:
            # cache result to avoid repeat processing of escapes
            self.__eoln_save = eoln
            self._eoln = strip_escapes(eoln)
        return self._eoln

# since Digi NDS lacks the 'string_escape' codex, mimic partially here
def strip_escapes(st):
    x = st.find('\\')
    if x >= 0:
        # then we have at least one escape
        rs = []
        while x >= 0:
            # while more escape sequences
            rs.append(st[:x]) # save the string from before seq
            c = st[x+1]
            if c == 'r':
                # for '\r', append actual <carriage return> byte
                rs.append('\r')
                st = st[x+2:]
            elif c == 'n':
                # for '\n', append actual <new line> byte
                rs.append('\n')
                st = st[x+2:]
            elif c == 'x':
                # for '\xXX', append chr() of the 2 hexadecimal bytes XX
                rs.append(chr(int(st[x+2:x+4], 16)))
                st = st[x+4:]
            else:
                # otherwise just ignore, appending unhandled sequence
                rs.append('\\%c' % c)
                st = st[x+2:]
            x = st.find('\\')
        # note: we do this 'append' and 'join' to avoid creating
        # a lot of small temporary strings as we append bytes
        rs.append(st)
        st = "".join(rs)
    return st
