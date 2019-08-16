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
A DIA Driver for the XBee Analog IO on the Coordinator
"""

# imports
import digihw
from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.types.boolean import Boolean, STYLE_ONOFF
from common.digi_device_info import query_state, get_platform_name

from devices.xbee.common.prodid \
    import MOD_XB_802154, MOD_XB_ZNET25, MOD_XB_ZB, MOD_XB_S2C_ZB, parse_dd
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep \
    import CYCLIC_SLEEP_EXT_MAX_MS, SM_DISABLED, XBeeConfigBlockSleep
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *

from devices.xbee.common.io_sample import parse_is

# constants


# exception classes

# interface functions

# classes
class XBeeLocalAIO(XBeeBase):
    """\
        This class extends one of our base classes and is intended as an
        example of a concrete, example implementation, but it is not itself
        meant to be included as part of our developer API. Please consult the
        base class documentation for the API and the source code for this file
        for an example implementation.

    """
    LOCAL_AIO_CONTROL_LINES = [ "d0", "d1", "d2", "d3" ]

    LOCAL_AIO_MODE_CURRENTLOOP = "CurrentLoop"
    LOCAL_AIO_MODE_TENV = "TenV"

    LOCAL_AIO_MODE_MAP = { LOCAL_AIO_MODE_CURRENTLOOP.lower(): LOCAL_AIO_MODE_CURRENTLOOP,
                 LOCAL_AIO_MODE_TENV.lower(): LOCAL_AIO_MODE_TENV }

    LOCAL_AIO_LOOP_R_OHMS = 51.3
    LOCAL_AIO_TENV_SCALE = 3.3 / 28.2

    LOCAL_AIO_CALIBRATION_06 = 511.5
    LOCAL_AIO_CALIBRATION_10 = 853.333

    LOCAL_AIO_R1_STRAPPING_A = '0048'
    LOCAL_AIO_R1_STRAPPING_B = '0049'

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Local State Variables:
        self.__xbee_manager = None

        self.__OLD_HARDWARE = False
        self.__scale = 0.0
        self.__offset = 0.0

        # Force a calibration every read.
        self.__calibration_interval = 0
        self.__calibration_time = -self.__calibration_interval

        self.__lock = threading.Lock()

        # Settings
        #
        # xbee_device_manager: must be set to the name of an XBeeDeviceManager
        #                      instance.
        # sample_rate_ms: the sample rate of the XBee adapter.
        # channel1_mode: Operating input mode for pin 1 of the adapter.
        #                Must be a string value comprised of one of the following:
        #                    "TenV" - 0-10v input available on any channel.
        #                    "CurrentLoop" - 0-20 mA current loop available on
        #                                    any channel.
        # channel2_mode: Operating input mode for pin 2 of the adapter.
        #                See channel1_mode for valid setting information.
        # channel3_mode: Operating input mode for pin 3 of the adapter.
        #                See channel1_mode for valid setting information.
        # channel4_mode: Operating input mode for pin 4 of the adapter.
        #                See channel1_mode for valid setting information.

        settings_list = [
            # Setting( This is in xbee_base!
            #    name='extended_address', type=str, required=False,
            #    default_value=''),
            Setting(
                name='sample_rate_ms', type=int, required=True,
                default_value=60000,
                verify_function=lambda x: x >= 0 and x <= CYCLIC_SLEEP_EXT_MAX_MS),
            Setting(
                name='channel1_mode', type=str, required=False,
                verify_function=_verify_channel_mode,
                default_value=self.LOCAL_AIO_MODE_TENV),
            Setting(
                name='channel2_mode', type=str, required=False,
                verify_function=_verify_channel_mode,
                default_value=self.LOCAL_AIO_MODE_TENV),
            Setting(
                name='channel3_mode', type=str, required=False,
                verify_function=_verify_channel_mode,
                default_value=self.LOCAL_AIO_MODE_TENV),
            Setting(
                name='channel4_mode', type=str, required=False,
                verify_function=_verify_channel_mode,
                default_value=self.LOCAL_AIO_MODE_TENV),

        ]

        ## Channel Properties Definition:
        property_list = [
            ChannelSourceDeviceProperty(name="channel1_value", type=float,
                initial=Sample(timestamp=0, unit="V", value=0.0),
                perms_mask=DPROP_PERM_GET|DPROP_PERM_REFRESH, options=DPROP_OPT_AUTOTIMESTAMP,
                refresh_cb = self.refresh),
            ChannelSourceDeviceProperty(name="channel2_value", type=float,
                initial=Sample(timestamp=0, unit="V", value=0.0),
                perms_mask=DPROP_PERM_GET|DPROP_PERM_REFRESH, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="channel3_value", type=float,
                initial=Sample(timestamp=0, unit="V", value=0.0),
                perms_mask=DPROP_PERM_GET|DPROP_PERM_REFRESH, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="channel4_value", type=float,
                initial=Sample(timestamp=0, unit="V", value=0.0),
                perms_mask=DPROP_PERM_GET|DPROP_PERM_REFRESH, options=DPROP_OPT_AUTOTIMESTAMP),
        ]
                                            
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

        return XBeeBase.probe()

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # there were problems with settings, terminate early:
            self.__tracer.error("Settings rejected/not found: %s %s", 
                                rejected, not_found)
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self, "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Attempt to detect if we are on older units that require a different
        # algorithm for determine calibration.
        try:
            device_info = query_state("device_info")
            for item in device_info:
                hardware_strapping = item.find('hardwarestrapping')
                if hardware_strapping != None:
                    hardware_strapping = hardware_strapping.text
                    break
            else:
                hardware_strapping = ''

            if hardware_strapping == self.LOCAL_AIO_R1_STRAPPING_A or hardware_strapping == self.LOCAL_AIO_R1_STRAPPING_B:
                self.__tracer.info("Old hardware detected. Turning on old support flag.")
                self.__OLD_HARDWARE = True
        except:
            pass

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        # Create a callback specification that calls back this driver when
        # our device has left the configuring state and has transitioned
        # to the running state:
        xbdm_running_event_spec = XBeeDeviceManagerRunningEventSpec()
        xbdm_running_event_spec.cb_set(self.running_indication)
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                                        xbdm_running_event_spec)

        extended_address = None

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)

        for io_pin in range(4):
            # I/O pin for analog input:
            xbee_ddo_cfg.add_parameter('D%d' % (io_pin), 2)

            mode = SettingsBase.get_setting(self, 'channel%d_mode' % (io_pin+1) )
            mode = self.LOCAL_AIO_MODE_MAP[mode.lower()]

            if mode == self.LOCAL_AIO_MODE_CURRENTLOOP:
                digihw.configure_channel(io_pin, 1)
                xbee_ddo_cfg.add_parameter(self.LOCAL_AIO_CONTROL_LINES[io_pin], 2)
            elif mode == self.LOCAL_AIO_MODE_TENV:
                digihw.configure_channel(io_pin, 2)
                xbee_ddo_cfg.add_parameter(self.LOCAL_AIO_CONTROL_LINES[io_pin], 2)
            
        # Register this configuration block with the XBee Device Manager:
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        return True

    def stop(self):

        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)

        return True


    def refresh(self):
        if not self.__lock.acquire(False):
                self.__tracer.warning("Sample is already in process.")
                return
        else:
            try:
                self.__make_request()
            finally:
                self.__lock.release()


    def make_request(self):
        self.__tracer.debug("make_request")
        self.__lock.acquire()
        try:
            self.__make_request()
        finally:
            self.__lock.release()

        # Schedule another heart beat poll.
        self.__schedule_request()
        self.__reschedule_retry_watchdog()


    def __make_request(self):
        self.__tracer.debug("__make_request")

        # Calibrate every Calibration Interval seconds
        now = digitime.real_clock()
        self.__tracer.debug("Time is %f, calibration_time is %f",
                            now, self.__calibration_time)
        if now >= self.__calibration_time + self.__calibration_interval or now < self.__calibration_time:
            try:
                self.__calibrate()
            except Exception, e:
                pass

        try:
            sample = self.__xbee_manager.xbee_device_ddo_get_param(None, 'IS')
            self.__decode_sample(sample)
            self.__tracer.debug("Successfully retrieved and decoded sample.")
        except:
            self.__tracer.warning("Xmission failure, will retry.")
            pass

    def __schedule_request(self):
        self.__tracer.debug("Scheduling request")
        sample_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")
        self.__xbee_manager.xbee_device_schedule_after(
            sample_rate_ms / 1000, self.make_request)


    def __reschedule_retry_watchdog(self):
        self.__tracer.debug("Reschedule watchdog")
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
        self.__tracer.debug("Retry request.")
        self.make_request()
        self.__reschedule_retry_watchdog()

    def running_indication(self):
        # Our device is now running, load our initial state:
        self.__tracer.info("Running indication")
        self.make_request()

    def sample_indication(self, buf, addr):
        self.__tracer.info("Got sample indication from: %s, buf is len %d.",
                           str(addr), len(buf))
        self.__decode_sample(buf)


    def __decode_sample(self, buf):
        io_sample = parse_is(buf)

        for aio_num in range(4):
            aio_name = "AD%d" % (aio_num)
            channel_name = "channel%d_value" % (aio_num+1)
            channel_mode = SettingsBase.get_setting(self,
                                "channel%d_mode" % (aio_num+1))
            channel_mode = channel_mode.lower()
            channel_mode = self.LOCAL_AIO_MODE_MAP[channel_mode.lower()]

            if aio_name not in io_sample:
                continue

            raw_value = io_sample[aio_name]
            raw_value = raw_value * self.__scale

            # Don't reduce the raw_value by the offset if the raw_value is 1023.
            if self.__offset != 0.0 and raw_value < 1023:
                raw_value = raw_value - self.__offset

            raw_value = int(round(raw_value))

            if channel_mode == self.LOCAL_AIO_MODE_CURRENTLOOP:
                mV = raw_value * 1200.0 / 1023
                mA = mV / self.LOCAL_AIO_LOOP_R_OHMS

                # If we have gone negative by a tiny bit, which can happen
                # because of scaling, just set us back to 0.0.
                if mA < 0.0:
                    mA = 0.0

                self.property_set(channel_name, Sample(0, mA, "mA"))
            elif channel_mode == self.LOCAL_AIO_MODE_TENV:
                V = float(raw_value) * 1.2 / 1024.0 / self.LOCAL_AIO_TENV_SCALE
                self.property_set(channel_name, Sample(0, V, "V"))


    def __calibrate(self):
        """__calibrate()
        Calibrate analog inputs. Calculates scale and offset."""

        xbee_dd_ddo_value = self.__xbee_manager.xbee_device_ddo_get_param(None,
                            'DD', use_cache=True)
        module_id, product_id = parse_dd(xbee_dd_ddo_value)

        # XBee series 1 uses one calibration voltage on AN2
        if module_id == MOD_XB_802154:

            # Enable calibration voltage on channel 1
            self.__xbee_manager.xbee_device_ddo_set_param(None, 'D4', 4,
                                apply=True)
            digitime.sleep(0.010)

            # Read calibration sample
            result = self.__xbee_manager.xbee_device_ddo_get_param(None, 'IS')
            sample = parse_is(result)["AD1"]
            self.__tracer.debug("Calibration sample is %d", sample)

            # Return channel to operating mode
            self.__xbee_manager.xbee_device_ddo_set_param(None, 'D4', 5,
                                apply=True)
            digitime.sleep(0.010) 

            if sample == 0:
                raise ValueError, "Calibration error: bad sample"

            # Calulate linear scale and offset.
            # These apply to all analog channels.
            self.__scale = 1.25 / sample
            self.__offset = 0

        # XBee series 2 uses two calibration voltages on AN1 and AN2
        elif module_id == MOD_XB_ZNET25 or module_id == MOD_XB_ZB or module_id == MOD_XB_S2C_ZB:

            # Enable calibration voltages on channels 0 and 1
            if get_platform_name() == 'digix3':
                self.__xbee_manager.xbee_device_ddo_set_param(None, 
                            self.LOCAL_AIO_CONTROL_LINES[0], 2, apply=True)
                self.__xbee_manager.xbee_device_ddo_set_param(None,
                            self.LOCAL_AIO_CONTROL_LINES[1], 2, apply=True)
                digihw.gpio_set_value(0, 0)
            elif get_platform_name() == 'digiconnect':
                self.__xbee_manager.xbee_device_ddo_set_param(None, 'P2', 4,
                                    apply=True)
                self.__xbee_manager.xbee_device_ddo_set_param(None, 'D4', 4, 
                                    apply=True)

            digitime.sleep(0.010)

            # Read calibration samples
            result = self.__xbee_manager.xbee_device_ddo_get_param(None, 'IS')
            data = parse_is(result)
            sample = [ data["AD0"], data["AD1"] ]

            self.__tracer.debug("Calibration samples are %d, %d", 
                               sample[0], sample[1])

            # Return channels to operating mode
            if get_platform_name() == 'digix3':
                digihw.gpio_set_value(0, 1)
            elif get_platform_name() == 'digiconnect':
                self.__xbee_manager.xbee_device_ddo_set_param(None, 'P2', 5,
                                    apply=True)
                self.__xbee_manager.xbee_device_ddo_set_param(None, 'D4', 5,
                                    apply=True)

            digitime.sleep(0.010)

            for io_pin in range(2):
                mode = SettingsBase.get_setting(self, 'channel%d_mode' % (io_pin+1) )
                mode = self.LOCAL_AIO_MODE_MAP[mode.lower()]

                if mode == self.LOCAL_AIO_MODE_CURRENTLOOP:
                    self.__xbee_manager.xbee_device_ddo_set_param(None,
                           self.LOCAL_AIO_CONTROL_LINES[io_pin], 2, apply=True)
                elif mode == self.LOCAL_AIO_MODE_TENV:
                    self.__xbee_manager.xbee_device_ddo_set_param(None,
                           self.LOCAL_AIO_CONTROL_LINES[io_pin], 2, apply=True)

            if sample[0] == sample[1]:
                raise ValueError, "Calibration error: equal samples"

            self.__sample1 = sample[1]
            self.__sample2 = sample[0]

            scale1 = self.LOCAL_AIO_CALIBRATION_06 / float(sample[1])
            scale2 = self.LOCAL_AIO_CALIBRATION_10 / float(sample[0])

            self.__scale = (scale1 + scale2) / 2.0

            if self.__OLD_HARDWARE == True:
                self.__offset = (self.__sample1 *
                       self.__scale - self.LOCAL_AIO_CALIBRATION_06) * 2.4
            else:
                self.__offset = 0.0

        else:
            raise ValueError, "XBee does not support analog inputs"

        self.__calibration_time = digitime.real_clock()

        self.__tracer.debug("Scale is %f, offset is %f", 
                            self.__scale, self.__offset)


# internal functions & classes

def _verify_channel_mode(mode):
    if mode.lower() not in XBeeLocalAIO.LOCAL_AIO_MODE_MAP:
        raise ValueError, "Invalid mode '%s': must be one of %s" % \
            (mode, XBeeLocalAIO.LOCAL_AIO_MODE_MAP.values())

