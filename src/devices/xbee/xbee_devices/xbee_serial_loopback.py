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

"""\
Demo LoopBack Driver connected to an XBee 232 Adapter.

"""

# imports
import random

from devices.xbee.xbee_devices.xbee_serial import XBeeSerial
import devices.xbee.common.bindpoints as bindpoints
from settings.settings_base import SettingsBase, Setting
from common.types.boolean import Boolean, STYLE_ONOFF, STYLE_YESNO
from channels.channel_source_device_property import *

from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import gw_extended_address_tuple

# constants

# exception classes

# interface functions


# classes
class XBeeLoopBack(XBeeSerial):
    """\
        This class extends one of our base classes and is intended as an
        example of a concrete, example implementation, but it is not itself
        meant to be included as part of our developer API. Please consult the
        base class documentation for the API and the source code for this file
        for an example implementation.

    """
    def __init__(self, name, core_services):

        ## These will be created by XBeeSerial
        # self._name = name
        # self._core = core_services
        # self._tracer = get_tracer(name)
        # self._xbee_manager = None
        # self._extended_address = None

        ## Local State Variables:
        self.__request_events = []
        self.__request_retry_events = []
        self._loopback_data = ""
        self._loopback_attempts = 0
        self._loopback_passes = 0
        self._loopback_fails = 0
        self._loopback_total_bytes_sent = 0
        self._loopback_total_bytes_received = 0

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='loop_rate_sec', type=int, required=False,
                default_value=5,
                verify_function=lambda x: x >= 0),
            Setting(
                name='packet_size', type=int, required=False,
                default_value=5,
                verify_function=lambda x: x <= 10),
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="attempts", type=int,
                initial=Sample(timestamp=0, value=0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="total_bytes_sent", type=int,
                initial=Sample(timestamp=0, value=0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="total_bytes_received", type=int,
                initial=Sample(timestamp=0, value=0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="passes", type=int,
                initial=Sample(timestamp=0, value=0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="fails", type=int,
                initial=Sample(timestamp=0, value=0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]

        ## Initialize the XBeeSerial interface:
        XBeeSerial.__init__(self, name, core_services,
                                settings_list, property_list)

        self._tracer.calls("XBeeLoopBack.__init__()")

    ## Functions which must be implemented to conform to the XBeeSerial
    ## interface:

    def read_callback(self, buf):
        self.message_indication(buf)

    # not using sample_indication(io_sample)

    def running_indication(self):
        # Scheduling first request and watchdog:
        self.__schedule_request()
        self.__reschedule_retry_watchdog()


    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:


    # def apply_settings(): uses XBeeSerial.apply_settings()

    def start(self):

        # Seed random number generator.
        random.seed()

        return XBeeSerial.start(self)

    # def stop(): uses XBeeSerial.stop()

    ## Locally defined functions:



    def make_request(self):
        self._tracer.calls("make_request")

        try:
            packet_size = SettingsBase.get_setting(self, "packet_size")
        except:
            packet_size = 1

        buf = ""
        for i in range(0, packet_size):
            d = random.randint(0, 255)
            buf += chr(d)

        try:
            self._loopback_attempts += 1
            ret = self.write(buf)
            if ret == False:
                raise Exception, "write failed"
            self._loopback_data = buf
            self._loopback_total_bytes_sent += len(buf)
            self.property_set("attempts", Sample(0, self._loopback_attempts, ""))
            self.property_set("total_bytes_sent", Sample(0, self._loopback_total_bytes_sent, ""))
        except:
            # try again later:
            self._tracer.warning("Xmission failure, will retry.")
            self.__schedule_request()
            self.__reschedule_retry_watchdog()


    def __schedule_request(self):
        self._tracer.calls("Scheduling request")
        loop_rate_sec = SettingsBase.get_setting(self, "loop_rate_sec")

        # Attempt to Cancel all/any pending request events still waiting
        # to run for our device.
        for event in self.__request_events:
            try:
                self._xbee_manager.xbee_device_schedule_cancel(event)
            except:
                pass
        self.__request_events = []

        # Request a new event at our poll rate in the future.
        event = self._xbee_manager.xbee_device_schedule_after(
            loop_rate_sec, self.make_request)
        if event != None:
            self.__request_events.append(event)


    def __reschedule_retry_watchdog(self):
        self._tracer.calls("__reschedule_retry_watchdog")
        loop_rate_sec = SettingsBase.get_setting(self, "loop_rate_sec")
        if loop_rate_sec == 0:
            loop_rate_sec = 1

        # Attempt to Cancel all/any pending retry request events still waiting
        # to run for our device.
        for event in self.__request_retry_events:
            try:
                self._xbee_manager.xbee_device_schedule_cancel(event)
            except:
                pass
        self.__request_retry_events = []

        # Request a new event at our poll rate in the future.
        event = self._xbee_manager.xbee_device_schedule_after(
            loop_rate_sec * 1.5, self.retry_request)
        if event != None:
            self.__request_events.append(event)


    def retry_request(self):
        self._tracer.calls("retry_request")
        self.make_request()
        self.__reschedule_retry_watchdog()


    def message_indication(self, buf):
        self._tracer.calls("message_indication")

        self._loopback_total_bytes_received += len(buf)
        self.property_set("total_bytes_received", Sample(0, self._loopback_total_bytes_received, ""))

        # Update our channels:
        if buf == self._loopback_data:
            self._loopback_passes += 1
            self.property_set("passes", Sample(0, self._loopback_passes, ""))

            # Schedule our next poll:
            self.__schedule_request()

        else:
            self._loopback_fails += 1
            self.property_set("fails", Sample(0, self._loopback_fails, ""))
            # Since something went wrong, its possible we have stale data
            # out there still.
            # In this case, lets let the network settle down, by not sending
            # a new data packet yet, but schedule a retry watchdog
            # instead.

        # Reschedule retry watchdog:
        self.__reschedule_retry_watchdog()


# internal functions & classes
