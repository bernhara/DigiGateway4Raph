############################################################################
#                                                                          #
# Copyright (c)2011-2012, Digi International (Digi). All Rights Reserved.  #
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

'''
ZigBee Device Manager

The ZigBee Device Manager class and related classes.

This class will manage all ZigBee devices seen and controlled by the DIA.
'''
import traceback

from xbee import ddo_get_param, ddo_set_param
from xbee_device_manager import *
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep import \
     generate_sn_sp
from common.helpers.parse_duration import parse_time_duration
from devices.xbee.common.prodid import MOD_XB_ZB, MOD_XB_S2C_ZB, \
     MOD_UNSPECIFIED

SUPPORTED_MODULES = (MOD_XB_ZB, MOD_XB_S2C_ZB, MOD_UNSPECIFIED)


# exceptions
class ZigBeeDeviceManagerUnsupportedModuleType(ValueError):
    '''
    Raised when the ZigbeeDeviceManager is run on a device with
    a non-zigbee adapter.
    '''
    pass


def _time_formatter(str_arg, test_only=True):
    '''
    Return the value of str_arg as msec or raise an exception.

    If test_only, simply return True or False if the string is parsable.
    (None counts as valid.)

    If test_only returns True, calling again with test_only==False will
    not raise an exception.
    '''
    if str_arg == None:
        if test_only:
            return True
        else:
            return str_arg

    try:
        val = parse_time_duration(str_arg, in_type='sec', out_type='msec')
    except Exception:
        if test_only:
            return False
        else:
            raise

    if test_only:
        return True
    else:
        return val


class ZigBeeDeviceManager(XBeeDeviceManager):
    '''
        This class implements the ZigBee Device Manager.

        Keyword arguments:

        * **name:** the name of the device instance.
        * **core_services:** the core services instance.
    '''
    # set default source routing AR broadcast to 30 * 10 = 300 (5 minutes)
    DEFAULT_AR_SOURCE_ROUTING = 30
    SN_SP_DEFAULT = 'no'

    def __init__(self, name, core_services):

        # over-ride base-class defaults - YML still over-rides these over-rides

        # for zigbee we do nothing - no change to DH/DL
        self.DH_DL_FORCE_DEFAULT = 'True'
        self.DH_DL_REFRESH_DEFAULT = self.DH_DL_REFRESH_NOT_SET

        # existing default of 00:00:00:00:00:00:FF:FF! is okay for Zigbee

        settings_list = [
            # valid settings:
            #  None = ignore (no coordinator change)
            #  True/On = enable, setting AR to self.DEFAULT_AR_SOURCE_ROUTING
            #  False/Off = disable, setting AR to 0xFF (XBee default)
            #  {dec} like '30' = set AR to this, if between 0 and 255
            #  {hex} like '0x1D' = set AR to this, if between 0x00 and 0xFF
            Setting(
                name='source_routing', type=str, required=False,
                default_value=None,
                verify_function=self.__verify_source_routing),
            # valid settings:
            # A time format (as in parse_time_duration:
            #     '13 mins' or '1 hour' or '134 secs'
            # or None (for don't use)
            Setting(
                name='sn_sp_override', type=str, required=False,
                default_value=ZigBeeDeviceManager.SN_SP_DEFAULT,
                verify_function=lambda x: x == \
                    ZigBeeDeviceManager.SN_SP_DEFAULT or _time_formatter(x)),
            ]

        property_list = []

        XBeeDeviceManager.__init__(self, name, core_services, settings_list,
                                   property_list)

    # use XBeeDeviceManager.run(self)

    def _coordinator_ddo_config(self):
        # handle rare case where coordinator child-table is 'full' after
        # restart. Since we have no idea how long we've been offline, it is
        # possible all 10 children seek new association, and with NC=0 the
        # coordinator will NOT offer association for 3 * SN * SP time
        # so if sensor wakes once per 4 hours, then would take 12 hours for
        # coordinator to begin allowing association and data resumption
        nc = ord(ddo_get_param(None, 'NC'))
        self._tracer.debug("Coordinator NC=%d at startup", nc)
        if nc == 0:
            # then issue network reset
            self._tracer.debug("Child Table is full - Reset coordinator")
            ddo_set_param(None, 'NR', 0)
            # note: reading NC immediately will still have NC=0

        sn_sp_val = SettingsBase.get_setting(self, 'sn_sp_override')
        if sn_sp_val != ZigBeeDeviceManager.SN_SP_DEFAULT:
            sn_sp_override = _time_formatter(sn_sp_val,
                                             test_only=False)
            if sn_sp_override != None:
                try:
                    self._sn_sp_override = generate_sn_sp(sn_sp_override)
                    self._tracer.debug('Setting SN/SP override.')
                except ValueError:
                    self._tracer.warning('SN/SP override could not be set. '
                                'The given time does not factor cleanly.')

        ar_new = SettingsBase.get_setting(self, 'source_routing')
        self._tracer.debug("Zigbee Source Routing setting is:%s", ar_new)
        ar_new = self.__parse_source_routing(ar_new)
        if ar_new is not None and (ar_new != ord(ddo_get_param(None, 'AR'))):
            # only update if changing
            self._tracer.debug("Zigbee Source Routing: " \
                                   "set AR=%d (0x%02x)", ar_new, ar_new)
            ddo_set_param(None, 'AR', ar_new, timeout=15)
            ddo_set_param(None, 'AC', timeout=15)
            ddo_set_param(None, 'WR', timeout=15)
        return

    def get_default_dh_dl_address(self):
        '''
        Return the (DH, DL) tuple for downloading to nodes as DH/DL

        For ZigBee preferred DH/DL is 0/0, which is coordinator
        '''
        return ('\x00\x00\x00\x00', '\x00\x00\x00\x00')

    def is_zigbee(self):
        return True

    def wait_for_awake(self):
        '''
        Returns True the network is awake and ready to pass packets,
        returns False with the wait loop has been broken via
        XBeeDeviceManager.__unblock_inner_select()
        '''
        return True

    def network_asleep(self):
        ''' Returns True when the network is asleep. '''
        return False

    def validate_network_protocol(self, module_id, product_id):
        ''' Fail if this is being used on a non ZigBee network. '''
        if module_id not in SUPPORTED_MODULES:
            raise ZigBeeDeviceManagerUnsupportedModuleType(
                'module_id: %i, accepted module ids: %s' % (
                    module_id, SUPPORTED_MODULES))

    def get_sleep_block(self, extended_address, sleep=None,
                        sleep_rate_ms=0,
                        awake_time_ms=5000,
                        sample_predelay=None):
        # TODO: validation on settings?
        # Note: if sleep=False and sleep_rate_ms <= 0xFFFF, we set to IR
        xbee_sleep_cfg = XBeeConfigBlockSleep(extended_address)

        if sleep == None:
            # empty config block
            return xbee_sleep_cfg

        elif sleep:
            # assume Sleep means cyclic sleep
            xbee_sleep_cfg.sleep_cycle_set(awake_time_ms, sleep_rate_ms)
            xbee_sleep_cfg._add_parameter('IR', 0xffff)
            if sample_predelay:
                xbee_sleep_cfg._add_parameter('WH', sample_predelay)

        else:
            # we don't sleep, but treat the rate as IR
            xbee_sleep_cfg.sleep_mode_set(SM_DISABLED)

            if (sleep_rate_ms >= 0) and (sleep_rate_ms <= 0xFFFF):
                # 'IS' sample rate fits into 'IR'
                xbee_sleep_cfg._add_parameter('IR', sleep_rate_ms)
            else:
                # DIA will need to manually poll 'IS'
                xbee_sleep_cfg._add_parameter('IR', 0)

        return xbee_sleep_cfg

    def wait_until_xbee_ready(self):
        ''' We don't need to wait for anything. '''
        return True

    def get_ddo_block(self, extended_address, add_dh_dl=False):
        '''
        Returns an XBeeConfigBlockDDO.

        This method is DEPRECATED.
        Addressing information is now added at "xbee_device_configure"
        time.
        '''
        self._tracer.debug('zigbee_device_manager.get_ddo_block() ' \
                               'is DEPRECATED. Use XBeeConfigBlockDDO(' \
                               'extended_address) directly. (Import it from' \
                               ' xbee_device_manager.)')

        xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)

        # if add_dh_dl and self._dh_dl_addr is not None:
        #     # Set the destination for unaddressed/AT-mode/IS-data
        #     xbee_ddo_cfg.add_parameter('DH', self._dh_dl_addr[0])
        #     xbee_ddo_cfg.add_parameter('DL', self._dh_dl_addr[1])

        return xbee_ddo_cfg

    def __verify_source_routing(self, new_type):
        '''
        Verify 'source_routing' setting values
        '''
        try:
            self.__parse_source_routing(new_type)
            return
        except:
            pass

    def __parse_source_routing(self, src):
        '''
        Convert 'source_routing' setting into either None or 0 to 255

        Return None if coordinator AR should be ignored/left as is
        Return 0x00 to 0xFF if coordinator AR should be set accordingly

        @TODO: support a setting like '5 min' or '15 min'?
        '''
        if src is None:
            # have no effect on AR - leave as is
            return None

        # else should be string
        try:
            src = src.lower()
            if src in ['true','on']:
                # return a good default value
                return self.DEFAULT_AR_SOURCE_ROUTING

            elif src in ['false','off']:
                # return AR to disable source routing
                return 0xFF

            elif src in ['none']:
                # have no effect on AR - leave as is
                return None

            # else assume is actual number to load
            if src[:2] == '0x':
                n = int(src, 16)
            else:
                n = int(src)

            if n >= 0 and n <= 255:
                return n
        except:
            traceback.print_exc()

        raise ValueError, \
            "Invalid type '%s': must be 'On','Off' or 0 to 255" % (src)
