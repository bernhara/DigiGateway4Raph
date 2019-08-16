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
Common helper functions for time-sync'ng events. For example, to upload
data every hour, on the hour.
"""

import time
import types
import random
import traceback

from parse_duration import parse_time_duration

from sleep_aids import *
# secs_until_next_second_period(), secs_until_next_minute_period(), secs_until_next_hour_period()
# PERMITTED_SECOND_VALUES, PERMITTED_MINUTE_VALUES, PERMITTED_HOUR_VALUES

class CleanPeriod(object):
    """
    Class to simplify handling clean time periods, like hourly actions
    """

    MODE_RAW = 0
    MODE_SECS = 1
    MODE_MINS = 2
    MODE_HRS = 3
    MODE_NAME = ('raw', 'sec', 'min', 'hr')

    def __init__(self, period=None, min_skew=None, max_skew=None):

        self._period_source = period
        self._period = 0
        self._mode = 0
        self._min_skew = None
        self._max_skew = None

        if period is None:
            # assume config is done later
            return

        self.set_period(period)
        self.set_skew(min_skew, max_skew)
        return
        
    def __repr__(self):
        st = "CleanPeriod(%d %s)" % (self._period, self.MODE_NAME[self._mode])
        if self._min_skew is None:
            st += " without skew"
        else:
            if self._max_skew is None:
                st += " fixed %d sec skew" % self._min_skew
            else:
                st += " random skew between %d and %d secs" % (self._min_skew+1, self._max_skew)
        return st

    def force_raw(self, period):
        """
        Force raw, so disable clean adjustments
        """
        self._mode = self.MODE_RAW
        self._period = period
        return
        
    def set_period(self, period):

        self._period_source = period
        self._period = parse_time_duration(period, in_type='sec', out_type='sec')

        # print "Period; Source(%s) seconds(%d)" % (self._period_source, self._period)

        # determine period mode
        if self._period <= 60:
            # then should be 1 to 60 seconds

            # a dummy trial to trigger correct exception for bad values
            # self._period = seconds already
            try:
                x = secs_until_next_second_period(self._period)
                self._mode = self.MODE_SECS
            except:
                traceback.print_exc()
                self._mode = self.MODE_RAW
                # for RAW, self._period remains seconds

        elif self._period <= 3600:
            # then should be 1 to 60 minutes

            # a dummy trial to trigger correct exception for bad values
            try:
                x = self._period / 60 # make into minutes
                secs_until_next_minute_period(x)
                self._mode = self.MODE_MINS
                self._period = x
            except:
                traceback.print_exc()
                self._mode = self.MODE_RAW
                # for RAW, self._period remains seconds

        elif self._period <= 86400:
            # then should be 1 to 24 hours

            # a dummy trial to trigger correct exception for bad values
            try:
                x = self._period / 3600 # make into hours
                secs_until_next_hour_period(x)
                self._mode = self.MODE_HRS
                self._period = x
            except:
                traceback.print_exc()
                self._mode = self.MODE_RAW
                # for RAW, self._period remains seconds

        else:
            raise ValueError("clean_period(%s) is out of range (must be <= 24 hours)" % period)

        # print "Period mode:(%s)" % (self._mode)

        return

    def set_skew(self, min_skew, max_skew=None):

        # handle the skews
        if min_skew is None:
            # print "No Skew"
            self._min_skew = None
            self._max_skew = None
        else:
            self._min_skew = parse_time_duration(min_skew, in_type='sec', out_type='sec')
            # print "Min Skew is %d seconds" % self._min_skew

            if max_skew is None:
                # print "Min Skew is fixed, no random range"
                self._max_skew = None

            else:
                self._max_skew = parse_time_duration(max_skew, in_type='sec', out_type='sec')
                # print "Max Skew is %d seconds" % self._max_skew

                if (self._max_skew == self._min_skew) or (self._max_skew == 0):
                    # then disable the range, just use self._min_skew
                    self._max_skew = None

                elif self._max_skew < self._min_skew:
                    # then this is an error
                    raise ValueError("clean_period() max skew cannot be less than min skew)")
                    
                else: # we have a range for random
                    self._min_skew -= 1 # decrement, as random.randint(min,max) doesn't include min

                # NOTE: we don't enforce rules like skew < period. A user may have
                # a clean period of 5 minutes, with a skew of 2-9 minutes. This means
                # a period might be 5+9 (or 14) minutes from 'now'.

        return

    def import_config(self, dct):

        if isinstance(dct, types.StringType):
            # in case passed in as string
            dct = eval(dct)

        x = dct.get('period', None)
        if x is not None:
            self.set_period(x)

        x = dct.get('min_skew', None)
        if x is not None:
            self.set_skew(x, dct.get('max_skew', None))

        return

        
    def get_period_as_seconds(self):
    
        if not self._period:
            # then period isn't initialized yet
            return 0
            
        elif self._mode == self.MODE_MINS:
            return self._period * 60
            
        elif self._mode == self.MODE_HRS:
            return self._period * 3600
            
        elif self._mode == self.MODE_SECS:
            return self._period
            
        elif self._mode == self.MODE_RAW:
            return self._period
            
        else:
            raise ValueError("clean_period().get_period_as_seconds() bad mode")
        
    
    def get_next_period_seconds(self, now_tup=None):
    
        if self._period == 0 or self._period is None:
            return 0

        if self._mode == self.MODE_RAW:
            # just return the period
            return self._period
            
        ## process the 'now' time, make into time.struct_time() tuple
        if now_tup is None:
            # default to local time if none passed in
            now_tup = time.localtime()

        elif not isinstance(now_tup, time.struct_time):
            # assume is int/float time, so make tuple
            now_tup = time.localtime(now_tup)

        ## calc the base delay in seconds
        if self._mode == self.MODE_SECS:
            secs_until = secs_until_next_second_period(self._period, now_tup)
            # print 'clean_period %s secs, delay is %d seconds' % \
            #       (self._period, secs_until)
            
        elif self._mode == self.MODE_MINS:
            secs_until = secs_until_next_minute_period(self._period, now_tup)
            # print 'clean_period %s mins, delay is %d seconds' % \
            #       (self._period, secs_until)
            
        elif self._mode == self.MODE_HRS:
            secs_until = secs_until_next_hour_period(self._period, now_tup)
            # print 'clean_period %s hrs, delay is %d seconds' % \
            #       (self._period, secs_until)
            
        else:
            raise ValueError("clean_period().get_period_as_seconds() bad mode")
        
        ## add any skew
        if self._min_skew is not None:
            if self._max_skew is None:
                # then Min Skew is a fixed constant
                skew = self._min_skew
                # print 'clean_period add fixed skew %d seconds' % skew
                
            else: # get random skew between min & max
                skew = random.randint(self._min_skew, self._max_skew)
                # print 'clean_period add random skew %d seconds (%d-%d)' % \
                #       (skew, self._min_skew, self._max_skew)
                
            secs_until += skew
        
        return secs_until