############################################################################
#                                                                          #
# Copyright (c)2009, Digi International (Digi). All Rights Reserved.       #
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
Driver for TZB43 Xbee RCS Thermostat.

Settings:

* **xbee_device_manager:** Must be set to the name of an XBeeDeviceManager
  instance.
* **extended_address:** The extended address of the XBee device you
  would like to monitor.
* **sample_rate_sec:** Rate at which to sample the thermometer in seconds.
  Default rate is 5 min, but the minimum time is every 15 seconds.

To Use:

Issue channel_get (or channel_dump) to read the desired channel.  In
most cases the channel name is descriptive of its purpose.  When issued,
the thermostat device is queried and the channels are filled with the
returned data.  Actual use of serialSend and serialRecieve is discouraged,
instead use the specific channels.

"""

# imports
import time
from threading import Lock

from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *


from common.types.boolean import Boolean, STYLE_ONOFF
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *
from devices.xbee.common.io_sample import parse_is, sample_to_mv

# constants

# exception classes

# interface functions

# classes
class XBeeRCS(DeviceBase):

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        self.__event_timer = None
        self.__serial_lock = Lock()

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Local State Variables:
        self.__xbee_manager = None
        self.update_timer = None
        self.modes = {"Off":0, "Heat":1, "Cool":2, "Auto":3}

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='xbee_device_manager', type=str, required=True),
            Setting(
                name='extended_address', type=str, required=True),
            Setting(
                name='sample_rate_sec', type=int, required=False,
                default_value=300,
                verify_function=lambda x: x >= 10 and x < 0xffff),
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="serialReceive", type=str,
                initial=Sample(timestamp=0, unit="", value=""),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="serialSend", type=str,
                initial=Sample(timestamp=0, unit="", value=""),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.serial_send),
            ChannelSourceDeviceProperty(name="current_temp", type=int,
                initial=Sample(timestamp=0, unit="F", value=0),
                perms_mask=(DPROP_PERM_GET),
                options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="set_point_temp", type=int,
                initial=Sample(timestamp=0, unit="F", value=75),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.set_sp),
            ChannelSourceDeviceProperty(name="set_point_high_temp", type=int,
                initial=Sample(timestamp=0, unit="F", value=80),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.set_sph),
            ChannelSourceDeviceProperty(name="set_point_low_temp", type=int,
                initial=Sample(timestamp=0, unit="F", value=65),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.set_spc),
            ChannelSourceDeviceProperty(name="mode", type=str,
                initial=Sample(timestamp=0, unit="o/h/c/a", value="Off"),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.set_mode),
            ChannelSourceDeviceProperty(name="fan", type=Boolean,
                initial=Sample(timestamp=0,
                value=Boolean(True, style=STYLE_ONOFF)),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.set_fan),
            ChannelSourceDeviceProperty(name="state", type=str,
                initial=Sample(timestamp=0, unit="o/h/c/a", value="Off"),
                perms_mask=(DPROP_PERM_GET),
                options=DPROP_OPT_AUTOTIMESTAMP),
        ]

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)


    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):
        """\
            Called when new configuration settings are available.

            Must return tuple of three dictionaries: a dictionary of
            accepted settings, a dictionary of rejected settings,
            and a dictionary of required settings that were not
            found.
        """

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # there were problems with settings, terminate early:
            self.__tracer.warning("There was an error with the settings. " +
                  "Attempting to continue.")

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        """Start the device driver.  Returns bool."""

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self, "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        # Get the extended address of the device:
        extended_address = SettingsBase.get_setting(self, "extended_address")

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec.cb_set(self.serial_receive)
        xbdm_rx_event_spec.match_spec_set(
            (extended_address, 0xe8, 0xc105, 0x11),
            (True, True, True, True))
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                xbdm_rx_event_spec)

        #register a callback for when the config is done
        xb_rdy_state_spec = XBeeDeviceManagerRunningEventSpec()
        xb_rdy_state_spec.cb_set(self._config_done_cb)
        self.__xbee_manager.xbee_device_event_spec_add(self, xb_rdy_state_spec)

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)

        # Get the gateway's extended address:
        gw_xbee_sh, gw_xbee_sl = gw_extended_address_tuple()

        # Set the destination for I/O samples to be the gateway:
        xbee_ddo_cfg.add_parameter('DH', gw_xbee_sh)
        xbee_ddo_cfg.add_parameter('DL', gw_xbee_sl)

        # Register this configuration block with the XBee Device Manager:
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        return True

    def stop(self):
        """Stop the device driver.  Returns bool."""

        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)

        return True


    ## Locally defined functions:
    def update(self):
        """
            Request the latest data from the device.
        """

        self.__tracer.debug("acquiring update lock...")
        if not self.__serial_lock.acquire(False): #non blocking
            #(update in progress)
            self.__tracer.debug("couldnt get update lock... try again later.")
            return -1

        try:
            self.serial_send("A=1,Z=1,R=1\x0D")

            # We will process receive data when it arrives in the callback
        finally:
            #done with the serial
            self.__serial_lock.release()

        #Reschedule this update method
        if self.__event_timer is not None:
            try:
                self.__xbee_manager.xbee_device_schedule_cancel(
                    self.__event_timer)
            except:
                pass

        self.__event_timer = self.__xbee_manager.xbee_device_schedule_after(
                SettingsBase.get_setting(self, "sample_rate_sec"),
                self.update)

    def _parse_return_message(self, msg):
        """ Take a status string from thermostat, and
            split it up into a dictionary::

                "A=0 T=74" -> {'A':0, 'T':74}

        """
        try:
            if not msg:
                return {}

            ret = {}
            split_msg = msg.split(" ") #tokenize

            for i in split_msg:
                i = i.split("=")
                ret[i[0]] = i[1]

            return ret

        except:
            self.__tracer.warning("Error parsing return message: " + repr(msg))
            return {}

    def set_spc(self, val):
        """ set point cool """
        self.__serial_lock.acquire(1)
        try:
            self.serial_send("A=1,Z=1,SPC=" + str(val.value) + "\x0D")
        finally:
            self.__serial_lock.release()

        self.update()

    def set_sph(self, val):
        """ set point high """
        self.__serial_lock.acquire(1)
        try:
            self.serial_send("A=1,Z=1,SPH=" + str(val.value) + "\x0D")
        finally:
            self.__serial_lock.release()

        self.update()

    def set_sp(self, val):
        """ Set the set-point temperature """

        self.__serial_lock.acquire(1)
        try:
            self.serial_send("A=1,Z=1,SP=" + str(val.value) + "\x0D")
        finally:
            self.__serial_lock.release()

        self.update()

    def set_mode(self, val):
        """ set system mode.
            where mode is one of [Off, Heat, Cool, Auto]
        """
        self.__serial_lock.acquire(1)
        try:
            self.serial_send("A=1,Z=1,M=" + \
                str(self.modes[val.value.title()]) + "\x0D")
        finally:
            self.__serial_lock.release()

        self.update()

    def set_fan(self, val):
        """ Set system fan.

            Value can be:

            * on
            * off

            Setting fan to off will only put the fan in auto mode, there is no
            way to force the fan totally off.  Also, even in auto mode there
            is no way to tell if the fan is actually spinning or not.
        """
        self.__serial_lock.acquire(1)
        try:
            self.serial_send("A=1,Z=1,F=" + str(int(val.value)) + "\x0D")
        finally:
            self.__serial_lock.release()

        self.update()


    def _config_done_cb(self):
        """ Indicates config is done. """
        self.__tracer.debug("done configuring, starting polling")
        self.update()


    def serial_receive(self, buf, addr):
        # Parse the I/O sample:
        self.__tracer.debug("serialReceive:%s", repr(buf))
        # Update channels:
        self.property_set("serialReceive", Sample(0, buf, ""))

        d = self._parse_return_message(buf)

        if d.has_key("T"):
            self.property_set("current_temp",
                                Sample(0, value=int(d["T"]), unit="F"))
        if d.has_key("SP"):
            self.property_set("set_point_temp",
                                Sample(0, value=int(d["SP"]), unit="F"))
        if d.has_key("SPH"):
            self.property_set("set_point_high_temp",
                                Sample(0, value=int(d["SPH"]), unit="F"))
        if d.has_key("SPC"):
            samp = Sample(0, value=int(d["SPC"]), unit="F")
            self.property_set("set_point_low_temp", samp)
        if d.has_key("M"):
            self.property_set("mode", \
                Sample(0, value=d["M"], unit="o/h/c/a"))
        if d.has_key("FM"):
            self.property_set("fan", Sample(0, value=Boolean(bool(int(d["FM"])),
            style=STYLE_ONOFF)))

        # This next bit deciedes the 'state' of the thermostat.
        # Similar to 'mode', but depends on the set points and temperature
        if(self.property_get("mode").value == 'Cool' and
            self.property_get("set_point_low_temp").value <\
            self.property_get("current_temp").value):
            c = 'Cool'
        elif(self.property_get("mode").value == 'Heat' and \
            self.property_get("set_point_high_temp").value >\
                self.property_get("current_temp").value):
            c = 'Heat'
        else:
            c = 'Off'

        self.property_set("state", Sample(0, value=c, unit="o/h/c/a"))

    def serial_send(self, serialString):
        """ Takes either a string or a Sample() """

        if not type(serialString) == type(''):
            serialString = serialString.value # type is Sample

        self.__tracer.debug("serialString:%s", repr(serialString))
        extended_address = SettingsBase.get_setting(self, "extended_address")
        addr = (extended_address, 0xe8, 0xc105, 0x11)
        buf = serialString + chr(0x0D)
        try:
            self.__xbee_manager.xbee_device_xmit(0xe8, buf, addr)
        except:
            self.__tracer.warning("Error writing to " +
                                  "extended_address:%s", extended_address)

# internal functions & classes
