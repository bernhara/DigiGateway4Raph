############################################################################
#                                                                          #
# Copyright (c)2008, Digi International (Digi). All Rights Reserved.       #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice, and the following   #
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
.. _permissions:

.. py:data:: PERM_NONE

   No permissions granted

.. py:data:: PERM_GET

   Can perform a :meth:`consumer_get`

.. py:data:: PERM_SET

   Can perform a :meth:`consumer_set`

.. py:data:: PERM_REFRESH

   Can perform a :meth:`consumer_refresh`

.. _options:

.. py:data:: OPT_NONE

   Nothing selected
   
.. py:data:: OPT_AUTOTIMESTAMP

   :class:`~samples.sample.Sample` objects with no
   :attr:`~samples.sample.Sample.timestamp` attribute specified will
   have the :attr:`~samples.sample.Sample.timestamp` populated with the
   current time.
   
.. py:data:: OPT_DONOTLOG

   :mod:`Logging events <channels.logging.logging_events` will not be
   generated for this channel.
   
.. py:data:: OPT_DONOTDUMPDATA

   A hint to presentations to not include this channel in channel
   dumps.

"""

# imports
from channels.channel_source import ChannelSource

# constants
PERM_NONE = 0x0
PERM_GET = 0x1
PERM_SET = 0x2
PERM_REFRESH = 0x4
PERM_MAX = 0x8

OPT_NONE = 0x0
OPT_AUTOTIMESTAMP = 0x1
OPT_DONOTLOG = 0x2
OPT_DONOTDUMPDATA = 0x4
OPT_MAX = 0x8

# exception classes
class ChannelCallbackNotFound(KeyError):
    """Exception raised when attempting to unregister an unknown callback."""
    pass

# interface functions

# classes

class Channel:
    """
    Channels are the means that the DIA uses to communicate values 
    to different parts of itself, as well as the outside world.

    A channel contains the current sample value and a list of
    callbacks.

    """
    def __init__(self, name, channel_source):
        self.__name = name
        self.__channel_source = channel_source
        self.__new_sample_cbs = [ ]
        if not isinstance(channel_source,ChannelSource):
            raise ValueError, \
            "channel_source must be a ChannelSource instance"

    ## Class Internal functions
    def __dispatch_cbs(self, cb_list, *args, **kwargs):
        for f in cb_list:
            try:
                f(*args, **kwargs)
            except:
                pass

    ## Events
    def __on_new_sample(self):
        """called by the data source when a new sample is available."""
        self.__dispatch_cbs(self.__new_sample_cbs, self)

    ## External Interface
    def name(self):
        """Returns the name of the channel"""
        
    	return self.__name

    def type(self):
        """Returns the type of the channel"""
        
    	return self.__channel_source.type

    def producer_get(self):
        """
        Allows the source of the channel to retrieve its value.

        The producer interface is intended for use by the driver
        providing the channel or priviledged access by the logging
        subsystem.  It should not be used by presentations or any
        other module in the system.  Instead, they should perform a
        :meth:`get` operation which, by default, maps to the
        :meth:`consumer_get` method.
        
        """
    	return self.__channel_source.producer_get()

    def producer_set(self, sample):
        """
        Allows the source of the channel to set a new value

        The producer interface is meant for use by the driver
        providing the channel, it should not be used by presentations
        or other modules in the system intending to use the value.

        """
        
    	self.__channel_source.producer_set(sample)
    	self.__on_new_sample()

    def consumer_get(self):
        """
        Retrieves the current value as a
        :class:`~samples.sample.Sample` object.

        """
    	return self.__channel_source.consumer_get()

    def consumer_set(self, sample):
        """
        Sets the current value, expects a
        :class:`~samples.sample.Sample` object.

        """
        
    	do_event = self.__channel_source.consumer_set(sample)
        if do_event:
            self.__on_new_sample()

    def consumer_refresh(self):
        """
        Request for the the channel to perform an immediate update of
        s :class:`~samples.sample.Sample`.

        """
        return self.__channel_source.consumer_refresh()

    def perm_mask(self):
        """Returns the permissions applicable to this :class:`Channel`"""
        return self.__channel_source.perms_mask

    def options_mask(self):
        """Returns the options in effect upon this :class:`Channel`"""
        return self.__channel_source.options

    # Aliases for consumer functions:
    get = consumer_get
    set = consumer_set
    refresh = consumer_refresh

    def add_new_sample_cb(self, f):
    	"""
        Add a function f to be called back when this channel is updated.

        The call should accept a single argument.  The argument will be
        set to this channel object.
        
        .. note:: This is not the recommended means of subscribing to
            channel events.  Please see the
            :class:`~channels.channel_publisher.ChannelPublisher`
            which may be accessed from the
            :class:`~channels.channel_manager.ChannelManager` service.
            
    	"""
        if not f in self.__new_sample_cbs:
            self.__new_sample_cbs.append(f)

    def remove_new_sample_cb(self, f):
        """Remove a function f from the updated call back list."""
        
        if f not in self.__new_sample_cbs:
            raise ChannelCallbackNotFound, "Callback function not found."

        self.__new_sample_cbs.remove(f)

# internal functions & classes
