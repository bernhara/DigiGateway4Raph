############################################################################
#                                                                          #
# Copyright (c)2008-2011, Digi International (Digi). All Rights Reserved.  #
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
Massa M-300 Driver Connected to XBee 485 Adapter Driver

Supports a Massa M-300 device connected to a XBee 485 driver.  The following
Massa M-300 devices are supported:

    M-300/95 (min 12 in. / max. 180 in.)
    M-300/150 (min 7 in. / max. 96 in.)
    M-300/210 (min 4 in. / max. 50 in.)

Wiring information:

    M-300 Brown --> XBee 485 Pin 1 (485 Port B {+})
    M-300 Green --> XBee 485 Pin 2 (485 Port A {-})
    M-300 Black --> XBee 485 Pin 5 (GND)
    M-300 Red   --> XBee 485 Pin 6 (+12 DC)
    M-300 White --> Not Connected

XBee RS-485 DIP Switch Configuration:

    Pins 2, 3, 4 = ON (RS-485 Mode)
    Pins 5, 6    = OFF (Disable Bias, Termination)

NOTE: this driver at present does not support any sleep modes.

"""

# imports
import struct
from lib.serial import *

from devices.device_base import DeviceBase
from devices.device_base import *
from settings.settings_base import SettingsBase, Setting
from common.types.boolean import Boolean, STYLE_ONOFF, STYLE_YESNO
from channels.channel_source_device_property import *

# constants

# exception classes

# interface functions

# classes
class MassaM300s(DeviceBase, Serial):

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        ## Local State Variables:
        self.__response_buffer = ""
        self.__request_events = []
        self.__request_retry_events = []

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='poll_rate_sec', type=int, required=False,
                default_value=5,
                verify_function=lambda x: x >= 0),
            Setting(
                name='bus_id', type=int, required=False,
                default_value=0,
                verify_function=lambda x: x >= 0),
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="strength", type=int,
                initial=Sample(timestamp=0, value=0, unit="%"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="target_detected", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(False, style=STYLE_YESNO)),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="error_flag", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(False, style=STYLE_YESNO)),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="range", type=int,
                initial=Sample(timestamp=0, value=0, unit="in"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="temperature", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="C"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Initialize the serial interface:
        Serial.__init__(self, 0, 19200, timeout = 0)


    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):
        """\
            Called when new configuration settings are available.

            Must return tuple of three dictionaries: a dictionary of
            accepted settings, a dictionary of rejected settings,
            and a dictionary of required settings that were not
            found.
        """

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # there were problems with settings, terminate early:
            self.__tracer.error("Settings rejected/not found: %s %s", rejected, not_found)
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)


    def start(self):
        """Start the device driver.  Returns bool."""

        # Set the baud rate to 19200:

        self.__sched = self.__core.get_service("scheduler")

        # Scheduling first request and watchdog:
        self.__schedule_request()
        self.__reschedule_retry_watchdog()

        return True

    def stop(self):
        """Stop the device driver.  Returns bool."""

        return True


    ## Locally defined functions:
    def make_request(self):
        self.__tracer.debug("make_request")
        bus_id = SettingsBase.get_setting(self, "bus_id")
        req = [ 170, bus_id, 3, 0, 0 ]
        req.append(sum(req) % 256)
        buf = reduce(lambda s, b: s + struct.pack("B", b), req, "")

        try:
            self.write(buf)
            data = self.read(6)
            self.message_indication(data, None)
        except:
            self.__tracer.warning("xmission failure, will retry.")
            self.__schedule_request()
            self.__reschedule_retry_watchdog()


    def __schedule_request(self):
        self.__tracer.debug("scheduling request")
        poll_rate_sec = SettingsBase.get_setting(self, "poll_rate_sec")

        # Attempt to Cancel all/any pending request events still waiting
        # to run for our device.
        for event in self.__request_events:
            try:
                self.__sched.cancel(event)
            except:
                pass
        self.__request_events = []

        # Request a new event at our poll rate in the future.
        event = self.__sched.schedule_after(poll_rate_sec, self.make_request)
        if event != None:
            self.__request_events.append(event)

    def __reschedule_retry_watchdog(self):
        self.__tracer.debug("reschedule watchdog")
        poll_rate_sec = SettingsBase.get_setting(self, "poll_rate_sec")

        # Attempt to Cancel all/any pending retry request events still waiting
        # to run for our device.
        for event in self.__request_retry_events:
            try:
                self.__sched.cancel(event)
            except:
                pass
        self.__request_retry_events = []

        # Request a new event at our poll rate in the future.
        event = self.__sched.schedule_after(poll_rate_sec * 1.5, self.retry_request)
        if event != None:
            self.__request_events.append(event)

    def retry_request(self):
        self.__tracer.debug("retry request.")
        self.make_request()
        self.__reschedule_retry_watchdog()

    def message_indication(self, buf, addr):
        self.__tracer.debug("message indication.")
        self.__response_buffer += buf

        if len(self.__response_buffer) < 6:
            # We may need to just give the network a bit more time
            # but just in case, reschedule the retry event now:
            self.__reschedule_retry_watchdog()
            return

        bus_id = 0
        strength = 0.00
        target_detected = False
        error_flag = False
        range = 0
        temperature = 0
        checksum_good = False

        response = self.__response_buffer[0:6]
        self.__response_buffer = self.__response_buffer[6:]
        response = struct.unpack("6B", response)

        # Parse the response packet:

        bus_id = response[0]

        b = (response[1] & 0xf0) >> 4
        strength_tab = { 0x1: 25, 0x2: 50, 0x3: 75, 0x4: 100 }
        if b in strength_tab:
            strength = strength_tab[b]
        else:
            strength = 0

        b = (response[1] & 0xf)
        if (b & 0x8):
            target_detected = True
#	    if (b & 0x4):
#		vout_mode = True
#	    if (b & 0x2):
#		switch_mode = True
        if (b & 0x1):
            error_flag = True

        range = ((response[3] << 8) | response[2]) / 128
        temperature = (response[4] * 0.48876) - 50

        if (sum(response[0:5]) % 256 == response[5]):
            checksum_good = True

        if not checksum_good:
            # Ick!  The RS-485 reply packets may not been packetized
            # in the proper sequence.  Flush the buffer.
            self.__response_buffer = ""
        else:
            # Update our channels:
            self.property_set("strength", Sample(0, strength, "%"))
            self.property_set("target_detected",
                Sample(0, Boolean(target_detected, STYLE_YESNO)))
            self.property_set("error_flag",
                Sample(0, Boolean(error_flag, STYLE_YESNO)))
            self.property_set("range", Sample(0, range, "in"))
            self.property_set("temperature", Sample(0, temperature, "C"))
            self.__tracer.debug("temp=%0.1fC range=%0.1fin strength=%d%%",
                temperature, range, strength)

        # Schedule our next poll:
        self.__schedule_request()
        # Reschedule retry watchdog:
        self.__reschedule_retry_watchdog()



# internal functions & classes

