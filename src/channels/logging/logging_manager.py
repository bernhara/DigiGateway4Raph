############################################################################
#                                                                          #
# Copyright (c)2008, Digi International (Digi). All Rights Reserved.       #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,	and the following  #
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
import sys, traceback

from common.abstract_service_manager import AbstractServiceManager
from channels.logging.logging_events import LoggingEventBase

# classes
class LoggingManager(AbstractServiceManager):
    """
    The LoggingManager allows for the dynamic loading of
    :class:`logger <channels.logging.logger_base.LoggerBase>` as well
    as the ability to retrieve an instance of a :class:`logger
    <channels.logging.logger_base.LoggerBase>` by name.

    The LoggingManager also provides an interface to query a logger for
    its configuration parameters, as well the interface to start and stop a
    given logger instance.

    The LoggingManager is also responsible for distributing new sample
    notifications from the
    :class:`~channels.channel_publisher.ChannelPublisher` to
    :class:`logger <channels.logging.logger_base.LoggerBase>`
    instances.

    """

    def __init__(self, core_services):
        self.__core = core_services
        self.__core.set_service("logging_manager", self)

        from core.tracing import get_tracer
        self.__tracer = get_tracer('LoggingManager')

        # Initialize our base class:
        AbstractServiceManager.__init__(self, core_services, ('loggers',))

    def dispatch_logging_event(self, logging_event):
        """
        Send `logging_event` to all configured loggers.

        Uses the instance management code from parent class
        :class:`~common.abstract_service_manager.AbstractServiceManager`
        to find and send the logging event passed in as an argument to
        each logger configured in the settings file.  Valid logging
        events are defined in module
        :mod:`~channels.logging.logging_events`.

        In normal operation, this method will be called automatically
        in the system by the
        :class:`~channels.channel_publisher.ChannelPublisher`, and it
        should not be necessary to use it directly.

        """
        if not isinstance(logging_event, LoggingEventBase):
            raise TypeError, "LoggingManager: logging_event TypeError"

        for name in AbstractServiceManager.instance_list(self):
            logger_instance = AbstractServiceManager.instance_get(self, name)
            try:
                logger_instance.log_event(logging_event)
            except Exception, e:
                self.__tracer.error("exception during log_event dispatch: %s",
                                    str(e))
                self.__tracer.debug(traceback.format_exc())

# internal functions & classes
