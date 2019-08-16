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
A device driver implementation for the AutoTap LDVDS.
"""

# imports
import threading
import time
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from ldvds_implementation import AutoTapStreamer
from common.shutdown import SHUTDOWN_WAIT

# constants

PID_NAME_MAP = {0x00: "vehicle_speed", 0x01: "engine_speed",
          0x02: "throttle_position", 0x03: "odometer",
          0x04: "fuel_level", 0x05: "fuel_level_remaining",
          0x06: "transmission_gear", 0x08: "ignition_status",
          0x09: "mil_status", 0x0A: "airbag_dash_indicator",
          0x0B: "abs_dash_indicator", 0x0C: "fuel_rate",
          0x0D: "battery_voltage", 0x0E: "pto_status",
          0x0F: "seatbelt_fastened", 0x10: "misfire_monitor",
          0x11: "fuel_system_monitor", 0x12: "comprehensive_component_monitor",
          0x13: "catalyst_monitor", 0x14: "heated_catalyst_monitor",
          0x15: "evaporative_system_monitor",
          0x16: "secondary_air_system_monitor",
          0x17: "ac_system_refrigerant_monitor", 0x18: "oxygen_sensor_monitor",
          0x19: "oxygen_sensor_heater_monitor", 0x1A: "egr_system_monitor",
          0x1B: "brake_switch_status", 0x1D: "cruise_control_status",
          0x1E: "turn_signal_status", 0x1F: "oil_pressure_lamp",
          0x20: "brake_indicator_light", 0x21: "coolant_hot_lamp",
          0x22: "trip_odometer", 0x23: "trip_fuel_consumption"}

PID_TYPE_MAP = {0x00: float, 0x01: float,
          0x02: float, 0x03: float,
          0x04: float, 0x05: float,
          0x06: str, 0x08: str,
          0x09: str, 0x0A: str,
          0x0B: str, 0x0C: float,
          0x0D: float, 0x0E: str,
          0x0F: str, 0x10: str,
          0x11: str, 0x12: str,
          0x13: str, 0x14: str,
          0x15: str, 0x16: str,
          0x17: str, 0x18: str,
          0x19: str, 0x1A: str,
          0x1B: str, 0x1D: str,
          0x1E: str, 0x1F: str,
          0x20: str, 0x21: str,
          0x22: float, 0x23: float}

# exception classes

# interface functions

# classes


class AutoTapLDVDS(DeviceBase, threading.Thread):

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Settings Table Definition:
        settings_list = [
            Setting(
            name='xbee_device_manager', type=str, required=True),
            Setting(
            name='extended_address', type=str, required=True),
            Setting(
            name='update_rate', type=float, required=False, default_value=5.0,
              verify_function=lambda x: x > 0.0),
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ### vehicle parameters
            ChannelSourceDeviceProperty(name="vehicle_speed", type=float,
            initial=Sample(timestamp=0, value=-1.0),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="engine_speed", type=float,
            initial=Sample(timestamp=0, value=-1.0),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="throttle_position", type=float,
            initial=Sample(timestamp=0, value=-1.0),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="odometer", type=float,
            initial=Sample(timestamp=0, value=-1.0),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="fuel_level", type=float,
            initial=Sample(timestamp=0, value=-1.0),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="fuel_level_remaining",
                                        type=float,
            initial=Sample(timestamp=0, value=-1.0),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="transmission_gear", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="ignition_status", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="mil_status", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="airbag_dash_indicator", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="abs_dash_indicator", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="fuel_rate", type=float,
            initial=Sample(timestamp=0, value=-1.0),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="battery_voltage", type=float,
            initial=Sample(timestamp=0, value=-1.0),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="pto_status", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="seatbelt_fastened", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="misfire_monitor", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="fuel_system_monitor", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="comprehensive_component_monitor",
                                        type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="catalyst_monitor", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="heated_catalyst_monitor",
                                        type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="evaporative_system_monitor",
                                        type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="secondary_air_system_monitor",
                                        type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="ac_system_refrigerant_monitor",
                                        type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="oxygen_sensor_monitor", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="oxygen_sensor_heater_monitor",
                                        type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="egr_system_monitor", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="brake_switch_status", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="cruise_control_status", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="turn_signal_status", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="oil_pressure_lamp", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="coolant_hot_light", type=str,
            initial=Sample(timestamp=0, value="?"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="trip_odometer", type=float,
            initial=Sample(timestamp=0, value=-1.0),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="trip_fuel_consumption",
                                        type=float,
            initial=Sample(timestamp=0, value=-1.0),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ### static vehicle parameters

            ChannelSourceDeviceProperty(name="vin", type=str,
            initial=Sample(timestamp=0, value="not acquired"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="supported_parameters", type=str,
            initial=Sample(timestamp=0, value="not acquired"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="diagnostic_trouble_codes",
                                        type=str,
            initial=Sample(timestamp=0, value="not acquired"),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="ready_for_communication",
                                        type=int,
            initial=Sample(timestamp=0, value=0),
            perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            # settable properties
            ChannelSourceDeviceProperty(name="force_redetect", type=int,
            perms_mask=DPROP_PERM_SET,
            set_cb=self.prop_set_force_redetect),
        ]

        ## Initialize the Devicebase interface:
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
        try:
            if not threading.Thread.isAlive(self):
                return
        except:
            return

        if 'update_rate' in accepted and \
               accepted['update_rate'] > SHUTDOWN_WAIT:
            self.__tracer.warning('Long update_rate setting may ' +
                                  'interfere with shutdown of DIA.')


        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)


    def start(self):
        """Start the device driver.  Returns bool."""
        threading.Thread.start(self)
        return True

    def stop(self):
        """Stop the device driver.  Returns bool."""
        self.__stopevent.set()
        return True


    ## Locally defined functions:
    # Property callback functions:
    def prop_set_force_redetect(self, ignored_int):
        self.__autotap.forceRedetect()

    # Threading related functions:
    def run(self):
        """run when our device driver thread is started"""

        self.apply_settings()

        addr = SettingsBase.get_setting(self, 'extended_address')
        xbee_manager = SettingsBase.get_setting(self, 'xbee_device_manager')
        dm = self.__core.get_service("device_driver_manager")
        xbee_manager = dm.instance_get(xbee_manager)
        self.__autotap = AutoTapStreamer(xbee_manager, addr)

        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break

            if self.property_get("ready_for_communication").value == 0:
                if self.__autotap.readyForCommunication():
                    vin = self.__autotap.getVIN()
                    supported_parameters = []
                    for pid in self.__autotap.getSupportedParameters():
                        supported_parameters.append(
                            AutoTapStreamer.PID_NAME_MAP[pid])

                    self.property_set("ready_for_communication", Sample(0, 1))
                    self.property_set("vin", Sample(0, vin))
                    self.property_set("supported_parameters",
                                      Sample(0, str(supported_parameters)))

            if self.property_get("ready_for_communication").value == 1:
                for pid in self.__autotap.getSupportedParameters():
                    val = self.__autotap.getParameterValues([pid])
                    pidValue = self.__autotap.\
                               convertValueToReadableFormat(pid, val[pid])
                    self.property_set(PID_NAME_MAP[pid],
                                  Sample(0, PID_TYPE_MAP[pid](pidValue)))

            time.sleep(SettingsBase.get_setting(self, "update_rate"))

# internal functions & classes
