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

# imports
from types import InstanceType

from channels.channel_source_type_map import TYPE_MAP

# constants

# exception classes

# interface functions

# classes

class ChannelSource(object):
    """
    :class:`ChannelSource` objects are used as a common interface to
    get, set, and refresh data in a given channel.

    :class:`ChannelSource` objects also contain a minimum of meta
    information presented in public variables.  These variables are:
    
    - `type`: the Python type for this channel
    - `perms_mask`: a list of :ref:`permissions <permissions>`
      (:mod:`~channels.channel`.py)
    - `options`: a list of channel :ref:`options <options>`
      (:mod:`~channels.channel`.py)

    """
    __slots__ = ["type", "perms_mask", "options"]

    def __init__(self, type, perms_mask, options):
        self.type = type
        self.perms_mask = perms_mask
        self.options = options
        
        raise NotImplementedError, "virtual function"

    def _instance_type_name(self, instance):
        if instance is InstanceType:
            return instance.__class__.__name__

        return str(type(instance))

    def _type_remap(self, type_obj):    
        if type_obj in TYPE_MAP:
            return TYPE_MAP[type_obj]
        else:
            return type_obj

    def _type_remap_and_check(self, target_type, sample):
        mapped_type = target_type
        
        # special treatment of zero, so 0 = 0.0, etc.
        if sample.value == 0:
            sample.value = mapped_type(0)
        
        if type(sample.value) in TYPE_MAP:
            mapped_type = TYPE_MAP[type(sample.value)]
            try:
                # type re-mapping
                sample.value = mapped_type(sample.value)
            except:
                raise ValueError, \
                    "(ChannelSource): unable to remap value '%s' from %s to %s" % \
                        (str(sample.value),
                            self._instance_type_name(sample.value),
                            str(mapped_type))

        if not isinstance(sample.value, mapped_type):
            raise ValueError, \
                "(ChannelSource): sample type/property type mis-match ('%s' != '%s')" % \
                    (self._instance_type_name(sample.value),
                     str(mapped_type))

        return sample

    def producer_get(self):
        """
        Return a copy of the current sample object.

        """
        raise NotImplementedError, "virtual function"

    def producer_set(self, sample):
        """
        Update the current sample object.

        """
        raise NotImplementedError, "virtual function"

    def consumer_get(self):
        """
        Called from a channel wishing to read this property's data.

        Returns a copy of the current sample value.

        """
        raise NotImplementedError, "virtual function"

    def consumer_set(self, sample):
        """
        Called from a channel wishing to write this property's data.

        """
        raise NotImplementedError, "virtual function"

    def consumer_refresh(self):
        raise NotImplementedError, "virtual function"


# internal functions & classes
