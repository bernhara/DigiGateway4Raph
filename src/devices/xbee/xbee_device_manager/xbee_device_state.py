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
XBee Device Manager XBee State Class Definition

"""

# imports
import traceback
from copy import copy

from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import XBeeDeviceManagerRunningEventSpec

from devices.xbee.xbee_config_blocks.xbee_config_block_sleep import \
    XBeeConfigBlockSleep


# exceptions
class XBeeDeviceStateInvalidStateForOperation(Exception):
    pass


class XBeeDeviceState:
    """\
        XBee Device Manager XBee State Class

        This class defines each of the possible states any given
        XBee Device node might be in.
        It also offers methods of things that needs to be done per state,
        as well as retrieval of what state the device is currently in.

    """

    # States that an XBee node may be in:
    STATE_INITIALIZING           = 0
    STATE_CONFIG_SCHEDULED       = 1
    STATE_CONFIG_IMMEDIATE       = 2
    STATE_CONFIG_ACTIVE          = 3
    STATE_RUNNING                = 4

    def __init__(self):
        self.__state = self.STATE_INITIALIZING
        self.__event_specs = []
        self.__config_blocks = []
        self.__config_sched_handle = None
        self.__ext_addr = None      # Set by xbee_device_event_spec_add()
        self.__config_attempts = 0
        self.__last_heard_from = None

        from core.tracing import get_tracer
        self.__tracer = get_tracer('XbeeDeviceState')

    def get_state(self):
        return self.__state

    def event_spec_add(self, event_spec):
        """\
            Adds an event spec to the list of event specs stored
            in this object.

        """
        self.__event_specs.append(event_spec)

    def event_spec_remove(self, event_spec):
        """\
            Removes an event spec from the list of event specs stored in this
            object.

        """
        self.__event_specs.remove(event_spec)

    def event_spec_list(self):
        """\
            Returns a list of event specs stored in this object.

        """
        # Copy so they can't change our list w/o using the add/remove methods
        return copy(self.__event_specs)

    def config_block_add(self, config_block):
        """\
            Adds a config block to the list of config blocks stored in this
            object.  The addition is only permitted to be done when the device
            is in the initializing state.

        """
        if self.__state != self.STATE_INITIALIZING:
            raise XBeeDeviceStateInvalidStateForOperation(
                "Device is already being configured or is running.")
        self.__config_blocks.append(config_block)

    def config_block_remove(self, config_block):
        """\
            Removes a config block from the list of config blocks stored in
            this object.  The removal is only permitted to be done when the
            device is in the initializing state.

        """
        if self.__state != self.STATE_INITIALIZING:
            raise XBeeDeviceStateInvalidStateForOperation(
                "Device is already being configured or is running.")
        self.__config_blocks.remove(config_block)

    def config_block_list(self):
        """\
            Returns a list the config blocks stored in this object.

        """
        return self.__config_blocks

    def configuration_sched_handle_set(self, sched_handle):
        """\
            Stores the handle that was given by the scheduler.

        """
        self.__config_sched_handle = sched_handle

    def configuration_sched_handle_get(self):
        """\
            Returns the handle that was given by the scheduler.

        """
        return self.__config_sched_handle

    def ext_addr_set(self, ext_addr):
        """\
            Sets our internally stored extended address.
            Function will the convert extended address to lower case if needed.

        """
        if ext_addr != None:
            self.__ext_addr = ext_addr.lower()
        else:
            self.__ext_addr = ext_addr

    def ext_addr_get(self):
        """\
            Get our internally stored extended address.
            Function will the convert extended address to lower case if needed.

        """
        if self.__ext_addr != None:
            return self.__ext_addr.lower()
        else:
            return self.__ext_addr

    def _get_state(self):
        """\
            Returns the current state the XBee device is in.

        """
        return self.__state

    def goto_initializing(self):
        """\
            Set current state of XBee device to 'initializing'
            and reset config attempts to 0.

        """
        self.__state = self.STATE_INITIALIZING
        self.__config_attempts = 0

    def goto_config_scheduled(self):
        """\
            Set current state of XBee device to 'scheduled'.

        """
        self.__state = self.STATE_CONFIG_SCHEDULED

    def goto_config_immediate(self):
        """\
            Set current state of XBee device to 'immediate'.

        """
        self.__state = self.STATE_CONFIG_IMMEDIATE

    def goto_config_active(self):
        """\
            Set current state of XBee device to 'active'.

        """
        self.__state = self.STATE_CONFIG_ACTIVE

    def goto_running(self):
        """\
            Set current state of XBee device to 'running' and reset
            config attempts to 0.

        """
        self.__state = self.STATE_RUNNING
        # Zero the configuration attempts counter in case we
        # are asked to reconfigure later.
        self.__config_attempts = 0

        running_event_specs = \
            filter(lambda s: isinstance(s, XBeeDeviceManagerRunningEventSpec),
                    self.__event_specs)

        for spec in running_event_specs:
            # call running event callbacks:
            try:
                (spec.cb_get())()
            except Exception, e:
                self.__tracer.error("XBeeDeviceState.goto_running: " +
                                    "exception occurred while calling" +
                                    " cb %s (%s): %s",
                                    spec.cb_get(), str(e),
                                    traceback.format_exc())

    def is_initializing(self):
        """\
            Returns True if current state of XBee device is 'initializing'.
            Otherwise returns False.

        """
        return self.__state == self.STATE_INITIALIZING

    def is_config_scheduled(self):
        """\
            Returns True if current state of XBee device is 'scheduled'.
            Otherwise returns False.

        """
        return self.__state == self.STATE_CONFIG_SCHEDULED

    def is_config_immediate(self):
        """\
            Returns True if current state of XBee device is 'immediate'.
            Otherwise returns False.

        """
        return self.__state == self.STATE_CONFIG_IMMEDIATE

    def is_config_active(self):
        """\
            Returns True if current state of XBee device is 'active'.
            Otherwise returns False.

        """
        return self.__state == self.STATE_CONFIG_ACTIVE

    def is_running(self):
        """\
            Returns True if current state of XBee device is 'running'.
            Otherwise returns False.

        """
        return self.__state == self.STATE_RUNNING

    def config_attempts_get(self):
        """\
            Returns how many config attempts the device currently has had.

        """
        return self.__config_attempts

    def config_attempts_set(self, config_attempts):
        """\
            Sets how many config attempts the device currently has had.
            Returns the newly set number of config attempts.

        """
        self.__config_attempts = config_attempts
        return self.__config_attempts

    def last_heard_from_get(self):
        """\
            Returns when we last heard from the device.

        """
        return self.__last_heard_from

    def last_heard_from_set(self, timestamp):
        """\
            Sets when we last heard from the device.

        """
        self.__last_heard_from = timestamp
        return self.__last_heard_from

    def xbee_sleep_period_sec(self):
        """\
            Returns the number of seconds this XBee is configured to sleep.

            This method will return 0 if the device is not configured to sleep.
            Keep in mind that this method returns how the node is _configured_;
            the actual configuration may not be running on the node.

        """
        sleep_blocks = filter(lambda b: isinstance(b, XBeeConfigBlockSleep),
                              self.__config_blocks)

        if not len(sleep_blocks):
            return 0

        period_ms = max(map(lambda sb: sb.sleep_period_ms_get(), sleep_blocks))

        if not period_ms:
            return 0
        return max(1, (period_ms // 1000))
