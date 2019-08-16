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
Short Messaging (End User)

"""

# imports
import digitime

from common.digi_device_info import get_device_id
from core.tracing import get_tracer

from common.helpers.format_channels import iso_date
from presentations.short_messaging.transports.sms import SMSTransportClient
from presentations.short_messaging.transports.iridium import \
    IridiumTransportClient

# constants

enduser_client_tracer = get_tracer("EnduserClient")

# exception classes

# interface functions

# classes
class EnduserClient:

    # List of Supported Transports.
    SUPPORTED_TRANSPORTS = { 'sms'     : SMSTransportClient,
                             'iridium' : IridiumTransportClient }

    def __init__(self, name, core, transport_managers, settings):

        self.__name = name
        self.__core = core
        self.__transport_managers = transport_managers

        # Store a few of the settings that we use outside of init.
        self.__update_message = settings['update_message']
        self.__alarm_message = settings['alarm_message']
        self.__command_access = settings['command_access']
        self.__transport = settings['transport']

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
        self.__deviceid = get_device_id()
        self.__tracer = get_tracer(name)

        # Allocate the transport method we should use for this client.
        try:
            if settings['transport'] == "sms":
                self.__transport_obj = SMSTransportClient(self,
                                 self.__transport_managers['SMS'],
                                 settings['number'])
            elif settings['transport'] == "iridium":
                self.__transport_obj = IridiumTransportClient(self,
                                 self.__transport_managers['Iridium'])
            else:
                raise Exception, "Unknown Transport Type"
        except:
            raise


    @staticmethod
    def verify_settings(settings):

        if 'transport' not in settings:
            enduser_client_tracer.warning("Settings: " \
                  "'transport' option must be defined!")
            return False

        if type(settings['transport']) != str:
            enduser_client_tracer.warning("Settings: " \
                  "'transport' must be a string!")
            return False

        # Convert Transport value to be all lower-case.
        settings['transport'] = settings['transport'].lower()

        if settings['transport'] not in EnduserClient.SUPPORTED_TRANSPORTS:
            enduser_client_tracer.warning("Settings: Unknown 'transport' type of '%s'!", \
                                          settings['transport'])
            return False
        
        if 'command_access' not in settings:
            enduser_client_tracer.warning("Enduser Client Settings: "
                  "'command_access' option not defined.  Defaulting to False")
            settings['command_access'] = False            

        if type(settings['command_access']) != bool:
            enduser_client_tracer.warning("Settings: " \
                  "'command_access' must be set to True or False!")
            return False

        # SMS is the only transport that requires a number (phone number) setting.
        if settings['transport'] == 'sms':
            if 'number' not in settings:
                enduser_client_tracer.warning("Settings: " \
                      "'number' option must be defined!")
                return False

            if type(settings['number']) != str:
                enduser_client_tracer.warning("Settings: " \
                      "'number' must be set a string!")
                return False

        if 'update_message' not in settings:
            enduser_client_tracer.warning("Settings: " \
                  "'update_message' option must be defined!")
            return False

        if type(settings['update_message']) != str:
            enduser_client_tracer.warning("Settings: " \
                  "'update_message' must be a string!")
            return False

        if 'alarm_message' not in settings:
            enduser_client_tracer.warning("Settings: " \
                  "'alarm_message' option must be defined!")
            return False

        if type(settings['alarm_message']) != str:
            enduser_client_tracer.warning("Settings: " \
                  "'alarm_message' must be a string!")
            return False

        # Have the transport client verify its settings.
        return EnduserClient.SUPPORTED_TRANSPORTS[settings['transport']]\
                                                  .verify_settings(settings)


    def get_enabled(self):

        return self.__enabled


    def name(self):

        return self.__name


    def announce_device(self):
 
        message_list = []
        message = "Device %s now online at %s" % (self.__deviceid,
                                                  iso_date(digitime.time()))
        message_list.append(message)
        self.__transport_obj.send_message(message_list)


    def create_update_message(self, channel):
        
        return self.__create_message(self.__update_message, channel)


    def create_alarm_message(self, channel):
        
        return self.__create_message(self.__alarm_message, channel)


    def command_access_permitted(self):

        return self.__command_access


    def command_access_allowed_sender(self):

        return self.__transport_obj.get_address()


    def transport_type(self):

        return self.__transport


    def send_message(self, message_list):

        return self.__transport_obj.send_message(message_list)


    def receive_message(self, sender, message):

        # Just print out the Sender and Message.
        # It is intended that a developer will enhance this to
        # their specific needs.
        self.__tracer.info("SENDER: %s, MESSAGE: %s", sender, message)


    def __create_message(self, message_format, channel):

        # Run through the message format string, substituting
        # out any of the magic values, specifically:
        # %c, %v, %u, %t, and %h

        message = ""
        escape = False
        for i in message_format:
            if escape == True and i == 'c':
                    message += channel.name()
                    escape = False
            elif escape == True and i == 'v':
                    message += str(channel.get().value)
                    escape = False
            elif escape == True and i == 'u':
                    message += str(channel.get().unit)
                    escape = False
            elif escape == True and i == 't':
                    message += str(channel.get().timestamp)
                    escape = False
            elif escape == True and i == 'h':
                    message += iso_date(channel.get().timestamp)
                    escape = False
            elif i == '%':
                # If we are already in escaped mode, then the previous
                # escape was not used.
                # Reinsert the previous escape into the stream, and keep
                # ourselves in escape mode for the next character.
                if escape == True:
                    message += '%'
                escape = True
            else:
                # If we are in escaped mode, and we get an escape
                # character that we don't recognize, make sure
                # we put back the escape character into our stream.
                if escape == True:
                    escape = False
                    message += '%'
                message += i

        # If user had the last character as an escape character,
        # then we should reinsert said escape character into the
        # stream, as it is unused for our parsing.
        if escape == True:
            message += '%'

        return message
