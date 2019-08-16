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
'''
The XBeeDeviceManager's Digi Device Objects ("DDO") parameter cache module.

This module contains a caching sub-system used to store the values of
network parameters to reduce the number of operations performed on the
network.
'''

from core.tracing import get_tracer
from devices.xbee.common.addressing import normalize_address, addresses_equal
import struct

class XBeeDDOParamCacheMiss(KeyError):
    pass

class XBeeDDOParamCacheMissNodeNotFound(XBeeDDOParamCacheMiss):
    pass

class XBeeDDOParamCacheMissParamNotFound(XBeeDDOParamCacheMiss):
    pass


class XBeeDDOParamCache(object):
    ''' XBee Digi Device Objects ("DDO") Parameter Cache '''
    def __init__(self):
        self.__ddo_param_cache = {}
        self._tracer = get_tracer('XBeeDDOParamCache')
        
    def cache_get(self, addr_extended, param):
        '''
        Retrieve a value from the cache.
        
        :raises XBeeDDOParamCacheMissNodeNotFound: if the node is not in the
                                                   cache.
        :raises XBeeDDOParamCacheMissParamNotFound: if the parameter does not
                                                    exist in the cache for the
                                                    given node address.
        :param addr_extended: a valid XBee extended address string
        :param param: a two letter mnemonic string of a DDO parameter
        :retval: returns the cached parameter value as a string
        '''
        addr_extended = normalize_address(addr_extended)
        if addr_extended not in self.__ddo_param_cache:
            self._tracer.debug("CACHE MISS param '%s' addr '%s'"
                               "reason: node not found" % (
                                   param, addr_extended))
            raise XBeeDDOParamCacheMissNodeNotFound()
        
        if param not in self.__ddo_param_cache[addr_extended]:
            self._tracer.debug("CACHE MISS param '%s' addr '%s'"
                               "reason: param not found" % (
                                   param, addr_extended))
            raise XBeeDDOParamCacheMissParamNotFound()

        self._tracer.debug("CACHE HIT: '%s' = %s for '%s'" % (
            param, repr(self.__ddo_param_cache[addr_extended][param]),
            addr_extended))
        
        return self.__ddo_param_cache[addr_extended][param]

    def cache_set(self, addr_extended, param, value):
        '''
        Set a value to the cache.
        
        If `value` is None the cached value will be invalidated for
        `addr_extended`.
        
        If `value` is given as an integer it will be packed to a 16-bit
        big-endian ordered byte string.  This is to mimic the return
        value of ddo_get_param when values are retrieved from the cache.
        
        :param addr_extended: a valid XBee extended address string
        :param param: a two letter mnemonic string of a DDO parameter
        :param value: a string or integer
        :rtype: None
        '''
        addr_extended = normalize_address(addr_extended)
        param = param.upper()
        if addr_extended not in self.__ddo_param_cache:
            self.__ddo_param_cache[addr_extended] = {}
        
        if value is None:
            self.cache_invalidate(addr_extended, param)
        else:
            if isinstance(value, int):
                if value <= 0xffff:
                    value = struct.pack(">H", value)
                else:
                    # try to mimic 4 byte return value for large items
                    value = struct.pack(">I", value)

            self._tracer.debug("CACHE STORE: cached '%s' = %s for '%s'" % (
                               param, repr(value), addr_extended))
            self.__ddo_param_cache[addr_extended][param] = value
        
    def cache_invalidate(self, addr_extended, param=None):
        '''
        Invalidate a portion of the cache.

        If `addr_extended` is given and `param` is None, all parameters
        for `addr_extended` will be invalidated.
        
        If `param` is not None and it is a valid two-letter DDO mnemonic,
        only that parameter will be invalidated from the cache for the
        node given by `addr_extended`. 
        
        :raises XBeeDDOParamCacheMissNodeNotFound: if `addr_extended` is not
                                                   found in the cache.       
        :param addr_extended: a valid XBee extended address string
        :param param: a two letter mnemonic string of a DDO parameter
        :rtype: None
        '''
        addr_extended = normalize_address(addr_extended)
        param = param.upper()
        if addr_extended not in self.__ddo_param_cache:
            raise XBeeDDOParamCacheMissNodeNotFound
        
        if param is None:
            del(self.__ddo_param_cache[addr_extended])
            
        if param not in self.__ddo_param_cache[addr_extended]:
            # no-op
            return
        
        del(self.__ddo_param_cache[addr_extended][param])
