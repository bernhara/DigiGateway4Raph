############################################################################
#                                                                          #
# Copyright (c)2010 Digi International (Digi). All Rights Reserved.        #
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
Various utilities and common variables that are used throughout DIA.

(This was repurposed from Scott Kilau's SMS code.)

'''

# TODO: remove dead dependency (if no modules requiring this depend on it)
import string


# Define a useful dictionary of seconds to known period times.
# This can (and is) used by the transport classes.
TimeIntervals = [
                    { 'name' : 'second', 'value' : 1        },
                    { 'name' : 'minute', 'value' : 60       },
                    { 'name' : 'hour',   'value' : 3600     },
                    { 'name' : 'day',    'value' : 86400    },
                    { 'name' : 'week',   'value' : 604800   },
                    { 'name' : 'month',  'value' : 2678400  },
                    { 'name' : 'year',   'value' : 31536000 }
                ]


def get_next_interesting_character(pattern):
    next_wildmatch = pattern.find('*')
    next_wildchar  = pattern.find('?')

    if next_wildmatch == -1 and next_wildchar == -1:
        #print "Returning end of pattern"
        return len(pattern)
    elif next_wildmatch == -1 and next_wildchar != -1:
        #print "Returning next_wildchar"
        #print next_wildchar
        return next_wildchar
    elif next_wildmatch != -1 and next_wildchar == -1:
        #print "Returning next_wildmatch"
        #print next_wildmatch
        return next_wildmatch
    else:
        #print "Returning min(%s, %s) " %(next_wildmatch, next_wildchar)
        return min(next_wildmatch, next_wildchar)

def wild_match(pattern, input):
    """\
        This function will take a given wildcard mask, and match it against a
        given string, and return whether it matches or not.
        The wildcard characters that can be used are the standard "glob" style
        characters of the asterick (*) and question mark (?).
        The regex (re) Python library is NOT used.
        Returns True if the string matches the mask/pattern, and will return
        False otherwise.

        Some examples are:
            ret = wild_match('animal',  'animal') -> True
            ret = wild_match('ani*',    'animal') -> True
            ret = wild_match('anim?l',  'animal') -> True
            ret = wild_match('anima',   'animal') -> False
            ret = wild_match('animi?',  'animal') -> False
            ret = wild_match('ani*a',   'animal') -> False
    """
    if not len(pattern):
        return False

    # None ::= lambda (the empty string)
    if input == None:
        return False

    if not len(input):
        return False

    while len(pattern):
#        print "Pattern: %s" %pattern
#        print "String:  %s" %input

        if not len(pattern):
            #print "Pattern stopped, string continued!"
            #print "Input: ", input
            return False

        if pattern[0] == '*':
#            print "Matching *"
            pattern = pattern.lstrip("*?") #'?' following * does not matter
            if not len(pattern):
                #print "* is last meaningful character(s) in pattern, matched"
                return True


            next_index = get_next_interesting_character(pattern)
            pattern_slice = pattern[:next_index]
#            print "Pattern slice: %s" %pattern_slice
#            print "Pattern: %s" %pattern


            index = input.rfind(pattern_slice)
            if index != -1:
                pattern = pattern[next_index:]
                input = input[index+len(pattern_slice):]
            else:
#                print ("Remaining block: %s did not rfind input: %s"
#                                            %(pattern_slice, input))
                return False


        elif pattern[0] == '?':
            #print "Moving pattern, input forward a character"
            if len(input) < 1:
                #print "No remaining characters in pattern stream"
                return False
            pattern = pattern[1:]
            input = input[1:]

        ##This means its a non-special character next in the stream
        else:
            next_index = get_next_interesting_character(pattern)
            pattern_slice = pattern[:next_index]
#            print "Remaining pattern: %s" %pattern[next_index:]
#            print "Pattern slice", pattern_slice
            pattern = pattern[next_index:]
#            print "Pattern is now: %s" %pattern
            if len(input) < next_index:
#                print "Not enough characters remaining to match"
                return False

            match_slice = input[:next_index]

#            print "Match slice is: %s" %match_slice
            if match_slice != pattern_slice:
#                print ("Pattern: %s did not match: %s" %
#                      (pattern_slice, match_slice))
                return False

            input = input[next_index:]
#            print "String is now: %s" %input


       #End while
    #If there is still unmatched input, and our pattern ended, return False
    if len(input):
      return False
    else:
      return True

def wild_subscribe(core_services, channel_pattern, callback):
    """
    wild_subscribe
    
    Subscribes to current and future channels that match the given pattern.
    Channels that are created AFTER this is called that match the pattern
    will also be subscribed to.  Call wild_unsubscribe to stop all 
    subscriptions.  Returns a reference to a anonymous function created, which
    is necessary to unsubscribe. 
    
    Uses the wild_match function to pattern match, which means that
    ? and * tokens are supported. 
    
    core_services - The core services that are passed into all DIA
                    objects that need to subscribe.
    
    channel_pattern -  The pattern to match existing and future channels
    
    callback - The function which accepts the channel object when new samples
               are created.
    
    """
    chm = core_services.get_service("channel_manager")
    cdb = chm.channel_database_get()
    cp  = chm.channel_publisher_get()
    ##Take care of the existing channels
  
    for channel_name in cdb.channel_list():              
        if wild_match(channel_pattern, channel_name):      
            cp.subscribe(channel_name, callback)
      
    ## Setup a callback on subscribe_new_channels that performs the match
    ## Create a temporary function that does this
    
    
    def anon(channel_name):              
        if wild_match(channel_pattern, channel_name):
            cp.subscribe(channel_name, callback)
    cp.subscribe_new_channels(anon)
    return anon

def wild_unsubscribe(core_services, channel_pattern, anon, callback):
    """
    Unsubscribes a callback that was subscribed with wild_subscribe.
    
    core_services - The core services that are passed into all DIA
                    objects that need to subscribe.
                    
    channel_pattern -  The pattern to match existing and future channels
    
    anon - The anonymous function that was returned from wild_subscribe.
    
    callback - The function which accepts the channel object when new samples
               are created.
    
    """
    chm = core_services.get_service("channel_manager")
    cdb = chm.channel_database_get()
    cp  = chm.channel_publisher_get()
    
    ##Remove from existing channels  
    for channel_name in cdb.channel_list():
        if wild_match(channel_pattern, channel_name):
            try:
                cp.unsubscribe(channel_name, callback)
            except Exception, e: ## May throw exception 
                print e
    
    ##Remove the anon callback to subscribe_new_channels
    cp.unsubscribe_new_channels(anon)

if __name__ == '__main__':
    import sys
    #        pattern, input
    inputs = [
              ('animal', 'animal'),
              ('ani*', 'animal'),
              ('anim?l', 'animal'),
              ('anima', 'animal'),
              ('animi?', 'animal'),
              ('ani*a', 'animal'),
              ('???mal', 'animal'),
              ('an*ma*', 'animal'),
              ('a**a*l', 'animal'),
              ('?????l', 'animal'),
              ('**??al', 'animal'),
              ('??????', 'animal'),
              ('really*long*conjugate*', 'really_big_thing_that_is_long_and_full_of_conjugates'),
              ('template*', 'template_device0.counter'),


              ('test', 'fail'),
              ('test*', 'test'),
              ('test?', 'test'),
              ('t*st',  'tesssssssssssssssssssssssssssssssssssssssst'),
              ('t*s*t*', 'teslasterburger'),
              ('t*st?erata', 'tststaerata')

            ]

    for pattern, input in inputs:
        ret = wild_match(pattern, input)
        print "%s -> %s: %s" % (pattern, input, str(ret))
