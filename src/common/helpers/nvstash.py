############################################################################
#                                                                          #
# Copyright (c)2008-2013, Digi International (Digi). All Rights Reserved.  #
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
A module (not a DIA Driver) which saves items into NVRAM/FLASH as a Python Dictionary.

It includes a delay timer, which defaults to 30 seconds meaning all updates
which fall within that 30 seconds will be included within the same save/write.
This allows a driver to update multiple items in a natural way without stressing
the NVRAM media.
'''

# imports
import os
import traceback
import types

try:
    import digitime as time
except:
    import time

SHOW_TRACE = True
    
# classes
class nvStash(object):
    '''
    This class adds a simple NVRAM stash of Python dictionary values
    '''

    SAVE_NAME = 'nvstash.txt'

    # this will be a singleton
    __SINGLETON = None

    def __init__(self, filename=SAVE_NAME):

        # save ourself into the singleton
        if nvStash.__SINGLETON is None:
            nvStash.__SINGLETON = self
        # else raise ValueError("Error - more than one NvramStash instance defined!")
        
        self._save_timestamp = 0
        self._save_required = False
        self._data = { 'nvstash.time':0 }

        self._set_filename(filename)

        # self.load()
        
        if SHOW_TRACE: print "nvStash.__init__() %s" % nvStash.__SINGLETON


    @staticmethod
    def get_instance_singleton():
        # this will return None if there are no instances created
        if nvStash.__SINGLETON is None:
            # boot-strap
            nvStash.__SINGLETON = __nvs

        if SHOW_TRACE: print "nvStash.get_instance_singleton()"
        
        return nvStash.__SINGLETON

    def put(self, dict, value=None):
        self._put_no_save(dict, value)
        self.save()
        return
        
    def _put_no_save(self, dict, value=None):

        try:
            if isinstance(dict, types.DictType):
                # if already dictionary, then merge
                self._data.update(dict)

            else:
                # assume dict is a tag, then manually add to dict
                self._data[dict] = value

            self._save_required = True
            
        except:
            traceback.print_exc()

        return

    def get(self, tag):

        try:
            return self._data.get(tag, None)

        except:
            traceback.print_exc()

        return None

    def _get_filename(self):
        return self._filename

    def _set_filename(self, fname, test=False):
        if not os.path.exists(fname):
            # Try again for NDS, which doesn't have concept of local directory
            fname = os.path.abspath(fname)
            # we ignore the missing file, as it may not exist yet
            if test and not os.path.exists(fname):
                raise RuntimeError("file: %s not found" % fname)
        self._filename = fname
        return fname

    def save(self):
        if SHOW_TRACE: print "nvStash.save()"
        self._save_timestamp = time.time()
        self._data['nvstash.time'] = self._save_timestamp
        return self.__raw_save()

    def clear(self):
        if SHOW_TRACE: print "nvStash.clear()"
        self._save_timestamp = 0
        self._data = { 'nvstash.time':0 }
        return self.__raw_save()

    def __raw_save(self):
    
        data = str(self._data) + '\r\n'

        fname = self._get_filename()
        try:
            fn = file(fname, 'wb')
            fn.write(data)
            fn.close()
            self._save_required = False
            return True

        except:
            traceback.print_exc()

        return False
        
    def load(self, test=False):
    
        if SHOW_TRACE: print "nvStash.load()"

        fname = self._get_filename()
        if not os.path.exists(fname):
            if test:
                raise RuntimeError("_load_data file: %s not found" % fname)
            return False

        try:
            fn = file(fname, 'rb')
            data = fn.read()
            fn.close()

            # note: eval hates ending CR/NL, so strip all white space.
            # we added CR/NL, but user might have edited and added more
            data = eval(data.strip())
            self._data.update(data)

        except:
            traceback.print_exc()

        return True
        
__nvs = nvStash()
    
