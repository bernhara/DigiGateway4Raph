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
Filter Channels : Threshold Alarms with Hysteresis Filter.
"""

# imports
from devices.filter_channels.filter_channel_base import FilterChannelFactoryBase,\
        FilterChannelBase
from channels.channel_source_device_property import ChannelSourceDeviceProperty,\
        DPROP_PERM_GET, DPROP_PERM_SET, DPROP_OPT_AUTOTIMESTAMP, Sample
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import Sample
from core.tracing import get_tracer

# constants

factory_tracer = get_tracer("ThresholdAlarmWithHysteresisFactory")


class ThresholdAlarmWithHysteresisFactory(FilterChannelFactoryBase):

    # Define what types of alarms we support.
    HIGH = 1
    LOW = 2
    HIGH_STRING = "High"
    LOW_STRING = "Low"

    def __init__(self, name, core_services):
        """\
            Standard __init__ function.
        """

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='alarm_type', type=str,   required=True,
                                   verify_function = self.__verify_alarm_type),
            Setting(
                name='threshold',  type=float, required=True,
                                   verify_function = self.__verify_threshold),
            Setting(
                name='hysteresis', type=float, required=True,
                                   verify_function = self.__verify_hysteresis),
            Setting(
                name='readings',   type=int,   required=False, default_value=1,
                                   verify_function = self.__verify_readings),
            Setting(
                name='continuous', type=bool,  required=False, default_value=False,
                                   verify_function = self.__verify_continuous),
        ]

        ## Channel Properties Definition:
        property_list = []

        ## Initialize the DeviceBase interface:
        FilterChannelFactoryBase.__init__(self, name, core_services,
                                settings_list, property_list)


    @staticmethod
    def __verify_alarm_type(alarm_type):
        """\
            Verify the Alarm Type the user has given us
        """
        if type(alarm_type) != str:
            factory_tracer.warning("Settings: " \
                           "'alarm_type' must be a str!")
            return False
        if alarm_type != "High" and alarm_type != "Low":
            factory_tracer.warning("Settings: " \
                           "'alarm_type' must be either 'High' or 'Low'!")
            return False
        return True

    @staticmethod
    def __verify_threshold(threshold):
        """\
            Verify the Threshold the user has given us
        """
        if type(threshold) != float:
            factory_tracer.warning("Settings: 'threshold' must be a float!")
            return False
        return True

    @staticmethod
    def __verify_hysteresis(hysteresis):
        """\
            Verify the Hysteresis the user has given us
        """
        if type(hysteresis) != float:
            factory_tracer.warning("Settings: 'hysteresis' must be a float!")
            return False
        return True

    @staticmethod
    def __verify_readings(readings):
        """\
            Verify the Readings value the user has given us
        """
        if type(readings) != int:
            factory_tracer.warning("Settings: 'readings' must be an int!")
            return False
        return True

    @staticmethod
    def __verify_continuous(continuous):
        """\
            Verify the Continuous value the user has given us
        """
        if type(continuous) != bool:
            factory_tracer.warning("Settings: 'continuous' must be a bool!")
            return False
        return True

    def create_filter_channel(self, source_channel, filter_channel):
        """\
            Required override of the base channel's call of the same name.

            This allows us create/build a custom class to control the filter.

            Keyword arguments:

            source_channel -- the channel we are shadowing

            filter_channel -- the shadow/filter channel
        """
        alarm_type_str = SettingsBase.get_setting(self, "alarm_type")
        threshold = SettingsBase.get_setting(self, "threshold")
        hysteresis = SettingsBase.get_setting(self, "hysteresis")
        readings = SettingsBase.get_setting(self, "readings")
        continuous = SettingsBase.get_setting(self, "continuous")

        if alarm_type_str == "High":
            alarm_type = ThresholdAlarmWithHysteresisFactory.HIGH
        elif alarm_type_str == "Low":
            alarm_type = ThresholdAlarmWithHysteresisFactory.LOW
        else:
            raise ValueError, "Alarm Type is not correct. Must be 'High' or 'Low'"

        return ThresholdAlarmWithHysteresis(self._name, self._core,
                                            source_channel, filter_channel,
                                            alarm_type, threshold,
                                            hysteresis, readings,
                                            continuous)

    def physically_create_filter_channel(self, original_channel, filter_channel_name):
        """\
            Optional override of the base channel's call of the same name.

            This allows us to create a new channel, and define its type,
               based on whatever type we desire it to be.

            Keyword arguments:

            original_channel -- the shadowed channel

            filter_channel_name -- the name of the channel we should create
        """
        filter_channel = ChannelSourceDeviceProperty(name = filter_channel_name,
            type = bool,
            initial = Sample(timestamp = 0, value = bool()),
            perms_mask = DPROP_PERM_GET | DPROP_PERM_SET,
            options = DPROP_OPT_AUTOTIMESTAMP)
        return filter_channel


class ThresholdAlarmWithHysteresis(FilterChannelBase):
    def __init__(self, name, core, source_channel, filter_channel,
                 alarm_type, threshold, hysteresis, readings, continuous):
        self._tracer = get_tracer(name)
        self._filter_channel = filter_channel
        self._alarm_type = alarm_type
        self._threshold = threshold
        self._hysteresis = hysteresis
        self._readings = readings
        self._continuous = continuous
        self.__above_count = 0
        self.__below_count = 0
        FilterChannelBase.__init__(self, name, core, source_channel, filter_channel)

    def _receive(self, channel):
        """\
            Called whenever there is a new sample on the channel
                that we are following/shadowing.

            Keyword arguments:

            channel -- the shadowed channel with the new sample
        """
        test_sample = channel.get()
        filter_channel_sample = self.property_get()

        # High type alarm...
        if self._alarm_type == ThresholdAlarmWithHysteresisFactory.HIGH:
            if test_sample.value >= self._threshold:
                self.__above_count += 1
                self.__below_count = 0
                self._tracer.info("Above Threshold Set HIGH Alarm...  Threshold: %f Readings: %d Hysteresis %f", self._threshold, self.__above_count, self._hysteresis)
                if self.__above_count >= self._readings:
                    if self._continuous == True or filter_channel_sample.value != True:
                        self._tracer.info("Threshold Alarm and count reached, setting!")
                        self.property_set(Sample(timestamp = test_sample.timestamp,
                                                 value = True))
            else:
                self.__above_count = 0
                # Only check if we are currently in an alarm condition.
                if filter_channel_sample.value == True:
                    # If previous value of the alarm is true, apply the hysteresis
                    # to determine whether we should unset to alarm.
                    if test_sample.value <= self._threshold - self._hysteresis:
                        self.__below_count += 1
                        self._tracer.info("Below Threshold Set HIGH Alarm...  Threshold: %f Readings: %d Hysteresis %f", self._threshold, self.__below_count, self._hysteresis)
                        if self.__below_count >= self._readings:
                            self._tracer.info("Threshold Alarm resolved, unsetting! Threshold: %f Hysteresis %f", self._threshold, self._hysteresis)
                            self.property_set(Sample(timestamp = test_sample.timestamp,
                                                     value = False))
                    else:
                        self._tracer.info("In DeadZone...  Threshold: %f Hysteresis %f", self._threshold, self._hysteresis)
                        self.__below_count = 0
                        if self._continuous == True:
                            self.property_set(Sample(timestamp = test_sample.timestamp,
                                                     value = True))

        # Low type alarm...
        else:

            if test_sample.value <= self._threshold:
                self.__above_count += 1
                self.__below_count = 0
                self._tracer.info("Above Threshold Set LOW Alarm...  Threshold: %f Readings: %d Hysteresis %f", self._threshold, self.__above_count, self._hysteresis)
                if self.__above_count >= self._readings:
                    if self._continuous == True or filter_channel_sample.value != True:
                        self._tracer.info("Threshold Alarm and count reached, setting!")
                        self.property_set(Sample(timestamp = test_sample.timestamp,
                                                 value = True))
            else:
                self.__above_count = 0
                # Only check if we are currently in an alarm condition.
                if filter_channel_sample.value == True:
                    # If previous value of the alarm is true, apply the hysteresis
                    # to determine whether we should unset to alarm.
                    if test_sample.value >= self._threshold + self._hysteresis:
                        self.__below_count += 1
                        self._tracer.info("Below Threshold Set LOW Alarm...  Threshold: %f Readings: %d Hysteresis %f", self._threshold, self.__below_count, self._hysteresis)
                        if self.__below_count >= self._readings:
                            self._tracer.info("Threshold Alarm resolved, unsetting! Threshold: %f Hysteresis %f", self._threshold, self._hysteresis)
                            self.property_set(Sample(timestamp = test_sample.timestamp,
                                                     value = False))
                    else:
                        self._tracer.info("In DeadZone...  Threshold: %f Hysteresis %f", self._threshold, self._hysteresis)
                        self.__below_count = 0
                        if self._continuous == True:
                            self.property_set(Sample(timestamp = test_sample.timestamp,
                                                     value = True))
