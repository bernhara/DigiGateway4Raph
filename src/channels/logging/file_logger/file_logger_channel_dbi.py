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
from copy import copy
from threading import RLock, Event

from channels.channel import Channel
from channels.logging.channel_source_logger import ChannelSourceLogger
from channels.logging.logging_events import \
    LoggingEventNewSample, LoggingEventChannelNew, LoggingEventChannelRemove, \
    LoggingEventMeta
from channels.logging.file_logger.file_logger_storage_manager import \
    RetrieveSeek, RetrieveNext, RetrievePrevious, \
    DBIEventBase, DBIEventChannelNew, DBIEventChannelRemove, \
    DBIEventNewSample, DBIEventChannelDump, \
    NoEvent, FlushOperation

from channels.channel_database_interface import \
    LOG_SEEK_SET, LOG_SEEK_CUR, LOG_SEEK_END, LOG_SEEK_REC, \
    ChannelDatabaseInterface, ChannelAlreadyExists, ChannelDoesNotExist


# classes

class FileLoggerChannelDBI(ChannelDatabaseInterface):
    """
    Implements a
    :class:`~channels.channel_database_interface.ChannelDatabaseInterface`
    for the :class:`~channels.logging.file_logger.file_logger.FileLogger`.

    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.

    """

    def __init__(self, op_req_method):
        self.__channels = { }
        self.__position = None

        self.__op_req_method = op_req_method
        self.__op_req_lock = RLock()
        self.__op_req_complete = Event()
        self.__op_req_result = None

        # The following are used by log_event_iterator() :
        self.__last_logging_event = None

    def __op_complete_indication(self, *args, **kwargs):
        self.__op_req_result = args[0]
        self.__op_req_complete.set()

    def __perform_operation(self, op):
        # ensure all log event requests are serialized by locking here:
        self.__op_req_lock.acquire()
        try:
            op.set_completion_cb(self.__op_complete_indication)
            self.__op_req_method(op)
            self.__op_req_complete.wait()
            self.__op_req_complete.clear()
        finally:
            ret = self.__op_req_result
            self.__op_req_result = None
            self.__op_req_lock.release()

        if isinstance(ret, Exception):
            raise ret

        return ret

    def __apply_cdo(self, cdo):
        # Apply a channel dump object to the DBI context.
        if not isinstance(cdo, DBIEventChannelDump):
            raise ValueError, "_apply_event: event must be of type EventBase"

        self.__channels.clear()
        for channel_name in cdo.channel_dict:
            self.__channels[channel_name] = Channel(
                name=channel_name,
                channel_source=ChannelSourceLogger(
                    initial=cdo.channel_dict[channel_name]))

        self.__position = cdo.record_position
        self.__last_logging_event = LoggingEventMeta(record=self.__position,
                                        description="Channel dump")

    def _apply_event(self, event):
        # Apply a log event to the DBI context.
        if not isinstance(event, DBIEventBase):
            raise ValueError, "_apply_event: event must be of type EventBase"
        if isinstance(event, DBIEventChannelDump):
            return self.__apply_cdo(event)

        logging_event = None
        if isinstance(event, DBIEventChannelNew):
            self.__channels[event.channel_name] = Channel(
                name=event.channel_name,
                channel_source=ChannelSourceLogger(initial=event.sample))
            logging_event = LoggingEventChannelNew(
                        channel=copy(self.__channels[event.channel_name]),
                        record=event.record_position)
        elif isinstance(event, DBIEventNewSample):
            self.__channels[event.channel_name].producer_set(event.sample)
            logging_event = LoggingEventNewSample(
                        channel=copy(self.__channels[event.channel_name]),
                        record=event.record_position)
        elif isinstance(event, DBIEventChannelRemove):
            logging_event = LoggingEventChannelRemove(
                        channel=copy(self.__channels[event.channel_name]),
                        record=event.record_position)
            del(self.__channels[event.channel_name])
        else:
            raise ValueError, "_apply_event: unknown event %s" % (
                                    event.__class__.__name__)

        self.__last_logging_event = logging_event
        self.__position = event.record_position

    def _apply_event_inverse(self, event):
        # Apply a log event inversely to the DBI context.
        if not isinstance(event, DBIEventBase):
            raise ValueError, "_apply_event: event must be of type EventBase"
        if isinstance(event, DBIEventChannelDump):
            return self.__apply_cdo(event)

        self.__apply_last_event = event

        logging_event = None
        if isinstance(event, DBIEventChannelNew):
            logging_event = LoggingEventChannelNew(
                        channel=copy(self.__channels[event.channel_name]),
                        record=event.record_position)
            logging_event.channel = copy(self.__channels[event.channel_name])
            try:
                del(self.__channels[event.channel_name])
            except:
                pass
        elif isinstance(event, DBIEventChannelRemove):
            self.__channels[event.channel_name] = Channel(
                name=event.channel_name,
                channel_source=ChannelSourceLogger(initial=event.sample))
            logging_event = LoggingEventChannelRemove(
                        channel=copy(self.__channels[event.channel_name]),
                        record=event.record_position)
        elif isinstance(event, DBIEventNewSample):
            self.__channels[event.channel_name].producer_set(event.sample)
            logging_event = LoggingEventNewSample(
                        channel=copy(self.__channels[event.channel_name]),
                        record=event.record_position)
        else:
            raise ValueError, "_apply_event_inverse: unknown event %s" % (
                                    event.__class__.__name__)

        self.__last_logging_event = logging_event
        self.__position = event.record_position

    def channel_add(self, channel_name, channel_source):
        raise NotImplementedError, "channel add not valid on logging DBI"

    def channel_remove(self, channel_name):
        raise NotImplementedError, "channel remove not valid on logging DBI"

    def channel_get(self, channel_name):
        if not self.channel_exists(channel_name):
            raise ChannelDoesNotExist, "channel '%s' does not exist" % \
                (channel_name)
        return self.__channels[channel_name]

    def channel_list(self):
        return self.__channels.keys()

    def channel_exists(self, name):
        return name in self.__channels

    def log_next(self):
        op = RetrieveNext()
        self.__perform_operation(op)

        return True

    def log_prev(self):
        op = RetrievePrevious()
        self.__perform_operation(op)

        return True


    def log_rewind(self):
        self.log_seek(offset=0, whence=LOG_SEEK_SET)

    def log_seek(self, offset=0, whence=LOG_SEEK_SET, record_index=None):
        op = RetrieveSeek(offset=offset, whence=whence,
                          record_index=record_index)
        self.__perform_operation(op)

    def log_position(self):
        return self.__position

    def log_event_iterator(self, from_record, to_record=None):
        # If you wish to terminate iteration of the log early the user MUST
        # call the close() method of the iterator in order to release
        # internal mutual exclusion locks.  Not calling close() on the
        # iterator will leave the logger's ChannelDatabaseInterface context
        # in a locked state; making it impossible to perform other operations
        # on the context.

        def get_last_event():
            return self.__last_logging_event

        class LogEventIterator(object):
            def __init__(self, from_record, to_record, step,
                            lock, perform_op, get_last_event):
                self.__from_record = from_record
                self.__to_record = to_record
                self.__step = step

                self.__lock = lock
                self.__islocked = False
                self.__perform_op = perform_op
                self.__get_last_event = get_last_event

                # Force a flush of any pending events from memory to disk.
                op = FlushOperation()
                self.__perform_op(op)

            def __iter__(self):
                return self.__log_event_generator()

            def __del__(self):
                try:
                    self.close()
                except:
                    pass

            def __log_event_generator(self):
                self.__lock.acquire()
                self.__islocked = True

                try:
                    # set initial seek position:
                    op = RetrieveSeek(offset=0, whence=LOG_SEEK_REC,
                                      record_index=self.__from_record)
                    self.__perform_op(op)

                    i = None
                    last_logging_event = self.__get_last_event()
                    if last_logging_event is not None:
                        yield last_logging_event
                        i = last_logging_event.record

                    while 1:
                        # are we finished?
                        if i is not None and self.__to_record is not None:
                            if (step > 0 and i >= self.__to_record):
                                break
                            elif (step < 0 and i <= self.__to_record):
                                break

                        # perform operation
                        op = RetrieveSeek(offset=step, whence=LOG_SEEK_CUR,
                                          record_index=None)
                        try:
                            self.__perform_op(op)
                        except NoEvent, e:
                            if None not in (self.__from_record,
                                                self.__to_record):
                                # unexpected error:
                                raise e
                            else:
                                break
                        last_logging_event = self.__get_last_event()
                        if last_logging_event is None:
                            # must have been a channel dump or other
                            # event we have no representation for
                            continue

                        yield last_logging_event
                        i = last_logging_event.record
                except Exception, e:
                    self.close()
                    raise
                self.close()

            def close(self):
                if self.__islocked:
                    self.__lock.release()


        # take the lock in order to block other operations:
        step = 1
        # this works even if from_record or to_record is None:
        if (to_record is not None and from_record > to_record):
            step = -1

        return LogEventIterator(from_record, to_record, step,
                                self.__op_req_lock, self.__perform_operation,
                                get_last_event)
