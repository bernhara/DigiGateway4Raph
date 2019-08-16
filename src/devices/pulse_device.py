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
A device driver with the capability of pulsing a single Boolean channel to
its opposite Boolean value for a specified period of time, after which it
will return to its original Boolean value.

For example,
You may use this driver as a channel_source for a DIO device.  If your
output is False to begin with, and you want to pulse it true for 5 seconds
and then have it go back to false, you can do that with this driver.
You would set that up by setting initial_value to False, and setting
duration to 5.

A 'stop pulse' feature is also added for reverting settings to their initial
value before they are scheduled to revert.  This is useful because if you 
have a long pulse and want to stop it for any reason, you will be able to.
This feature is always enabled, so you can stop a pulse at any time
by setting this channel to its initial value.

Settings:
    duration:   Float - The duration of a pulse in seconds.
                Not Required - Default value is 5.0 (seconds)

    initial_value:  Boolean - The initial value you want the channel to be 
                    set to.  If this setting is set to false, the channel
                    will go from false, go to true for a period of time, and
                    return to false.
                    Not Required - Default value is False

Properties:
    pulse_channel:  The Boolean channel source that will pulse it's opposite
                    Boolean value for a specified period of time.
"""

# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

# constants

# classes


class PulseDevice(DeviceBase):

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        # The __scheduler_handler is the variable that will tell us if there
        # is already a pulse. It is 'None' when the channel is not pulsing
        self.__sched = self.__core.get_service("scheduler")
        self.__scheduler_handler = None

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='duration', type=float, required=False, 
                default_value=5.0, verify_function=lambda x: x > 0.0),

            Setting(
                name='initial_value', type=bool, 
                required=False, default_value=False,
                verify_function=lambda x: x is True or x is False),
        ]

        ## Channel Properties Definition:
        property_list = [
            ChannelSourceDeviceProperty(name="pulse_channel", type=bool,
                initial=Sample(timestamp=0, value=False),
                perms_mask=DPROP_PERM_GET | DPROP_PERM_SET,
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.pulse_channel_cb),
        ]

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

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
            self.__tracer.error("Settings rejected/not found: %s %s", 
                                rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        """\
            Start the device driver.  Returns bool.
            Set channel to initial value because settings
            are initialized by now.
        """
        self.property_set("pulse_channel",\
                Sample(0, self.get_setting("initial_value")))
        return True

    def stop(self):
        """\
            Remove all scheduled events.
            Stop the device driver. Returns bool.
        """
        if self.__scheduler_handler is not None:
            try:
                self.__sched.cancel(self.__scheduler_handler)
            except ValueError:
                pass

        return True

    ## Locally defined functions:
    # Property callback functions:
    def pulse_channel_cb(self, bool_sample):
        """\
            Called when the 'pulse_channel is set', or when a channel that
            'pulse_channel' is subscribed to changes values.

            We will determine the initial value of 'pulse_channel'.
            If the value being set is opposite to the initial value, then
            set 'pulse_channel' to this new value for a period of time,
            after which set 'pulse_channel' back to its initial value.

            If the value being set is the same as the initial value, and
            'pulse_channel' is in the middle of a pulse (it's current value
            is the opposite bool value to initial value), then immediately
            set pulse_channel to its initial value.

            The initial value is obtained from the setting 'initial_value'
            The pulse duration is obtained from the setting 'duration'
        """

        # if the value being set is NOT equal to the channels current value
        if not bool_sample.value == self.property_get("pulse_channel").value:

            # if no task is scheduled to set the channel back to its initial
            # value, swap current Boolean values and schedule an event
            # to swap the values back after a period of time.
            if self.__scheduler_handler is None:

                self.swap_values(bool_sample.value)

                self.__scheduler_handler = \
                    self.__sched.schedule_after( \
                        self.get_setting("duration"), self.swap_values,\
                        self.get_setting("initial_value"))

            else:
                # 'pulse_channel' is currently in a pulse. This means that
                # the value being set is equal to 'initial_value'. Cancel
                # the scheduled event to return 'pulse_channel' to its
                # initial value after a period of time, and set 
                # 'pulse_channel' to 'initial_value' immediately.

                try:
                    self.__sched.cancel(self.__scheduler_handler)
                except Exception:
                    pass
                self.swap_values(self.get_setting('initial_value'))

    def swap_values(self, new_value):
        """\
            Remove the scheduler handler so that pulse_channel can perform
            another pulse. Set the value of 'pulse_channel' to 'new_value'.
        """
        self.__scheduler_handler = None

        self.property_set("pulse_channel", Sample(0, new_value))

# internal functions & classes


def main():
    pass

if __name__ == '__main__':
    import sys
    status = main()
    sys.exit(status)
