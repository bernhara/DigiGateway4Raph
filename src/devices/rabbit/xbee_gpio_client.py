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

import traceback
import sys
from math import ceil

# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *

from xbee_gpio_structs import *
from xbee_gpio_locks import *

class XBeeGPIOClient(DeviceBase):
    # Override the appropriate methods
    # __init__() needs to know about the attribute setting
    def __init__(self, name, core_services):
        # Create protected dictionaries and lists
        self.name_to_signal = lockDict()
        self.name_to_type = lockDict()
        self.signal_to_name = lockDict()
        self.signal_to_units_range = lockDict()
        self.reads_reqd = lockList()
        self.signals_reqd = lockList()
        self.units_reqd = lockList()
        self.names_reqd = lockList()

        self.info_timeout_scale = 1

        self.__name = name
        self.__core = core_services

        ## Local State Variables:
        self.__xbee_manager = None

        from core.tracing import get_tracer
        self.__tracer = get_tracer("XBeeGPIOClient")

        ## Settings Table Definition:
        settings_list = [
            Setting( name='xbee_device_manager', type=str, required=True),
            Setting( name='extended_address', type=str, required=True),
            Setting( name='poll_rate', type=float, required=False),
        ]

        ## Channel Properties Definition is in start() below:
        property_list = []
                                            
        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):
        """\
            Called when new configuration settings are available.

            Must return tuple of three dictionaries: a dictionary of
            accepted settings, a dictionary of rejected settings, and a
            dictionary of required settings that were not found.
        """

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        #if len(rejected) or len(not_found):
        if len(not_found):
            # Ignore extra settings, but reject if required settings are
            # not found
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        """Start up the XBeeString object, and add our own XBee Device
        Manager rx callbacks"""

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self,
            "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        # Get the extended address of the device:
        self.extended_address = SettingsBase.get_setting(self, 
                "extended_address")

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec.cb_set(self.receive_data)
        xbdm_rx_event_spec.match_spec_set(
            (self.extended_address, XBEE_ENDPOINT_RESPONSE, XB_PROFILE_DIGI, 0),
            (True, False, True, False))
        self.__xbee_manager.xbee_device_event_spec_add(self,
                xbdm_rx_event_spec)

        # Create a callback specification that calls back this driver when
        # our device has left the configuring state and has transitioned
        # to the running state:
        xbdm_running_event_spec = XBeeDeviceManagerRunningEventSpec()
        xbdm_running_event_spec.cb_set(self.request_info)
        self.__xbee_manager.xbee_device_event_spec_add(self,
                xbdm_running_event_spec)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        # Add a wrapper for the XBee manager's schedule_after, schedule_cancel
        # routines.  Round up timeout to nearest second (ConnectPort's time
        # resolution), otherwise, ConnectPort will round down (possibly to 0).
        self.timeout = GPIO_TIMEOUT/1000.
        self.schedule_after = \
            lambda cb, timeout=self.timeout, *args: \
                self.__xbee_manager.xbee_device_schedule_after(
                ceil(timeout),
                cb, *args)
        self.schedule_cancel = self.__xbee_manager.xbee_device_schedule_cancel

        return True

    def receive_data(self, buf, addr):
        """Receive any data for our profile, and hand off to the
        cluster handler."""
        cluster = addr[3]   # addr: MAC, endpoint, profile, cluster
        if cluster == XBEE_GPIO_CLUST_INFO:
            self.receive_info(buf)
        elif cluster == XBEE_GPIO_CLUST_NAME:
            self.receive_names(buf)
        elif cluster == XBEE_GPIO_CLUST_ANA_RANGE:
            self.receive_units(buf)
        elif cluster == XBEE_GPIO_CLUST_READ:
            self.receive_read(buf)
        elif cluster == XBEE_GPIO_CLUST_WRITE:
            self.receive_write(buf)
        else:
            self.__tracer.warning("Received on an unknown profile/cluster: %d/%d", addr[2:])
        
    def send_to_cluster(self, buf, cluster):
        """Send from our endpoint to the remote endpoint, GPIO
        profile, and specified cluster"""
        mepc = (self.extended_address, XBEE_ENDPOINT_GPIO,
                XB_PROFILE_DIGI, cluster)
        self.__xbee_manager.xbee_device_xmit(XBEE_ENDPOINT_RESPONSE, buf, mepc)

    def request_info(self):
        """Request cluster info: single byte of 0x00"""
        self.send_to_cluster('\x00', XBEE_GPIO_CLUST_INFO)
        self.__tracer.info("XBeeGPIOClient: Discovery request sent: %s", digitime.time())
        # Schedule a timeout
        self.info_timer = self.schedule_after(self.request_info, 
                self.timeout * self.info_timeout_scale)
        if self.info_timeout_scale < 8:
            self.info_timeout_scale = self.info_timeout_scale * 2

        self.poll_secs = SettingsBase.get_setting(self, "poll_rate")

    def receive_info(self, buf):
        """Receive the GPIO info frame, and request IO names"""
        # Cancel timeout, if one exists (and it should :)
        try:
            self.schedule_cancel(self.info_timer)
        except:
            pass

        while(len(buf) > 0):
            protocol_ver, io_count, manufacturer, device_type, firmware_ver = \
                xbee_frame_gpio_info_t.unpack_(buf) 
            self.io_count = io_count
            buf = buf[xbee_frame_gpio_info_t.len():]
            self.__tracer.info("receive_info: io_count: %d", self.io_count)

            # Request GPIO names: \x00 through \x<io_count>
            self.signals_reqd = lockList(range(0, self.io_count))
        if len(self.names_reqd) == 0:
            self.request_names()

    def request_names(self):
        """Ask for the list of IO names"""
        self.names_reqd.append(1)
        self.__tracer.info("requesting names: ", \
                tuple(['<%dB' % len(self.signals_reqd)] + self.signals_reqd), \
                " from endpoint %x", XBEE_GPIO_CLUST_NAME)
        self.send_to_cluster(pack(*tuple(['<%dB'%len(self.signals_reqd)] + \
                self.signals_reqd)), XBEE_GPIO_CLUST_NAME)
        # Schedule a timeout
        self.name_timer = self.schedule_after(self.request_names)

    def receive_names(self, buf):
        """Receive the IO names in buf and create channels.  When
        done, request IO values."""
        try:
            self.schedule_cancel(self.name_timer)
        except:
            pass
        if len(self.names_reqd) > 0:
            del self.names_reqd[0]
        # Multiple xbee_gpio_rec_name_resp_t in a message
        while(len(buf) > 0):
            signal, type_, name = xbee_gpio_rec_name_resp_t.unpack_(buf)
            if signal in self.signals_reqd:
                self.signals_reqd.remove(signal)
            if name in self.name_to_signal:
                continue
            self.name_to_signal[name] = signal
            self.name_to_type[name] = type_
            self.signal_to_name[signal] = name
            if type_ & XBEE_GPIO_MASK_TYPE_ANALOG:
                self.units_reqd.append(signal)
            self.__tracer.info("receive_names:%3d %02x %s", signal, type_, name)
            #'gettable': (DPROP_PERM_GET|DPROP_PERM_REFRESH),
            #'settable': (DPROP_PERM_GET|DPROP_PERM_SET|DPROP_PERM_REFRESH),
            perm = DPROP_PERM_REFRESH | DPROP_PERM_GET
            refresh = lambda name=name: self.send_read(name)
            if not (type_ & XBEE_GPIO_MASK_TYPE_INPUT):
                # Output, settable
                perm |= DPROP_PERM_SET
                set = lambda sample, name=name: self.send_write(name, sample)
            else:
                set = lambda: None
            self.add_property(
                ChannelSourceDeviceProperty(name=name, type=IO_Types[type_],
                    initial=Sample(timestamp=0, value=IO_Types[type_](0)),
                    perms_mask=perm,
                    options=DPROP_OPT_AUTOTIMESTAMP,
                    refresh_cb = refresh,
                    set_cb = set
                    )
                )
            buf = buf[xbee_gpio_rec_name_resp_t.len(name):]
        # Request remaining signal names, if any
        if len(self.signals_reqd) > 0:
            self.request_names()
        else:
            #self.__schedule_refresh()
            self.request_units()

    def request_units(self):
        if len(self.units_reqd):
            req = pack("<%dB" % len(self.units_reqd), *tuple(self.units_reqd))
            self.send_to_cluster(req, XBEE_GPIO_CLUST_ANA_RANGE)
            self.units_timer = self.schedule_after(self.request_units)
        else:
            self.__schedule_refresh()

    def receive_units(self, buf):
        try:
            self.schedule_cancel(self.units_timer)
        except:
            pass
        while (len(buf) > 0):
            signal, length = unpack('<2B', buf[:2])
            buf = buf[2:]
            if length == XBEE_GPIO_TYPE_INVALID:
                continue
            range, length = length & 0x80, length & 0x0F
            units = buf[:length]
            buf = buf[length:]
            if range:
                lower, upper = xbee_gpio_rec_ar_resp_range_t.unpack_(buf)
                buf = buf[xbee_gpio_rec_ar_resp_range_t.len():]
            else:
                lower, upper = None, None
            self.signal_to_units_range[signal] = units, lower, upper
            self.__tracer.info('%d %s: unit: %s lower: %s upper: %s', signal,
                    self.signal_to_name[signal], repr(units), str(lower),
                    str(upper))
            if signal in self.units_reqd:
                self.units_reqd.remove(signal)
        if (len(self.units_reqd) > 0):
            self.request_units()
        else:
            self.__schedule_refresh()
        
    def send_read(self, name):
        """
        Request a single IO value.
        
        If a request is currently pending, queue this request, otherwise send
        the request.  receive_read() will send any queued requests when a
        request is received.
        """
        signal = self.name_to_signal[name]
        if len(self.reads_reqd) == 0:
            self.send_to_cluster('%c' % signal, XBEE_GPIO_CLUST_READ)
        self.reads_reqd.append(signal)

    def receive_read(self, buf):
        """Receive one or more IO values in buf.  If any outstanding
        reads, resend request for those reads."""
        #self.__tracer.info("receive_read: %d bytes received", len(buf))
        while len(buf):
            signal, type_ = unpack("<BB", buf[:2])
            buf = buf[2:]
            # Do a bit of error checking.  If the device is pushing data, we
            # may receive a read before we've finished attached a name and type
            # to a signal value.  If so, ignore the read.
            if signal not in self.signal_to_name:
                self.__tracer.warning("Read: Unknown signal %d, type %02x, ignoring frame.", \
                        signal, type_)
                return
            else:
                name = self.signal_to_name[signal]
            if name not in self.name_to_type or name not in self.name_to_signal:
                self.__tracer.warning("Read: Unknown name %s (%d), type %02x, ignoring frame.", \
                        name, signal, type_)
                return
            if type_ != self.name_to_type[name]:
                self.__tracer.warning("Read: Type changed for %d (%s).  Was " \
                    "0x%02x, now 0x%02x, ignoring frame.") % (signal, name,
                    self.name_to_type[name], type_)
                return    # Expect a cascade of errors ....
            if type_ in [XBEE_GPIO_TYPE_DISABLED, XBEE_GPIO_TYPE_INVALID]:
                continue
            # Sanitized -- we apparently know this signal.
            if signal in self.reads_reqd:
                self.reads_reqd.remove(signal)
            if type_ & XBEE_GPIO_MASK_TYPE_ANALOG:
                # Expect a float
                value, = unpack("<f", buf[:4])
                buf = buf[4:]
                if signal in self.signal_to_units_range:
                    units = self.signal_to_units_range[signal][0]
                else:
                    units = ""
            else:
                # Expect an int
                value, = unpack("<B", buf[:1])
                buf = buf[1:]
                units = ""
            value = IO_Types[self.name_to_type[name]](value)
            self.property_set(name, Sample(digitime.time(), value, units))
            #self.__tracer.warning("receive_read: %d (%s), 0x%02x, value: ", signal, name,
            #        type_), value
        if len(self.reads_reqd) > 0:
            self.refresh_read()

    def refresh_read(self):
        """Request all IO values."""
        if len(self.reads_reqd) == 0:
            self.reads_reqd = lockList(range(0, self.io_count))
        if self.reads_reqd.acquire(0):
            self.send_to_cluster(pack(*tuple(['B'*len(self.reads_reqd)] +
                    self.reads_reqd)), XBEE_GPIO_CLUST_READ)
            self.reads_reqd.release()

    def send_write(self, name, sample):
        """Write a value an IO (output)."""
        value = sample.value
        type_ = self.name_to_type[name]
        signal = self.name_to_signal[name]
        self.__tracer.info("send_write: %02X: name '%s', type %02X, value ", \
                signal, name, type_), value
        if signal in self.signal_to_units_range and \
                self.signal_to_units_range[signal][1] is not None:
            value = IO_Types[self.name_to_type[name]](value)
            if value.range_check(*self.signal_to_units_range[signal][1:3]):
                self.__tracer.info("... value, ", sample.value, ", adjusted to ", \
                        value, " to be in the range ", \
                        self.signal_to_units_range[signal][1:3])
                sample.value = value
        if not (type_ & XBEE_GPIO_MASK_TYPE_INPUT):
            if type_ & XBEE_GPIO_MASK_TYPE_ANALOG:
                buf = pack("<BBf", signal, type_, float(value))
            else:
                buf = pack("<BBB", signal, type_, int(value))
            self.send_to_cluster(buf, XBEE_GPIO_CLUST_WRITE)
            self.property_set(name, sample)

    def receive_write(self, buf):
        """Receive status for a previously written output request."""
        signal, response = unpack("<BB", buf)
        if response == XBEE_GPIO_STATUS_SUCCESS:
            #self.__tracer.info("receive_write: %3d %s: written okay", signal,
            #    self.signal_to_name[signal])
            return
        elif response == XBEE_GPIO_STATUS_DISABLED:
            error = "Failed: %s is disabled" % self.signal_to_name[signal]
        elif response == XBEE_GPIO_STATUS_BAD_TYPE:
            error = "Failed: %s: bad type" % self.signal_to_name[signal]
        elif response == XBEE_GPIO_STATUS_OUT_OF_RANGE:
            error = "Failed: %s: out of range" % self.signal_to_name[signal]
        elif response == XBEE_GPIO_STATUS_INVALID:
            error = "Failed: %s: invalid" % self.signal_to_name[signal]
        else:
            error = "Failed: %s: unknown error" % self.signal_to_name[signal]
        #raise Exception(error)
        self.__tracer.error(error)

    def __schedule_refresh(self):
        """Request refresh: do this when there are no outstanding reads.
        Poll if "polling" setting exists and is non-zero."""
        if len(self.reads_reqd) == 0:
            self.refresh_read()
        # Next, set up polling
        if self.poll_secs:
            self.__xbee_manager.xbee_device_schedule_after(
                    self.poll_secs, self.__schedule_refresh)
