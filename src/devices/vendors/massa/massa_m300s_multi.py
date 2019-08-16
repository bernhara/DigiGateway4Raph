############################################################################
#                                                                          #
# Copyright (c)2008-2010, Digi International (Digi). All Rights Reserved.  #
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

"""\
Massa M-300 Driver Connected to local serial with multi-drop

Settings:

    sample_rate_sec: the sample rate for polling in seconds, default = 60
                     The type is string and can include the modifiers 'ms',
                     'sec','min','hr', or 'day'. For example '15 min' will
                     be treated as once per 900 seconds

    bus_id: A string list of ID Tags to poll, default = "(1)"
            As example, can be "(1,2,3,4)"

    manual_trigger: True or False, default = False
                    If True, then the M300 'software trigger'
                    request is sent before polling for status. This is required
                    if the multiple M300 might interfere if active at the same
                    time. If False, then assumes M300 is always active.

    trace: defines if trace output is shown or not. Type is string,
           default = on/fancy and the string is not case sensitive.
           ['true','on','fancy'] trace shows only major changes and data samples
           ['false','off'] no trace information is shown after start up.
           ['debug','all'] chatty trace information.

Channels:

    error_nn: True/False; True if the device is not functioning as expected -
              probably means init failed or adapter is not updating data.
    note: error_01, error_02 ... error_nn: 'nn' is the ID Tag from 01 to 32

    error_flag_nn: True/False; True if the device returned an error flag.

    range_nn: range returned in inches

    strength_nn: target strength in % (prc). limited to 0, 25, 50, 75, 100%

    temperature_nn: reported sensor temperature in degree-C

Usage/Wiring information:
    M-300 Brown --> RS-485 Port B (+)
    M-300 Green --> RS-485 Port A (-)
    M-300 Black --> Signal ground (GND)
    M-300 Red   --> Power (+12VDC or +24VDC)
    M-300 White --> Not Connected (0-10v output)

To use multi-drop, the sensor "ID Tag" must be set correctly before field
installation. This value defaults to one (1), so to have 4 M300 on the same
multi-drop you must set their ID Tags to 1, 2, 3, and 4 respectively.
This is done using the Massa M300 software tool before field installation.
"""

# imports
import struct
import traceback
import types
import digitime

from lib.serial.serialdigi import *

from devices.device_base import DeviceBase
from devices.device_base import *
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from core.tracing import get_tracer

from samples.annotated_sample import *
from common.helpers.parse_duration import parse_time_duration
from common.helpers.sleep_aids import secs_until_next_minute_period

from devices.vendors.massa.massa_m300_sensor import MassaM300_Sensor

# constants
SHOW_COMM = True

# exception classes

# interface functions

# classes
class MassaM300s_multi(DeviceBase, Serial):

    # reduce trashing of strings for common bus_id
    PRE_NAM = 5
    ERR_NAM = ('error_%02d', 'error_01', 'error_02', \
               'error_03', 'error_04', 'error_05')
    STRN_NAM = ('strength_%02d', 'strength_01', 'strength_02', \
                'strength_03', 'strength_04', 'strength_05')
    EFLG_NAM = ('sensor_error_%02d', 'sensor_error_01', 'sensor_error_02', \
                'sensor_error_03', 'sensor_error_04', 'sensor_error_05')
    RNG_NAM = ('range_%02d', 'range_01', 'range_02', \
               'range_03', 'range_04', 'range_05')
    TMP_NAM = ('temperature_%02d', 'temperature_01', 'temperature_02', \
               'temperature_03', 'temperature_04', 'temperature_05')

    # misc defaults
    INITIAL_POLL_SEC = 10.0
    MANUAL_DELAY_SEC = 0.1
    READ_SIZE = 10

    STRENGTH_TABLE = { 0x10: 25, 0x20: 50, 0x30: 75, 0x40: 100 }

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        self.showname = 'M300(%s)' % name

        ## Local State Variables:
        self.__response_buffer = ""
        self.__poll_event = None
        self.__request_events = []

        # will hold the list of sensor objects
        self.__sensor_list = []

        self._tracer = get_tracer(name)

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='sample_rate_sec', type=str, required=False,
                default_value='60'),

            Setting(
                name='bus_id_list', type=list, required=False,
                default_value=[1]),

            Setting(
                name='manual_trigger', type=bool, required=False,
                default_value=False),

            Setting(name='trace', type=str, required=False,
                    default_value='fancy'),
        ]

        ## Channel Properties Definition:
        #    are defined dynamically within self.start()
        property_list = [
        ]

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Initialize the serial interface:
        # Set the baud rate to 19200,8,N,1 expect answer within 1 secs
        Serial.__init__(self, 0, baudrate=19200, parity='N', \
                        timeout=0.5)

        return

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def start(self):
        """Start the device driver.  Returns bool."""

        self._tracer.info("Start Device")

        # parse YML string setting to local, adjust as required
        self.__import_settings()

        for sensor in self.__sensor_list:
            # for each ID tag (or node), spawn the channel list
            id = sensor.get_id_tag()

            # each node starts in error
            isam = AnnotatedSample(Sample(0, True))
            isam.errors.add(ERSAM_NOT_INIT)
            inam = self.make_chn_name_error(id)
            self.add_property(
                ChannelSourceDeviceProperty(name=inam, type=bool, initial=isam,
                    perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP))

            isam = AnnotatedSample(Sample(0, 0.0, 'prc'))
            isam.errors.add(ERSAM_NOT_INIT)
            inam = self.make_chn_name_strength(id)
            self.add_property(
                ChannelSourceDeviceProperty(name=inam, type=float, initial=isam,
                    perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP))

            isam = AnnotatedSample(Sample(0, True))
            isam.errors.add(ERSAM_NOT_INIT)
            inam = self.make_chn_name_error_flag(id)
            self.add_property(
                ChannelSourceDeviceProperty(name=inam, type=bool, initial=isam,
                    perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP))

            isam = AnnotatedSample(Sample(0, 0.0, 'in'))
            isam.errors.add(ERSAM_NOT_INIT)
            inam = self.make_chn_name_range(id)
            self.add_property(
                ChannelSourceDeviceProperty(name=inam, type=float, initial=isam,
                    perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP))

            isam = AnnotatedSample(Sample(0, 0.0, 'C'))
            isam.errors.add(ERSAM_NOT_INIT)
            inam = self.make_chn_name_temperature(id)
            self.add_property(
                ChannelSourceDeviceProperty(name=inam, type=float, initial=isam,
                    perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP))

        self.__sched = self.__core.get_service("scheduler")

        # Scheduling first request and watchdog:
        self.__schedule_poll_cycle(self.INITIAL_POLL_SEC)
        # self.__reschedule_retry_watchdog()

        return True

    def stop(self):
        """Stop the device driver.  Returns bool."""

        self._tracer.info("Stopping Device")

        # cancel any out-standing events
        try:
            self.__sched.cancel(self.__poll_event)
        except:
            pass

        return True

    ## Locally defined functions:
    def make_chn_name_error(self, id):
        try:
            # 1 to self.PRE_NAM (5?) succeeds
            return self.ERR_NAM[id]
        except: # other fail and create new string
            return self.ERR_NAM[0] % id

    def make_chn_name_strength(self, id):
        try:
            return self.STRN_NAM[id]
        except:
            return self.STRN_NAM[0] % id

    def make_chn_name_error_flag(self, id):
        try:
            return self.EFLG_NAM[id]
        except:
            return self.EFLG_NAM[0] % id

    def make_chn_name_range(self, id):
        try:
            return self.RNG_NAM[id]
        except:
            return self.RNG_NAM[0] % id

    def make_chn_name_temperature(self, id):
        try:
            return self.TMP_NAM[id]
        except:
            return self.TMP_NAM[0] % id

    def next_poll_cycle(self):

        self.__poll_event = None

        manual = SettingsBase.get_setting(self, "manual_trigger")

        for sensor in self.__sensor_list:
            # repeat for each ID tag (or node)
            id = sensor.get_id_tag()

            self._tracer.debug("%s: poll sensor ID tag %d", self.showname, id)

            if manual:
                # then issue the manual software poll
                req = sensor.req_software_trigger_1()

                try:
                    self.write(req)
                    if SHOW_COMM:
                        print "M300: send MANUAL READ, len=%d, " % len(req),
                        for by in req:
                            print '%02X ' % ord(by),
                        print
                    # there is NO response to this poll,
                    #   but we need to wait some delay
                    time.sleep(self.MANUAL_DELAY_SEC)

                except:
                    traceback.print_exc()
                    self._tracer.error("manual poll xmission failure, abort cycle.")
                    break

            # poll the status
            req = sensor.req_status_3()

            if SHOW_COMM:
                print "M300: send STATUS, len=%d, " % len(req),
                for by in req:
                    print '%02X ' % ord(by),
                print

            try:
                self.write(req)
                data = self.read(self.READ_SIZE)
                self.flushInput()
                self.message_indication(sensor, data)

            except:
                traceback.print_exc()
                self._tracer.error("status xmission failure, will retry.")
                break

        self.__schedule_poll_cycle()
        # self.__reschedule_retry_watchdog()
        return

    def __schedule_poll_cycle(self, delay=None):

        if delay is None:
            # then use configured poll rate in self.__rate
            if self.__clean_minutes is None:
                # then don't worry about clean time
                next_poll_sec = self.__rate
            else:
                # else do cleanly, skewed by self.__clean_minutes seconds
                next_poll_sec = secs_until_next_minute_period(self.__rate/60) + \
                                self.__clean_minutes
        else:
            # else use the passed in value
            next_poll_sec = delay

        self._tracer.debug("schedule next poll cycle in %d sec", next_poll_sec)

        # Attempt to Cancel all/any pending request events still waiting
        # to run for our device.
        if self.__poll_event is not None:
            try:
                self.__sched.cancel(self.__poll_event)
            except:
                pass

        # Request a new event at our poll rate in the future.
        self.__poll_event = self.__sched.schedule_after( \
                            next_poll_sec, self.next_poll_cycle)
        return

    def __reschedule_retry_watchdog(self):
        print "M300: reschedule watchdog"
        poll_rate_sec = SettingsBase.get_setting(self, "sample_rate_sec")

        # Attempt to Cancel all/any pending retry request events still waiting
        # to run for our device.
        for event in self.__request_events:
            try:
                self.__sched.cancel(event)
            except:
                pass
        self.__request_events = []

        # Request a new event at our poll rate in the future.
        event = self.__sched.schedule_after(poll_rate_sec * 1.5, self.retry_request)
        if event != None:
            self.__request_events.append(event)


    def message_indication(self, sensor, buf, addr=None):
        if SHOW_COMM:
            print "M300: message indication, len=%d, " % len(buf),
            for by in buf:
                print '%02X ' % ord(by),
            print

        self.__response_buffer += buf

        if len(self.__response_buffer) < 6:
            # We may need to just give the network a bit more time
            # but just in case, reschedule the retry event now:
            self.__reschedule_retry_watchdog()
            return

        bus_id = sensor.get_id_tag()
        dct = sensor.ind_status_3(buf)

        if dct.has_key('error'):
            # then we failed
            # Ick!  The RS-485 reply packets may not been packetized
            # in the proper sequence.  Flush the buffer.
            self.__response_buffer = ""
            print 'bad checksum'

        else:
            # Update our channels:
            now = digitime.time()

            if dct['target_detected']:
                # then perhaps no error

                self._tracer.info('ID:%d rng:%0.1fin, str:%d%% tmp:%0.1fC', \
                    bus_id, dct['range'], dct['strength'], dct['temperature'])

                self.property_set(self.make_chn_name_error(bus_id), \
                                  Sample(now, False))
                self.property_set(self.make_chn_name_strength(bus_id), \
                                  Sample(now, float(dct['strength']), "prc"))
                self.property_set(self.make_chn_name_error_flag(bus_id), \
                                  Sample(now, False))
                self.property_set(self.make_chn_name_range(bus_id), \
                                  Sample(now, dct['range'], "in"))
                self.property_set(self.make_chn_name_temperature(bus_id), \
                                  Sample(now, dct['temperature'], "C"))

            else:
                self._tracer.warning('ID:%d - no target detected', bus_id)

        return

    def __import_settings(self):
        '''Pre-Process the settings, connverting if required'''

        # enble the trace as configured
        # self.set_trace(SettingsBase.get_setting(self, "trace").lower())

        # Parse out the sample rate string, set self.__rate to seconds
        self.__adjust_sample_rate_sec()

        # no import of 'manual_trigger' required

        # handle the bus id list
        id_list = SettingsBase.get_setting(self, "bus_id_list")
        if isinstance(id_list, types.StringType):
            # convert YML string to list
            id_list = eval(id_list)

        elif isinstance(id_list, types.IntType):
            # repair YML's conversion of '(1)' to be just 1
            id_list = tuple(id_list)

        print 'id_list = %s' % str(id_list)

        # create the sensor list
        for id in id_list:
            self._tracer.debug('%s: add sensor id tag %d', self.showname, id)
            sen = MassaM300_Sensor(id)
            sen.set_mode_multidrop(True)
            self.__sensor_list.append(sen)

        return

    def __adjust_sample_rate_sec(self, val=None):

        if val is None:
            # then use existing setting, which shall be string
            val = SettingsBase.get_setting(self, "sample_rate_sec")

        elif isinstance(val, types.IntType):
            # else make int as seconds into string
            val = str(val)

        # else assume is string

        # Parse out the sample rate string, set self.__rate to seconds
        self.__rate = int(parse_time_duration( val, in_type='sec', out_type='sec'))
        #if self.trace_debug_events():
        #    print '%s: import sample rate (%s) as %d sec' % \
        #          (self.showname, val, self.__rate)

        val = SettingsBase.get_setting(self, "sample_rate_sec")
        if val != str(self.__rate):
            # then we changed the value
            try:
                SettingsBase.set_pending_setting(self, \
                        "sample_rate_sec", str(self.__rate))

                # push the new settings into running system
                self.apply_settings()

            except:
                traceback.print_exc()

        if (self.__rate % 60) == 0:
            # then we'll do the 'clean minutes' function
            self.__clean_minutes = 0
        else:
            self.__clean_minutes = None

        return

# internal functions & classes

