############################################################################
#                                                                          #
# Copyright (c)2008-2013 Digi International (Digi). All Rights Reserved.   #
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
Database Synchronization Module
"""

# imports
from settings.settings_base import SettingsBase, Setting
from devices.device_base import DeviceBase
from channels.channel_database_interface import ChannelDoesNotExist
# for backwards compatible not-quite-iso 8601 timestamps
from common.helpers.format_channels import iso_date
from common.file_utils import percent_remaining, blocks_remaining
from common.path_utils import create_full_path
from core.tracing import get_tracer
from common.utils import wild_match
from common.types.boolean import Boolean

import os
import threading
import digitime
import cStringIO

from channels.channel_source_device_property import *

DISK_FLUSH = 60 * 5  # every five minutes we sync collected samples to disk
MAX_SIZE = 50 * (1 << 10)  # 50kB max in-memory sample collection size
MAX_UPLOAD_SIZE = 100 * (1 << 10)  # 100kB max upload block
SAMPLE_SIZE = 100  # kludge: each sample is roughly 100 bytes in xml

# path name for sync buffer
BUFFER_NAME = create_full_path('_edp_cache')

TRACER = get_tracer('edp_upload')
try:
    import idigidata
except:
    TRACER.critical('This EDP_Upload driver can only be run on a '
                    'Digi device with EDP.')
    TRACER.critical('The running platform is not supported.')
    raise


# constants
ENTITY_MAP = {
    "<": "&lt;",
    ">": "&gt;",
    "&": "&amp;",
    "\"": "&quot;",
    "'": "&apos;",
}

# compatibility levels
DBF_11 = '1.1'
DBF_FULL = 'idigi_db_full'
DBF_COMPACT = 'idigi_db_compact'

# maximum blocking time
# running threads will be blocked for no longer than this
MAX_SLEEP = 5

# contains file creation, # of successful upload attempts, total
# upload attempts, last successful, last failure, current file
# number, and a list of outstanding files to upload
STATS_FILE = 'edpstats.txt'

# The maximum number of "stale" data files to push after a successful
# upload. (In other words, if we had 200 failures (and 200 saved data files),
# once we got a successful upload, we would turn around and try to send up to
# MAX_RECOVER of the files in a row, halting on error. So we would have 197
# left to upload if everything went well. And this happens every time
# we upload.)
MAX_RECOVER = 3

# minimums for saving data
MIN_FS_PERCENT = 0.05
MIN_BLOCKS = 4

# default string for always-enabled uploading
ALWAYS_ON = 'magic_on_string'

# exception classes
class BadFormatException(Exception):
    ''' raised when output format is initialized incorrectly '''
    pass


# functions
def _save_fail(fname):
    ''' Generate an warning message about losing data. '''
    TRACER.warning('Could not save %s locally... ' \
                   'the data is gone forever!' % (fname))


def _delete_fail(fname):
    '''
    Generate a warning message about not being able to remove a
    dead file.
    '''
    TRACER.warning('Could not delete %s locally... ' \
                   'it could still be taking up space.' % (fname))


def _escape_entities(sample_value):
    ''' map forbidden characters to safe xml representation '''
    if not isinstance(sample_value, str):
        return sample_value
    for char in ENTITY_MAP:
        sample_value = sample_value.replace(char, ENTITY_MAP[char])
    return sample_value


def _type_str(typeobj):
    '''
    Return a nice string represention of a type.
    (Defaults to str(type), but removes the "<type " prefix and ">" postfix
    if possible.)
    '''
    # our custom Boolean type should be mapped to a Python bool
    if Boolean == typeobj:
        return 'bool'
    retval = str(typeobj)
    prefix = '<type \''
    postfix = '\'>'
    if retval.startswith(prefix) and retval[-len(postfix):] == postfix:
        retval = retval[len(prefix):len(retval) - len(postfix)]
    return retval


def _parse_date(timestr):
    '''
    Return UTC seconds from a string.
    '''
    if timestr == 'None':
        return 0

    return digitime.parse_iso_date_str(timestr)


def _make_date(timestamp):
    '''
    Return time string.
    '''
    if timestamp == 0:
        return None

    return digitime.form_iso_date_str(timestamp)


def _parse_int(intstr):
    '''
    Return integer seconds from a string.
    '''
    return int(intstr)


def _make_int(intval):
    '''
    Return integer string from an int.
    '''
    return str(intval)


def _parse_csv_list(csvstr):
    '''
    Return a list of strings from a comma-separated list of strings.
    '''
    if len(csvstr.strip()) == 0:
        return list()
    return [x.strip() for x in csvstr.split(',')]


def _make_csv_list(csv_list):
    '''
    Return a csv string from the passed list.
    '''
    return ', '.join(csv_list)


def _read_last_bytes(fobj, max_bytes):
    '''
    Reads up to max_bytes from the file object (and strips up to the next
    valid opener).
    '''
    fobj.seek(0, 2)
    tot_bytes = fobj.tell()
    start_point = max(0, tot_bytes - max_bytes)

    fobj.seek(start_point)
    output = fobj.read()

    # strip garbage on the front
    # shudder...
    real_start = output.find('<sample name=')
    if real_start == -1:
        TRACER.debug('_read_last_bytes returning empty string')
        output = ''
    else:
        output = output[real_start:]
    return output


_DATES = (_parse_date, _make_date)
_INTS = (_parse_int, _make_int)
_CSVS = (_parse_csv_list, _make_csv_list)


# classes
class StatsFile(object):
    '''
    Encapsulates stats file reading and writing.

    If incorrect types are written for various entries, they may
    be ignored on load.

    In particular:

    * 'creation_time', 'last_failure', and 'last_success'
    are written as iso8601 times (see lib.digitime.form_iso_dat_str for
    details) or None if not set.

    * 'upload_attempts', 'file_number', and 'successful_uploads' are integers.

    * 'files_list' is a string of comma separated filenames.

     @param name: name of backing file
    '''

    # parseable values
    VALS = {'creation_time': _DATES, 'upload_attempts': _INTS,
            'successful_uploads': _INTS, 'last_failure': _DATES,
            'last_success': _DATES, 'file_number': _INTS,
            'files_list': _CSVS}

    def __init__(self, name=STATS_FILE):
        '''
        Create/load the backing file and load current values.
        '''
        
        self.file_name = create_full_path(name)
        self.creation_time = 0
        self.upload_attempts = 0
        self.successful_uploads = 0
        self.last_failure = 0
        self.last_success = 0
        self.file_number = 0
        self.files_list = []  # files that need to be pushed
        if os.path.exists(self.file_name):
            old_vals = open(self.file_name, 'r')
            self.load(old_vals)
            old_vals.close()

        # if this file is new, or the old creation time was corrupted...
        if self.creation_time == 0:
            self.creation_time = digitime.time()

    def __str__(self):
        output = []
        for lbl, fncs in StatsFile.VALS.items():
            try:
                outstr = ''.join((lbl, ':', str(fncs[1](
                    self.__getattribute__(lbl))), '\n'))
                output.append(outstr)
            except Exception:
                TRACER.warning('%s has bad value (%s)... ignoring it.' % (
                    lbl, self.__getattribute__(lbl)))

        return ''.join(output)

    def load(self, fdesc):
        '''
        Load values from the backing file.

        If any entries are mangled, the default value is used.
        '''
        for i in fdesc:
            if i[-1] == '\n':
                i = i[:-1]
            args = i.split(':', 1)
            if len(args) != 2:
                TRACER.warning('ignoring stats file line %s' % str(i))
                continue
            lbl, rest = args

            if lbl in StatsFile.VALS:
                try:
                    func = StatsFile.VALS[lbl][0]
                    object.__setattr__(self, lbl, func(rest))
                except Exception:
                    TRACER.error('Couldn\'t parse stats file <%s:%s>. ' \
                                 'Using default value of <%s>.' % (
                                     lbl, rest, self.__getattribute__(lbl)))
            else:
                TRACER.warning('Coudn\'t parse unknown line is stats file: ' \
                               '%s. Ignoring it...' % (i))

    def save(self):
        '''
        Write current stats to file.
        '''
        fout = open(self.file_name, 'w')

        for lbl, fncs in StatsFile.VALS.items():
            try:
                outstr = ''.join((lbl, ':', str(fncs[1](
                    self.__getattribute__(lbl))), '\n'))
                fout.write(outstr)
            except Exception:
                TRACER.warning('%s has bad value (%s)... ignoring it.' % (
                    lbl, self.__getattribute__(lbl)))
        fout.close()


class EDPUpload(DeviceBase, threading.Thread):
    '''
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.
    '''
    headers = {DBF_11: ' compact="True" version="1.1"',
               DBF_FULL: '',
               DBF_COMPACT: ' compact="True"'}

    def __init__(self, name, core_services):

        # these variables created by DeviceBase
        # self._name, self._core, self._tracer
    
        self.__stopevent = core_services
        self.__subscribed_channels = []

        # key: channel name
        # val: duple (type, list of samples from that channel)
        self.__upload_queue = {}
        self._stats_file = StatsFile()
        TRACER.debug("initial statsfile: %s", self._stats_file)

        self.channel_blacklist = (''.join((name, '.upload_samples')),
                                  ''.join((name, '.upload_snapshot')))

        self.__entry_lock = threading.Lock()
        self.__sample_count = 0
        self.__sample_sync = digitime.time()

        chm = core_services.get_service("channel_manager")
        self.__cp = chm.channel_publisher_get()
        self.__cdb = chm.channel_database_get()

        self.methods = {DBF_11: self.__make_xml,
                        DBF_FULL: self.__make_full_xml,
                        DBF_COMPACT: self.__make_compact_xml}

        # Properties
        # ----------
        # upload_now: Boolean which forces an upload now if set to true.
        #     It automatically resets to false.

        # Settings
        # --------
        # initial_upload: is the number of seconds before the first initial
        #     upload.  If it is not specified, initial upload is disabled.
        #     The initial upload is handled before normal interval and
        #     sample_threshold processing. If you set the initial upload
        #     for 600 (10 minutes), after ten minutes, the first samples
        #     will be uploaded. Then normal processing will occur.
        #
        # interval: is the maximum interval in seconds that this
        #     module waits before sending all collected samples
        #     to the Device Cloud Database. This timer can be reset
        #     by three different methods:
        #         1) forced upload (by setting "update_now" channel to True)
        #         2) interval upload
        #         3) sample upload
        #     The timer is reset *even if these methods fail*.
        #     If interval is equal to 0, the feature is disabled.
        #
        # sample_threshold: is the mininum number of samples required before
        #     sending data to the Device Cloud Database.  If it is equal to
        #     0, the feature is disabled.
        #
        # collection: is the collection on the database where the data will
        #     be stored.
        #
        # file_count: the number of unique files we will keep on Device Cloud
        #             (and/or locally in the case of upload failure).
        #
        # filename: the name of the xml file we will push to Device Cloud, with
        #     a number appended to the end (cycling from 1 to file_count)
        #
        # legacy_time_format:
        #     use the old, non-iso format that idigi_db used
        #
        # channels: is the list of channels the module is subscribed to.
        #     If no channels are listed, all channels are subscribed to.
        #     Wildcards '*' and '?' are supported in channel names.
        #
        # upload_control: a DIA channel reference to enable or suppress uploading.
        #     String which can be None or a channel (ie "driver0.channel1"). 
        #     The channel should hold a boolean value. If None or the channel 
        #     has a True value, then uploading takes place. If the channel is 
        #     false, uploading is paused (and samples are *NOT* saved).
        #
        # compact_xml: (when set to True) will produce output XML with the
        #     information stored as attributes to the sample node instead of
        #     separately tagged, resulting in smaller XML output.
        #
        # upload_time_zero: when False, suppress upload of samples with a 
        #     timestamp of 0 (1970-01-01 00:00:00). this defaults to False
        #
        # trigger_snapshot: a DIA channel reference to trigger a one-shot 
        #     upload of all normal channels.

        settings_list = [
            Setting(
                name='initial_upload', type=int, required=False,
                default_value=0),
            Setting(
                name='interval', type=int, required=False,
                default_value=0),
            Setting(
                name='snapshot_interval', type=int, required=False,
                default_value=0),
            Setting(
                name='sample_threshold', type=int, required=False,
                default_value=0),
            Setting(
                name='collection', type=str, required=False,
                default_value=''),
            Setting(
                name="channels", type=list, required=False,
                default_value=[]),
            Setting(
                name='file_count', type=int, required=False,
                default_value=20),
            Setting(
                name='filename', type=str, required=False,
                default_value="upload"),
            Setting(
                name='upload_type', type=bool, required=False,
                default_value=True),
            Setting(
                name='legacy_time_format', type=bool, required=False,
                default_value=False),
            Setting(
                name='upload_control', type=str, required=False,
                default_value=ALWAYS_ON),
            # backwards compatibility:
            # use 'idigi_db_full' or 'idigi_db_compact'
            # as arguments to be backwards compatible with either old style
            Setting(
                name='compatibility', type=str, required=False,
                default_value=DBF_11, verify_function=lambda x: \
                x == DBF_FULL or x == DBF_COMPACT or x == DBF_11),

            Setting(
                name='upload_time_zero', type=bool, required=False,
                default_value=False),

            Setting(
                name='trigger_snapshot', type=str, required=False),
            ]

            ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name='upload_snapshot',
                                        type=Boolean,
                perms_mask=DPROP_PERM_SET | DPROP_PERM_REFRESH,
                options=(DPROP_OPT_AUTOTIMESTAMP | DPROP_OPT_DONOTDUMPDATA),
                initial=Sample(value=Boolean(False)),
                set_cb=lambda x: self.upload_now(x, snapshot=True)),
            ChannelSourceDeviceProperty(name='upload_samples',
                                        type=Boolean,
                perms_mask=DPROP_PERM_SET | DPROP_PERM_REFRESH,
                options=(DPROP_OPT_AUTOTIMESTAMP | DPROP_OPT_DONOTDUMPDATA),
                initial=Sample(value=Boolean(False)),
                set_cb=lambda x: self.upload_now(x, snapshot=False)),

        ]

        DeviceBase.__init__(self, name,
                            core_services,
                            settings_list,
                            property_list)

        self.__stopevent = threading.Event()

        # Event to use for notification of meeting the sample threshold
        self.__threshold_event = threading.Event()

        # event for enabled/disabled signalling
        self.__enabled = threading.Event()
        self.__control_initialized = False

        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    def _enabled_trigger(self, channel):
        '''
        Listener for upload_control.

        set_run should only be true for initialization call
        '''
        name = SettingsBase.get_setting(self, 'upload_control')
        try:
            channel = self.__cdb.channel_get(name)
        except ChannelDoesNotExist:
            # this is ok... we will get set on the first channel event
            return

        if not (channel.perm_mask() & DPROP_PERM_GET):
            TRACER.error('\'upload_control\' setting points to a ' \
                         'channel without get permissions. ' \
                         'Uploading will never be enabled.')
            return

        value = bool(channel.get().value)

        if not self.__control_initialized:
            self.__control_initialized = True
            TRACER.info('Triggering on %s, uploading is currently %s.' %
                        (name, ('disabled', 'enabled')[int(value)]))
        elif name != channel.name():
            raise ValueError('Unknown channel %s registered to upload ' \
                             'control listener! This is definitely a ' \
                             'programming error!' % (channel.name()))

        if value and not self.__enabled.isSet():
            self.__enabled.set()
        elif not value and self.__enabled.isSet():
            self.__enabled.clear()

    def _validate_channel(self, chan):
        '''
        Validation method for control channel... this can only be
        called *after* we are running.
        '''
        if chan == ALWAYS_ON:
            self.__enabled.set()
            return True

        self._subscribe(chan, self._enabled_trigger)

        # initialize if the channel already exists
        self._enabled_trigger(None)
        return True

    def _get_channels(self):
        '''
        Return the list of subscribed channels (matching our possible
        wildcards in the "channels" setting) that currently exist.
        '''
        return self.__subscribed_channels

    def _add_new_channel(self, channel):
        '''
        Callback for newly registered channels.

        We check if they should be tracked and if so, add them.
        '''

        channel_list = SettingsBase.get_setting(self, "channels")

        if (len(channel_list) == 0 or channel in channel_list) and \
               channel not in self.channel_blacklist:
            TRACER.debug('Subscribed to channel %s.' % (channel))
            self._subscribe(channel)
        else:
            # check for wildcards
            wild_list = [x for x in channel_list if \
                         x.find('*') + x.find('?') > -2]
            for i in wild_list:
                if wild_match(i, channel) and \
                       channel not in self.channel_blacklist:
                    TRACER.debug('Subscribed to channel %s.' % (channel))
                    self._subscribe(channel)
                    break
        # otherwise, ignore the new channel

    def _subscribe(self, channel, fname=None):
        '''
        subscribe to a channel

        If fname=None, defaults to listening for new samples
        and is added to the registry.
        '''
        if fname == None:
            fname = self.receive
            if channel not in self.__subscribed_channels:
                self.__cp.subscribe(channel, fname)
                self.__subscribed_channels.append(channel)
        else:
            self.__cp.subscribe(channel, fname)

    def start(self):
        # wait for new channels
        self.__cp.subscribe_new_channels(self._add_new_channel)
        channels = self.__cdb.channel_list()
        for channel in channels:
            # want to ensure we don't register to upload control...
            # it gets its own handler
            if channel != SettingsBase.get_setting(self, 'upload_control'):
                # check our filter rules for things
                self._add_new_channel(channel)

        threading.Thread.start(self)
        self.apply_settings()
        return True

    def stop(self):
        self.__stopevent.set()
        return True

    def _samples_in_queue(self, data_dict=None):
        '''
        Return the number of samples currently stored in memory
        (inside of __upload_queue).

        This *must* be called while holding the __entry_lock if
        using the default data_dict argument!
        '''
        count = 0
        if data_dict == None:
            data_dict = self.__upload_queue
        for i, j in data_dict.iteritems():
            count += len(j[1])
        return count

    def receive(self, channel):
        '''
        Store a sample from a given channel and possibly trigger upload.

        The channel argument is ignored (but is required by the
        notification mechanism).
        '''
        
        if not self.__enabled.isSet():
            TRACER.debug('self.__enabled.isSet is NOT set')
            return

        sam = channel.get()
        if not SettingsBase.get_setting(self, "upload_time_zero"):
            if sam.timestamp == 0:
                TRACER.debug('discard sample with null time')
                return

        # save the sample
        try:
            self.__entry_lock.acquire()
            self.__sample_count += 1
            prev = self.__upload_queue.get(channel.name(),
                                           (channel.type(), list()))
            prev[1].append(sam)
            self.__upload_queue[channel.name()] = prev

            mem_samples = self._samples_in_queue()
            # sync to disk?
            if mem_samples * SAMPLE_SIZE > MAX_SIZE:
                TRACER.info('flushing samples to disk due to memory ' \
                            'constraint')
                self._sync_to_disk()
            elif digitime.time() - self.__sample_sync > DISK_FLUSH:
                TRACER.info('flushing samples to disk due to time')
                self._sync_to_disk()
        finally:
            self.__entry_lock.release()

        sample_threshold = SettingsBase.get_setting(self, "sample_threshold")
        if sample_threshold > 0 and self.__sample_count >= sample_threshold:
            # It really doesn't matter that we set sample count to zero
            # here... self.__upload sets self.__sample_count back to zero.
            # We just don't want to repeatedly bang on the threshold event.
            try:
                self.__entry_lock.acquire()
                self.__sample_count = 0
            finally:
                self.__entry_lock.release()
            self.__threshold_event.set()
            self._tracer.debug("Reached threshold of %i, setting event flag",
                                sample_threshold)

    def run(self):
        # validate control channel
        run_chan = SettingsBase.get_setting(self, 'upload_control')
        if not self._validate_channel(run_chan):
            TRACER.error('Couldn\'t validate channel setting... dying.')
            self._core.request_shutdown()
            return

        # Subscribe to a named channel to force a snap-shot upload
        x = SettingsBase.get_setting(self, 'trigger_snapshot')
        if x is not None and len(x) > 0:
            # these are set in our self.__init__
            # chm = core_services.get_service("channel_manager")
            # self.__cp = chm.channel_publisher_get()
            self.__cp.subscribe(x, self._trigger_snapshot)
            
        start_time = digitime.time()
        upload_now = SettingsBase.get_setting(self, "initial_upload")

        interval = SettingsBase.get_setting(self, "interval")
        snapshot_interval = SettingsBase.get_setting(self, 'snapshot_interval')

        # track last upload signal (this is separate from last success/fail)
        last = digitime.time()
        last_snapshot = digitime.time()
        while not self.__stopevent.isSet():
            try:
                # spin/sleep until we get enabled
                self.__enabled.wait(MAX_SLEEP)
                if not self.__enabled.isSet():
                    continue

                # handle initial upload
                if upload_now > 0:
                    diff = start_time + upload_now - digitime.time()
                    if diff <= 0:
                        upload_now = 0
                        self.__upload_data(force=True)
                    else:
                        # spin here
                        digitime.sleep(min(MAX_SLEEP, diff))
                        continue

                if snapshot_interval > 0 and \
                       digitime.time() - last_snapshot >= snapshot_interval:
                    last_snapshot = digitime.time()
                    self.__upload_data(force=True)

                tts = MAX_SLEEP
                if interval > 0:
                    now = digitime.time()
                    time_passed = now - max(self._stats_file.last_success,
                                            self._stats_file.last_failure,
                                            last)
                    tts = interval - time_passed
                    if tts <= 0:
                        self.__upload_data()
                        last = now

                # hang out for a while
                self.__threshold_event.wait(min(MAX_SLEEP, tts))
                if self.__threshold_event.isSet():
                    self.__upload_data()

            except Exception, e:
                self._tracer.error("exception in EDP upload thread: %s",
                                    str(e))

        self._tracer.warning("Out of run loop.  Shutting down...")

        # Clean up channel registration
        self.__cp.unsubscribe_from_all(self.receive)

    def upload_now(self, sample, snapshot):
        '''
        Force a snapshot/samples upload now.
        '''
        if snapshot:
            channel = 'upload_snapshot'
        else:
            channel = 'upload_samples'

        if sample:
            self.property_set(channel, Sample(value=Boolean(False)))
            self.__upload_data(force=snapshot)

    def _trigger_snapshot(self, bool_sample):
        '''
        Set the power on the device and the power_on property.
        '''
        if not isinstance(bool_sample, Sample):
            bool_sample = bool_sample.get()
            
        trigger = bool_sample.value
        self._tracer.calls('Trigger Snapshot source input goes %s', trigger)
        if trigger:
            # if true, trigger the snapshot upload
            self.__upload_data(force=True)
        # else, ignore transition to False
        return

    def _make_snapshot(self):
        '''
        Used to collect a "forced" set of samples.

        Returns a dict in the same format as
        self.__upload_queue
        (key: channel_name, val: (type, (list of samples))

        where each list of samples contains a single sample with
        a forced sample.
        '''
        self._tracer.calls('Forced SNAPSHOT upload')
        ret = dict()
        channel_list = self._get_channels()
        for channel_name in channel_list:
            channel = self.__cdb.channel_get(channel_name)
            if not (channel.perm_mask() & DPROP_PERM_GET):
                # skip ungettable things
                continue
            #if (channel.perm_mask() & DPROP_PERM_REFRESH):
                # try to 'refresh' things which can be refreshed
            if (channel.options_mask() & DPROP_OPT_DONOTDUMPDATA):
                # skip no-dump things
                continue
            self._tracer.debug('Forced upload, including channel '
                                '%s', channel_name)
            ret[channel_name] = (channel.type(), [channel.get()])
        return ret

    def __upload_data(self, force=False):
        '''
        write xml up to Device Cloud

        If force == True, a snapshot of all samples are written,
        not the history of those whose values have changed.

        FIXME: This method is *waaay* too long.
        '''
        now = digitime.time()
        output_list = dict()
        preformed_xml = ''
        if force:
            output_list = self._make_snapshot()
        else:
            try:
                self.__entry_lock.acquire()
                self.__sample_count = 0
                output_list = self.__upload_queue
                self._tracer.debug("Output List (%d): %s", len(output_list),
                                                          str(output_list))
                self.__upload_queue = dict()
                # return chunk of preformed xml from disk sync (truncated
                # to MAX_SIZE)

                # the _merge_cache needs to be inside the lock, because
                # we may sync to disk in another thread
                preformed_xml = self._merge_cache(self._samples_in_queue(
                    output_list))
            finally:
                self.__entry_lock.release()
            self.__threshold_event.clear()

        if len(output_list) < 1 and len(preformed_xml) < 1:
            self._tracer.debug("No sample data to send to Device Cloud")
            return

        xml = cStringIO.StringIO()
        xml.write("<?xml version=\"1.0\"?>")
        compat = SettingsBase.get_setting(self, 'compatibility')
        try:
            xml.write("<idigi_data%s>" % self.headers[compat])
        except Exception:
            raise BadFormatException('\'compatibility\' has strange value!' \
                                     ' (Has %s, should be in %s.)' % \
                                     (compat, self.headers.keys()))
        # write in-memory samples
        self.__write_dict_to_xml_output(output_list, xml)

        # add cached data
        xml.write(preformed_xml)
        xml.write("</idigi_data>")

        if self._tracer.debug():
            self._tracer.debug("%s", str(xml.getvalue()))

        self._tracer.debug("Starting upload to Device Cloud")
        filename = self._get_current_filename()
        self._stats_file.upload_attempts += 1

        file_count = SettingsBase.get_setting(self, 'file_count')
        if file_count < 1:
            file_count = 1
        self._stats_file.file_number = \
                        (self._stats_file.file_number + 1) % file_count

        success = self.__send_to_idigi(filename, xml.getvalue())
        if success:
            self._stats_file.last_success = digitime.time()
            self._stats_file.successful_uploads += 1
        else:
            self._stats_file.last_failure = digitime.time()
            self._save_failed_data(filename, xml.getvalue())

        self._stats_file.save()

        # if we did succeed, try to push old leftovers
        if success and len(self._stats_file.files_list) > 0:
            self._upload_old_data()

        xml.close()

    def _sync_to_disk(self):
        '''
        Dumps the samples currently in memory to disk.

        As a side-effect, clears the current memory cache and
        resets the self.__sample_sync timer.

        If this method fails, it will have cleared the in-memory cache,
        but *may have thrown away data*.

        Must be called with __entry_lock!
        '''
        try:
            # swap out data store
            output_list = self.__upload_queue
            self.__upload_queue = dict()
            self.__sample_sync = digitime.time()

            mem_samples = self._samples_in_queue(output_list)
            append = not (self.__sample_count == mem_samples)

            temp_string = cStringIO.StringIO()
            self.__write_dict_to_xml_output(output_list, temp_string)

            # flush to disk
            self._save_failed_data(BUFFER_NAME, temp_string.getvalue(),
                                   write_stats=False, append=append)
            temp_string.close()
        except Exception, e:
            TRACER.warning('Error while syncing to disk: data may have ' \
                           'been lost. (%s)' % (str(e)))
            return

    def _merge_cache(self, num_samples_in_memory):
        '''
        Returns an xml fragment consisting of <sample> elements.

        Must be called with __entry_lock!

        This also removes the cache file.
        '''
        mem_size = num_samples_in_memory * SAMPLE_SIZE
        max_sample_bytes_to_collect = MAX_UPLOAD_SIZE - mem_size
        try:
            self.__sample_sync = digitime.time()
            if not os.path.exists(BUFFER_NAME):
                return ''
            f = open(BUFFER_NAME)
            op_string = f.readline()

            # braindead check for good data
            if op_string.startswith('<sample'):
                retval = _read_last_bytes(f, max_sample_bytes_to_collect)
            else:
                TRACER.debug('Removed stale non-cache data file %s.' \
                             % BUFFER_NAME)
                retval = ''
            f.close()
            os.remove(BUFFER_NAME)
            return retval
        except Exception, e:
            TRACER.debug('problem merging cache... data may be lost\n' \
                         '(%s)' % (str(e)))
            try:
                f.close()
                os.remove(BUFFER_NAME)
                return ''
            except Exception, e2:
                TRACER.debug('problem with merge_cache cleanup: %s' \
                             % (str(e2)))
                return ''
            return ''

    def __write_dict_to_xml_output(self, data_dict, output_object):
        '''
        Write all the samples in the data_dict to the output_object.
        '''
        compat = SettingsBase.get_setting(self, 'compatibility')
        for name, vals in data_dict.iteritems():
            sample_type = vals[0]
            for sample in vals[1]:
                output_object.write(self.methods[compat](name, sample,
                                                         sample_type))
                output_object.write('\n')

    def _get_current_filename(self):
        '''
        Return the current data filename.
        '''
        f_prefix = SettingsBase.get_setting(self, 'filename')
        llen = SettingsBase.get_setting(self, 'file_count')
        try:
            rlen = len(str(llen - 1))
        except Exception:
            rlen = 0
        fstring = "%%0%s" % (rlen)
        return ''.join((f_prefix, fstring, "i.xml")) \
               % self._stats_file.file_number

    def _save_failed_data(self, filename, data, write_stats=True,
                          append=False):
        '''
        Save failed upload to be tried later, removing old data if we
        have to.

        (The stats file is saved immediately after this method call,
        and is not saved inside this method.)
        '''
        while percent_remaining() < MIN_FS_PERCENT or \
           MIN_BLOCKS >= blocks_remaining():
            # try to remove one old failed files
            if len(self._stats_file.files_list) > 0:
                # try to delete one
                try:
                    os.remove(create_full_path(self._stats_file.files_list[0]))
                except Exception:
                    _delete_fail(self._stats_file.files_list[0])
                self._stats_file.files_list = \
                                            self._stats_file.files_list[1:]
            else:
                TRACER.warning('Removed all files possible, but still ' \
                               'don\'t have room to save new data locally.')
                _save_fail(filename)
                return

        # save this for later...
        try:
            if append:
                mode = 'a'
            else:
                mode = 'w'
            fout = open(create_full_path(filename), mode)
            fout.write(data)
            fout.close()
            if write_stats:
                if filename not in self._stats_file.files_list:
                    self._stats_file.files_list.append(filename)
        except Exception:
            _save_fail(filename)

    def _upload_old_data(self):
        '''
        Upload (up to MAX_RECOVER) saved files from failed uploads.
        '''
        count = 0
        todo = self._stats_file.files_list
        while count < MAX_RECOVER:
            if len(todo) == 0:
                break
            fname = todo[0]
            if not os.path.exists(create_full_path(fname)):
                TRACER.warning('When trying to upload old data, discovered ' \
                               '%s no longer exists on the filesystem. ' \
                               'Skipping...' % (fname))
                todo = todo[1:]
                continue
            fin = None
            try:
                fin = open(create_full_path(fname), 'r')
                data = fin.read()
                fin.close()
            except Exception:
                TRACER.warning('When trying to upload old data, could not ' \
                               'open %s for reading. Removing...' % (fname))
                if fin:
                    fin.close()
                try:
                    os.remove(create_full_path(fname))
                except Exception:
                    # we give up here
                    TRACER.debug('Could not remove bad file %s. It will be ' \
                                 'ignored in the future.' % (fname))
                todo = todo[1:]
                continue

            # trying to upload now...
            self._stats_file.upload_attempts += 1
            self._tracer.debug("starting upload of old data to Device Cloud")

            success = self.__send_to_idigi(fname, data)
            if success:
                self._tracer.debug("finished upload of old data to Device Cloud")
                self._stats_file.last_success = digitime.time()
                self._stats_file.successful_uploads += 1
                todo = todo[1:]
                try:
                    os.remove(create_full_path(fname))
                except Exception:
                    # we give up here...
                    _delete_fail(fname)
                count += 1
            else:
                self._tracer.debug("upload of old data to Device Cloud failed")
                self._stats_file.last_failure = digitime.time()
                break

        self._stats_file.files_list = todo
        self._stats_file.save()

    def __make_xml(self, channel_name, sample, type_info):
        '''
        Version 1.1 xml (first versioned version, can be parsed
        by Device Cloud's initial "compact" version parser)
        '''
        upload_type = SettingsBase.get_setting(self, 'upload_type')
        real = not SettingsBase.get_setting(self, 'legacy_time_format')

        if upload_type:
            frame = '<sample name="%s" value="%s" unit="%s" type="%s" '\
                    'timestamp="%s" />'
            args = [_escape_entities(y) for y in \
                    [str(x) for x in (channel_name, sample.value,
                                      sample.unit,
                                      _type_str(type_info),
                                      iso_date(sample.timestamp,
                                               real_iso=real))]]
        else:
            frame = '<sample name="%s" value="%s" unit="%s" timestamp="%s" />'
            args = [_escape_entities(y) for y in \
                    [str(x) for x in (channel_name, sample.value,
                                      sample.unit,
                                      iso_date(sample.timestamp,
                                               real_iso=real))]]
        return frame % tuple(args)

    def __make_full_xml(self, channel_name, sample, type_info=None):
        ''' initial DIA upload format '''
        data = "<sample>"
        data += "<name>%s</name>"
        data += "<value>%s</value>"
        data += "<unit>%s</unit>"
        data += "<timestamp>%s</timestamp>"
        data += "</sample>"

        return data % (channel_name, _escape_entities(sample.value),
                       sample.unit, iso_date(sample.timestamp))

    def __make_compact_xml(self, channel_name, sample, type_info=None):
        ''' second DIA upload format (parsed by Device Cloud) '''
        data = "<sample name=\"%s\" value=\"%s\" unit=\"%s\"" \
               " timestamp=\"%s\" />"

        return data % (channel_name, _escape_entities(sample.value),
                       sample.unit, iso_date(sample.timestamp))

    def __send_to_idigi(self, fname, data):
        '''
        Push a file to Device Cloud.

        Returns boolean success value.
        '''
        success = False
        collection = SettingsBase.get_setting(self, 'collection')
        try:
            self._tracer.debug('Attempting to upload %s to Device Cloud', fname)
            success, err, errmsg = idigidata.send_to_idigi(data,
                                                           fname,
                                                           collection)
            if success:
                self._tracer.debug('Successfully uploaded %s to Device Cloud',
                                    fname)
            else:
                self._tracer.error('Unsuccessful upload attempt of %s ' \
                                    'to Device Cloud. (Err: %s Errmsg: ' \
                                    '%s)', fname, str(err),
                                    str(errmsg))
        except Exception, e:
            self._tracer.error('Took an Exception during upload of %s' \
                                ' to Device Cloud: %s', fname, str(e))
        return success
