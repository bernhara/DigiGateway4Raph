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

"""\
"""

# imports
import sys
import threading
import Queue
import struct
import os
import pickle
import operator
import StringIO
import bisect
import traceback
from copy import deepcopy

import digitime
from core.tracing import get_tracer

from collections import deque

from channels.channel_database_interface import \
    LOG_SEEK_SET, LOG_SEEK_CUR, LOG_SEEK_END, LOG_SEEK_REC
from samples.sample import Sample

# constants

#### File structure ####
# The log file is comprised of three sections.  The first, containing
# location information for all other sections is the header. The
# bulk of the log is implementing in the second region, the ERB (Event
# Ring Buffer).  The final area, the only area of non-bounded size is
# the string dictionary at the end.

# A future enhancement that may be made depending on profiling and
# system startup performance is storing a CDORB (Channel Dump Object
# Ring Buffer) which would contain information used for the efficient
# retrieval of log data by providing sorted, convenient access to
# record numbering data.  This is a data structure that is maintained
# in memory from an initial startup scan of the ERB presently.

# Header

# The header contains the following elements
# Offset     Item
#      0     Magic 'FL'
#      2     ERB offset
#      6     nameDB offset
#      10     Instance name length
#      11     File_Logger name when log file was created

MAGIC = 'FL'
LOG_HDR_FMT = '>2sIIH'
LOG_HDR_SIZE = struct.calcsize(LOG_HDR_FMT)

# The CDORB.  The CDORB is a list that contains at a minimum ordered
# offsets to channel dump events in the ERB.  It can be used to
# efficiently locate a channel dump to provide a starting location
# with localized channel information when seeking a particular record
# in the logging event stream.  It is the responsibility of the write
# handler to maintain this data structure and ensure that it removes
# elements when it invalidates their channel dump event. If we decide
# to store this into the file, it will simply be a sequence of these
# offsets in a section of known size that is sufficient to hold a
# reasonable amount of offsets.  The "empty" offset may be chosen to
# be either zero (can't point to the beginning of the file and
# convenient with POSIX file seek behavior), or 0xffffffff (Erase
# state of flash). Choice of either/both deferred until implementation.

# ERB elements

# Events stored to the log have the general header format of
# ---
# Offset   Item
#      0   Type identifier (ChannelNew, ChannelRemove, NewSample, ChannelDump)
#      2   Record number
#      6   Total Length (including header)
#      8   Offset of previous event in ERB
# ---
# Using the length, one can scan headers to find specific events of
# interest.
EVENT_HEADER_FMT = ">HIII"
EVENT_HEADER_SIZE = struct.calcsize(EVENT_HEADER_FMT)


class EventHeader(object):
    ''' encapsulates a single event object header '''
    __slots__ = ['type', 'record', 'length', 'previous']

    def __init__(self, args):
        self.type = args[0]
        self.record = args[1]
        self.length = args[2]
        self.previous = args[3]

    def __repr__(self):
        if self.type == 0xffff:
            typename = "NONE"
        elif self.type >= MAX_TYPE:
            typename = "BAD"
        else:
            typename = EVENT_NAMES[self.type]

        return '<EventHeader: %s record %d length %d previous 0x%x>' % (
            typename, self.record, self.length, self.previous)

    def bin_repr(self):
        ''' return binary represtation of header '''
        return struct.pack(EVENT_HEADER_FMT,
                           self.type,
                           self.record,
                           self.length,
                           self.previous)


class NoEvent(Exception):
    pass


class BadEvent(Exception):
    pass


class EventApplicationException(Exception):
    pass


def read_event_hdr(fobj):
    ''' parse a hex string into an event hdr object '''
    hdr = EventHeader(struct.unpack(EVENT_HEADER_FMT,
                                    fobj.read(EVENT_HEADER_SIZE)))
    if hdr.type == 0x0 or hdr.type == 0xffff:
        raise NoEvent("NoEvent on event header read (0x%04x)" % hdr.type)
    elif hdr.type >= MAX_TYPE:
        raise BadEvent("Bad event on event header read (0x%04x)" % hdr.type)
    return hdr


# Events
CHANNEL_NEW    = 1
CHANNEL_REMOVE = 2
NEW_SAMPLE     = 3
CHANNEL_DUMP   = 4
PAD_EVENT      = 5
MAX_TYPE       = 6

EVENT_NAMES = ["NONE", "CHANNEL_NEW", "CHANNEL_REMOVE", "NEW_SAMPLE",
               "CHANNEL_DUMP", "PAD_EVENT"]

# All events have the same event representation.  ChannelDump simply
# repeats Sample serializations for all items that existed in the
# channel database at the time of the dump

# Offset   Item
#      0   Channel Name offset from nameDB
#      4   Serialization of Sample

# Sample serializing
# Samples as currently existing in the system contain three members
# (unit, value, timestamp).  When an event writes sample(s) to disk it
# uses a combination of the 'struct' (for unit and timestamp), and
# 'pickle' (for value) modules to do so.

# We will always pickle with protocol=1 currently because that
# provides the best overhead for the simple data that is intended to
# be primarily stored in Sample objects.

# Offset    Item
#      0    Unit offset (offset of unit string in nameDB)
#      4    Timestamp
#      8    Value (pickled)

SAMPLE_FMT = ">II"
SAMPLE_SIZE = struct.calcsize(SAMPLE_FMT)

# nameDB elements
# Offset    Item
#      0    Length
#      1    Name
# List of nameDB objects MUST be terminated with a final NULL byte


########
# interface

# classes

class FileLoggerStorageManagerOperation(object):
    """Abstract Base Class for all FileLoggerStoreManager operations."""
    PRI_HIGH = 0x1
    PRI_LOW = 0x2
    PRI_MAX = 0x2

    def __init__(self, priority):
        if (not isinstance(priority, int) or
            priority < 0 or
            priority > FileLoggerStorageManagerOperation.PRI_MAX):
            raise AttributeError("invalid priority '%s'" % repr(priority))
        self.priority = priority


class VolumeInit(FileLoggerStorageManagerOperation):
    """Opens or creates a new logger volume with the supplied parameters."""
    def __init__(self, filename, event_volume_size):
        self.filename = filename
        self.event_volume_size = event_volume_size
        FileLoggerStorageManagerOperation.__init__(self,
            priority=FileLoggerStorageManagerOperation.PRI_HIGH)


class StoreNewSample(FileLoggerStorageManagerOperation):
    '''
    Instructs the FileLoggerStoreManager to write a new sample to the log.
    '''
    def __init__(self, channel_name, sample):
        self.channel_name = channel_name
        self.sample = sample
        FileLoggerStorageManagerOperation.__init__(self,
            priority=FileLoggerStorageManagerOperation.PRI_LOW)


class StoreChannelNew(FileLoggerStorageManagerOperation):
    '''
    Instructs the FileLoggerStoreManager to add a new channel to the log.
    '''
    def __init__(self, channel_name, initial_sample):
        self.channel_name = channel_name
        self.sample = initial_sample
        FileLoggerStorageManagerOperation.__init__(self,
            priority=FileLoggerStorageManagerOperation.PRI_LOW)


class StoreChannelRemove(FileLoggerStorageManagerOperation):
    '''
    Instructs the FileLoggerStoreManager to remove a channel from the log.
    '''
    def __init__(self, channel_name, previous_sample):
        self.channel_name = channel_name
        self.sample = previous_sample
        FileLoggerStorageManagerOperation.__init__(self,
            priority=FileLoggerStorageManagerOperation.PRI_LOW)


class StoreChannelDump(FileLoggerStorageManagerOperation):
    '''
    Instructs the FileLoggerStoreManager to store a channel dump in
    the log.

    Channel dumps are used to increase the speed of seeking to
    specific points in the logging journal.

    Channel dumps are stored in this object as a mapping dictionary
    given as 'channel_dump_dict' mapping channel names to sample
    objects.
    '''
    def __init__(self, channel_dump_dict):
        self.channel_dict = channel_dump_dict
        FileLoggerStorageManagerOperation.__init__(self,
            priority=FileLoggerStorageManagerOperation.PRI_LOW)


class RetrievalOperationBase(FileLoggerStorageManagerOperation):
    def __init__(self, completion_cb=None):
        self.__tracer = get_tracer('RetrievalOperationBase')
        self.__cb = completion_cb
        FileLoggerStorageManagerOperation.__init__(self,
            priority=FileLoggerStorageManagerOperation.PRI_HIGH)

    def set_completion_cb(self, cb):
        self.__cb = cb

    def do_completion_callback(self, *args, **kwargs):
        ''' call on completion '''
        try:
            self.__cb(*args, **kwargs)
        except Exception, e:
            self.__tracer.warning('callback failed with: %s' % (str(e)))
            self.__tracer.debug(traceback.format_exc())


class RetrieveSeek(RetrievalOperationBase):
    '''
    Instructs the FileLoggerStoreManager to retrieve the next sample
    from the log.

    Calls the given callback upon completion.
    '''
    def __init__(self, offset, whence, record_index, completion_cb=None):
        self.offset = offset
        self.whence = whence
        self.record_index = record_index
        RetrievalOperationBase.__init__(self,
            completion_cb=completion_cb)


class RetrieveNext(RetrievalOperationBase):
    '''
    Instructs the FileLoggerStoreManager to retrieve the next sample
    from the log.

    Calls the given callback upon completion.
    '''
    pass


class RetrievePrevious(RetrievalOperationBase):
    '''
    Instructs the FileLoggerStoreManager to retrieve the previous
    sample from the log.

    Calls the given callback upon completion.
    '''
    pass


class FlushOperation(RetrievalOperationBase):
    '''
    Instructs the FileLoggerStoreManager to flush any pending data
    from memory to disk.

    Calls the given callback upon completion.
    '''
    pass


class StopOperation(FileLoggerStorageManagerOperation):
    '''
    Instructs the FileLoggerStoreManager to terminate its thread.

    This event will be enqueued automatically by calling the
    FileLoggerStoreManager's stop() method.
    '''
    def __init__(self):
        FileLoggerStorageManagerOperation.__init__(self,
            priority=FileLoggerStorageManagerOperation.PRI_HIGH)


class DBIEventBase(object):
    @staticmethod
    def from_op(record_position, op):
        raise NotImplementedError("virtual function")

    def __init__(self, record_position):
        self.record_position = record_position


class DBIEventChannelNew(StoreChannelNew, DBIEventBase):
    @staticmethod
    def from_op(record_position, op):
        if not isinstance(op, StoreChannelNew):
            raise TypeError("op must be of type StoreChannelNew")
        if not isinstance(record_position, (int, long)):
            raise TypeError("record_position must be integer")
        return DBIEventChannelNew(op.channel_name, op.sample, record_position)

    def __init__(self, channel_name, initial_sample, record_position):
        StoreChannelNew.__init__(self, channel_name, initial_sample)
        DBIEventBase.__init__(self, record_position)

    def __repr__(self):
        return "<%s: channel_name '%s' value '%s'>" % (
            self.__class__.__name__,
            self.channel_name,
            self.sample.value)


class DBIEventChannelRemove(StoreChannelRemove, DBIEventBase):
    @staticmethod
    def from_op(record_position, op):
        if not isinstance(op, StoreChannelRemove):
            raise TypeError("op must be of type StoreChannelRemove")
        if not isinstance(record_position, (int, long)):
            raise TypeError("record_position must be integer")
        return DBIEventChannelRemove(op.channel_name, op.sample,
                                     record_position)

    def __init__(self, channel_name, previous_sample, record_position):
        StoreChannelRemove.__init__(self, channel_name, previous_sample)
        DBIEventBase.__init__(self, record_position)

    def __repr__(self):
        return "<%s: channel_name '%s' value '%s'>" % (
            self.__class__.__name__,
            self.channel_name,
            self.sample.value)


class DBIEventNewSample(StoreNewSample, DBIEventBase):
    @staticmethod
    def from_op(record_position, op):
        if not isinstance(op, StoreNewSample):
            raise TypeError("op must be of type StoreNewSample")
        if not isinstance(record_position, (int, long)):
            raise TypeError("record_position must be integer")
        return DBIEventNewSample(op.channel_name, op.sample, record_position)

    def __init__(self, channel_name, sample, record_position):
        StoreNewSample.__init__(self, channel_name, sample)
        DBIEventBase.__init__(self, record_position)

    def __repr__(self):
        return "<%s: channel_name '%s' value '%s'>" % (
            self.__class__.__name__,
            self.channel_name,
            self.sample.value)


class DBIEventChannelDump(StoreChannelDump, DBIEventBase):
    @staticmethod
    def from_op(record_position, op):
        if not isinstance(op, StoreChannelDump):
            raise TypeError("op must be of type StoreChannelDump")
        if not isinstance(record_position, (int, long)):
            raise TypeError("record_position must be integer")
        return DBIEventChannelDump(op.channel_dict, record_position)

    def __init__(self, channel_dump_dict, record_position):
        StoreChannelDump.__init__(self, channel_dump_dict)
        DBIEventBase.__init__(self, record_position)

    def __repr__(self):
        return "<%s: num_channels %d>" % (
            self.__class__.__name__, len(self.channel_dict))


SINGLE_EVENT_MAP = {StoreChannelNew: CHANNEL_NEW,
                    StoreNewSample: NEW_SAMPLE,
                    StoreChannelRemove: CHANNEL_REMOVE}


def do_nothing(*args):
    ''' dummy method for OP_MAP '''
    pass


class FileLoggerStorageManager(threading.Thread):
    ''' presents a logger interface backed by a file '''

    def __init__(self, name, core_services, file_logger,
                    op_q_depths, file_write_q_depth):
        self.__name = name
        self.__core_services = core_services
        self.__file_logger = file_logger

        self.__tracer = get_tracer(name)

        ## Debug choices
        self.__debug_scan = False # re-scan & validate erb state after writes

        ## Storage Operations queue initialization
        self.__op_q_depths = op_q_depths
        self.__op_q_semaphore = threading.Semaphore(0)
        self.__op_q_pri_high = Queue.Queue(op_q_depths)
        self.__op_q_pri_low = Queue.Queue(op_q_depths)

        ## File Write Queue initialization and state information:
        self.__file_write_q_depth = file_write_q_depth
        self.__file_write_q = deque()
        self.__last_write = digitime.time()

        ## Scanned state from log file
        self._logfile = None
        self.__cdorb = deque() # List of ChannelDump offsets in ERB
        self.__names = {} # Maps channel names to offsets
        self.__offset_to_name_cache = {} # maps offsets to names on retrieval

        self.__record = -1
        self.__lastrecord = None
        self.__recordcursor = None

        self.__erb_off = None
        self.__nameDB_off = None

        self.__wraps = 0

        ## Retrieval pathway state information:
        self.__ret_off = None
        self.__ret_record = None
        self.__ret_last_prev = None

        ## mapping of operation types to methods
        self.__op_map = {VolumeInit: self.do_volume_init,
                       StoreNewSample: self.queue_write_event,
                       StoreChannelNew: self.queue_write_event,
                       StoreChannelRemove: self.queue_write_event,
                       StoreChannelDump: self.queue_write_event,
                       RetrieveSeek: self.do_retrieve_seek,
                       RetrieveNext: self.do_retrieve_next,
                       RetrievePrevious: self.do_retrieve_prev,
                       FlushOperation: self.do_flush_operation,
                       StopOperation: do_nothing}

        ## DBI:
        self.__logger_dbi = self.__file_logger.channel_database_get()

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    def start(self):
        """Start the FileLoggerStorageManager thread.  Returns bool."""
        threading.Thread.start(self)

        return True

    def stop(self):
        """Stop the FileLoggerStorageManager thread.  Returns bool."""
        self.__stopevent.set()
        self.queue_operation(StopOperation())
        self.join()
        return True

    def queue_operation(self, operation):
        if not isinstance(operation, FileLoggerStorageManagerOperation):
            raise TypeError("operation must be subclassed from "
                            " FileLoggerStorageManagerOperation")

        queue = None
        if operation.priority == FileLoggerStorageManagerOperation.PRI_HIGH:
            queue = self.__op_q_pri_high
        elif operation.priority == FileLoggerStorageManagerOperation.PRI_LOW:
            queue = self.__op_q_pri_low
        else:
            raise AttributeError("invalid operation priority '%s'" %
                                 repr(operation.priority))

        # Enqueue item in appropriate queue:
        try:
            queue.put_nowait(operation)
        except Queue.Full:
            self.__tracer.warning("no space in q, tossing '%s'",
                                  operation.__class__.__name__)
            return

        # Notify thread of new operation:
        # NOTE: This is not being used to protect a critical section,
        # and does not need to match an acquire in this method
        self.__op_q_semaphore.release()

    def run(self):
        """FileLoggerStorageManager thread execution beings here."""
        while 1:
            # Case 1: have we been requested to stop out thread?
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                # TODO: consider attempting to sync the write queue one final
                #       time.
                break

            # Case 2: if there are no pending operations and there
            #         are items in our file write queue, go and service
            #         the file write queue.  We must have more than 100
            #         entries in the queue, or not have written for at
            #         least a minute.  This helps us to use the flash
            #         file system effectively.:
            if (self.__op_q_pri_high.empty() \
                and self.__op_q_pri_low.empty() \
                and len(self.__file_write_q) \
                and (len(self.__file_write_q) > 100
                     or digitime.time() - self.__last_write > 60)):

                self.__tracer.info("Writing %d items at time %.2f",
                                   len(self.__file_write_q), digitime.time())

                if self.__debug_scan:  # pragma: no cover
                    pre_state = self._extract_state()

                self.empty_write_q()

                if self.__debug_scan:  # pragma: no cover
                    post_state = self._extract_state()

                    self._clear_state()
                    self._scan_erb()
                    self.__tracer.debug("Wraps: %d", self.__wraps)

                    scan_state = self._extract_state()
                    if post_state != scan_state:
                        from pprint import pformat
                        self.__tracer.debug("Pre-state: %s",
                                pformat(pre_state))
                        self.__tracer.debug("Post-state: %s",
                                pformat(post_state))
                        self.__tracer.debug("Scan-state: %s",
                                pformat(scan_state))
                        sys.exit()

                self.__last_write = digitime.time()
                continue

            # Case 3: wait for an operation to show up in one of our queues:
            self.__op_q_semaphore.acquire(True)

            # Get the operation:
            opr = None
            try:
                opr = self.__op_q_pri_high.get_nowait()
            except Queue.Empty:
                pass
            if opr is None:
                opr = self.__op_q_pri_low.get_nowait()

            # Dispatch the operation:
            self.__op_map.get(type(opr), do_nothing)(opr)

    def queue_write_event(self, op):
        if len(self.__file_write_q) >= self.__file_write_q_depth:
            self.__tracer.warning("Dropped log event, write queue full")
            return

        self.__file_write_q.append((self.__record, op))
        self.__record += 1

    def empty_write_q(self):
        ''' write all queued entries '''
        dq = self.__file_write_q

        while dq:
            #self.__tracer.info("dq: %s", dq)
            tmpcursor = self.__recordcursor
            tmplast = self.__lastrecord
            wrap = False

            writebuf = ''
            totallength = 0
            eventspan = 0

            while dq: # Can't decide we need to stop until we've serialized
                #self.__tracer.info("writebuf: %s", repr(writebuf))
                # pop an op
                record, op = dq.popleft()
                #self.__tracer.info("record: %s op: %s", record, op)

                # serialize event
                event, length = self._generate_event(op, record, tmplast)
                #self.__tracer.info("event: %s", repr(event))
                #self.__tracer.info("length: %s", length)

                # if it will fit place in write stream, else push back op
                newcursor = tmpcursor + length
                if self.__nameDB_off - newcursor >= EVENT_HEADER_SIZE:
                    # Keep CDORB up to date
                    self._clear_cdorb(tmpcursor, newcursor)

                    if isinstance(op, StoreChannelDump):
                        #self.__tracer.info("Append: ", (tmpcursor, record))
                        self.__cdorb.append((tmpcursor, record))

                    writebuf = writebuf + event
                    tmplast = tmpcursor
                    tmpcursor = newcursor
                    totallength += length
                    eventspan += length
                else:
                    #self.__tracer.warning("Can't fit another, break")
                    # Process later
                    dq.appendleft((record, op))
                    break # Time to write

#                self.__tracer.info("totallength: %s tmpcursor: %s tmplast: %s",
#                                   totallength, hex(tmpcursor), hex(tmplast))

#            self.__tracer.info("totallength: %s tmpcursor: %s tmplast: %s",
#                               totallength, hex(tmpcursor), hex(tmplast))

            endpad = False
            if len(dq) == 0:
                # Pad until next event
                try:
                    pad = self._pad_write(writebuf, totallength, tmplast)
                    writebuf = writebuf + pad
                except self.PlaceError:
                    endpad = True
            else:
                endpad = True

            #self.__tracer.info("endpad: %s", endpad)

            if endpad:
                # Pad until end of buffer (de facto next event)
                pad = EventHeader((PAD_EVENT,
                                   0,
                                   self.__nameDB_off - tmpcursor,
                                   tmplast)).bin_repr()

                writebuf = writebuf + pad
                wrap = True

            #self.__tracer.info("writebuf: %s", repr(writebuf))

            padhdr = struct.unpack(EVENT_HEADER_FMT, pad)
            padhdr = EventHeader(padhdr)
            eventspan += padhdr.length

            # Keep CDORB up to date

            self.__tracer.info("Clearing pad: %d - %d",
                               tmpcursor, tmpcursor + padhdr.length)
            self._clear_cdorb(tmpcursor,
                              tmpcursor + padhdr.length)

            # Write out padded event stream
            self._erb_seek(self.__recordcursor)
            self._logfile.write(writebuf)
            self._logfile.flush()

            if wrap:
                #self.__tracer.info("Wrapping")
                self.__wraps += 1
                # self.__tracer.info("Wrapped.  This was wrap number
                # %s", self.__wraps)
                self.__recordcursor = self.__erb_off
            else:
                #self.__tracer.info("NOT wrapping")
                self.__recordcursor += totallength

            self.__lastrecord = tmplast

    def _clear_cdorb(self, before, after):
        while (self.__cdorb and
                  self.__cdorb[0][0] >= before and
                  self.__cdorb[0][0] < after):
            self.__cdorb.popleft()

    def _generate_event(self, opr, record, lastrecord):
        ''' returns (rawhex, length) '''
        if type(opr) in SINGLE_EVENT_MAP:
            return self._generate_single_event(opr, record, lastrecord)
        elif isinstance(opr, StoreChannelDump):
            return self._generate_dump_event(opr, record, lastrecord)
        else:
            self.__tracer.warning('_generate_event called with unknown '
                                  'operation %s' % (str(opr)))

    def _generate_single_event(self, opr, record, lastrecord):
        ''' returns (event, size) where event is a byte string '''
        etype = SINGLE_EVENT_MAP.get(type(opr))
        if etype == None:
            raise BadEvent('_generate_single_event passed '
                           'bad op type %s' % (str(opr)))
        channel_off = self._get_name_offset(opr.channel_name)
        channel_off = struct.pack('>I', channel_off)

        sample = self._format_sample(opr.sample)

        size = EVENT_HEADER_SIZE + len(channel_off) + len(sample)
        header = EventHeader((etype, record, size, lastrecord)).bin_repr()

        event = ''.join((header, channel_off, sample))
        return event, size

    def _generate_dump_event(self, op, record, lastrecord):
        body = ""

        for name in op.channel_dict:
            channel_off = self._get_name_offset(name)
            channel_off = struct.pack('>I', channel_off)

            sample = self._format_sample(op.channel_dict[name])

            body += channel_off + sample

        size = EVENT_HEADER_SIZE + len(body)
        header = EventHeader((CHANNEL_DUMP,
                              record, size,
                              lastrecord)).bin_repr()

        event = header + body
        return event, size

    class PlaceError(Exception):
        pass

    def _pad_write(self, event, length, lastrecord):
        # If we can find another valid event before the end of the
        # buffer, we will create a pad event to bring us to it.
        # Otherwise, we will just stick a sentinal on the end to stop
        # traversal when someone else comes along, we may still be
        # able to write there
        cursor = self.__recordcursor
        end = cursor + length

        while cursor < end:
            cursor = self._next_event(cursor)

            if cursor == self.__nameDB_off:
                break

        padlength = cursor - end

        if padlength < EVENT_HEADER_SIZE:
            if cursor == self.__nameDB_off:
                raise self.PlaceError
            # Always need at least enough room for a full header
            cursor = self._next_event(cursor)

        padlength = cursor - end
        pad = EventHeader((PAD_EVENT,
                           0,
                           padlength,
                           lastrecord)).bin_repr()

        if padlength and padlength < EVENT_HEADER_SIZE:
            raise RuntimeError

        if padlength != 0:
            return pad

        return ""

    def _next_event(self, cursor, wrap=False):
        self._erb_seek(cursor)
        hdr = read_event_hdr(self._logfile)
        return cursor +  hdr.length

    def _format_sample(self, sample):
        unit_off = self._get_name_offset(sample.unit)
        hdr = struct.pack(SAMPLE_FMT, unit_off, int(sample.timestamp))
        return hdr + pickle.dumps(sample.value, protocol=1)

    def _get_name_offset(self, name):
        # Keep names less than 256 bytes
        if len(name) > 255:
            name = name[:256]

        if len(name) == 0:
            name = " " # Can't store the empty string

        # Lookup the name first in our dict
        if name in self.__names:
            return self.__names[name]

        # If not found, insert it into the log file and return the new offset
        self._logfile.seek(0, 2) # End of file, should be \x00
        offset = self._logfile.tell()
        self._logfile.write(chr(len(name)))
        self._logfile.write(name)
        self._logfile.flush()
        self.__names[name] = offset

        return offset

    def _get_name_by_offset(self, name_offset):
        if name_offset in self.__offset_to_name_cache:
            return self.__offset_to_name_cache[name_offset]

        self._logfile.seek(name_offset)
        name_len = ord(self._logfile.read(1))
        name = self._logfile.read(name_len)

        self.__offset_to_name_cache[name_offset] = name
        return name

    def do_volume_init(self, op):
        try:
            self.logfile_startup(op)
        except Exception, e:
            self.__tracer.error(repr(e))
            self.__tracer.error("Bad logfile, re-creating")
            # If we encounter an error during the scanning of the log,
            # we will delete it and start anew.  Of course, if that
            # fails the world will end so we can't loop.
            if self._logfile:
                self._logfile.close()
                self._logfile = None
            try:
                os.remove(op.filename)
            except OSError:
                pass

            self.logfile_startup(op)

        # Always populate a channel dump when we're starting.  This
        # assists the DBI interface in that it can always LOG_SEEK_END
        # from this point.
        self.queue_write_event(StoreChannelDump(dict()))
        self.empty_write_q()

        self._dbi_initialize()

    def logfile_startup(self, op):
        ''' initialize internal state variables and open the log file '''
        try:
            os.stat(op.filename)
        except OSError:
            exist = False
        else:
            exist = True

        if not exist:
            self._create_logfile(op)

        # Read-only and buffered so that stdio can optimize seeks and
        # overall scanning time is faster.  This is an optimization
        # that benefits the Digi file-system enormously because we
        # don't know why it has long access times when going to flash.
        # If logging to another flash device like a USB drive, this
        # provides the wrong behavior, although still
        # semi-reasonable. You may wish to provide unbuffered access
        # however because seeks are really cheap there.

        # TODO: change this fopen behavior based on the platform?
        self._logfile = file(op.filename, "rb", 4096)

        self._logfile.seek(0)
        # Verify we're looking at a good logfile
        hdr = self._logfile.read(LOG_HDR_SIZE)
        magic, self.__erb_off, self.__nameDB_off, name_length = \
               struct.unpack(LOG_HDR_FMT, hdr)

        if magic != MAGIC:
            raise IOError("%s(%s): : Bad log file" %
                          (self.__class__.__name__, self.__name))

        self.__tracer.info("Log self identifies as instance: ")
        self.__tracer.info(self._logfile.read(name_length))

        self._scan_erb()
        self._scan_names()

        # For true operation we need write access and we want
        # immediate commits of write buffers for better record sanity.
        self._logfile.close()
        self._logfile = file(op.filename, "rb+", 0)

    def _create_logfile(self, op):
        self._logfile = file(op.filename, "wb+", 0)
        length = len(self.__name)
        creation_fmt = LOG_HDR_FMT + "%ds" % length
        erb_off = struct.calcsize(creation_fmt)
        nameDB_off = erb_off + op.event_volume_size

        hdr = struct.pack(creation_fmt, MAGIC,
                          erb_off, nameDB_off,
                          length, self.__name)
        self._logfile.write(hdr)
        # ERB - one big pad event
        hdr = EventHeader((PAD_EVENT,
                           0,
                           op.event_volume_size,
                           erb_off)).bin_repr()
        self._logfile.write(hdr)

        length = op.event_volume_size - EVENT_HEADER_SIZE
        while length:
            # Don't write it all at once to avoid creating a huge
            # string in memory
            sz = max(512, length)
            self._logfile.write('\xff' * sz)
            length -= sz

        #self._logfile.write('\x00') # nameDB
        self._logfile.close()
        self._logfile = None

    def _scan_erb(self):
        # Traverse the entire ERB building the __cdorb list in memory
        # by adding a new offset value each time we encounter a
        # ChannelDump event

        #self.__tracer.info("Beginning event scan")
        begin = digitime.time()

        offset = self.__erb_off
        records = 0
        dumps = 0

        while offset < self.__nameDB_off:
            # Read in an event header
            self._erb_seek(offset)

            try:
                hdr = read_event_hdr(self._logfile)
            except NoEvent:
                # Hit the end of events in the ERB
                break

            records += 1

            #self.__tracer.info("0x%x: %s" % (offset, repr(hdr)))

            if hdr.type == CHANNEL_DUMP:
                # Add this offset to cdorb
                self.__cdorb.append((offset, hdr.record))
                dumps += 1

            if hdr.record >= self.__record:
                self.__record = hdr.record + 1
                self.__lastrecord = offset
                self.__recordcursor = offset + hdr.length

                if self.__recordcursor == self.__nameDB_off:
                    self.__recordcursor = self.__erb_off

            offset += hdr.length

        self.__tracer.info("Found %d channel dump events", dumps)
        self.__tracer.info("Starting at record %d", self.__record)

        end = digitime.time()
        span = end - begin

        if span:
            self.__tracer.info("Scan: %d records, %.2f seconds.  "
                               "%.2f records/sec",
                               records, span, records / span)

        # Rotate the CDORB so that it has the right relationship to
        # the advancing record cursor for us to maintain it as we
        # write out.

        # If record cursor is greater than any record offset in the
        # cdorb, we're already in the correct state
        if self.__cdorb and self.__recordcursor < self.__cdorb[-1][0]:
            while self.__cdorb[0][0] < self.__recordcursor:
                self.__cdorb.rotate(-1)

    def _scan_names(self):
        # Build name database in memory
        offset = self.__nameDB_off
        names = 0

        while True:
            self._logfile.seek(offset)

            length = self._logfile.read(1)
            if not length:
                break # End of file
            length = ord(length)
            name = self._logfile.read(length)

            if not length:
                break

            self.__names[name] = offset

            names += 1
            offset += length + 1

        self.__tracer.info("Found %d names", names)

    def do_retrieve_next(self, op):
        try:
            ret = self._seek(1, LOG_SEEK_CUR)
        except Exception, e:
            ret = e
        op.do_completion_callback(ret)

    def do_retrieve_prev(self, op):
        try:
            ret = self._seek(-1, LOG_SEEK_CUR)
        except Exception, e:
            ret = e
        op.do_completion_callback(ret)

    def do_retrieve_seek(self, op):
        try:
            ret = self._seek(offset=op.offset, whence=op.whence,
                             record_index=op.record_index)
        except Exception, e:
            ret = e
        op.do_completion_callback(ret)

    def do_flush_operation(self, op):
        try:
            self.__tracer.warning("Writing %d items at time %.2f",
                len(self.__file_write_q), digitime.time())
            self.empty_write_q()
            self.__last_write = digitime.time()
            ret = True
        except Exception, e:
            ret = e
        op.do_completion_callback(ret)

    def _erb_seek(self, offset):
        if offset >= self.__nameDB_off:
            raise RuntimeError(hex(offset))

        if offset < self.__erb_off:
            raise RuntimeError(hex(offset))

        self._logfile.seek(offset)

    def _retrieve_erb_event(self, event_header):
        '''
        Retrieves the event from the current ERB location as described by
        the given event header 'event_header'.

        This method is most useful when used after a call to the helper
        method read_event_hdr()
        '''
        if event_header.type == PAD_EVENT:
            raise NoEvent("pad event")
        ret_event = None
        sio = StringIO.StringIO(self._logfile.read(event_header.length))
        if event_header.type in SINGLE_EVENT_MAP.values():
            fmt_size = struct.calcsize(">I")
            channel_off = struct.unpack(">I", sio.read(fmt_size))[0]
            fmt_size = struct.calcsize(SAMPLE_FMT)
            unit_off, timestamp = struct.unpack(SAMPLE_FMT, sio.read(fmt_size))
            value = pickle.load(sio)
            channel_name = self._get_name_by_offset(channel_off)
            unit_name = self._get_name_by_offset(unit_off)
            sample = Sample(timestamp=timestamp, value=value, unit=unit_name)

            if event_header.type == CHANNEL_NEW:
                ret_event = DBIEventChannelNew(channel_name=channel_name,
                                            initial_sample=sample,
                                            record_position=event_header.record)
            elif event_header.type == CHANNEL_REMOVE:
                ret_event = DBIEventChannelRemove(channel_name=channel_name,
                                            previous_sample=sample,
                                            record_position=event_header.record)
            else:
                ret_event = DBIEventNewSample(channel_name=channel_name,
                                            sample=sample,
                                            record_position=event_header.record)

        elif event_header.type == CHANNEL_DUMP:
            channel_dict = {}
            while sio.tell() < (event_header.length - EVENT_HEADER_SIZE - 1):
                fmt_size = struct.calcsize(">I")
                channel_off = struct.unpack(">I", sio.read(fmt_size))[0]
                fmt_size = struct.calcsize(SAMPLE_FMT)
                unit_off, timestamp = struct.unpack(SAMPLE_FMT,
                                                    sio.read(fmt_size))
                value = pickle.load(sio)
                channel_name = self._get_name_by_offset(channel_off)
                unit_name = self._get_name_by_offset(unit_off)
                channel_dict[channel_name] = Sample(
                                                timestamp=timestamp,
                                                value=value,
                                                unit=unit_name)
            ret_event = DBIEventChannelDump(channel_dump_dict=channel_dict,
                                        record_position=event_header.record)
        else:
            raise ValueError("unknown event type: 0x02x" % event_header.type)

        sio.close()
        return ret_event

    def __closest_cdo_to(self, record_number, forward_retry):
        sorted_cdorb = sorted(self.__cdorb, key=operator.itemgetter(1))
        sorted_records = [ cdo[1] for cdo in sorted_cdorb ]
        bisect_result = bisect.bisect_left(sorted_records, record_number)
        if forward_retry:
            bisect_result = max(0, bisect_result-1)
        try:
            cdo = sorted_cdorb[bisect_result]
            if bisect_result > 0 and cdo[1] > record_number:
                # favor CDORB entries with lower record numbers than our needle:
                return sorted_cdorb[bisect_result - 1]
            return cdo
        except IndexError:
            # All channel dumps are /less/ than the desired record, return
            # the last CDORB entry:
            return sorted_cdorb[-1]

    def __create_event_from_q_op(self, record, op):
        if isinstance(op, StoreChannelNew):
            return DBIEventChannelNew.from_op(record, op)
        elif isinstance(op, StoreChannelRemove):
            return DBIEventChannelRemove.from_op(record, op)
        elif isinstance(op, StoreNewSample):
            return DBIEventNewSample.from_op(record, op)
        elif isinstance(op, StoreChannelDump):
            return DBIEventChannelDump.from_op(record, op)
        else:
            raise Exception("unsupported op type: %s" % op.__class__.__name__)

    def __write_q_seek(self, record_index):
        # determine if the offset exists in the file_write_q:
        if len(self.__file_write_q) == 0:
            raise NoEvent("File write queue empty")

        if not (record_index >= self.__file_write_q[0][0] and
            record_index <= self.__file_write_q[-1][0]):
            # record not in memory buffer
            raise NoEvent("record %d not in file write queue" % record_index)

        # Invalidate disk offset:
        self.__ret_off = None

        # scan-forward replaying events up until event record is replayed:
        i = 0
        while 1:
            record, op = self.__file_write_q[i]
            event = self.__create_event_from_q_op(record, op)
            self.__logger_dbi._apply_event(event)
            self.__ret_record = record
            if record >= record_index:
                break
            i += 1

    def __next_offset(self, cur_off, hdr):
        offset = cur_off + hdr.length
        if offset >= self.__nameDB_off:
            offset = self.__erb_off
        return offset

    def __prev_offset(self, cur_off, hdr):
        return hdr.previous

    def __finished_chk_forward(self, prev_hdr, hdr, cur_off):
        ''' return True if we've hit the end '''
        # if there is pad, we've hit the end
        if hdr and hdr.type == PAD_EVENT:
            return True
        # if we overlap
        if prev_hdr and hdr:
            if prev_hdr.record >= hdr.record:
                return True
        return False

    def __finished_chk_reverse(self, prev_hdr, hdr, cur_off):
        ''' return True if we've hit the front '''
        if hdr and hdr.type == PAD_EVENT:
            return True
        if prev_hdr and hdr:
            if prev_hdr.record <= hdr.record:
                return True
        return False

    def __seek_earliest_rec(self):
        """Find the earliest record number in the logging storage system."""
        cur_off, record_index = self.__cdorb[0]
        prev_hdr = None
        while 1:
            self._erb_seek(cur_off)
            try:
                hdr = read_event_hdr(self._logfile)
            except Exception:
                # If the log is in good shape, we just ran off the beginning
                break
            if hdr.type == PAD_EVENT:
                break
            if self.__finished_chk_reverse(prev_hdr, hdr, cur_off):
                break
            record_index = hdr.record
            prev_hdr = hdr
            cur_off = self.__prev_offset(cur_off, hdr)

        return record_index

    def __seek_latest_rec(self):
        """Find the latest record number in the logging storage system."""
        # Optimal case, we have an entry in the file_write_q:
        if len(self.__file_write_q):
            # the latest record is the last record in the queue:
            return self.__file_write_q[-1][0]

        # Otherwise, we must find the record number on disk:
        cur_off, record_index = self.__cdorb[-1]
        prev_hdr = None
        while 1:
            print 'inside seek loop'
            self._erb_seek(cur_off)
            hdr = read_event_hdr(self._logfile)
            if self.__finished_chk_forward(prev_hdr, hdr, cur_off):
                break
            record_index = hdr.record
            prev_hdr = hdr
            cur_off = self.__next_offset(cur_off, hdr)

        return record_index

    def __seek_offset_from_cur(self, offset):
        # Define disk seeking methods appropriate for offset direction:
        apply_method = self.__logger_dbi._apply_event
        next_offset = self.__next_offset
        finished_chk = self.__finished_chk_forward
        if offset < 0:
            apply_method = self.__logger_dbi._apply_event_inverse
            next_offset = self.__prev_offset
            finished_chk = self.__finished_chk_reverse
        apply_first = (self.__ret_last_prev is None or
                           self.__ret_last_prev ^ (offset < 0))

        # Perform the seek, applying events:
        terminal_offset = abs(offset)
        prev_hdr = None
        cur_off = self.__ret_off
        i = 0
        while 1:
            self._erb_seek(cur_off)
            try:
                hdr = read_event_hdr(self._logfile)
            except BadEvent:
                raise NoEvent("end of log on disk")
            if finished_chk(prev_hdr, hdr, cur_off):
                raise NoEvent("no previous record")

            if hdr.type == PAD_EVENT:
                # Skip processing of PAD_EVENT
                cur_off = next_offset(cur_off, hdr)
                continue

            event = self._retrieve_erb_event(hdr)
            if i > 0 or apply_first:
                # only apply the first record if we have changed
                # directions since the last operation:
                try:
                    apply_method(event)
                except:
                    raise EventApplicationException

            self.__ret_off, self.__ret_record = cur_off, hdr.record
            prev_hdr = hdr
            cur_off = next_offset(cur_off, hdr)
            if i >= terminal_offset and hdr.type != PAD_EVENT:
                break
            i += 1

    def _seek(self, offset=0, whence=LOG_SEEK_SET, record_index=None,
              _forward_retry=False):
        '''
        Move the current position.
        '''
        cdo = None

        if len(self.__file_write_q):
            self.__tracer.info("BOUNDARY: %s", self.__file_write_q[0][0])

        # Step 1: re-write all seeks in terms of a seek to an absolute
        #         record number (LOG_SEEK_REC)
        if whence == LOG_SEEK_SET:
            if offset < 0:
                raise NoEvent("offset must be positive with LOG_SEEK_SET")
            record_index = self.__seek_earliest_rec() + offset
        elif whence == LOG_SEEK_CUR:
            if self.__ret_record == None:
                raise Exception("No current record set")
            record_index = self.__ret_record + offset
        elif whence == LOG_SEEK_END:
            if offset > 0:
                raise NoEvent("offset must be negative with LOG_SEEK_END")
            record_index = self.__seek_latest_rec() + offset
        elif whence == LOG_SEEK_REC:
            record_index = record_index + offset
        else:
            raise ValueError("unknown whence: %s" % whence)

        # Step 2: attempt to locate a cdorb entry if:
        #           a) We do not have a current disk offset because the
        #              previous operation was in memory.
        #           b) The requested record_index is more than halfway to
        #              the next index marker.
        idx_frequency = self.__file_logger.get_setting(
            'sample_index_frequency')

        if (self.__ret_off is None or self.__ret_record is None or
             (abs(record_index - self.__ret_record) > (idx_frequency // 2)) or
             _forward_retry):
            cdo = self.__closest_cdo_to(record_index, _forward_retry)
            self.__tracer.info("USING CDORB: %s", repr(cdo))

        # Step 3: if we have a cdorb entry, seek to and apply it:
        if cdo is not None:
            self._erb_seek(cdo[0])
            try:
                hdr = read_event_hdr(self._logfile)
            except:
                raise Exception("unable to seek to channel dump index offset")
            try:
                event = self._retrieve_erb_event(hdr)
            except:
                raise Exception("unable to retrieve initial channel dump event")
            try:
                self.__logger_dbi._apply_event(event)
            except Exception, e:
                raise Exception("unable to apply initial channel dump: %s" %
                                str(e))
            self.__ret_off, self.__ret_record = cdo
            self.__ret_last_prev = None

        # Step 4: Seek and apply events from disk:
        seek_exc = None
        try:
            self.__seek_offset_from_cur(record_index - self.__ret_record)
        except NoEvent, e:
            seek_exc = e
        except EventApplicationException, e:
            self.__tracer.error("EventApplicationException!")
            if _forward_retry:
                raise
            self._seek(offset, whence, record_index, _forward_retry=True)

        # Step 5: NoEvent? For CUR, REC, & END try memory:
        if isinstance(seek_exc, NoEvent):
            try:
                if whence in (LOG_SEEK_CUR, LOG_SEEK_REC, LOG_SEEK_END):
                    self.__write_q_seek(record_index)
                else:
                    raise seek_exc
            except NoEvent:
                raise seek_exc

        self.__ret_last_prev = (offset < 0)

    def _dbi_initialize(self):
        '''
        Initialize the DBI to the earliest state in the event ring buffer.
        '''
        try:
            self._seek(offset=0, whence=LOG_SEEK_SET)
        except:
            self.__ret_off = self.__recordcursor

    def _extract_state(self):
        ''' return a deep copy of the state '''
        return deepcopy((self.__record,
                         self.__lastrecord,
                         self.__recordcursor,
                         self.__cdorb))

    def _clear_state(self):
        ''' reset the file logger storage manager '''
        self.__record = -1
        self.__lastrecord = None
        self.__recordcursor = None
        self.__cdorb.clear()
