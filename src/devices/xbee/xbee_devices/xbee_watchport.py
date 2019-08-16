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
A DIA Driver for the XBee Watchport Sensor Adapter.

The XBee Watchport Sensor Adapter has 5 optional Sensors that
can be used to provide environmental monitoring services.

The following Watchport Sensors are supported::

    ------------------------------------------------------------------------
    |  Watchport Sensor                           |  DIA Driver Name       |
    ------------------------------------------------------------------------
    |                                             |                        |
    ------------------------------------------------------------------------
    |  Watchport/T Temperature Sensor             |  XBeeWatchportSensorT  |
    ------------------------------------------------------------------------
    |  Watchport/H Humidity/ Temperature Sensor   |  XBeeWatchportSensorH  |
    ------------------------------------------------------------------------
    |  Watchport/D Distance Sensor                |  XBeeWatchportSensorD  |
    ------------------------------------------------------------------------
    |  Watchport/A Acceleration/Tilt Sensor       |  XBeeWatchportSensorA  |
    ------------------------------------------------------------------------
    |  Watchport/W Water Detector                 |  XBeeWatchportSensorW  |
    ------------------------------------------------------------------------


NOTE:

    Only "-01" revision Watchport Sensors are supported!

    To determine your Watchport sensor revision, look at the back of the
    Sensor for the "PN:" value.
    The PN value will be an 8 digital value, starting with "50".
    After those 8 digits, the revision of the Sensor will be given,
    starting with a "-".

"""

# imports

import math
import struct
from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

from common.types.boolean import Boolean, STYLE_YESNO, STYLE_ONOFF
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep \
    import CYCLIC_SLEEP_EXT_MAX_MS, SM_DISABLED, XBeeConfigBlockSleep
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *
from devices.xbee.common.io_sample import parse_is, sample_to_mv
from devices.xbee.common.prodid import PROD_DIGI_XB_ADAPTER_SENSOR

# constants

# exception classes

# interface functions


# classes

class XBeeWatchportSensor(XBeeBase):
    """\
        This class extends one of our base classes and is intended as an
        example of a concrete, example implementation, but it is not itself
        meant to be included as part of our developer API. Please consult the
        base class documentation for the API and the source code for this file
        for an example implementation.

    """
    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [[0xe8, 0xc105, 0x92], [0xe8, 0xc105, 0x11]]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [PROD_DIGI_XB_ADAPTER_SENSOR, ]

    def __init__(self, name, core_services, property_list):
        self.__name = name
        self.__core = core_services
        self.__property_list = property_list

        from core.tracing import get_tracer
        self._tracer = get_tracer(name)

        ## Local State Variables:
        self.__xbee_manager = None

        self.sensor = None

        # Settings
        #
        # xbee_device_manager: must be set to the name of an XBeeDeviceManager
        #                      instance.
        # extended_address: the extended address of the XBee Watchport Sensor
        #                   device you would like to monitor.
        # sleep: True/False setting which determines if we should put the
        #        device to sleep between samples.
        # sample_rate_ms: the sample rate of the XBee adapter.
        # enable_low_battery: Force an adapter to enable support for
        #                     battery-monitor pin.
        #                     It should be only enabled if adapter is using
        #                     internal batteries. Optional, Off by default.

        settings_list = [
            Setting(
                name='sleep', type=bool, required=False,
                default_value=False),
            Setting(
                name='sample_rate_ms', type=int, required=True,
                default_value=60000,
                verify_function=lambda x: x >= 0 and x <= CYCLIC_SLEEP_EXT_MAX_MS),

            # This setting is provided for advanced users, it is not required:
            Setting(
                name='awake_time_ms', type=int, required=False,
                default_value=5000,
                verify_function=lambda x: x >= 0 and x <= 0xffff),
            Setting(
                name='enable_low_battery', type=Boolean, required=False,
                default_value=Boolean("Off", STYLE_ONOFF)),
        ]

        ## Channel Properties Definition:
        __property_list_internal = [

        ]
        property_list.extend(__property_list_internal)

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

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

        for address in XBeeWatchportSensor.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeWatchportSensor.SUPPORTED_PRODUCTS:
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

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)


    def start(self):

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self, "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        # Get the extended address of the device:
        extended_address = SettingsBase.get_setting(self, "extended_address")

        # Retrieve the flag which tells us if we should sleep:

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec.cb_set(self.sample_indication)
        xbdm_rx_event_spec.match_spec_set(
            (extended_address, 0xe8, 0xc105, 0x92),
            (True, True, True, True))
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                xbdm_rx_event_spec)

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)

        # Get the gateway's extended address:
        gw_xbee_sh, gw_xbee_sl = gw_extended_address_tuple()

        # Set the destination for I/O samples to be the gateway:
        xbee_ddo_cfg.add_parameter('DH', gw_xbee_sh)
        xbee_ddo_cfg.add_parameter('DL', gw_xbee_sl)



        # if adapter is using internal batteries, then configure battery-monitor
        # pin and add low_battery channel
        if SettingsBase.get_setting(self, "enable_low_battery"):
            # configure battery-monitor pin DIO11/P1 for digital input
            xbee_ddo_cfg.add_parameter('P1', 3)
            # add low_battery channel
            self._tracer.info("Adapter is using internal batteries " +
                               "adding low_battery channel")
            self.add_property(
                ChannelSourceDeviceProperty(name="low_battery", type=bool,
                    initial=Sample(timestamp=0, value=False),
                    perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP))
        else:
            self._tracer.info("Adapter is not using internal batteries")

        ic = 0
        xbee_ddo_cfg.add_parameter('IC', ic)

        # Configure the IO Sample Rate:
        # Clip sample_rate_ms to the max value of IR:
        sample_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")
        sample_rate_ms = min(sample_rate_ms, 0xffff)
        xbee_ddo_cfg.add_parameter('IR', sample_rate_ms)

        # Register this configuration block with the XBee Device Manager:
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Setup the sleep parameters on this device:
        will_sleep = SettingsBase.get_setting(self, "sleep")
        awake_time_ms = SettingsBase.get_setting(self, "awake_time_ms")
        # The original sample rate is used as the sleep rate:
        sleep_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")
        xbee_sleep_cfg = XBeeConfigBlockSleep(extended_address)
        if will_sleep:
            xbee_sleep_cfg.sleep_cycle_set(awake_time_ms, sleep_rate_ms)
        else:
            xbee_sleep_cfg.sleep_mode_set(SM_DISABLED)
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_sleep_cfg)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        # Scheduling first request and watchdog heart beat poll,
        # but only if we aren't in sleep mode.
        if will_sleep != True:
            self.__schedule_request()
            self.__reschedule_retry_watchdog()

        return True

    def stop(self):

        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)

        return True


    ## Locally defined functions:

    def make_request(self):
        success = True
        self._tracer.debug("make_request")

        extended_address = SettingsBase.get_setting(self, "extended_address")

        try:
            sample = self.__xbee_manager.xbee_device_ddo_get_param(extended_address, '1S')
            self.__decode_sample(sample)
            self._tracer.debug("Successfully retrieved and decoded sample.")
        except TypeError:
            success = False
            self._tracer.error("Device driver does not match with connected hardware.")
            pass
        except:
            success = False
            self._tracer.warning("Xmission failure, will retry.")
            pass

        # Schedule another heart beat poll, but only if we aren't in sleep mode.
        will_sleep = SettingsBase.get_setting(self, "sleep")
        if will_sleep != True:
            self.__schedule_request()
            self.__reschedule_retry_watchdog()

        return success

    def __schedule_request(self):
        self._tracer.debug("__schedule_request")
        sample_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")
        self.__xbee_manager.xbee_device_schedule_after(
            sample_rate_ms / 1000, self.make_request)

    def __reschedule_retry_watchdog(self):
        self._tracer.debug("__reschedule_retry_watchdog")
        sample_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")
        try:
            if self.__retry_event:
                self.__xbee_manager.xbee_device_schedule_cancel(
                    self.__retry_event)
        except:
            pass

        self.__retry_event = \
            self.__xbee_manager.xbee_device_schedule_after(
                sample_rate_ms * 1000 * 1.5, self.retry_request)

    def retry_request(self):
        self._tracer.debug("retry_request")
        self.make_request()
        self.__reschedule_retry_watchdog()

    def sample_indication(self, buf, addr):
        #print "XBeeWatchport: Got sample indication from: %s, buf is len %d." \
        #    % (str(addr), len(buf))

        io_sample = parse_is(buf)

        # Low battery check (attached to DIO11/P1):
        if SettingsBase.get_setting(self, "enable_low_battery"):
            # Invert the signal it is actually not_low_battery:
            low_battery = not bool(io_sample["DIO11"])
            self.property_set("low_battery", Sample(0, low_battery))

        # If we are in sleep mode, request a sample right now while we are awake!
        will_sleep = SettingsBase.get_setting(self, "sleep")
        if will_sleep == True:
            self.make_request()

    def __decode_sample(self, sample):
        self.sensor.parse_sample(sample)



    class XBeeSensor:
        def __init__(self):
            pass

        class _1SSample:
            AD_VDD     = 5.1  # Supply voltage to the A/D converter
            AD_BITMASK = 0xff # Bit mask for the A/D (here, 8-bits)

            def __init__(self, sample):
                # Intialize our attributes:
                self.sample = []
                self.sensors = 0
                self.ad_sample = [None] * 4
                self.temperature = None

                # Do the parsing:
                self.sample = struct.unpack("!B4HH", sample)
                self.sensors = self.sample[0]

                ad_to_v = lambda ad: (ad / float(self.AD_BITMASK)) * self.AD_VDD

                if self.has_ad():
                    self.ad_sample = []
                    self.ad_sample.append(ad_to_v(self.sample[1]))
                    self.ad_sample.append(ad_to_v(self.sample[2]))
                    self.ad_sample.append(ad_to_v(self.sample[3]))
                    self.ad_sample.append(ad_to_v(self.sample[4]))

                if self.has_temperature():
                    temp = struct.pack('>h', ~self.sample[5])
                    self.temperature = ~struct.unpack('>h', temp)[0] / 16.0

            def __repr__(self):
                str = "<_1SSample"
                if self.has_temperature():
                    str += " Temp: y (%f)" % (self.temperature)
                else:
                    str += " Temp: n"
                if self.has_ad():
                    str += " A/D: y (%s)" % (self.ad_sample)
                else:
                    str += " A/D: n"
                str += ">"
                return str

            def has_ad(self):
                if self.sensors & 0x01:
                    return True
                return False

            def has_temperature(self):
                if self.sensors & 0x02:
                    return True
                return False

            def ad_sample_to_v(self, ad_sample):
                return (ad_sample / float(self.AD_BITMASK)) * self.AD_VDD

        def parse_sample(self, sample):
            return self._1SSample(sample)

    class XBeeWatchportA(XBeeSensor):
        V_DD = 5.00
        SENSITIVITY = 0.312

        def __init__(self):
            # Initialize our attributes:
            self.xout = 0
            self.yout = 0
            self.pitch = 0
            self.roll = 0

            # Initialize private variables:
            self._calibration_xout = 0
            self._calibration_yout = 0

            XBeeWatchportSensor.XBeeSensor.__init__(self)

        def __repr__(self):
            return "<XBeeWatchportA xout=%f yout=%f pitch=%f roll=%f>" % \
                (self.xout, self.yout, self.pitch, self.roll)

        def set_0g_calibration(self, sample):
            calibration = self.parse_sample(sample, False)
            self._calibration_xout = -calibration.xout
            self._calibration_yout = -calibration.yout
            self.xout = 0
            self.yout = 0
            self.pitch = 0
            self.roll = 0

        def parse_sample(self, sample):
            sample_obj = XBeeWatchportSensor.XBeeSensor.parse_sample(self, sample)

            if not sample_obj.has_ad():
                raise ValueError, "Given sample has no A/D values."

            v_to_g = lambda v: (v - (self.V_DD / 2)) / self.SENSITIVITY
            self.xout = ( v_to_g(sample_obj.ad_sample[3]) +
                        self._calibration_xout )
            self.yout = ( v_to_g(sample_obj.ad_sample[2]) +
                        self._calibration_yout )

            # Function to clip a value x between -1 <= x <= 1:
            clip = lambda x: [[x, -1][x < -1], 1][x > 1]

            # Calculate pitch and roll:
            self.pitch = math.degrees(math.asin(clip(self.xout)))
            self.roll = math.degrees(math.asin(clip(self.yout)))

            return self

    class XBeeWatchportD(XBeeSensor):
        def __init__(self):
            # Initialize our attributes:
            self.distance = 0

            XBeeWatchportSensor.XBeeSensor.__init__(self)

        def __repr__(self):
            return "<XBeeWatchportD distance=%f>" % (self.distance)

        def parse_sample(self, sample):
            sample_obj = XBeeWatchportSensor.XBeeSensor.parse_sample(self, sample)

            # Calculate distance:
            v = sample_obj.ad_sample[3]
            if v <= 0.43:
                self.distance = 150.0
            elif v >= 2.5:
                self.distance = 20.0
            else:
                # This function was derived from performing a regression
                # on observed data, it is only an approximation:
                self.distance = 61.442 * math.pow(v, -1.073)

            return self

    class XBeeWatchportH(XBeeSensor):
        def __init__(self):
            # Initialize our attributes:
            self.sensor_rh = 0
            self.true_rh = 0
            self.temperature = 0

            XBeeWatchportSensor.XBeeSensor.__init__(self)

        def __repr__(self):
            return "<XBeeWatchportH sensor_rh=%f true_rh=%f temperature=%f>" % \
                    (self.sensor_rh, self.true_rh, self.temperature)

        def parse_sample(self, sample):
            sample_obj = XBeeWatchportSensor.XBeeSensor.parse_sample(self, sample)

            v_supply = sample_obj.ad_sample[2]
            v_output = sample_obj.ad_sample[3]

            # These equations are given by the HIH-3610 series datasheet:
            self.sensor_rh = (1 / 0.0062) * ((v_output / v_supply) - 0.16)
            self.true_rh = self.sensor_rh / (1.0546 - (0.00216 * sample_obj.temperature))
            self.temperature = sample_obj.temperature

            return self

    class XBeeWatchportT(XBeeSensor):
        def  __init__(self):
            self.temperature = 0

            XBeeWatchportSensor.XBeeSensor.__init__(self)

        def __repr__(self):
            return "<XBeeWatchportT temperature=%f>" % (self.temperature)

        def parse_sample(self, sample):
            sample_obj = XBeeWatchportSensor.XBeeSensor.parse_sample(self, sample)
            self.temperature = sample_obj.temperature
            return self

    class XBeeWatchportW(XBeeSensor):
        def __init__(self):
            self.water = False

            XBeeWatchportSensor.XBeeSensor.__init__(self)

        def __repr__(self):
             return "<XBeeWatchportW Water present=%s>"%(self.water)

        def parse_sample(self, sample):
            if ord(sample[0]) & 128:
                self.water = True
            else:
                self.water = False
            return self





class XBeeWatchportSensorT(XBeeWatchportSensor):
    def __init__(self, name, core_services):

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="temperature", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="C"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]

        XBeeWatchportSensor.__init__(self, name, core_services, property_list)
        self.sensor = XBeeWatchportSensor.XBeeWatchportT()

    def make_request(self):
        self._tracer.debug("make_request")
        success = XBeeWatchportSensor.make_request(self)

        if success:
            self.property_set("temperature", Sample(0, float(self.sensor.temperature), "C"))




class XBeeWatchportSensorH(XBeeWatchportSensor):
    def __init__(self, name, core_services):

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="temperature", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="C"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="sensor_rh", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="%"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="true_rh", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="%"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]

        XBeeWatchportSensor.__init__(self, name, core_services, property_list)
        self.sensor = XBeeWatchportSensor.XBeeWatchportH()

    def make_request(self):
        self._tracer.debug("make_request")
        success = XBeeWatchportSensor.make_request(self)

        if success:
            self.property_set("temperature", Sample(0, float(self.sensor.temperature), "C"))
            self.property_set("sensor_rh", Sample(0, float(self.sensor.sensor_rh), "%"))
            self.property_set("true_rh", Sample(0, float(self.sensor.true_rh), "%"))



class XBeeWatchportSensorD(XBeeWatchportSensor):
    def __init__(self, name, core_services):

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="distance", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="cm"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]
        XBeeWatchportSensor.__init__(self, name, core_services, property_list)
        self.sensor = XBeeWatchportSensor.XBeeWatchportD()

    def make_request(self):
        self._tracer.debug("make_request")
        success = XBeeWatchportSensor.make_request(self)

        if success:
            self.property_set("distance", Sample(0, float(self.sensor.distance), "cm"))

class XBeeWatchportSensorA(XBeeWatchportSensor):
    def __init__(self, name, core_services):

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="xout", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="in"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="yout", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="in"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="pitch", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="in"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="roll", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="in"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]
        XBeeWatchportSensor.__init__(self, name, core_services, property_list)
        self.sensor = XBeeWatchportSensor.XBeeWatchportA()

    def make_request(self):
        self._tracer.debug("make_request")
        success = XBeeWatchportSensor.make_request(self)

        if success:
            self.property_set("xout", Sample(0, float(self.sensor.xout), "?"))
            self.property_set("yout", Sample(0, float(self.sensor.yout), "?"))
            self.property_set("pitch", Sample(0, float(self.sensor.pitch), "?"))
            self.property_set("roll", Sample(0, float(self.sensor.roll), "?"))



class XBeeWatchportSensorW(XBeeWatchportSensor):
    def __init__(self, name, core_services):

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="water", type=bool,
                initial=Sample(timestamp=0, value=False),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]
        XBeeWatchportSensor.__init__(self, name, core_services, property_list)
        self.sensor = XBeeWatchportSensor.XBeeWatchportW()

    def make_request(self):
        self._tracer.debug("make_request")
        success = XBeeWatchportSensor.make_request(self)

        if success:
            self.property_set("water", Sample(0, bool(self.sensor.water)))


# internal functions & classes
