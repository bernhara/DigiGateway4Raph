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

# imports
from channels.channel import Channel
from channels.channel_publisher import ChannelPublisher
from channels.logging.logging_manager import LoggingManager
from channels.channel_database_interface import \
    ChannelDatabaseInterface, ChannelAlreadyExists, ChannelDoesNotExist
from copy import copy

# constants

# exception classes


# interface functions

# classes

class ChannelDatabase(ChannelDatabaseInterface):
    """
    The :class:`~channels.channel_database.ChannelDatabase` manages the
    list of :class:`~channels.channel.Channel` objects and is responsible
    for managing the query interface to this list of channel objects.

    There should only be one primary :class:`ChannelDatabase` instance
    in a running DIA environment, created by the core system.  It
    implements
    :class:`~channels.channel_database_interface.ChannelDatabaseInterface`,
    of which there may be additional instances to provide access to
    loggers configured in the system.

    The core :class:`ChannelDatabase` object in the system is the
    latest published state of the channels.
    """

    def __init__(self, core_services):
        self.__channels = { }

        self.__core = core_services

        self.__logging_manager = LoggingManager(core_services)
        self.__channel_publisher = ChannelPublisher(core_services)
        self.__channel_publisher.set_logging_manager(self.__logging_manager)


    # ChannelDatabaseInterface functions
    def channel_add(self, channel_name, channel_source):
        if self.channel_exists(channel_name):
            raise ChannelAlreadyExists, "channel '%s' already exists" % \
                (channel_name)

        channel = Channel(name=channel_name, channel_source=channel_source)
        self.__channels[channel_name] = channel
        
        self.__channel_publisher.new_channel(channel)
        
        return channel

    def channel_remove(self, channel_name):
        chan = self.channel_get(channel_name)
        if chan:
            # Remove the entry from the channel publisher database.
            # Then remove entry from our internal database.
            # NOTE: This does NOT delete the object itself!
            try:
                self.__channel_publisher.remove_channel(chan)
            except:
                pass
            del self.__channels[channel_name]
        return chan

    def channel_get(self, channel_name):
        if not self.channel_exists(channel_name):
            raise ChannelDoesNotExist, "channel '%s' does not exist" % \
                (channel_name)

        return self.__channels[channel_name]

    def channel_list(self):
        '''
        Returns the name of every channel in the database.
        '''
        return [cn for cn in copy(self.__channels)]

    def channel_exists(self, name):
        return name in self.__channels

    ## Additional accessor functions:
    def channel_publisher_get(self):
        """
        Returns the
        :class:`~channels.channel_publisher.ChannelPublisher` for the
        system

        """
        return self.__channel_publisher

    def channel_logging_manager_get(self):
        """
        Returns the
        :class:`~channels.logging.logging_manager.LoggingManager` for
        the system

        """
        return self.__logging_manager

    # We are not interacting with a logger in this interface, so leave
    # those functions un-implemented
    
# internal functions & classes
