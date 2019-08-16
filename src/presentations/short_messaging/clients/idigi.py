############################################################################
#                                                                          #
# Copyright (c)2010 Digi International (Digi). All Rights Reserved.        #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its	   #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,	and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. Contact Product Management, Digi International, Inc., 11001 Bren   #
# Road East, Minnetonka, MN, +1 952-912-3444, for commercial licensing	   #
# opportunities for non-Digi products.                                     #
#                                                                          #
# DIGI SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED   #
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A          #
# PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, #
# PROVIDED HEREUNDER IS PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND. #
# DIGI HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES,         #
# ENHANCEMENTS, OR MODIFICATIONS.                                          #
#                                                                          #
# IN NO EVENT SHALL DIGI BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,	   #
# SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS,   #
# ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF   #
# DIGI HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.                #
#                                                                          #
############################################################################

"""
Short Messaging Client
"""

# imports
import types
import struct
import digitime
import binascii

from common.digi_device_info import get_device_id
from common.dia_version import DIA_VERSION
from common.types.boolean import Boolean
from channels.channel import PERM_GET, PERM_SET, PERM_REFRESH
from samples.sample import Sample
from core.tracing import get_tracer

from devices.device_base import DeviceBase
from presentations.short_messaging.transports.sms import \
     iDigiSMSTransportClient
from presentations.short_messaging.transports.iridium import \
     iDigiIridiumTransportClient

# constants

idigi_client_tracer = get_tracer("iDigiClient")

# exception classes

# interface functions

# classes
class iDigiClient:

    # List of Supported Transports.
    SUPPORTED_TRANSPORTS = { 'sms' : iDigiSMSTransportClient,
                             'iridium' : iDigiIridiumTransportClient }

    # Encoding length of a DIA command message.
    MESSAGE_LEN = 0x2
    # Encoding length of a DIA command.
    COMMAND_LEN = 0x1

    # Command values for Device Cloud Communication
    COMMAND_ANNOUNCE_DEVICE               = 0x00
    COMMAND_UPDATE_CHANNEL                = 0x01
    COMMAND_ALARM_CHANNEL                 = 0x02
    COMMAND_GET_DIA_VERSION               = 0x03
    COMMAND_GET_DEVICEID                  = 0x04
    COMMAND_GET_CHANNEL                   = 0x05
    COMMAND_SET_CHANNEL                   = 0x06
    COMMAND_REFRESH_CHANNEL               = 0x07
    COMMAND_GET_DEVICE_LIST               = 0x08
    COMMAND_GET_CHANNELS_LIST             = 0x09

    def __init__(self, name, core, transport_managers, settings):
        """\
            The typical init function.
        """
        self.__name = name
        self.__core = core
        self.__transport_managers = transport_managers

        # Store a few of the settings that we use outside of init.
        self.__transport = settings['transport']
        self.__tracer = get_tracer(name)

        # Massage the enabled setting into the type/format we want.
        if type(settings['enabled']) == bool:
            self.__enabled = settings['enabled']
        elif type(settings['enabled']) == str:
            enabled = settings['enabled'].lower()
            if enabled == "true":
                self.__enabled = True
            elif enabled == "false":
                self.__enabled = False
            else:
                self.__enabled = settings['enabled']
        else:
            self.__enabled = False

        # Get our device ID
        try:
            self.__deviceid = get_device_id()
        except:
            raise

        # Allocate the transport method we should use for this client.
        try:
            if settings['transport'] == "sms":
                self.__transport_obj = iDigiSMSTransportClient(self,
                                 self.__transport_managers['SMS'])
            elif settings['transport'] == "iridium":
                self.__transport_obj = iDigiIridiumTransportClient(self,
                                 self.__transport_managers['Iridium'])
            else:
                raise Exception, "Unknown Transport Type"
        except:
            raise


    @staticmethod
    def verify_settings(settings):

        if 'transport' not in settings:
            idigi_client_tracer.warning("Settings: " \
                  "'transport' option must be defined!")
            return False

        if type(settings['transport']) != str:
            idigi_client_tracer.warning("Settings: " \
                  "'transport' must be a string!")
            return False

        # Convert Transport value to be all lower-case.
        settings['transport'] = settings['transport'].lower()

        if settings['transport'] not in iDigiClient.SUPPORTED_TRANSPORTS:
            idigi_client_tracer.warning("Settings: Unknown 'transport' type of '%s'!", \
                                          settings['transport'])
            return False

        # Have the transport client verify its settings.
        return iDigiClient.SUPPORTED_TRANSPORTS[settings['transport']]\
                                                .verify_settings(settings)


    def get_enabled(self):
        """\
            Returns whether this client is currently enabled or not.
        """
        return self.__enabled


    def name(self):
        """\
            Returns the Clients name.
        """
        return self.__name


    # Device Cloud Server does not want or support this command.
    def announce_device(self):
        """\
            Announce to the Device Cloud Server that we are now up and running.
            Typically this would return the device ID of the unit.

            NOTE:  The current Device Cloud Server does not want nor support this
                   command!
        """
        return


    def create_update_message(self, channel):
        """\
            The Short Messaging Service presentation will call this function
            when it decides it wants to send the Device Cloud Server an update
            message about a channel.
            When it decides to do this, is based upon what interval the
            user decided to set up for each channel/filter.

            NOTE: This is an unsolicited message that Device Cloud will receive,
                  parse and store into its database of DIA channels for
                  this device.
        """
        return (self.__create_channel_message(self.COMMAND_UPDATE_CHANNEL,
                                             channel.name()), False)


    def create_alarm_message(self, channel):
        """\
            The Short Messaging Service presentation will call this function
            when it decides it wants to send the Device Cloud Server an alarm
            message about a channel.
            When it decides to do this, is based upon what alarm the
            user decided to set up for each channel/filter.

            NOTE: This is an unsolicited message that Device Cloud will receive,
                  parse and store into its database of DIA channels for
                  this device.
        """
        return (self.__create_channel_message(self.COMMAND_ALARM_CHANNEL,
                                             channel.name()), False)


    def command_access_permitted(self):
        """\
            The Short Messaging Service presentation will call this function
            when it wants to know if command access is permitted for this
            client.

            NOTE: For Device Cloud Clients, Command Access is always permitted.
        """
        return True


    def command_access_allowed_sender(self):
        """\
            The Short Messaging Service presentation will call this function
            when it wants to know who the allowed Sender (Device Cloud) is.
        """
        return self.__transport_obj.get_address()


    def transport_type(self):
        """\
            Returns the type of Transport this client is.
        """
        return self.__transport


    def send_message(self, message_list):
        """\
            Sends a list of messages out the Client to the Device Cloud Server.
        """
        return self.__transport_obj.send_message(message_list)


    def receive_message(self, sender, message, response_required):
        """\
            Receives a message from the Device Cloud Server.
        """
        # Verify command access is permitted for this client.
        if self.command_access_permitted() != True:
            self.__tracer.warning("Received Message (%s) from %s.  " \
                  "We do not permit command access... Ignoring...", \
                          message, sender)
            return None

        return self.__parse_message(message, response_required)


    def __parse_message(self, message, response_required):
        """\
            Parses a message from the Device Cloud Server.
        """
        message_list = []

        # Split up the long message into short/distinct commands.
        # Each command from Device Cloud is sent as len, command, data.
        commands = []
        raw_data = message
        while raw_data != "":
            command_len = struct.unpack("!H", raw_data[0:self.MESSAGE_LEN])[0]
            raw_data = raw_data[self.MESSAGE_LEN:]
            command = struct.unpack("!B", raw_data[0:self.COMMAND_LEN])[0]
            command_data = raw_data[self.COMMAND_LEN:command_len]
            commands.append((command, command_data))
            raw_data = raw_data[command_len:]

        self.__tracer.info("Number of Commands received: %s", len(commands))

        # Now that each command is split up, go and parse each command,
        # and create a response (if any) for each command.
        for command, command_data in commands:

            if command < self.COMMAND_GET_DIA_VERSION or \
               command > self.COMMAND_GET_CHANNELS_LIST:
                self.__tracer.warning("Unknown Command: %x", command)

                # Unknown command, just send back an empty response.
                d = struct.pack("!B%ds" % (len("")),
                                           command,
                                           "")
                l = struct.pack("!H", len(d))
                message_back = l + d
                response_required = False
                message_list.append((message_back, response_required))
                continue

            self.__tracer.info("Processing Command: %x", command)

            message_back = ""

            # Get the DIA Version...
            if command == self.COMMAND_GET_DIA_VERSION:
                d = struct.pack("!B%ds" % (len(DIA_VERSION)),
                                           self.COMMAND_GET_DIA_VERSION,
                                           DIA_VERSION)
                l = struct.pack("!H", len(d))
                message_back = l + d
                response_required = False
                message_list.append((message_back, response_required))

            # Get the Device ID...
            elif command == self.COMMAND_GET_DEVICEID:
                d = struct.pack("!B%ds" % (len(self.__deviceid)),
                                            self.COMMAND_GET_DEVICEID,
                                            self.__deviceid)
                l = struct.pack("!H", len(d))
                message_back = l + d
                response_required = False
                message_list.append((message_back, response_required))

            # Get the Channel data given a specific channel name...
            elif command == self.COMMAND_GET_CHANNEL:
                l = len(command_data)
                cn = struct.unpack("!%ds" % (l), command_data)
                cn = cn[0]

                message_back = self.__command_get_channel_data(
                                              self.COMMAND_GET_CHANNEL, cn)
                response_required = False
                message_list.append((message_back, response_required))

            # Set the Channel value given a specific channel name...
            elif command == self.COMMAND_SET_CHANNEL:

                message_back = self.__command_set_channel_data(command_data)
                response_required = False
                message_list.append((message_back, response_required))

            # Refresh the Channel given a specific channel name...
            elif command == self.COMMAND_REFRESH_CHANNEL:
                l = len(command_data)
                cn = struct.unpack("!%ds" % (l), command_data)
                cn = cn[0]

                message_back = self.__command_refresh_channel_data(cn)
                response_required = False
                message_list.append((message_back, response_required))

            # Get the Device Listing
            elif command == self.COMMAND_GET_DEVICE_LIST:

                message_back = self.__command_get_device_list()
                response_required = False
                message_list.append((message_back, response_required))

            # Get Channels Listing
            elif command == self.COMMAND_GET_CHANNELS_LIST:
                l = len(command_data)
                device_name = struct.unpack("!%ds" % (l), command_data)
                device_name = device_name[0]

                message_back = self.__command_get_channel_list(device_name)
                response_required = False
                message_list.append((message_back, response_required))

            else:
                self.__tracer.error("Unknown Command. Message: %x", \
                       command)
                # Unknown command, just send back an empty response.
                d = struct.pack("!B%ds" % (len("")),
                                           command,
                                           "")
                l = struct.pack("!H", len(d))
                message_back = l + d
                response_required = False
                message_list.append((message_back, response_required))

        # Send back a response, if any
        if len(message_list) > 0:
            self.__tracer.info("Returning data back to Device Cloud Server.")
            return message_list
        else:
            return None


    def __command_get_channel_data(self, command, channel_name):
        """\
            Given a channel name, returns information about the channel.
        """
        return self.__create_channel_message(command, channel_name)


    def __command_set_channel_data(self, data):
        """\
            Given a channel name, sets the specified data value on the channel.
            Returns the current information about the channel.
        """
        channel_name = ""
        for i in data:
            if i == '\0':
                break
            channel_name += i
        else:
            self.__tracer.warning("Ill-formed Set Channel Command." \
                                 "  Channel name not sent correctly.")
            return None

        data = data[len(channel_name) + 1:]
        self.__tracer.info("Set Channel name: %s", channel_name)

        value_type = struct.unpack("!c", data[0])[0]
        data = data[1:]
        self.__tracer.info("Set value type: %s", value_type)

        if value_type == '?':
            value = struct.unpack("!B", data[0:1])[0]
            value = bool(value)
            data = data[1:]
        elif value_type == 'i':
            value = struct.unpack("!i", data[0:4])[0]
            data = data[4:]
        elif value_type == 'f':
            value = struct.unpack("!f", data[0:4])[0]
            data = data[4:]
        elif value_type == 's':
            value = ""
            for i in data:
                if i == '\0':
                    break
                value += i
            else:
                self.__tracer.warning("Ill-formed Set Channel Command." \
                                     "  String value type not sent correctly.")
                return None
            data = data[len(value) + 1:]
        else:
            self.__tracer.warning("Ill-formed Set Channel Command." \
                                 "  Unknown value type.")
            return None

        self.__tracer.info("Set Value: %s", value)

        cm = self.__core.get_service("channel_manager")
        cdb = cm.channel_database_get()
        channel = cdb.channel_get(channel_name)

        sample = None
        try:
            sample = Sample(digitime.time(), channel.type()(value), "")
        except Exception, e:
            self.__tracer.error("Set Channel Command." \
                                 "  Unable to create sample.")
            return None

        try:
            channel.set(sample)
        except Exception, e:
            self.__tracer.error("Set Channel Command." \
                                 "  Unable to Set Channel.")
            return None

        # Now just return the GET function data of the current channel
        # data that we just set.
        return self.__create_channel_message(self.COMMAND_SET_CHANNEL,
                                             channel_name)


    def __command_refresh_channel_data(self, channel_name):
        """\
            Given a channel name, forces DIA to refresh that channel.
        """
        cm = self.__core.get_service("channel_manager")
        cdb = cm.channel_database_get()
        ret = True

        if not cdb.channel_exists(channel_name):
            self.__tracer.error("Refresh Channel Command." \
                                 "  Channel does not exist.")
            ret = False

        # Attempt to refresh channel, only if the channel exists.
        if ret != False:
            channel = cdb.channel_get(channel_name)
            try:
                perm = channel.perm_mask()
                if perm & PERM_REFRESH:
                    self.__tracer.info("Refresh Command. Performing refresh.")
                    channel.refresh()
                else:
                    self.__tracer.warning("Refresh Channel Command." \
                              "  Unable to Refresh Channel.  No Permission.")
                    ret = False
            except Exception, e:
                self.__tracer.error("Refresh Channel Command." \
                                  "  Unable to Refresh Channel.")
                ret = False

        # Create our response back to the Server.
        d = struct.pack("!B%dscB" % (len(channel_name)),
                                    self.COMMAND_REFRESH_CHANNEL,
                                    channel_name, '\0', ret)
        l = struct.pack("!H", len(d))
        data = l + d
        return data


    def __command_get_device_list(self):
        """\
            Returns a lost of the names of all the devices currently present
            in DIA.
        """
        dm = self.__core.get_service("device_driver_manager")
        device_list = dm.instance_list()

        d = struct.pack("!B", self.COMMAND_GET_DEVICE_LIST)

        # Walk each device name, and encode it into our response
        # back to the Server.
        for device_name in device_list:
            if device_name != None and type(device_name) == str:
                d += struct.pack("!%dsc" % (len(device_name)),
                                             device_name, '\0')
        l = struct.pack("!H", len(d))
        data = l + d
        return data


    def __command_get_channel_list(self, device_name):
        """\
            Given a device name, return a list of the names of all the channels
            that the device has.
        """
        dm = self.__core.get_service("device_driver_manager")
        cm = self.__core.get_service("channel_manager")

        # Always send back the command name, and the device name
        # we are trying to collect channel name data for.
        channels_list = struct.pack("!B%dsc" % (len(device_name)),
                                    self.COMMAND_GET_CHANNELS_LIST,
                                    device_name, '\0')

        instance_list = dm.instance_list()
        cdb = cm.channel_database_get()

        # Walk each device in the system, trying to find our the device.
        for device in instance_list:
            obj = dm.instance_get(device)
            # Check to see if we found the device we are interested in.
            if device_name == obj.get_name():
                # Only DeviceBase instances have channels/properties.
                if isinstance(obj, DeviceBase):
                    for ch in obj.property_list():
                        channel_name = "%s.%s" % (device_name, ch)
                        chan = cdb.channel_get(channel_name)
                        # Ask the channel what "type" it is:
                        type_val = chan.type()
                        if type_val == bool:
                            type_val = '?'
                        elif type_val == Boolean:
                            type_val = '?'
                        elif type_val == float:
                            type_val = 'f'
                        elif type_val == int:
                            type_val = 'i'
                        elif type_val == str:
                            type_val = 's'
                        else:
                            self.__tracer.warning("Get Channel List Command." \
                                 "  Unknown type for channel.  Type: %s", type_val)
                            continue

                        channels_list += struct.pack("!%dscc" % (len(ch)),
                                             ch, '\0', type_val)

                # Device matched string, but doesn't have any channels
                else:
                    break

        # Calculate length, and pass the buffer back up.
        l = struct.pack("!H", len(channels_list))
        channels_list = l + channels_list
        return channels_list


    def __create_channel_message(self, command, channel_name):
        """\
            Given a command and channel name, returns a data blob that
            will contain all the current information about the channel.
            NOTE: The command will be embedded in this returned data blob.
        """
        cm = self.__core.get_service("channel_manager")
        cdb = cm.channel_database_get()

        value = ""
        value_type = type(int)
        unit = ""
        timestamp = ""

        d = struct.pack("!B%dsc" % (len(channel_name)),
                                    command,
                                    channel_name, '\0')

        # If the channel doesn't exist, return back the command and channel,
        # nothing more.
        if not cdb.channel_exists(channel_name):
            self.__tracer.error("Create Channel Message. Channel does not exist.")
            l = struct.pack("!H", len(d))
            data = l + d
            return data

        channel = cdb.channel_get(channel_name)

        try:
            sample = channel.get()
            value = str(sample.value)

            value_type = type(value)
            if value_type == bool:
                d += struct.pack("!cB", '?', value)
            elif value_type == Boolean:
                d += struct.pack("!cB", '?', value)
            elif value_type == int:
                d += struct.pack("!ci", 'i', value)
            elif value_type == float:
                d += struct.pack("!cf", 'f', value)
            elif value_type == str:
                d += struct.pack("!c%dsc" % (len(value)), 's', value, '\0')
            else:
                self.__tracer.warning("Get Channel List Command." \
                      "  Unknown type for channel.  Type: %s", value_type)
                l = struct.pack("!H", len(d))
                data = l + d
                return data

            unit = sample.unit
            d += struct.pack("!%dsc" % (len(unit)), unit, '\0')

            timestamp = sample.timestamp
            d += struct.pack("!I", int(timestamp))

        except Exception, e:
            self.__tracer.error(str(e))
            pass

        # Calculate length, and pass the buffer back up.
        l = struct.pack("!H", len(d))
        data = l + d
        return data
