############################################################################
#                                                                          #
# Copyright (c)2008, 2009, Digi International (Digi). All Rights Reserved. #
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
Massa Model M3 Wireless Ultrasonic Level Sensor - DIA Driver

The following Massa M3 devices are supported:
    Model M3/150:   150kHz
    Model M3/150is: 150kHz
    Model M3/95:    95kHz
    Model M3/95is:  95kHz
    Model M3/50:    50kHz
    Model M3/50is:    50kHz

Vendor and Product Website can be found here:
    http://www.massa.com/air_products.htm

Settings:

* **sample_rate_sec:** The rate, in seconds, in which the device should take
  a sample.  (default value: 3600)
* **sleep_rate_sec:** The rate, in seconds, for how long the device should
  sleep before sending the DIA driver it's stored samples.
  (default value: 14400)
* **awake_time_sec:** The rate, in seconds, for how long the device should
  remain awake after it awakes and sends DIA it's samples.
  (default value: 30)

NOTE: A deeper explanation between the sample rate and sleep rate follows.
The Massa M3 can send and store up to 8 sensor samples per packet that it
automatically sends upon wake up.
Because of this, it is NOT necessary to have the sample rate and sleep
rate be equal to each other.
Instead, to optimize battery life, a more relaxed setting can be used.
If the XBee network that the Massa M3 is on is low traffic and pretty
reliable, it is recommended that given a sample rate of 'X', that the
sleep rate should be 4 * 'X'.
On the other hand, if the Massa M3 is on a less reliable network,
it is recommended that the given a sample rate of 'X', that the
sleep rate should be 2 * 'X'.

"""

# imports
import struct

from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from common.types.boolean import Boolean, STYLE_ONOFF, STYLE_YESNO
from channels.channel_source_device_property import *

from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import gw_extended_address_tuple
from devices.xbee.common.prodid import PROD_MASSA_M3
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep \
    import XBeeConfigNetworkSleep, SM_DISABLED

# constants

# exception classes

# interface functions

# classes
class MassaM3(XBeeBase):

    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [ [ 0xe8, 0xc105, 0x11 ] ]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [ PROD_MASSA_M3, ]

    GlobalDestinationID = 1
    GlobalSenderID = 251

    # Supported Massa M3 Models.
    MODEL_M3_150   = 50
    MODEL_M3_150IS = 52
    MODEL_M3_95    = 51
    MODEL_M3_95IS  = 53
    MODEL_M3_50    = 54
    MODEL_M3_50IS  = 55


    # State Table

    M3_STATE_SENSORINFO =         1
    M3_STATE_SETSLEEP0 =          2
    M3_STATE_SETINTERVAL =        3
    M3_STATE_CLEARHISTORY =       4
    M3_STATE_REBOOT =             5
    M3_STATE_GETHISTORY =         6
    M3_STATE_SETSENDAFTERWAKEUP = 7
    M3_STATE_SETSENDAWAKETIME   = 8
    M3_STATE_SETSLEEP =           9
    M3_STATE_RUNNING =            10


    # Command Table

    CommandReadEventDataFromTheHistoryBuffer              = 1
    CommandAcquireNewEventDataNoRecordToDataHistoryBuffer = 2
    CommandAcquireNewEventDataRecordToDataHistoryBuffer   = 3
    CommandAcquireUltrasonicWaveform                      = 10
    CommandBlockWriteToConfigurationRegisters             = 25
    CommandBlockReadFromConfigurationRegisters            = 35
    CommandRequestForMiscSensorInformation                = 100
    CommandClearDataHistoryBuffer                         = 101
    CommandResetEventCounter                              = 102
    CommandResetDeepSleepCounter                          = 103
    CommandRebootSensor                                   = 199
    CommandAcknowledge                                    = 200
    CommandResend                                         = 201
    CommandChecksumError                                  = 202
    CommandApplicationFirmwareNotPresent                  = 249


    # Register Address Table

    RegisterAddressSensorIDTag                       = 0
    RegisterAddressDataCollectionInterval            = 1
    RegisterAddressDeepSleepCounter                  = 4
    RegisterAddressWakeUpTimerAfterDeepSleep         = 6
    RegisterAddressOutgoingRadioMessageOperatingMode = 8
    RegisterAddressUserDescriptionField              = 32
    RegisterAddressSensorOperatingMode               = 64
    RegisterAddressErrorIndicator                    = 65
    RegisterAddressBlockingDistance                  = 66
    RegisterAddressThresholdVoltage1S                = 68
    RegisterAddressThresholdVoltage2S                = 69
    RegisterAddressThresholdVoltage3S                = 70
    RegisterAddressThresholdVoltage4S                = 71
    RegisterAddressThresholdSwitchTime2S             = 72
    RegisterAddressThresholdSwitchTime3S             = 74
    RegisterAddressThresholdSwitchTime4S             = 76
    RegisterAddressThresholdVoltage1L                = 78
    RegisterAddressThresholdVoltage2L                = 79
    RegisterAddressThresholdVoltage3L                = 80
    RegisterAddressThresholdVoltage4L                = 81
    RegisterAddressThresholdSwitchTime2L             = 82
    RegisterAddressThresholdSwitchTime3L             = 84
    RegisterAddressThresholdSwitchTime4L             = 86
    RegisterAddressAverage                           = 88
    RegisterAddressNoEchoTimeout                     = 89
    RegisterAddressGainControlShortCycle             = 90
    RegisterAddressGainControlLongCycle              = 91
    RegisterAddressGainSwitchDistance                = 92
    RegisterAddressTemperatureCompensation           = 94
    RegisterAddressManualTemperature                 = 95
    RegisterAddressUltrasonicSampleInterval          = 96
    RegisterAddressMinimumDistanceProcessing         = 100
    RegisterAddressReserved101                       = 101
    RegisterAddressReserved103                       = 103
    RegisterAddressReserved105                       = 105
    RegisterAddressReserved107                       = 107
    RegisterAddressltrasonicWaveformCycles           = 109
    RegisterAddressUltrasonicWaveformGain            = 110
    RegisterAddressReserved111                       = 111


    # A couple register Maxs and Mins this driver uses.

    DataCollectionIntervalMin    = 0
    DataCollectionIntervalMax    = 16777215
    DeepSleepCounterMin          = 0
    DeepSleepCounterMax          = 43200 * 2.04
    WakeUpTimerAfterDeepSleepMin = 6 * 2.04
    WakeUpTimerAfterDeepSleepMax = 293 * 2.04

    # poll value to push down
    DEF_DDO_PO = 5

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        ## Local State Variables:
        self.__xbee_manager = None
        self.__callback_event = None
        self.__backup_callback_event = None

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name = 'sample_rate_sec', type = int, required = False,
                default_value = 3600,
                verify_function = lambda x: \
                                  x >= self.DataCollectionIntervalMin and \
                                  x <= self.DataCollectionIntervalMax),
            Setting(
                name = 'sleep_rate_sec', type = int, required = False,
                default_value = 14400,
                verify_function = lambda x: \
                                  x >= self.DeepSleepCounterMin and \
                                  x <= self.DeepSleepCounterMax),
            Setting(
                name = 'awake_time_sec', type = int, required = False,
                default_value = 30,
                verify_function = lambda x: \
                                  x >= self.WakeUpTimerAfterDeepSleepMin and \
                                  x <= self.WakeUpTimerAfterDeepSleepMax),
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties

            ChannelSourceDeviceProperty(name="distance", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="in"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_NONE),

            ChannelSourceDeviceProperty(name="temperature", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="C"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_NONE),

            ChannelSourceDeviceProperty(name="target_strength", type=int,
                initial=Sample(timestamp=0, value=0, unit="%"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_NONE),

            ChannelSourceDeviceProperty(name="strength", type=str,
                initial=Sample(timestamp=0, value="?"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_NONE),

            ChannelSourceDeviceProperty(name="battery", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="V"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_NONE),

            ChannelSourceDeviceProperty(name="gain", type=str,
                initial=Sample(timestamp=0, value="?"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_NONE),

            ChannelSourceDeviceProperty(name="event", type=int,
                initial=Sample(timestamp=0, value=0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_NONE),

            ChannelSourceDeviceProperty(name="serial_number", type=str,
                initial=Sample(timestamp=0, value="?"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_NONE),

            ChannelSourceDeviceProperty(name="sensor_model", type=str,
                initial=Sample(timestamp=0, value="?"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_NONE),

            ChannelSourceDeviceProperty(name="FWa_version", type=str,
                initial=Sample(timestamp=0, value="?"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_NONE),

            ChannelSourceDeviceProperty(name="FWb_version", type=str,
                initial=Sample(timestamp=0, value="?"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_NONE),


        ]

        self.last_event = 0
        self.last_event_time = 0
        self.model = self.MODEL_M3_150
        self.about_me = None

        self.WaitForResponse = None
        self.WaitForResponseData1 = None
        self.WaitForResponse2 = None

        self.state = self.M3_STATE_SENSORINFO

        ## Initialize the DeviceBase interface:
        XBeeBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)


    ## Functions which must be implemented to conform to the XBeeBase
    ## interface:

    @staticmethod
    def probe():
        """\
            Collect important information about the driver.

            .. Note::

                * This method is a static method.  As such, all data returned
                  must be accessible from the class without having a instance
                  of the device created.

            Returns a dictionary that must contain the following 2 keys:
                    1) address_table:
                       A list of XBee address tuples with the first part of the
                       address removed that this device might send data to.
                       For example: [ 0xe8, 0xc105, 0x95 ]
                    2) supported_products:
                       A list of product values that this driver supports.
                       Generally, this will consist of Product Types that
                       can be found in 'devices/xbee/common/prodid.py'
        """
        probe_data = XBeeBase.probe()

        for address in MassaM3.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in MassaM3.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

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
            # there were problems with settings, terminate early:
            self.__tracer.error("Settings rejected/not found: %s %s", \
                rejected, not_found)
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)


    def start(self):
        """Start the device driver.  Returns bool."""

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self, "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        # Get the extended address of the device:
        extended_address = SettingsBase.get_setting(self, "extended_address")

        # Retrieve the flag which tells us if we should sleep:

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec.cb_set(self.message_indication)
        xbdm_rx_event_spec.match_spec_set(
            (extended_address, 0xe8, 0xc105, 0x11),
            (True, True, True, True))
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                xbdm_rx_event_spec)

        # Create a callback specification that calls back this driver when
        # our device has left the configuring state and has transitioned
        # to the running state:
        xbdm_running_event_spec = XBeeDeviceManagerRunningEventSpec()
        xbdm_running_event_spec.cb_set(self.running_indication)
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                                xbdm_running_event_spec)

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)

        # Get the gateway's extended address:
        gw_xbee_sh, gw_xbee_sl = gw_extended_address_tuple()

        # Set the destination for I/O samples to be the gateway:
        xbee_ddo_cfg.add_parameter('DH', gw_xbee_sh)
        xbee_ddo_cfg.add_parameter('DL', gw_xbee_sl)

        # After much investigation, it has been determined that setting PO=4
        # really helps speed things up after a Gateway reboot when many
        # Massa M3 sensors are out there sleeping on us.
        xbee_ddo_cfg.add_parameter('PO', self.DEF_DDO_PO)

        # Register configuration blocks with the XBee Device Manager:
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Define a Network Sleep block.
        # This block will NOT send any sleep parameters to the device,
        # but instead, will provide a hint to the DIA about how long
        # we expect our device to sleep for.
        # This is required for long sleeping nodes, as the coordinator
        # and all routers on the network need to know these values.

        xbee_sleep_cfg = XBeeConfigNetworkSleep(extended_address)

        sleep_rate = SettingsBase.get_setting(self, "sleep_rate_sec")
        sleep_rate *= 1000
        if sleep_rate != 0:
            xbee_sleep_cfg.sleep_cycle_set(1, sleep_rate)
        else:
            xbee_sleep_cfg.sleep_mode_set(SM_DISABLED)
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_sleep_cfg)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)
        return True

    def stop(self):
        '''Stop the device driver.  Returns bool.'''
        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)
        return True

    def __schedule_state_machine_callback(self, retry_time):
        '''
       The M3 driver state machine scheduler.

       During the state machine part of the M3 driver, this function
       will be called to ensure that if an XBee packet is lost or corrupt,
       that the state machine will continue to run, and our commands will
       continue to be sent out on the network.

       After the state machine completes, and the device is in a RUNNING state,
       this function will no longer be called.
        '''
        self.__tracer.debug('scheduling a state machine callback of %d '
                            'seconds and a backup callback of %d seconds.',
                            retry_time, retry_time * 1.5)

        # Go cancel any regular callback that still might be scheduled
        # but not run yet.
        try:
            if self.__callback_event:
                self.__xbee_manager.xbee_device_schedule_cancel(
                    self.__callback_event)
        except:
            pass

        # Go cancel any backup callback that still might be scheduled
        # but not run yet.
        try:
            if self.__backup_callback_event:
                self.__xbee_manager.xbee_device_schedule_cancel(
                    self.__backup_callback_event)
        except:
            pass

        # Schedule our regular callback.
        self.__callback_event = \
            self.__xbee_manager.xbee_device_schedule_after(
                retry_time, self.__run_config_state_machine)

        # Schedule our backup callback.
        self.__backup_callback_event = \
            self.__xbee_manager.xbee_device_schedule_after(
                retry_time * 1.5, self.__run_config_state_machine)

    def __run_config_state_machine(self):
        '''
        The M3 Configuration state machine function.

        After the unit has had its XBee DDO values saved to it, this
        function will be called, and will continue to be called until
        the device gets to a known state.

        The state machine will determine what type of device it is,
        send default values to the device, and also apply the
        user-specified values of sample rate, sleep rate and awake time.

        Once the state machine has finished, the device will be moved
        to a RUNNING state, which will allow the M3 to continue on all
        by itself for the rest of the DIA run.
        '''
        if self.state == self.M3_STATE_SENSORINFO:
            self.DoCommandRequestForMiscSensorInformation()
        elif self.state == self.M3_STATE_SETSLEEP0:
            self.SetSleepInterval(0)
        elif self.state == self.M3_STATE_SETINTERVAL:
            interval = SettingsBase.get_setting(self, "sample_rate_sec")
            self.SetDataCollectionInterval(interval)
        elif self.state == self.M3_STATE_CLEARHISTORY:
            ret = self.DoCommandClearDataHistoryBuffer()
        elif self.state == self.M3_STATE_REBOOT:
            ret = self.DoCommandRebootSensor()
        elif self.state == self.M3_STATE_GETHISTORY:
            self.DoCommandReadEventDataFromTheHistoryBuffer(1)
        elif self.state == self.M3_STATE_SETSENDAFTERWAKEUP:
            self.SetSendSampleAfterWakeup(2)
        elif self.state == self.M3_STATE_SETSENDAWAKETIME:
            awake_time_sec = SettingsBase.get_setting(self, "awake_time_sec")
            self.SetAwakeTime(awake_time_sec)
        elif self.state == self.M3_STATE_SETSLEEP:
            sleep_rate_sec = SettingsBase.get_setting(self, "sleep_rate_sec")
            self.SetSleepInterval(sleep_rate_sec)
        elif self.state == self.M3_STATE_RUNNING:
            return

        # Now set up a timeout callback under the XBee Manager to
        # call our driver back after a period of time.
        #
        # This callback is used as a backup to "kick" the state machine
        # to continue on, in case the unit did not respond to our request
        # or for some reason the XBee packet to or from our Device got lost
        # out on the XBee network.
        self.__schedule_state_machine_callback(20)

    def running_indication(self):
        '''
        DIA will call this function when it has finished sending the
        preliminary DDO command blocks to the M3 device.
        At this point, the M3 is correctly configured at the XBee level,
        to be able to accept data from us.
        Now we should start our state machine to bring the device "up"
        in terms of the Massa M3 Protocol.
        '''
        self.__run_config_state_machine()

    def message_indication(self, buf, addr):
        '''
        DIA will call this function whenever it has received data on the
        XBee network that was destined for this device.
        '''
        self.__tracer.debug("message indication.")

        # Rewrite data into an array of ordinals, and tally up the sum
        # of bytes.
        data = []
        sum = 0
        length = len(buf)
        for n in range(0, length):
            byte = ord(buf[n])
            data.append(byte)
            sum += byte

        # Subtract off the last byte, as that is the checksum...
        sum -= data[length - 1]

        # Checksum: This is the sum of all bytes (not including MAC
        # address) modulo 256

        # If the checksum doesn't match, toss the data away, and tell
        # ourselves to resend the request.
        if sum % 256 != data[length - 1]:
            self.__tracer.error("Bad checksum on inbound data...")
            self.__run_config_state_machine()
            return

        self.__tracer.debug("data: %s", str(data))

        # All responses should be at LEAST 4 bytes.
        if len(data) < 4:
            self.__tracer.error("Bad amount of data in received data...")
            self.__run_config_state_machine()
            return

        # Since the checksum check above has ensured we have received valid
        # M3 protocol data, lets take a look at the 4th byte, which tells
        # us what kind of data response it is.

        command = data[3]

        if command == self.CommandReadEventDataFromTheHistoryBuffer:
            if self.WaitForResponse == self.CommandReadEventDataFromTheHistoryBuffer:
                results = []
                results = self.ParseCommandReadEventDataFromTheHistoryBuffer(data, self.WaitForResponseData1)
                self.__update_channels(results)
                results = []
                self.WaitForResponse = None
                if self.state == self.M3_STATE_GETHISTORY:
                    self.state = self.M3_STATE_SETSENDAFTERWAKEUP
                    self.__run_config_state_machine()
            elif self.state == self.M3_STATE_RUNNING:
                self.__tracer.debug("Unsolicited Data - State Running - Update Channels")
                results = []
                results = self.ParseCommandReadEventDataFromTheHistoryBuffer(data, 8)
                self.__update_channels(results)
                results = []

        elif command == self.CommandAcquireNewEventDataNoRecordToDataHistoryBuffer:
            if self.WaitForResponse == self.CommandAcquireNewEventDataNoRecordToDataHistoryBuffer:
                results = []
                results = self.ParseCommandReadEventDataFromTheHistoryBuffer(data, 1)
                self.__update_channels(results)
                results = []
                self.WaitForResponse = None

        elif command == self.CommandAcquireNewEventDataRecordToDataHistoryBuffer:
            if self.WaitForResponse == self.CommandAcquireNewEventDataRecordToDataHistoryBuffer:
                results = []
                results = self.ParseCommandReadEventDataFromTheHistoryBuffer(data, 1)
                self.__update_channels(results)
                results = []
                self.WaitForResponse = None

        elif command == self.CommandAcquireUltrasonicWaveform:
            pass

        elif command == self.CommandBlockWriteToConfigurationRegisters:
            pass

        elif command == self.CommandBlockReadFromConfigurationRegisters:
            pass

        elif command == self.CommandRequestForMiscSensorInformation:
            if self.WaitForResponse == self.CommandRequestForMiscSensorInformation:
                version = 0
                ret = self.ParseCommandRequestForMiscSensorInformation(data)
                if ret != None:
                    self.about_me = ret
                    try:
                        version = int(self.about_me['FWa_version'])
                    except:
                        version = 0
                self.WaitForResponse = None
                if self.state == self.M3_STATE_SENSORINFO:
                    # Set the sleep rate to 0 for now.
                    # This will allow us to move through the rest of our initial
                    # state machine with leisure, knowing we won't have to worry
                    # that the M3 will go back to sleep on us.
                    self.state = self.M3_STATE_SETSLEEP0
                    self.__run_config_state_machine()

        elif command == self.CommandClearDataHistoryBuffer:
            pass

        elif command == self.CommandResetEventCounter:
            pass

        elif command == self.CommandResetDeepSleepCounter:
            pass

        elif command == self.CommandRebootSensor:
            pass

        elif command == self.CommandAcknowledge:
            if self.WaitForResponse == self.CommandAcknowledge:
                self.ParseCommandAcknowledge(data, self.WaitForResponseData1)
            elif self.WaitForResponse == self.CommandBlockWriteToConfigurationRegisters:
                self.ParseCommandBlockWriteToConfigurationRegisters(data)
                self.WaitForResponse = None
                if self.state == self.M3_STATE_SETSLEEP0:
                    self.state = self.M3_STATE_SETINTERVAL
                    self.__run_config_state_machine()
                elif self.state == self.M3_STATE_SETINTERVAL:
                    self.state = self.M3_STATE_CLEARHISTORY
                    self.__run_config_state_machine()
                elif self.state == self.M3_STATE_SETSENDAFTERWAKEUP:
                    self.state = self.M3_STATE_SETSENDAWAKETIME
                    self.__run_config_state_machine()
                elif self.state == self.M3_STATE_SETSENDAWAKETIME:
                    self.state = self.M3_STATE_SETSLEEP
                    self.__run_config_state_machine()
                elif self.state == self.M3_STATE_SETSLEEP:
                    self.state = self.M3_STATE_RUNNING
                    self.__tracer.info("Device has completed its config state machine" +
                                       " and is now up and fully running!")
            elif self.WaitForResponse == self.CommandClearDataHistoryBuffer:
                self.ParseCommandClearDataHistoryBuffer(data)
            elif self.WaitForResponse == self.CommandRebootSensor:
                self.ParseCommandRebootSensor(data)

        elif command == self.CommandResend:
            pass

        elif command == self.CommandChecksumError:
            pass

        elif command == self.CommandApplicationFirmwareNotPresent:
            pass


    def __update_channels(self, results):
        if isinstance(results, list):
            for result in results:
                self.property_set("distance", Sample(result['timestamp'], round(result['distance'], 6), "in"))
                self.property_set("temperature", Sample(result['timestamp'], round(result['temperature'], 6), "C"))
                self.property_set("target_strength", Sample(result['timestamp'], result['target_strength'], "%"))
                self.property_set("strength", Sample(result['timestamp'], result['strength'], ""))
                self.property_set("battery", Sample(result['timestamp'], round(result['battery'], 6), "V"))
                self.property_set("gain", Sample(result['timestamp'], result['gain'], ""))
                self.property_set("event", Sample(result['timestamp'], result['event'], ""))
                self.property_set("serial_number", Sample(result['timestamp'], result['serial_number'], ""))
                self.property_set("sensor_model", Sample(result['timestamp'], result['sensor_model'], ""))
                self.property_set("FWa_version", Sample(result['timestamp'], result['FWa_version'], ""))
                self.property_set("FWb_version", Sample(result['timestamp'], result['FWb_version'], ""))


    def __decode_history_data(self, data):

        # Ensure we get exactly 8 bytes passed in.
        if len(data) != 8:
            return None

        # Break out each byte of data.
        event1  = data[0]
        event2  = data[1]
        status1 = data[2]
        status2 = data[3]
        range1  = data[4]
        range2  = data[5]
        temp    = data[6]
        volt    = data[7]

        # self.__tracer.debug(' parse:%s', str(data))

        # When the history buffer is reset, it sets the Range msb for all
        # entries to 255, which means the entry is invalid.
        if range2 == 255:
            return None

        event1 += (event2 << 8)

        parse = status1 & 3
        if parse == 3:
            target_strength = 100
        elif parse == 2:
            target_strength = 75
        elif parse == 1:
            target_strength = 50
        else:
            target_strength = 0

        status1 = status1 >> 2
        parse = status1 & 3
        if parse == 3:
            strength = "Very Strong"
        elif parse == 2:
            strength = "Strong"
        elif parse == 1:
            strength = "Moderate"
        else:
            strength = "Weak"

        status1 = status1 >> 2
        parse = status1 & 1
        if parse == 1:
            gain = "Hi"
        else:
            gain = "Low"

        status1 = status1 >> 3
        if status1 == 1:
            error = True
        else:
            error = False

        if self.model == self.MODEL_M3_150 or \
           self.model == self.MODEL_M3_150IS or \
           self.model == self.MODEL_M3_95 or \
           self.model == self.MODEL_M3_95IS:
            range1 = ((range1 + (range2 << 8)) / 128.0)
        elif self.model == self.MODEL_M3_50 or \
             self.model == self.MODEL_M3_50IS:
            range1 = ((range1 + (range2 << 8)) / 64.0)
        else:
            range1 = ((range1 + (range2 << 8)) / 128.0)

        temp = 0.587085 * float(temp) - 50.0

        volt = (float(volt) - 14.0) / 40.0

        item = { 'event': event1, 'target_strength': target_strength, 'strength': strength, 'gain': gain, 'error': error, 'distance': range1, 'temperature': temp, 'battery': volt, 'timestamp': 0, 'address': SettingsBase.get_setting(self, "extended_address")}
        # Tack on the Unit's "about me"information.
        item.update(self.about_me)
#    self.__tracer.info(item)

        return item


    def DoCommandAcquireNewEventDataNoRecordToDataHistoryBuffer(self):
        # <Destination ID> <Sender ID> <Message Length> <Command> <Checksum>

        self.__tracer.debug("DoCommandAcquireNewEventDataNoRecordToDataHistoryBuffer -> START!")

        dest = self.GlobalDestinationID
        sender = self.GlobalSenderID
        length = 5
        command = self.CommandAcquireNewEventDataNoRecordToDataHistoryBuffer

        raw_data = struct.pack("BBBB", dest, sender, length, command)
        checksum = dest + sender + length + command
        checksum %= 256
        raw_data += struct.pack("B", checksum)

        extended_address = SettingsBase.get_setting(self, "extended_address")
        addr = (extended_address, 0xe8, 0xc105, 0x11)

        try:
            self.__xbee_manager.xbee_device_xmit(0xe8, raw_data, addr)
            self.WaitForResponse = self.CommandAcquireNewEventDataNoRecordToDataHistoryBuffer
            self.__tracer.debug("DoCommandAcquireNewEventDataNoRecordToDataHistoryBuffer -> REQUEST SENT!")
        except:
            # try again later:
            self.__tracer.warning("xmission failure, will retry.")
            self.__schedule_request()
            self.__reschedule_retry_watchdog()
            self.__tracer.debug("DoCommandAcquireNewEventDataNoRecordToDataHistoryBuffer -> FAIL!")


    def DoCommandAcquireNewEventDataRecordToDataHistoryBuffer(self):
        # <Destination ID> <Sender ID> <Message Length> <Command> <Checksum>

        self.__tracer.debug("DoCommandAcquireNewEventDataRecordToDataHistoryBuffer -> START!")

        dest = self.GlobalDestinationID
        sender = self.GlobalSenderID
        length = 5
        command = self.CommandAcquireNewEventDataRecordToDataHistoryBuffer

        raw_data = struct.pack("BBBB", dest, sender, length, command)
        checksum = dest + sender + length + command
        checksum %= 256
        raw_data += struct.pack("B", checksum)

        extended_address = SettingsBase.get_setting(self, "extended_address")
        addr = (extended_address, 0xe8, 0xc105, 0x11)

        try:
            self.__xbee_manager.xbee_device_xmit(0xe8, raw_data, addr)
            self.WaitForResponse = self.CommandAcquireNewEventDataRecordToDataHistoryBuffer
            self.__tracer.debug("DoCommandAcquireNewEventDataRecordToDataHistoryBuffer -> REQUEST SENT!")
        except:
            # try again later:
            self.__tracer.warning("xmission failure, will retry.")
            self.__schedule_request()
            self.__reschedule_retry_watchdog()
            self.__tracer.debug("DoCommandAcquireNewEventDataRecordToDataHistoryBuffer -> FAIL!")


    def DoCommandReadEventDataFromTheHistoryBuffer(self, amount):
        # <Destination ID> <Sender ID> <Message Length> <Command> <Addr Ptr> <EventsToRetrieve> <Checksum>

        self.__tracer.debug("DoCommandReadEventDataFromTheHistoryBuffer -> START!")

        dest = self.GlobalDestinationID
        sender = self.GlobalSenderID
        length = 7
        command = self.CommandReadEventDataFromTheHistoryBuffer
        addrptr = 1
        events = amount

        raw_data = struct.pack("BBBBBB", dest, sender, length, command, addrptr, events)
        checksum = dest + sender + length + command + addrptr + events
        checksum %= 256
        raw_data += struct.pack("B", checksum)

        extended_address = SettingsBase.get_setting(self, "extended_address")
        addr = (extended_address, 0xe8, 0xc105, 0x11)

        try:
            self.__xbee_manager.xbee_device_xmit(0xe8, raw_data, addr)
            self.WaitForResponse = self.CommandReadEventDataFromTheHistoryBuffer
            self.WaitForResponseData1 = events
            self.__tracer.debug("DoCommandReadEventDataFromTheHistoryBuffer -> REQUEST SENT!")
        except:
            # try again later:
            self.__tracer.warning("xmission failure, will retry.")
            self.__schedule_request()
            self.__reschedule_retry_watchdog()
            self.__tracer.debug("DoCommandReadEventDataFromTheHistoryBuffer -> FAIL!")


    def ParseCommandReadEventDataFromTheHistoryBuffer(self, data, amount):

        if data[0] == self.GlobalSenderID and data[1] == self.GlobalDestinationID and \
           data[3] == self.CommandReadEventDataFromTheHistoryBuffer:
            self.__tracer.debug("DoCommandReadEventDataFromTheHistoryBuffer -> PASS -> PART 1!")

            total = data[2]
            total -= 7
            total /= 8
            amount = total

            if len(data) != 6 + 8 * amount + 1:
                return None

            ret = []
            for j in range(0, amount):
                data2 = data[6 + 8 * j : 6 + 8 * (j + 1)]

                data2 = self.__decode_history_data(data2)

                # This can happen if the decode function finds a 255 in the
                # event msb.  This means the entry is invalid.
                if data2 == None:
                    continue

                self.__tracer.debug("Last Event: %d Event reported: %d", self.last_event, data2['event'])

                # Only report back new events.
                if data2['event'] > self.last_event:
                    self.last_event = data2['event']
                    interval = SettingsBase.get_setting(self, "sample_rate_sec")
                    self.last_event_time += interval
                    data2['timestamp'] = self.last_event_time
                    # self.last_event_time = digitime.time()
                    self.__tracer.debug("APPENDING!!!")
                    ret.append(data2)
                elif data2['event'] + 8 < self.last_event:
                    self.last_event = data2['event']
                    interval = SettingsBase.get_setting(self, "sample_rate_sec")
                    self.last_event_time += interval
                    data2['timestamp'] = self.last_event_time
                    # self.last_event_time = digitime.time()
                    self.__tracer.warning("AUTO-RECOVER FROM BAD EVENT! APPENDING!!!")
                    ret.append(data2)
                else:
                    self.__tracer.debug("Tossing %d. Duplicate.", data2['event'])


            # Okay, now that we have a list of values to return,
            # we need to try to create a timestamp for each value.
            tnow = digitime.time()

            for event in reversed(ret):
                interval = SettingsBase.get_setting(self, "sample_rate_sec")
                t = tnow - ((self.last_event - event['event']) * interval)
                event['timestamp'] = t

                self.__tracer.info("Event %d, level %0.1f inch, timestamp of %d", \
                     event['event'], event['distance'], t)

            self.__tracer.debug(str(ret))
            return ret

    # Collection Information about the Sensor Unit.
    def DoCommandRequestForMiscSensorInformation(self):
        # <Destination ID> <Sender ID> <Message Length> <Command> <Checksum>

        self.__tracer.debug("DoCommandRequestForMiscSensorInformation -> START!")

        dest = self.GlobalDestinationID
        sender = self.GlobalSenderID
        length = 5
        command = self.CommandRequestForMiscSensorInformation

        raw_data = struct.pack("BBBB", dest, sender, length, command)
        checksum = dest + sender + length + command
        checksum %= 256
        raw_data += struct.pack("B", checksum)

        extended_address = SettingsBase.get_setting(self, "extended_address")
        addr = (extended_address, 0xe8, 0xc105, 0x11)

        try:
            self.__xbee_manager.xbee_device_xmit(0xe8, raw_data, addr)
            self.WaitForResponse = self.CommandRequestForMiscSensorInformation
            self.__tracer.debug("DoCommandRequestForMiscSensorInformation -> REQUEST SENT!")
        except:
            # try again later:
            self.__tracer.warning("xmission failure, will retry.")
            self.__schedule_request()
            self.__reschedule_retry_watchdog()
            self.__tracer.debug("DoCommandRequestForMiscSensorInformation -> FAIL!")


    def ParseCommandRequestForMiscSensorInformation(self, data):
        # <Destination ID> <Sender ID> <Message Length> <Command> <SensorModel> <LSB> <MSB> <LSB> <MSB> <LSB> . . . <MSB> <Checksum>

        if data[0] == self.GlobalSenderID and data[1] == self.GlobalDestinationID and \
           data[2] == 14 and data[3] == self.CommandRequestForMiscSensorInformation:

            if data[4] == self.MODEL_M3_150:
                self.model = self.MODEL_M3_150
                model = "M3-150"
            elif data[4] == self.MODEL_M3_95:
                self.model = self.MODEL_M3_95
                model = "M3-95"
            elif data[4] == self.MODEL_M3_150IS:
                self.model = self.MODEL_M3_150IS
                model = "M3-150is"
            elif data[4] == self.MODEL_M3_95IS:
                self.model = self.MODEL_M3_95IS
                model = "M3-95is"
            elif data[4] == self.MODEL_M3_50:
                self.model = self.MODEL_M3_50
                model = "M3-50"
            else:
                self.model = self.MODEL_M3_150
                model = "<UNKNOWN>"

            FWa = str(data[6]) + str(data[5])
            FWb = str(data[8]) + str(data[7])
            Ser = str(data[12]) + str(data[11]) + str(data[10]) + str(data[9])

            item = { 'sensor_model': model, 'FWa_version': FWa, 'FWb_version': FWb, 'serial_number': Ser }
            if self.__tracer.debug():
                self.__tracer.debug("DoCommandRequestForMiscSensorInformation -> PASS!")
                self.__tracer.debug(str(item))
            return item

        self.__tracer.debug("DoCommandRequestForMiscSensorInformation -> FAIL!")
        return None


    def DoCommandBlockWriteToConfigurationRegisters(self, register, data_to_write):
        # <Destination ID><Sender ID><Message Length><Command><AddrLSB> <AddrMSB><RegQty><Data> . . . <DataN><Checksum>

        self.__tracer.debug("DoCommandBlockWriteToConfigurationRegisters -> START!")

        dest = self.GlobalDestinationID
        sender = self.GlobalSenderID
        length = 8
        command = self.CommandBlockWriteToConfigurationRegisters
        lsb = register
        msb = 0
        amount = len(data_to_write)
        length = 8 + amount

        raw_data = struct.pack("BBBBBBB", dest, sender, length, command, lsb, msb, amount)
        for j in range(0, len(data_to_write)):
            raw_data += struct.pack("B", data_to_write[j])

        checksum = dest + sender + length + command + lsb + msb + amount
        for j in range(0, len(data_to_write)):
            checksum += int(data_to_write[j])

        checksum %= 256
        raw_data += struct.pack("B", checksum)

        extended_address = SettingsBase.get_setting(self, "extended_address")
        addr = (extended_address, 0xe8, 0xc105, 0x11)

        try:
            self.__xbee_manager.xbee_device_xmit(0xe8, raw_data, addr)
            self.WaitForResponse = self.CommandBlockWriteToConfigurationRegisters
            self.__tracer.debug("DoCommandBlockWriteToConfigurationRegisters -> REQUEST SENT!")
        except:
            # try again later:
            self.__tracer.warning("xmission failure, will retry.")
            self.__schedule_request()
            self.__reschedule_retry_watchdog()
            self.__tracer.debug("DoCommandBlockWriteToConfigurationRegisters -> FAIL!")


    def ParseCommandBlockWriteToConfigurationRegisters(self, data):
        # <Destination ID> <Sender ID> <Message Length> <Command> <AcknowledgeToCommand> <Checksum>

        # Check to see if the command returned an error (data[5] == 1),
        # if so, we need to set the EI Register to 0, and then try it
        # all over again.
        if data[0] == self.GlobalSenderID and data[1] == self.GlobalDestinationID and \
           data[2] == 7 and data[3] == self.CommandAcknowledge and \
           data[4] == self.CommandBlockWriteToConfigurationRegisters and data[5] == 1:
            self.__tracer.debug("DoCommandBlockWriteToConfigurationRegisters -> CLEARING!")
            data = []
            data.append(0)

            self.DoCommandBlockWriteToConfigurationRegisters(self.RegisterAddressErrorIndicator, data)
            return False

        # If everything comes back okay, return True
        if data[0] == self.GlobalSenderID and data[1] == self.GlobalDestinationID and \
           data[2] == 7 and data[3] == self.CommandAcknowledge and \
           data[4] == self.CommandBlockWriteToConfigurationRegisters and data[5] == 0:
            self.__tracer.debug("DoCommandBlockWriteToConfigurationRegisters -> PASS!")
            return True

        self.__tracer.debug("DoCommandBlockWriteToConfigurationRegisters -> FAIL!")
        return False


    def DoCommandClearDataHistoryBuffer(self):
        # <Destination ID> <Sender ID> <Message Length> <Command> <Checksum>

        self.__tracer.debug("DoCommandClearDataHistoryBuffer -> START!")

        dest = self.GlobalDestinationID
        sender = self.GlobalSenderID
        length = 5
        command = self.CommandClearDataHistoryBuffer

        raw_data = struct.pack("BBBB", dest, sender, length, command)
        checksum = dest + sender + length + command
        checksum %= 256
        raw_data += struct.pack("B", checksum)

        extended_address = SettingsBase.get_setting(self, "extended_address")
        addr = (extended_address, 0xe8, 0xc105, 0x11)

        try:
            self.__xbee_manager.xbee_device_xmit(0xe8, raw_data, addr)
            self.WaitForResponse = self.CommandClearDataHistoryBuffer
            self.__tracer.debug("DoCommandClearDataHistoryBuffer -> REQUEST SENT!")
        except:
            # try again later:
            self.__tracer.warning("xmission failure, will retry.")
            self.__schedule_request()
            self.__reschedule_retry_watchdog()
            self.__tracer.debug("DoCommandClearDataHistoryBuffer -> FAIL!")


    def ParseCommandClearDataHistoryBuffer(self, data):
        # <Destination ID> <Sender ID> <Message Length> <Command> <AcknowledgeToCommand> <Checksum>

        if data[0] == self.GlobalSenderID and data[1] == self.GlobalDestinationID and \
           data[2] == 6 and data[3] == self.CommandAcknowledge and \
           data[4] == self.CommandClearDataHistoryBuffer:
            self.__tracer.debug("DoCommandClearDataHistoryBuffer -> PASS -> PART 1!")

            dest = self.GlobalDestinationID
            sender = self.GlobalSenderID
            length = 6
            command = self.CommandAcknowledge
            command2 = 71
            raw_data = struct.pack("BBBBB", dest, sender, length, command, command2)
            checksum = dest + sender + length + command + command2
            checksum %= 256
            raw_data += struct.pack("B", checksum)

            extended_address = SettingsBase.get_setting(self, "extended_address")
            addr = (extended_address, 0xe8, 0xc105, 0x11)

            try:
                self.__xbee_manager.xbee_device_xmit(0xe8, raw_data, addr)
                self.WaitForResponse = self.CommandAcknowledge
                self.WaitForResponseData1 = self.CommandClearDataHistoryBuffer
                self.__tracer.debug("DoCommandClearDataHistoryBuffer -> PART 2 -> REQUEST SENT!")
            except:
                # try again later:
                self.__tracer.warning("xmission failure, will retry.")
                self.__schedule_request()
                self.__reschedule_retry_watchdog()
                self.__tracer.debug("DoCommandClearDataHistoryBuffer -> PART 2 -> FAIL!")


    def DoCommandRebootSensor(self):
        # <Destination ID> <Sender ID> <Message Length> <Command> <Checksum>

        self.__tracer.debug("DoCommandRebootSensor -> START!")
        dest = self.GlobalDestinationID
        sender = self.GlobalSenderID
        length = 5
        command = self.CommandRebootSensor

        raw_data = struct.pack("BBBB", dest, sender, length, command)
        checksum = dest + sender + length + command
        checksum %= 256
        raw_data += struct.pack("B", checksum)

        extended_address = SettingsBase.get_setting(self, "extended_address")
        addr = (extended_address, 0xe8, 0xc105, 0x11)

        try:
            self.__xbee_manager.xbee_device_xmit(0xe8, raw_data, addr)
            self.WaitForResponse = self.CommandRebootSensor
            self.__tracer.debug("DoCommandRebootSensor -> REQUEST SENT!")
        except:
            # try again later:
            self.__tracer.warning("xmission failure, will retry.")
            self.__schedule_request()
            self.__reschedule_retry_watchdog()
            self.__tracer.debug("DoCommandRebootSensor -> FAIL!")


    def ParseCommandRebootSensor(self, data):
        # <Destination ID> <Sender ID> <Message Length> <Command> <AcknowledgeToCommand> <Checksum>

        if data[0] == self.GlobalSenderID and data[1] == self.GlobalDestinationID and \
           data[2] == 6 and data[3] == self.CommandAcknowledge and \
           data[4] == self.CommandRebootSensor:
            self.__tracer.debug("DoCommandRebootSensor -> PASS PART 1!")

            dest = self.GlobalDestinationID
            sender = self.GlobalSenderID
            length = 6
            command = self.CommandAcknowledge
            command2 = 71
            raw_data = struct.pack("BBBBB", dest, sender, length, command, command2)
            checksum = dest + sender + length + command + command2
            checksum %= 256
            raw_data += struct.pack("B", checksum)

            extended_address = SettingsBase.get_setting(self, "extended_address")
            addr = (extended_address, 0xe8, 0xc105, 0x11)

            try:
                self.__xbee_manager.xbee_device_xmit(0xe8, raw_data, addr)
                self.WaitForResponse = self.CommandAcknowledge
                self.WaitForResponseData1 = self.CommandRebootSensor
                self.__tracer.debug("DoCommandRebootSensor -> PART 2 -> REQUEST SENT!")
            except:
                # try again later:
                self.__tracer.warning("xmission failure, will retry.")
                self.__schedule_request()
                self.__reschedule_retry_watchdog()
                self.__tracer.debug("DoCommandRebootSensor -> PART 2 -> FAIL!")


    def ParseCommandAcknowledge(self, data, ack_command):
        # <Destination ID> <Sender ID> <Message Length> <Command> <AcknowledgeToCommand> <Checksum>

        if ack_command == self.CommandClearDataHistoryBuffer:

            if data[0] == self.GlobalSenderID and data[1] == self.GlobalDestinationID and \
               data[2] == 6 and data[3] == self.CommandAcknowledge and \
               data[4] == self.CommandClearDataHistoryBuffer:
                self.WaitForResponse = None
                if self.state == self.M3_STATE_CLEARHISTORY:
                    self.state = self.M3_STATE_REBOOT
                    self.__run_config_state_machine()

        if ack_command == self.CommandRebootSensor:

            if data[0] == self.GlobalSenderID and data[1] == self.GlobalDestinationID and \
               data[2] == 6 and data[3] == self.CommandAcknowledge and \
               data[4] == self.CommandRebootSensor:
                self.WaitForResponse = None
                if self.state == self.M3_STATE_REBOOT:
                    self.state = self.M3_STATE_GETHISTORY
                    self.__run_config_state_machine()


    def SetDataCollectionInterval(self, seconds):

        # Register Name:       Data Collection Interval
        # Register Address:    1-3
        # Register Limits:     0 - 16777215
        # NOTE:                default = 3600 (once an hour), resolution 1 sec/bit

        self.__tracer.info("Setting Data Collection of %d seconds", seconds)

        data = []
        data.append(seconds & 0xff)
        data.append((seconds >> 8) & 0xff)
        data.append((seconds >> 16) & 0xff)
        self.DoCommandBlockWriteToConfigurationRegisters(self.RegisterAddressDataCollectionInterval, data)


    def SetAwakeTime(self, seconds):

        # Register Name:       Awake Timer
        # Register Address:    6-7
        # Register Limits:     6-293
        # NOTE:                default = 12 (24 seconds)

        units = seconds / 2
        units = int(units)
        if units > 293:
            units = 293

        self.__tracer.info("Setting Awake Timer of %d units (%d seconds)", units, seconds)

        data = []
        data.append(units & 0xff)
        data.append((units >> 8) & 0xff)
        self.DoCommandBlockWriteToConfigurationRegisters(self.RegisterAddressWakeUpTimerAfterDeepSleep, data)


    def SetSendSampleAfterWakeup(self, value):

        # Register Name:       Operation after waking up from Deep-Sleep
        # Register Address:    8
        # Register Limits:     0-5
        # NOTE:                default = 0 (disabled)

        self.__tracer.info("Setting Send Sample After Wakeup of %d", value)

        data = []
        data.append(value & 0xff)
        self.DoCommandBlockWriteToConfigurationRegisters(self.RegisterAddressOutgoingRadioMessageOperatingMode, data)


    def SetSleepInterval(self, seconds):

        # Register Name:       Deep-Sleep Counter
        # Register Address:    4-5
        # Register Limits:     0-43200
        # NOTE:                default = 0 (counter disabled), 2.048 second units

        units = seconds / 2.048
        units = int(units)
        if units > 43200:
            units = 43200

        self.__tracer.info("Setting Sleep of %d units (%d seconds)", units, seconds)

        data = []
        data.append(units & 0xff)
        data.append((units >> 8) & 0xff)
        self.DoCommandBlockWriteToConfigurationRegisters(self.RegisterAddressDeepSleepCounter, data)



# internal functions & classes
