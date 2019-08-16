############################################################################
#                                                                          #
# Copyright (c)2008-2010, Digi International (Digi). All Rights Reserved.  #
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
This module provides access to runtime information about the DIA system.
'''

# imports

# constants
DEVICE_CLASSES = ('devices', 'loggers', 'presentations', 'services')

# exception classes
class BadDeviceClassException(Exception):
    '''
    Raised if get_drivers() is called with a bad device class.
    '''
    pass

class BadParseException(Exception):
    '''
    Raised on a parse error in the 'tracing:' yaml configuration block.
    '''
    pass

# interface functions
def get_drivers(core, types=DEVICE_CLASSES, pending=False):
    '''
    Return a list of (name_string, driver_string) pairs of all
    currently loaded drivers within the set of device classes `types`.

    :param core: a reference to the core_services object
    :param types: list of device types to return \
    (some subset of DEVICE_CLASSES)
    :param pending: If True, return results from global_pending_registry. \
              Otherwise, return results from global_running_registry.

    The only time setting pending=True is useful is before the various
    managers start up. For example, the TracingManager uses it to
    peek at all devices before they are loaded.
    '''

    if pending:
        base_dict = core._settings_global_pending_registry
    else:
        base_dict = core._settings_global_running_registry

    ret = []
    
    for _ in types:
        if not _ in base_dict:
            raise BadDeviceClassException(_)
        else:
            ret += map(_make_name_driver_pair,
                       _unpack_instance_list(base_dict[_]))

    return ret


def _unpack_instance_list(il_dict):
    '''\
    Unpack an 'instance_list' dictionary and return the
    list of items inside.
    '''
    if il_dict == []:
        return []
    if not isinstance(il_dict, dict):
        raise BadParseException('%s is not a dictionary!' % (il_dict))
    if not 'instance_list' in il_dict:
        raise BadParseException('%s doesn\'t contain "instance_list"' %\
              (il_dict))
    return il_dict['instance_list']


def _make_name_driver_pair(d_dict):
    '''\
    Argument entry is a single device-ish dict with a
    name and driver entry.

    Returns a tuple (name, driver)
    '''
    if not isinstance(d_dict, dict):
        raise BadParseException('%s is not a dictionary!' % (d_dict))

    return _lookup('name', d_dict), _lookup('driver', d_dict)

def _lookup(key, _dict):
    '''\
    Validate and return a value.

    This is probably superfluous and unnecessary.
    '''
    if not key in _dict:
        raise BadParseException('%s doens\'t contain "%s")' % \
                                (_dict, key))
    return _dict[key]

