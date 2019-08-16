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
A DIA Driver for the XBee Analog IO Adapter
"""

# Hardware details as of June 2009
# XBee.D0  = ADC #1, so ddo_set to 0x02
# XBee.D1  = ADC #2, so ddo_set to 0x02
# XBee.D2  = ADC #3, so ddo_set to 0x02
# XBee.D3  = ADC #4, so ddo_set to 0x02
# XBee.D4  = select AIN conditioning, so ddo_set to 0x04 or 0x05
# XBee.D5  =
# XBee.D6  = select AIN conditioning, so ddo_set to 0x04 or 0x05
# XBee.D7  = select AIN conditioning, so ddo_set to 0x04 or 0x05
# XBee.D8  = select AIN conditioning, so ddo_set to 0x04 or 0x05

# XBee.P0  = select AIN conditioning, so ddo_set to 0x04 or 0x05
# XBee.P2  = select AIN conditioning, so ddo_set to 0x04 or 0x05

# imports
from devices.xbee.xbee_devices.xbee_base import XBeeBase
import devices.xbee.common.bindpoints as bindpoints
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.types.boolean import Boolean, STYLE_ONOFF

from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep \
    import CYCLIC_SLEEP_EXT_MAX_MS
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *

from devices.xbee.common.io_sample import parse_is
from devices.xbee.common.prodid \
    import MOD_XB_ZB, MOD_XB_S2C_ZB, PROD_DIGI_XB_ADAPTER_AIO

# constants

AIO_CONTROL_LINES = [  # A     B
                      ["d4", "d8"],
                      ["d6", "d8"],
                      ["d7", "p0"],
                      ["p2", "p0"],
                    ]

AIO_LINE_A = 0
AIO_LINE_B = 1

AIO_MODE_OFF = "Off"
AIO_MODE_CURRENTLOOP = "CurrentLoop"
AIO_MODE_TENV = "TenV"
AIO_MODE_DIFFERENTIAL = "Differential"

AIO_MODE_MAP = {AIO_MODE_OFF.lower(): AIO_MODE_OFF,
                AIO_MODE_CURRENTLOOP.lower(): AIO_MODE_CURRENTLOOP,
                AIO_MODE_TENV.lower(): AIO_MODE_TENV,
                AIO_MODE_DIFFERENTIAL.lower(): AIO_MODE_DIFFERENTIAL}

AIO_LOOP_R_OHMS = 51.1

# With all calibration firmware, the midpoints are now dead center.
AIO_DIFFERENTIAL_MIDPOINT_CHANNEL0 = 512.0
AIO_DIFFERENTIAL_MIDPOINT_CHANNEL2 = 512.0
AIO_DIFFERENTIAL_MAX = 2.54
AIO_DIFFERENTIAL_MIN = -2.352

# exception classes

# interface functions


# classes
class XBeeAIO(XBeeBase):
    '''
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.
    '''
    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [bindpoints.SERIAL, bindpoints.SAMPLE]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [PROD_DIGI_XB_ADAPTER_AIO, ]

    # avoid needlessly trashing strings
    CHN_MODE_NAME = ("channel1_mode", "channel2_mode", 
                        "channel3_mode", "channel4_mode" )
    CHN_VALUE_NAME = ("channel1_value", "channel2_value", 
                        "channel3_value", "channel4_value" )
                                                
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
        

        # Settings
        #
        # sleep: True/False setting which determines if we should put the
        #        device to sleep between samples.
        # sample_rate_ms: the sample rate of the XBee adapter.
        # power: True/False setting to enable/disable the power output
        #        on terminal 6 of the adapter.
        #
        # raw_value: On/Off; On makes output sample raw binary, Off for scaled
        #            output.  Defaults to Off/False.
        # zero_clamp: min raw binary setting to call zero; if zero is disabled,
        #             else forces low values to zero.
        # channel1_mode: Operating input mode for pin 1 of the adapter.
        #                Must be a string value comprised of one of
        #                the following:
        #                "TenV" - 0-10v input available on any channel.
        #                "CurrentLoop" - 0-20 mA current loop available on
        #                                any channel.
        #                "Differential" - +/- 2.4a differential current mode
        #                                 enabled on channel1 & channel2 or
        #                                 channel3 & channel4.
        # channel2_mode: Operating input mode for pin 2 of the adapter.
        #                See channel1_mode for valid setting information.
        # channel3_mode: Operating input mode for pin 3 of the adapter.
        #                See channel1_mode for valid setting information.
        # channel4_mode: Operating input mode for pin 4 of the adapter.
        #                See channel1_mode for valid setting information.
        # awake_time_ms: How many milliseconds should the device remain
        #                awake after waking from sleep.
        # sample_predelay: How long, in milliseconds, to wait after waking
        #                  up from sleep before taking a sample from the
        #                  inputs.
        # enable_low_battery: Force an adapter to enable support for
        #                     battery-monitor pin.
        #                     It should be only enabled if adapter is using
        #                     internal batteries. Optional, Off by default.
        settings_list = [
            Setting(
                name='sleep', type=bool, required=False,
                default_value=False),
            Setting(
                name='sample_rate_ms', type=int, required=False,
                default_value=60000,
                verify_function=lambda x: x >= 0 and \
                                x <= CYCLIC_SLEEP_EXT_MAX_MS),
            Setting(
                name='power', type=Boolean, required=False,
                default_value=Boolean("On", STYLE_ONOFF)),
            Setting(
                name='raw_value', type=Boolean, required=False,
                default_value=Boolean("Off", STYLE_ONOFF)),
            Setting(
                name='zero_clamp', type=int, required=False,
                default_value=0, verify_function=lambda x: x >= 0),
            Setting(
                name=self.CHN_MODE_NAME[0], type=str, required=False,
                verify_function=_verify_channel_mode,
                default_value=AIO_MODE_TENV),
            Setting(
                name=self.CHN_MODE_NAME[1], type=str, required=False,
                verify_function=_verify_channel_mode,
                default_value=AIO_MODE_TENV),
            Setting(
                name=self.CHN_MODE_NAME[2], type=str, required=False,
                verify_function=_verify_channel_mode,
                default_value=AIO_MODE_TENV),
            Setting(
                name=self.CHN_MODE_NAME[3], type=str, required=False,
                verify_function=_verify_channel_mode,
                default_value=AIO_MODE_TENV),

            # These settings are provided for advanced users, they are
            # not required:
            Setting(
                name='awake_time_ms', type=int, required=False,
                default_value=5000,
                verify_function=lambda x: x >= 0 and x <= 0xffff),
            Setting(
                name='sample_predelay', type=int, required=False,
                default_value=1000,
                verify_function=lambda x: x >= 0 and x <= 0xffff),
            Setting(
                name='enable_low_battery', type=Boolean, required=False,
                default_value=Boolean("Off", STYLE_ONOFF)),
        ]
        # Add our settings_list entries into the settings passed to us.
        set_in = self.merge_settings(set_in, settings_list)

        ## Channel Properties Definition:
        property_list = [
            ChannelSourceDeviceProperty(name=self.CHN_VALUE_NAME[0], type=float,
                initial=Sample(timestamp=0, unit="V", value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name=self.CHN_VALUE_NAME[1], type=float,
                initial=Sample(timestamp=0, unit="V", value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name=self.CHN_VALUE_NAME[2], type=float,
                initial=Sample(timestamp=0, unit="V", value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name=self.CHN_VALUE_NAME[3], type=float,
                initial=Sample(timestamp=0, unit="V", value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]

        # Add our property_list entries into the properties passed to us.
        prop_in = self.merge_properties(prop_in, property_list)

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, name, core_services, set_in, prop_in)

        self._tracer.calls("XBeeAIO.__init__()")

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

        for address in XBeeAIO.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeAIO.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):

        self._tracer.calls("XBeeAIO.apply_settings()")
    
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
                                "when added together cannot exceed " +
                                "65535.", accepted['sample_predelay'],
                                accepted['awake_time_ms'])

            rejected['awake_time_ms'] = accepted['awake_time_ms']
            del accepted['awake_time_ms']
            rejected['sample_predelay'] = accepted['sample_predelay']
            del accepted['sample_predelay']
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):

        self._tracer.calls("XBeeAIO.start()")

        # init self._xbee_manager and self._extended_address
        # then register ourself with our Xbee manager
        XBeeBase.pre_start(self)

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        self._xbee_manager.register_sample_listener(self, self._extended_address,
                                                     self.sample_indication)

        # XBeeBase.pre_start(self) enables self.running_indication

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(self._extended_address)

        for io_pin in range(4):
            # I/O pin for analog input:
            xbee_ddo_cfg.add_parameter('D%d' % (io_pin), 2)

            mode = SettingsBase.get_setting(self,
                                            self.CHN_MODE_NAME[io_pin])
            mode = AIO_MODE_MAP[mode.lower()]

            if io_pin % 2 == 1:
                last_mode = SettingsBase.\
                            get_setting(self, 'channel%d_mode' % (io_pin))
                last_mode = AIO_MODE_MAP[last_mode.lower()]

                if mode == AIO_MODE_DIFFERENTIAL:
                    if last_mode != AIO_MODE_DIFFERENTIAL:
                        raise ValueError("Differential mode may only "\
                                         "be set on odd channels.")
                    elif last_mode == AIO_MODE_DIFFERENTIAL:
                        # Nothing to do for this paired channel.
                        continue

                elif mode != AIO_MODE_DIFFERENTIAL and \
                    last_mode == AIO_MODE_DIFFERENTIAL:
                    raise ValueError("Unable to change mode, paired " \
                                     "channel is configured for "\
                                     "Differential operation.")

            if mode == AIO_MODE_CURRENTLOOP:
                xbee_ddo_cfg.add_parameter(
                    AIO_CONTROL_LINES[io_pin][AIO_LINE_A], 4)
                xbee_ddo_cfg.add_parameter(
                    AIO_CONTROL_LINES[io_pin][AIO_LINE_B], 4)
            elif mode == AIO_MODE_TENV:
                xbee_ddo_cfg.add_parameter(
                    AIO_CONTROL_LINES[io_pin][AIO_LINE_A], 5)
                xbee_ddo_cfg.add_parameter(
                    AIO_CONTROL_LINES[io_pin][AIO_LINE_B], 4)
            elif mode == AIO_MODE_DIFFERENTIAL:
                xbee_ddo_cfg.add_parameter(
                    AIO_CONTROL_LINES[io_pin][AIO_LINE_A], 4)
                xbee_ddo_cfg.add_parameter(
                    AIO_CONTROL_LINES[io_pin][AIO_LINE_B], 5)
                xbee_ddo_cfg.add_parameter(
                    AIO_CONTROL_LINES[io_pin + 1][AIO_LINE_A], 4)
            # else: for OFF, do nothing

            # TODO: in the future when we support changing the settings
            #       for this adapter on the fly we would need to do:
            #if previous_mode == Differential and new_mode != Differential:
            #    xbee_ddo_cfg.add_paramseter(
            #        (AIO_CONTROL_LINES[io_pin+1][AIO_LINE_A], 5))
            #    # TODO: Set setting for io_pin+1 to TenV Mode

        # if adapter is using internal batteries, then configure
        # battery-monitor pin and add low_battery channel
        if SettingsBase.get_setting(self, "enable_low_battery"):
            # configure battery-monitor pin DIO11/P1 for digital input
            xbee_ddo_cfg.add_parameter('P1', 3)
            # add low_battery channel
            self._tracer.info("adapter is using internal batteries... " +
                               "adding low battery channel")
            self.add_property(
                ChannelSourceDeviceProperty(name="low_battery", type=bool,
                    initial=Sample(timestamp=0, value=False),
                    perms_mask=DPROP_PERM_GET, \
                                            options=DPROP_OPT_AUTOTIMESTAMP))
        else:
            self._tracer.info("adapter is not using internal batteries.")

        # disable the triggered low-battery alarm since it causes problems
        # we see the value every time new values are sent anyway
        ic = 0
        xbee_ddo_cfg.add_parameter('IC', ic)

        # Assert input pull-ups
        xbee_ddo_cfg.add_parameter('PR', 0x1fff)

        # Is the unit meant to sleep or not?
        will_sleep = SettingsBase.get_setting(self, "sleep")

        # Configure the IO Sample Rate.
        #
        # This gets a little trickier in cases where the unit is NOT
        # in sleep mode, yet the sampling rate is over a minute.
        #
        # (The max value for IR is 64K and is in milliseconds.
        # This ends up being a tad over a minute.
        #
        # So if we are NOT in sleep mode, and our sample rate
        # is over 1 minute, 5 seconds (64K), we will set IR to 0,
        # and set up DIA (in the make_request call), to call us back
        # when our poll rate is about to trigger.

        # self._xbee_manager.get_sleep_block() manages 'IR'

        # Enable/disable power output on terminal 6:
        power = SettingsBase.get_setting(self, "power")
        if power:
            xbee_ddo_cfg.add_parameter('p3', 5)
        else:
            xbee_ddo_cfg.add_parameter('p3', 4)

        # Register this configuration block with the XBee Device Manager:
        self._xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Setup the sleep parameters on this device:
        will_sleep = SettingsBase.get_setting(self, "sleep")
        sample_predelay = SettingsBase.get_setting(self, "sample_predelay")
        awake_time_ms = (SettingsBase.get_setting(self, "awake_time_ms") +
                         sample_predelay)
        # The original sample rate is used as the sleep rate:
        sleep_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")

        xbee_sleep_cfg = self._xbee_manager.get_sleep_block(
            self._extended_address,
            sleep=will_sleep,
            sample_predelay=sample_predelay,
            awake_time_ms=awake_time_ms,
            sleep_rate_ms=sleep_rate_ms)

        self._xbee_manager.xbee_device_config_block_add(self, xbee_sleep_cfg)

        # we've no more to config, indicate we're ready to configure.
        return XBeeBase.start(self)

    # use XbeeBase.def stop(self):

    ## Locally defined functions:

    def running_indication(self):
        self._tracer.calls("XBeeAIO.running_indication()")
    
        # Our device is now running, load our initial state:
        self.make_request()
            
        return XBeeBase.running_indication(self)

    def make_request(self):
        self._tracer.calls("XBeeAIO.make_request()")

        will_sleep = SettingsBase.get_setting(self, "sleep")
        sample_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")
        
        if not will_sleep:
            try:
                io_sample = self.ddo_get_param('IS')
                self.sample_indication(io_sample, self._extended_address)
            except:
                self._tracer.warning("Xmission failure, will retry.")
                pass

        # Scheduling first request and watchdog heart beat poll,
        # but only if we aren't in sleep mode and .

        if will_sleep != True and sample_rate_ms > 0xffff:
            self.__schedule_request()
            self.__reschedule_retry_watchdog()

    def __schedule_request(self):
        self._tracer.calls("Scheduling request")
        sample_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")
        self._xbee_manager.xbee_device_schedule_after(
            sample_rate_ms / 1000, self.make_request)

    def __reschedule_retry_watchdog(self):
        self._tracer.calls("Reschedule watchdog")
        sample_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")
        try:
            if self.__retry_event:
                self._xbee_manager.xbee_device_schedule_cancel(
                    self.__retry_event)
        except:
            pass

        self.__retry_event = \
            self._xbee_manager.xbee_device_schedule_after(
                sample_rate_ms * 1000 * 1.5, self.retry_request)

    def retry_request(self):
        self._tracer.calls("Retry request.")
        self.make_request()

    def sample_indication(self, buf, addr):
    
        self._tracer.calls("XBeeAIO.sample_indication()")
        
        zero_clamp = SettingsBase.get_setting(self, "zero_clamp")

        # check if we want to scroll a trace line or not

        if self._tracer.info():
            # will be true for debug also
            msg = []
        else:
            msg = None

        raw_output = SettingsBase.get_setting(self, "raw_value")

        io_sample = parse_is(buf)
        if self._tracer.calls():
            self._tracer.calls('io_sample:%s', str(io_sample))

        for aio_num in range(4):
            aio_name = "AD%d" % (aio_num)
            channel_name = self.CHN_VALUE_NAME[aio_num]
            channel_mode = SettingsBase.get_setting(self,
                                self.CHN_MODE_NAME[aio_num])
            channel_mode = channel_mode.lower()
            channel_mode = AIO_MODE_MAP[channel_mode.lower()]

            if aio_name not in io_sample:
                continue

            if msg is not None:
                msg.append('%s=' % aio_name)

            raw_value = io_sample[aio_name]

            if zero_clamp and (raw_value < zero_clamp):
                # then user doesn't want to see low near-zero garbage
                raw_value = 0

            if channel_mode == AIO_MODE_OFF:
                # self.property_set(channel_name, Sample(0, 0, ""))
                if msg is not None:
                    msg.append('Off ')

            elif raw_output:
                # then just put the raw binary in the sample
                self.property_set(channel_name,
                                  Sample(0, float(raw_value), "raw"))
                if msg is not None:
                    msg.append('%04d ' % raw_value)

            elif channel_mode == AIO_MODE_CURRENTLOOP:
                mV = raw_value * 1200.0 / 1023
                mA = mV / AIO_LOOP_R_OHMS
                self.property_set(channel_name, Sample(0, mA, "mA"))
                if msg is not None:
                    msg.append('%0.2fmA ' % mA)

            elif channel_mode == AIO_MODE_TENV:
                V = (float(raw_value) / 1024) * 10.25
                self.property_set(channel_name, Sample(0, V, "V"))

                # msg.append('(%04d) ' % raw_value)
                if msg is not None:
                    msg.append('%0.2fV ' % V)

            elif channel_mode == AIO_MODE_DIFFERENTIAL:
                # Only report the even AIO channels, ie, 0 and 2.
                # We will replicate and report these values for the
                # odd AIO channels as well.
                if aio_num % 2:
                    continue

                mid = AIO_DIFFERENTIAL_MIDPOINT_CHANNEL0
                if aio_num == 2:
                    mid = AIO_DIFFERENTIAL_MIDPOINT_CHANNEL2

                V = 0
                if raw_value >= mid:
                    V = ((raw_value - mid) / (1023.0 - mid)) * \
                            AIO_DIFFERENTIAL_MAX
                else:
                    V = ((mid - raw_value) / mid) * AIO_DIFFERENTIAL_MIN

                self.property_set(channel_name, Sample(0, V, "V"))
                channel2_name = "channel%d_value" % (aio_num + 2)
                self.property_set(channel2_name, Sample(0, V, "V"))

                if msg is not None:
                    msg.append('%0.2fV ' % V)
                # msg.append('%s=%0,2fV ' % (aio_name+2, V))

        # Low battery check (attached to DIO11/P1):
        if SettingsBase.get_setting(self, "enable_low_battery"):
            # Invert the signal it is actually not_low_battery:
            low_battery = not bool(io_sample["DIO11"])
            self.property_set("low_battery", Sample(0, low_battery))
            if low_battery and msg is not None:
                msg.append('bat=LOW!')

        if msg is not None:
            self._tracer.info("".join(msg))


# internal functions & classes

def _verify_channel_mode(mode):
    if mode.lower() not in AIO_MODE_MAP:
        raise ValueError('Invalid mode "%s": must be one of %s' %
                         (mode, AIO_MODE_MAP.values()))
