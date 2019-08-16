############################################################################
#                                                                          #
# Copyright (c)2012, Digi International (Digi). All Rights Reserved.       #
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

'''
digitime module

** This is a temporary, partial implementation until all platforms
   implement the module natively.  **

This is an *incomplete* implementation. Specifically:
  * msec() is not implemented
  * proc_clock() is not implemented
  * sleep() is just a pass-through to the underlying architecture, and
    does not handle potential rounding in a consistent manner

This provides a platform-independent time module for Dia.
'''

try:
    from digitime import time, asctime, gmtime, localtime, strftime, \
        sleep, real_clock, proc_clock, msec, form_iso_date_str, \
        parse_iso_date_str
except ImportError:
    # sigh... not implemented yet...

    class UnknownPlatformException(Exception):
        '''
        Raised when a method is called with no implementation, because
        the platform, and therefore the implementation, is not known.
        '''
        pass

    class UnsupportedPlatformException(Exception):
        '''
        Raised when a method is called with no implementation,
        because this module is a partially implemented shim until
        native modules spring magically into existence.
        '''
        pass


    def msec():
        ''' not supported '''
        raise UnsupportedPlatformException('msec() is not implemented!')


    def proc_clock():
        ''' not supported '''
        raise UnsupportedPlatformException('proc_clock() is not implemented!')

    import sys
    import time as sys_time
    from datetime import date

    # pass through sleep
    sleep = sys_time.sleep

    # pass through a few standard methods
    asctime = sys_time.asctime
    gmtime = sys_time.gmtime
    localtime = sys_time.localtime
    strftime = sys_time.strftime

    _CACHED_OFFSET = None


    def _local_time_offset(t):
        '''
        HACK: until we have timezone data in NDS...

        Return offset of local zone from GMT as seconds,
        either at present or at time t.
        '''
        # python2.3 localtime() can't take None

        # ConnectPort X4s don't have an RTC, so we need to check for that
        # functionality first.
        global _CACHED_OFFSET

        if 'timezone' in dir(time):
            if sys_time.localtime(t).tm_isdst > 0 and sys_time.daylight:
                return -sys_time.altzone
            else:
                return -sys_time.timezone
        else:
            if _CACHED_OFFSET is not None:
                return _CACHED_OFFSET
            # We are going to fake it with localtime and gmtime support,
            # which even the X4 has.
            utc = sys_time.gmtime()
            lcl = sys_time.localtime()

            # account for
            day_shift = lcl[7] - utc[7]

            # crafy day shifts (can't use mod unless we want to check
            # for leap year...)
            if day_shift < -1:
                day_shift = 1
            elif day_shift > 1:
                day_shift = -1
            hrs = lcl[3] - utc[3] + 24 * day_shift
            mins = lcl[4] - utc[4]
            _CACHED_OFFSET = (hrs * 60 + mins) * 60

            return _CACHED_OFFSET

    def parse_iso_date_str(timestr):
        '''
        Returns the UTC value for the given time string.

        This expects the *exact* format given by form_iso_date_str.
        '''
        # is this localtime?
        if timestr[-1] == 'Z':
            sec_offset = 0
            timestr = timestr[:-1]
        else:
            # last 6 must be formatted characters
            offset = timestr[-6:]
            timestr = timestr[:-6]
            hrs = int(offset[1:3])
            mins = int(offset[4:])
            sec_offset = (hrs * 60 + mins) * 60
            if offset[0] == '-':
                sec_offset *= -1
            elif offset[0] == '+':
                pass
            else:
                raise ValueError('Bad symbol for first character of ' \
                                 'localtime offset: %s' % (str(offset[0])))

        # The code below would work, but NDS has a strptime bug...
        # ----
        try:
            tuple_time = sys_time.strptime(timestr, '%Y-%m-%dT%H:%M:%S')
        except ImportError:
            # start workaround
            day_time = timestr.split('T')
            if len(day_time) != 2:
                raise ValueError('Bad time string %s' % timestr)
            try:
                ymd = map(int, day_time[0].split('-'))
                hms = map(int, day_time[1].split(':'))
            except:
                raise ValueError('Bad time string %s' % timestr)
            if len(ymd) != 3 or len(hms) != 3:
                raise ValueError('Bad time string %s' % timestr)

            julian = date(*ymd).toordinal() - \
                     date(ymd[0], 1, 1).toordinal() + 1
            weekday = date(*ymd).weekday()
            tuple_time = sys_time.struct_time(ymd + hms + [weekday, julian, 0])
            # end workaround

        # since we don't have calendar.timegm...
        # mktime removes our own offset, so we need to re-add it, then
        # remove the offset given in the timestr
        lcl_time = sys_time.mktime(tuple_time)
        return lcl_time + _local_time_offset(lcl_time) - sec_offset


    def form_iso_date_str(t=None, local_time=False):
        '''
        Return an ISO-formatted date string from a provided date/time object.

        Arguments:

        * `t` - The time object to use.  Defaults to the current time.
        * `use_local_time_offset` - Boolean value, which will adjust
            the ISO date by the local offset if set to `True`. Defaults
            to `False`.

        '''
        if t is None:
            t = sys_time.time()
        lto = None
        if local_time:
            lto = _local_time_offset(t)

        if lto is None:
            time_str = sys_time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                         sys_time.gmtime(t))
        else:
            hours = lto // (60 * 60)
            mins = (lto % (60 * 60)) // 60
            time_str = sys_time.strftime("%Y-%m-%dT%H:%M:%S",
                                         sys_time.localtime(t)) + \
                "%+03d:%02d" % (hours, mins)

        return time_str

    if sys.platform == 'digiconnect':
        real_clock = sys_time.clock
        time = sys_time.time

    elif sys.platform == 'linux2':
        time = sys_time.time

        try:
            # if we have ULC uptime module...
            import uptime
            real_clock = uptime.uptime
        except ImportError:

            def real_clock():
                '''
                Grab uptime from proc. Monotonic increasing
                and it marches along in real seconds.
                '''
                f = open('/proc/uptime')
                ret = float(f.read().split()[0])
                f.close()
                return ret

    elif sys.platform == 'win32':
        real_clock = sys_time.clock
        time = sys_time.time

    else:
        time = sys_time.time
        real_clock = sys_time.clock
