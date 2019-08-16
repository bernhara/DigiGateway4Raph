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
A DIA Driver for the XBee Sensor /L/T(/H) Product.

Note: this is not the driver for the XBee Sensor Adapter product.
"""

# imports
import digitime
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.types.boolean import Boolean

from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep \
    import CYCLIC_SLEEP_EXT_MAX_MS, SM_DISABLED
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *
from devices.xbee.common.io_sample import parse_is, sample_to_mv
from devices.xbee.common.prodid \
    import MOD_XB_ZB, MOD_XB_S2C_ZB, parse_dd, format_dd, product_name, \
    PROD_DIGI_XB_SENSOR_LTH, PROD_DIGI_XB_SENSOR_LT

# constants

# exception classes

# interface functions

# classes
class XBeeSensor(XBeeBase):
    '''
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.
    '''
    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [[0xe8, 0xc105, 0x92], [0xe8, 0xc105, 0x11]]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [PROD_DIGI_XB_SENSOR_LTH, PROD_DIGI_XB_SENSOR_LT, ]

    # settings defaults
    DEF_SLEEP = True
    DEF_SAMPLE_MS = 60000
    DEF_AWAKE_MS = 1000
    DEF_PREDELAY = 125
    DEF_HUMIDITY = False
    DEF_DEGF = False
    DEF_OFFSET = 0.0

    def __init__(self, name, core_services, set_in=None, prop_in=None):

        # DeviceBase will create:
        #   self._name, self._core, self._tracer,
        # XBeeBase will create:
        #   self._xbee_manager, self._extended_address

        ## XBeeBase manages these settings:
        #   xbee_device_manager: the name of an XBeeDeviceManager instance.
        #   extended_address:    the extended address of the XBee device you
        #                            would like to monitor.

        ## Local State Variables:
        self._last_timestamp = 0

        # Settings
        #
        # xbee_device_manager: must be set to the name of an XBeeDeviceManager
        #                      instance.
        # extended_address: the extended address of the XBee Sensor device you
        #                   would like to monitor.
        # sleep: True/False setting which determines if we should put the
        #        device to sleep between samples.  Default: True
        # sample_rate_ms: the sample rate of the XBee adapter. Default:
        #                 60,000 ms or one minute.
        #
        # Advanced settings:
        #
        # awake_time_ms: how long should the sensor stay awake after taking
        #                a sample?  The default is 1000 ms.
        # sample_predelay: how long should the sensor be awake for
        #                  before taking its sample reading?  This
        #                  delay is used to allow the
        #                  device's sensoring components to warm up before
        #                  taking a sample.  The default is 125ms.
        # humidity_present: force a sensor which has not been detected to have
        #                   humidity capability to having humidity capability
        #                   present.  Writes the devices DD device-type value
        #                   as a side effect.
        # degf:             The temperature channel will output in Fahrenheit,
        #                   and units will be "F", if this boolean is set to True
        # offset:           A simple float that will be applied against the temperature.
        #                   This offset is in degrees Celsius if degf = False,
        #                   and in degrees Fahrenheit if degf = True.

        settings_list = [
            Setting(
                name='sleep', type=bool, required=False,
                default_value=self.DEF_SLEEP),
            Setting(
                name='sample_rate_ms', type=int, required=False,
                default_value=self.DEF_SAMPLE_MS,
                verify_function=lambda x: x >= 0 and \
                                          x <= CYCLIC_SLEEP_EXT_MAX_MS),

            # These settings are provided for advanced users, they
            # are not required:

            Setting(
                name='awake_time_ms', type=int, required=False,
                default_value=self.DEF_AWAKE_MS,
                verify_function=lambda x: x >= 0 and x <= 0xffff),

            Setting(
                name='sample_predelay', type=int, required=False,
                default_value=self.DEF_PREDELAY,
                verify_function=lambda x: x >= 0 and x <= 0xffff),

            Setting(
                name='humidity_present', type=bool, required=False,
                default_value=self.DEF_HUMIDITY),

            Setting(
                name='degf', type=bool, required=False,
                default_value=self.DEF_DEGF),

            Setting(
                name='offset', type=float, required=False,
                default_value=self.DEF_OFFSET),
            ]

        # Add our settings_list entries into the settings passed to us.
        set_in = self.merge_settings(set_in, settings_list)

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="light", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="brightness"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="temperature", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="C"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="low_battery", type=bool,
                initial=Sample(timestamp=0, value=False),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]

        # Add our property_list entries into the properties passed to us.
        prop_in = self.merge_properties(prop_in, property_list)

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, name, core_services, set_in, prop_in)

        self._tracer.calls("XBeeSensor.__init__()")

    ## Functions which must be implemented to conform to the XBeeBase
    ## interface:

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

        for address in XBeeSensor.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeSensor.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # there were problems with settings, terminate early:
            self._tracer.error("Settings rejected/not found: %s %s",
                                rejected, not_found)

            return (accepted, rejected, not_found)

        # Verify that the sample predelay time when added to the awake time
        # is not over 0xffff.
        if accepted['sample_predelay'] + accepted['awake_time_ms'] > 0xffff:
            self._tracer.error("The awake_time_ms value (%d) " +
                                "and sample_predelay value (%d) " +
                                "when added together cannot exceed 65535.",
                                self._name, accepted['sample_predelay'],
                                accepted['awake_time_ms'])

            rejected['awake_time_ms'] = accepted['awake_time_ms']
            del accepted['awake_time_ms']
            rejected['sample_predelay'] = accepted['sample_predelay']
            del accepted['sample_predelay']
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):

        self._tracer.calls("XBeeSensor.start()")

        # init self._xbee_manager and self._extended_address
        # register ourself with our Xbee manager
        # create the self.running_indication callback
        XBeeBase.pre_start(self)

        # Retrieve the flag which tells us if we should sleep:

        # Create a callback specification for our device address
        self._xbee_manager.register_sample_listener(self, self._extended_address,
                                                     self.sample_indication)

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(self._extended_address)

        # Configure pins DI1 .. DI3 for analog input:
        for io_pin in ['D1', 'D2', 'D3']:
            xbee_ddo_cfg.add_parameter(io_pin, 2)

        # Configure battery-monitor pin DIO11/P1 for digital input:
        xbee_ddo_cfg.add_parameter('P1', 3)
        # Enable change detection on DIO11:
        #
        # 0x   8    0    0
        #   1000 0000 0000 (b)
        #   DDDD DDDD DDDD
        #   IIII IIII IIII
        #   OOOO OOOO OOOO
        #   1198 7654 3210
        #   10
        #
        xbee_ddo_cfg.add_parameter('IC', 0x800)

        if SettingsBase.get_setting(self, "humidity_present"):
            # Get gateway module_id, universal to all nodes on the network:
            gw_dd = self._xbee_manager.xbee_device_ddo_get_param(
                        None, 'DD', use_cache=True)
            module_id, product_id = parse_dd(gw_dd)
            # Re-program DD value to set sensor type to /L/T/H:
            device_dd = format_dd(module_id, PROD_DIGI_XB_SENSOR_LTH)
            xbee_ddo_cfg.add_parameter('DD', device_dd)

        # Configure the IO Sample Rate:
        # Clip sample_rate_ms to the max value of IR:
        sample_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")
        sample_rate_ms = min(sample_rate_ms, 0xffff)
        xbee_ddo_cfg.add_parameter('IR', sample_rate_ms)

        # Register this configuration block with the XBee Device Manager:
        self._xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Setup the sleep parameters on this device:
        will_sleep = SettingsBase.get_setting(self, "sleep")
        sample_predelay = SettingsBase.get_setting(self, "sample_predelay")
        awake_time_ms = (SettingsBase.get_setting(self, "awake_time_ms") +
                         sample_predelay)

        if will_sleep:
            # Sample time pre-delay, allow the circuitry to power up and
            # settle before we allow the XBee to send us a sample:
            xbee_ddo_wh_block = XBeeConfigBlockDDO(self._extended_address)
            xbee_ddo_wh_block.apply_only_to_modules((MOD_XB_ZB,
                                                     MOD_XB_S2C_ZB,))
            xbee_ddo_wh_block.add_parameter('WH', sample_predelay)
            self._xbee_manager.xbee_device_config_block_add(self,
                                    xbee_ddo_wh_block)

        # The original sample rate is used as the sleep rate:
        sleep_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")

        # new method for mesh health monitoring
        self.set_data_update_rate_seconds(sleep_rate_ms / 1000)

        # not including sample_predelay here... specially configured above
        xbee_sleep_cfg = self._xbee_manager.get_sleep_block(
            self._extended_address, sleep=will_sleep,
            sleep_rate_ms=sleep_rate_ms, awake_time_ms=awake_time_ms)

        self._xbee_manager.xbee_device_config_block_add(self,
                                                         xbee_sleep_cfg)

        # we've no more to config, indicate we're ready to configure.
        return XBeeBase.start(self)

    def stop(self):

        if self._xbee_manager is not None:
            # Unregister ourselves with the XBee Device Manager instance:
            self._xbee_manager.xbee_device_unregister(self)

        return True

    ## Locally defined functions:
    def time_of_last_data(self):
        return self._last_timestamp

    def running_indication(self):
        # request initial status here.
        self._tracer.info("Running indication")
        humidity_present = SettingsBase.get_setting(self, "humidity_present")

        # this is a flawed design - if the gateway has just rebooted,
        # and the Xbee sensor sleeps (which it should), then an actual
        # GET_DDO will be issued, which causes DIA to freeze here and
        # almost certainly throw exception and put the device off line.
        try:
            dd_value = self._xbee_manager.xbee_device_ddo_get_param(
                    self._extended_address, 'DD', use_cache=True)
        except:
            self._tracer.warning('Using default DD')
            dd_value = 0x0003000E

        module_id, product_id = parse_dd(dd_value)
        self._tracer.debug('DD info (module_id, product_id) = ' +
                           '(0x%04x, 0x%04x)"', module_id, product_id)

        if product_id == PROD_DIGI_XB_SENSOR_LTH or humidity_present == True:
            self._tracer.info("Sensor is a '%s' adding humidity channel",
                               product_name(product_id))

            self.add_property(
                ChannelSourceDeviceProperty(name="humidity", type=float,
                    initial=Sample(timestamp=0, value=0.0, unit="%"),
                    perms_mask=DPROP_PERM_GET,
                    options=DPROP_OPT_AUTOTIMESTAMP))
        else:
            self._tracer.info("Sensor is a '%s' no humidity capability.",
                               product_name(product_id))

    def sample_indication(self, buf, addr):

        self._tracer.calls("XBeeSensor.sample_indication()")

        # save time of last data, plus we want ALL of the samples to have
        # exact same timestamp (leaving 0 means some may be 1 second newer)
        self._last_timestamp = digitime.time()

        # new method for mesh health monitoring
        self.set_time_of_last_data(self._last_timestamp)

        if self._tracer.info():
            msg = []
        else:
            msg = None

        # Parse the I/O sample:
        io_sample = parse_is(buf)

        # Calculate sensor channel values:
        if "AD1" in io_sample and "AD2" in io_sample and \
               "AD3" in io_sample:
            light_mv, temperature_mv, humidity_mv = \
                map(lambda cn: sample_to_mv(io_sample[cn]),
                    ("AD1", "AD2", "AD3"))

            #
            # handle temperature - first as celsius
            #
            temperature = (temperature_mv - 500.0) / 10.0
            if not SettingsBase.get_setting(self, "sleep"):
                # self-heating correction if running full-time - reduce 2 DegC
                temperature -= 2.0

            if SettingsBase.get_setting(self, "degf"):
                temperature = (temperature * 1.8) + 32.0
                units = 'F'
            else:
                units = 'C'

            # offset is a simple float value - we don't care if DegC or DegF
            temperature += SettingsBase.get_setting(self, "offset")

            temperature = round(temperature, 2)

            self.property_set("temperature",
                Sample(self._last_timestamp, temperature, units))
            if msg is not None:
                msg.append("%d %s" % (temperature, units))

            #
            # handle the light value
            #
            light = round(light_mv, 0)
            if light < 0:
                # clamp to be zero or higher
                light = 0
            self.property_set("light",
                Sample(self._last_timestamp, light, "brightness"))
            if msg is not None:
                msg.append(", %d brightness" % light)

            #
            # handle humidity - might be missing
            #
            if self.property_exists("humidity"):
                humidity = ((humidity_mv * 108.2 / 33.2) / 5000.0 - 0.16) / \
                           0.0062
                if humidity < 0.0:
                    # clamp to min of 0%
                    humidity = 0.0
                elif humidity > 100.0:
                    # clamp to be max of 100%
                    humidity = 100.0
                self.property_set("humidity",
                    Sample(self._last_timestamp, humidity, "%"))
                if msg is not None:
                    # cannot use %% in string, __tracer will misunderstand
                    msg.append(", %d RH" % humidity)

            else:  # it remains the original default
                humidity = 0

        # Low battery check (attached to DIO11/P1):
        # Invert the signal it is actually not_low_battery:
        if "DIO11" in io_sample:
            low_battery = not bool(io_sample["DIO11"])
            if low_battery != bool(self.property_get("low_battery").value):
                self.property_set("low_battery",
                    Sample(self._last_timestamp, low_battery))

            if low_battery and msg is not None:
                msg.append(", low_battery")
                # try to keep memory use from dragging out

        if msg is not None:
            self._tracer.info("".join(msg))
            del msg

        return

# internal functions & classes
