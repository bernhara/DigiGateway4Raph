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

"""
ChannelSource objects manage the interface differences between referencing
the get()/set()/refresh() methods on a device property and a native
channel object.

A device's values are known as properties.  Each property has one or more
unique names associated with it, an inital value, access permissions,
options mask, and callback functions.

Permissions for a property are set in the form of a mask and are defined to
be one or more of the following:

* **DPROP_PERM_GET:** values from this property can be read
* **DPROP_PERM_SET:** values from this property can be written
* **DPROP_PERM_REFRESH:** this property is allowed to be arbitrarily updated

* **DPROP_OPT_AUTOTIMESTAMP:** set time automatically on samples from a driver
* **DPROP_OPT_DONOTLOG:** do not log any channel operations associated with
                          this device propery.
* **DPROP_OPT_DONOTDUMPDATA:** a hint to presentations to not include this
                               channel in channel dumps.

.. note::

   These are the same as the :ref:`permissions <permissions>` and
   :ref:`options <options>` in :mod:`~channels.channel`

"""

# imports
from copy import copy
from exceptions import Exception
import threading
import digitime

from channels.channel_source import ChannelSource
from samples.sample import Sample

from channels.channel import \
    PERM_NONE as DPROP_PERM_NONE, \
    PERM_GET as DPROP_PERM_GET, \
    PERM_SET as DPROP_PERM_SET, \
    PERM_REFRESH as DPROP_PERM_REFRESH, \
    PERM_MAX as DPROP_PERM_MAX
    
from channels.channel import \
    OPT_NONE as DPROP_OPT_NONE, \
    OPT_AUTOTIMESTAMP as DPROP_OPT_AUTOTIMESTAMP, \
    OPT_DONOTLOG as DPROP_OPT_DONOTLOG, \
    OPT_DONOTDUMPDATA as DPROP_OPT_DONOTDUMPDATA, \
    OPT_MAX as DPROP_OPT_MAX 

# constants
BUILTIN_TYPE = type

# exception classes
class DevicePropertyPermError(Exception):
    """Permissions Error"""
    pass

class DevicePropertyChannelExists(AttributeError):
    """Channel already exists"""
    pass

# interface functions

# classes
class ChannelSourceDeviceProperty(ChannelSource):
    """
    Create a ChannelSourceDeviceProperty.
    """    
    __slots__ = ['name', 'type', 'perms_mask', 'options', 'device_set_cb', 
                 'device_refresh_cb', '__rlock', '__sample']

    def __init__(self, name, type, initial=Sample(timestamp=0, value=0),
                    perms_mask=DPROP_PERM_NONE,
                    options=DPROP_OPT_NONE,
                    set_cb=lambda s: None, refresh_cb=lambda: None):
        """
        Create a DevicePropertyItem.

        Keyword arguments:
        * **name:** the name of the device property
        * **type:** a type constructor to create the item from a string
        * **initial:** the initial Sample object used to populate the channel
        * **permissions:** a mask of permissions (constants DPROP_PERM_*)
        * **options:** a mask of options (constants DPROP_OPT_*)
        * **set_cb:** function called with sample argument for a set request
        * **refresh_cb:** function called when this property should be updated

        """

        if not isinstance(name, str):
            raise ValueError, "Channel name must be a string"
        if name.find('.') >= 0:
            raise ValueError("Channel name may not contain a dot (%s)" % name)
        if not callable(type):
            raise ValueError, "type must be callable"
        if not isinstance(initial, Sample):
            raise ValueError, "initial value must be Sample object instance"
        if not isinstance(initial.value, type):
            raise ValueError, \
                "(%s): cannot create, sample type/property type mis-match ('%s' != '%s')" % \
                    (name, repr(BUILTIN_TYPE(initial.value)), repr(type))
        if not isinstance(perms_mask, int) or perms_mask >= DPROP_PERM_MAX:
            raise ValueError, "invalid permissions mask"
        if not isinstance(options, int) or options >= DPROP_OPT_MAX:
            raise ValueError, "invalid options mask"
        if set_cb is not None and not callable(set_cb):
            raise ValueError, "set_cb must be callable"
        if not callable(refresh_cb):
            raise ValueError, "refresh_cb must be callable"

        # attributes of this property:
        self.name = name
        self.type = ChannelSource._type_remap(self, type)
        self.perms_mask = perms_mask
        self.options = options
        self.device_set_cb = set_cb
        self.device_refresh_cb = refresh_cb
        self.__rlock = threading.RLock()

        # the current sample for this channel:
        self.__sample = initial

    def producer_get(self):
        """
        Return a copy of the current sample object.
        
        This function should only be called by a DeviceProperties object.
        """
        return self.__sample

    def producer_set(self, sample):
        """
        Update the current sample object.
        
        This function should only be called by a DeviceProperties object.
        """
        sample = ChannelSource._type_remap_and_check(self, self.type, sample)
        self.__rlock.acquire()
        try:
            if sample.timestamp == 0 and self.options & DPROP_OPT_AUTOTIMESTAMP:
                sample.timestamp = digitime.time()
            self.__sample = copy(sample)
        finally:
            self.__rlock.release()


    def consumer_get(self):
        """
        Called from a channel wishing to read this property's data.

        Returns a copy of the current sample value.
        """
        if not self.perms_mask & DPROP_PERM_GET:
            raise DevicePropertyPermError, "get permission denied"

        return copy(self.__sample)

    def consumer_set(self, sample):
        """
        Called from a channel wishing to write this property's data.

        If there is a device set callback defined, it is called.  If
        the callback is called it is the callback's responsiblity to
        set the data in the channel (by calling producer_set()).  If
        the device wishes to reject the value of the set, it must
        raise an exception.

        If no callback is defined, the value is simply set on the
        channel as long as it passes type checking.

        Return: Returns True if the set was performed by the
        channel_source rather than the driver and the Channel needs to
        generate an event.
        """
        if not self.perms_mask & DPROP_PERM_SET:
            raise DevicePropertyPermError, "set permission denied"

        sample = ChannelSource._type_remap_and_check(self, self.type, sample)
        retval = False

        self.__rlock.acquire()
        try:
            if self.device_set_cb is not None:
                # Exceptions are propagated upward:
                self.device_set_cb(sample)
            else:
                self.__sample = sample
                retval = True
        finally:
            self.__rlock.release()

        return retval

    def consumer_refresh(self):
        """
        Called from a channel wishing to have this property's value
        refreshed now.
        
        Calls the device driver refresh callback registered for this property.
        """
        if not self.perms_mask & DPROP_PERM_REFRESH:
            raise DevicePropertyPermError, "refresh permission denied"

        self.device_refresh_cb()


# internal functions & classes
