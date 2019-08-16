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

# imports
import sys, traceback
import threading
from copy import copy

from channels.channel import Channel, OPT_DONOTLOG
from channels.logging.logging_events import \
    LoggingEventNewSample, LoggingEventChannelNew, LoggingEventChannelRemove

# constants

# exception classes
class SubscriberNotFound(KeyError):
    """
    Exception raised when callback and channel name cannot be found
    while unsubscribing.

    """
    pass

class ChannelDoesNotExist(KeyError):
    """
    Exception raised when attempting to unsubscribe from a
    channel with no subscriptions

    """
    pass

# interface

# classes

class ChannelPublisher:
    """
    The :class:`ChannelPublisher` exposes :meth:`subscribe` and
    :meth:`unsubscribe` methods and sends a notification whenever a
    :class:`~channels.channel.Channel` gets a new
    :class:`~samples.sample.Sample`

    Consumers may choose to subscribe to individual channels or all
    existing channels, and can specify a method to be called when new
    samples are received.

    The primary routines of interest to most users of this class are:

    * :meth:`subscribe`
    * :meth:`unsubscribe`
    * :meth:`subscribe_to_all`
    * :meth:`unsubscribe_from_all`
    * :meth:`subscribe_new_channels`
    * :meth:`unsubscribe_new_channels`

    All other routines help integrate the :class:`ChannelPublisher`
    into other components in the system
     
    """

    def __init__(self, core_services):
        self.__core = core_services
        self.__new_channel_listeners = set()
        self.__channel_listeners = {}
        self.__rlock = threading.RLock()
        self.__logging_manager = None
		
        from core.tracing import get_tracer
        self.__tracer = get_tracer("ChannelPublisher")

    def subscribe(self, channel_name, callback):
        """
        Subscribe to the :class:`~channels.channel.Channel` specified
        by `channel_name`.  Subscribers may only have one callback per
        channel, so subsequent calls to subscribe will replace the
        callback used.

        You may subscribe to channels that do not exist at the time of
        the subscription.  When they come into existence they will
        properly notify subscribers of updates.

        Parameters:

        * `channel_name`: Name of channel to subscribe to 
        * `callback`: Callable object to be called

        """

        self.__rlock.acquire()
        
        try:
            if channel_name not in self.__channel_listeners:
                self.__channel_listeners[channel_name] = set()
        
            self.__channel_listeners[channel_name].add(callback)
        finally:
            self.__rlock.release()

    def unsubscribe(self, channel_name, callback):
        """
        Unsubscribe from the :class:`~channels.channel.Channel` specified
        by `channel_name`.

        Parameters:

        * `channel_name`:  Name of channel to unsubscribe from
        * `callback`: The callback registered previously

        """

        self.__rlock.acquire()
        
        try:
            if channel_name not in self.__channel_listeners:
                raise ChannelDoesNotExist, "channel '%s' does not exist" % \
                      (channel_name)
        
            if callback not in self.__channel_listeners[channel_name]:
                raise SubscriberNotFound, "Subscriber not found."
        
            self.__channel_listeners[channel_name].remove(callback)
        
        finally:
            self.__rlock.release()

    def subscribe_to_all(self, callback):
        """
        Subscribe to all currently existing channels.  Subscribers may only have
        one callback per channel, so calls to this method will replace
        any existing callbacks.

        .. note::
           Be warned that unlike subscribe, which will allow
           specification of a non-existent channel.  The subscriptions
           provided by :meth:`subscribe_to_all` will only be added to
           channels that exist at the time of the call.

           See :meth:`subscribe_new_channels` to receive new channel
           notifications.

        Parameters:
        
        * `callback`:  Callable object to register

        """

    	self.__rlock.acquire()
    
        try:
            cdb = self.__core.get_service("channel_manager").channel_database_get()
            channel_list = cdb.channel_list()
            for channel_name in channel_list:
                self.subscribe(channel_name, callback)
        finally:
            self.__rlock.release()

    def unsubscribe_from_all(self, callback):
        """
        Unsubscribe from all channels.
        
        * `callback`:  Callable previously registered on channels
        """

    	self.__rlock.acquire()
    
        try:
            for channel_name in self.__channel_listeners:
                if callback in self.__channel_listeners[channel_name]:
                    self.__channel_listeners[channel_name].remove(callback)
        finally:
            self.__rlock.release()


    def subscribe_new_channels(self, callback):
        """
        Subscribe to get a callback whenever a new channel is added.
        Subscribers may only have one callback, so subsequent calls to
        subscribe will replace the callback used.

        Parameters:
        
        * `callback`: Callable object to be called

        """

        self.__rlock.acquire()

        try:
            self.__new_channel_listeners.add(callback)
        finally:
            self.__rlock.release()


    def unsubscribe_new_channels(self, callback):
        """
        Unsubscribe callback from new channel events.

        Parameters:
        
        * `callback`:  Callable previously registered

        """

        self.__rlock.acquire()

        try:
            self.__new_channel_listeners.remove(callback)

        finally:
            self.__rlock.release()


    def set_logging_manager(self, logging_manager):
    	"""
    	Sets the
    	:class:`~channels.logging.logging_manager.LoggingManager`
    	which receives priority sample information notification.

        Parameters:

        * `logging_manager`:
          :class:`~channels.logging.logging_manager.LoggingManager` to
          install

        Primarily part of an interface provided to the
        :class:`~channels.channel_database.ChannelDatabase`. A default
        initial
        :class:`~channels.logging.logging_manager.LoggingManager` is
        installed on DIA start.  This should be sufficient in all but
        the most unusual environments.

    	"""

    	self.__logging_manager = logging_manager

    def remove_logging_manager(self):
    	"""
        Removes current
    	:class:`~channels.logging.logging_manager.LoggingManager`

        """

    	self.__logging_manager = None

    def __dispatch_logging_event(self, logging_event):
        # dispatches all events to the logging manager.

        if logging_event.channel.options_mask() & OPT_DONOTLOG:
            return
        
        if self.__logging_manager is None:
            return
  
        callback = getattr(self.__logging_manager,
                           "dispatch_logging_event", None)
        if callback is None:
            raise NotImplementedError, \
                "LoggingManager does not implement dispatch_logging_event."
        callback(logging_event)

    def new_channel(self, channel):
        """
        Callback to receive a notification when a new channel is
        created.

        Part of an interface provided to the
        :class:`~channels.channel_database.ChannelDatabase`.

        Parameters:
        
        * `channel`:  the new channel
        
        """
        self.__notify_new_channel(channel)
        self.__dispatch_logging_event(LoggingEventChannelNew(channel))
    	channel.add_new_sample_cb(self.new_sample_cb)

    def remove_channel(self, channel):
    	"""
    	Callback to receive a notification when a channel is removed.

        Part of an interface provided to the
        :class:`~channels.channel_database.ChannelDatabase`.

        Parameter:
        
        * `channel`:  the channel to be removed
        
    	"""
        self.__dispatch_logging_event(LoggingEventChannelRemove(channel))

    def new_sample_cb(self, channel):
        """
        Callback to receive new samples from channels.

        Part of an interface provided to the
        :class:`~channels.channel.Channel`. Each
        :class:`~channels.channel.Channel` independently informs the
        :class:`ChannelPubliser` of new samples through this means.

        Parameter:
        
        * `channel`:  the channel with a new sample
        
        """
        self.__dispatch_logging_event(LoggingEventNewSample(channel))
        self.__notify(channel)

    def __notify(self, channel):
        self.__rlock.acquire()
        try:
            channel_listeners = copy(self.__channel_listeners)
        finally:
            self.__rlock.release()
        try:
            if channel.name() in channel_listeners:
                for callback in copy(channel_listeners[channel.name()]):
                    callback(channel)
        except Exception, e:
            self.__tracer.error("exception during channel" +
								" notification: %s", traceback.format_exc())

    def __notify_new_channel(self, channel):
        self.__rlock.acquire()
        try:
            new_channel_listeners = copy(self.__new_channel_listeners)
        finally:
            self.__rlock.release()

        try:
            for callback in new_channel_listeners:
                callback(channel.name())
        except Exception, e:
            self.__tracer.error("exception during channel" + 
			"notification: %s", traceback.format_exc())

# internal functions & classes
