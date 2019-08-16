############################################################################
#                                                                          #
# Copyright (c)2008,2009 Digi International (Digi). All Rights Reserved.   #
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


# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

import threading
import sys
import digitime as time

# constants
# time tup from time module
TM_WDAY = 6     # day of week, 0-6 with 0=Monday

PROP_15SEC = '15_sec'
PROP_MINUTE = 'minute'
PROP_15MIN = '15_min'
PROP_HOUR = 'hour'
PROP_SIXHR = 'six_hour'
PROP_DAY = 'day'
PROP_TICK_RATE = 'tick_rate'
PROP_PRINTF = 'printf'

DEFAULT_TICK_RATE = 15

channel_map = { PROP_15SEC: 15,
                PROP_MINUTE: 60,
                PROP_15MIN: 900,
                PROP_HOUR: 3600,
                PROP_SIXHR: 21600,
                PROP_DAY: 86400 }

# exception classes

# interface functions

# classes

class AlarmClockDevice(DeviceBase, threading.Thread):
    """
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.

    """

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        self.targets = {}

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Settings Table Definition:
        settings_list = [

            Setting(name=PROP_PRINTF, type=str, required=False, default_value=PROP_MINUTE),

            Setting( # how often to check for work
                name=PROP_TICK_RATE, type=int, required=False,
                default_value=DEFAULT_TICK_RATE,
                verify_function=lambda x: x > 0.0),
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties

            ChannelSourceDeviceProperty(name=PROP_15SEC, type=tuple,
                initial=Sample(timestamp=0, value=(0,None)),
                perms_mask=DPROP_PERM_GET),

            ChannelSourceDeviceProperty(name=PROP_MINUTE, type=tuple,
                initial=Sample(timestamp=0, value=(0,None)),
                perms_mask=DPROP_PERM_GET),

            ChannelSourceDeviceProperty(name=PROP_15MIN, type=tuple,
                initial=Sample(timestamp=0, value=(0,None)),
                perms_mask=DPROP_PERM_GET),

            ChannelSourceDeviceProperty(name=PROP_HOUR, type=tuple,
                initial=Sample(timestamp=0, value=(0,None)),
                perms_mask=DPROP_PERM_GET),

            ChannelSourceDeviceProperty(name=PROP_SIXHR, type=tuple,
                initial=Sample(timestamp=0, value=(0,None)),
                perms_mask=DPROP_PERM_GET),

            ChannelSourceDeviceProperty(name=PROP_DAY, type=tuple,
                initial=Sample(timestamp=0, value=(0,None)),
                perms_mask=DPROP_PERM_GET),

        ]

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        if len(rejected) or len(not_found):
            self.__tracer.error("Settings rejected/not found: %s %s",
                                rejected, not_found)

        if PROP_TICK_RATE in accepted and \
               accepted[PROP_TICK_RATE] != DEFAULT_TICK_RATE:

            self.__tracer.warning(
                "tick_rate settings is depreciated, using %d",
                DEFAULT_TICK_RATE)
            accepted[PROP_TICK_RATE] = DEFAULT_TICK_RATE

        SettingsBase.commit_settings(self, accepted)
        return (accepted, rejected, not_found)

    def start(self):
        threading.Thread.start(self)

        return True

    def stop(self):
        self.__stopevent.set()
        return True

    ## Locally defined functions:
    # Property callback functions:

    def print_time_is_now(self):

        # then user wants the lines
        self.time_str = ("%04d-%02d-%02d %02d:%02d:%02d"
                         % self.time_tup[:TM_WDAY])
        self.__tracer.info('\ntime is now %s' % self.time_str)
        return

    def _set_targets(self):

        # Set targets to produce samples
        self.time_now = time.time()

        for tgt in channel_map.keys():
            self.targets[tgt] = self.time_now + channel_map[tgt]

    def _trigger(self, rate):
        want_print = SettingsBase.get_setting(self, PROP_PRINTF)

        new_time = time.time()

        if abs(new_time - self.time_now) > rate + 10:
            # If time has jumped considerably between polls, the
            # wall time has jumped.  Best thing to do is just
            # re-target based on the new time
            self.__tracer.warning("System time jump, resetting")
            self._set_targets()

        self.time_now = new_time
        self.time_tup = time.localtime(self.time_now)
        self.sample = (self.time_now, tuple(self.time_tup))

        # Check target channels
        for tgt in channel_map.keys():
            if self.time_now >= self.targets[tgt]:
                if want_print == tgt:
                    self.print_time_is_now()
                self.property_set(tgt,
                                  Sample(self.time_now, self.sample,
                                         'time'))
                self.targets[tgt] = self.time_now + channel_map[tgt]


    # Threading related functions:
    def run(self):

        # Baseline relative time targets
        self._set_targets()

        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break

            rate = SettingsBase.get_setting(self, PROP_TICK_RATE)
            self._trigger(rate)

            time.sleep(rate)

        return

# internal functions & classes
