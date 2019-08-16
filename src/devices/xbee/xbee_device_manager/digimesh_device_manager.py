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
DigiMesh Device Manager

The DigiMesh Device Manager class and related classes.

This class will manage all DigiMesh devices seen and controlled by the DIA.

'''
import threading
from select import select
from time import sleep
from channels.channel_source_device_property import DPROP_PERM_GET, \
     DPROP_OPT_AUTOTIMESTAMP, ChannelSourceDeviceProperty, Sample, \
     DPROP_PERM_SET
from common.types.boolean import Boolean
from xbee_device_manager import XBeeDeviceManager, Setting, SettingsBase, \
     XBeeConfigBlockDDO, XBeeConfigBlockSleep, MAX_RECVFROM_LEN
from devices.xbee.common.addressing import gw_extended_address_tuple
from socket import socket, AF_ZIGBEE, SOCK_DGRAM, XBS_PROT_XAPI
from xbee import ddo_get_param, ddo_set_param
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep \
    import DM_SLEEP, DM_SUPPORT
from devices.xbee.common.prodid import MOD_XB_DIGIMESH900, \
     MOD_XB_DIGIMESH24, MOD_XB_S3C_DIGIMESH900, MOD_XB_868_DIGIMESH, \
     MOD_UNSPECIFIED

# HACK: remove these imports once network discovery issue resolved
import xbee
from devices.xbee.common.addressing import addresses_equal

# last byte of awake and asleep messages
AWAKE = 'j'
ASLEEP = 'i'

# modem status endpoint
MODEM_STATUS = 0x8a

SUPPORTED_MODULES = (MOD_XB_DIGIMESH900, MOD_XB_DIGIMESH24,
                     MOD_XB_S3C_DIGIMESH900, MOD_XB_868_DIGIMESH,
                     MOD_UNSPECIFIED)


# exceptions
class DigiMeshDeviceManagerUnsupportedModuleType(ValueError):
    '''
    Raised when the DigiMeshDeviceManager is run on a device with
    a non-digimesh adapter.
    '''
    pass


class SleepChecker(threading.Thread):
    '''
    Listen for awake/asleep frames.
    '''
    def __init__(self, mesh_manager):
        self.manager = mesh_manager

        self._stopevent = threading.Event()
        threading.Thread.__init__(self, name=str(mesh_manager))

        # handler for awake/sleep signals
        self.__sd = None

    def stop(self):
        self._stopevent.set()

    def run(self):
        self.__sd = socket(AF_ZIGBEE, SOCK_DGRAM, XBS_PROT_XAPI)
        self.__sd.bind(('', MODEM_STATUS, 0, 0))

        self._clear_queue()

        while True:
            # Check to see if our thread's stop flag is set:
            if self._stopevent.isSet():
                break

            # MAGIC NUMBER: 5 second responsiveness to stop()
            x, _, _ = select([self.__sd], [], [], 5.0)
            if x:
                data, _ = self.__sd.recvfrom(MAX_RECVFROM_LEN)
                if AWAKE == data[-1]:
                    self.manager._awakeEvent.set()
                else:
                    self.manager._awakeEvent.clear()

    def _clear_queue(self):
        '''
        Clear the device manager's incoming queue.

        This is called during initialization to remove the
        pileup of network awake/network asleep notification frames.
        '''
        read_list, _, _ = select([self.__sd], [], [], 0.0)

        # assume initially asleep
        last = ASLEEP

        while read_list:
            data, _ = self.__sd.recvfrom(MAX_RECVFROM_LEN)
            last = data[-1]
            read_list, _, _ = select([self.__sd], [], [], 0.0)
        if AWAKE == last:
            self.manager._awakeEvent.set()
        else:
            self.manager._awakeEvent.clear()


class DigiMeshDeviceManager(XBeeDeviceManager):
    '''
    This class implements the DigiMesh Device Manager.

    Keyword arguments:

    * **name:** the name of the device instance.
    * **core_services:** the core services instance.

    Settings:

    * **sleep_time:** Time in ms for each sleep cycle. This must
        be a value between 10 and 1440000 inclusive.

    * **wake_time:** Time in ms for each awake period. This must
        be a value betweeen 69 and 3600000 inclusive.
    '''

    DMMAN_DEF_SLEEP_TIME = 2000
    DMMAN_DEF_WAKE_TIME = 2000
    DMMAN_DEF_SET_IF = True

    def __init__(self, name, core_services, settings_list=None,
                 property_list=None):
        if settings_list == None:
            settings_list = []
        if property_list == None:
            property_list = []

        # over-ride base-class defaults - YML still over-rides these over-rides

        # digimesh requires DH/DL to match the coordinator
        self.DH_DL_FORCE_DEFAULT = 'coordinator'
        # this is in minutes - default to once every 3 hours/180 minutes
        self.DH_DL_REFRESH_DEFAULT = 180

        # existing default of 00:00:00:00:00:00:FF:FF! is okay for DigiMesh
        # self.MESH_BROADCAST

        settings_list.extend([
            Setting(
                name='sleep_time', type=int, required=False,
                default_value=self.DMMAN_DEF_SLEEP_TIME,
                verify_function=lambda x: (x == 0) or (10 <= x <= 14400000)),
            Setting(
                name='wake_time', type=int, required=False,
                default_value=self.DMMAN_DEF_WAKE_TIME,
                verify_function=lambda x: 69 <= x <= 3600000),

            # if True try setting IR/IF as required otherwise leave alone
            # and assume the user has managed all of this
            Setting(
                name='set_if', type=bool, required=False,
                default_value=self.DMMAN_DEF_SET_IF),

            ])

        property_list.extend([
            ChannelSourceDeviceProperty(
                name='wake_time', type=int,
                initial=Sample(timestamp=0, value=-1, unit='ms'),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                name='sleep_time', type=int,
                initial=Sample(timestamp=0, value=-1, unit='ms'),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
            ])

        XBeeDeviceManager.__init__(self, name, core_services, settings_list,
                                   property_list)

        # will be initialized during run() startup
        self.__dh_dl_refresh_sec = self.DH_DL_REFRESH_NOT_SET
        self.listener = SleepChecker(self)

    def initialize_sleep_config(self):
        '''
        Called by the super class during the start of it's run block
        (after the configurator is initialized).

        This is the first place we can set xbee settings.
        '''
        sleep_time_ms = SettingsBase.get_setting(self, 'sleep_time')
        wake_time_ms = SettingsBase.get_setting(self, 'wake_time')

        # only block as long as we are awake
        self._select_timeout = wake_time_ms * 0.001

        try:
            # ensure device configured properly
            # SM/ST is set as required in this routine
            self._set_sleep_wake(sleep_time_ms, wake_time_ms)
        except Exception, e:
            self._critical_die(e)

    def run(self):
        self.listener.start()
        return XBeeDeviceManager.run(self)

    def stop(self):
        ''' Stop the listener thread, then the whole manager. '''
        self.listener.stop()
        return XBeeDeviceManager.stop(self)

    def get_default_dh_dl_address(self):
        '''
        Return the (DH, DL) tuple for downloading to nodes as DH/DL
        '''
        return gw_extended_address_tuple()

    def get_total_sleep_cycle_msec(self):
        '''
        Return the sleep_time + wake_time, or 0 if no sleep cycle
        '''
        sleep_time_ms = SettingsBase.get_setting(self, 'sleep_time')
        if sleep_time_ms > 0:
            sleep_time_ms += SettingsBase.get_setting(self, 'wake_time')
        return sleep_time_ms

    def is_digimesh(self):
        return True

    def wait_for_awake(self):
        '''
        Returns when the network wakes up (or on shutdown signal).
        '''
        # MAGIC NUMBER: response time is 3 seconds
        while not self._awakeEvent.isSet():
            if self.listener._stopevent.isSet():
                return
            self._awakeEvent.wait(3)

    def network_asleep(self):
        '''
        Returns True when the network is asleep.
        '''
        if self.__sleeping:
            return not self._sleepEvent.isSet()
        else: # network never sleeps
            return False

    def validate_network_protocol(self, module_id, product_id):
        ''' Fail if this is being used on a non DigiMesh network. '''
        if module_id not in SUPPORTED_MODULES:
            raise DigiMeshDeviceManagerUnsupportedModuleType(
                'module_id: %i, accepted module ids: %s' % (
                    module_id, SUPPORTED_MODULES))

    def xbee_get_node_list(self, refresh=False, clear=False):
        '''
        Returns the DigiMeshDeviceManager's internal copy of the network
        node list.

        If refresh is True, a network discovery will be performed.

        If clear is True, the node list will be cleared before
        a discovery is performed (only if refresh is True).  Be careful
        with the clear command.  Executing this function may disrupt internal
        network management logic.

        HACK: Once the xbee.get_node_list bug is fixed, this method
              should be removed (and reverted to it's superclass method).

        '''
        if clear:
            self.__xbee_node_list = []

        self.NETWORK_DISCOVER_HACK.clear()
        new_node_candidates = xbee.get_node_list(refresh=refresh)
        self.wait_until_xbee_ready()
        self.NETWORK_DISCOVER_HACK.set()

        for node in new_node_candidates:
            is_new_node = True
            for old_node in self.__xbee_node_list:
                if addresses_equal(node.addr_extended,
                                   old_node.addr_extended):
                    is_new_node = False
            if not is_new_node:
                continue
            # new node, add it to local list:
            self.__xbee_node_list.append(node)

        return self.__xbee_node_list

    def wait_until_xbee_ready(self):
        ''' wait until we can read something again '''
        while True:
            try:
                # HACK: remove once firmware issue resolved
                ddo_get_param(None, 'SH')
                break
            except Exception:
                sleep(1)
                continue

    def get_ddo_block(self, extended_address, add_dh_dl=False):
        '''
        Returns an XBeeConfigBlockDDO.

        The method is DEPRECATED.
        Addressing information is now added at "xbee_device_configure"
        time.
        '''
        self._tracer.debug('digimesh_device_manager.get_ddo_block() ' \
                               'is DEPRECATED. Use XBeeConfigBlockDDO(' \
                               'extended_address) directly. (Import it from' \
                               ' xbee_device_manager.)')

        xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)

        # if add_dh_dl and self._dh_dl_addr is not None:
        #     # Set the destination for unaddressed/AT-mode/IS-data
        #     xbee_ddo_cfg.add_parameter('DH', self._dh_dl_addr[0])
        #     xbee_ddo_cfg.add_parameter('DL', self._dh_dl_addr[1])

        return xbee_ddo_cfg

    def get_sleep_block(self, extended_address, sleep=None,
                        sleep_rate_ms=0,
                        awake_time_ms=0,
                        sample_predelay=None):
        '''
        Returns an XBeeConfigBlockSleep configured for this
        network type.
        '''
        xbee_sleep_cfg = XBeeConfigBlockSleep(extended_address)

        #if sleep and sleep_rate_ms != 0:
        #    self._tracer.warning('The device driver for %s ' \
        #                             'called get_sleep_block() with ' \
        #                             'sleep settings that ' \
        #                             'will be ignored. (Sleep/wake cycles ' \
        #                             'are synchronized with the gateway in ' \
        #                             'a digimesh network.)', extended_address)

        if sleep == None:
            # blank configuration
            return xbee_sleep_cfg

        if sleep:
            xbee_sleep_cfg.sleep_mode_set(DM_SLEEP)

        else:
            xbee_sleep_cfg.sleep_mode_set(DM_SUPPORT)

        if SettingsBase.get_setting(self, 'set_if'):
            # then try to manage the IR/IF values

            total_ms = self.get_total_sleep_cycle_msec()
            self._tracer.debug("Total Cycle = %dms, Requested = %dms",
                total_ms, sleep_rate_ms)

            if sleep_rate_ms == 0:
                # then assume no IS data, or will be manually polled only
                IR_ms = 0
                IF_cycles = 1

            else:
                IR_ms = 0xFFFF
                IF_cycles = int(round(float(sleep_rate_ms) / float(total_ms)))
                if IF_cycles <= 0:
                    IF_cycles = 1
                elif IF_cycles > 0xFF:
                    self._tracer.warning('Based on total cycle time of %d ' \
                            'the max sleep_rate is %d', total_ms,
                            total_ms * 0xFF)
                    IF_cycles = 0xFF
                # else IF_cycles >= 1 and <= 0xFF

            self._tracer.debug("Setting IR = 0x%04X  IF = %d",
                                    IR_ms, IF_cycles)
            xbee_sleep_cfg._add_parameter('IR', IR_ms)
            xbee_sleep_cfg._add_parameter('IF', IF_cycles)

            if sample_predelay:
                xbee_sleep_cfg._add_parameter('WH', sample_predelay)

        return xbee_sleep_cfg

    def _set_sleep_wake(self, sleep_time, wake_time):
        '''
        Set the network's sleep/wake cycle to the passed parameters.

        sleep_time and wake_time are both in milliseconds.
        '''
        self.property_set('sleep_time', Sample(0, value=sleep_time,
                                               unit='ms'))
        self.property_set('wake_time', Sample(0, value=wake_time,
                                              unit='ms'))

        # need to set SM/SP/ST here to enable switching between
        # sleep and non-sleep in gateway.
        if sleep_time == 0:
            # then no sleep
            self._tracer.debug("Disabling Sleep; set SM=0, run fully awake")
            self.__sleeping = False
            self._awakeEvent.set()
            # disable sleep support
            self.xbee_device_ddo_set_param(None, 'SM', 0x0, timeout=15)
            # note: these two at 'not available' when SM=0x0
            # ddo_set_param(None, 'SP', 0x0)
            # ddo_set_param(None, 'ST', 0x7D0)

            # define as non-sleep coordinator
            self.xbee_device_ddo_set_param(None, 'SO', 0x2, timeout=15)

            self.listener.stop()
            self.remove_all_properties()

        else:
            # SM=0x7 for non-sleeping gway only
            self.__sleeping = True
            self._awakeEvent.clear()
            self._tracer.debug("Enabling Sleeping, sleep=%d, wake=%d",
                                sleep_time, wake_time)
            # sleep support
            self.xbee_device_ddo_set_param(None, 'SM', 0x7, timeout=15)
            self.xbee_device_ddo_set_param(None, 'SP', sleep_time / 10)
            self.xbee_device_ddo_set_param(None, 'ST', wake_time)

            # preferred sleep coord with api msgs
            self.xbee_device_ddo_set_param(None, 'SO', 0x5, timeout=15)

        self.xbee_device_ddo_set_param(None, 'WR', '')
