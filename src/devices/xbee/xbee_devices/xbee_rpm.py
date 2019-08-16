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
A DIA Driver for the Digi XBee SmartPlug with Power Management
"""

# imports
import struct
import traceback
import digitime

from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

from core.tracing import get_tracer
from common.types.boolean import Boolean, STYLE_ONOFF
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *
from devices.xbee.common.io_sample import parse_is, sample_to_mv
from devices.xbee.common.prodid import PROD_DIGI_XB_RPM_SMARTPLUG

# constants

POWER_ON = 5
POWER_OFF = 4
UNKNOWN_POWER_STATE = 'unknown'

initial_states = ["on", "off", "same"]

# exception classes

# interface functions

# classes
class XBeeRPM(XBeeBase):
    """\
        This class extends one of our base classes and is intended as an
        example of a concrete, example implementation, but it is not itself
        meant to be included as part of our developer API. Please consult the
        base class documentation for the API and the source code for this file
        for an example implementation.

    """
    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [ [0xe8, 0xc105, 0x92], [0xe8, 0xc105, 0x11] ]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [ PROD_DIGI_XB_RPM_SMARTPLUG, ]

    # settings defaults
    DEF_SAMPLE_MS = 1000
    DEF_STATE = 'same'
    DEF_IDLE_OFF = 0
    DEF_PF = 1.0
    DEF_DEGF = False

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
        self.offset = 520.0
        self.__power_on_time = 0

        # Settings
        #
        # xbee_device_manager: must be set to the name of an
        #                      XBeeDeviceManager instance.
        # extended_address: the extended address of the XBee device you
        #                   would like to monitor.
        # sample_rate_ms: the sample rate of the XBee SmartPlug.
        # default_state: "On"/"Off"/"Same", if "On" the plug will default to
        #                being switched on.
        # idle_off_seconds: Number of seconds to go by before forcing
        #                   power off.
        #                   If not set the value defauts to 0, which means
        #                   the device never idles out.
        # power_on_source: optional setting; string name of a Boolean
        #                  "device.channel" to be used as the state.  For
        #                  example, if set to the name of a channel which
        #                  changes value from False to True, the SmartPlug
        #                  would change from being off to on.
        # pf_adjustment: optional setting; floating point value between
        #                0 and 1, that is used to adjust the current
        #                output given a known power factor.
        #                defaults to 1 (i.e no adjustment)
        #                Note: The unit cannot determine the pf,
        #                it is strictly a user supplied value.
        # device_profile: optional setting; string value corresponding
        #                 to a preset pf_adjustment value.
        #                 These values are by not intended to be precise;
        #                 they are only estimates.
        #                 For a list of valid device_profile settings see the
        #                 check_profiles() function in the driver source.

        settings_list = [
            Setting(
                name='sample_rate_ms', type=int, required=False,
                default_value=self.DEF_SAMPLE_MS,
                verify_function=lambda x: x > 0 and x < 0xffff),
            Setting(
                name='default_state', type=str, required=False,
                default_value=self.DEF_STATE,
                parser=lambda s: s.lower(),
                verify_function=lambda s: s in initial_states),
            Setting(
                name='idle_off_seconds', type=int, required=False,
                default_value=self.DEF_IDLE_OFF,
                verify_function=lambda x: x >= 0),
            Setting(
                name="power_on_source", type=str, required=False),
            Setting(
                name="pf_adjustment", type=float, required=False,
                default_value=self.DEF_PF,
                verify_function=lambda i:0 < i and i <= 1.0),
            Setting(name="device_profile", type=str, required=False),
            Setting(
                name="degf", type=bool, required=False,
                default_value=self.DEF_DEGF),

        ]

        # Add our settings_list entries into the settings passed to us.
        set_in = self.merge_settings(set_in, settings_list)

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="light", type=float,
                initial=Sample(timestamp=0, unit="brightness", value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="temperature", type=float,
                initial=Sample(timestamp=0, unit="C", value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="current", type=float,
                initial=Sample(timestamp=0, unit="A", value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="power_on", type=str,
                initial=Sample(timestamp=0,
                    value=str(Boolean(True, style=STYLE_ONOFF))),
                perms_mask=(DPROP_PERM_GET | DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.prop_set_power_control),
        ]

        # Add our property_list entries into the properties passed to us.
        prop_in = self.merge_properties(prop_in, property_list)

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, name, core_services, set_in, prop_in)

        self._tracer.calls("XBeeRPM.__init__()")

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

        for address in XBeeRPM.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeRPM.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

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

        self._tracer.calls("XBeeRPM.start()")

        # init self._xbee_manager and self._extended_address
        # register ourself with our Xbee manager
        # create the self.running_indication callback
        XBeeBase.pre_start(self)

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        self._xbee_manager.register_sample_listener(self, self._extended_address,
                                                     self.sample_indication)

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(self._extended_address)

        # Configure pins DI1 .. DI3 for analog input:
        for io_pin in ['D1', 'D2', 'D3']:
            xbee_ddo_cfg.add_parameter(io_pin, 2)

        # Get the extended address of the device:
        default_state = SettingsBase.get_setting(self, 'default_state')

        if default_state != 'same':
            # Configure pin DI4 for digital output, default state setting:
            self.prop_set_power_control(Sample(0,
                            str(Boolean(default_state, STYLE_ONOFF))))
        else:
            self.property_set('power_on', Sample(0, UNKNOWN_POWER_STATE))

        # Configure the IO Sample Rate:
        sample_rate = SettingsBase.get_setting(self, 'sample_rate_ms')
        xbee_ddo_cfg.add_parameter('IR', sample_rate)

        # new method for mesh health monitoring
        self.set_data_update_rate_seconds(sample_rate / 1000)
        
        # Handle subscribing the devices output to a named channel,
        # if configured to do so:
        power_on_source = SettingsBase.get_setting(self, 'power_on_source')
        if power_on_source is not None:
            cm = self._core.get_service('channel_manager')
            cp = cm.channel_publisher_get()
            cp.subscribe(power_on_source, self.update_power_state)

        # Register this configuration block with the XBee Device Manager:
        self._xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # we've no more to config, indicate we're ready to configure.
        return XBeeBase.start(self)

    def _set_initial_power_state(self):
        '''
        set the initial power state (if set as "same")

        This needs to be outside of the start method, because
        it requires active communication with the device.

        Returns True on success, False on failure.
        '''
        # Retrieve current state from device for channel
        d4 = self._xbee_manager.xbee_device_ddo_get_param(
                                    self._extended_address, 'd4')

        d4 = struct.unpack('B', d4)[0]

        if d4 == POWER_ON:
            state = True

            # Treat as having just been turned on for shut-off
            self.__power_on_time = digitime.time()
        elif d4 == POWER_OFF:
            state = False
        else:
            self._tracer.warning('Unrecognized initial power_on state '
                                  '<%s>!\nNot touching "power_on" property.'
                                  % d4)
            return False

        self.property_set("power_on",
                          Sample(0, str(Boolean(state, style=STYLE_ONOFF))))
        return True

    def get_power_factor(self):
        pf_setting = SettingsBase.get_setting(self, 'pf_adjustment')
        dev_prof = SettingsBase.get_setting(self, 'device_profile')

        if dev_prof is not None:
            return self.check_profiles(dev_prof)
        else:
            return pf_setting

    def stop(self):

        # Unregister ourselves with the XBee Device Manager instance:
        if self._xbee_manager is not None:
            self._xbee_manager.xbee_device_unregister(self)

        return True


    ## Locally defined functions:
    def time_of_last_data(self):
        return self._last_timestamp

    def check_profiles(self, device):
        """
            Preset device profiles and their power factors.
            These values are by no means meant to be precise,
            and at best represent ball-park estimates.
        """
        string = device.lower()

        if string == 'fluor-mag':
            return 0.4
        elif string == 'fluor-electronic':
            return 0.6
        elif string == '1/3hp-dc-motor':
            return 0.6
        elif string == 'laptop':
            return 0.53
        elif string == 'lcd_monitor':
            return 0.65
        elif string == 'workstation':
            return 0.97 #p.s with pf correction
        else:
            self._tracer.warning("Couldn't find device profile %s, using 1.0",
                                  string)
            return 1.0


    def sample_indication(self, buf, addr):
    
        self._tracer.calls("XBeeRPM.sample_indication()")
    
        # save time of last data, plus we want ALL of the samples to have
        # exact same timestamp (leaving 0 means some may be 1 second newer)
        self._last_timestamp = digitime.time()
        
        # new method for mesh health monitoring
        self.set_time_of_last_data(self._last_timestamp)
    
        # if we haven't gotten initial state yet, ask for it
        if self.property_get('power_on').value == UNKNOWN_POWER_STATE:
            if not self._set_initial_power_state():
                self._tracer.warning('Power state unknown, ignoring '
                                      'sample indication.')
                return
                
        # Parse the I/O sample:
        io_sample = parse_is(buf)

        # Calculate channel values:
        light_mv, temperature_mv, current_mv = \
            map(lambda cn: sample_to_mv(io_sample[cn]),
                ('AD1', 'AD2', 'AD3'))
        light = round(light_mv, 0)
        if light < 0:
            # clamp to be zero or higher
            light = 0

        power_state = Boolean(self.property_get("power_on").value,
                              style=STYLE_ONOFF)

        # TODO: CRA Max could you remove this offset code?  Change to
        # clip at 0.
        if not power_state:
            self.offset = current_mv * (157.0 / 47.0)
            if self.offset >= 600.0:
                # Probably a current spike from flipping the power relay
                self.offset = 520.0

        current = round((current_mv * (157.0 / 47.0) - self.offset) \
                        / 180.0 * 0.7071, 3)

        pf_adj = self.get_power_factor()
        # compute powerfactor adjusted current
        if 1.0 >= pf_adj and 0.0 <= pf_adj:
            current *= pf_adj

        if current <= 0.05:
            # Clip the noise at the bottom of this sensor:
            current = 0.0
        temperature = (temperature_mv - 500.0) / 10.0
        # self-heating correction
        temperature = (temperature - 4.0) - \
                      (0.017 * current ** 2 + 0.631 * current)
                      
        if SettingsBase.get_setting(self, "degf"):
            temperature = (temperature * 1.8) + 32.0
            units = 'F'
        else:
            units = 'C'
                      
        temperature = round(temperature, 2)

        # Update channels:
        self.property_set("light", Sample(self._last_timestamp, light, "brightness"))
        self.property_set("temperature", Sample(self._last_timestamp, temperature, units))
        self.property_set("current", Sample(self._last_timestamp, current, "A"))

        ## Check if sample has information about the power state
        if io_sample.has_key('AD4'):
            ## Define it as a boolean
            compare_state = Boolean(io_sample['AD4'], style=STYLE_ONOFF)

            ## compare to current power_state
            if not compare_state == power_state:
                ## It's different, set the power state to the new value
                self._tracer.warning("Power state was: %s, but now it is: %s"
                                      %(power_state, compare_state))
                self._tracer.warning("Returning power state to: %s"
                                      %(power_state))

                self.prop_set_power_control(Sample(0, str(power_state)))

        if self._tracer.info():
            self._tracer.info('Power:%r light:%d %0.1f%s %0.2fA',
                    power_state, light, temperature, units, current)

        # check the realtime clock and compare to the last power_on_time
        # turn off if the idle_off_setting has been met or exceeded
        idle_off_setting = SettingsBase.get_setting(self, "idle_off_seconds")
        if (power_state and idle_off_setting > 0):
            if ((digitime.time() - self.__power_on_time) \
                >= idle_off_setting):
                power_on_state_bool = self.property_get("power_on")
                power_on_state_bool.value = False
                self.prop_set_power_control(power_on_state_bool)
                self._tracer.debug('Idle Off True')

    def update_power_state(self, chan):
        # Perform power control:
        self.prop_set_power_control(chan.get())

    def prop_set_power_control(self, bool_sample):
        '''
        Set the power on the device and the power_on property.
        '''
        power_on = Boolean(bool_sample.value, style=STYLE_ONOFF)
        if power_on:
            ddo_io_value = POWER_ON
            self.__power_on_time = digitime.time()
        else:
            ddo_io_value = POWER_OFF

        try:
            self._xbee_manager.xbee_device_ddo_set_param(
                                    self._extended_address, 'D4', ddo_io_value,
                                    apply=True)
            self.property_set("power_on", Sample(0, str(power_on)))
            if self._tracer.info():
                self._tracer.info('Power going %r at %s', power_on,
                                    digitime.asctime())
        except:
            self._tracer.debug(traceback.format_exc())
