############################################################################
#                                                                          #
# Copyright (c)2008-2012, Digi International (Digi). All Rights Reserved.  #
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
XBee Device Manager

The XBee Device Manager class and related classes.

This is the superclass for the ZigBee and DigiMesh device managers.

Using XBeeDeviceManager directly in a DIA configuration is DEPRECATED.
It currently behaves as a ZigBeeDeviceManager for backwards compatibility.
'''

import traceback

import devices.xbee.common.bindpoints as bindpoints

# constants

MAX_RECVFROM_LEN = 256
# No harm in asking for more than allowed
# ZB-PRO is 255 with fragmentation support
# DM is about 240 to 250
# SE is 128

# states:
STATE_NOT_READY = 0x0
STATE_READY = 0x1

# behavior flags:
BEHAVIOR_NONE = 0x0
BEHAVIOR_HAS_ATOMIC_DDO = 0x1

DH_DL_REFRESH_INITIAL_WAIT = 40  # wait time in seconds before first write

# These channels are shared between zigbee and digimesh.
BINDPOINTS = {bindpoints.JOIN: {'endpoint': 0xe8,
                                'profile_id': 0xc105,
                                'cluster_id': 0x95},

              bindpoints.SERIAL: {'endpoint': 0xe8,
                                  'profile_id': 0xc105,
                                  'cluster_id': 0x11},

              bindpoints.SAMPLE: {'endpoint': 0xe8,
                                  'profile_id': 0xc105,
                                  'cluster_id': 0x92}}



# imports
import traceback

import errno
import socket
from select import select
import threading
import digitime
import types

try:
    import xbee
except:
    import zigbee as xbee

from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from devices.xbee.common.addressing import gw_extended_address_tuple, \
     validate_address
from channels.channel_source_device_property import *

from common.digi_device_info import device_firmware_gte_to, get_platform_name
from common.helpers.parse_duration import parse_time_duration

from common.types.boolean import Boolean
from devices.xbee.xbee_device_manager.xbee_device_manager_configurator \
    import XBeeDeviceManagerConfigurator
from devices.xbee.xbee_device_manager.xbee_device_state import XBeeDeviceState
from devices.xbee.xbee_device_manager.xbee_ddo_param_cache \
    import XBeeDDOParamCache
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs import *
from devices.xbee.xbee_config_blocks.xbee_config_block_final_write import \
    XBeeConfigBlockFinalWrite
from devices.xbee.xbee_config_blocks.xbee_config_block_wakeup import \
      XBeeConfigBlockWakeup
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo import \
    AbstractXBeeConfigBlockDDO, XBeeConfigBlockDDO
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep \
    import SM_DISABLED, XBeeConfigBlockSleep
from devices.xbee.common.addressing import addresses_equal, \
    normalize_address, address_to_tuple, tuple_to_address
from devices.xbee.common.prodid import \
    MOD_XB_802154, MOD_XB_ZNET25, MOD_XB_ZB, MOD_XB_S2C_ZB, parse_dd
from devices.xbee.common.ddo import \
     GLOBAL_DDO_TIMEOUT, GLOBAL_DDO_RETRY_ATTEMPTS, DDOTimeoutException


# exceptions
class XBeeDeviceManagerEndpointNotFound(KeyError):
    pass


class XBeeDeviceManagerInstanceExists(Exception):
    pass


class XBeeDeviceManagerInstanceNotFound(KeyError):
    pass


class XBeeDeviceManagerUnknownEventType(ValueError):
    pass


class XBeeDeviceManagerEventSpecNotFound(ValueError):
    pass


class XBeeDeviceManagerStateException(Exception):
    pass


class XBeeDeviceManagerBadBindpointException(Exception):
    '''
    Raised when an improperly formatted bindpoint is passed
    to get_bindpoint().
    '''
    pass


def _true_or_zero(x):
    ''' helper for get_rx_event_spec '''
    if x != False:
        return x
    else:
        return 0x0


# classes
class XBeeEndpoint(object):
    '''
        This class stores the data for a given XBee endpoint.
        This includes the file description of our socket,
        the receive queue and a use reference count.

    '''
    __slots__ = ['reference_count', 'sd', 'xmit_q']

    def __init__(self, sd):
        self.reference_count = 0
        self.sd = sd
        self.xmit_q = []


class XBeeDeviceManager(DeviceBase, threading.Thread):
    '''
        This class implements the XBee Device Manager.

        Keyword arguments:

        * **name:** the name of the device instance.
        * **core_services:** the core services instance.

        Advanced Settings:

        * **skip_config_addr_list:** XBee addresses appearing in this list will
          skip directly from the INIT state to the RUNNING state, by-passing
          the application of any configuration blocks.
          Not required, it is empty by default.

            .. Warning::
                Be careful when using this setting. By specifying
                nodes in this list, they will not be configured by the
                DIA framework, potentially leaving the node in an
                unusable state.

        * **addr_dd_map:** A map of XBee addresses to DD device type values.
          By configuring this mapping dictionary, a node's DD value will not
          have to be queried from the network before a node is configured.
          Not required, it is empty by default.

            .. Warning::
                Be careful when using this setting. It asserts a node to be of
                a particular module and product type. Using the wrong value
                could cause a node to be configured incorrectly.

        * **worker_threads:** Number of handles to manage background tasks in
          the DIA framework. Not required, 1 by default.

    '''
    MINIMUM_RESCHEDULE_TIME = 10

    DH_DL_REFRESH_NOT_SET = None
    DH_DL_REFRESH_ONCE = 'once'         # boot/broadcast and config
    DH_DL_REFRESH_CONFIG = 'config'     # config only

    # set a default here so derived classes can over-ride easily
    DH_DL_FORCE_DEFAULT = 'true' # means auto based on Xbee type
    DH_DL_REFRESH_DEFAULT = DH_DL_REFRESH_CONFIG
    DH_DL_REFRESH_MININUM = 60 # in seconds, so once a minute/60 seconds

    # default broadcast MAC
    MESH_BROADCAST = "00:00:00:00:00:00:FF:FF!"

    # allowing deprecated creation
    def __new__(cls, *al, **nal):
        if cls.__name__ == 'XBeeDeviceManager':
            from zigbee_device_manager import ZigBeeDeviceManager
            return ZigBeeDeviceManager(*al, **nal)
        return super(XBeeDeviceManager, cls).__new__(cls, *al, **nal)

    def __init__(self, name, core_services, settings_list=None,
                 property_list=None):
        # DeviceBase will create:
        #   self._name, self._core, self._tracer,

        ## Local state variables and resources:
        self.__state = STATE_NOT_READY
        self.__behavior_flags = BEHAVIOR_NONE
        self.__lock = threading.RLock()
        self.__sched = core_services.get_service("scheduler")
        self.__xbee_device_states = {}
        self.__xbee_ddo_param_cache = XBeeDDOParamCache()
        self.__xbee_node_list = []
        # Event specs are stored as tuples (spec, device_state):
        self.__rx_event_spec_state_map = {False: []}
        self.__xbee_endpoints = {}
        self.__xbee_module_type = None
        self.__behavior_flags = 0

        # SN/SP override control (overridden by ZB manager sometimes
        # for passing into sleep_block.prepare_network)
        # If it is provided, must be a dictionary including
        # 'SN' and 'SP' as strings, with integer values.
        self._sn_sp_override = None

        ############# subclass inspection ##########
        self._dh_dl_addr = None

        ########### end subclass inspection #######

        ####### subclass overrides ######
        # default is block forever
        self._select_timeout = None
        self._awakeEvent = threading.Event()
        self._awakeEvent.set()

        # HACK: this is a temporary workaround for a network
        #       discovery issue with digimesh modules with SM=0x7
        self.NETWORK_DISCOVER_HACK = threading.Event()
        self.NETWORK_DISCOVER_HACK.set()

        ####### end subclass overrides ######

        # Setup internal socket which can be used for unblocking the
        # internal event loop asynchronously:
        self._outer_sd, self._inner_sd = socket.socketpair()
        for sde in [self._outer_sd, self._inner_sd]:
            sde.setblocking(0)

        if settings_list == None:
            settings_list = []

        if property_list == None:
            property_list = []

        ## Settings table Definition:
        settings_list.extend([
            Setting(
                name='skip_config_addr_list', type=list, required=False,
                default_value=[]),
            Setting(
                name='addr_dd_map', type=dict, required=False,
                default_value={}),
            Setting(
                name='worker_threads', type=int, required=False,
                default_value=1,
                verify_function=lambda x: x >= 1),
            Setting(
                name="update_skiplist", type=Boolean, required=False,
                default_value=Boolean(False)),

            # valid settings are including:
            # - None/'none'/False/'false' = don't effect DH/DL at all
            # - 'coordinator' = use MAC of coordinator for DH/DL
            # - 'true'/True = use the best value based on XBee type
            Setting(
                name='dh_dl_force', type=str, required=False,
                default_value=self.DH_DL_FORCE_DEFAULT,
                verify_function=self.__verify_dh_dl_force),

            # valid settings are including:
            # - None, 'none' = don't effect DH/DL at all
            # - 'once' = only set DH/DL in config, plus 1 broadcast
            # - 'config' = only set DH/DL in config, no broadcast
            # - time with tag, like '5 min', '1 day'
            # - raw number assumed minutes
            Setting(
                name='dh_dl_refresh_min', type=str, required=False,
                # TODO: what is a reasonable valid range?
                default_value=self.DH_DL_REFRESH_DEFAULT,
                verify_function=self.__verify_dh_dl_min),
        ])

        ## Initialize the Devicebase interface:
        DeviceBase.__init__(self, name, core_services,
                                settings_list, property_list)

        self._tracer.calls("XBeeDeviceManager.__init__()")

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    ## Internal functions:
    def __unblock_inner_select(self):
        self._outer_sd.send('a')

    def __endpoint_add(self, endpoint):
        self._tracer.xbee("__endpoint_add(): endpoint = %d", endpoint)

        self.__lock.acquire()
        try:
            if endpoint not in self.__xbee_endpoints:
                sd = socket.socket(socket.AF_ZIGBEE, socket.SOCK_DGRAM,
                                self.__xbee_endpoint_protocol)
                try:
                    sd.bind(('', endpoint, 0, 0))
                except:
                    raise Exception(("Unable to bind endpoint 0x%02x!"
                                    " Check that no other programs are running"
                                    " or are set to run on the device. ") % (
                                        endpoint))

                self.__xbee_endpoints[endpoint] = XBeeEndpoint(sd)

            self.__xbee_endpoints[endpoint].reference_count += 1
            self._tracer.xbee("__endpoint_add(): reference_count now = %d",
                                self.__xbee_endpoints[endpoint].\
                                reference_count)
        finally:
            self.__lock.release()

        self.__unblock_inner_select()
        self._tracer.xbee('__endpoint_add(): exit')

    def __endpoint_remove(self, endpoint):
        self.__lock.acquire()
        try:
            if endpoint not in self.__xbee_endpoints:
                raise XBeeDeviceManagerEndpointNotFound(
                    "endpoint 0x%02x has no active references." % (endpoint))
            self.__xbee_endpoints[endpoint].reference_count -= 1
            if not self.__xbee_endpoints[endpoint].reference_count:
                self.__xbee_endpoints[endpoint].sd.close()
                del(self.__xbee_endpoints[endpoint])
        finally:
            self.__lock.release()

    def __select_config_now_chk(self, buf, addr):
        # self._tracer.xbee("__select_config_now_chk() enter")
        self.__lock.acquire()
        try:
            matching_xbee_states = \
                filter(lambda s: s.is_config_scheduled() and \
                           addresses_equal(s.ext_addr_get(), addr[0]),
                       self.__xbee_device_states.values())

            for xbee_state in matching_xbee_states:
#                self._tracer.xbee("__select_config_now_chk():" +
#                                    "found matching node %s",
#                                    xbee_state.ext_addr_get())

                if xbee_state.configuration_sched_handle_get():
                    # If the node had a scheduled configuration retry,
                    # cancel it.
                    try:
#                        self._tracer.xbee("__select_config_now_chk():" +
#                                            " un-scheduling event")
                        self.xbee_device_schedule_cancel(
                            xbee_state.configuration_sched_handle_get())
#                        self._tracer.xbee("__select_config_now_chk():" +
#                                            " event unscheduled")
                    except Exception, e:
                        # ignore any failure to cancel scheduled action
                        self._tracer.warning(('__select_config_now_chk(): ' +
                                              'Error in canceling scheduled ' +
                                              'configuration event: %s') %
                                              (str(e)))

                # (Re-)schedule the configuration attempt ASAP:
                xbee_state.goto_config_immediate()
                xbee_state.configuration_sched_handle_set(
                    self.xbee_device_schedule_after(0,
                        self.__xbee_configurator.configure, xbee_state))

        finally:
            self.__lock.release()

#        self._tracer.xbee("__select_config_now_chk(): exit")

    def __select_rx_cbs_for(self, buf, addr):
        self._tracer.xbee("__select_rx_cbs_for(%s, %s)", buf, addr)
        self.__lock.acquire()

        #We create a one time use list that contains all rx_events that
        #at least match the mac address element.  This reduces the testing
        #set drastically.

        #All entries after hash comparison match the mac address element,
        #So additional address checks are not performed.

        proc_list = []
        if addr[0] in self.__rx_event_spec_state_map:
            proc_list = proc_list + self.__rx_event_spec_state_map[addr[0]]
        proc_list += self.__rx_event_spec_state_map[False]

        for rx_event, state in proc_list:
            # Update the time we last heard from the node:
            state.last_heard_from_set(digitime.time())
            if not state.is_running():
#                self._tracer.xbee("__select_rx_cbs_for(): cb not made, " +
#                                    "device %s not running.",
#                                    (str(rx_event.match_spec_get()[0])))
#
#                self._tracer.xbee("__select_rx_cbs_for(): device is in " +
#                                    "state: %d", state._get_state())
                continue

            if isinstance(rx_event, XBeeDeviceManagerRxConfigEventSpec):
                if not state.is_config_active():
                    self._tracer.xbee('__select_rx_cbs_for(): cb ' \
                                    'not made, device %s not configured. ' \
                                    '(in state %s)',
                                    (str(rx_event.match_spec_get()[0])))
                    continue

            if not rx_event.match_spec_test(addr, mac_prematch=True):
                self._tracer.xbee('__select_rx_cbs_for(%s): cb not made,'\
                                    ' test failed. (Spec was %s)',
                                    str(addr),
                                    str(rx_event.match_spec_get()))
                continue

            try:
                rx_event.cb_get()(buf, addr)
            except Exception:
                # exceptions in driver callbacks are non-fatal to us
                self._tracer.error('Exception during rx callback for ' +
                                    'addr = %s',  str(addr))
                self._tracer.debug(traceback.format_exc())
                pass

        self.__lock.release()
        return

    def __convert_to_lower(self, a):
        if a == None:
            return a
        else:
            return a.lower()


    def initialize_sleep_config(self):
        '''
        Called at the beginning of the run() main loop to
        configure sleep parameters. (Digimesh overrides this method.)
        '''
        pass

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):
        '''
                Called when new configuration settings are available.

                Must return tuple of three dictionaries: a dictionary of
                accepted settings, a dictionary of rejected settings,
                and a dictionary of required settings that were not
                found.

        '''

        self._tracer.calls("XBeeDeviceManager.apply_settings()")

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        if len(rejected) or len(not_found):
            self._tracer.error('Settings rejected/not found: %s %s',
                                rejected, not_found)

        # convert all skip_config addresses to lower case:
        accepted["skip_config_addr_list"] = map(
             self.__convert_to_lower, accepted["skip_config_addr_list"])

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        '''Start the device driver.  Returns bool.'''
        self._tracer.calls("XBeeDeviceManager.start()")

        threading.Thread.start(self)

        return DeviceBase.start(self)

    def stop(self):
        '''Stop the device driver.  Returns bool.'''
        self._tracer.calls("XBeeDeviceManager.stop()")

        self.__xbee_configurator.stop()

        self.__stopevent.set()
        self.__unblock_inner_select()

        return DeviceBase.stop(self)

    def _coordinator_ddo_config(self):
        '''
        helper for run() - allow derived classes to init the coordinator
        after the xbee_device_manager has validated the technologies.

        For example, the ZigBeeDeviceManager needs to check child-table
        status and the source-routing settings.
        '''
        return

    def _build_wait_lists(self):
        '''
        helper for run()

        Returns (read_list, write_list, sd_to_endpoint_map)
        '''
        self.__lock.acquire()
        # Build wait lists for select()
        rl = [self._inner_sd]
        rl += [self.__xbee_endpoints[ep].sd for ep in \
               self.__xbee_endpoints]

        wl = []
        sd_to_endpoint_map = dict()
        # While building wl, build the sd_to_endpoint map:
        for ep in filter(lambda ep: len(self.__xbee_endpoints[ep].xmit_q),
                    self.__xbee_endpoints):
            sd = self.__xbee_endpoints[ep].sd
            wl.append(sd)
            sd_to_endpoint_map[sd] = ep
        self.__lock.release()
        return rl, wl, sd_to_endpoint_map

    def _process_reads(self, rl):
        '''
        helper for run()

        Returns True if we should re-loop immediately instead
        of processing writes (due to an internal unblock).
        '''
        # Process reads:
        for sd in rl:
            # Check to see if we were told to unblock internally:
            if sd is self._inner_sd:
                sd.recv(1)
                return True

            # Process endpoint messages and perform callbacks:
            buf, addr = sd.recvfrom(MAX_RECVFROM_LEN)

            # Check to see if this node needs to be configured,
            # and if so, configure it now:
            self.__select_config_now_chk(buf, addr)
            # Check to see if this node has any RX callbacks
            # to perform:
            self.__select_rx_cbs_for(buf, addr)
        return False

    def _process_writes(self, wl, sd_to_endpoint_map):
        ''' helper for run() '''
        for sd in wl:
            if sd not in sd_to_endpoint_map:
                continue

            if self.network_asleep():
                return

            # N.B: the entire xmit queue is not drained here
            # for better interleaving of reads with writes.
            self.__lock.acquire()
            try:
                ep = sd_to_endpoint_map[sd]
                buf, addr = self.__xbee_endpoints[ep].xmit_q[0]
                try:
                    num_bytes = sd.sendto(buf, 0, addr)
                    # print "XBeeDeviceManager: xmit wrote %d bytes" % \
                    # (num_bytes)
                except socket.error:
                # xmit of message failed, will retry in select() loop
                    continue
                # xmit succeeded, de-queue message:
                self.__xbee_endpoints[ep].xmit_q.pop(0)
            finally:
                self.__lock.release()

    def _identify_xbee(self):
        '''
        Determine the appropriate protocol for setting up new sockets
        and initializes internals.

        Returns (module_id, product_id).
        '''
        self.__xbee_endpoint_protocol = socket.XBS_PROT_TRANSPORT
        try:
            gw_dd = self.__xbee_configurator.ddo_get_param(None, 'DD',
                                                           use_cache=True)
        except Exception, e:
            # TODO: This exception may be raised when using SE XB FW
            #       here (31xx)

            # TODO: determine the appropriate DD value to use here.
            gw_dd = 0

        module_id, product_id = parse_dd(gw_dd)
        self.__xbee_module_type = module_id
        if module_id == MOD_XB_802154:
            self.__xbee_endpoint_protocol = socket.XBS_PROT_802154
        elif module_id == MOD_XB_ZNET25:
            self.__xbee_endpoint_protocol = socket.XBS_PROT_TRANSPORT
        elif module_id == MOD_XB_ZB:
            self.__xbee_endpoint_protocol = socket.XBS_PROT_APS
        elif module_id == MOD_XB_S2C_ZB:
            self.__xbee_endpoint_protocol = socket.XBS_PROT_APS
        else:
            self.__xbee_endpoint_protocol = socket.XBS_PROT_TRANSPORT
        return module_id, product_id

    ## Thread execution begins here:
    def run(self):

        self._tracer.calls("XBeeDeviceManager.run()")

        # TODO: dynamically determine how many parallel DDO requests may take
        #       place and give that number to the configurator.
        self.__xbee_configurator = \
            XBeeDeviceManagerConfigurator(self,
                SettingsBase.get_setting(self, "worker_threads"))

        module_id, product_id = self._identify_xbee()

        try:
            self.validate_network_protocol(module_id, product_id)
        except ValueError, e:
            self._tracer.critical('This xbee manager cannot use the xbee ' \
                                  'module on the gateway. (Maybe ' \
                                  'there is a digimesh/zigbee mismatch?)')
            self._core.request_shutdown()
            raise

        # do specific gateway/coordinator DDO checks like ZB Source Routing
        self._coordinator_ddo_config()

        # Determine XBee behaviors based on the Digi platform and version.
        if get_platform_name() == 'digix3':
            self.__behavior_flags |= BEHAVIOR_HAS_ATOMIC_DDO
            
        elif get_platform_name() == 'digiconnect':
            if not device_firmware_gte_to((2, 8, 3)):
                self.__behavior_flags |= BEHAVIOR_NEED_DISCOVER_WORK_AROUND
            else:
                self.__behavior_flags |= BEHAVIOR_HAS_ATOMIC_DDO

        elif get_platform_name() == 'linux2':
            self.__behavior_flags |= BEHAVIOR_HAS_ATOMIC_DDO

        self._tracer.xbee("retrieving node list")
        self.xbee_get_node_list(refresh=True, clear=True)

        self.__parse_dh_dl_force(SettingsBase.get_setting(self, \
                                                     "dh_dl_force"))

        # at this point, self._dh_dl_addr should be valid for all relevent
        # uses by the DM/ZB managers
        if self._dh_dl_addr is None:
            self._tracer.debug('node DH/DL will not be changed')
            self.__dh_dl_refresh_sec = None

        else:
            if self._tracer.debug():
                # we double this up because tuple_to_address() is complex
                self._tracer.debug('node DH/DL will be forced to %s', \
                                    tuple_to_address(self._dh_dl_addr))

            try:
                self.__dh_dl_refresh_sec = self.__parse_dh_dl_min(
                    SettingsBase.get_setting(self, "dh_dl_refresh_min"))
            except:
                traceback.print_exc()

        self.initialize_sleep_config()

        addr_dd_dict = SettingsBase.get_setting(self, "addr_dd_map")
        for addr in addr_dd_dict:
            self._xbee_device_ddo_param_cache_set(addr,
                'DD', addr_dd_dict[addr])

        self.wait_until_xbee_ready()
        self.__state = STATE_READY

        while True:
            try:
                # Check to see if our thread's stop flag is set:
                if self.__stopevent.isSet():
                    self.__stopevent.clear()
                    break

                rl, wl, endpoint_map = self._build_wait_lists()
                self.wait_for_awake()

                # Wait for there is work for us to perform:
                rl, wl, _ = select(rl, wl, [], self._select_timeout)

                if self._process_reads(rl):
                    # we got an internal unblock event
                    continue
                self._process_writes(wl, endpoint_map)
            except Exception, e:
                self._critical_die(e)


    def is_digimesh(self):
        '''Digimesh_device_manager will over-ride, returning True.
        '''
        return False

    def is_zigbee(self):
        '''Zigbee_device_manager will over-ride, returning True.
        '''
        return False

    def _schedule_broadcast(self):
        '''
        Start a repeating broadcast_address() at __dh_dl_refresh_sec intervals.
        '''
        if self.__dh_dl_refresh_sec in \
                    [None, self.DH_DL_REFRESH_NOT_SET,
                    self.DH_DL_REFRESH_ONCE, self.DH_DL_REFRESH_CONFIG]:
            self._tracer.debug('Do Not Schedule Broadcast DH/DL refresh')

        else:  # we send broadcast and schedule a repeat
            if self._tracer.debug():
                # use double because time.asctime() computationally expensive
                self._tracer.debug('Broadcast DH/DL refresh at %s', \
                    digitime.asctime())

            # generally is 'safer' to rescedule BEFORE we do the action,
            # makes the system self restarting if an unexpected error occurs
            self.xbee_device_schedule_after(self.__dh_dl_refresh_sec,
                                            self._schedule_broadcast)
            self._broadcast_address()

    def _broadcast_address(self):
        '''
        Set all listeners' destination to the configured device.
        '''
        # sanity check
        if self._dh_dl_addr is None:
            # then is None or False
            raise Exception('_broadcast_address called with broken logic!')

        # Since is Broadcast with NO response, need timeout=0 or
        # xbee_device_ddo_set_param() throws an exception of no ACK
        self.xbee_device_ddo_set_param(self.MESH_BROADCAST, 'DH', \
                                    self._dh_dl_addr[0], timeout=0)
        self.xbee_device_ddo_set_param(self.MESH_BROADCAST, 'DL', \
                                    self._dh_dl_addr[1], timeout=0)
        return

#######################################################################
################### overridden methods for children ###################
#######################################################################
    def get_bindpoint(self, name):
        '''
        Return the actual channel type that channels.* maps
        to for this manager type.

        For both ZigbeeDeviceManager and DigiMeshDeviceManager,
        this is a dict in the form:
            {'endpoint': <int>,
             'profile_id': <int>,
             'cluster_id': <int>}

        The name can be one of three things:
            - a defined BINDPOINT (via devices.xbee.common.bindpoints)
            - a list of three values (as in the old style)
            - a dictionary with keys in 'tags' (see tags below)

        (These are all defined in the global variable BINDPOINTS at the
         top of this module.)

        In the future (when 802.15.4 is supported) this return value
        may change.
        '''
        # isinstance necessary to prevent TypeError:list objects unhashable
        if isinstance(name, int) and name in BINDPOINTS:
            return BINDPOINTS[name]
        else:
            tags = ('endpoint', 'profile_id', 'cluster_id')
            try:
                if len(name) == 3 and (isinstance(name, list) or \
                    isinstance(name, tuple)):
                    return dict(zip(tags, name))
                if len(name) == 3 and isinstance(name, dict):
                    for i in tags:
                        if i not in name:
                            raise XBeeDeviceManagerBadBindpointException(name)
                    return name
            except Exception, e:
                raise XBeeDeviceManagerBadBindpointException(name)
        raise XBeeDeviceManagerBadBindpointException(name)


    def wait_for_awake(self):
        '''
        Returns when the network is ready to communicate.
        '''
        return True

    def network_asleep(self):
        '''
        Returns True when network is not ready to communicate.
        '''
        pass

    def validate_network_protocol(self, module_id, product_id):
        '''
        Raises an error if the discovered network protocol is
        incompatible with this device manager.
        '''
        pass

    def wait_until_xbee_ready(self):
        '''
        Returns when the device's xbee responds to queries.

        (DigiMesh overrides this function, because calling
         self.xbee_get_node_list() makes it unresponsive for
         a bit.)
        '''
        pass

    def get_ddo_block(self, extended_address):
        '''
        Returns an XBeeConfigBlockDDO with addressing information
        configured.
        '''
        raise Exception('Virtual function')

    def get_sleep_block(self, extended_address, sleep=None,
                        sleep_rate_ms=0,
                        awake_time_ms=5000,
                        sample_predelay=None):
        '''
        Returns an XBeeConfigBlockSleep configured for this
        network type.

        If sleep==None, no sleep-related configuration is done to the
        device by the xbee manager. (The call returns a blank
        configuration block. But if a sleep parameter is not being
        passed, you shouldn't be calling get_sleep_block in the first
        place...)
        '''
        raise Exception('Virtual function')

    def register_sample_listener(self, instance, extended_address,
                                 callback):
        self.register_rx_listener(instance, extended_address,
                                  callback, bindpoints.SAMPLE)

    def register_serial_listener(self, instance, extended_address,
                                 callback):
        self.register_rx_listener(instance, extended_address,
                                  callback, bindpoints.SERIAL)

    def register_rx_listener(self, instance, extended_address,
                             callback, bindpoint=bindpoints.SERIAL):
        '''
        Depreciates get_rx_event_spec()

        bindpoint is one of:
            1) a symbol from devices.xbee.common.bindpoints
            2) a tuple or list of (endpoint, profile_id, cluster_id)
            3) a dictionary with endpoint, profile_id, and cluster_id as keys

        Handles all internal event spec configuration.
        '''
        args = {'extended_address': extended_address,
                'callback': callback}
        tags = ('endpoint', 'profile_id', 'cluster_id')

        if bindpoint in BINDPOINTS:
            args.update(BINDPOINTS[bindpoint])
        # only valid thing is a list of tuples or an unlisted dict
        elif len(bindpoint) == 3 and (isinstance(bindpoint, list) or \
                isinstance(bindpoint, tuple)):
            args.update(dict(zip(tags, bindpoint)))
        elif len(bindpoint) == 3 and isinstance(bindpoint, dict):
            for i in tags:
                if i not in bindpoint:
                    raise XBeeDeviceManagerBadBindpointException(bindpoint)
            args.update(bindpoint)
        else:
            raise XBeeDeviceManagerBadBindpointException(bindpoint)

        xbdm_rx_event_spec = self._get_rx_event_spec(**args)
        self.xbee_device_event_spec_add(instance, xbdm_rx_event_spec)

    def get_rx_event_spec(self, *args, **kargs):
        '''
        We still need this.
        '''
        # self._tracer.warning('driver for %s used deprecated method for ' \
        #                      'event callback registration.' % args[0])
        return self._get_rx_event_spec(*args, **kargs)

    def _get_rx_event_spec(self, extended_address, callback,
                           endpoint=None, profile_id=False,
                           cluster_id=False, listen_endpoint=None):
        '''
        Returns an XBeeeDeviceManagerRxEventSpec configured for this
        network type.

        **args**
        - extended_address to False to enable for all addresses.

        - endpoint : defaults to 0xe8 set to False to enable
                     for all endpoints

        - listen_endpoint: if the cluster to bind on is different
          than cluster_id, set this. (Otherwise, the the cluster_id is
                                      bound.) (This applies to DigiMesh.)
        '''
        if endpoint == None:
            endpoint = 0xe8

        xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec.cb_set(callback)
        matches = map(lambda x: x != False, (extended_address,
                                             endpoint,
                                             profile_id,
                                             cluster_id))
        # add fake extended_address name on False
        if extended_address == False:
            extended_address = None

        names = map(_true_or_zero, (endpoint, profile_id, cluster_id))

        name_set = [extended_address]
        name_set.extend(names)

        xbdm_rx_event_spec.match_spec_set(tuple(name_set), tuple(matches),
                                          listen_endpoint=listen_endpoint)

        return xbdm_rx_event_spec

######################## end override section ###########################

    ## XBee Device Driver Interface function definitions:
    def xbee_device_register(self, instance):
        '''
        Register a device instance with the XBee Driver Manager.
        Returns True.

        This call needs to be made before any other requests of the
        XBee driver stack may be made.

        '''
        if instance in self.__xbee_device_states:
            raise XBeeDeviceManagerInstanceExists('instance already exists')

        # Ensure that we are ready to accept devices before allowing
        # this call to complete.
        while self.__state != STATE_READY:
            digitime.sleep(1)

        self.__lock.acquire()
        try:
            self.__xbee_device_states[instance] = XBeeDeviceState()
        finally:
            self.__lock.release()

        return True

    def xbee_device_unregister(self, instance):
        '''
        Unregister a device instance with the XBee Driver Manager.
        Returns True.

        This call will remove any Event Specifications which have been
        registered xbee_device_event_spec_add() and will de-allocate
        any resources which have been associated with this device.

        '''
        if instance not in self.__xbee_device_states:
            raise XBeeDeviceManagerInstanceNotFound('instance not found')

        self.__lock.acquire()
        try:
            # Remove any event specs this instance may have registered:
            for spec in self.__xbee_device_states[instance].event_spec_list():
                self.xbee_device_event_spec_remove(instance, spec)
            del(self.__xbee_device_states[instance])
        finally:
            self.__lock.release()

        return True

    def xbee_get_module_type(self):
        '''
        Returns the XBee module type installed in the gateway.

        See :py:mod:`~devices.xbee.common.prodid` for information on how to
        interpret this value.

        '''
        return self.__xbee_module_type

    def xbee_device_event_spec_add(self, instance, event_spec):
        '''
        Add a new event spec to our list of events we should react to.

        See:
        :py:mod:`~devices.xbee.xbee_device_manager.xbee_device_manager_event_specs`
        for the definition and structure of the event spec.

        '''
        if instance not in self.__xbee_device_states:
            raise XBeeDeviceManagerInstanceNotFound('instance not found')

        self.__lock.acquire()
        try:
            # Add the event spec, processed by spec type:
            if isinstance(event_spec, XBeeDeviceManagerRxEventSpec):
                # RxEventSpecs get added to a special list in the manager:
                spec = event_spec.match_spec_get()
                norm_address = normalize_address(spec[0][0])

                if spec[1][0] == False:
                    self.__rx_event_spec_state_map[False].append(
                        (event_spec, self.__xbee_device_states[instance]))
                else:
                    if not self.__rx_event_spec_state_map.\
                           has_key(norm_address):
                        self.__rx_event_spec_state_map[norm_address] = []
                    self.__rx_event_spec_state_map[norm_address].append(
                            (event_spec, self.__xbee_device_states[instance]))

#                self.__rx_event_spec_state_map.append(
#                    (event_spec, self.__xbee_device_states[instance]))
                # The endpoint is registered and the ext_addr is added to the
                # device state:
                # (get_listen_endpoint is a function, because some protocols
                # (like digimesh) can't actually be bound to specific
                # ports. But thankfully, it still reports the port on
                # received messages, so everything else works.
                self.__endpoint_add(endpoint=event_spec.get_listen_endpoint())
                self.__xbee_device_states[instance].ext_addr_set(spec[0][0])
            elif isinstance(event_spec, XBeeDeviceManagerRunningEventSpec):
                pass
            else:
                raise XBeeDeviceManagerUnknownEventType('unknown event ' \
                                                        'spec type: %s' % (
                                                    str(type(event_spec))))

            # Keep track of which instances own which specs in the device state
            self.__xbee_device_states[instance].event_spec_add(event_spec)
        finally:
            self.__lock.release()

    def xbee_device_event_spec_remove(self, instance, event_spec):
        '''
        Remove an existing event spec from our list of events we should
        react to.

        See:
        :py:mod:`~devices.xbee.xbee_device_manager.xbee_device_manager_event_specs`
        for the definition and structure of the event spec.

        '''
        if instance not in self.__xbee_device_states:
            raise XBeeDeviceManagerInstanceNotFound('instance not found')

        self.__lock.acquire()
        try:
            # Remove the spec from the device state:
            state = self.__xbee_device_states[instance]

            # Remove the event spec from the appropriate manager list:
            if isinstance(event_spec, XBeeDeviceManagerRxEventSpec):
                try:
                    spec = event_spec.match_spec_get()
                    if spec[1][0] == False:
                        self.__rx_event_spec_state_map[False].remove(
                                              (event_spec, state))
                    else:
                        norm_addr = normalize_address(spec[0][0])
                        rmobj = (event_spec, state)
                        self.__rx_event_spec_state_map[norm_addr].remove(rmobj)
                except:
                    raise XBeeDeviceManagerEventSpecNotFound(
                        'event specification not found')
            elif isinstance(event_spec, XBeeDeviceManagerRunningEventSpec):
                pass
            else:
                raise XBeeDeviceManagerUnknownEventType(
                      'unknown event spec type: %s' % (str(type(event_spec))))

            # Remove event spec from instance:
            state.event_spec_remove(event_spec)
        finally:
            self.__lock.release()

    def xbee_device_config_block_add(self, instance, config_block):
        '''Add a configuration block to a device instance.'''
        config_block.configurator_set(self.__xbee_configurator)
        self.__xbee_device_states[instance].config_block_add(config_block)

    def xbee_device_config_block_remove(self, instance, config_block):
        '''Remove a configuration block from a device instance.'''
        self.__xbee_device_states[instance].config_block_remove(config_block)

    def xbee_device_configure(self, instance):
        '''
        Configure a device with configuration blocks that were added with
        the xbee_device_config_block_add() method.

        Once xbee_device_configure() is called, a device may not have any
        more configuration blocks added to it.  Configuration of this
        device will be handled by the XBee Device Manager as quickly
        as it can be scheduled.

        '''
        device_state = self.__xbee_device_states[instance]
        ext_addr = self.__xbee_device_states[instance].ext_addr_get()

        # add addressing information (except for a fake xbee device)
        if self._dh_dl_addr is not None and \
           ext_addr != '00:00:00:00:00:00:00:00!':
            xbee_ddo_cfg = XBeeConfigBlockDDO(ext_addr)
            xbee_ddo_cfg.add_parameter('DH', self._dh_dl_addr[0])
            xbee_ddo_cfg.add_parameter('DL', self._dh_dl_addr[1])
            self.xbee_device_config_block_add(instance, xbee_ddo_cfg)

        if not device_state.is_initializing():
            raise XBeeDeviceManagerStateException(
                'device already configuring or is already running.')

        # Add initial attempt to extend wakeup of sleeping nodes
        # TODO: add an automatic prioritization to the config_blocks and
        #       ensure that this class would always be added to the end
        #       of the chain.
        if False:  # ext_addr: # CB doesn't work, don't do this until it does
            # TODO, FIXME: Find another wakeup mechanism
            initial_config_block = XBeeConfigBlockWakeup(ext_addr)
            initial_config_block.configurator_set(self.__xbee_configurator)
            self.__xbee_device_states[instance].config_block_list().insert(
                0, initial_config_block)
            # FIXME: Once this is a priority queue, this must change,
            # performing an insert will break the invariant if we use
            # a heapq

        if True in [isinstance(cb, AbstractXBeeConfigBlockDDO) for cb in \
            self.__xbee_device_states[instance].config_block_list()]:
            # Add final write:
            # TODO: add an automatic prioritization to the config_blocks and
            #       ensure that this class would always be added to the end
            #       of the chain.
            final_config_block = XBeeConfigBlockFinalWrite(ext_addr)
            final_config_block.configurator_set(self.__xbee_configurator)
            self.__xbee_device_states[instance].config_block_add(
                final_config_block)

        # Determine whether or not the node is in the "skip_config_addr_list"
        # setting.  If so, transition it to the running state
        # immediately, bypassing the configuration state:
        skip_config_addr_list = \
            SettingsBase.get_setting(self, "skip_config_addr_list")

        if ext_addr in skip_config_addr_list:
            self._tracer.info("node '%s' " +
                               "in skip config address list, promoting " +
                               "to RUNNING state.", ext_addr)
            device_state.goto_running()
            return

        self._tracer.info("node '%s' moved to CONFIGURE state.", ext_addr)

        device_state.goto_config_scheduled()

        self._xbee_device_configuration_heuristic(device_state)

    def xbee_device_ddo_get_param(self, dest, param,
                                    timeout=GLOBAL_DDO_TIMEOUT,
                                    use_cache=False):
        '''
        Works together with the XBee configurator thread to process
        a blocking DDO get request.

        If use_cache is True, the parameter will first be sought in the
        DDO parameter cache.  If the parameter is not found in the cache
        it will be set from a successful network request.

        It is necessary to channel DDO requests through this path
        (rather than with xbee.ddo_get_param()) in order to
        schedule an optimal number of pending DDO requests at one
        time.

        '''
        return self.__xbee_configurator.ddo_get_param(dest, param, timeout)

    def xbee_device_ddo_set_param(self, dest, param, value='',
                                    timeout=GLOBAL_DDO_TIMEOUT,
                                    order=False, apply=False):
        '''
        Works together with the XBee configurator thread to process
        a blocking DDO set request.

        It is necessary to channel DDO requests through this path
        (rather than with xbee.ddo_set_param()) in order to
        schedule an optimal number of pending DDO requests at one
        time.

        A side-effect of calling this function is that the internal DDO
        parameter cache will be updated if setting the parameter was
        successful.

        '''
        return self.__xbee_configurator.ddo_set_param(
                    dest, param, value=value, timeout=timeout, 
                    order=order, apply=apply)

    def xbee_device_schedule_after(self, delay, action, *args):
        '''
        Schedule an action (a method) to be called with ``*args``
        after a delay of delay seconds.  Delay may be less than a second.

        If the scheduler gets behind it will simply get behind.

        All tasks will be executed from a separate thread context than
        other event callbacks from the XBee Device Manager.  This means
        that if your driver receives callbacks from the scheduler and
        processes events from the XBee Device Manager (e.g a receive
        packet event), the called driver will have to have its vital
        state data protected by a lock or other synchronization device.

        '''
        return self.__sched.schedule_after(delay, action, *args)

    def xbee_device_schedule_cancel(self, event_handle):
        '''
        Try and cancel a schedule event.

        The event_handle is parameter is the return value from a previous
        call to xbee_device_schedule_after.

        Calling this function on a non-existent event will cause an
        exception to be raised.

        '''
        self.__sched.cancel(event_handle)

    def xbee_device_xmit(self, src_ep, buf, addr):
        '''
        Transmit buf to addr using endpoint number src_ep.  Returns None.

        If the transmit can not complete immediately, the transmit
        will be scheduled.

        '''

        if src_ep not in self.__xbee_endpoints:
            raise XBeeDeviceManagerEndpointNotFound(
                "error during xmit, source endpoint 0x%02x not found." % \
                    (src_ep))

        sd = self.__xbee_endpoints[src_ep].sd
        try:
            num_bytes = sd.sendto(buf, 0, addr)
            self._tracer.xbee('xmit wrote %d bytes' % num_bytes)
            return
        except socket.error, e:
            if e[0] == errno.EWOULDBLOCK:
                pass
            raise e

        # Buffer transmission:
        self.__xbee_endpoints[src_ep].xmit_q.append((buf, addr))
        # Indicate to I/O handling thread we have a new event:
        self.__unblock_inner_select()

    def xbee_get_node_list(self, refresh=False, clear=False):
        '''
        Returns the XBeeDeviceManager's internal copy of the network
        node list.

        If refresh is True, a network discovery will be performed.

        If clear is True, the node list will be cleared before
        a discovery is performed (only if refresh is True).  Be careful
        with the clear command.  Executing this function may disrupt internal
        network management logic.

        '''
        if clear:
            self.__xbee_node_list = []
        new_node_candidates = xbee.get_node_list(refresh=refresh)
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

    def _xbee_remove_node_from_list(self, addr_extended):
        '''
        Removes a node from the internal copy of the XBee network
        node list.

        This function is called when the XBeeDeviceManager has
        reason to believe that a node no longer exists on a given
        network.  Do not execute this function unless you know what you
        are doing.

        '''
        target_nodes = filter(lambda n: addresses_equal(
                                n.addr_extended, addr_extended),
                            self.__xbee_node_list)

        if not len(target_nodes):
            raise ValueError(
                "XBeeDeviceManager: cannot remove node, '%s' not found" % (
                    addr_extended))

        for node in target_nodes:
            self.__xbee_node_list.remove(node)

    ## XBeeDeviceManagerConfigurator interface and callbacks:
    def _get_behavior_flags(self):
        '''
        Returns the current set of XBee behavior flags.

        The behaviors defined by these flags are internal to the
        XBeeDeviceManager and are not intended for general usage.
        '''
        return self.__behavior_flags

    def _state_lock(self):
        '''Lock internal state, used by configator helper class.'''
        self.__lock.acquire()

    def _state_unlock(self):
        '''Unlock internal state, used by configator helper class.'''
        self.__lock.release()

    def _xbee_device_configuration_heuristic(self, xbee_state):
        '''
        Internal method to determine if an XBee node is ready for
        configuration.

        '''
        # If we aren't ready, defer:
        if self.__state != STATE_READY:
            # print "XDMH: Not ready, deferring configuration for %s" %
            # xbee_state.ext_addr_get()
            self._xbee_device_configuration_defer(xbee_state)
            return

        configuration_attempts = xbee_state.config_attempts_get()
        xbee_state.config_attempts_set(configuration_attempts + 1)
        current_time = digitime.time()

        if not xbee_state.xbee_sleep_period_sec():
            # If a device is not configured to sleep, attempt to configure
            # the node immediately.
            #print "XDMH: No sleep configuration, configuring
            #immediately %s" % xbee_state.ext_addr_get()
            self.__xbee_configurator.configure(xbee_state)
            return

        # Checks to see if we should defer configuration:
        if xbee_state.config_attempts_get() <= 1:
            # We haven't waited long enough for the node to report in, scan
            # the config block list for sleep blocks, prepare the network
            # as needed:
            for sleep_block in [x for x in xbee_state.config_block_list() \
                                if isinstance(x, XBeeConfigBlockSleep)]:
                preparation_successful = False
                try:
                    preparation_successful = \
                        sleep_block.prepare_network(self._sn_sp_override)
                except DDOTimeoutException, e:
                    self._tracer.warning("Timeout while preparing " +
                                          "for sleep: %s. Will try again " +
                                          "later...", str(e))
                except Exception, e:
                    self._tracer.error('Exception while preparing' +
                                        ' network for sleep support: %s',
                                        str(e))
                    self._tracer.debug(traceback.format_exc())

                if not preparation_successful:
                    # Ensure that we will try to prepare the network again:
                    xbee_state.config_attempts_set(0)

#             print "XDMH: Deferring configuration after net prep
#             attempt for %s" % (
#                         xbee_state.ext_addr_get())
            self._xbee_device_configuration_defer(xbee_state, multiple=2)
            return

        # We may elect to configure this node now.  However, we must
        # must check to see if this node's configuration attempt could
        # possibly interrupt any node configuration we've heard from in
        # the past, including the candidate node itself:

        # Build a list of all nodes which are scheduled to be configured
        # and which we have heard from in the past:
        tbc_l = filter(lambda xbs: xbs.is_config_scheduled() and
                             xbs.last_heard_from_get() is not None,
                           self.__xbee_device_states.values())
        # Map this list to the amount of seconds remaining before we
        # expect to hear from these nodes again:
        tbc_l = map(lambda xbs: xbs.xbee_sleep_period_sec() -
                                  (current_time -
                                     xbs.last_heard_from_get()),
                    tbc_l)

        # Filter out any negative values or any values outside of the
        # current DDO remote-command timeout period:
        ddo_worst_cast_t = GLOBAL_DDO_TIMEOUT * GLOBAL_DDO_RETRY_ATTEMPTS + 1
        tbc_l = filter(lambda t: t >= 0 and t <= ddo_worst_cast_t, tbc_l)

        # If there are values in the list, we should elect to defer
        # configuration for this node now:
        if len(tbc_l):
#             print "XDMH: Deferring configuration for %s, expecting
#             other nodes soon" % (
#                         xbee_state.ext_addr_get())
#             print "XDMH: Expected nodes:"
#             print tbc_l
#             print "XDMH: End expected nodes"
            self._xbee_device_configuration_defer(xbee_state)
            return

#         print "XDMH: Continuing configuration attempt for %s" %
#         xbee_state.ext_addr_get()
        # There is no other recourse than to try and to reach out to the
        # node now:
        self.__xbee_configurator.configure(xbee_state)

    def _xbee_device_configuration_defer(self, xbee_state, multiple=1):
        self.__lock.acquire()
        try:
            # Set state to configuration scheduled and reschedule:
            try:
                prev_sched_handle = xbee_state.configuration_sched_handle_get()
                try:
                    if prev_sched_handle:
                        self.xbee_device_schedule_cancel(prev_sched_handle)
                except:
                    pass

                xbee_state.goto_config_scheduled()
                wait_time = max(xbee_state.xbee_sleep_period_sec() * multiple,
                                self.MINIMUM_RESCHEDULE_TIME)
                xbee_state.configuration_sched_handle_set(
                    self.xbee_device_schedule_after(
                        wait_time,
                        self._xbee_device_configuration_heuristic,
                        xbee_state))
            except Exception, e:
                self._tracer.error("Configuration defer " +
                                    "unexpected failure: %s", str(e))

        finally:
            self.__lock.release()

    def _xbee_device_configuration_done(self, xbee_state):
        '''
        This method is called by the XBee Device Manager's Configurator
        once a configuration attempt has been completed.

        '''

        if not xbee_state.is_config_active():
            self._tracer.debug("XBee device state %d for node %s " +
                                "is invalid post configuration.",
                                xbee_state.get_state(),
                                xbee_state.ext_addr_get())
            return

        # Advance the state of this XBee if all of the configuration
        # blocks have been applied successfully:
#        print "_xbee_device_configuration_done(): check ready"
        xbee_ready = reduce(lambda rdy, blk: rdy and blk.is_complete(),
                                xbee_state.config_block_list(), True)

        if not xbee_ready:
            # Device is not ready and still needs to be initialized:
            self._xbee_device_configuration_defer(xbee_state)
            return

        ext_addr = xbee_state.ext_addr_get()
        self._tracer.info("Configuration done for node '%s'" \
                           " promoting to RUNNING state.", ext_addr)
        self.__lock.acquire()
        try:
            xbee_state.goto_running()
        finally:
            self.__lock.release()

        # Add this node to the skip_config_addr_list
        if self.get_setting("update_skiplist"):
            try:
                skiplist = self.get_setting("skip_config_addr_list")
                skiplist.append(ext_addr)

                self.set_pending_setting("skip_config_addr_list", skiplist)
                self.apply_settings()
                self._core.save_settings()
            except Exception, e:
                self._tracer.error("Failed to update " +
                                    "configuration file: %s", str(e))

    def _xbee_device_ddo_param_cache_get(self, dest, param):
        '''Fetch a cached DDO value for a given destination.'''
        return self.__xbee_ddo_param_cache.cache_get(dest, param)

    def _xbee_device_ddo_param_cache_set(self, dest, param, value):
        '''
        Cache a DDO parameter value in all matching state objects.

        Setting value to None invalidates the parameter.

        '''
        return self.__xbee_ddo_param_cache.cache_set(dest, param, value)

    def _critical_die(self, e):
        '''
        Trace and handle critical exceptions that need a shutdown.

        The argument 'e' is the exception.
        '''
        self._tracer.critical('Caught a fatal exception: %s' \
                               '\n\trequesting DIA shutdown...', str(e))
        self._tracer.debug(traceback.format_exc())
        self._core.request_shutdown()

    def __verify_dh_dl_force(self, new_type):
        '''
        Verify the DH/DL force setting values
        '''
        try:
            self.__parse_dh_dl_force(new_type, test_only=True)
            return
        except:
            pass


    def __parse_dh_dl_force(self, dh_dl_force, test_only=False):
        '''
        Normalize the DH/DL force settings
        '''
        # self._tracer.debug('__parse_dh_dl_force(%s)', dh_dl_force)

        if isinstance(dh_dl_force, types.StringType):
            dh_dl_force = dh_dl_force.lower()

        if dh_dl_force == 'coordinator':
            # set DH/DL to match the coordinator MAC
            if test_only:
                return True
            self._dh_dl_addr = gw_extended_address_tuple()

        elif dh_dl_force in ('true', True, 'on'):
            if test_only:
                return True
            self._dh_dl_addr = self.get_default_dh_dl_address()

        elif dh_dl_force in ('false', False, 'off', None, 'none'):
            # disable DH/DL changes of any kind
            if test_only:
                return True
            self._dh_dl_addr = None

        else: # then must be a specific address
            if test_only:
                return validate_address(dh_dl_force)

            try:
                self._dh_dl_addr = address_to_tuple(dh_dl_force)
            except:
                traceback.print_exc()
                raise ValueError('bad logic in dh_dl_force parsing')

        return dh_dl_force

    def __verify_dh_dl_min(self, new_type):
        '''
        Verify 'dh_dl_refresh_min' setting values
        '''
        try:
            self.__parse_dh_dl_min(new_type, test_only=True)
            return
        except:
            pass


    def __parse_dh_dl_min(self, value, test_only=False):
        '''
        Normalize a dh_dl_refresh_min setting
        '''
        # self._tracer.debug('__parse_dh_dl_min(%s)', value)

        if value is not None:
            if isinstance(value, types.StringType):
                value = value.lower()

            if value == self.DH_DL_REFRESH_ONCE:
                # we have a one_time broadcast plus config
                if test_only:
                    return True
                self._tracer.debug('node DH/DL forced by config, 1 broadcast')
                self.xbee_device_schedule_after(DH_DL_REFRESH_INITIAL_WAIT,
                                                self._broadcast_address)

            elif value == self.DH_DL_REFRESH_CONFIG:
                # we have a one_time broadcast plus config
                if test_only:
                    return True
                self._tracer.debug('node DH/DL forced by config, no broadcast')

            elif value == 'none':
                # we do none of these
                if test_only:
                    return True
                self._tracer.debug('node DH/DL forced set to None')
                return None

            else:
                # we have a repeating broadcast
                value = parse_time_duration(value, in_type='min', \
                                                    out_type='sec')

                if value is not None:
                    # then was a valid time
                    if value > 0 and value < self.DH_DL_REFRESH_MININUM:
                        raise ValueError("DH/DL Broadcast time is too short")

                    if test_only:
                        # TODO - add a reasonable min/max range
                        return value is not None

                if value == 0:
                    self._tracer.debug(
                        'DH/DL repeat broadcast disabled by 0 time')
                else:
                    self._tracer.debug(
                        'DH/DL forced by repeat broadcast every %d seconds', value)
                    self.xbee_device_schedule_after(DH_DL_REFRESH_INITIAL_WAIT,
                                                   self._schedule_broadcast)

        return value
