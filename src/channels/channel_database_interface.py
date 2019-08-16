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

# imports
class ChannelAlreadyExists(AttributeError):
    """Exception when attempting to add an existing channel"""
    
    pass

class ChannelDoesNotExist(KeyError):
    """Exception when attempting to retrieve a non-existent channel"""
    
    pass

# constants
LOG_SEEK_SET = 0x0
LOG_SEEK_CUR = 0x1
LOG_SEEK_END = 0x2
LOG_SEEK_REC = 0x3

# exception classes

# interface functions

# classes

class ChannelDatabaseInterface:
    """
    :class:`ChannelDatabaseInterface` provides a generic interface for
    providing a view into the state of a running DIA system and its
    :class:`~channels.channel.Channel` values.

    Normally, there exists one sub-classed
    :class:`~channels.channel_database.ChannelDatabase` object in the
    system for the latest up-to-date state.

    This class is also often sub-classed by an implementation of a
    logger to provide a view into and the ability to traverse the
    historical data provided by the log.

    """
    
    def __init__(self, core_services):
        raise NotImplementedError, "virtual function"

    def channel_add(self, channel_name, channel_source):
        """Add a channel to the
        :class:`~channels.channel_database.ChannelDatabase`.

        This method adds the `channel_name` channel to the
        :class:`~channels.channel_database.ChannelDatabase`.  Data for
        that channel will be provided by the `channel_source`
        :class:`~channels.channel_source.ChannelSource` object.  Most
        drivers will not need to explicitly call this routine.  It is
        managed through the device property interface.
        
        Returns the new :class:`~channels.channel.Channel` object back
        to caller.

        """

        raise NotImplementedError, "virtual function"

    def channel_remove(self, channel_name):
        """
        Remove a :class:`~channels.channel.Channel` from the channel
        database instance.
        
        If supported, this method will generate an appropriate log event.
        """

        raise NotImplementedError, "virtual function"

    def channel_get(self, channel_name):
        """
        Get a :class:`~channels.channel.Channel` from the channel
        database instance by name.

        """

        raise NotImplementedError, "virtual function"

    def channel_list(self):
        """
        Get a list of :class:`~channels.channel.Channel` names from
        the channel database instance.

        """

        raise NotImplementedError, "virtual function"

    def channel_exists(self, name):
        """
        Test if a :class:`~channels.channel.Channel` name exists in
        the channel database.

        """

        raise NotImplementedError, "virtual function"

    def log_next(self):
        """Progress the state of this database one event in time."""

        raise NotImplementedError, "virtual function"

    def log_prev(self):
        """Regress the state of this database one event in time."""

        raise NotImplementedError, "virtual function"

    def log_rewind(self):
        """Alias for `log_seek(offset=0, whence=LOG_SEEK_SET)` """
        
        self.log_seek(offset=0, whence=LOG_SEEK_SET)

    def log_seek(self, offset=0, whence=LOG_SEEK_SET, record_index=None):
        """
        Progress or regress the state of this channel database.
        
        `offset` specifies a record offset number to seek to.
        
        `whence` values are:
        
            LOG_SEEK_SET
               set position equal to 'offset' records from the
               earliest record in the database.
                            
            LOG_SEEK_CUR
               set position equal to 'offset' records relative to the
               current position of the database.
                            
            LOG_SEEK_END
               set position equal to the end-of-file plus 'offset'.
                            
            LOG_SEEK_REC
               set the position of the database 'offset' records from
               absolute record number 'record_index'.

        """
        raise NotImplementedError, "virtual function"

    def log_position(self):
        """Return time of the last processed log event."""
        
        raise NotImplementedError, "virtual function"

    def log_event_iterator(self, from_record, to_record=None):
        """
        Return an iterator for
        :class:`~channels.logging.logging_events.LoggingEvent`
        objects.
        
        `from_record` and `to_record` are absolute record numbers to
        seek from/to inclusively.  If `to_record` is omitted, the log
        will continue seeking to the last record.
                
        Calling this method has the side-effect of modifying the
        logger state as logger records are retrieved.

        """
        raise NotImplementedError, "virtual function"


# internal functions & classes
