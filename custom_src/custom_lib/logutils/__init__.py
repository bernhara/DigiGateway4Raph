"""The logutils package is a library developed by Spectrum targeted for use
on Digi products. It contains logging features that have been found useful 
on multiple projects.
"""

import sys
import os
import logging
import cStringIO

try:
    _fsync = os.fsync
except AttributeError:
    import warnings
    warnings.warn("os.fsync is not available so some logged data may be lost")
    def _fsync(fd):
        pass

def basicConfig(filename=None,
                stream=sys.stderr,
                format="%(asctime)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                formatter=logging.Formatter):
    """Do basic configuration for the logging system.

    This function does nothing if the root logger already has handlers
    configured. It is a convenience method intended for use by scripts
    to do one-shot configuration of the logging package.

    The default behavior is to add a :class:`logging.StreamHandler` which writes 
    to sys.stderr to the root logger.

    A number of optional keyword arguments may be specified, which can alter
    the default behavior:

    * filename - Specifies that a :class:`SmartHandler` be created, using the 
      specified filename, in addition to the StreamHandler.
    * stream - Use the specified stream to initialize the StreamHandler. If
      ``None`` the :class:`logging.StreamHandler` will not be used.
    * format - Use the specified format string for the handler.
    * datefmt - Use the specified date/time format.
    * formatter - Use the specified Formatter class instead of :class:`logging.Formatter`.
      
    .. note::
    
       Unlike :func:`logging.basicConfig`, this function can create *both*
       a StreamHandler and a FileHandler (actually a :class:`SmartHandler`.

    Note that you could specify a stream created using open(filename, mode)
    rather than passing the filename and mode in. However, it should be
    remembered that StreamHandler does not close its stream (since it may be
    using sys.stdout or sys.stderr), whereas FileHandler closes its stream
    when the handler is closed.
    """
    logger = logging.getLogger()
    if len(logger.handlers) == 0:
        fmt = formatter(format, datefmt)
        if stream is not None:
            handler = logging.StreamHandler(stream)
            handler.setFormatter(fmt)
            logger.addHandler(handler)
        if filename is not None:
            handler = SmartHandler(filename=filename)
            handler.setFormatter(fmt)
            logger.addHandler(handler)
    
class TimeStampFormatter(logging.Formatter):
    """Instead of using :func:`time.strftime` to format the time, this
    formatter uses normal string formatting codes. This can be useful on devices
    that may not keep accurate time (ex: ConnectPort X2).
    """
    def __init__(self, fmt=None, datefmt=None):
        logging.Formatter.__init__(self, fmt, datefmt)
        
    def formatTime(self, record, datefmt=None):
        return self.datefmt % record.created

class SmartHandler(logging.Handler):
    """Logs to a in-memory buffer and to file(s) with automatic rollover.
    """
    def __init__(self,
                 buffer_size=50, 
                 filename=None, max_bytes=512*2*32, max_backups=5, 
                 flush_level=logging.ERROR,
                 flush_window=300):
        """Initialize the SmartHandler. It optionally logs records to an
        in-memory buffer and/or to file with automatic backups.
        
        The in-memory buffer is configured with the *buffer_size* parameter.
        Set *buffer_size* to a positive integer to set the maximum number
        of entries the buffer can hold, to 0 to create an unlimited buffer
        (not recommended with limited memory) and `None` to disable the
        buffer completely. When *buffer_size* is a positive integer
        it makes the buffer act as a "sliding window", meaning that once
        it is full, a new entry will cause the oldest entry to be deleted.
    
        The file logging is configured with *filename*, *max_bytes* and
        *max_backups*. Set *filename* to a filename to log to or `None`
        to disable file logging. Set *max_bytes* to an integer greater 
        than 0 to limit the size of the log file or to 0 or `None` to
        allow the log file to grow indefinitely (not recommended). Set
        *max_backups* to an integer greater than 0 to keep up to that
        many backups of previous log files or to 0 or `None` to disable
        the automatic backups. So for example, if you set *filename*
        to 'WEB/python/log.txt', *max_bytes* to 4096 and *max_backups*
        to 3, the latest log records will always be in WEB/python/log.txt.
        The next newest log will be in WEB/python/log.1.txt, the next
        in WEB/python/log.2.txt, and the last in WEB/python/log.3.txt.
        When adding a new log record to WEB/python/log.txt would cause
        it to exceed 4096 bytes the file is closed, WEB/python/log.2.txt
        is renamed to WEB/python/log.3.txt, WEB/pythong/log.1.txt is
        renamed to WEB/python/log.2.txt, WEB/python/log.txt is renamed
        to WEB/python/log.1.txt and a new WEB/python/log.txt file is
        created.
        
        The *flush_level* and *flush_window* parameters control
        how the log records are taken from the buffer (if configured)
        and saved in the log file (if configured). The *flush_level*
        should be set to a level understood by the logging facility.
        By default it is set to :attr:`logging.ERROR`. Any time
        the handler receives a log record at *flush_level* or above
        it will flush some or all of the contents of the buffer
        to the file. How much of the buffer is controlled by the
        *flush_window* parameter. This is the number of seconds
        of log data from the buffer to flush to the log file and
        it defaults to 300 seconds which is 5 minutes. The idea
        is to keep unimportant information from filling up the log
        files except when that seemingly unimportant information
        comes close to a critical log record where it may help
        to debug a exception or otherwise better understand a 
        problem. Set *flush_window* to 0 or None to flush all
        the records in the buffer to the file.
        """
        logging.Handler.__init__(self)
        self.filename = filename
        self.max_bytes = max_bytes
        self.max_backups = max_backups
        self.buffer_size = buffer_size
        self.last_flushed_index = -1
        self.buffer = []
        self.flush_level = flush_level
        self.flush_window = flush_window
        
    def emit(self, record):
        # Always put the record in the buffer, even if buffer is
        # disabled, because flush works on the buffer.
        self.buffer.append(record)
        if self.should_flush(record):
            self.flush()
        # If buffering is disabled, effectively remove the item
        # from the buffer by reinitializing the buffer.
        if self.buffer_size is None:
            self.buffer = []
        # Otherwise, if the buffer has a limited size, pop items
        # off the left until it is the correct size. This will
        # usually pop a single item once the buffer reaches capacity.
        elif self.buffer_size > 0:
            while len(self.buffer) > self.buffer_size:
                self.buffer.pop(0)
                self.last_flushed_index -= 1
            
    def should_flush(self, record):
        return record.levelno >= self.flush_level
    
    def flush(self):
        """Flush the records in the buffer to the log file if file logging
        is enabled.
        """
        record = None
        try:      
            if self.file_logging_enabled():
                retries_left = 3
                while True:
                    try:
                        log_file = open(self.filename, 'a')
                        try:
                            available_bytes = self.max_file_size() - self.get_file_length(log_file)
                            msg_buffer = cStringIO.StringIO()
                            for index, record in self.records_to_flush():
                                msg = "%s\n" % self.format(record)
                                # Check to see if there is enough room in the file to fit another message
                                if len(msg) > available_bytes:
                                    # There isn't enough room in the file for any more messages, so write
                                    # all the messages in the message buffer into the file, flush it and
                                    # fsync it to make sure it is actually written to the file system.
                                    msgs = msg_buffer.getvalue()
                                    msg_buffer.close()
                                    log_file.write(msgs)
                                    log_file.flush()
                                    _fsync(log_file)
                                    log_file.close()
         
                                    # Now that the records have been flushed we can update
                                    # the last flushed index
                                    self.last_flushed_index = index
                                    
                                    # Now do the rolloever of the backup copies, if enabled.
                                    self.do_rollover()
                                    
                                    # Now start a new log file and reinitialize the important vars. 
                                    log_file = open(self.filename, 'w')
                                    msg_buffer = cStringIO.StringIO()
                                    available_bytes = self.max_file_size()
        
                                msg_buffer.write(msg)
                                available_bytes -= len(msg)
                                
                            msgs = msg_buffer.getvalue()
                            msg_buffer.close()
                            log_file.write(msgs)
                            
                            # Now that we are finished flushing the buffer, update the
                            # last_flushed_index to indicate the entire buffer has been
                            # flushed.
                            self.last_flushed_index = len(self.buffer) - 1
                            
                            break # Break out of retry loop since we didn't get any IO errors
                        finally:
                            log_file.flush()
                            _fsync(log_file)
                            log_file.close()
                    except (OSError, IOError):
                        retries_left -= 1
                        if retries_left == 0:
                            raise
                    else:
                        break                    
        except:
            self.handleError(record)
                
    def records_to_flush(self):
        """Return a list of tuples, each containing the index of the record and
        the record itself for the records that should be flushed.
        """
        records = []
        for index, record in enumerate(self.buffer[self.last_flushed_index+1:]):
            if (self.flush_window is None or
                self.flush_window == 0 or 
                (self.buffer[-1].created - record.created) <= self.flush_window):
                records.append((index + self.last_flushed_index + 1, record))        
        return records
    
    def get_file_length(self, open_file):
        open_file.seek(0, 2)
        return open_file.tell()
                
    def max_file_size(self):
        """Returns the maximum size a log file can grow up to.
        """
        if self.file_limits_enabled():
            return self.max_bytes
        else:
            return sys.maxint
        
    def file_limits_enabled(self):
        return (self.max_bytes is not None and self.max_bytes > 0)
    
    def file_logging_enabled(self):
        """Returns `True` if file logging is enabled.
        """
        return (self.filename is not None)
    
    def rollover_enabled(self):
        """Returns `True` if automatic backup of log files is enabled.
        """
        return (self.max_backups is not None and self.max_backups > 0)

    def do_rollover(self):
        """Rollover the log file backups if backups are enabled.
        """
        if self.rollover_enabled():
            for i in range(self.max_backups - 1, 0, -1):
                sfn = (".%d" % i).join(os.path.splitext(self.filename))
                dfn = (".%d" % (i + 1)).join(os.path.splitext(self.filename))
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = ".1".join(os.path.splitext(self.filename))
            if os.path.exists(dfn):
                os.remove(dfn)
            os.rename(self.filename, dfn)

    def get_formatted_buffer(self, formatter=None):
        """Get a list of all the formatted log messages using the Formatter
        specified by *formatter* or the default Formatter if *formatter* is
        `None`.
        """
        if formatter is None:
            formatter = self.formatter
        for record in self.buffer[:]:
            yield formatter.format(record)
