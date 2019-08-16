# Test the Clean Period class

# imports
import traceback
import types
import time         # we need strptime support

from clean_period import CleanPeriod

# test routines follow!

def test_object(chatty):
    print 'testing CleanPeriod object',
    
    if chatty:
        print
    
    clean = CleanPeriod()
    print '\nbase init, no params'
    print '    ', clean
    
    clean = CleanPeriod(10)
    print '\nbase init, period=10'
    print '    ', clean
    
    clean = CleanPeriod('10 sec')
    print '\nbase init, period="10 sec"'
    print '    ', clean
    
    clean = CleanPeriod('10 min')
    print '\nbase init, period="10 min"'
    print '    ', clean
    
    clean = CleanPeriod('8 hr')
    print '\nbase init, period="8 hr"'
    print '    ', clean
    
    clean = CleanPeriod(10, 2)
    print '\nbase init, period=10, skew=2'
    print '    ', clean
    
    clean = CleanPeriod('10 sec', 2, 10)
    print '\nbase init, period="10 sec", skew=2-10'
    print '    ', clean
    
    clean = CleanPeriod('10 min', '15 sec', '95 sec')
    print '\nbase init, period="10 min", skew="15 sec"-"95 sec"'
    print '    ', clean
    
    clean = CleanPeriod('8 hr', '15 sec')
    print '\nbase init, period="8 hr", skew="15 sec"'
    print '    ', clean
    
    clean = CleanPeriod('5 min', '15 sec', '9 min')
    print '\nbase init, period="5 min", skew="15 sec"-"9 min"'
    print '    ', clean
    
    # CleanPeriod.set_period() and set_skew() should be okay since __init__ uses

    st = "{'period':'10 min'}"
    clean = CleanPeriod()
    clean.import_config(st)
    print '\nimport str(%s)' % st
    print '    ', clean
    clean = CleanPeriod()
    clean.import_config(eval(st))
    print '\nimport DCT %s' % st
    print '    ', clean
    
    st = "{'period':'10 min', 'min_skew':'20 sec'}"
    clean = CleanPeriod()
    clean.import_config(st)
    print '\nimport str(%s)' % st
    print '    ', clean
    clean = CleanPeriod()
    clean.import_config(eval(st))
    print '\nimport DCT %s' % st
    print '    ', clean
    
    st = "{'period':'10 min', 'min_skew':'20 sec', 'max_skew':'90 sec'}"
    clean = CleanPeriod()
    clean.import_config(st)
    print '\nimport str(%s)' % st
    print '    ', clean
    clean = CleanPeriod()
    clean.import_config(eval(st))
    print '\nimport DCT %s' % st
    print '    ', clean
    
    print "Okay!"
    return True


def test_minutes_no_skew(chatty):
    print 'testing CleanPeriod, every 10 minutes, no skew',

    if chatty:
        print
    
    # we don't fully test the secs_until_next_minute_period()
    
    tsts = [
        ( "2013-06-27 07:38:25",   95, "07:40:00"),
        ( "2013-06-27 07:41:00",  540, "07:50:00"),
        ( "2013-06-27 07:59:01",   59, "08:00:00"),
        ( "2013-06-27 08:01:00",  540, "08:10:00"),
        ]

    clean = CleanPeriod('10 min')

    rtn = __sub_minutes_test(chatty, clean, tsts)
    if not rtn:
        return False

    return True

def __sub_minutes_test(chatty, clean, tsts):

    for tst in tsts:
        tim_st = tst[0]
        expect = tst[1]
        exp_st = tst[2]

        tup = time.strptime(tim_st, "%Y-%m-%d %H:%M:%S")
        tim = time.mktime(tup)
        
        try:
            rtn = clean.get_next_period_seconds(tup)
        except:
            rtn = None

        if rtn != expect:
            print "ERROR: rtn:%s didn't match expected:%s in test:%s" % (rtn, expect, tst)
            print 'next=%s' % time.strftime("%H:%M:%S", time.localtime(tim+rtn))
            return False

        if expect is not None:
            target = time.strftime("%H:%M:%S", time.localtime(tim+expect))
            if exp_st != target:
                print "ERROR: rtn:%s didn't match expected:%s in test:%s" % (target, exp_st, tst)
                print 'next=%s' % target
                return False

        if chatty:
            print 'next=%s' % target
                
    return True

def test_minutes_skew(chatty):
    print 'testing CleanPeriod, every 10 minutes, with fixed skew',

    if chatty:
        print
    
    # we don't fully test the secs_until_next_minute_period()
    
    tsts = [
        ( "2013-06-27 07:38:25",  110, "07:40:15"),
        ( "2013-06-27 07:41:00",  555, "07:50:15"),
        ( "2013-06-27 07:59:01",   74, "08:00:15"),
        ( "2013-06-27 08:01:00",  555, "08:10:15"),
        ]

    clean = CleanPeriod('10 min', '15 sec')

    rtn = __sub_minutes_test(chatty, clean, tsts)
    if not rtn:
        return False

    print 'testing CleanPeriod, every 10 minutes, with random skew between 15-85 secs',

    if chatty:
        print
        
    clean = CleanPeriod('10 min', '15 sec', '85 sec')

    for tst in tsts:
        tim_st = tst[0]
        expect = tst[1]
        exp_st = tst[2]

        tup = time.strptime(tim_st, "%Y-%m-%d %H:%M:%S")
        tim = time.mktime(tup)
        rtn = clean.get_next_period_seconds(tup)
        target = time.strftime("%H:%M:%S", time.localtime(tim+rtn))
        if chatty:
            print 'next=%s' % target

    return True

if __name__ == '__main__':

    test_all = False
    chatty = True

    if(False or test_all):
        test_object(chatty)
    
    if(True or test_all):
        test_minutes_no_skew(chatty)

    if(True or test_all):
        test_minutes_skew(chatty)

        