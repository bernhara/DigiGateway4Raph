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

from devices.filter_channels.filter_channel_base import FilterChannelFactoryBase, FilterChannelBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import Sample
from core.tracing import get_tracer


class SampleAverageFactory(FilterChannelFactoryBase):
    def __init__(self, name, core_services):
        
        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='number_of_samples', type=int, required=False, default_value=0,
                  verify_function=lambda x: x > 0),
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
        number_of_samples = SettingsBase.get_setting(self, "number_of_samples")
        return SampleAverager(self._name, self._core, channel,
                              filter_channel, number_of_samples)
        
    
class SampleAverager(FilterChannelBase):
    def __init__(self, name, core, source_channel, filter_channel, number_of_samples):
        self._tracer = get_tracer(name)
        self._sample_queue = []
        self._number_of_samples = number_of_samples
        FilterChannelBase.__init__(self, core, source_channel, filter_channel)
        
    def _receive(self, channel):
        """\
            Called whenever there is a new sample on the channel
                that we are following/shadowing.

            Keyword arguments:

            channel -- the shadowed channel with the new sample
        """
        self._sample_queue.append(channel.get())
        if len(self._sample_queue) >= self._number_of_samples:
            average = self._average(list(x.value for x in self._sample_queue))
            self.property_set(Sample(value = average, unit = self._sample_queue[0].unit))
            self._sample_queue = []

    def _average(self, l):
        return (sum(l))/len(l)
