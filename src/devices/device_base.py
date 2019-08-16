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

# imports
from core.tracing import get_tracer
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import ChannelSourceDeviceProperty

import traceback
# constants

# exception classes
class DeviceBasePropertyNotFound(KeyError):
    pass

# interface functions

# classes

class DeviceBase(SettingsBase):
    """
    Base class that any device driver must derive from.

    The :class:`DeviceBase` class is extended in order to create new
    DIA device drivers. :class:`DeviceBase` defines several properties
    and methods for use in DIA devices including a name for the
    device, a set of property channels that can be populated with
    information about the device as well as the methods for
    interacting with those channels, and virtual *start* and *stop*
    methods that must be implemented in each driver.

    Parameters:

    * *name*: the name of the device
    * *settings*: configures device settings. Used to initialize
      :class:`~settings.settings_base.SettingsBase`
    * *core_services*: The system
      :class:`~core.core_services.CoreServices` object.

    """

    DEF_TRACE = '' # None - no change

    def __init__(self, name, core_services, settings, properties):

        # save these for use of sub-classed device drivers
        self._name = name
        self._core = core_services
        self._tracer = get_tracer(name)

        ## local variables

        # These are to be used by 'health monitoring' functions - all drivers
        # should correctly manage these (or leave set to None to mark as N/A)
        #
        # use self.get_time_of_last_data() and
        #     self.set_time_of_last_data() to access!
        self.__last_data_timestamp = None
        # use self.get_data_update_rate_seconds() and
        #     self.set_data_update_rate_seconds() to access!
        self.__data_update_rate = None

        # cache the channel DB reference
        self._channel_db = None

        # Initialize settings:
        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='trace', type=str, required=False,
                default_value=self.DEF_TRACE),
        ]
        # Add our settings_list entries into the settings passed to us.
        settings = self.merge_settings(settings, settings_list)

        self.__settings = settings
        SettingsBase.__init__(self, binding=("devices", (name,), "settings"),
                                    setting_defs=settings)

        # Initialize properties:
        self.__properties = { }
        if properties is not None:
            for property in properties:
                self.add_property(property)

        # pre_start - check if special trace level requested
        trace = SettingsBase.get_setting(self, "trace")
        try:
            self._tracer.set_level(trace)
        except:
            self._tracer.warning("Ignoring bad trace level \'%s\' for this device", trace)

        self._tracer.calls("DeviceBase.__init__()")


    # def __del__(self):
    #     channel_db = \
    #         self._core.get_service("channel_manager").channel_database_get()

    #     # Walk the pending registry, if this device is in there, remove it.
    #     try:
    #         for tmp in self._settings_global_pending_registry['devices']['instance_list']:
    #             if tmp['name'] == self._name:
    #                 try:

    def apply_settings(self):
        """\
            Called when new configuration settings are available.

            Must return tuple of three dictionaries: a dictionary of
            accepted settings, a dictionary of rejected settings,
            and a dictionary of required settings that were not found.
        """

        self._tracer.calls("DeviceBase.apply_settings()")
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # there were problems with settings, terminate early:
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)


    def start(self):
        """
        Start the device driver.  Returns bool.
        """

        self._tracer.calls("DeviceBase.start()")
        return True


    def pre_start(self):
        """
        Call at start of start (normal DeviceBase.start called at end bool.
        """
        self._tracer.calls("DeviceBase.pre_start()")
        return True


    def stop(self):
        """
        Stop the device driver.  Returns bool.
        """
        self._tracer.calls("DeviceBase.stop()")

        self.__settings = None
        self.__properties = None
        self._name = None
        self._core = None
        self._channel_db = None

        ## leave self._tracer, deleting here is problematic during shutdown

        return True


    ## These functions are inherited by derived classes and need not be changed:
    def get_core_services(self):
        """
        Returns the core_services handle registered for this device
        """

        return self._core


    def get_name(self):
        """
        Returns the name of the device.
        """

        return self._name

    def get_channel_database(self):
        """
        Cache and return the name of the channel database.
        """

        if self._channel_db is None:
            # cache the channel DB reference
            self._channel_db = \
                self._core.get_service("channel_manager").channel_database_get()

        return self._channel_db


    def __get_property_channel(self, name):
        """
        Returns channel designated by property *name*.

        """

        channel_db = self.get_channel_database()
        channel_db.channel_get(self._name + '.' + name)
        if name not in self.__properties:
            raise DeviceBasePropertyNotFound, \
                "channel device property '%s' not found." % (name)

        return self.__properties[name]

    def add_property(self, channel_source_device_property):
        """
        Adds a channel to the set of device properties.

        """
        channel_db = self.get_channel_database()
        channel_name = "%s.%s" % \
                        (self._name, channel_source_device_property.name)
        channel = channel_db.channel_add(
                                    channel_name,
                                    channel_source_device_property)
        self.__properties[channel_source_device_property.name] = channel

        return channel

    def property_get(self, name):
        """
        Returns the current :class:`~samples.sample.Sample` specified
        by *name* from the devices property list.

        """

        channel = self.__get_property_channel(name)
        return channel.producer_get()

    def property_set(self, name, sample):
        """
        Sets property specified by the string *name* to the
        :class:`~samples.sample.Sample` object *sample* and returns
        that value.

        """

        channel = self.__get_property_channel(name)
        return channel.producer_set(sample)

    def property_exists(self, name):
        """
        Determines if a property specified by *name* exists.

        """

        if name in self.__properties:
            return True
        return False

    def property_list(self):
        """
        Returns a list of all properties for the device.

        """

        return [name for name in self.__properties]

    def remove_all_properties(self):
        """
        Removes all properties from the set of device properties.

        """

        channel_db = self.get_channel_database()

        for chan in self.__properties:
            channel_name = "%s.%s" % (self._name, chan)
            chan_obj = channel_db.channel_remove(channel_name)
            if chan_obj:
                del chan_obj
        self.__properties = { }

    def remove_one_property(self, chan):
        """
        Removes one named property from the set of device properties.
        """

        channel_db = self.get_channel_database()

        channel_name = "%s.%s" % (self._name, chan)
        try:
            chan_obj = channel_db.channel_remove(channel_name)
            if chan_obj:
                del chan_obj
            self.__properties.pop(chan)
        except:
            self._tracer.debug(traceback.format_exc())
            pass
        return

    def get_time_of_last_data(self):
        """Get the time of last data update, in time.time() format.

        Return is None if the device does not support
        """
        return self.__last_data_timestamp

    def set_time_of_last_data(self, t=None):
        """Update the time of last data update
        """
        if t is None:
            t = digitime.time()
        self.__last_data_timestamp = t

    def get_data_update_rate_seconds(self):
        """Get the expected data refresh rate (in seconds). This
        is used by various routines to monotor device health.

        Return is None if the device does not support
        """
        return self.__data_update_rate

    def set_data_update_rate_seconds(self, rate):
        """Update the expected data refresh rate.
        """
        self.__data_update_rate = rate

    def merge_settings(self, orig, addin):
        # safely add-in settings to those from derived classes
        #
        # NOTE: If a setting with the same name is found,
        #       save the original and discard the new/add-in one

        if orig is None or len(orig) == 0:
            # then there are no original-class settings
            return addin

        for add1 in addin:
            # for each new setting
            use = True
            for orig1 in orig:
                # compare to those from original/derived class
                if orig1.name == add1.name:
                    # then ignore new setting, use original/derived classes
                    try:
                        self._tracer.warning("Discard Duplicate Setting: %s", add1.name)
                    except AttributeError:
                        # may not yet be initialized
                        pass
                    use = False
                    break

            if use: # else append new setting to derived classes
                orig.append(add1)

        return orig


    def merge_properties(self, orig, addin):
        # safely add-in properties to those from from derived classes
        if orig is None or len(orig) == 0:
            # then there are no original/derived-class settings
            orig = addin

        else:
            orig.extend(addin)
        return orig


# internal functions & classes

