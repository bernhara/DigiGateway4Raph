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
from channels.channel_database import ChannelDatabase
from settings.settings_base import SettingsBase, Setting

# constants

# interface functions

# classes


class ChannelManager(object):
    """
    The channel manager provides access to a number of channel related
    objects in the system:

    * The :class:`~channels.channel_database.ChannelDatabase`, through which
      the current :class:`~channels.channel.Channel` objects may be accessed.
    * The :class:`~channels.channel_publisher.ChannelPublisher`, which
      enables components of the system to register to receive channel
      updates.
    * The :class:`~channels.logging.logging_manager.LoggingManager`, which
      allows access to  :class:`loggers
      <channels.logging.logger_base.LoggerBase>`. and the historical
      information that they can provide.

    It also provides shortcuts for the most common operations on these objects.

    """

    def __init__(self, core_services):
        self.__core = core_services
        self.__core.set_service("channel_manager", self)

        self.__channel_database = ChannelDatabase(self.__core)

    def channel_database_get(self):
        """Return a reference to the
        :class:`~channels.channel_database.ChannelDatabase`.

        """
        return self.__channel_database

    def channel_publisher_get(self):
        """
        Return a reference to the
        :class:`~channels.channel_publisher.ChannelPublisher`.

        """
        return self.__channel_database.channel_publisher_get()

    def channel_logging_manager_get(self):
        """Return a reference to the
        :class:`~channels.logging.logging_manager.LoggingManager`.

        """
        return self.__channel_database.channel_logging_manager_get()

    def channel_logger_list(self):
        """Return a list of channel
        :class:`loggers <channels.logging.logger_base.LoggerBase>`

        """
        logging_manager = self.__channel_database.channel_logging_manager_get()
        return logging_manager.instance_list()

    def channel_logger_get(self, logger_name):
        """Retrieve a specific
        :class:`logger <channels.logging.logger_base.LoggerBase>`
        instance

        Parameter:

        * `logger_name`: Name of the logger

        """
        logging_manager = self.__channel_database.channel_logging_manager_get()
        return logging_manager.instance_get(logger_name)

    def channel_logger_exists(self, logger_name):
        """Returns whether the specified
        :class:`logger <channels.logging.logger_base.LoggerBase>`
        exists

        Parameter:

        * `logger_name`: Name of the logger

        """
        logging_manager = self.__channel_database.channel_logging_manager_get()
        return logging_manager.instance_exists(logger_name)

# internal functions & classes
