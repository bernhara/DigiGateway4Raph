############################################################################
#                                                                          #
# Copyright (c)2010, Digi International (Digi). All Rights Reserved.       #
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
**XBee Local IO Driver**

A DIA Driver for XBee Analog and Digital IO on the Coordinator
"""

# imports
import digihw
from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_local_io.xbee_local_aio import XBeeLocalAIO
from devices.xbee.xbee_devices.xbee_local_io.xbee_local_dio import XBeeLocalDIO
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.digi_device_info import query_state
from devices.xbee.common.prodid \
    import MOD_XB_802154, MOD_XB_ZNET25, MOD_XB_ZB, MOD_XB_S2C_ZB, parse_dd
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *
from devices.xbee.common.io_sample import parse_is
from common.digi_device_info import get_platform_name

# constants

# exception classes

# interface functions

# classes
class XBeeLocalIO:

    OLD_HARDWARE_STRAPPING_A = '0048'
    OLD_HARDWARE_STRAPPING_B = '0049'

    def __init__(self, parent, core, aio_channels, dio_channels):
        self.__parent = parent
        self.__core = core
        self.__aio_channels = aio_channels
        self.__dio_channels = dio_channels

        # NOTE: If this is actually used anymore, and parent
        #       is the name of the actual module subclassing
        #       this, then the get_tracer() line should be
        #       changed to get_tracer(parent).
        
        # NOTE: MK: This is NOT the case.  The call from local_io.py is:
        #XBeeLocalIO(self, core_services,
        #            self.__analog_channels,
        #            self.__digital_channels)
        #
        # Meaning that the 'parent' parameter is the object, not the string 
        # name.  Changing it to parent.__Local_IO__name would work, but lets
        # not rely on the name mangling.
        
        from core.tracing import get_tracer
        self.__tracer = get_tracer('XBeeLocalIO')

        ## Local State Variables:

        self.__CALIBRATION_06 = 511.5
        self.__CALIBRATION_10 = 853.333
        self.__OLD_HARDWARE = False
        self.__scale = 0.0
        self.__offset = 0.0

        self.__calibration_interval = 0
        self.__calibration_time = 0

        self.__xbee_manager = None

        self.__aio_channel_structures = []
        self.__dio_channel_structures = []

        self.__request_events = []
        self.__request_refresh_events = []


    def start(self):
        """Start the device driver.  Returns bool."""

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

            if hardware_strapping == self.OLD_HARDWARE_STRAPPING_A or hardware_strapping == self.OLD_HARDWARE_STRAPPING_B:
                self.__tracer.info("Old hardware detected. " +
                                   "Turning on old support flag.")
                self.__OLD_HARDWARE = True
        except:
            pass

        # Grab the calibration rate setting, and store it
        self.__calibration_interval = SettingsBase.get_setting(self.__parent,
                                                   "calibration_rate_ms")

        self.__calibration_interval /= 1000.0

        # Force a calibration the first time getting samples.
        self.__calibration_time = -self.__calibration_interval

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self.__parent, "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Walk through the channels, allocating required channel types
        # and creating each channels respective channel properties.
        for channel in self.__aio_channels:
            channel_name = "channel%d" % (channel + 1)
            mode = SettingsBase.get_setting(self.__parent, 'channel%d_mode' % (channel + 1))
            aio_chan = XBeeLocalAIO(channel_name, self, channel, mode.lower())
            self.__aio_channel_structures.append(aio_chan)

        for channel in self.__dio_channels:
            channel_name = "channel%d" % (channel + 1)
            direction = SettingsBase.get_setting(self.__parent, 'channel%d_dir' % (channel + 1))
            direction = direction.lower()
            source = SettingsBase.get_setting(self.__parent, 'channel%d_source' % (channel + 1))
            source = source.lower()
            dio_chan = XBeeLocalDIO(channel_name, self, channel, direction.lower(), source)
            self.__dio_channel_structures.append(dio_chan)

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        # Create a callback specification that calls back this driver when
        # our device has left the configuring state and has transitioned
        # to the running state:
        xbdm_running_event_spec = XBeeDeviceManagerRunningEventSpec()
        xbdm_running_event_spec.cb_set(self.running_indication)
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                                        xbdm_running_event_spec)

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec.cb_set(self.sample_indication)
        # xbdm_rx_event_spec.match_spec_set((None,
        xbdm_rx_event_spec.match_spec_set((gw_extended_address(),
                0xe8, 0xc105, 0x92), (True, True, True, True))
        self.__xbee_manager.xbee_device_event_spec_add(self, xbdm_rx_event_spec)


        # Create a DDO configuration block for this device.
        # None indicates that we will be using the local radio.
        xbee_ddo_cfg = XBeeConfigBlockDDO(None)

        # Get the gateway's extended address:
        gw_xbee_sh, gw_xbee_sl = gw_extended_address_tuple()

        # Set the destination for I/O samples to be the gateway:
        xbee_ddo_cfg.add_parameter('DH', gw_xbee_sh)
        xbee_ddo_cfg.add_parameter('DL', gw_xbee_sl)

        # For the X3, aux power can be turned on/off.
        # For all other platforms, it is always on, and cannot be turned off.
        if get_platform_name() == 'digix3':
            power = SettingsBase.get_setting(self.__parent, "power")
            if power == Boolean(True, style = STYLE_ONOFF):
                xbee_ddo_cfg.add_parameter('d4', 5)
            elif power == Boolean(False, style=STYLE_ONOFF):
                xbee_ddo_cfg.add_parameter('d4', 4)

        # Call each channels start function to configure itself and start.
        # It will append any needed DDO commands to the 'xbee_ddo_cfg' block
        # we pass in.
        for channel in self.__aio_channel_structures:
            channel.start(xbee_ddo_cfg)

        for channel in self.__dio_channel_structures:
            channel.start(xbee_ddo_cfg)

        # Walk the digital channels again, if any are set to input,
        # we need to have the pin monitored.
        ic = 0
        for channel in self.__dio_channel_structures:
            if channel.mode() == "in":
                ic |= 1 << channel.channel()

        # Enable I/O line monitoring on pins DIO0 .. DIO3 &
        # enable change detection on DIO11:
        #
        # 0x   8    0    0
        #   1000 0000 0000 (b)
        #   DDDD DDDD DDDD
        #   IIII IIII IIII
        #   OOOO OOOO OOOO
        #   1198 7654 3210
        #   10
        #
        xbee_ddo_cfg.add_parameter('IC', ic)

        # Disable any periodic I/O sampling:
        xbee_ddo_cfg.add_parameter('IR', 0)

        # Register this configuration block with the XBee Device Manager:
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        return True


    def stop(self):
        """Stop the device driver.  Returns bool."""

        # Call each channel's stop function.
        for ch in self.__aio_channel_structures:
            ch.stop()
        for ch in self.__dio_channel_structures:
            ch.stop()

        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)

        return True


    def refresh(self):
        """\
            Attempt to refresh all our channels as soon as possible.
        """
        # Cancel any/all pending refresh requests.
        self.cancel_all_pending_refresh_requests()

        # Request a new event 1 second in the future, leaving intact any
        # any regularly scheduled events that are scheduled in the future.
        event = self.__xbee_manager.xbee_device_schedule_after(1,
                                                self.make_request)
        if event != None:
            self.__request_refresh_events.append(event)


    def schedule_request(self):
        """\
            Schedule a request to acquire samples for all our channels.
        """
        # Cancel any/all pending requests.
        self.cancel_all_pending_requests()

        # Request a new event at our poll rate in the future.
        sample_rate_ms = SettingsBase.get_setting(self.__parent, "sample_rate_ms")
        event = self.__xbee_manager.xbee_device_schedule_after(
            sample_rate_ms / 1000, self.make_request)
        if event != None:
            self.__request_events.append(event)


    def cancel_all_pending_requests(self):
        """\
        Attempt to cancel all/any pending request events still waiting
        to run for our device.
        """
        for event in self.__request_events:
            try:
                self.__xbee_manager.xbee_device_schedule_cancel(event)
            except:
                pass
        self.__request_events = []


    def cancel_all_pending_refresh_requests(self):
        """\
            Attempt to cancel all/any pending refresh request events still waiting
            to run for our device.
        """
        for event in self.__request_refresh_events:
            try:
                self.__xbee_manager.xbee_device_schedule_cancel(event)
            except:
                pass
        self.__request_refresh_events = []


    def make_request(self):
        """\
            Make a request to get all IO values from the local XBee radio.
        """
        self.__tracer.calls("make_request")

        # Trap any possible error here, as to make sure we are able to schedule
        # our next request.
        try:

            # Pure DIO units do not need calibration done.
            # So only do the calibration code if we have at least 1 AIO channel.
            if len(self.__aio_channel_structures) >= 1:
                # Calibrate every Calibration Interval seconds
                now = digitime.real_clock()
                # self.__tracer.debug("Time is %f, calibration_time is %f",
                #                    now, self.__calibration_time)
                if ((now >= self.__calibration_time + self.__calibration_interval) or
                    (now < self.__calibration_time)):
                    self.calibrate()

            # Request a sample from the local XBee Radio
            sample = self.__xbee_manager.xbee_device_ddo_get_param(None, 'IS')
            self.__decode_sample(sample)
                
        except Exception, e:
            self.__tracer.error("Grabbing IO values failed %s", str(e))
            pass

        # Always schedule our next poll, regardless of whether the
        # the previous poll worked or not.
        self.schedule_request()


    def running_indication(self):
        """\
        This function will be called by the DIA core when our device has left
        the configuring state and has transitioned to the running state.
        """
        self.__tracer.info("Running indication")
        # Force an initial sample to be grabbed.
        self.refresh()
        # Finally, schedule ourselves for a cyclical callback.
        self.schedule_request()


    def get_parent(self):
        """\
            Returns our stored parent value.
            This call is typically used by our children (channels),
            if they need access to one of the core DIA services.
        """
        return self.__parent


    def get_xbee_manager(self):
        """\
            Returns our stored xbee_manager value.
            This call is typically used by our children (channels), to register
            with, or talk to the system's xbee manager.
        """
        return self.__xbee_manager


    def sample_indication(self, buf, addr):
        self.__tracer.debug("Got sample indication from: %s, buf is len %d.",
                           str(addr), len(buf))
        self.__decode_sample(buf)


    def __decode_sample(self, buf):
        """\
            Given raw sample data from our device, break it down, and send
            that result to each of our channels.
            Each channel will look at the sample, determine if any data in
            the sample is something it cares about, and if so, return back
            parsed data that is scaled for the type of channel it is.
        """
        io_sample = parse_is(buf)
        for ch in self.__aio_channel_structures:
            sample = ch.decode_sample(io_sample, self.__scale, self.__offset)
            if sample != None:
                chn = ch.name() + "_value"
                self.__parent.property_set(chn, sample)
                if self.__tracer.debug():
                    self.__tracer.debug("%s = %s", chn, sample)

        for ch in self.__dio_channel_structures:
            sample = ch.decode_sample(io_sample, self.__scale, self.__offset)
            if sample != None:
                chn = ch.name() + "_input"
                self.__parent.property_set(chn, sample)
                if self.__tracer.debug():
                    self.__tracer.debug("%s = %s", chn, sample)

    def calibrate(self):
        """\
            Calibrate analog inputs on the XBee radio.
            Calculates scale and offset.
        """

        # Retrieve the radio type.
        # Calibration is different based on the XBee radio in the unit.
        xbee_dd_ddo_value = self.__xbee_manager.xbee_device_ddo_get_param(None,
                            'DD', use_cache = True)
        module_id, product_id = parse_dd(xbee_dd_ddo_value)

        # XBee series 1 uses one calibration voltage on AN2
        if module_id == MOD_XB_802154:

            # Enable calibration voltages on channel 1
            for ch in self.__aio_channel_structures:
               if ch.channel() == 1:
                  ch.turn_on_calibration_series1()

            # Give it a moment to synch up.  Yes, this IS required!
            digitime.sleep(0.010)

            # Read calibration sample
            result = self.__xbee_manager.xbee_device_ddo_get_param(None, 'IS')
            sample = parse_is(result)["AD1"]
            self.__tracer.debug("Calibration sample is %d", sample)

            # Disable calibration voltages on channels 0 and 1
            for ch in self.__aio_channel_structures:
               if ch.channel() == 0 or ch.channel() == 1:
                  ch.turn_off_calibration_series2()

            # Give it a moment to synch up.  Yes, this IS required!
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
            for ch in self.__aio_channel_structures:
               if ch.channel() == 0 or ch.channel() == 1:
                  ch.turn_on_calibration_series2()

            # Give it a moment to synch up.  Yes, this IS required!
            digitime.sleep(0.010)

            # Read calibration samples
            result = self.__xbee_manager.xbee_device_ddo_get_param(None, 'IS')
            data = parse_is(result)
            sample = [ data["AD0"], data["AD1"] ]

            self.__tracer.debug("Calibration samples are %d, %d", 
                                sample[0], sample[1])

            # Disable calibration voltages on channels 0 and 1
            for ch in self.__aio_channel_structures:
               if ch.channel() == 0 or ch.channel() == 1:
                  ch.turn_off_calibration_series2()

            # Give it a moment to synch up.  Yes, this IS required!
            digitime.sleep(0.010)

            if sample[0] == sample[1]:
                raise ValueError, "Calibration error: equal samples"

            scale1 = self.__CALIBRATION_06 / float(sample[1])
            scale2 = self.__CALIBRATION_10 / float(sample[0])

            self.__scale = (scale1 + scale2) / 2.0

            if self.__OLD_HARDWARE == True:
                self.__offset = (sample[1] *
                       self.__scale - self.LOCAL_AIO_CALIBRATION_06) * 2.4
            else:
                self.__offset = 0.0

        else:
            raise ValueError, "XBee does not support analog inputs"

        self.__calibration_time = digitime.real_clock()

        self.__tracer.debug("Scale is %f, offset is %f", 
                            self.__scale, self.__offset)





#internal functions & classes


