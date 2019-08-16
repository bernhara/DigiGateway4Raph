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
    A DIA Driver for the Digi XBee Wall Router
"""

# imports
import digitime

from core.tracing import get_tracer
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.common.io_sample import parse_is
from devices.xbee.common.prodid import PROD_DIGI_XB_WALL_ROUTER

# constants

# exception classes

# interface functions


# classes
class XBeeXBR(XBeeBase):
    """
    This class extends one of our base classes and is intended as
    an example of a concrete, example implementation, but it is
    not itself meant to be included as part of our developer
    API. Please consult the base class documentation for the API
    and the source code for this file for an example
    implementation.

    """
    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [[0xe8, 0xc105, 0x92], [0xe8, 0xc105, 0x11]]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [PROD_DIGI_XB_WALL_ROUTER, ]

    # due to self-heating, the Wall Router usually reads about 4 DegC too warm
    BASE_OFFSET_DEGC = -4.0

    # if the temperature is less then this, assume NOT a WR (is -56 DegC)
    BASE_RAW_TEMP_CUTOFF = 10

    # settings defaults
    DEF_SAMPLE_MS = 1000
    DEF_OFFSET = 0.0
    DEF_DEGF = False

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

        ## XBeeBase manages these settings:
        #   xbee_device_manager: the name of an XBeeDeviceManager instance.
        #   extended_address:    the extended address of the XBee device you
        #                            would like to monitor.
        #
        ## This driver maintains
        #   sample_rate_ms: the sample rate in msec of the XBee Wall Router.
        #   offset:         a raw offset to add/subtract from resulting temperature
        #   degf:           T/F if degress Fahrenheit is desired instead of Celsius

        settings_list = [
            Setting(
                name='sample_rate_ms', type=int, required=False,
                default_value=self.DEF_SAMPLE_MS,
                verify_function=lambda x: x > 0 and x < 0xffff),
            Setting(
                name='offset', type=float, required=False,
                default_value=self.DEF_OFFSET),
            Setting(
                name='degf', type=bool, required=False,
                default_value=self.DEF_DEGF),
        ]
        # Add our settings_list entries into the settings passed to us.
        set_in = self.merge_settings(set_in, settings_list)

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="light", type=float,
                initial=Sample(timestamp=0, unit="not init", value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="temperature", type=float,
                initial=Sample(timestamp=0, unit="not init", value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]
        # Add our property_list entries into the properties passed to us.
        prop_in = self.merge_properties(prop_in, property_list)

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, name, core_services, set_in, prop_in)

        self._tracer.calls("XBeeXBR.__init__()")


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

        for address in XBeeXBR.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeXBR.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    # use XBeeBase.apply_settings(self):

    def start(self):

        self._tracer.calls("XBeeXBR.start()")

        # init self._xbee_manager and self._extended_address
        # register ourself with our Xbee manager
        # create the self.running_indication callback
        XBeeBase.pre_start(self)

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        self._xbee_manager.register_sample_listener(self, self._extended_address,
                                                     self._sample_indication)

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(self._extended_address)

        # Configure pins DI1 & DI2 for analog input:
        for io_pin in ['D1', 'D2']:
            xbee_ddo_cfg.add_parameter(io_pin, 2)

        # Register this configuration block with the XBee Device Manager:
        self._xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Configure the IO Sample Rate:
        sample_rate = SettingsBase.get_setting(self, "sample_rate_ms")

        # DigiMesh requires at least 'Sleep Compatibility'
        # this call will also set IR to sample_rate
        xbee_sleep_cfg = self._xbee_manager.get_sleep_block(
            self._extended_address,
            sleep=False, sleep_rate_ms=sample_rate, awake_time_ms=0)

        self._xbee_manager.xbee_device_config_block_add(self, xbee_sleep_cfg)

        # we've no more to config, indicate we're ready to configure.
        return XBeeBase.start(self)

    # use XbeeBase.stop(self):

    ## Locally defined functions:
    def _sample_indication(self, buf, addr):
        """\
            Receive and parse an I/O sample

        """
        self._tracer.calls("XBeeXBR.sample_indication()")

        io_sample = parse_is(buf)
        #  print io_sample

        if io_sample["AD2"] <= self.BASE_RAW_TEMP_CUTOFF:
            # then assume has no valid inputs
            self._tracer.debug('sample_indication: lacks temperature/light hardware')
            return False

        # light is only a 'brightness', so we just return as mv
        light = round(self.raw_to_mv(io_sample["AD1"]))

        # temperature we'll convert from mv to degree C
        temperature = ((self.raw_to_mv(io_sample["AD2"]) - 500.0) / 10.0) + self.BASE_OFFSET_DEGC

        if SettingsBase.get_setting(self, "degf"):
            temperature = (temperature * 1.8) + 32.0
            units = 'F'
        else:
            units = 'C'

        # offset is a simple float value - we don't care if DegC or DegF
        temperature += SettingsBase.get_setting(self, "offset")

        # Update channels:
        now = digitime.time()
        self.property_set("light", Sample(now, light, "brightness"))
        self.property_set("temperature", Sample(now, temperature, units))
        self._tracer.debug('temperature:%0.1f%s light:%d ',
                temperature, units, light)

        return True

# internal functions & classes
    def raw_to_mv(self, raw):
        if self._xbee_manager.is_digimesh():
            # DigiMesh uses a 3.3v reference, so 0-1023 = 0-3300mv
            return raw * 3300.0 / 1023

        # ZigBee uses a 1.2v reference, so 0-1023 = 0-1200mv
        return raw * 1200.0 / 1023
