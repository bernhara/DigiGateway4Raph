############################################################################
#                                                                          #
# Copyright (c)2008-2011, Digi International (Digi). All Rights Reserved.  #
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
Common helper functions for handling sleep/wake tasks

"""

import time

# the valid 'period' in minutes for secs_until_next_minute_period()
PERMITTED_MINUTE_VALUES = (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)
PERMITTED_VALUES = PERMITTED_MINUTE_VALUES

# the valid 'period' in seconds for secs_until_next_second_period()
PERMITTED_SECOND_VALUES = (5, 6, 10, 12, 15, 20, 30, 60)

# the valid 'period' in hours for secs_until_next_hour_period()
PERMITTED_HOUR_VALUES = (1, 2, 3, 4, 6, 8, 12, 24)

def secs_until_next_minute_period(period, now_tup=None):
    """
    Allows a task to sleep/wake on clean time periods.

    For example, if the sleep period were set to 5 (minutes),
    the device could be made to wake at HH:05:00, HH:10:00, etc...
    This method does not provide the sleep functionality, it
    only returns the number of seconds remaining in the current
    interval.

    Note that 'period' must be a factor of 60, so the available periods are:
    (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)

    'Now_tup' is an optional time tuple, as would be returned by time.gmtime()
    or time.localtime().  If None is passed in, then localtime() is used.
    """

    if period > 60:
        # then assume is seconds, convert to minutes
        # note: this is ambigous at 60sec/60min
        if (period % 60) != 0:
            raise ValueError("Minute period of %s is not a factor of 60" % period)
        period /= 60.0

    if period not in PERMITTED_MINUTE_VALUES:
        # then is not a factor of 60
        raise ValueError("Minute period of %s is not a factor of 60" % period)

    if now_tup is None:
        # default to local time if none passed in
        now_tup = time.localtime()

    # start with seconds until next minute, so want tm_sec = 0
    sec_til = (60 - now_tup.tm_sec)

    if(period > 1):
        # then calc the adder for the minutes adjust
        sec_til += ((period - (now_tup.tm_min % period) - 1) * 60)

    # else, until next minute if fine, we are done
    return sec_til

def secs_until_next_second_period(period, now_tup=None):
    """
    Allows a task to sleep/wake on clean time periods.

    For example, if the sleep period were set to 5 (seconds),
    the device could be made to wake at HH:MM:00, HH:MM:05, etc...
    This method does not provide the sleep functionality, it
    only returns the number of seconds remaining in the current
    interval.

    Note that 'period' must be a factor of 60 *PLUS* at least 5 seconds,
    so the available periods are: (5, 6, 10, 12, 15, 20, 30, 60) The minimum
    time of 5 seconds is somewhat arbitrary, yet given time limits to seconds
    resolution, trying to tighly since periods to 'msec' resolution is
    unreasonable and bound to fail to perform.

    'Now_tup' is an optional time tuple, as would be returned by time.gmtime()
    or time.localtime().  If None is passed in, then localtime() is used. To use
    UTC/gmtime(), generate the tuple externally and pass in.
    """

    if period < 5:
        # then period is unreasonably small
        raise ValueError("Seconds period of %s is smaller than min 5 sec" % period)

    if period not in PERMITTED_SECOND_VALUES:
        # then is not a factor of 60
        raise ValueError("Seconds period of %s is not a factor of 60" % period)

    if now_tup is None:
        # default to local time if none passed in
        now_tup = time.localtime()

    # start with seconds until next minute, so want tm_sec = 0
    sec_target = ((now_tup.tm_sec / period) + 1) * period
    sec_til = sec_target - now_tup.tm_sec

    return sec_til

def secs_until_next_hour_period(period, now_tup=None):
    """
    Allows a task to sleep/wake on clean time periods.

    For example, if the sleep period were set to 3 (hours),
    the device could be made to wake at 00:00:00, 03:00:00, etc...
    This method does not provide the sleep functionality, it
    only returns the number of seconds remaining in the current interval.

    Note that 'period' must be a factor of 24, so the available periods are:
    (1, 2, 3, 4, 6, 8, 12, 24)

    'Now_tup' is an optional time tuple, as would be returned by time.gmtime()
    or time.localtime().  If None is passed in, then localtime() is used. To use
    UTC/gmtime(), generate the tuple externally and pass in.
    """

    if period >= 3600:
        # then assume is seconds, convert to hours
        if (period % 3600) != 0:
            raise ValueError("Hours period of %s is not a factor of 24" % period)
        period /= 3600

    if period not in PERMITTED_HOUR_VALUES:
        # then is not a factor of 60
        raise ValueError("Hours period of %s is not a factor of 24" % period)

    if now_tup is None:
        # default to local time if none passed in
        now_tup = time.localtime()

    # zero seconds until next minute (gains 1 minute)
    sec_til = (60 - now_tup.tm_sec)

    # zero minutes until next hour (& take off the minute gained above)
    #  plus gains 1 hour
    sec_til += (59 - now_tup.tm_min) * 60

    # find the next period
    hr_target = ((now_tup.tm_hour / period) + 1) * period
    sec_til += ((hr_target - now_tup.tm_hour) * 3600) - 3600

    return sec_til
