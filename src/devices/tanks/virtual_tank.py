############################################################################
#                                                                          #
# Copyright (c)2010, Digi International (Digi). All Rights Reserved.       #
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
Dia Virtual Tank device. It represents a virtual tank which displays its 
level, temperature, valves and alarm status. As it is completely simulated 
by the DIA framework, it doesn't depend on any other DIA devices.

Settings:

* **volume** Total volume of the tank, in liters.

* **initial_level** The initial level of the tank, (%).

* **initial_temperature** The initial temperature of the tank, (C).

* **inflow_rate** Flow rate of the input valve (liters/second).

* **outflow_rate** Flow rate of the output valve (liters/second).

* **min_level_alarm** The minimum value of the tank level (%) to trigger a 
  high level alarm. Leave it in blank to disable the high level alarm.

* **max_level_alarm** The maximum value of the tank level (%) to trigger a 
  low level alarm. Leave it in blank to disable the low level alarm.

* **min_temperature_alarm** The minimum value of the temperature (C) to 
  trigger a high temperature alarm. Leave it in blank to disable the high 
  temperature alarm.

* **max_temperature_alarm** The maximum value of the temperature (C) to 
  trigger a low temperature alarm. Leave it in blank to disable the low 
  temperature alarm.

YML Example::

      - name: tank_v0
        driver: devices.tanks.virtual_tank:VirtualTank
        settings:
            volume: 5000
            initial_level: 40
            initial_temperature: 15
            inflow_rate: 5
            outflow_rate: 10
            min_level_alarm: 10
            max_level_alarm: 90
            min_temperature_alarm: 6
            max_temperature_alarm: 18
"""

# Imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.types.boolean import Boolean, STYLE_ONOFF
import threading
import digitime
import random

# Constants
VALVE_IN="valve_in"
VALVE_OUT="valve_out"

LEVEL_ALARM="level_alarm"
TEMPERATURE_ALARM="temperature_alarm"
MINIMUM_LIMIT=0
MAXIMUM_LIMIT=1

TEMPERATURE_MIN_LIMIT=-25
TEMPERATURE_MAX_LIMIT=50

LEVEL_ALARM_MESSAGE="Tank level reached %s%%"
TEMPERATURE_ALARM_MESSAGE="Tank temperature reached %sC"

FILLING_MESSAGE=" while filling."
DRAINING_MESSAGE=" while draining."

ALARM_SEPARATOR="@@"

# Classes
class VirtualTank(DeviceBase, threading.Thread):

    # Variables
    valve_in_status = False
    valve_out_status = False
    total_volume= 0
    current_volume = 0
    current_level = 0
    current_temperature= 0.0
    level_growing = False
    temperature_growing = False
    max_level_alarm = 0
    min_level_alarm = 0
    max_temperature_alarm = 0
    min_temperature_alarm = 0
    level_alarm_high_triggered = False
    level_alarm_low_triggered = False
    temperature_alarm_high_triggered = False
    temperature_alarm_low_triggered = False

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Settings Table Definition:
        settings_list = [
            Setting(
                    name='volume', type=int, required=True, 
                    default_value=5000,
                    verify_function=lambda x: x >= 1),
            Setting(
                    name='initial_level', type=int, required=False, 
                    default_value=50,
                    verify_function=lambda x: x >= 0 and x <= 100),
            Setting(
                    name='initial_temperature', type=int, required=False, 
                    default_value=12,
                    verify_function=lambda x: x >= TEMPERATURE_MIN_LIMIT and x <= TEMPERATURE_MAX_LIMIT),
            Setting(
                    name='inflow_rate', type=float, required=False, 
                    default_value=10,
                    verify_function=lambda x: x >= 0),
            Setting(
                    name='outflow_rate', type=float, required=False, 
                    default_value=20,
                    verify_function=lambda x: x >= 0),
            Setting(
                    name='min_level_alarm', type=int, required=False, 
                    default_value=None,
                    verify_function=lambda x: x >= 0 and x<=100),
            Setting(
                    name='max_level_alarm', type=int, required=False, 
                    default_value=None,
                    verify_function=lambda x: x > 0 and x<=100),
            Setting(
                    name='min_temperature_alarm', type=int, required=False, 
                    default_value=None,
                    verify_function=lambda x: x >= 0),
            Setting(
                    name='max_temperature_alarm', type=int, required=False, 
                    default_value=None,
                    verify_function=lambda x: x >= 0),
        ]

        ## Channel Properties Definition:
        property_list = [
            ChannelSourceDeviceProperty(
                    name="level", type=int,
                    initial=Sample(timestamp=0, value=0, unit="%"),
                    perms_mask=DPROP_PERM_GET, 
                    options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                    name="temperature", type=float,
                    initial=Sample(timestamp=0, value=0.0, unit="C"),
                    perms_mask=DPROP_PERM_GET, 
                    options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                    name="valve_in", type=Boolean,
                    initial=Sample(timestamp=0, 
                                   value=Boolean(False, style=STYLE_ONOFF)),
                    perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET), 
                    options=DPROP_OPT_AUTOTIMESTAMP, 
                    set_cb=lambda sample: self.set_valve(VALVE_IN, sample)),
            ChannelSourceDeviceProperty(
                    name="valve_out", type=Boolean,
                    initial=Sample(timestamp=0, 
                                   value=Boolean(False, style=STYLE_ONOFF)),
                    perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET), 
                    options=DPROP_OPT_AUTOTIMESTAMP, 
                    set_cb=lambda sample: self.set_valve(VALVE_OUT, sample)),
            ChannelSourceDeviceProperty(
                    name="level_alarm", type=str,
                    initial=Sample(timestamp=0, value=""),
                    perms_mask=DPROP_PERM_GET, 
                    options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                    name="temperature_alarm", type=str,
                    initial=Sample(timestamp=0, value=""),
                    perms_mask=DPROP_PERM_GET, 
                    options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                    name="virtual", type=bool,
                    initial=Sample(timestamp=0, value=True),
                    perms_mask=DPROP_PERM_GET, 
                    options=DPROP_OPT_AUTOTIMESTAMP),
        ]

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

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
            self.__tracer.error("Settings rejected/not found: %s %s", 
                                rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        """
            Start the device driver.  Returns bool.
        """

        threading.Thread.start(self)
        return True

    def stop(self):
        """
            Stop the device driver.  Returns bool.
        """
        self.__stopevent.set()
        return True

    # Threading related functions:
    def run(self):
        """run when our device driver thread is started"""

        # Take all the driver settings
        self.get_settings()

        # Save the current level percent
        self.current_level = self.initial_level
        # Save the current temperature
        self.current_temperature = self.initial_temperature
        # Obtain and save the current tank volume
        self.current_volume = self.get_initial_volume(self.initial_level)

        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break

            # Calculate the new level percent of the tank
            new_level = self.get_new_volume_percent()
            # Check if the level is growing or descending
            if(new_level > self.current_level):
                self.level_growing = True
            elif(new_level < self.current_level):
                self.level_growing = False
            # Save the level percent for the next time
            self.current_level = new_level

            # Calculate the new temperature of the tank
            new_temperature = self.get_new_temperature()
            # Check if the temperature is growing or descending
            if(new_temperature > self.current_temperature):
                self.temperature_growing = True
            elif(new_temperature < self.current_temperature):
                self.temperature_growing = False
            # Save the temperature for the next time
            self.current_temperature = new_temperature

            # Set the new level percent on its corresponding channel
            self.set_new_level(self.current_level)
            # Set the new temperature on its corresponding channel
            self.set_new_temperature(self.current_temperature)
            # Check if any alarm should be triggered
            self.check_alarms()

            # Sleep one second
            digitime.sleep(1)

# Internal functions & classes
    def set_valve(self, valve_name, sample):
        """
            Change the value of the given valve. Save the status of the 
            valve internally for the level calculation method.
        """

        if valve_name == VALVE_IN:
            if sample.value == Boolean(False, style=STYLE_ONOFF):
                self.valve_in_status = False
            else:
                self.valve_in_status = True
        else:
            if sample.value == Boolean(False, style=STYLE_ONOFF):
                self.valve_out_status = False
            else:
                self.valve_out_status = True

        # Set the corresponding valve channel with the given sample value
        self.property_set(valve_name,
                          Sample(0, Boolean(sample.value, style=STYLE_ONOFF)))

    def get_new_volume_percent(self):
        """
            Calculate the new level percent of the tank. As this method is 
            called each second, the level calculated must 
        """

        volume_difference = 0
        if self.valve_in_status == True:
            volume_difference += self.inflow_rate
        if self.valve_out_status == True:
            volume_difference -= self.outflow_rate
        self.current_volume += volume_difference

        # Check that the volume doesn't break the logical limits
        if self.current_volume > self.total_volume:
            self.current_volume = self.total_volume
        elif self.current_volume < 0:
            self.current_volume = 0

        # Calculate the level percent from the volume
        percent = self.current_volume*100/self.total_volume
        return percent

    def get_new_temperature(self):
        """
            Calculate the new temperature of the tank. The temperature 
            difference must be very little because this method will be called 
            each second. 
        """

        temperature = self.current_temperature
        difference = random.randint(0,10)/100.0
        if random.randint(0,100) > 50:
            temperature += difference
            if (temperature > TEMPERATURE_MAX_LIMIT):
                temperature = TEMPERATURE_MAX_LIMIT
        else:
            temperature -= difference
            if (temperature < TEMPERATURE_MIN_LIMIT):
                temperature = TEMPERATURE_MIN_LIMIT
        return temperature

    def get_initial_volume(self, level):
        """
            Obtain the initial volume of liquid depending on the initial 
            level percent of the tank.
        """

        volume = self.initial_level * self.total_volume / 100
        return volume

    def set_new_level(self, level):
        """
            Write the given level percent in the level channel of the 
            device.
        """

        self.property_set("level",
                          Sample(0, int(level), unit="%"))

    def set_new_temperature(self, temperature):
        """
            Write the given temperature in the temperature channel of the 
            device.
        """

        self.property_set("temperature",
                          Sample(0, float(temperature), unit="C"))

    def check_alarms(self):
        """
            Check if there is any level or temperature alarm and call the 
            alarm generator method if necessary.
        """

        # Low level alarm
        # Check if the low level alarm is configured
        if self.min_level_alarm != None:
            if (self.current_level <= self.min_level_alarm):
                if (not self.level_alarm_low_triggered
                    and self.level_growing == False):
                    self.generate_alarm(LEVEL_ALARM, MINIMUM_LIMIT)
                    self.level_alarm_low_triggered = True
                    self.level_alarm_high_triggered = False
            else:
                self.level_alarm_low_triggered = False

        # High level alarm
        # Check if the high level alarm is configured
        if self.max_level_alarm != None:
            if(self.current_level >= self.max_level_alarm):
                if (not self.level_alarm_high_triggered
                    and self.level_growing == True):
                    self.generate_alarm(LEVEL_ALARM, MAXIMUM_LIMIT)
                    self.level_alarm_high_triggered = True
                    self.level_alarm_low_triggered = False
            else:
                self.level_alarm_high_triggered = False

        # Low temperature alarm
        # Check if the low temperature alarm is configured
        if self.min_temperature_alarm != None:
            if (self.current_temperature <= self.min_temperature_alarm):
                if (not self.temperature_alarm_low_triggered
                    and self.temperature_growing == False):
                    self.generate_alarm(TEMPERATURE_ALARM, MINIMUM_LIMIT)
                    self.temperature_alarm_low_triggered = True
                    self.temperature_alarm_high_triggered = False
            else:
                self.temperature_alarm_low_triggered = False

        # High temperature alarm
        # Check if the high temperature alarm is configured
        if self.max_temperature_alarm != None:
            if(self.current_temperature >= self.max_temperature_alarm):
                if (not self.temperature_alarm_high_triggered
                    and self.temperature_growing == True):
                    self.generate_alarm(TEMPERATURE_ALARM, MAXIMUM_LIMIT)
                    self.temperature_alarm_high_triggered = True
                    self.temperature_alarm_low_triggered = False
            else:
                self.temperature_alarm_high_triggered = False

    def generate_alarm(self, type, limit):
        """
            Generate the alarm with the given data: type (level or 
            temperature) and limit (maximum or minimum).
        """

        # Get the current time and add it to the alarm message.
        alarm_value = digitime.asctime()
        alarm_value += ALARM_SEPARATOR
        # Check the alarm type
        # Level alarm
        if type == LEVEL_ALARM:
            if limit == MINIMUM_LIMIT:
                alarm_value += LEVEL_ALARM_MESSAGE %self.min_level_alarm \
                + DRAINING_MESSAGE
            else:
                alarm_value += LEVEL_ALARM_MESSAGE %self.max_level_alarm \
                + FILLING_MESSAGE
        # Temperature alarm
        else:
            if limit == MINIMUM_LIMIT:
                alarm_value += TEMPERATURE_ALARM_MESSAGE \
                    %self.min_temperature_alarm
            else:
                alarm_value += TEMPERATURE_ALARM_MESSAGE \
                    %self.max_temperature_alarm

        # Set the alarm message to the corresponding channel
        self.property_set(type, Sample(0, alarm_value))

    def clear_alarm(self, type):
        """
            Clear the given alarm channel.
        """

        self.property_set(type, Sample(0, ""))

    def get_settings(self):
        """
            Read and save locally all the tank device settings.
        """

        self.total_volume = \
            SettingsBase.get_setting(self,"volume")
        self.initial_level = \
            SettingsBase.get_setting(self,"initial_level")
        self.initial_temperature = \
            SettingsBase.get_setting(self,"initial_temperature")
        self.inflow_rate = \
            SettingsBase.get_setting(self,"inflow_rate")
        self.outflow_rate = \
            SettingsBase.get_setting(self,"outflow_rate")
        self.max_level_alarm = \
            SettingsBase.get_setting(self,"max_level_alarm")
        self.min_level_alarm = \
            SettingsBase.get_setting(self,"min_level_alarm")
        self.max_temperature_alarm = \
            SettingsBase.get_setting(self,"max_temperature_alarm")
        self.min_temperature_alarm = \
            SettingsBase.get_setting(self,"min_temperature_alarm")

