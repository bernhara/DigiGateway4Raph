'''
Created on Aug 9, 2010

@author: Lynn
'''

import types

class MinMaxAvg(object):

    AVG_SLIDING = 0   # each new average is a % of old average and new sample
    AVG_TRUE = 1      # use list if actual samples to re-calc new average

    DEF_SLIDING = 0.2 # each new average is 80% old average, 20% new sample
    DEF_SAMPLES = 10  # actual number samples to hold
    MAX_SAMPLES = 100 # never save more samples than this

    TAG_MODE = 0
    TAG_MIN = 1
    TAG_AVG = 2
    TAG_MAX = 3
    TAG_NUM_SAM = 4
    TAG_SAMS = 5
    TAG_PRC_NEW = 6
    TAG_PRC_OLD = 7
    TAG_FP_RND = 8

    def __init__(self):

        # our state data is list so it can be manupulated at will
        self.data = [self.AVG_SLIDING, None, None, None, \
                     self.DEF_SAMPLES, [], \
                     0, 0, \
                     None] # no rounding - doesn't work on X3 anyway

        self.set_mode_sliding_average(self.DEF_SLIDING)
        return

    def get_average(self):
        return self.data[self.TAG_AVG]

    def get_minimum(self):
        return self.data[self.TAG_MIN]

    def get_maximum(self):
        return self.data[self.TAG_MAX]

    def get_stats(self):
        return (self.data[self.TAG_MIN], self.data[self.TAG_AVG], self.data[self.TAG_MAX])

    def get_sample_list(self):
        return self.data[self.TAG_SAMS]

    def load_small_item_list(self, data):
        '''Import tuple of basic stats'''
        print 'load data type=', type(data), data
        if data is None:
            # then nothing to import/load
            return

        if isinstance(data, types.StringType):
            # then parse string to python object
            data = eval(data)

        if isinstance(data, types.TupleType) and (len(data) >= 3):
            # then update self with the info
            # no change for TAG_MODE, TAG_NUM_SAM, TAG_PRC_NEW, TAG_PRC_OLD
            self.data[self.TAG_MIN] = data[0]
            self.data[self.TAG_AVG] = data[1]
            self.data[self.TAG_MAX] = data[2]
            if data[1] is not None:
                self.data[self.TAG_SAMS] = [data[1]] # last avg as only item
            else:
                self.data[self.TAG_SAMS] = []

        return

    def save_small_item_list(self):
        '''Export tuple of basic stats'''
        min = self.data[self.TAG_MIN]
        avg = self.data[self.TAG_AVG]
        max = self.data[self.TAG_MAX]
        do_round = self.data[self.TAG_FP_RND]
        if do_round is not None:
            # then force to FP and round to shorten
            min = round(float(min), do_round)
            avg = round(float(avg), do_round)
            max = round(float(max), do_round)
        return (min, avg, max)

    def set_mode_sliding_average(self, prc, sam_num=DEF_SAMPLES):

        if prc < 100.0 and prc > 1.0:
            # convert 1% to 100% into 0.01 to 1.0
            prc = prc / 100.0

        if (prc < 1.0) and (prc > 0.0) and (sam_num >= 0) \
                and (sam_num <= self.MAX_SAMPLES):
            self.data[self.TAG_MODE] = self.AVG_SLIDING
            self.data[self.TAG_PRC_NEW] = prc
            self.data[self.TAG_PRC_OLD] = (1.0 - prc)
            self.data[self.TAG_NUM_SAM] = int(sam_num) # zero is fine here
        else:
            self.data[self.TAG_MODE] = None
        return

    def set_mode_true_average(self, sam_num=DEF_SAMPLES):

        if (sam_num >= 0) and (sam_num <= self.MAX_SAMPLES):
            self.data[self.TAG_MODE] = self.AVG_TRUE
            self.data[self.TAG_NUM_SAM] = int(sam_num)
        else:
            self.data[self.TAG_MODE] = None
        return

    def update(self, new_data):

        # handle no data, do nothing
        if new_data is None:
            return False

        # handle the MINIMUM
        x = self.data[self.TAG_MIN]
        if x is None or (new_data < x):
            # then this is a new minimum, save rounded
            self.data[self.TAG_MIN] = new_data

        # handle the MAXIMUM
        x = self.data[self.TAG_MAX]
        if x is None or (new_data > x):
            # then this is a new maximum, save rounded
            self.data[self.TAG_MAX] = new_data

        # update the saved sample list
        if self.data[self.TAG_NUM_SAM] > 0:
            avg_sam = self.data[self.TAG_SAMS]
            avg_sam.append(new_data)
            x = self.data[self.TAG_NUM_SAM]
            if len(avg_sam) > x:
                # then too long, so truncate to desired length
                avg_sam = avg_sam[-x:]
            self.data[self.TAG_SAMS] = avg_sam
            # note: avg_sam is used again down in True average section
        else:
            avg_sam = []

        # handle the AVERAGE
        avg = self.data[self.TAG_AVG]
        avg_typ = type(new_data)
        if avg is None:
            # then is first update, just use first value
            self.data[self.TAG_AVG] = new_data

        elif(self.data[self.TAG_MODE] == self.AVG_SLIDING):
            # then do simple sliding average
            # for example 0.1 means 10% new and 90% old
            avg = (new_data * self.data[self.TAG_PRC_NEW]) + \
                  (avg * self.data[self.TAG_PRC_OLD])
            # save and re-cast to match input data type
            self.data[self.TAG_AVG] = avg_typ(avg)

        elif(self.data[self.TAG_MODE] == self.AVG_TRUE):
            # then do a true sum-up average, min/max
            avg = 0
            vmin = self.data[self.TAG_MAX] # min will be less than OLD max
            vmax = self.data[self.TAG_MIN] # max will be more than OLD min
            # print 'total samples = %d' % len(avg_sam)
            for rs in avg_sam:
                # print '  rs:%s min:%s max:%s avg:%s' % (rs,vmin,vmax,avg)
                avg += rs
                if rs < vmin:
                    vmin = rs
                if rs > vmax:
                    vmax = rs

            # save and re-cast to match input data type
            self.data[self.TAG_MIN] = vmin
            self.data[self.TAG_MAX] = vmax
            self.data[self.TAG_AVG] = (avg / len(avg_sam))
            # self.data[TAG_PRC_NEW] & self.data[TAG_PRC_OLD] not used

        else:
            print 'MinMaxAvg() mode or config was invalid, no avg'
            self.data[self.TAG_AVG] = None
            return False

        return True

