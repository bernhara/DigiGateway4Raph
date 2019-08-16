"""\
Driver for the GE Ventostat with builtin XBee (such as model T8100-HD-ZB).
It acts like a 'thermostat' for ventilation systems, using CO2 levels (instead of
temperature) to control the volume of ventilation.

The XB in the ventostat will return a DD of 0x000A02E1, runs as a Router AT
at baud rate 19200,N,8,1

See 'readme.txt' for Settings and Channels created

YML Example:

  - name: upstairs
    driver: devices.vendors.GE_Energy.ventostat:Ventostat
    settings:
        xbee_device_manager: xbee_device_manager
        extended_address: "00:13:a2:00:40:67:29:fe!"
        dev_poll_rate_sec: '5 min'
        dev_poll_cleanly_min: True

"""

# imports
import time
import traceback
import types
import gc
import xbee

from core.tracing import get_tracer
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *

from devices.xbee.common.prodid import PROD_GE_VENTOSTAT
from devices.vendors.robust.robust_xserial import RobustXSerial

from samples.annotated_sample import *

# this should be in the dia\src\devices\modbus directory
# but we just ignore this feature if missing
try:
    import common.modbus.create_modbus_config as rci_modbus
    from common.modbus.mbdia_block import *
except:
    pass

import ut_minmaxavg as stats

# constants

# exception classes

# interface functions

# classes
class Ventostat(RobustXSerial):

    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [ [0xe8, 0xc105, 0x11], [0xe8, 0xc105, 0x92] ]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [ PROD_GE_VENTOSTAT, ]

    # over-ride Robust_Base parent defaults
    RDB_DEF_ENABLE_ERROR_CHAN = 'True'
    RDB_DEF_POLL_RATE = '1 min'
    RDB_DEF_RESPONSE_TIMEOUT = '10 sec'

    # over-ride Robust_XBee parent defaults
    RXBEE_DEF_HEART_BEAT = 60
    RXBEE_DEF_HEART_BEAT_IO = 'D1'
    RXBEE_DEF_FORCE_WPAN = True
    RXBEE_DEF_ROBUST_ROUTER = True

    # over-ride Robust_XSerial parent defaults
    XSER_DEFAULT_TYPE = 'oem'
    XSER_DEFAULT_BAUD = 19200

    STATE_ERROR = 0
    STATE_IDLE = 1
    STATE_SEND_REQ = 2
    STATE_WAIT_RSP = 3
    STATE_SEND_CO2_REQ = 4
    STATE_WAIT_CO2_RSP = 5
    STATE_SEND_HUM_REQ = 6
    STATE_WAIT_HUM_RSP = 7
    STATE_SEND_TMP_REQ = 8
    STATE_WAIT_TMP_RSP = 9
    STATE_SEND_VER_REQ = 10
    STATE_WAIT_VER_RSP = 11
    STATE_OFFLINE = 12
    STATE_NAMES = ('error', 'idle', 'send_req', 'wait_rsp', \
                   'send_co2', 'wait_co2', 'send_hum', 'wait_hum', \
                   'send_temp', 'wait_temp', \
                   'send_ver', 'wait_ver', 'offline',)

    # go offline on 3rd missed responses in a row
    RSP_TOUT = 15.0
    RSP_TOUT_LIMIT = 3

    # Min/Max sanity values
    SANE_CO2_MIN = 300
    SANE_CO2_MAX = 3000
    SANE_HUM_MIN = 1.0
    SANE_HUM_MAX = 100.0
    SANE_TMP_MIN = -20.0
    SANE_TMP_MAX = 50.0

    DEF_CO2_DELTA = 10.0
    DEF_HUM_DELTA = 1.0
    DEF_TMP_DELTA = 1.0

    def __init__(self, name, core_services):
        self.__name = name

        # these set in robust_base
        # self.__settings
        # self.__core
        # self.__sched
        # self.__properties = { }
        # self._tracer = get_tracer('Robust')

        # make our own tracer
        self.__tracer = get_tracer("ventostat(%s)" % self.__name)

        # these are in robust_xbee
        # self.__xbee_manager = None
        # self.__extended_address = None

        ## Local State Variables:
        self.__units = 'F'
        self.__state = self.STATE_SEND_VER_REQ
        self.__am_offline = True
        self.__three_command = True

        self.__co2_error = True
        self.__co2_last = None
        self.__co2_delta = self.DEF_CO2_DELTA
        self.__co2_stats = stats.MinMaxAvg()
        self.__co2_stats.set_mode_true_average(60)

        self.__hum_error = True
        self.__hum_last = None
        self.__hum_delta = self.DEF_HUM_DELTA
        self.__hum_stats = stats.MinMaxAvg()
        self.__hum_stats.set_mode_true_average(60)

        self.__tmp_error = True
        self.__tmp_last = None
        self.__tmp_delta = self.DEF_TMP_DELTA
        self.__tmp_stats = stats.MinMaxAvg()
        self.__tmp_stats.set_mode_true_average(60)

        ## Settings Table Definition:
        settings_list = [

            # setting in Robust_Base
            # - dev_enable_error:       self.RDB_DEF_ENABLE_ERROR_CHAN
            # - dev_poll_rate_sec:      self.RDB_DEF_POLL_RATE
            # - dev_response_timeout_sec: self.RDB_DEF_RESPONSE_TIMEOUT
            # - dev_poll_cleanly_min:   self.RDB_DEF_POLL_CLEANLY
            # - dev_trace:              self.RDB_DEF_TRACE

            # Setting( name='xbee_device_manager' is in base class
            # Setting( name='extended_address' is in base class

            # select 'F' or 'C'
            Setting(
                name='degf', type=bool, required=False,
                default_value=False),

            # set the change-deltas to limit
            Setting(
                name='co2_delta', type=float, required=False,
                default_value=self.DEF_CO2_DELTA),
            Setting(
                name='hum_delta', type=float, required=False,
                default_value=self.DEF_HUM_DELTA),
            Setting(
                name='tmp_delta', type=float, required=False,
                default_value=self.DEF_TMP_DELTA),

            # enable use of older 3 commands
            Setting(
                name='three_commands', type=bool, required=False,
                default_value=True),

            # enable the statistics channels
            Setting(
                name='add_statistics', type=bool, required=False,
                default_value=False),

            # enable the LED to blink or be dark
            Setting(
                name='disable_led', type=bool, required=False,
                default_value=False),

            # enable/disable Modbus - technically, we cannot disable
            # Modbus, but we can prevent this driver from creating
            # a default IA config if it won't be used
            Setting(
                name='enable_modbus', type=bool, required=False,
                default_value=False),

        ]

        ## Channel Properties Definition:
        property_list = []

        init_sam = Sample(timestamp=0, value=True)
        property_list.append(
            ChannelSourceDeviceProperty(name="error", type=bool,
                initial=init_sam, perms_mask=(DPROP_PERM_GET),
                options=DPROP_OPT_AUTOTIMESTAMP) )

        init_sam = AnnotatedSample(Sample(timestamp=0, value=0.0))
        init_sam.errors.add(ERSAM_NOT_INIT)
        property_list.append(
            ChannelSourceDeviceProperty(name="temperature", type=float,
                initial=init_sam, perms_mask=(DPROP_PERM_GET),
                options=DPROP_OPT_AUTOTIMESTAMP) )

        init_sam = AnnotatedSample(Sample(timestamp=0, value=0.0))
        init_sam.errors.add(ERSAM_NOT_INIT)
        property_list.append(
            ChannelSourceDeviceProperty(name="humidity", type=float,
                initial=init_sam, perms_mask=(DPROP_PERM_GET),
                options=DPROP_OPT_AUTOTIMESTAMP) )

        init_sam = AnnotatedSample(Sample(timestamp=0, value=0))
        init_sam.errors.add(ERSAM_NOT_INIT)
        property_list.append(
            ChannelSourceDeviceProperty(name="co2", type=int,
                initial=init_sam, perms_mask=(DPROP_PERM_GET),
                options=DPROP_OPT_AUTOTIMESTAMP) )

        init_sam = AnnotatedSample(Sample(timestamp=0, value=''))
        init_sam.errors.add(ERSAM_NOT_INIT)
        property_list.append(
            ChannelSourceDeviceProperty(name="version", type=str,
                initial=init_sam, perms_mask=(DPROP_PERM_GET),
                options=DPROP_OPT_AUTOTIMESTAMP) )

        init_sam = AnnotatedSample(Sample(timestamp=0, value=''))
        init_sam.errors.add(ERSAM_NOT_INIT)
        property_list.append(
            ChannelSourceDeviceProperty(name="co2_stats", type=str,
                initial=init_sam, perms_mask=(DPROP_PERM_GET),
                options=DPROP_OPT_AUTOTIMESTAMP) )

        init_sam = AnnotatedSample(Sample(timestamp=0, value=''))
        init_sam.errors.add(ERSAM_NOT_INIT)
        property_list.append(
            ChannelSourceDeviceProperty(name="hum_stats", type=str,
                initial=init_sam, perms_mask=(DPROP_PERM_GET),
                options=DPROP_OPT_AUTOTIMESTAMP) )

        init_sam = AnnotatedSample(Sample(timestamp=0, value=''))
        init_sam.errors.add(ERSAM_NOT_INIT)
        property_list.append(
            ChannelSourceDeviceProperty(name="tmp_stats", type=str,
                initial=init_sam, perms_mask=(DPROP_PERM_GET),
                options=DPROP_OPT_AUTOTIMESTAMP) )

        ## Initialize the DeviceBase interface:
        self.XSER_IS_ASCII = True
        self.XSER_STRING_CRNL = True
        self.XSER_SHOW_BYTES = True
        RobustXSerial.__init__(self, self.__name, core_services,
                                settings_list, property_list)

        return

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    @staticmethod
    def probe():
        """\
        Collect important information about the driver.
        """

        probe_data = RobustXSerial.probe()

        for address in Ventostat.ADDRESS_TABLE:
            probe_data['address_table'].append(address)

        # We don't care what devices our base class might support.
        # We do not want to support all of those devices, so we will
        # wipe those out, and instead JUST use ours instead.
        probe_data['supported_products'] = Ventostat.SUPPORTED_PRODUCTS

        return probe_data


    def apply_settings(self):
        # use parent's apply
        accepted, rejected, not_found = RobustXSerial.apply_settings(self)

        self.__co2_delta = SettingsBase.get_setting(self, "co2_delta")
        self.__hum_delta = SettingsBase.get_setting(self, "hum_delta")
        self.__tmp_delta = SettingsBase.get_setting(self, "tmp_delta")

        return accepted, rejected, not_found

    def start(self):
        """Start the device driver.  Returns bool."""

        self.__tracer.info("Starting device")

        # force desired fixed parameters into our base/parent devices
        RobustXSerial.start_pre(self)

        # match our private tracer to Robust_Base's family one
        self.__tracer.level = self._tracer.level

        ## Remove the statistic channels if NOT desired
        # why add, then remove?  Otherwise they don't exist at
        # start-up for subscription by other devices/presentations
        if SettingsBase.get_setting(self, "add_statistics"):
            self.__tracer.info("Statistic Channels are enabled.")
        else:
            self.__tracer.info("Statistic Channels are disabled.")
            self.remove_list_of_properties(
                    ["co2_stats", "hum_stats", "tmp_stats"])
            self.__co2_stats = None
            self.__hum_stats = None
            self.__tmp_stats = None

        ## Force a default IA Modbus config if none
        # 'enabling' really only enables this config check
        if SettingsBase.get_setting(self, "enable_modbus"):
            try:
                if rci_modbus.rci_test_for_ia_table():
                    self.__tracer.info("Detected existing Modbus IA Config.")
                else:
                    if rci_modbus.rci_create_ia_table_mbdia():
                        self.__tracer.info("Created new Modbus IA Config.")
                    else:
                        self.__tracer.error("Modbus IA Config creation FAILED.")

            except:
                self.__tracer.debug(traceback.format_exc())
                self.__tracer.error('Modbus IA Config creation FAILED!')

        self.__three_command = SettingsBase.get_setting(self, "three_commands")

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = self.get_ddo_block()

        # enable/disable the LED statistics channels
        if SettingsBase.get_setting(self, "disable_led"):
            # disable by setting DIO-10 (p0) to 5/dig-out high
            xbee_ddo_cfg.add_parameter('P0', 5)
        else:
            # enable by setting DIO-10 (p0) to 1/RSSI/PWM
            xbee_ddo_cfg.add_parameter('P0', 1)

        # Register configuration blocks with the XBee Device Manager:
        self.get_xbee_manager().xbee_device_config_block_add(self, xbee_ddo_cfg)

        RobustXSerial.start_post(self)

        # force garbage collection in case we deleted big things
        gc.collect()

        return True

    def stop(self):
        """Stop the device driver.  Returns bool."""

        self.__tracer.info("Stopping device")
        RobustXSerial.stop(self)

        return True


    ## Locally defined functions:

    def next_poll(self, trns_id):
        return self.update()

    # def response_timeout(self):

    def get_temperature_units(self):
        if SettingsBase.get_setting(self, "degf"):
            return 'F'
        else:
            return 'C'

    def update(self, rate=None):
        """
            Request the latest data from the device.
        """

        if self.__state != self.STATE_IDLE:
            # don't bother showing state of IDLE
            self.__tracer.debug('Update: state is %s',
                                self.STATE_NAMES[self.__state])

        req = None
        if self.__state in [self.STATE_IDLE, self.STATE_SEND_CO2_REQ, \
                            self.STATE_SEND_REQ, \
                            self.STATE_ERROR, self.STATE_OFFLINE]:
            if self.__three_command:
                # then poll for CO2 (using old commands)
                req = '$33$80\r\n'
                self.__state = self.STATE_WAIT_CO2_RSP
            else: # poll for all 3 at once, with single new command
                req = '$33$88\r\n'
                self.__state = self.STATE_WAIT_RSP

            #Reschedule this update method
            self.schedule_next_poll(rate)

        elif self.__state == self.STATE_SEND_HUM_REQ:
            # then poll for Humidity
            req = '$33$81\r\n'
            self.__state = self.STATE_WAIT_HUM_RSP

        elif self.__state == self.STATE_SEND_TMP_REQ:
            # then poll for Humidity
            req = '$33$82\r\n'
            self.__state = self.STATE_WAIT_TMP_RSP

        elif self.__state == self.STATE_SEND_VER_REQ:
            # then poll for Humidity
            req = '$33$DF\r\n'
            self.__state = self.STATE_WAIT_VER_RSP

        elif self.__state in [self.STATE_WAIT_RSP, self.STATE_WAIT_CO2_RSP,
                self.STATE_WAIT_HUM_RSP, self.STATE_WAIT_TMP_RSP,
                self.STATE_WAIT_VER_RSP]:
            # we are waiting for a response

            # else let response timeout do it's job!
            self.schedule_next_poll(rate)
            return

        else:
            self.__tracer.error('Update: unexpected state')
            self.__state = self.STATE_IDLE
            self.schedule_next_poll(5.0)
            return

        try:
            self.serial_send(req)

            # We will process receive data when it arrives in the callback
        except:
            #done with the serial
            self.__tracer.debug(traceback.format_exc())
            self.__tracer.error('XBee Serial Write Failed!')
            self.__state = self.STATE_IDLE

        if self.__state in [self.STATE_IDLE, self.STATE_OFFLINE]:
            self.schedule_next_poll(rate)

        return

    def read_callback(self, buf, addr):
        # Receive any GE response

        try:
            self.__tracer.debug('SerialRcv: state(%s) data(%s)', \
                self.STATE_NAMES[self.__state], buf[:-2])

            # must not be offline anymore
            self.__am_offline = False

            # have data, no timeout
            self.cancel_response_timeout()

            # Update channels:

            if buf[-2] == '\r':
                # print 'cut 2'
                buf = buf[:-2]
            elif buf[-1] == '\r':
                # print 'cut 1'
                buf = buf[:-1]
            else: # we need to expact partial data at times
                self.__tracer.warning('SerialRcv: bad data')
                self.__state = self.STATE_IDLE
                return

            update_now = False
            now = time.time()
            now_st = iso_date(now, use_local_time_offset=True)[:19]

            # if SettingsBase.get_setting(self, "three_commands"):

            if self.__state == self.STATE_WAIT_RSP:
                # then we are waiting for all 3 responses at once
                self.process_all(buf, now, now_st)
                self.signal_end_of_poll()
                self.__state = self.STATE_IDLE
                # do not need to poll again immediately
                # update_now = False

            elif self.__state == self.STATE_WAIT_CO2_RSP:
                # then we are waiting for CO2 PPM response
                self.process_co2(buf, now, now_st)
                self.__state = self.STATE_SEND_HUM_REQ
                update_now = True

            elif self.__state == self.STATE_WAIT_HUM_RSP:
                # then waiting for Humidity
                self.process_humidity(buf, now, now_st)
                self.__state = self.STATE_SEND_TMP_REQ
                update_now = True

            elif self.__state == self.STATE_WAIT_TMP_RSP:
                # then waiting for Temperature
                self.process_temperature(buf, now, now_st)
                self.signal_end_of_poll()
                self.__state = self.STATE_IDLE

                if self.__co2_error or self.__hum_error or self.__tmp_error:
                    # some error occured
                    self.set_error_channel(True)
                else:
                    self.set_error_channel(False)

                update_now = False # end of the line

            elif self.__state == self.STATE_WAIT_VER_RSP:
                # then waiting for Version
                if self.process_version(buf, now, now_st):
                    self.__state = self.STATE_SEND_CO2_REQ
                else:
                    self.__state = self.STATE_SEND_VER_REQ

                update_now = True

            else:
                self.__tracer.error('SerialRcv: unexpected state %s',
                                    self.STATE_NAMES[self.__state])
                self.__state = self.STATE_IDLE
                self.set_error_channel(True)
                return

            if update_now:
                self.update()

        except:
            traceback.print_exc()

        return

    def process_all(self, buf, now, now_st):
        '''Expect all three, such as "719, 35.3, 23.3" - try to process it'''

        try:
            # confirm is NOT of form ##.#, should be ####
            val = buf.split(',')
            if len(val) < 3:
                raise ValueError('Malformed All-Data response')

            # don't send non_st in - we don't want 3 lines, only 1
            co2 = int(val[0])
            self.set_co2(co2, now)

            hum = float(val[1])
            self.set_humidity(hum, now)

            tmp = float(val[2])
            self.set_temperature(tmp, now)
            if self.__units == 'F':
                # convert to F
                tmp = (tmp * 1.8) + 32

            self.__tracer.info("%d PPM, %0.1f RH%%, %0.1f Deg%s at %s",
                    co2, hum, tmp, self.__units, now_st)
            return True

        except:
            self.__tracer.debug(traceback.format_exc())
            self.__tracer.warning('SerialRcv: bad All data(%s) - discard', buf)
            self.set_error_channel(True)
            return True

        return False

    def process_co2(self, buf, now, now_st):
        '''Expect CO2 Response - try to process it'''

        try:
            # confirm is NOT of form ##.#, should be ####
            if not buf or (len(buf) < 3) or (buf[-2] == '.'):
                raise ValueError('Malformed CO2 response')

            return self.set_co2(buf, now, now_st)

        except:
            self.__tracer.debug(traceback.format_exc())
            self.__tracer.warning('SerialRcv: bad CO2 data(%s) - discard', \
                                    buf)
            self.__co2_error = True
            self.set_error_channel(True)

        return False

    def set_co2(self, val, now, now_st=None):
        '''Expect CO2 Response - try to process it'''

        val = int(val)
        if (val >= self.SANE_CO2_MIN) and (val <= self.SANE_CO2_MAX):
            # then is sane CO2
            if (self.__co2_last is None) or \
                    (abs(self.__co2_last - val) > self.__co2_delta):
                # then update the sample
                self.__co2_last = val
                self.property_set("co2", Sample(now, val, 'PPM'))
                self.update_stats_c02(val, now, now_st)
            if now_st is not None:
                self.__tracer.info("CO2=%d PPM at %s", val, now_st)
            self.__co2_error = False

        else:
            self.__tracer.warning('bad CO2 data(%d) - discard', val)
            self.__co2_error = True
            self.set_error_channel(True)

        return not self.__co2_error

    def process_humidity(self, buf, now, now_st):
        '''Expect Humidity Response - try to process it'''
        try:
            # confirm is of form ##.# - might be CO2 as ####
            if buf[-2] != '.':
                raise ValueError('Malformed Humidity response')

            return self.set_humidity(buf, now, now_st)

        except:
            self.__tracer.debug(traceback.format_exc())
            self.__tracer.warning('SerialRcv: bad Humidity data(%s) - discard',
                                buf)
            self.__hum_error = True
            self.set_error_channel(True)

        return False

    def set_humidity(self, val, now, now_st=None):
        '''Expect Humidity Response - try to process it'''

        val = float(val)
        if (val >= self.SANE_HUM_MIN) and (val <= self.SANE_HUM_MAX):
            # then is sane value
            if (self.__hum_last is None) or \
                    (abs(self.__hum_last - val) > self.__hum_delta):
                # then update the sample
                self.__hum_last = val
                self.property_set("humidity", Sample(now, val, 'RH'))
                self.update_stats_humidity(val, now, now_st)
            if now_st is not None:
                self.__tracer.info("Humidity=%0.1f RH%% at %s", val, now_st)
            self.__hum_error = False

        else:
            self.__tracer.warning('bad Humidity data(%f) - discard', val)
            self.__hum_error = True
            self.set_error_channel(True)

        return not self.__hum_error

    def process_temperature(self, buf, now, now_st):
        '''Expect Temperature Response - try to process it'''
        try:
            # confirm is of form ##.# - might be CO2 as ####
            if buf[-2] != '.':
                raise ValueError('Malformed Temperature response')

            return self.set_temperature(buf, now, now_st)

        except:
            self.__tracer.debug(traceback.format_exc())
            self.__tracer.warning('SerialRcv: bad Temperature data(%s) - discard',
                                buf)
            self.__tmp_error = False
            self.set_error_channel(True)

        return not self.__tmp_error

    def set_temperature(self, val, now, now_st=None):
        '''Expect Humidity Response - try to process it'''

        val = float(val)
        if (val >= self.SANE_TMP_MIN) and (val <= self.SANE_TMP_MAX):
            # then is sane value
            if SettingsBase.get_setting(self, "degf"):
                # convert to F
                val = (val * 1.8) + 32
                self.__units = 'F'
            else:
                self.__units = 'C'
            if (self.__tmp_last is None) or \
                    (abs(self.__tmp_last - val) > self.__tmp_delta):
                # then update the sample
                self.__tmp_last = val
                self.property_set("temperature", Sample(now, val, self.__units))
                self.update_stats_temperature(val, now, now_st)
            if now_st is not None:
                self.__tracer.info("Temperature=%0.1f Deg%s at %s", \
                                    val, self.__units, now_st)
            self.__tmp_error = False

        else:
            self.__tracer.warning('bad Temperature data(%f) - discard', val)
            self.__tmp_error = False
            self.set_error_channel(True)

        return not self.__tmp_error

    def process_version(self, buf, now, now_st):
        '''Expect Version Response - try to process it'''
        try:
            # first, see if ERRORx
            if buf.startswith('ERR'):
                pass

            # should look something like "104, 2011/08/12 11:56:44"
            elif buf.find('/') < 0:
                # perhaps is another stale response?
                # might be old '19.1' or new '543, 42.1, 23.1'
                pass

            else:
                self.property_set("version", Sample(0, buf, ''))
                self.__tracer.info("Sensor Version=\"%s\" at %s", buf, now_st)
                self.set_error_channel(False)

                # see if this supports the single command
                if not buf.startswith('100,'):
                    self.__three_command = False

                if self.__three_command:
                    self.__tracer.debug("Sensor requires 3 separate commands")
                    self.__state = self.STATE_SEND_CO2_REQ
                else:
                    self.__tracer.debug("Sensor supports newer 3-in-1 command")
                    self.__state = self.STATE_SEND_REQ
                return True

        except:
            self.__tracer.debug(traceback.format_exc())

        self.__tracer.warning('Bad version data(%s) - discard & retry', buf)
        self.__state = self.STATE_SEND_VER_REQ
        self.set_error_channel(True)

        return False

    def update_stats_c02(self, val, now, now_st=None):
        if self.__co2_stats is not None:
            # p rint 'update CO2 stats'
            self.__co2_stats.update(val)
            msg = 'CO2, min=%d, avg=%d, max=%d' % \
                  (self.__co2_stats.get_minimum(),
                   self.__co2_stats.get_average(),
                   self.__co2_stats.get_maximum())
            self.property_set("co2_stats", Sample(now, msg, ''))
            if now_st is not None:
                msg += ', as of ' + now_st[11:16]
            self.__tracer.info(msg)
        # else: p rint 'skip update CO2 stats - is None'
        return

    def update_stats_humidity(self, val, now, now_st=None):
        if self.__hum_stats is not None:
            self.__hum_stats.update(val)
            msg = 'HUM, min=%0.1f, avg=%0.1f, max=%0.1f' % \
                  (self.__hum_stats.get_minimum(),
                   self.__hum_stats.get_average(),
                   self.__hum_stats.get_maximum())
            self.property_set("hum_stats", Sample(now, msg, ''))
            if now_st is not None:
                msg += ', as of ' + now_st[11:16]
            self.__tracer.info(msg)
        return

    def update_stats_temperature(self, val, now, now_st=None):
        if self.__tmp_stats is not None:
            self.__tmp_stats.update(val)
            msg = 'TMP, min=%0.1f, avg=%0.1f, max=%0.1f' % \
                  (self.__tmp_stats.get_minimum(),
                   self.__tmp_stats.get_average(),
                   self.__tmp_stats.get_maximum())
            self.property_set("tmp_stats", Sample(now, msg, ''))
            if now_st is not None:
                msg += ', as of ' + now_st[11:16]
            self.__tracer.info(msg)
        return

    def serial_send(self, serialString):
        """ Takes either a string or a Sample() """

        if not isinstance(serialString, types.StringType):
            # then is likely Sample object
            serialString = serialString.value

        self.write( serialString)
        # one cannot create a timeout AFTER the send!
        # response may arrive before we start the rsp timer!
        # self.start_response_timeout()
        return

    def set_error_channel(self, error=False):
        """ Set the event callback for failed responses """

        existing = self.property_get("error").value
        if self.property_get("error").value != error:
            # then Error change status
            self.__tracer.info('error_channel status changing to %s', error)
            self.property_set("error", Sample(0, value=error))
        else:
          self.__tracer.debug('current error = %s, no change', existing)

        return

    def response_timeout(self, count):
        # Parse the I/O sample:

        if self.__am_offline:
            # should already by offline
            self.__state = self.STATE_OFFLINE
            self.__tracer.debug('Response Timeout in State - already offline')
            return

        elif count >= self.RSP_TOUT_LIMIT:
            self.__am_offline = True
            if self.__state != self.STATE_OFFLINE:
              # then mark as offline
                self.__state = self.STATE_OFFLINE
                self.__tracer.error('too many response timeouts - going offline')
                self.set_error_channel(True)

                sam = self.property_get("co2")
                if not isinstance(sam, AnnotatedSample):
                    self.__tracer.debug('marking channels as STALE - going offline')
                    sam = AnnotatedSample(sam)
                    sam.errors.add(ERSAM_STALE_DATA)
                    # sam.value = '' # clear old value
                    self.property_set("co2", sam)

                sam = self.property_get("temperature")
                if not isinstance(sam, AnnotatedSample):
                    sam = AnnotatedSample(sam)
                    sam.errors.add(ERSAM_STALE_DATA)
                    # sam.value = '' # clear old value
                    self.property_set("temperature", sam)

                sam = self.property_get("humidity")
                if not isinstance(sam, AnnotatedSample):
                    sam = AnnotatedSample(sam)
                    sam.errors.add(ERSAM_STALE_DATA)
                    # sam.value = '' # clear old value
                    self.property_set("humidity", sam)

            return

        # else assume count < self.RSP_TOUT_LIMIT, so retry

        self.__tracer.warning('Response Timeout, Retry State=%s count=%d', \
                self.STATE_NAMES[self.__state], count)

        if self.__state == self.STATE_WAIT_RSP:
            # retry the 3-in-1 poll
            self.__state = self.STATE_SEND_REQ

        elif self.__state == self.STATE_WAIT_CO2_RSP:
            # retry the CO2 poll
            self.__state = self.STATE_SEND_CO2_REQ

        elif self.__state == self.STATE_WAIT_HUM_RSP:
            # retry the humidity poll
            self.__state = self.STATE_SEND_HUM_REQ

        elif self.__state == self.STATE_WAIT_TMP_RSP:
            # retry the temperature poll
            self.__state == self.STATE_SEND_TMP_REQ

        elif self.__state == self.STATE_WAIT_VER_RSP:
            # retry the version poll
            self.__state = self.STATE_SEND_VER_REQ

        else:
            self.__tracer.error('response_timeout: unexpected state %s',
                                self.STATE_NAMES[self.__state])
            self.__state = self.STATE_IDLE
            self.set_error_channel(True)
            return

        self.__tracer.debug('Retry poll as State(%s)', \
                self.STATE_NAMES[self.__state])

        self.update()
        return

    ## Modbus add-ons
    def get_mbus_device_type( self):
        """We define nice small names for debug use"""
        return 'GE_Ventostat'

    def get_mbus_device_code( self):
        """We overload use of the lower DD word"""
        return PROD_GE_VENTOSTAT

    def export_device_id( self):
        """Return the Device Id response strings"""
        dct = { 0:'GE Sensing', 1:'T8100-HD-ZB', 2:'1.0',
                3:'www.gesensing.com',
                4:'GE Ventostat', 5:'T8100', 6:'Dia' }
        return dct

    def export_base_regs( self, ind):
        """Dump this device's data out to Modbus-style dict"""

        # check the time and thus status
        try:
            rate_sec =  self.get_setting("sample_rate_sec")
            sam =  self.property_get("co2")

        except:
            # major fault, we'll return NO response
            self.__tracer.debug(traceback.format_exc())
            return None

        # check if time is too old, returns iablk with timestamp in
        iablk =  test_time(sam, rate_sec)
        if not iablk:
            # some time problem
            return None

        # update extended address (if any)
        iablk = set_extended_address(iablk, self)

        # okay, do the data
        for tag in [ (MBBLK_AIN1, 'co2', 1.0),
                     (MBBLK_AIN2, 'temperature', 10.0),
                     (MBBLK_AIN3, 'humidity', 10.0),
                     # (MBBLK_AIN4, 'channel4_value')
                     ]:
            try:
                sam = self.property_get(tag[1]).value * tag[2]
                iablk.update({ tag[0]:int(round(sam)) })

            except:
                self.__tracer.debug(traceback.format_exc())
                iablk.update({ tag[0]:-1 })

        # do the status
        x = (MBBLK_STS_AIN_VALID | MBBLK_STS_TIME_VALID)

        iablk.update( { MBBLK_STAT:x, MBBLK_DDTYPE:PROD_GE_VENTOSTAT })

        regs = mbblk_to_data( iablk, ind) # handles regs or coils as required
        # self.__tracer.info('regs = ', regs)
        return regs

# internal functions & classes
