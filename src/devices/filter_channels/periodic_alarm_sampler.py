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
from threading import Lock
from core.tracing import get_tracer


class PeriodicAlarmSamplerFactory(FilterChannelFactoryBase):
    """This module will sample a channel periodically and if the channel is in a particular state then
    it will forward the sample to the filter channel.  This was originally written for a DIO in
    alarm state where the state wasn't updated unless it changed.  This creates a filter channel
    the continues creating samples while the alarm state is asserted."""
    def __init__(self, name, core_services):
        self._scheduler = core_services.get_service("scheduler")
        
        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='interval', type=float, required=False, default_value=0.0,
                  verify_function=lambda x: x > 1.0),
            Setting(
                name='trigger_value', type=bool, required=False, default_value=True)
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
        interval = SettingsBase.get_setting(self, "interval")
        trigger_value = SettingsBase.get_setting(self, "trigger_value")
        return SampleAverager(self._name, self._core, channel, filter_channel,
                              interval, trigger_value, self._scheduler)
        
    
class SampleAverager(FilterChannelBase):
    def __init__(self, name, core, source_channel, filter_channel,
                 interval, trigger_value, scheduler):
        self._tracer = get_tracer(name)
        self._interval = interval
        self._trigger_condition = trigger_value
        self._scheduled_event_handle = None
        self._scheduler = scheduler
        self._scheduler_lock = Lock()
        FilterChannelBase.__init__(self, name, core, source_channel, filter_channel)
        
    def _receive(self, channel):
        """\
            Called whenever there is a new sample on the channel
                that we are following/shadowing.

            Keyword arguments:

            channel -- the shadowed channel with the new sample
        """
        self._tracer.info("sample received in periodic alarm %s, %s, %s", channel.get(), channel.get().value, self._trigger_condition)
        if channel.get().value == self._trigger_condition:
            self._tracer.info("sample passed test in periodic alarm")
            self.property_set(Sample(value = self._trigger_condition))
            self._schedule_event()
        else:
            self._scheduler_lock.acquire()
            try:
                try:
                    if self._scheduled_event_handle:
                        self._scheduler.cancel(self._scheduled_event_handle)
                        self._scheduled_event_handle = None
                except ValueError:
                    pass #The event has already occured, nothing to remove
            finally:
                self._scheduler_lock.release()
            
    def _interval_check(self):
        self.property_set(Sample(value = self._trigger_condition))
        self._schedule_event()

    def _schedule_event(self):
        self._tracer.info("periodic_alarm_sampler forwarding sample")
        self._scheduler_lock.acquire()
        try:
            try:
                if self._scheduled_event_handle:
                    self._scheduler.cancel(self._scheduled_event_handle)
                    self._scheduled_event_handle = None
            except ValueError:
                pass #The event has already occured, nothing to remove
            self._scheduled_event_handle = self._scheduler.schedule_after(self._interval,
                                                                          self._interval_check)
        finally:
            self._scheduler_lock.release()
        
