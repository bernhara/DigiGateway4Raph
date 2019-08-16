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

'''
The FileLogger writes samples to a persistent storage device such as a
file stored on the flash file system.
'''

# imports
from settings.settings_base import SettingsBase, Setting

from channels.channel import OPT_DONOTLOG
from channels.logging.logger_base import LoggerBase
from channels.logging.logging_events import \
    LoggingEventNewSample, LoggingEventChannelNew, LoggingEventChannelRemove
from channels.logging.file_logger.file_logger_channel_dbi import \
    FileLoggerChannelDBI
from channels.logging.file_logger.file_logger_storage_manager import \
    FileLoggerStorageManager, VolumeInit, \
    StoreNewSample, StoreChannelNew, StoreChannelRemove, \
    StoreChannelDump
from common.path_utils import create_full_path

# constants
OP_Q_DEPTH = 512
FILE_WRITE_Q_DEPTH = 512
DEFAULT_SAMPLE_INDEX_FREQUENCY = 128

# interface

# classes
class FileLogger(LoggerBase):
    '''
    Logs data to a file.

    Provides a LoggerBase interface and interfaces to a
    FileLoggerStorageManager in order to log events to a file on a
    file system accessible to the Python core.
    '''
    def __init__(self, name, core_services):
        # Basic logger instance state data:
        self.__name = name
        self.__core_services = core_services

        settings_list = [
            Setting(
                name='filename', type=str, required=True),
            Setting(
                name='event_volume_size_k', type=int, required=False,
                default_value=50),
            Setting(
                name='include_channel_prefixes', type=list, required=False,
                default_value=[]),
            Setting(
                name='exclude_channel_prefixes', type=list, required=False,
                default_value=[]),
            Setting(
                name='sample_index_frequency', type=int, required=False,
                default_value=DEFAULT_SAMPLE_INDEX_FREQUENCY),
        ]

        # State information:
        self.__logging_started = False
        self.__log_storage_mgr = None
        self.__ops_since_last_dump = 0
        self.__logger_dbi = FileLoggerChannelDBI(
                                op_req_method=self._queue_operation)
        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)
        LoggerBase.__init__(self, name=name, settings_list=settings_list)

    def log_event(self, logging_event):
        '''
        Called when we should log a new event

        :param event: the new event
        :type event: child of LoggingEventBase
        '''
        # Initialize the logging storage volume:
        ops = self._create_operations(logging_event)
        for op in ops:
            try:
                self._queue_operation(op)
            except Exception, e:
                self.__tracer.error("storage manager queue: %s", str(e))

    def _queue_operation(self, op):
        if self.__log_storage_mgr is None:
            raise Exception("%s._queue_operation(%s): log storage manager " \
                              "is not ready" % (
                    self.__class__.__name__, self.__name))
        self.__log_storage_mgr.queue_operation(op)

    def channel_database_get(self):
        # TODO: return our instance of the correct DBI
        return self.__logger_dbi

    def apply_settings(self):
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            self.__tracer.error("settings rejected/not found: %s/%s",
                                rejected, not_found)

        # Initialize the logging storage volume:
        if self.__log_storage_mgr is not None and not self.__logging_started:
            volume_init = VolumeInit(
                            filename=create_full_path(accepted['filename']),
                            event_volume_size=(
                                accepted["event_volume_size_k"] * 1024))
            self.__log_storage_mgr.queue_operation(volume_init)
            self.__logging_started = True

        # Commit settings as active running settings:
        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        self.__log_storage_mgr = FileLoggerStorageManager(
                                    self.__name, self.__core_services, self,
                                    OP_Q_DEPTH, FILE_WRITE_Q_DEPTH)
        self.__log_storage_mgr.start()

        if self.__log_storage_mgr is not None and not self.__logging_started:
            volume_init = VolumeInit(
                filename=create_full_path(
                    self.get_setting('filename')),
                event_volume_size=(
                    self.get_setting("event_volume_size_k") * 1024))
            self._queue_operation(volume_init)
            self.__logging_started = True
        return True

    def stop(self):
        self.__log_storage_mgr.stop()

        return True

    def _should_log_channel(self, channel):
        include_list = self.get_setting('include_channel_prefixes')
        exclude_list = self.get_setting('exclude_channel_prefixes')

        # re
        # i = '^(' + '|'.join(map(re.escape, include_list)) + ').*$'
        # e = '$(' + '|'.join(map(re.escape, exclude_list)) + ').*$'
        # return re.match(channel.name(), i) and not re.match(channel.name(), e)

        include = False

        if include_list:
            include = reduce(lambda x, pfx: x or channel.name().startswith(pfx),
                             include_list,
                             False)
        else:
            include = True

        if include:
            include = reduce(lambda x, pfx: x and not
                               channel.name().startswith(pfx) and not
                               (channel.options_mask() & OPT_DONOTLOG),
                             exclude_list,
                             True)

#        self.__tracer.info("Asked about channel %s, logging: %s",
#                           channel.name(0, str(include))

        return include

    def _create_operations(self, logging_event):
        '''
        Creates a tuple operations for a FileLoggerStoreManager based
        on a given 'log_event'.

        Returns a tuple of FileLoggerStorageManagerOperations.
        '''

        op = None

        if not self._should_log_channel(logging_event.channel):
            return ()

        if isinstance(logging_event, LoggingEventNewSample):
            op = StoreNewSample(channel_name=logging_event.channel.name(),
                                sample=logging_event.channel.producer_get())
        elif isinstance(logging_event, LoggingEventChannelNew):
            op = StoreChannelNew(
                    channel_name=logging_event.channel.name(),
                    initial_sample=logging_event.channel.producer_get())
        elif isinstance(logging_event, LoggingEventChannelRemove):
            # We may receive the channel name and sample now because at this
            # time the channel will not be destroyed until all logging event
            # callbacks have been propagated.  This is by design.
            op = StoreChannelRemove(
                channel_name=logging_event.channel.name(),
                previous_sample=logging_event.channel.producer_get())
        else:
            self.__tracer.warning("Unknown logging event '%s'",
                logging_event.__class__.__name__)
            return ()

        self.__ops_since_last_dump += 1
        if (self.__ops_since_last_dump >=
            SettingsBase.get_setting(self, 'sample_index_frequency')):
            cdb = (self.__core_services.get_service("channel_manager")
                    .channel_database_get())
            channel_list = filter(lambda cn: self._should_log_channel(
                                                cdb.channel_get(cn)),
                                    cdb.channel_list())
            channel_dump_dict = dict([(cdb.channel_get(cn).name(),
                                        cdb.channel_get(cn).producer_get())
                                            for cn in channel_list])
            self.__ops_since_last_dump = 0
            return (op, StoreChannelDump(channel_dump_dict))

        return (op,)
