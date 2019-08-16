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
Common helper functions which print and format channels.
"""

import time
import digitime
from channels.channel import PERM_GET, OPT_DONOTDUMPDATA
from core.tracing import get_tracer

_tracer = get_tracer("format_channels")

def format_channel_table_generic(obj, channel_list_method,
                                    channel_access_check_method,
                                    sample_access_method,
                                    channel_startswith = "",
                                    use_local_time_offset = False):
    """
    Return an entire
    :class:`~channels.channel_database.ChannelDatabase` as a formatted
    string.

    Accepts a :class:`~channels.channel_database.ChannelDatabase`
    (`obj`), three methods which provide channel functionality
    (`channel_list_method`, `channel_access_check_method`,
    `sample_access_method`), an optional filter string
    (`channel_startswith`), and a optional boolean (default = False)
    which allows for the use of a local time offset
    (`use_local_time_offset`).

    Example output::

       Device instance: template

       Channel                  Value              Unit     Timestamp
       ------------------------ ------------------ -------- -------------------
       adder_reg1               0.0                         2010-09-17 15:21:13
       adder_reg2               0.0                         2010-09-17 15:21:13
       adder_total              0.0                         2010-09-17 15:21:13
       counter                  11661                       2010-09-17 18:35:52
       counter_reset            (N/A)
       global_reset             (N/A)

    """
    result = ""
    try:
        channel_list = channel_list_method(obj)
    except Exception, e:
                _tracer.error("Exception encountered while getting channel list: %s",
            repr(e))

    if len(channel_startswith):
        channel_list = filter(lambda chan: chan.startswith(channel_startswith),
                                channel_list)
    channel_list.sort()

    headings = (("Channel", 24), ("Value", 18), ("Unit", 8), ("Timestamp", 19))

    # Table header
    header_top = "  "
    header_bot = "  "
    field_fmt  = "  "
    for field in headings:
        header_top += ' '
        header_top += field[0].ljust(field[1])[:field[1]]
        header_bot += ' '
        header_bot += '-' * field[1]
        field_fmt += ' '
        field_fmt += '%-' + str(field[1]) + '.' + str(field[1]) + 's'

    header_top += '\r\n'
    header_bot += '\r\n'
    field_fmt += '\r\n'

    # We need to split the channels up according to their device
    # so we create a dictionary indexed by device name, with each
    # value being a list of channels
    table = dict()
    for entry in channel_list:
        device, channel_name = entry.split('.')

        if not table.has_key(device):
            table[device] = list()

        try:
            if not channel_access_check_method(obj, entry):
                raise Exception
            sample = sample_access_method(obj, entry)
            table[device].append((channel_name, sample.value,
                sample.unit,
                iso_date(sample.timestamp, use_local_time_offset),))
        except Exception, e:
            table[device].append((channel_name, "(N/A)", "", "",))


    sorted_table = list()
    for key in table.keys():
        sorted_table.append((key, table[key]))
        sorted_table.sort(key = lambda x: x[0])

    if len(sorted_table):
        # Now that we've built our map, we can print
        for entry in sorted_table:
            device, channels = entry

            result += "\r\nDevice instance: %-40.40s\r\n\r\n" % (device,)
            result += header_top
            result += header_bot

            for entry in channels:
                result += field_fmt % entry

            result += "\r\n"
    else:
        result += "\r\n\tNone channel starts with %s.\r\n" % channel_startswith

    return result


def dump_channel_db_as_text(cdb, startswith=""):
    """
    Perform a formatted text dump of the given
    :class:`~channels.channel_database.ChannelDatabase`.

    Accepts an optional `startswith` string to filter the list of
    channels.

    Returns the channel database as a formatted string.

    """
    # method which retrieves the channel list from the provided database
    channel_list_method = lambda cdb: cdb.channel_list()

    # method which checks if a channel is accessible
    channel_access_check_method = lambda cdb, cn: (
                    (cdb.channel_get(cn).perm_mask() & PERM_GET) and not
                    (cdb.channel_get(cn).options_mask() & OPT_DONOTDUMPDATA))

    # method which returns the value of a given channel in the database
    sample_access_method = lambda cdb, cn: cdb.channel_get(cn).get()

    # calls the database formatting function
    result = format_channel_table_generic(cdb, channel_list_method,
                                            channel_access_check_method,
                                            sample_access_method,
                                            startswith)
    # return the formatted text dump of the channel database from
    # format_channel_table_generic
    return result


def dump_channel_dict_as_text(a_dict, startswith=""):
    """
    Perform a text dump of a given channel dictionary.

    Assumes channel:value pairs.

    Functions similarly to :meth:`dump_channel_db_as_text`, but the
    dictionary aspect makes the lambda methods quite a bit simpler.
    e.g.  channel_access_check_method can always return `True`, since
    we're working with a dict.

    """
    channel_list_method = lambda d: d.keys()
    channel_access_check_method = lambda d, cn: True
    sample_access_method = lambda d, cn: d[cn]

    result = format_channel_table_generic(a_dict, channel_list_method,
                                            channel_access_check_method,
                                            sample_access_method,
                                            startswith)

    return result


def iso_date(t=None, use_local_time_offset=False, real_iso=False):
    """
    Return an ISO-formatted date string from a provided date/time object.

    Arguments:

    * `t` - The time object to use.  Defaults to the current time.
    * `use_local_time_offset` - Boolean value, which will adjust
        the ISO date by the local offset if set to `True`. Defaults
        to `False`.
    * real_iso - Set to True for real iso 8601 format. (False by default
        for backwards compatibility.)

    """
    ret_str = digitime.form_iso_date_str(t=t,
                                         local_time=use_local_time_offset)
    if not real_iso:
        _tracer.debug('Using a deprecated, non-iso 8601 time format.')
        # remove the 'T' and possibly the 'Z'
        ret_str = ret_str.replace('T', ' ')
        ret_str = ret_str.replace('Z', '')

    return ret_str
