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
Dia Tank device. It represents a physical tank which displays its level, 
temperature, valves and alarm status. It needs a Massa M3 sensor device to 
work properly and two DIA channels to control the status of the valves. 

Settings:

* **tank_sensor_device** Name of a of a Massa M3 instance running in the 
  DIA framework.

* **input_valve_channel** Name of an existing DIA channel to be interpreted 
  as Input Valve status.

* **output_valve_channel** Name of an existing DIA channel to be interpreted 
  as Output Valve status.

* **tank_height** Height of the tank, in meters.

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

      - name: tank0
        driver: devices.tanks.tank:Tank
        settings:
            tank_sensor_device: tank_sensor0
            input_valve_channel: xbib0.led1
            output_valve_channel: xbib0.led2
            tank_height: 3.5
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
import time
import random ##TODO Max CR: Unused import random.

# Constants
VALVE_IN="valve_in"
VALVE_OUT="valve_out"

LEVEL_ALARM="level_alarm"
TEMPERATURE_ALARM="temperature_alarm"
MINIMUM_LIMIT=0
MAXIMUM_LIMIT=1

LEVEL_ALARM_MESSAGE="Tank level reached %s%%"
TEMPERATURE_ALARM_MESSAGE="Tank temperature reached %sC"

FILLING_MESSAGE=" while filling."
DRAINING_MESSAGE=" while draining."

ALARM_SEPARATOR="@@"

DISTANCE_CHANNEL="distance"
TEMPERATURE_CHANNEL="temperature"

INCH_TO_METER = 0.0254

#Exception classes
class TankError(Exception):
    pass

# Classes
class Tank(DeviceBase):

    # Variables
    current_level = 50
    current_temperature= 10.0
    level_growing = False
    temperature_growing = False
    max_level_alarm = None
    min_level_alarm = None
    max_temperature_alarm = None
    min_temperature_alarm = None
    level_alarm_high_triggered = False
    level_alarm_low_triggered = False
    temperature_alarm_high_triggered = False
    temperature_alarm_low_triggered = False
    massa_sensor_device = ""
    tank_height = 2.0
    input_valve = ""
    output_valve = ""
    input_valve_channel = None
    output_valve_channel = None

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        # Settings Table Definition:
        settings_list = [
            Setting(
                    name='tank_sensor_device', type=str, required=True, 
                    default_value=""),
            Setting(
                    name='input_valve_channel', type=str, required=True, 
                    default_value=""),
            Setting(
                    name='output_valve_channel', type=str, required=True, 
                    default_value=""),
            Setting(
                    name='tank_height', type=float, required=True, 
                    default_value=2.0,
                    verify_function=lambda x: x > 0.0),
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

        # Channel Properties Definition:
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
                    
                    
            
        ##TODO: Max CR: level_alarm and temperature alarm should be replaced
        ## with LEVEL_ALARM and TEMPERATURE ALARM constants that are defined
        ## This will ensure that they are kept in synch at all parts of the
        ## code.
            
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
                    initial=Sample(timestamp=0, value=False),
                    perms_mask=DPROP_PERM_GET, 
                    options=DPROP_OPT_AUTOTIMESTAMP),
        ]

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

    ## Functions which must be implemented to conform to the DeviceBase
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
            self.__tracer.error("Settings rejected/not found: %s %s", 
                                rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)
      
    def start(self):
        """
            Start the device driver.  Returns bool.
        """

        # Take all the driver settings
        self.get_settings()
        
        ##TODO CR Max:  Reference to XBIB channels.  Is this supposed to work  
        ## with a tank or an xbib?
        
        # Subscribe to the Massa sensor and XBIB devices channels.
        self.cm = self.__core.get_service("channel_manager")
        self.cp = self.cm.channel_publisher_get()
                
        self.cp.subscribe(".".join([self.massa_sensor_device, 
                                    DISTANCE_CHANNEL]), 
                          self.update_level)
        self.cp.subscribe(".".join([self.massa_sensor_device, 
                                    TEMPERATURE_CHANNEL]), 
                          self.update_temperature)
        self.cp.subscribe(self.input_valve, self.update_valve)
        self.cp.subscribe(self.output_valve, self.update_valve)

    def stop(self):
        """
            Stop the device driver.  Returns bool.
        """

        return True

    # Internal functions & classes
    def update_level(self, channel):
        """
            Change the value of the level channel calculated from the Massa 
            sensor distance one.
        """

        try:
            # Obtain the distance
            distance = channel.get().value
            
            # Transform the distance from inches to meters
            distance = distance * INCH_TO_METER
            
            # Calculate the level percent from the tank height
            level_percent = 100 - (distance * 100.0 / self.tank_height)

            # Adjust the level percent to the max and min limits
            if level_percent < 0:
                level_percent = 0
            elif level_percent > 100:
                level_percent = 100

            # Check if the level is growing or descending
            if(level_percent > self.current_level):
                self.level_growing = True
            elif(level_percent < self.current_level):
                self.level_growing = False
            # Save the level percent for the next time
            self.current_level = level_percent

            # Set the new level percent to the level channel of the tank.
            self.property_set("level", 
                              Sample(0, int(level_percent), unit="%"))

            # Check if there is any level alarm
            self.check_level_alarm()
        except:
            ##TODO CR Max:  try: except: pass block here.  Should give  
            ## indication of an exception somehow.
            pass

    def update_temperature(self, channel):
        """
            Change the value of the level channel calculated from the Massa 
            sensor distance one.
        """

        try:
            # Obtain the temperature
            temperature = channel.get().value

            # Check if the temperature is growing or descending
            if(temperature > self.current_temperature):
                self.temperature_growing = True
            elif(temperature < self.current_temperature):
                self.temperature_growing = False
            # Save the temperature for the next time
            self.current_temperature = temperature

            # Set the new temperature to the temperature channel of the tank.
            self.property_set("temperature", 
                              Sample(0, float(temperature), unit="C"))

            # Check if there is any temperature alarm
            self.check_temperature_alarm()
        except:
            ##TODO CR Max:  try: except: pass block here.  Should give  
            ## indication of an exception somehow.
            pass


    ##TODO CR Max:  Docstring has another reference to XBib.  Is this 
    ## intended?
    def update_valve(self, channel):
        """
            Change the value of the valve channel to be the same as the 
            corresponding XBIB LED one.
        """

        try:
            # Obtain the valve value
            val = channel.get().value

            # Get the name of the channel and determine the valve to update
            channel_name = channel.name()
            if channel_name == self.input_valve:
                valve_to_change = VALVE_IN
            else:
                valve_to_change = VALVE_OUT

            # Set the new value of the corresponding valve.
            self.property_set(valve_to_change, 
                              Sample(0, val))
        except:
            ##TODO CR Max:  try: except: pass block here.  Should give  
            ## indication of an exception somehow.
            pass

    ##TODO CR Max:  Docstring has another reference to XBib.  Is this 
    ## intended?
    def set_valve(self, valve_name, sample):
        """
            Called when any tank valve channel changes its status. XBIB LED 
            channel corresponding to the valve must change too.
        """

        if valve_name == VALVE_IN:
            if self.input_valve_channel == None:
                try:
                    self.input_valve_channel = \
                        self.cm.channel_database_get().channel_get(
                                                           self.input_valve)
                except:
                    raise TankError(
                             "Channel %s does not exist" % self.input_valve)
            val = Boolean(self.input_valve_channel.get().value, 
                          style=STYLE_ONOFF)
            if sample.value != val:
                self.input_valve_channel.set(Sample
                                             (0, Boolean(sample.value, 
                                                         style=STYLE_ONOFF)))
        else:
            if self.output_valve_channel == None:
                try:
                    self.output_valve_channel = \
                        self.cm.channel_database_get().channel_get(
                                                           self.output_valve)
                except:
                    raise TankError(
                             "Channel %s does not exist" % self.output_valve)
            val = Boolean(self.output_valve_channel.get().value, 
                          style=STYLE_ONOFF)
            if sample.value != val:
                self.output_valve_channel.set(Sample
                                              (0, Boolean(sample.value, 
                                                          style=STYLE_ONOFF)))

    def check_level_alarm(self):
        """
            Check if there is any level alarm and call the alarm generator 
            method if necessary.
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

    def check_temperature_alarm(self):
        """
            Check if there is any level alarm and call the alarm generator 
            method if necessary.
        """

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
    
    ##TODO CR Max K: Using variable 'type' is overriding the 'type' builtin 
    ##  for this method. Maybe 'alarm_type' could be used instead.
    
    def generate_alarm(self, type, limit):
        """
            Generate the alarm with the given data: type (level or 
            temperature) and limit (maximum or minimum).
        """

        # Get the current time and add it to the alarm message.
        alarm_value = str(time.ctime())
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

    ##TODO CR Max K: Using variable 'type' is overriding the 'type' builtin 
    ##  for this method. Maybe 'alarm_type' could be used instead.
    def clear_alarm(self, type):
        """
            Clear the given alarm channel.
        """

        self.property_set(type, Sample(0, ""))

    def get_settings(self):
        """
            Read and save locally all the tank device settings.
        """

        self.massa_sensor_device = \
            SettingsBase.get_setting(self,"tank_sensor_device")
        self.input_valve = \
            SettingsBase.get_setting(self,"input_valve_channel")
        self.output_valve = \
            SettingsBase.get_setting(self,"output_valve_channel")
        self.tank_height = \
            SettingsBase.get_setting(self,"tank_height")
        self.max_level_alarm = \
            SettingsBase.get_setting(self,"max_level_alarm")
        self.min_level_alarm = \
            SettingsBase.get_setting(self,"min_level_alarm")
        self.max_temperature_alarm = \
            SettingsBase.get_setting(self,"max_temperature_alarm")
        self.min_temperature_alarm = \
            SettingsBase.get_setting(self,"min_temperature_alarm")

