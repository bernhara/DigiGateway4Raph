############################################################################
#                                                                          #
# Copyright (c)2010 Digi International (Digi). All Rights Reserved.        #
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
**Short Messaging DIA Python Module**

--THIS MODULE WILL NOT FUNCTION EXCEPT ON DIGI DEVICES--

**Sample Config**::

  - name: Short_Messaging_Service
    driver: presentations.short_messaging.short_messaging:ShortMessaging
    settings:
        SMS:
            settings:
                limit: 5
                limit_interval: hour
        Iridium:
            settings:
                limit: 10
                limit_interval: hour
        clients:
            - name: iDigi
              settings:
                  enabled: True
                  transport: SMS
                  type: iDigi
            - name: Enduser_1
              settings:
                  enabled: False
                  transport: SMS
                  type: Enduser
                  number: 19525551234
                  command_access: True
                  update_message: "DIA Update.  Chan: %c  Val: %v %u  Time: %h"
                  alarm_message: "DIA Alarm!  Chan: %c  Val: %v %u  Time: %h"
            - name: Enduser_2
              settings:
                  enabled: device.channel
                  transport: SMS
                  type: Enduser
                  number: 19525556789
                  command_access: True
                  update_message: "<update><chan>%c</chan><val>%v</val><unit>%u</unit><time>%h</time></update>"
                  alarm_message: "<alarm><chan>%c</chan><val>%v</val><unit>%u</unit><time>%h</time></alarm>"
        updates:
            - name: MassaM3_distance_update
              settings:
                  filter: "Massa*distance*"
                  clients: [ iDigi, Enduser_1, Enduser_2 ]
                  interval: 60
        alarms:
            - name: MassaM3_distance_alarm
              settings:
                  filter: "Massa*distance*"
                  clients: [ iDigi, Enduser_1, Enduser_2 ]
                  condition: "%c <= 10.0 or %c > 30.0"


##########################################################################

This presentation allows for the DIA to send short messages about
channel updates and channel alarms over certain transports like
iDigi SMS, iDigi Iridium, regular SMS or regular Iridium.

"""

# imports
import digitime
import copy
import threading

from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase

from presentations.short_messaging.clients.idigi import iDigiClient
from presentations.short_messaging.clients.enduser import EnduserClient
from presentations.short_messaging.transports.sms import SMSTransportManager
from presentations.short_messaging.transports.iridium import \
    IridiumTransportManager
from common.types.boolean import Boolean
from common.utils import wild_match
from common.shutdown import SHUTDOWN_WAIT

# constants

# exception classes

# interface functions

# classes
class ShortMessaging(PresentationBase, threading.Thread):

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
		
        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        settings_list = [
            Setting(
                name = "SMS", type = dict, required = False,
                default_value = {}, verify_function = self.__verify_SMS),
            Setting(
                name = "Iridium", type = dict, required = False,
                default_value = {}, verify_function = self.__verify_iridium),
            Setting(
                name = "clients", type = dict, required = False,
                default_value = {}, verify_function = self.__verify_clients),
            Setting(
                name = "updates", type = dict, required = False,
                default_value = {}, verify_function = self.__verify_updates),
            Setting(
                name = "alarms", type = dict, required = False,
                default_value = {}, verify_function = self.__verify_alarms),
  ]

        PresentationBase.__init__(self, name = name,
                                  settings_list = settings_list)

        # Our dictionary of Transport Managers.
        self.__transport_managers = {}

        # Our cached list of clients.
        self.client_list = []

        # The list of DIA channels that have matched our filters and so we have
        # subscribed to getting channel updates from DIA as they come in.
        self.__channels_being_watched = []

        # The following list will contain a list of messages that should
        # be sent out at the next interval time.

        self.__coalesce_list = []

        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name = name)
        threading.Thread.setDaemon(self, True)


    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # there were problems with settings, terminate early:
            self.__tracer.error("Settings rejected/not found: %s %s", \
                rejected, not_found)
            return (accepted, rejected, not_found)
        
        if accepted['clients'].has_key('instance_list'):
            clients_list = accepted['clients']['instance_list']
        else:
            self.__tracer.error("Attempt to retrieve 'clients' " \
                  "list failed...")
            rejected['clients'] = accepted['clients']
            del accepted['clients']
            return (accepted, rejected, not_found)        
        if accepted['updates'].has_key('instance_list'):
            updates_list = accepted['updates']['instance_list']
        else:
            updates_list = {}
        
        if accepted['alarms'].has_key('instance_list'):
            alarms_list = accepted['alarms']['instance_list']
        else:
            alarms_list = {}

        ret = self.__verify_valid_client_in_list(updates_list, clients_list)
        if ret == False:
            self.__tracer.error("A client referenced in the " + \
                  "'updates' setting does not exist in the 'clients' setting")
            rejected['updates'] = accepted['updates']
            del accepted['updates']
            return (accepted, rejected, not_found)

        ret = self.__verify_valid_client_in_list(alarms_list, clients_list)
        if ret == False:
            self.__tracer.error("A client referenced in the " \
                  "'alarms' setting does not exist in the 'clients' setting")
            rejected['alarms'] = accepted['alarms']
            del accepted['alarms']
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)
        return (accepted, rejected, not_found)


    def start(self):
        """\
            Start the Short Messaging Presentation instance.
            Returns bool.
        """
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        cdb = cm.channel_database_get()

        # Get our SMS Settings values.
        #
        # Because of the way DIA requires defining a list in its configuration
        # file, the get_setting() call below will first return this value in a
        # dictionary with the actual transports list stored under the key name
        # of 'instance_list'.
        SMS_list = SettingsBase.get_setting(self, "SMS")

        # Allocate an SMS Manager based on the user settings.
        if SMS_list != {}:
            tm = self.__allocate_transport_manager('SMS', SMS_list)

            # Add it to our existing dictionary of transport managers.
            self.__transport_managers = dict(self.__transport_managers.items() + \
                                             tm.items())

        # Get our Iridium Settings values.
        #
        # Because of the way DIA requires defining a list in its configuration
        # file, the get_setting() call below will first return this value in a
        # dictionary with the actual transports list stored under the key name
        # of 'instance_list'.
        iridium_list = SettingsBase.get_setting(self, "Iridium")

        # Allocate an Iridium Manager based on the user settings.
        if iridium_list != {}:
            tm = self.__allocate_transport_manager('Iridium', iridium_list)

            # Add it to our existing dictionary of transport managers.
            self.__transport_managers = dict(self.__transport_managers.items() + \
                                             tm.items())

        # Get our clients list.
        #
        # Because of the way DIA requires defining a list in its configuration
        # file, the get_setting() call below will first return this value in a
        # dictionary with the actual client list stored under the key name of
        # 'instance_list'.
        client_list = SettingsBase.get_setting(self, "clients")
        try:
            client_list = client_list['instance_list']
        except Exception, e:
            self.__tracer.error("Unable to get Client list %s", str(e))
            client_list = []

        self.client_list = self.__allocate_clients(client_list)

        # Tell each client to announce that we are running.
        # This allows each client to send notification out (if desired)
        # that our presentation has been started.
        for client in self.client_list:
            client.announce_device()

        # We want to register for all new channels that might be added
        # during the DIA runtime.
        cp.subscribe_new_channels(self.new_channel_added)

        # Get a listing of all current DIA channels already in existence,
        # and walk through each of them.
        # If they match any of our filters, subscribe to receive notification
        # about new samples as they arrive on the channel.
        current_dia_channels = cdb.channel_list()
        for channel in current_dia_channels:
            filters = self.__match_filter(channel)
            if filters != None and len(filters) > 0:
                cp.subscribe(channel, self.receive)
                data = dict(channel = channel, filters = filters)
                self.__add_new_channel_to_channels_being_watched(data)
        threading.Thread.start(self)
        return True


    def stop(self):
        """Stop the Short Messaging instance.  Returns bool."""
        self.__stopevent.set()
        return True

    def run(self):
        """\
            The Run method.
        """
        # Create a shorthand list of our stored clients, along with any
        # stored messages we want to send to each client.
        client_message_list = []
        for client in self.client_list:
            e = dict(name = client.name(), client = client, message_list = [])
            client_message_list.append(e)

        wait_time = SHUTDOWN_WAIT
        while not self.__stopevent.isSet():
            try:

                #self.__tracer.info("ShortMessaging: Before sleeping of %d seconds", \
                #       wait_time)
                digitime.sleep(wait_time)
                #self.__tracer.info("ShortMessaging: After sleeping of %d seconds", \
                #       wait_time)

                current_time = digitime.time()

                # Walk through the queued up channels that have updates
                # waiting to be sent.

                #self.__tracer.info("ShortMessaging: Len of Watched List: %d", \
                #       len(self.__channels_being_watched))
                #for entry in self.__channels_being_watched:
                #    for filter in entry['filters']:
                #        self.__print_statistics(entry['channel'], filter)

                #self.__tracer. "ShortMessaging: Len of Coalesce List: %d", \
                #       len(self.__coalesce_list))
                #for entry in self.__coalesce_list:
                #    self.__print_statistics(entry['channel'], entry['filter'])

                for entry in copy.copy(self.__coalesce_list):
                    filter = entry['filter']
                    messages = entry['messages']
                    interval = filter['interval'] * 60
                    last = filter['last_sent']

                    # See if the time is up, and that we need to send
                    # a new update.
                    if (last + interval) < current_time:

                        self.__tracer.info("Past Time, Should Send!")

                        for message in messages:

                            # Find the correct client entry.
                            for client in client_message_list:
                                if message['client'] == client['name']:
                                    break
                            else:
                                self.__tracer.warning("Run: Unable to find " \
                                      "Client in Client List")
                                continue

                            # Add message to the list of messages we should
                            # send to this client.
                            client['message_list'].append(message['message'])

                            # Bump our filter's total sent value.
                            filter['total_sent'] += 1

                        # Bump our filter's last sent value to the current time
                        filter['last_sent'] = current_time

                        # Finally, remove entry from our list.
                        self.__coalesce_list.remove(entry)

                # Walk each client in our message list cache
                for client in client_message_list:

                    # Check to see if the client has any data that needs
                    # to be sent.
                    if len(client['message_list']) > 0:
                        ret = client['client'].send_message(client['message_list'])
                        if ret == False:
                            self.__tracer.error("Unable to send message!")

                        client['message_list'] = []

            except Exception, e:
                self.__tracer.error("exception while uploading: %s", str(e))


    def new_channel_added(self, channel):
        """\
            Called whenever there is a new channel added into DIA.

            Keyword arguments:

            channel -- the channel name that DIA just added.
        """
        filters = self.__match_filter(channel)
        if filters != None and len(filters) > 0:
            self.__tracer.info("Adding subscription to new channel %s", channel)

            cm = self.__core.get_service("channel_manager")
            cp = cm.channel_publisher_get()
            cp.subscribe(channel, self.receive)
            data = dict(channel = channel, filters = filters)
            self.__add_new_channel_to_channels_being_watched(data)


    def __add_new_channel_to_channels_being_watched(self, data):
        """\
            Add a new channel to our list of channels that are being watched.
        """
        self.__channels_being_watched.append(data)


    def receive(self, channel):
        """\
            Called whenever there is a new sample on one of our subscribed channels

            Keyword arguments:

            channel -- the channel with the new sample
        """
        #self.__tracer.info("ShortMessaging: Received new sample on channel %s", channel.name())
        self.__match_filter_and_send_message(channel)


    def __match_filter(self, channel):
        """\
            Given a full channel name, determine whether any of our
            patterns/filters matches against it.
            Returns the list of matched filters.
        """
        current_time = digitime.time()

        filters = []
        for update_type in [ "updates", "alarms" ]:

            # Get our updates and alarms list.
            #
            # Because of the way DIA requires defining a list in its
            # configuration file, the get_setting() call below will first
            # return this value in a dictionary with the actual updates and
            # alarms list stored under the key name of 'instance_list'.
            entry_list = SettingsBase.get_setting(self, update_type)

            # It's possible the user doesn't have any of the given type set up.
            # This is fine, and we should just continue to the next type.
            if len(entry_list) == 0:
                continue

            try:
                entry_list = entry_list['instance_list']
            except Exception, e:
                self.__tracer.error("Exception trying to get instance_list: %s", \
                       str(e))
                continue

            for entry in entry_list:

                if 'settings' not in entry or entry['settings'] == None:
                    continue

                settings = entry['settings']
                if 'filter' in settings:

                    # If this filter matches something we care about,
                    # add it to our list.
                    if wild_match(settings['filter'], channel) == True:
                        self.__tracer.info("Match (%s) Filter of %s and DIA channel name of %s", \
                                    update_type, settings['filter'], channel)
                        if update_type == "updates":
                            data = dict(type           = update_type,
                                        filter         = settings['filter'],
                                        clients        = settings['clients'],
                                        interval       = settings['interval'],
                                        condition      = None,
                                        synched        = False,
                                        total_sent     = 0,
                                        last_sent      = current_time)
                        else:
                            data = dict(type           = update_type,
                                        filter         = settings['filter'],
                                        clients        = settings['clients'],
                                        interval       = 0,
                                        condition      = settings['condition'],
                                        synched        = False,
                                        total_sent     = 0,
                                        last_sent       = 0.0)

                        filters.append(data)

        return filters


    def __match_filter_and_send_message(self, channel):
        """\
            This function will determine if the supply channel is one that
            we are watching, and if so, it will initiate sending
            notifications as needed.
        """

        for entry in self.__channels_being_watched:

            # If the channel matches, walk through each filter we have stored.
            if channel.name() == entry['channel']:
                self.__send_message_based_on_filter_entry(channel, entry)


    def __send_message_based_on_filter_entry(self, channel, entry):
        """\
            This function will determine if the supplied channel is one that
            we are watching, and if so, it will initiate sending
            notifications as needed.
        """
        cm = self.__core.get_service("channel_manager")
        cdb = cm.channel_database_get()

        for filter in entry['filters']:

            message_list = []

            for send_to_client in filter['clients']:
                message = ""
                client = None
                enabled = None

                # Find the correct client entry.
                for client in self.client_list:
                    if send_to_client == client.name():
                        break
                else:
                    continue

                if client == None:
                    self.__tracer.warning("Unable to find Client in Client List")
                    continue

                # Determine whether the client is enabled or not.
                enabled = client.get_enabled()
                if type(enabled) == bool:
                    if enabled == False:
                        self.__tracer.debug("Client (%s) is disabled", \
                                            client.name())
                        continue
                elif type(enabled) == str:
                    if not cdb.channel_exists(enabled):
                        self.__tracer.warning("Client (%s) channel (%s) does not exist", \
                                               client.name(), enabled)
                        continue
                    tmp_channel = cdb.channel_get(enabled)

                    # Ask the channel what "type" it is.
                    # We only accept "boolean"-like channels.
                    type_val = tmp_channel.type()
                    if type_val != bool and type_val != Boolean:
                        self.__tracer.warning("Client (%s) channel (%s) is not bool/Boolean type", \
                                               client.name(), enabled)
                        continue

                    try:
                        sample = tmp_channel.get()
                        if sample.value == False:
                            self.__tracer.debug("Client (%s) channel (%s) is disabled", \
                                                client.name(), enabled)
                            continue
                    except Exception, e:
                        self.__tracer.error(str(e))
                        continue

                if isinstance(client, iDigiClient) or \
                   isinstance(client, EnduserClient):

                    # If this type is an alarm, we should create a new
                    # message, and then send it out as soon as possible.
                    if filter['type'] == "alarms":

                        # Check to see if the condition has been met...
                        try:
                            ret = self.__check_for_alarm_condition(channel,
                                                         filter['condition'])
                            if ret == True:
                                tmp_message_list = []
                                tmp_message = client.create_alarm_message(channel)
                                tmp_message_list.append(tmp_message)
                                ret = client.send_message(tmp_message_list)
                        except Exception, e:
                            self.__tracer.error("Exception during Alarm condition check: %s", 
                                    str(e))
                            
                    # If the type of filter is an update, we should create
                    # a new message, and then add it to our coalesce list.
                    if filter['type'] == "updates":
                        message = client.create_update_message(channel)
                        d = dict(client = send_to_client, message = message)
                        message_list.append(d)
                
                else:
                    raise Exception, "Unknown Client Type"
                  
            # If there were any messages stored in our message_list,
            # these are "update" messages, and should be added to the
            # coalesce list.
            if len(message_list):
                d = dict(channel = channel.name(), filter = filter,
                         messages = message_list)
                self.__add_to_coalesce_list(d)


    def __add_to_coalesce_list(self, data):
        """\
            Adds new update to the coalesce list, while removing any older
            updates that have been made obsolete by this new update.

            During this addition to the list, we want to try to get our new
            update filters to report back to the end-user/Device Cloud at the same
            time, so that we can combine as much data as we can into
            as few SMS/Satellite/Iridium packets as possible.

            To do that, the idea is to walk through our existing list,
            find a filter that has our same interval rate, and set our
            "last sent" value to be the same, thus synching them together.

            If that doesn't work, we should also try doing a modulo of the
            interval rates, because we still might be able to synch up
            the reporting intervals to report back together at least some
            of the time

        """

        # Scan the coalesce list and see if our filter is already there
        # If it is, remove it.
        for entry in copy.copy(self.__coalesce_list):
            if entry['channel'] == data['channel'] and \
               entry['filter'] == data['filter']:
                self.__coalesce_list.remove(entry)

        # Now attempt to try to synch our update to
        # get it to be sent in with other samples.
        filter = data['filter']
        if filter['type'] == "updates" and filter['synched'] == False:

            for existing_filter in self.__coalesce_list:

                # If we find an existing filter that has the same
                # interval rate as the one we want to use, then
                # we want to "synch" these 2 together, so that
                # they both want to report their updates at the same
                # time.
                if filter['interval'] == existing_filter['filter']['interval']:
                    filter['last_sent'] = existing_filter['filter']['last_sent']
                    filter['synched'] = True
                    break
            else:

                # If we didn't find another filter that has the same
                # interval rate, lets try to see if we can find a filter
                # that has at least a modulo of our interval.

                for existing_filter in self.__coalesce_list:

                    if filter['interval'] % existing_filter['filter']['interval'] == 0:
                        # We found an existing filter that has a modulo
                        # interval rate as the one we want to use.
                        # We now want to "synch" these 2 together, so that
                        # our new filter will want to report its updates
                        filter['last_sent'] = existing_filter['filter']['last_sent']
                        filter['synched'] = True
                        break
                else:
                    filter['synched'] = True


        # Add the new entry to our list.
        self.__coalesce_list.append(data)


    def __check_for_alarm_condition(self, channel, condition):
        """\
            Given a channel structure and a condition string,
            decide whether an alarm condition has been triggerd.
            Returns True of False
        """
        condition_string = ""
        escape = False
        for i in condition:
            if escape == True and i == 'c':
                condition_string += str(channel.get().value)
                escape = False
            elif i == '%':
                # If we are already in escaped mode, then the previous
                # escape was not used.
                # Reinsert the previous escape into the stream, and keep
                # ourselves in escape mode for the next character.
                if escape == True:
                    condition_string += '%'
                escape = True
            else:
                # If we are in escaped mode, and we get an escape
                # character that we don't recognize, make sure
                # we put back the escape character into our stream.
                if escape == True:
                    escape = False
                    condition_string += '%'
                condition_string += i

        # If user had the last character as an escape character,
        # then we should reinsert said escape character into the
        # stream, as it is unused for our parsing.
        if escape == True:
            condition_string += '%'

        #self.__tracer.info("ShortMessaging: condition: ", condition_string)
        value = eval(condition_string)
        #self.__tracer.info("ShortMessaging: result: ", value)
        return value


    def __print_statistics(self, channel, filter):
        """\
            Print SMS, Satellite and Iridium Statistics.
        """
        self.__tracer.info("STAT: Channel %s (%s) SM %s (Total %d Last: %.0f Now: %.0f Next: %.0f)",
            channel, filter['filter'], filter['type'],
               filter['total_sent'], filter['last_sent'],
               digitime.time(),
               filter['last_sent'] + filter['interval'] * 60)


    def __allocate_transport_manager(self, transport, transport_settings):
        """\
            Allocate a transport manager.
        """
        transport_manager = {}

        # For SMS, allocate an SMS Transport Manager.
        if transport == 'SMS':
            limit = transport_settings['settings']['limit']
            limit_interval = transport_settings['settings']['limit_interval']
            transport_manager[transport] = \
                 SMSTransportManager(limit, limit_interval)

        # For Iridium, allocate an Iridium Transport Manager.
        if transport == 'Iridium':
            limit = transport_settings['settings']['limit']
            limit_interval = transport_settings['settings']['limit_interval']
            transport_manager[transport] = \
                 IridiumTransportManager(limit, limit_interval)

        return transport_manager


    def __allocate_clients(self, clients_list):
        """\
            Allocate our clients classes, and store them into 
            an internal list in our class.
        """
        new_clients = []
        for client in clients_list:
            if client['settings']['type'] == "idigi":
                client = iDigiClient(client['name'], self.__core,
                                     self.__transport_managers,
                                     client['settings'])
                new_clients.append(client)
            elif client['settings']['type'] == "enduser":
                client = EnduserClient(client['name'], self.__core,
                                     self.__transport_managers,
                                     client['settings'])
                new_clients.append(client)
            else:
                raise Exception, "Unknown Client Type"

        return new_clients

    
    def __verify_SMS(self, SMS_list):
        """\
            Verify the SMS list the user has given us.
        """
        # Have the SMS Transport Manager verify the settings for us.
        ret = SMSTransportManager.verify_settings(SMS_list['settings'])
        # If settings failed, fail right away.
        if ret == False:
            return False

        return True


    def __verify_iridium(self, iridium_list):
        """\
            Verify the Iridium list the user has given us.
        """
        # Have the Iridium Transport Manager verify the settings for us.
        ret = IridiumTransportManager.verify_settings(iridium_list['settings'])
        # If settings failed, fail right away.
        if ret == False:
            return False

        return True


    def __verify_clients(self, clients):
        """\
            Verify the client list the user has given us.
        """
        try:
            client_list = clients['instance_list']
        except Exception, e:
            self.__tracer.error(e)
            return False

        # Walk each client, and send off to the client type
        # to have it verify settings.
        for client in client_list:
            # Ensure they have a client 'type' setting and that it is a string.
            if 'type' not in client['settings']:
                self.__tracer.warning("Client Settings: (%s) Must specify a 'type'!", \
                       client['name'])
                return False
            if type(client['settings']['type']) != str:
                self.__tracer.warning("Client Settings: (%s) 'type' must be a string!", \
                       client['name'])
                return False

            # Convert value to be all lower-case.
            client['settings']['type'] = client['settings']['type'].lower()

            # All client entries will have an 'enabled' setting that will be
            # set to True, False, or point to a channel that contains a bool
            # value.
            # Verify this setting is present and valid.
            if 'enabled' not in client['settings']:
                self.__tracer.warning("Client Settings: (%s) Must specify an 'enabled' value!", \
                       client['name'])
                return False
            if type(client['settings']['enabled']) != str and \
               type(client['settings']['enabled']) != bool:
                self.__tracer.warning("Client Settings: (%s) 'enabled' must be a string or bool!", \
                       client['name'])
                return False

            ret = True
            if client['settings']['type'] == 'idigi':
                ret = iDigiClient.verify_settings(client['settings'])
            elif client['settings']['type'] == 'enduser':
                ret = EnduserClient.verify_settings(client['settings'])
            else:
                self.__tracer.warning("Client Settings: (%s) Unknown type '%s'!", \
                       client['name'], client['settings']['type'])
                ret = False

            # If settings failed, fail right away.
            if ret == False:
                return False

        return True


    def __verify_updates(self, updates):
        """\
            Verify the updates list the user has given us.
        """

        # It is possible the user doesn't have any updates set up.
        # This is fine, and we should not fail if they don't.
        if len(updates) == 0:
            return True

        try:
            updates_list = updates['instance_list']
        except Exception, e:
            self.__tracer.error(e)
            return False

        # Walk each client, and verify its settings.
        for update in updates_list:

            # Ensure they have a update 'filter' setting
            # and that it is a string.
            if 'filter' not in update['settings']:
                self.__tracer.warning("Updates Settings: " \
                      "(%s) Must specify a 'filter'!", update['name'])
                return False
            if type(update['settings']['filter']) != str:
                self.__tracer.warning("Updates Settings: ", \
                      "(%s) 'filter' must be a string!", update['name'])
                return False
            # Convert value to be all lower-case.
            update['settings']['filter'] = update['settings']['filter'].lower()

            # Ensure they have a update 'clients' setting
            # and that it is a list.
            if 'clients' not in update['settings']:
                self.__tracer.warning("Updates Settings: " \
                      "(%s) Must specify a 'clients'!", update['name'])
                return False
            if type(update['settings']['clients']) != list:
                self.__tracer.warning("Updates Settings: " \
                      "(%s) 'clients' must be a list!", update['name'])
                return False

            # Ensure they have a update 'interval' setting
            # and that it is a int.
            if 'interval' not in update['settings']:
                self.__tracer.warning("Updates Settings: " +
                      "(%s) Must specify an 'interval'!", (update['name']))
                return False
            if type(update['settings']['interval']) != int:
                self.__tracer.warning("Updates Settings: " +
                      "(%s) 'interval' must be a int!", update['name'])
                return False

        return True


    def __verify_alarms(self, alarms):
        """\
            Verify the alarms list the user has given us.
        """

        # It is possible the user doesn't have any alarms set up.
        # This is fine, and we should not fail if they don't.
        if len(alarms) == 0:
            return True

        try:
            alarms_list = alarms['instance_list']
        except Exception, e:
            self.__tracer.error(e)
            return False

        # Walk each client, and verify its settings.
        for alarm in alarms_list:

            # Ensure they have a alarm 'filter' setting
            # and that it is a string.
            if 'filter' not in alarm['settings']:
                self.__tracer.warning("Alarms Settings: " \
                      "(%s) Must specify a 'filter'!", alarm['name'])
                return False
            if type(alarm['settings']['filter']) != str:
                self.__tracer.warning("Alarms Settings: " \
                      "(%s) 'filter' must be a string!", alarms['name'])
                return False

            # Convert value to be all lower-case.
            alarm['settings']['filter'] = alarm['settings']['filter'].lower()

            # Ensure they have a alarm 'clients' setting
            # and that it is a list.
            if 'clients' not in alarm['settings']:
                self.__tracer.warning("Alarms Settings: " \
                      "(%s) Must specify a 'clients'!", alarm['name'])
                return False
            if type(alarm['settings']['clients']) != list:
                self.__tracer.warning("Alarms Settings: " \
                      "(%s) 'clients' must be a list!", alarm['name'])
                return False

            # Ensure they have a alarm 'condition' setting
            # and that it is a string.
            if 'condition' not in alarm['settings']:
                self.__tracer.warning("Alarms Settings: " \
                      "(%s) Must specify a 'condition'!", alarm['name'])
                return False
            if type(alarm['settings']['condition']) != str:
                self.__tracer.warning("Alarms Settings: " \
                      "(%s) 'condition' must be a str!", alarm['name'])
                return False

        return True


    def __verify_valid_client_in_list(self, check_dict, clients_list):
        """\
            Verify that a called out client in one of the update or alarm
            list points to a valid client in the client list.
        """
        
        if not len(check_dict):
            #No items in list, so how could something that doesn't exist 
            #reference something else that doesn't exist?
            return True
        
        name_list = []
        for entry in clients_list:
            name_list.append(entry['name'])
            
        for entry in check_dict:
            for item in entry['settings']['clients']:
                if item not in name_list:
                    self.__tracer.warning("Client %s does not exist!", item)
                    return False
        
        return True
