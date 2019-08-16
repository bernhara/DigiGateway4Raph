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

"""
Common helper functions which print and format logging events.
"""
import sys
import time

from channels.logging.logging_events import \
    LoggingEventNewSample, LoggingEventChannelNew, LoggingEventChannelRemove, \
    LoggingEventMeta
from channels.channel import PERM_GET
from common.helpers.format_channels import iso_date

def format_logging_events_iterator(log_event_iterator):
    """
    Format a plain ASCII table, given a logging event iterator.
    
    Such iterators can be seen in channels/channel_database_interface.py.
    
    In order to conserve memory, this formatter operates as an iterator and
    returns a single line of text at a time.  
    """
    
    log_event_type_map = { 
        LoggingEventNewSample: "Sample",
        LoggingEventChannelNew: "Channel+",
        LoggingEventChannelRemove: "Channel-",
        LoggingEventMeta: "Meta",
                         }
    headings = ( 
        ("Record #", len(repr(sys.maxint))),
        ("Type", max(map(lambda s: len(s), log_event_type_map.values()))),
        ("Channel Name", 24),
        ("Sample Val.", len(repr(sys.maxint))),
        ("Timestamp", 19),
        )

    # Table header
    header_top = ""
    header_bot = ""
    field_fmt  = ""
    for field in headings:
        header_top += ' '
        header_top += field[0].ljust(field[1])[:field[1]]
        header_bot += ' '
        header_bot += '-' * field[1]
        field_fmt += ' '
        field_fmt += '%-' + str(field[1]) + '.' + str(field[1]) + 's'

    yield header_top
    yield header_bot
    
    for log_event in log_event_iterator:
        line = ""
        if log_event.channel is None:
            if isinstance(log_event, LoggingEventMeta):
                line = field_fmt % (
                        "%d" % log_event.record,
                        log_event_type_map[log_event.__class__],
                        log_event.description,
                        "N/A",
                        "N/A")
            else:
                # unsupported LoggingEvent
                line = field_fmt % (
                        "-1",
                        "Unknown",
                        "N/A",
                        "Unknown event type: %s" % log_event.__class__.__name__,
                        "N/A")
        elif log_event.channel.perm_mask() & PERM_GET:
            line = field_fmt % (
                        "%d" % log_event.record,
                        log_event_type_map[log_event.__class__],
                        log_event.channel.name(),
                        repr(log_event.channel.get().value),
                        iso_date(log_event.channel.get().timestamp))
        else:
            line = field_fmt % (
                        "%d" % log_event.record,
                        log_event_type_map[log_event.__class__],
                        log_event.channel.name(),
                        "(N/A)",
                        iso_date(log_event.channel.get().timestamp))
        yield line

