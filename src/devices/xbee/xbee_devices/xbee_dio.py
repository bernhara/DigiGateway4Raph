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

'''
A DIA Driver for the XBee Digital IO Adapter
'''

# imports
import digitime

from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.types.boolean import Boolean, STYLE_ONOFF

from devices.xbee.xbee_config_blocks.xbee_config_block_sleep \
    import CYCLIC_SLEEP_EXT_MAX_MS, CYCLIC_SLEEP_MIN_MS
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *

from devices.xbee.common.io_sample import parse_is
from devices.xbee.common.prodid import PROD_DIGI_XB_ADAPTER_DIO

from devices.xbee.common.bindpoints import SERIAL, SAMPLE

# constants

# Control lines for configuration
IN = 0
OUT = 1

#                   in    out
CONTROL_LINES = [["d8", "d4"],
                 ["d1", "d6"],
                 ["d2", "d7"],
                 ["d3", "p2"]]

INPUT_CHANNEL_TO_PIN = [8, 1, 2, 3]

# exception classes

# interface functions


# classes
class XBeeDIO(XBeeBase):
    '''
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.
    '''
    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [SERIAL, SAMPLE]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [PROD_DIGI_XB_ADAPTER_DIO, ]

    # avoid needlessly trashing strings
    CHN_INPUT_NAME = ("channel1_input", "channel2_input",
                        "channel3_input", "channel4_input" )
    CHN_OUTPUT_NAME = ("channel1_output", "channel2_output",
                        "channel3_output", "channel4_output" )
    DIO_RAW_NAME = ("DIO8", "DIO1", "DIO2", "DIO3")
    DIO_USER_NAME = ("DIO1", "DIO2", "DIO3", "DIO4")

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
        # sleep_time_ms: If set for sleep, specifies the length of time that
        #                the module will sleep after a period of awake_time_ms
        #                each cycle.
        # sample_rate_ms: If set, then value is loaded into IR to
        #                 cause period data updated regardless of
        #                 change.  Also, if non-zero then samples are
        #                 always updated (timestamp refreshed)
        #                 even if there was no change.
        #                 (Is Optional, defaults to 0/off, valid range 0-60000)
        # power: True/False setting to enable/disable the power output
        #        on terminal 6 of the adapter.
        # channel1_dir: Operating I/O mode for pin 1 of the adapter.
        #               Must be a string value comprised of one of the
        #               following:
        #                   "In" - pin is configured to be an input.
        #                   "Out" - pin is configured to be an output.
        # channel2_dir: Operating I/O mode for pin 2 of the adapter.
        #               See channel1_dir for valid setting information.
        # channel3_dir: Operating I/O mode for pin 3 of the adapter.
        #               See channel1_dir for valid setting information.
        # channel4_dir: Operating I/O mode for pin 4 of the adapter.
        #               See channel1_dir for valid setting information.
        # channel1_source: If channel1_dir is configured as an output, this
        #                  option setting may be specified to a
        #                  "device.channel" channel name.  The Boolean value
        #                  of this channel will specify to logic state for
        #                  pin 1 on the adapter.
        # channel2_source: Configures output value source channel for pin 2
        #                  of the adapter.
        #                  See channel1_source setting information.
        # channel3_source: Configures output value source channel for pin 3
        #                  of the adapter.
        #                  See channel1_source setting information.
        # channel4_source: Configures output value source channel for pin 4
        #                  of the adapter.
        #                   See channel1_source setting information.
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
                name='sleep', type=Boolean, required=False,
                default_value=Boolean(False)),
            Setting(
                name='sample_rate_ms', type=int, required=False,
                default_value=0,
                verify_function=lambda x: x == 0 or \
                            CYCLIC_SLEEP_MIN_MS <= x <= 60000),
           Setting(
                name='sleep_time_ms', type=int, required=False,
                default_value=60000,
                verify_function=lambda x: x >= 0 and \
                                x <= CYCLIC_SLEEP_EXT_MAX_MS),
            Setting(
                name='power', type=Boolean, required=False,
                default_value=Boolean("On", STYLE_ONOFF)),
            Setting(
                name='channel1_dir', type=str, required=False,
                default_value='In'),
            Setting(
                name='channel1_default', type=Boolean, required=False),
            Setting(
                name='channel1_source', type=str, required=False,
                default_value=''),
            Setting(
                name='channel2_dir', type=str, required=False,
                default_value='In'),
            Setting(
                name='channel2_default', type=Boolean, required=False),
            Setting(
                name='channel2_source', type=str, required=False,
                default_value=''),
            Setting(
                name='channel3_dir', type=str, required=False,
                default_value='In'),
            Setting(
                name='channel3_default', type=Boolean, required=False),
            Setting(
                name='channel3_source', type=str, required=False,
                default_value=''),
            Setting(
                name='channel4_dir', type=str, required=False,
                default_value='In'),
            Setting(
                name='channel4_default', type=Boolean, required=False),
            Setting(
                name='channel4_source', type=str, required=False,
                default_value=''),

            # This setting is provided for advanced users, it is not required:
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
        # This device hardware can monitor the state of its output
        # pins.  Therefore, there are always four input channels.
        # The other properties and channels will be populated when we
        # know the directions of our IO ports.
        property_list = [
            ChannelSourceDeviceProperty(
                name=self.CHN_INPUT_NAME[0], type=bool,
                initial=Sample(timestamp=0, value=False, unit='bool'),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                name=self.CHN_INPUT_NAME[1], type=bool,
                initial=Sample(timestamp=0, value=False, unit='bool'),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                name=self.CHN_INPUT_NAME[2], type=bool,
                initial=Sample(timestamp=0, value=False, unit='bool'),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                name=self.CHN_INPUT_NAME[3], type=bool,
                initial=Sample(timestamp=0, value=False, unit='bool'),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
        ]
        # Add our property_list entries into the properties passed to us.
        prop_in = self.merge_properties(prop_in, property_list)

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, name, core_services, set_in, prop_in)

        self._tracer.calls("XBeeDIO.__init__()")


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

        for address in XBeeDIO.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeDIO.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):

        self._tracer.calls("XBeeDIO.apply_settings()")

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
                                accepted['sample_predelay'],
                                accepted['awake_time_ms'])

            rejected['awake_time_ms'] = accepted['awake_time_ms']
            del accepted['awake_time_ms']
            rejected['sample_predelay'] = accepted['sample_predelay']
            del accepted['sample_predelay']
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):

        self._tracer.calls("XBeeDIO.start()")

        # init self._xbee_manager and self._extended_address
        # then register ourself with our Xbee manager
        XBeeBase.pre_start(self)

        cm = self._core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        
        self._xbee_manager.register_sample_listener(self, self._extended_address,
                                                     self.sample_indication)

        # XbeeBase enables self.running_indication

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(self._extended_address)

        # Configure pins DIO0 .. DIO3 for digital input:
        pr = 0xe1 # DIO0-3 pullups off, all else on
        ic = 0

        for io_pin in range(4):
            dir = SettingsBase.get_setting(self, 'channel%d_dir' % \
                                           (io_pin + 1))
            dir = dir.lower()

            # Enable input on all pins:
            xbee_ddo_cfg.add_parameter(CONTROL_LINES[io_pin][IN], 3)

            # Build our change detection mask for all io pins:
            ic |= 1 << INPUT_CHANNEL_TO_PIN[io_pin]

            if dir == 'in':
                # Disable sinking driver output:
                xbee_ddo_cfg.add_parameter(CONTROL_LINES[io_pin][OUT], 4)

            elif dir == 'out':
                # Create the output channel for this IO pin:
                self.add_property(
                    ChannelSourceDeviceProperty(
                        name=self.CHN_OUTPUT_NAME[io_pin], type=Boolean,
                        initial=Sample(timestamp=0, value=Boolean(False),
                                       unit='bool'),
                        perms_mask=(DPROP_PERM_GET | DPROP_PERM_SET),
                        options=DPROP_OPT_AUTOTIMESTAMP,
                        set_cb=lambda sample, io=io_pin: \
                                self.set_output(sample, io)))

                # If set, subscribe to the channel that drives our
                # output logic:
                source = SettingsBase.get_setting(self, 'channel%d_source'
                                                  % (io_pin + 1))
                if len(source):
                    cp.subscribe(source,
                                 lambda chan, io=io_pin: \
                                       self.update(chan, io))

                    self._tracer.debug("Linking DOUT %d to channel %s", io_pin+1, source)
                    
                # If not set, attempt to grab the default output setting,
                # and use that instead.
                else:
                    out = SettingsBase.get_setting(self, 'channel%d_default'
                                                   % (io_pin + 1))
                    if out == True:
                        self._tracer.debug("Setting default output to High")
                        xbee_ddo_cfg.add_parameter(CONTROL_LINES[io_pin][OUT],
                                                   5)
                    elif out == False:
                        self._tracer.debug("Setting default output to Low")
                        xbee_ddo_cfg.add_parameter(CONTROL_LINES[io_pin][OUT],
                                                   4)
                    else:
                        self._tracer.debug("Not setting default output value")

        # if adapter is using internal batteries, then configure
        # battery-monitor pin and add low_battery channel
        if SettingsBase.get_setting(self, "enable_low_battery"):
            # configure battery-monitor pin DIO11/P1 for digital input
            xbee_ddo_cfg.add_parameter('P1', 3)
            # add low_battery channel
            self._tracer.debug("Adapter is using internal batteries... " +
                               "adding low_battery channel")
            self.add_property(
                ChannelSourceDeviceProperty(name="low_battery", type=bool,
                    initial=Sample(timestamp=0, value=False),
                    perms_mask=DPROP_PERM_GET,
                    options=DPROP_OPT_AUTOTIMESTAMP))
        else:
            self._tracer.debug("Adapter is not using internal batteries.")

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

        # Assert input pull-ups
        xbee_ddo_cfg.add_parameter('PR', 0x1fff)

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

        if sleep_rate_ms == 0 and will_sleep:
            # bounding sleep rate in when sampling is disabled and
            # sleeping is enabled
            sleep_rate_ms = CYCLIC_SLEEP_MIN_MS

        xbee_sleep_cfg = self._xbee_manager.get_sleep_block(\
            self._extended_address,
            sleep=will_sleep,
            sample_predelay=sample_predelay,
            awake_time_ms=awake_time_ms,
            sleep_rate_ms=sleep_rate_ms)

        self._xbee_manager.xbee_device_config_block_add(self, xbee_sleep_cfg)
        self._xbee_manager.xbee_device_configure(self)
        return True

    # use XBeeBase.stop(self):

    ## Locally defined functions:

    def time_of_last_data(self):
        return self._last_timestamp

    def running_indication(self):
        self._tracer.calls("XBeeDIO.running_indication()")

        if not SettingsBase.get_setting(self, "sleep"):
            # Our device is now running, load our initial state.
            # It is okay if we take an Exception here, as the device
            # might have already gone to sleep.
            try:
                io_sample = self.ddo_get_param('IS')
                self.sample_indication(io_sample, self._extended_address)
            except:
                pass

    def sample_indication(self, buf, addr):

        self._tracer.calls("XBeeDIO.sample_indication()")

        # save time of last data, plus we want ALL of the samples to have
        # exact same timestamp (leaving 0 means some may be 1 second newer)
        self._last_timestamp = digitime.time()

        if self._tracer.info():
            # will be true for debug also
            msg = ""
            change = False
        else:
            msg = None

        io_sample = parse_is(buf)

        for io_pin in range(4):
            key = self.DIO_RAW_NAME[io_pin]
            if key in io_sample:
                val = bool(io_sample[key])
                name = self.CHN_INPUT_NAME[io_pin]
                if msg is not None:
                    msg += self.DIO_USER_NAME[io_pin]

                # Always update the channel with the new sample value, and
                # its timestamp, even if it is the same as the previous value.
                try:
                    # Make a copy of the old values.
                    old = self.property_get(name)
                    # Set the new value.
                    self.property_set(name,  Sample(self._last_timestamp, val, "bool"))
                    # Print out some tracing about old versus new sample value.
                    if msg is not None:
                        if old.timestamp == 0 or old.value != val:
                            # show value with '^' for change
                            msg += '=%s^ ' % val
                            change = True
                        else:
                            # show value, no change
                            msg += '=%s ' % val
                except Exception, e:
                    self._tracer.error("Exception generated: %s", str(e))

        # Low battery check (attached to DIO11/P1):
        if SettingsBase.get_setting(self, "enable_low_battery"):
            # Invert the signal it is actually not_low_battery:
            val = not bool(io_sample["DIO11"])
            self.property_set("low_battery", Sample(self._last_timestamp, val))
            if val and msg is not None:  # only show if true
                msg += ' low_battery=True'

            # NOTE - IMPORTANT: this sample has always been reset
            # EVERY cycle not when it changes. Lynn did NOT change
            # this, plus Modbus expects low_battery.timestamp to
            # change to indicate the DIO device is live. If
            # low_battery channel is made option, Lynn will need a new
            # method to detect health of the DIO adapter

        if msg is not None:
            if change:
                # for normal info, only show whenchanges
                self._tracer.info(msg)
            else: # for debug show all
                self._tracer.debug(msg)
        return

    def set_output(self, sample, io_pin):

        self._tracer.calls("XBeeDIO.set_output(%s, %s)", io_pin, sample)

        new_val = False
        try:
            new_val = bool(sample.value)
        except:
            pass
        ddo_val = 4
        if new_val:
            ddo_val = 5
        cmd = CONTROL_LINES[io_pin][OUT]
        property = self.CHN_OUTPUT_NAME[io_pin]
        old_val = bool(self.property_get(property).value)

        self._tracer.info("set_output(%s) value=%r (old: %r)",
                            property, new_val, old_val)

        if new_val != old_val:
            try:
                self.ddo_set_param(cmd, ddo_val, apply=True)
            except Exception, e:
                self._tracer.error("Error setting output '%s'", str(e))
            self.property_set(property, Sample(0, new_val, "bool"))

    def update(self, channel, io_pin):
        sample = channel.get()
        self.set_output(sample, io_pin)

# internal functions & classes
