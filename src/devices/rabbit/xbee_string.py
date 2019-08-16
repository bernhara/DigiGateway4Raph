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
An Example DIA Driver for sending and receiving arbitrary strings.

Settings:

* **xbee_device_manager:** Must be set to the name of an XBeeDeviceManager
  instance.
* **extended_address:** The extended address of the remote device
* **endpoint:** Local and remote endpoint
* **profile:** Local and remote profile
* **cluster:** Local and remote cluster

"""

# XXX dc: Added for debugging, can be removed
import traceback

# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

from common.types.boolean import Boolean, STYLE_ONOFF
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *


# exception classes

# interface functions

# classes
class XBeeString(DeviceBase):

    def __init__(self, name, core_services, extra_settings=[],
            create_remote=True, create_local=True):
        self.__name = name
        self.__core = core_services
        self.__create_remote = create_remote
        self.__create_local = create_local

        ## Local State Variables:
        self.__xbee_manager = None

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Settings Table Definition:
        settings_list = [
            Setting( name='xbee_device_manager', type=str, required=True),
            Setting( name='extended_address', type=str, required=True),
            Setting( name='endpoint', type=int, required=True),
            Setting( name='profile', type=int, required=True),
            Setting( name='cluster', type=int, required=True),
            Setting( name='local', type=str, required=False),
            Setting( name='remote', type=str, required=False),
        ]
        for s in extra_settings:
            settings_list.append(Setting(name=s['name'], type=s['type'],
                required=s['required']))
            

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
        """Add channels, start the device driver.  Returns bool."""

        ## Add in the Channel Properties Definitions:
        # gettable properties
        if self.__create_remote:
            self.remote = SettingsBase.get_setting(self, "remote")
            if self.remote == None:
                self.remote = "remote"

            self.add_property(
                ChannelSourceDeviceProperty(name=self.remote, type=str,
                    initial=Sample(timestamp=0, value="<none>"),
                    perms_mask=DPROP_PERM_GET,
                    options=DPROP_OPT_AUTOTIMESTAMP,
                    refresh_cb = lambda : None))

        # gettable and settable properties
        if self.__create_local:
            # "local" is set on the ConnectPort, and sent to the Rabbit.
            self.local = SettingsBase.get_setting(self, "local")
            if self.local == None:
                self.local = "local"

            self.add_property(
                ChannelSourceDeviceProperty(name=self.local, type=str,
                    initial=Sample(timestamp=0, value="<none>"),
                    perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                    options=DPROP_OPT_AUTOTIMESTAMP,
                    set_cb=lambda sample: self.set_and_send(self.local,
                            sample)))


        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self,
            "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        # Get the extended address of the device:
        self.extended_address = SettingsBase.get_setting(self, "extended_address")
        try:
            self.endpoint = SettingsBase.get_setting(self, "endpoint")
        except:
            pass
        try:
            self.profile = SettingsBase.get_setting(self, "profile")
        except:
            pass
        try:
            self.cluster = SettingsBase.get_setting(self, "cluster")
        except:
            pass
        #                     MAC, endpoint, profile, cluster
        self.remote_mepc = (self.extended_address, self.endpoint, self.profile,
                            self.cluster)

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec.cb_set(self.receive_data)
        xbdm_rx_event_spec.match_spec_set(self.remote_mepc, 
            (True, True, True, True))
        self.__xbee_manager.xbee_device_event_spec_add(self,
                xbdm_rx_event_spec)

        # Create a callback specification that calls back this driver when
        # our device has left the configuring state and has transitioned
        # to the running state:
        xbdm_running_event_spec = XBeeDeviceManagerRunningEventSpec()
        xbdm_running_event_spec.cb_set(self.running_indication)
        self.__xbee_manager.xbee_device_event_spec_add(self,
                xbdm_running_event_spec)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        # Handle channels subscribed to output their data to our led
        # properties:
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()

        return True


    def stop(self):
        """Stop the device driver.  Returns bool."""

        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)

        return True
        

    ## Locally defined functions:
    def running_indication(self):
        # Our device is now running, load our initial state:
        # Nothing to do.  With actual channels, we might want to query the
        # channel values, but for the chat / string model, that doesn't
        # make sense.
        pass

    def receive_data(self, buf, addr):
        # Parse the I/O sample:
        self.__tracer.info("receive_data: '", buf, "', addr", addr)
        self.property_set(self.remote, Sample(digitime.time(), buf))

    def set_and_send(self, name, Sample):
        """\
            Given a property name, and a Sample, send the Sample.value and
            update the local value of the property.

            Return 0 on success, 1 on failure (i.e., Message too long).
        """
        #traceback.format_stack()
        self.__tracer.info("name = ", name, ", Sample = ", Sample)
        # Hmm.  Magic number.  XBee Device Manager will try to send up to
        # 85 characters, but the underlying socket appears to bulk at more
        # than 82.  > 85 generates exception 122, 'Message too long.'  83
        # and 84 don't generate the exception, but I don't receive the
        # message on the other side.
        if len(Sample.value) > 82:
            return 1
        self.property_set(name, Sample)
        self.__xbee_manager.xbee_device_xmit(
            # src_ep, Sample, addr
            self.endpoint, Sample.value, self.remote_mepc)
        return 0

# internal functions & classes

