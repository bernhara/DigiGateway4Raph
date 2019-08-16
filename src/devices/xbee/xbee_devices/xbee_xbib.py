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
A DIA Driver for the XBIB-x-DEV XBee Development Boards
"""

# imports
import traceback
import digitime

from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
import devices.xbee.common.bindpoints as bindpoints
from channels.channel_source_device_property import *

from common.types.boolean import Boolean, STYLE_ONOFF
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep \
    import CYCLIC_SLEEP_EXT_MAX_MS
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.common.io_sample import parse_is
from devices.xbee.common.prodid import PROD_DIGI_UNSPECIFIED

# constants
LED_IO_MAP = {
    "led1": "P2",
    "led2": "P1",
    "led3": "D4",
}


# exception classes

# interface functions

# classes
class XBeeXBIB(XBeeBase):
    """\
        This class extends one of our base classes and is intended as an
        example of a concrete, example implementation, but it is not itself
        meant to be included as part of our developer API. Please consult the
        base class documentation for the API and the source code for this file
        for an example implementation.

    """
    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [bindpoints.SERIAL, bindpoints.SAMPLE]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [PROD_DIGI_UNSPECIFIED, ]

    # no point 'thrashing' strings by making these on the fly
    SW_NAME = ['sw1', 'sw2', 'sw3', 'sw4']
    DIO_NAME = ['DIO0', 'DIO1', 'DIO2', 'DIO3']

    # settings defaults
    DEF_SLEEP_MS = 0
    DEF_AWAKE_MS = 1500

    def __init__(self, name, core_services, set_in=None, prop_in=None):
        """\
            Initialize an XBee Wall Router instance.

            Parameters:
                * name - The name of the XBee Wall Router instance.
                * core - The Core services instance.
                * set_in - settings from a derived class
                * prop_in - properties from a derived class

        """

        # DeviceBase will create:
        #   self._name, self._core, self._tracer,
        # XBeeBase will create:
        #   self._xbee_manager, self._extended_address

        ## Settings Table Definition:

        settings_list = [
            Setting(
                name='sleep_ms', type=int, required=False,
                default_value=self.DEF_SLEEP_MS,
                verify_function=lambda x: x >= 0 and \
                                x <= CYCLIC_SLEEP_EXT_MAX_MS),
            Setting(name="led1_source", type=str, required=False),
            Setting(name="led2_source", type=str, required=False),
            Setting(name="led3_source", type=str, required=False),
            # This setting is provided for advanced users:
            Setting(
                name='awake_time_ms', type=int, required=False,
                default_value=self.DEF_AWAKE_MS,
                verify_function=lambda x: x >= 0 and x <= 0xffff),
        ]
        # Add our settings_list entries into the settings passed to us.
        set_in = self.merge_settings(set_in, settings_list)

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="sw1", type=bool,
                initial=Sample(timestamp=0, value=False),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="sw2", type=bool,
                initial=Sample(timestamp=0, value=False),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="sw3", type=bool,
                initial=Sample(timestamp=0, value=False),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="sw4", type=bool,
                initial=Sample(timestamp=0, value=False),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            # gettable and settable properties
            ChannelSourceDeviceProperty(name="led1", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(False, style=STYLE_ONOFF)),
                perms_mask=(DPROP_PERM_GET | DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=lambda sample: self.prop_set_led("led1", sample)),
            ChannelSourceDeviceProperty(name="led2", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(False, style=STYLE_ONOFF)),
                perms_mask=(DPROP_PERM_GET | DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=lambda sample: self.prop_set_led("led2", sample)),
            ChannelSourceDeviceProperty(name="led3", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(False, style=STYLE_ONOFF)),
                perms_mask=(DPROP_PERM_GET | DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=lambda sample: self.prop_set_led("led3", sample)),
        ]
        # Add our property_list entries into the properties passed to us.
        prop_in = self.merge_properties(prop_in, property_list)

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, name, core_services, set_in, prop_in)

        self._tracer.calls("XBeeXBIB.__init__()")

    @staticmethod
    def probe():
        #   Collect important information about the driver.
        #
        #   .. Note::
        #
        #       This method is a static method.  As such, all data returned
        #       must be accessible from the class without having a instance
        #       of the device created.
        #
        #   Returns a dictionary that must contain the following 2 keys:
        #           1) address_table:
        #              A list of XBee address tuples with the first part of the
        #              address removed that this device might send data to.
        #              For example: [ 0xe8, 0xc105, 0x95 ]
        #           2) supported_products:
        #              A list of product values that this driver supports.
        #              Generally, this will consist of Product Types that
        #              can be found in 'devices/xbee/common/prodid.py'

        probe_data = XBeeBase.probe()

        for address in XBeeXBIB.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeXBIB.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    # use XBeeBase.apply_settings(self):

    def start(self):

        self._tracer.calls("XBeeXBIB.start()")

        # init self._xbee_manager and self._extended_address
        # then register ourself with our Xbee manager
        XBeeBase.pre_start(self)

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        self._xbee_manager.register_sample_listener(self, self._extended_address,
                                                     self.sample_indication)

        # Configure node sleep behavior:
        sleep_ms = SettingsBase.get_setting(self, "sleep_ms")
        awake_time_ms = SettingsBase.get_setting(self, "awake_time_ms")
        # The original sample rate is used as the sleep rate:

        xbee_sleep_cfg = self._xbee_manager.get_sleep_block(
            self._extended_address,
            sleep=sleep_ms > 0,
            sleep_rate_ms=sleep_ms,
            awake_time_ms=awake_time_ms)

        self._xbee_manager.xbee_device_config_block_add(self, xbee_sleep_cfg)

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(self._extended_address)

        # Configure pins DIO0 .. DIO3 for digital input:
        for io_pin in ['D0', 'D1', 'D2', 'D3']:
            xbee_ddo_cfg.add_parameter(io_pin, 3)

        # Turn off LEDs:
        for led in LED_IO_MAP:
            xbee_ddo_cfg.add_parameter(LED_IO_MAP[led], 0)

        # Assert that all pin pull-ups are enabled:
        xbee_ddo_cfg.add_parameter('PR', 0x1fff)

        # Enable I/O line monitoring on pins DIO0 .. DIO3:
        xbee_ddo_cfg.add_parameter('IC', 0xf)

        # Register this configuration block with the XBee Device Manager:
        self._xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Handle channels subscribed to output their data to our led
        # properties:
        cm = self._core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        for i in range(1, 4):
            setting_name = "led%d_source" % i
            channel_name = SettingsBase.get_setting(self, setting_name)
            if channel_name is not None:
                cp.subscribe(channel_name,
                    (lambda prop: lambda cn: self.update_property(prop, cn))(
                        "led%d" % i))

        # we've no more to config, indicate we're ready to configure.
        return XBeeBase.start(self)


    # use XbeeBase.def stop(self):

    ## Locally defined functions:
    def running_indication(self):
        # Over-ride XBeeBase's
        self._tracer.info("Running indication")
        # Our device is now running, load our initial state:
        self._extended_address = SettingsBase.get_setting(self, "extended_address")
        io_sample = self._xbee_manager.xbee_device_ddo_get_param(
                        self._extended_address, 'IS')
        self.sample_indication(io_sample, self._extended_address)

    def prop_set_led(self, led_name, sample):

        self._tracer.calls("XBeeXBIB.prop_set_led(%s, %s)", led_name, sample)

        now = digitime.time()

        ddo_io_value = 0  # I/O high impedance
        if sample.value:
            ddo_io_value = 4  # I/O sinking

        led_io = LED_IO_MAP[led_name]

        self._extended_address = SettingsBase.get_setting(self, "extended_address")

        # we want to allow the exception to propogate to the caller
        self._xbee_manager.xbee_device_ddo_set_param(
                                    self._extended_address, led_io, ddo_io_value,
                                    apply=True)
        val = Boolean(sample.value, style=STYLE_ONOFF)
        self.property_set(led_name, Sample(now, val))
        self._tracer.info('%s is now %r', led_name, val)

    def update_property(self, led_name, src_channel):
        self.prop_set_led(led_name, src_channel.get())

    def sample_indication(self, buf, addr):
        # Parse the I/O sample:

        self._tracer.calls("XBeeXBIB.sample_indication()")

        io_sample = parse_is(buf)
        change = False
        now = None

        for i in range(4):
            # Refresh switch states, if different:
            val = bool(io_sample[self.DIO_NAME[i]])
            oldval = bool(self.property_get(self.SW_NAME[i]).value)
            if oldval != val:
                change = True
                self.property_set(self.SW_NAME[i], Sample(0, val))
                if val:
                    # then switch is NOT pressed
                    self._tracer.info('%s is NOT pressed (val=%s)',
                                        self.SW_NAME[i], val)
                else:
                    self._tracer.info('%s is PRESSED (val=%s)',
                                        self.SW_NAME[i], val)

        if not change:
            self._tracer.debug('Sample indication, but no change to switches')

# internal functions & classes
