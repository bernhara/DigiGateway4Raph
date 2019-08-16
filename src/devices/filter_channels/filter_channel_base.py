############################################################################
#                                                                          #
# Copyright (c)2009, Digi International (Digi). All Rights Reserved.       #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,  and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. ContactProduct Management, Digi International, Inc., 11001 Bren    #
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

"""
"""

# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from core.tracing import get_tracer
from channels.channel_source_device_property import ChannelSourceDeviceProperty,\
        DPROP_PERM_GET, DPROP_PERM_SET, DPROP_PERM_REFRESH,\
        DPROP_OPT_AUTOTIMESTAMP, Sample
from common.abstract_service_manager import ASMInstanceNotFound
# constants

# exception classes

# interface functions

# classes

class FilterChannelFactoryBase(DeviceBase):
    """
    """

    def __init__(self, name, core, settings, properties):
        self._name = name
        self._core = core
        self._scheduler = self._core.get_service("scheduler")

        self._tracer = get_tracer(name)
        self._filter_channel_object = None
        self._filter_objects = []
        
        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='target_channel_filter', type=str, required=False,
                default_value = '*.*'),
            Setting(
                name='channel_name_override', type=str, required=False,
                default_value = ""),
        ]
        settings.extend(settings_list)
        
        property_list = []
        properties.extend(property_list)

        ## Initialize the ServiceBase interface:
        DeviceBase.__init__(self, self._name, self._core, settings, properties)

    ## Functions which must be implemented to conform to the ServiceBase
    ## interface:

    def apply_settings(self):
        """
            Called when new configuration settings are available.
       
            Must return tuple of three dictionaries: a dictionary of
            accepted settings, a dictionary of rejected settings,
            and a dictionary of required settings that were not
            found.
        """
        
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        if len(rejected) or len(not_found):
            self._tracer.error("Settings rejected/not found: %s %s", rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        cm = self._core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        cdb = cm.channel_database_get()

        # We want to register for all new channels that might be added
        # during the DIA runtime.
        cp.subscribe_new_channels(self._new_channel_added)

        # Get a listing of all current DIA channels already in existence,
        # and walk through each of them.
        # If they match any of our filters, subscribe to receive notification
        # about new samples as they arrive on the channel.
        current_dia_channels = cdb.channel_list()
        for channel in current_dia_channels:
            if self._match_filter(channel):
                self._add_filter_channel(channel)
        return True

    def stop(self):
        cm = self._core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        cp.unsubscribe_new_channels(self._new_channel_added)
        return True
    
    def create_filter_channel(self, channel, filter_channel):
        raise NotImplementedError, "virtual function"

    def _add_filter_channel(self, channel_name, retry=3):
        cm = self._core.get_service("channel_manager")
        cdb = cm.channel_database_get()
        channel = cdb.channel_get(channel_name)
        
        cm = self._core.get_service("channel_manager")
        cdb = cm.channel_database_get()
        dm = self._core.get_service("device_driver_manager")
        target_device_name = channel.name().split('.')[0]

        # If the user has specified an override name for the channel name
        # that we will make, use it by adding an underscore in front of it.
        channel_name_override = SettingsBase.get_setting(self, "channel_name_override")
        if channel_name_override != None and self._name != "":
            filter_channel_name = "_%s" % (channel_name_override)
        # Otherwise, append the name to the filter channel name with an underscore
        else:
            filter_channel_name = "_%s_%s"%(channel.name().split('.')[1], self._name)

        #check if we already added filter channel
        if cdb.channel_exists("%s.%s"%(target_device_name, filter_channel_name)):
            self._tracer.error("Trying to add duplicate filter channel")
            return

        #find the target device driver
        try:
            target_device = dm.instance_get(target_device_name)
        except ASMInstanceNotFound:
            if retry > 0:
                self._tracer.error("%s not started, rescheduling filter channel creation, retry %d",
                                   target_device_name, retry)
                self._scheduler.schedule_after(30, self._add_filter_channel, channel_name, retry-1)
            else:
                self._tracer.error("%s is not starting, filter channel creation giving up", target_device_name)
            return
        
        #create the filter property we are going to add
        filter_channel = self.physically_create_filter_channel(channel, filter_channel_name)
        
        target_device.add_property(filter_channel)
        
        #create the filter channel object and hook up to target channel
        filter_channel_object = self.create_filter_channel(channel, filter_channel)
        self._filter_objects.append(filter_channel_object)


    def physically_create_filter_channel(self, original_channel, filter_channel_name):
        #create the filter property we are going to add

        # perm_mask draws the refresh setting from the channel we are following.
        # If it is refreshable, then our channel will be refreshable as well.
        is_refreshable = bool(original_channel.perm_mask() & DPROP_PERM_REFRESH)
        if is_refreshable:
            perms_mask = DPROP_PERM_GET | DPROP_PERM_SET | DPROP_PERM_REFRESH
        else:
            perms_mask = DPROP_PERM_GET | DPROP_PERM_SET
        filter_channel = ChannelSourceDeviceProperty(name = filter_channel_name,
            type = original_channel.type(),
            initial = Sample(timestamp = 0, value = original_channel.type()()),
            perms_mask = perms_mask,
            refresh_cb = self._refresh,
            options = DPROP_OPT_AUTOTIMESTAMP)
        return filter_channel


    ## Locally defined functions:

    def _new_channel_added(self, channel_name):
        """\
            Called whenever there is a new channel added into DIA.
            Keyword arguments:
            channel -- the channel name that DIA just added.
        """
        if self._match_filter(channel_name):
            self._add_filter_channel(channel_name)

    def _refresh(self):
        """\
            Called whenever the user would like to refresh the channel.

            This function will typically be replaced automatically by a more
            specific callback function in one of the non-Factory classes.
        """
        self._tracer.info("Refresh called 1")
        for obj in self._filter_objects:
            # Only call function if it exists, and is callable.
            if hasattr(obj, 'property_refresh') and \
                             callable(getattr(obj, 'property_refresh')):
                obj.property_refresh()

    def _match_filter(self, channel_name):
        filter_string = SettingsBase.get_setting(self, "target_channel_filter")
        device_filter = '*'
        property_filter = '*'
        if filter_string.find('.') != -1:
            (device_filter, property_filter) = filter_string.split('.')
        
        (device_name, property_name) = channel_name.split('.')
        if (self._match_substrings(device_name, device_filter) and
            self._match_substrings(property_name, property_filter, True)):
            return True
        return False

    def _match_substrings(self, candidate, filter, star_not_match_leading_underscore=False):
        if filter.count('*') == 0:
            if candidate == filter:
                return True
            return False
        try:
            (filter_start, filter_end) = filter.split('*')
        except ValueError:
            self._tracer.error("Invalid filter, must contain 0 or 1 '*' character")
            return False
        #if the filter starts with a * and the candidate starts with _ then don't match.
        #This is to prevent infinite loops where filter channel spawns filter channel spawns filter_channel
        #You can still stack filter channels by explicitly listing the _ character in filter.
        if star_not_match_leading_underscore and filter_start == "" and candidate.startswith("_"):
            return False
        
        if candidate.startswith(filter_start) and candidate.endswith(filter_end):
            return True
        return False

# internal functions & classes
class FilterChannelBase(object):
    def __init__(self, name, core, source_channel, filter_channel):
        self._name = name
        self._core = core
        self.source_channel = source_channel
        self.filter_channel = filter_channel
        self._target_channel_name = filter_channel.name
        self._tracer = get_tracer(name)
        
        dm = self._core.get_service("device_driver_manager")
        target_device_name = source_channel.name().split('.')[0]
        target_device = dm.instance_get(target_device_name)
        self._target_device = target_device
        
        cm = self._core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        cp.subscribe(source_channel.name(), self._receive)

        # Attempt to force a copy of the source's current value into our value.
        try:
            self._receive(source_channel)
        except:
            pass

        # Override the default refresh callback with our more specific one.
        filter_channel.device_refresh_cb = self.property_refresh

    def _receive(self, channel):
        raise NotImplementedError, "virtual function"
    
    def property_set(self, sample):
        self._target_device.property_set(self._target_channel_name, sample)
        self.filter_channel.consumer_set(sample)

    def property_get(self):
        return self._target_device.property_get(self._target_channel_name)

    def property_refresh(self):
        """\
            Called whenever a user has requested that we refresh our data.
            Since we are shadowing a real channel, this means we will tell
            our source channel to refresh itself, which in turn will
            cause a refresh to ourselves as well.
        """
        self._tracer.info("Refresh called")
        # Only call function if it exists, and is callable.
        if hasattr(self.source_channel, 'consumer_refresh') and \
                   callable(getattr(self.source_channel, 'consumer_refresh')):
            self.source_channel.consumer_refresh()

