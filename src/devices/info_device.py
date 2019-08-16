############################################################################
#                                                                          #
# Copyright (c)2008-2013, Digi International (Digi). All Rights Reserved.  #
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
"""
The Info Device manages a collection of data channels describing the installation, such
a user assigned application name and version. Since these channels can be uploaded to
Device Cloud, large users can use the data for understanding application versions at various
 sites, and so on.

These data channels are included ONLY if the corresponding YML setting is not empty:
* 'name'        = a user assigned string, such as "Digi garden management"
* 'version'     = a user assigned string, such as "2.1.A2"
* 'sitename'    = a user assigned string, such as "Golden Valley #2"
* 'comment'     = a user assigned string, such as "Second site to go live"
* 'tags'        = a list as a string, such as "['fff', 'ggg', 23, ]"

These data channels are automatic, so always exist:
* 'build_date'  = a string with date/time created by make.py as dia.zip was built, such "2013-02-06T20:58:45Z"
* 'dia_version' = a string from the core DIA installed, such "2.2.0.1"
* 'python_version' = a string from the sys.version function, such as "2.4.3"
"""
# imports
import digitime
import sys

from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.dia_version import DIA_VERSION
from common.helpers.parse_duration import parse_time_duration
from common.helpers.nvstash import nvStash

# requires DIA 2.2 or newer
try:
    from zip_build_date import DIA_ZIP_BUILD_DATE, DIA_ZIP_BUILD_DATE_RAW
except ImportError:
    print "InfoDevice.__init__() Unable to import 'DIA_ZIP_BUILD_DATE'."
    DIA_ZIP_BUILD_DATE = None

# classes

class InfoDevice(DeviceBase):

    DEF_NAME = ''
    DEF_VERSION = ''
    DEF_SITENAME = ''
    DEF_COMMENT = ''
    DEF_TAGS = ''
    DEF_REFRESH = 'none'

    def __init__(self, name, core_services, settings=None, properties=None):
        """
        Standard device init function.
        """

        # DeviceBase will create:
        # self._name, self._core, self._tracer,

        self._last_timestamp = None
        self._next_refresh = None
        self._refresh_secs = None

        self._tag_list = []

        settings_list = [
            # name: "Filter Screen Flush Control"
            # application name
            Setting(name='name', type=str, required=False,
                    default_value=self.DEF_NAME),

            # name: "1.3b Summer"
            # is a freeform string, so isn't forced to be like 1.0 (major.minor)
            # users could be disciplined enough to use floats as string
            Setting(name='version', type=str, required=False,
                    default_value=self.DEF_VERSION),

            # sitename: "Golden Valley Pump #4"
            Setting(name='sitename', type=str, required=False,
                    default_value=self.DEF_SITENAME),

            # comment: "Is an old Vermison model 23"
            # a single free-form string
            Setting(name='comment', type=str, required=False,
                    default_value=self.DEF_COMMENT),

            # tags: "['active', 6573, 'Tom Jones']"
            # can be any list of Python elements
            Setting(name='tags', type=list, required=False,
                    default_value=self.DEF_TAGS),

            # how often to refresh the channels, such as '1 day'
            # ['ms','sec','min','hr','day']
            Setting(name='refresh', type=str, required=False,
                    default_value=self.DEF_REFRESH),

        ]
        # Add our settings_list entries into the settings passed to us.
        settings = self.merge_settings(settings, settings_list)

        ##No properties defined at first
        property_list = [
            ChannelSourceDeviceProperty(name="name", type=str,
                initial=Sample(timestamp=0, value=self.DEF_NAME, unit=""),
                perms_mask=DPROP_PERM_GET),
            ChannelSourceDeviceProperty(name="version", type=str,
                initial=Sample(timestamp=0, value=self.DEF_VERSION, unit=""),
                perms_mask=DPROP_PERM_GET),
            ChannelSourceDeviceProperty(name="sitename", type=str,
                initial=Sample(timestamp=0, value=self.DEF_SITENAME, unit=""),
                perms_mask=DPROP_PERM_GET),
            ChannelSourceDeviceProperty(name="comment", type=str,
                initial=Sample(timestamp=0, value=self.DEF_COMMENT, unit=""),
                perms_mask=(DPROP_PERM_GET | DPROP_PERM_SET),
                set_cb=self.prop_set_comment),
            ChannelSourceDeviceProperty(name="tags", type=str,
                initial=Sample(timestamp=0, value=self.DEF_TAGS, unit=""),
                perms_mask=(DPROP_PERM_GET | DPROP_PERM_SET),
                set_cb=self.prop_set_tags),
            ChannelSourceDeviceProperty(name="build_date", type=str,
                initial=Sample(timestamp=0, value='', unit=""),
                perms_mask=DPROP_PERM_GET),
            ChannelSourceDeviceProperty(name="dia_version", type=str,
                initial=Sample(timestamp=0, value='', unit=""),
                perms_mask=DPROP_PERM_GET),
            ChannelSourceDeviceProperty(name="python_version", type=str,
                initial=Sample(timestamp=0, value='', unit=""),
                perms_mask=DPROP_PERM_GET),
        ]
        # Add our property_list entries into the properties passed to us.
        properties = self.merge_properties(properties, property_list)

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, name, core_services,
                                settings, properties)

    def start(self):
        """
        Starts the driver.
        Subscribes the driver to the channel_pattern.
        """
        self._tracer.calls("InfoDevice.start()")

        self._sched = self._core.get_service("scheduler")

        # this will be a singleton, perhaps None
        self.__nvstash = nvStash.get_instance_singleton()
        if self.__nvstash is None:
            self._tracer.debug("no NVRAM STASH active - all data is volatile.")
        else:
            self.__nvstash.load()

        self._last_timestamp = digitime.time()
        for tag in ("name", "version", "sitename", "comment", "tags"):
            x = str(SettingsBase.get_setting(self, tag))
            if tag in ("comment", "tags") and self.__nvstash is not None:
                # for these, over-write from NVSTASH is anything there
                nv = self.__nvstash.get('%s.%s' % (self._name, tag))
                if nv is not None:
                    x = nv

            if x is None or len(x) == 0:
                # then delete this channel
                self._tracer.debug("delete tag %s", tag)
                self.remove_one_property(tag)
            else:
                sam = Sample(self._last_timestamp, x, "")
                self._tracer.debug("initialize tag %s, val = %s", tag, x)
                self.property_set(tag, sam)
                self._tag_list.append(tag)

        # restart timer is appropriate, static refreshed above
        self.refresh_cb(refresh_static=False)

        return True

    def stop(self):
        """
        Stops the driver.
        """
        self._tracer.calls("InfoDevice.stop()")

        # cancel any out-standing events
        try:
            if self._next_refresh is not None:
                # then try to delete old one
                self._sched.cancel(self._next_refresh)
        except Exception, e:
            self._tracer.error(str(e))

        if self.__nvstash is not None:
            self.__nvstash.save()

        return True

    def refresh_cb(self, refresh_static=True):
        """
        Callback function to schedule refreshes for this device's properties
        """
        self._tracer.calls("InfoDevice.refresh_cb()")

        self.refresh(refresh_static)

        if self._refresh_secs is None:
            # make it self-starting
            x = SettingsBase.get_setting(self, 'refresh')
            if x in ("none", "0", "None"):
                self._refresh_secs = 0
            else:
                try:
                    self._refresh_secs = parse_time_duration(x, in_type='sec', out_type='sec')
                    self._tracer.debug("refresh rate (%s) adjusted to %d sec", x, self._refresh_secs)
                except:
                    self._tracer.warning("refresh rate (%s) was rejected; disabling refresh", x)
                    self._refresh_secs = 0

        if self._refresh_secs > 0:
            # then reschedule ourself
            self._next_refresh = self._sched.schedule_after(self._refresh_secs,
                                                            self.refresh_cb)
        return

    def refresh(self, refresh_static=True):
        """
        Refreshes the properties of this device
        """
        self._tracer.calls("InfoDevice.refresh()")

        self._last_timestamp = digitime.time()

        if refresh_static:
            for tag in self._tag_list:
                old = self.property_get(tag)
                sam = Sample(self._last_timestamp, old.value, old.unit)
                self.property_set(tag, sam)
                self._tracer.debug("refresh tag %s, %s", tag, sam)

        tag = "build_date"
        if DIA_ZIP_BUILD_DATE is None:
            sam = Sample(self._last_timestamp, 'Unknown')
        else:
            # we use the RAW time as the time-stamp
            sam = Sample(DIA_ZIP_BUILD_DATE_RAW, DIA_ZIP_BUILD_DATE)
        self.property_set(tag, sam)
        self._tracer.debug("refresh tag %s, sam = %s", tag, sam)

        tag = "dia_version"
        sam = Sample(self._last_timestamp, str(DIA_VERSION), '')
        self.property_set(tag, sam)
        self._tracer.debug("refresh tag %s, sam = %s", tag, sam)

        # note: for version we just want the base version like 2.4.3
        tag = "python_version"
        sam = Sample(self._last_timestamp, sys.version.split()[0], '')
        self.property_set(tag, sam)
        self._tracer.debug("refresh tag %s, sam = %s", tag, sam)

        return

    def prop_set_comment(self, sam):
        '''
        Set the power on the device and the power_on property.
        '''
        self._tracer.calls("prop_set_comment %s", sam)

        if not isinstance(sam, Sample):
            # the publish/sub pushes in the channel, not sample
            sam = sam.get()

        val = str(sam.value)
        if len(val) > 1:
            if val[0] == '+':
                # then append
                self._tracer.debug("append comment %s", val)
                sam.value = self.property_get("comment").value + val

        self._tracer.debug("set comment %s", sam)
        self.property_set("comment", sam)

        if self.__nvstash is not None:
            self.__nvstash.put('%s.comment' % self._name, sam.value)

        return

    def prop_set_tags(self, sam):
        '''
        Set the power on the device and the power_on property.

        At the time of this writing. This procedure is not yet
        implemented.
        '''
        self._tracer.calls("prop_set_tags %s", sam)

        if not isinstance(sam, Sample):
            # the publish/sub pushes in the channel, not sample
            sam = sam.get()

        return
