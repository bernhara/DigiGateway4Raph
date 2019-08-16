############################################################################
#                                                                          #
# Copyright (c)2012 Digi International (Digi). All Rights Reserved.        #
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
Iridium Transport Manager, Iridium and Iridium Clients.
"""

# imports
import digitime
import copy
import heapq

# For regular Iridium messages.
try:
    import digi_iridium
except:
    pass

# For Iridium messages.
try:
    import idigi_iridium
except:
    pass

from digi_ElementTree import ElementTree
from common.utils import TimeIntervals
from core.tracing import get_tracer

# constants

iridium_manager_tracer = get_tracer("IridiumTransportManager")
iridium_client_tracer = get_tracer("IridiumTransportClient")
iridium_idigi_client_tracer = get_tracer("iDigiIridiumTransportClient")

# exception classes

# interface functions

# classes

class IridiumTransportManager:
    
    def __init__(self, max, interval):
        """Initialize the Iridium Transport Manager"""

        # Subscribe to a Callback to any Iridium messages that come in.
        self.__digi_iridium_cb_handle = None
        self.__digi_iridium_supported = False
        if 'digi_iridium' in globals():
            try:
                self.__digi_iridium_cb_handle = digi_iridium.Callback(\
                                            self.__digi_receive_cb)
                self.__digi_iridium_supported = True
            except:
                pass

        # Subscribe to a Callback to any DIA Iridium messages that come in.
        self.__idigi_iridium_cb_handle = None
        self.__idigi_iridium_supported = False
        if 'idigi_iridium' in globals():
            try:
                self.__idigi_iridium_cb_handle = idigi_iridium.Callback(\
                                              self.__idigi_receive_cb, None, 9)
                self.__idigi_iridium_supported = True
            except:
                pass

        # Iridium Clients list.
        self.__client_list = []

        # Store how many messages we are allowed to send in a given period.
        self.__message_queue_max = max

        # Store the given period interval value.
        for item in TimeIntervals:
            if item['name'] == interval: 
                self.__message_queue_interval = item['value']
                break
        else:
            raise Exception, "Unknown Interval setting"

        # We will store our messages on the queue until they pass the
        # given interval mark, at which time they will be removed.
        self.__message_queue = []


    @staticmethod
    def verify_settings(settings):
        """Verify the settings given to us by the user/system"""

        if 'limit' not in settings:
            iridium_manager_tracer.warning("Settings: " \
                  "'limit' option must be defined!")
            return False

        if type(settings['limit']) != int:
            iridium_manager_tracer.warning("Settings: 'limit' must be an int!")
            return False

        if 'limit_interval' not in settings:
            iridium_manager_tracer.warning("Settings: " \
                  "'limit_interval' option must be defined!")
            return False

        if type(settings['limit_interval']) != str:
            iridium_manager_tracer.warning("Settings: " \
                  "'limit_interval' must be an str!")
            return False

        # Force limit interval setting to always be lower case
        settings['limit_interval'] = settings['limit_interval'].lower()

        values = ''
        for item in TimeIntervals:
            if settings['limit_interval'] == item['name']:
                break
            values += item['name'] + ', '
        else:
            iridium_manager_tracer.warning("Settings: " \
                "'limit_interval' must be one of the following: %s", values)
            return False

        return True


    def register_client(self, client):
        """\
            Allow a Client to register with the Server..
        """
        if isinstance(client, IridiumTransportClient):
            if self.__digi_iridium_supported == False:
                iridium_manager_tracer.error("Settings: " \
                      "Device does not support Iridium! " \
                      "Ensure you have a product that supports Iridium " \
                      "and has up to date firmware!")
                return False
        elif isinstance(client, iDigiIridiumTransportClient):
            if self.__idigi_iridium_supported == False:
                iridium_manager_tracer.error("Settings: " \
                      "Device does not support iDigi Iridium!" \
                      "Ensure you have a product that supports iDigi Iridium " \
                      "and has up to date firmware!")
                return False
        else:
            iridium_manager_tracer.warning("Client not of valid type.")
            return False

        self.__client_list.append(client)
        return True


    def send_message(self, client, message):
        """\
            Send a message from a Client out using Iridium.
        """
        current_time = digitime.time()
        count = 0

        # Walk the saved message queue, and remove any/all
        # messages that have gone past our expiry time/date.
        while self.__message_queue:
            item_time, item_data = self.__message_queue[0]
            if item_time + self.__message_queue_interval < current_time:
                item = heapq.heappop(self.__message_queue)
                iridium_manager_tracer.info("Removing old item! %s", item)
                del item
            else:
                break

        # Whenever we want to send a message, we need to verify that we don't
        # go past what the user specified as their maximum they are willing to
        # send in a given interval time frame.
        if len(self.__message_queue) >= self.__message_queue_max:
            iridium_manager_tracer.warning("Maximum messages per interval have been met.  " \
                  "Not sending: %s", message)
            return 0

        if isinstance(client, IridiumTransportClient):
            iridium_manager_tracer.info("Sending Digi Iridium message: %s", message)
            digi_iridium.send(message)
        elif isinstance(client, iDigiIridiumTransportClient):
            iridium_manager_tracer.info("Sending iDigi Iridium message: %s", message[0])
            count, handle = idigi_iridium.send_dia(message[0])

        # Store the packet we just sent.
        # We do this for 2 reasons.
        # 1) Keep track of how many we sent per interval.
        # 2) To ensure we got our packet ACK'ed.
        if isinstance(client, IridiumTransportClient):
            d = dict(packet = message, acked = False)
        elif isinstance(client, iDigiIridiumTransportClient):
            d = dict(packet = message[0], acked = False)

        item = [ current_time, d]
        heapq.heappush(self.__message_queue, item)

        return count


    def __digi_receive_cb(self, message):
        """Callback function for Digi Iridium messages received."""
        # Forward the message off to each Iridium client that we manage.
        for client in self.__client_list:
            if isinstance(client, IridiumTransportClient):
                client.receive_message(message, None)


    def __idigi_receive_cb(self, path, message, response_required, timestamp):
        """Callback function for iDigi Iridium messages received."""
        # Forward the message off to each iDigi Iridium client that we manage.
        iridium_manager_tracer.warning("Receive Data.  Response_required: %d Message: %s", \
                                           response_required, message)
        for client in self.__client_list:
            if isinstance(client, iDigiIridiumTransportClient):
                response = client.receive_message(message, response_required)
                # If a response is required, and the client gave a us response,
                # we have to return the response to the callback function.
                # This means that only 1 client can respond to this message.
                # ie, first come, first served.
                if response_required and response != None:
                    iridium_manager_tracer.info("Response: %s", response)
                    full_response = ""
                    for res in response:
                        full_response += res[0]
                    return full_response

        iridium_manager_tracer.warning("No Response")
        return None



class IridiumTransportClient:
    
    # Maximum Payload that Iridium can do.
    MAX_PAYLOAD = 340

    def __init__(self, parent, manager):

        # Store a pointer to our parent.
        self.__parent = parent

        # Store a pointer to our Iridium Manager.
        self.__iridium_manager = manager

        # Register ourselves with the Iridium Manager.
        self.__iridium_manager.register_client(self)

        # Statistics
        self.__total_sent = 0
		
        from core.tracing import get_tracer
        self.__tracer = get_tracer("IridiumTransportClient")


    @staticmethod
    def verify_settings(settings):
        # No settings are required for a Digi Iridium Client.
        # All current settings are stored in the Device's firmware.
        return True


    def get_max_payload(self):
        return self.MAX_PAYLOAD


    def get_address(self):
        return "Digi"


    def send_message(self, message_list):
        ret = False
        max_length = self.MAX_PAYLOAD

        while True:
            message = ""
            count = 0

            # Nothing to send...
            if len(message_list) == 0:
                return ret

            for i in copy.copy(message_list):
                if count + len(i) >= max_length:
                    continue
                message += i
                message_list.remove(i)
                count += len(message)

            if len(message) > 0:
                try:
                    self.__iridium_manager.send_message(self, message)
                    self.__total_sent += 1
                    ret = True
                except Exception, e:
                    self.__tracer.error("Send Fail: %s", str(e))
        return ret


    def receive_message(self, message, response_required):
        if response_required is None:
            self.__parent.receive_message(message)
        else:
            self.__parent.receive_message(message, response_required)



class iDigiIridiumTransportClient:
    
    # Maximum Payload that iDigi Iridium can do.
    MAX_PAYLOAD = 76500

    def __init__(self, parent, manager):

        # Store a pointer to our parent.
        self.__parent = parent

        # Store a pointer to our iDigi Iridium Manager.
        self.__iridium_manager = manager

        # Register ourselves with the iDigi Iridium Manager.
        self.__iridium_manager.register_client(self)

        # Statistics
        self.__total_sent = 0
		
        from core.tracing import get_tracer
        self.__tracer = get_tracer("iDigiIridiumTransportClient")


    @staticmethod
    def verify_settings(settings):
        # No settings are required for an iDigi Iridium Client.
        # All current settings are stored in the Device's firmware.
        return True


    def get_max_payload(self):
        return self.MAX_PAYLOAD


    def get_address(self):
        """\
            Retrieves the current iDigi Iridium phone number from the Digi device.
        """
        return "iDigi"


    def send_message(self, message_list):
        ret = False

        # Nothing to send...
        if len(message_list) == 0:
            return ret

        # Walk each message in the message list, and send it.
        for msg in message_list:
            try:
                self.__total_sent += self.__iridium_manager.send_message(self, msg)
                ret = True
            except Exception, e:
                self.__tracer.error("Send Fail: %s", str(e))

        return ret


    def receive_message(self, message, response_required):
        return self.__parent.receive_message('iDigi', message, response_required)
