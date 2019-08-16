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
Helper function to parse a time duration.
"""

import types
# from core.tracing import get_tracer

# _tracer = get_tracer("parse_duration")


def parse_time_duration(src, in_type='ms', out_type='ms'):
    """
    Parse a given time duration into a specified unit of measure.

    Supports integer, float, and string input. String input will be split into
    a list and parsed if necessary.

    Arguments:
        src - The time duration to be parsed.
        in_type - Units of measure of the input duration. Defaults to 'ms'
        out_type - Units of measure of the output duration. Defaults to 'ms'.

    Returns an integer value, measured in "out_type" (for example as
    2 seconds).
    """
    in_type = in_type.lower()
    out_type = out_type.lower()
    if isinstance(src, types.IntType) or isinstance(src, types.FloatType):
        # _tracer.info('is number, so just return SAME type')
        return adjust_time_duration(src, in_type, out_type)

    # at this point, we assume src is a string, so it must be split into its
    # components (e.g. '123', '123 hr', etc)
    inp_list = src.split(' ')

    if(len(inp_list) == 1):
        num = adjust_time_duration(parse_value(inp_list[0]), in_type, out_type)

    else:
        num = 0
        # assume 2nd value is the modifier, and that we have an even number of
        # elements
        while(len(inp_list) > 1):
            num += adjust_time_duration(parse_value(inp_list[0]),
                                      inp_list[1], out_type)
            inp_list = inp_list[2:]
    # return the parsed time duration 'num' here
    return num


def parse_value(src):
    """Return the value of a given string as an int or float."""
    num = None
    if (src.find('.') >= 0):
        # _tracer.info("treat as float, handle '0.2', '.2', '2.'")
        num = float(eval(src))
    else:
        # _tracer.info("treat as int, handle '12', '012', '0x12'")
        try:
            num = int(src, 10)  # the (x,10) over-rides OCTAL support!
        except Exception:
            num = int(eval(src))  # handles '0x123' or '60*60'
    # 'n' should not be None at this point - should be int/float
    # or an exception was thrown
    return num


def duration_string_to_msec(st, bThrow=True):
    """
    Return the number of milliseconds in a given unit of time.

    Accepts an argument string 'st', which should be be a valid unit of time,
    formatted as follows: ['ms','sec','min','hr','day'].

    Defaults to 1 ms.
    """
    if not st or (len(st) < 1):
        # if no duration string is provided, assume msec (i.e. 1)
        return 1
    # only check if we seem to have something
    st = st.lower() + '   '
    st = st[:3]  # first 3 char only
    if(st == 'sec'):
        # sec, secs, second, seconds
        return 1000
    elif(st == 'min'):
        # min, mins, minute, minutes
        return 60000  # (60 * 1000)
    elif(st in ('hr ', 'hrs', 'hou')):
        # hr, hrs, hour, hours
        return 3600000  # (60 * 60 * 1000)
    elif(st in 'day'):
        # day, days
        return 86400000  # (24 * 60 * 60 * 1000)
    elif(st in ('mse', 'ms ', 'mil')):
        # ms, msec, msecs, millis...
        return 1
    else:  # assume msec, default to 1
        if not bThrow:
        # _tracer.error('ERROR: duration_string_to_msec(%s) is unknown', st)
            return None
        else:
            raise Exception('duration_string_to_msec() unknown string value "'
                           + str(st) + '"')


def adjust_time_duration(num, in_type, out_type):
    """
    Adjust a time duration from 'in_type' type to 'out_type' type.

    Supported types are ['ms','sec','min','hr','day'], with error/default 
    being treated as 'msec'
    """
    # _tracer('convert %f from %s to %s'n , in_type, out_type)
    if in_type == out_type:
        return num

    # convert num to msec
    in_n = duration_string_to_msec(in_type)
    out_n = duration_string_to_msec(out_type)
    # print "num=%s in=%s ont=%s" % (num, in_n, out_n)
    return (num * in_n) / out_n
