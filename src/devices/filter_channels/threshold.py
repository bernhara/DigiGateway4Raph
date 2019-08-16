############################################################################
#                                                                          #
# Copyright (c)2012 Digi International (Digi). All Rights Reserved.        #
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
Filter Channels : Threshold Alarms Filter.
"""

# imports
from devices.filter_channels.filter_channel_base import FilterChannelFactoryBase, FilterChannelBase
from channels.channel_source_device_property import ChannelSourceDeviceProperty,\
        DPROP_PERM_GET, DPROP_PERM_SET, DPROP_OPT_AUTOTIMESTAMP, Sample
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import Sample
from core.tracing import get_tracer

# constants

factory_tracer = get_tracer("ThresholdFactory")

class ThresholdFactory(FilterChannelFactoryBase):
    def __init__(self, name, core_services):
        """\
            Standard __init__ function.
        """

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='upper_threshold', type=float, required=True),
            Setting(
                name='lower_threshold', type=float, required=True),
            Setting(
                name='disable_lower', type=bool, required=False, default_value=False),
            Setting(
                name='disable_upper', type=bool, required=False, default_value=False),
        ]

        ## Channel Properties Definition:
        property_list = []
                                            
        ## Initialize the DeviceBase interface:
        FilterChannelFactoryBase.__init__(self, name, core_services,
                                settings_list, property_list)
            
    def create_filter_channel(self, channel, filter_channel):
        """\
            Required override of the base channel's call of the same name.

            This allows us create/build a custom class to control the filter.

            Keyword arguments:

            channel -- the channel we are shadowing

            filter_channel -- the shadow/filter channel
        """
        upper_threshold = SettingsBase.get_setting(self, "upper_threshold")
        lower_threshold = SettingsBase.get_setting(self, "lower_threshold")
        disable_lower = SettingsBase.get_setting(self, "disable_lower")
        disable_upper = SettingsBase.get_setting(self, "disable_upper")
        return Thresholder(self._name, self._core, channel, filter_channel,
                           upper_threshold, lower_threshold,
                           disable_upper, disable_lower)


class Thresholder(FilterChannelBase):
    def __init__(self, name, core, source_channel, filter_channel,
                 upper_threshold, lower_threshold,
                 disable_upper, disable_lower):
        self._tracer = get_tracer(name)
        self._lower_threshold = lower_threshold
        self._upper_threshold = upper_threshold
        self._disable_lower = disable_lower
        self._disable_upper = disable_upper
        FilterChannelBase.__init__(self, name, core, source_channel, filter_channel)
        
    def _receive(self, channel):
        """\
            Called whenever there is a new sample on the channel
                that we are following/shadowing.

            Keyword arguments:

            channel -- the shadowed channel with the new sample
        """
        test_sample = channel.get()
        if (not self._disable_lower) and test_sample.value <= self._lower_threshold:
            self.property_set(test_sample)
            return
        if (not self._disable_upper) and test_sample.value >= self._upper_threshold:
            self.property_set(test_sample)
            return
