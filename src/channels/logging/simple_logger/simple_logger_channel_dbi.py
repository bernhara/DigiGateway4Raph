############################################################################
#                                                                          #
# Copyright (c)2008, Digi International (Digi). All Rights Reserved.       #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice, and the following   #
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

"""
This code is provided as an example as to what needs to be implemented
should you choose to implement your own logger.

There is no working functionality in this module.
"""

from channels.channel_database_interface import \
    ChannelDatabaseInterface, ChannelAlreadyExists, ChannelDoesNotExist

class SimpleLoggerChannelDBI(ChannelDatabaseInterface):
    """
    Implements a simple
    :class:`~channels.channel_database_interface.ChannelDatabaseInterface`
    for the
    :class:`~channels.logging.simple_logger.simple_logger.SimpleLogger`.
    
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.

    """

    def __init__(self):
        pass

    def channel_add(self, channel_name, channel_source):
        raise NotImplementedError, "Not implemented"

    def channel_get(self, channel_name):
        if not self.channel_exists:
            raise ChannelDoesNotExist, "channel '%s' does not exist" % \
            (channel_name)

        return self.__channels[channel_name]

    def channel_list(self):
        return []

    def channel_exists(self, name):
        return False

    ## Functions Not implemented:
    def log_next(self):
        raise NotImplementedError, "Not implemented"

    def log_prev(self):
        raise NotImplementedError, "Not implemented"

    def log_rewind(self):
        raise NotImplementedError, "Not implemented"

    def log_seek(self, timestamp):
        pass

    def log_time(self):
        raise NotImplementedError, "Not implemented"

    def log_event_iterator(self, timestamp_from, timestamp_to):
        return []
