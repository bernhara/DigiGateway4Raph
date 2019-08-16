############################################################################
#                                                                          #
# Copyright (c)2008, Digi International (Digi). All Rights Reserved.	   #
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

"""\
Simple logger that prints a message when new events are received.

loggers:
  - name: myLogger
    driver: channels.logging.simple_logger.simple_logger:SimpleLogger
"""

# imports
from settings.settings_base import SettingsBase

from channels.logging.logger_base import LoggerBase
from channels.logging.logging_events import \
    LoggingEventNewSample, LoggingEventChannelNew, LoggingEventChannelRemove
from channels.logging.simple_logger.simple_logger_channel_dbi import \
    SimpleLoggerChannelDBI


class SimpleLogger(LoggerBase):

    def __init__(self, name, core_services):
        self.__name = name
        self.__core_services = core_services

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        settings_list = []

        LoggerBase.__init__(self, name=name, settings_list=settings_list)

    def log_event(self, logging_event):
        """
        Called when we should log a new event

        Keyword arguments:
        event -- the new event
        """
        if isinstance(logging_event, LoggingEventNewSample):
            self.__tracer.info("new sample %s)",
                repr(logging_event.channel.get()))
        elif isinstance(logging_event, LoggingEventChannelNew):
            self.__tracer.info("new channel '%s'",
                logging_event.channel.name())
        elif isinstance(logging_event, LoggingEventChannelRemove):
            self.__tracer.info("remove channel '%s'",
                logging_event.channel.name())
        else:
            self.__tracer.warning("unknown log event '%s'",
                logging_event.__class__.__name__)

    def channel_database_get(self):
        return SimpleLoggerChannelDBI()

    def apply_settings(self):
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            self.__tracer.error("settings rejected/not found: %s/%s",
                                rejected, not_found)
        SettingsBase.commit_settings(self, accepted)
        return (accepted, rejected, not_found)

    def start(self):
        return True

    def stop(self):
        return True
