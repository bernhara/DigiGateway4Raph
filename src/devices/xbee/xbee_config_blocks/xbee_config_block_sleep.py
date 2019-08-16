############################################################################
#                                                                          #
# Copyright (c)2008, 2009, Digi International (Digi). All Rights Reserved. #
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
The XBee Sleep Configuration Block module, definitions for XBee configuration
blocks with deal with sleeping node configurations.
"""

# imports
from copy import copy
import struct

from common.rho import rho
from common.helpers.format_strings import format_hexrepr
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo import \
    AbstractXBeeConfigBlockDDO
from devices.xbee.common.prodid import MOD_XB_ZNET25, MOD_XB_ZB, \
                                        MOD_XB_S2C_ZB, \
                                        MOD_XB_DIGIMESH900, \
                                        MOD_XB_DIGIMESH24, \
                                        MOD_XB_S3C_DIGIMESH900, \
                                        FW_FUNCSET_XB_ZB_COORD_AT, \
                                        FW_FUNCSET_XB_ZB_COORD_API, \
                                        FW_FUNCSET_XB_ZB_ROUTER_AT, \
                                        FW_FUNCSET_XB_ZB_ROUTER_API, \
                                        parse_dd, parse_vr
from devices.xbee.common.ddo import \
    GLOBAL_DDO_RETRY_ATTEMPTS as DDO_RETRY_ATTEMPTS

SLEEPABLE_MODULES = (MOD_XB_DIGIMESH900, \
                     MOD_XB_DIGIMESH24, \
                     MOD_XB_S3C_DIGIMESH900, \
                     MOD_XB_ZNET25, MOD_XB_ZB, MOD_XB_S2C_ZB)
# Sleep modes
SM_DISABLED = 0
SM_PIN_HIBERNATE = 1
SM_CYCLIC_SLEEP = 4
SM_CYCLIC_SLEEP_PIN_WAKE = 5
DM_SUPPORT = 0x7
DM_SLEEP = 0x8

SLEEP_MODES = (SM_DISABLED, SM_PIN_HIBERNATE, SM_CYCLIC_SLEEP,
               SM_CYCLIC_SLEEP_PIN_WAKE, DM_SUPPORT, DM_SLEEP)

# Impose a minimum SP time for routers on networks:
# 0x1f4 or 500 x 10ms = 5000ms (5s).
MINIMUM_ZB_RTR_SP_VALUE = 0x1f4

CYCLIC_SLEEP_MIN_MS = (0x20 * 10)
CYCLIC_SLEEP_MAX_MS = (0xaf0 * 10)
CYCLIC_SLEEP_PERIODS_MAX = 0xffff
CYCLIC_SLEEP_EXT_MAX_MS = (CYCLIC_SLEEP_PERIODS_MAX * CYCLIC_SLEEP_MAX_MS)

TIME_AWAKE_MIN_MS = 1
TIME_AWAKE_MAX_MS = 0xfffe

# These funcsets are not supported for sleep modes if FW version is
# less than 2x60:
UNSUPPORTED_ZB_FW_FUNCSETS = (
                                FW_FUNCSET_XB_ZB_COORD_AT,
                                FW_FUNCSET_XB_ZB_COORD_API,
                                FW_FUNCSET_XB_ZB_ROUTER_AT,
                                FW_FUNCSET_XB_ZB_ROUTER_API,
                             )
UNSUPPORTED_ZB_LT_FW_VERSION = 0x60

# exception classes

# interface functions


def generate_sn_sp(stime, name='time_asleep_ms'):
    '''
    Return a dictionary with 'SN' and 'SP' as keys and corresponding
    values as acceptable settings based on rho configuration.

    stime is requested sleep time in milliseconds

    name is only used in reporting the ValueError on failure
    '''
    result = None
    time_val = stime // 10
    criteria = lambda p, q: (
                   (p >= (CYCLIC_SLEEP_MIN_MS // 10) and
                        p <= (CYCLIC_SLEEP_MAX_MS // 10)) and
                    q <= CYCLIC_SLEEP_PERIODS_MAX)
    for nudge in range(0, -3, -1):
        time_val += nudge
        result = rho(time_val, test=criteria)
        # rho function can return long type, so we map to int:
        result = [int(n) for n in result]
        if len(result) == 2:
            break
    if len(result) != 2:
        raise ValueError(
            "%s cannot be factored cleanly," \
            " please choose another value." % name)

    # Use the calculated parameters:
    period, n_periods = result
    if not criteria(period, n_periods):
        period, n_periods = result[::-1]

    return {'SP': period, 'SN': n_periods}


# classes
class XBeeConfigBlockSleep(AbstractXBeeConfigBlockDDO):
    """
    XBee DDO Configuration Block

    Implements an
    :py:class:`~devices.xbee.xbee_config_blocks.xbee_config_block_ddo.AbstractXBeeConfigBlockDDO`
    for proper sequencing by the
    :py:class:`~devices.xbee.xbee_device_manager.xbee_device_manager.XBeeDeviceManager`.

    This class automatically configures the sleep cycle DDO parameters
    for XBee nodes via the :py:meth:`sleep_cycle_set` method.
    """
    def __init__(self, ext_addr):
        self.__parameters = {}
        self.__pending_parameters = {}
        self.__sleep_mode = SM_DISABLED
        self.__sleep_period_ms = 0

        from core.tracing import get_tracer
        self.__tracer = get_tracer('XBeeConfigBlockSleep')

        AbstractXBeeConfigBlockDDO.__init__(self, ext_addr)
        AbstractXBeeConfigBlockDDO.apply_only_to_modules(self,
            SLEEPABLE_MODULES)

    def _add_parameter(self, mnemonic, value):
        # zb_dev_manager needs to access
        if not isinstance(mnemonic, str) and len(mnemonic) == 2:
            raise AttributeError('mnemonic must be a string of length 2')
        self.__parameters[mnemonic] = value
        self.__pending_parameters[mnemonic] = value

    def __is_sleep_mode_available(self, ext_addr=False):
        '''
        If ext_addr is False, uses the device referred to in this
        config block.
        '''
        # Special case: if this is a ZB network we need to check if the
        # firmware version is less than 0x2x60.  If it is less than this,
        # then sleep mode is not supported on router modules (0x2260):
        if ext_addr == False:
            ext_addr = AbstractXBeeConfigBlockDDO.ext_addr_get(self)

        module_id, _ = parse_dd(AbstractXBeeConfigBlockDDO.\
                                configurator_get(self)\
                                .ddo_get_param(ext_addr, 'DD',
                                               retries=DDO_RETRY_ATTEMPTS,
                                               use_cache=True))
        if module_id not in SLEEPABLE_MODULES:
            return False

        if module_id == MOD_XB_ZB or module_id == MOD_XB_S2C_ZB:
            fw_func, fw_v = parse_vr(AbstractXBeeConfigBlockDDO.\
                                     configurator_get(self).\
                                     ddo_get_param(ext_addr, 'VR',
                                                   retries=\
                                                   DDO_RETRY_ATTEMPTS,
                                                   use_cache=True))

            if (fw_func in UNSUPPORTED_ZB_FW_FUNCSETS and
                fw_v < UNSUPPORTED_ZB_LT_FW_VERSION):
                self.__tracer.warning("'%s' FW version is %s < %s, "
                                "sleep mode configuration unavailable.",
                                ext_addr, hex(fw_v),
                                hex(UNSUPPORTED_ZB_LT_FW_VERSION))
                return False
        return True

    def reset(self):
        '''
        Reset the state of this configuration block object.

        See :py:class:`~devices.xbee.xbee_config_blocks.xbee_config_block.\
        XBeeConfigBlock`.
        '''
        self.__pending_parameters = copy(self.__parameters)
        # Complete the state reset:
        AbstractXBeeConfigBlockDDO.reset(self)

    def __prepare_network_update_param(self, ext_addr, param,
                                       override_map):
        '''
        Internal helper function used to update node parameters.

        Returns True if this node needs to be updated, otherwise False.
        '''

        minimum_sp_value = MINIMUM_ZB_RTR_SP_VALUE

        self.__tracer.debug("Fetching '%s' from '%s'", param, ext_addr)
        try:
            network_param = (
                AbstractXBeeConfigBlockDDO.configurator_get(self)
                    .ddo_get_param(ext_addr, param,
                                   retries=DDO_RETRY_ATTEMPTS,
                                   use_cache=True))
            # All params used here are 16-bit unsigned ints:
            network_param = struct.unpack('>H', network_param)[0]
        except Exception, e:
            self.__tracer.warning("Could not fetch param " \
                    "'%s' from '%s': %s", param, ext_addr, str(e))
            self.__tracer.debug("Removing '%s' from cache", ext_addr)
            (AbstractXBeeConfigBlockDDO
             .xbee_device_manager_get(self)
             ._xbee_remove_node_from_list(ext_addr))
            raise e

        # Do we have an SP/SN override?
        if override_map:
            pending_values = override_map
        else:
            pending_values = self.__pending_parameters

        value = None
        if (network_param < pending_values[param]):
            # Special-case SP to enforce minimum value:
            if param == 'SP':
                value = max(minimum_sp_value, pending_values[param])
            else:
                value = pending_values[param]

        if value is None:
            # signal nothing more to do
            return False

        self.__tracer.debug("Updating sleep param of node '%s', '%s' = %s",
                            ext_addr, param, format_hexrepr(value))
        try:
            (AbstractXBeeConfigBlockDDO.configurator_get(self)
                .ddo_set_param(ext_addr, param, value, apply=True))
        except Exception, e:
            self.__tracer.warning("Couldn't write param '%s' to '%s': %s",
                                  param, ext_addr, str(e))
            raise e
        return True

    def prepare_network(self, override_map=None):
        '''
        Setup the network to handle this node.

        It is important that all routers and the coordinator be
        prepared to reach a node with sleeping parameters.  Without
        preparing the network first, reaching the node to configure it
        (if it has been preconfigured, for instance) may leave the node
        unreachable!

        This method will be called as a special case from the
        XBeeDeviceManager at the appropriate time.

        Return type:
            * bool
        '''
        if self.__sleep_mode == SM_DISABLED:
            return

        # Test local node for sleep fitness:
        if not self.__is_sleep_mode_available(None):
            return False

        if self.__sleep_mode == DM_SUPPORT:
            # ensure this device is not a preferred sleep coord
            # bit 1: non-sleep coordinator
            # bit 2: enable api sleep status messages
            self._add_parameter('SO', 0x06)
            return True

        if self.__sleep_mode == DM_SLEEP:
            # ensure not a sleep coordinator
            self._add_parameter('SO', 0x0)
            return True

        # If we are setting up a node for cyclic sleep, we must set
        # appropriate values for SP and SN (if the values are not already
        # large enough) network wide so the network may buffer requests
        # long enough for our sleeping nodes:
        router_list = (AbstractXBeeConfigBlockDDO.\
                       xbee_device_manager_get(self)\
                        .xbee_get_node_list(refresh=False))
        router_list = [n.addr_extended for n in router_list if \
                       n.type == 'router' or n.type == 'coordinator']
        write_list = []


        module_id, _ = parse_dd(AbstractXBeeConfigBlockDDO.\
                                configurator_get(self)\
                                .ddo_get_param(None, 'DD',
                                               retries=DDO_RETRY_ATTEMPTS,
                                               use_cache=True))

        applicable_params = None
        if module_id == MOD_XB_ZNET25:
            # Only SP is valid network wide:
            applicable_params = ('SP', )
        elif module_id == MOD_XB_ZB or module_id == MOD_XB_S2C_ZB:
            applicable_params = ('SP', 'SN')
        for param in applicable_params:
            if param in self.__pending_parameters:
                for network_node in router_list:
                    try:
                        if not self.__prepare_network_update_param(
                                  network_node, param, override_map):
                            # no update necessary, continue
                            continue
                    except Exception, e:
                        self.__tracer.warning('Could not prepare network for '
                                              'sleeping node %s... will '
                                              'try again later.' %
                                              self._ext_addr)
                        return False
                    write_list.append(network_node)

        for network_node in write_list:
            # Attempt to write parameter values to non-volatile memory
            # for the coordinator and router nodes so that parameter
            # modifications persist through subsequent resets.
            try:
                (AbstractXBeeConfigBlockDDO.configurator_get(self)
                 .ddo_set_param(network_node, 'WR', ''))
            except Exception, e:
                self.__tracer.warning('couldn\'t write config '
                                      'to \'%s\': %s', network_node, str(e))
                # Ignore this failure, it is non-fatal to network
                # performance
                continue
        # Signal to XBeeDeviceManager that network preparation was successful
        return True

    def apply_config(self):
        '''
        Apply the configuration actions to the node targeted by this object.

        After this method has been called the
        :py:meth:`~devices.xbee.xbee_config_blocks.xbee_config_block.XBeeConfigBlock.is_complete`
        method will return True.

        See :py:class:`~devices.xbee.xbee_config_blocks.xbee_config_block.XBeeConfigBlock`.
        '''
        try:
            if not AbstractXBeeConfigBlockDDO._is_applicable(self):
                # If the block is not applicable, mark this block as complete:
                return AbstractXBeeConfigBlockDDO.apply_config(self)

        except:
            # Trace messages handled by _is_applicable() and apply_config()
            return False

        # Special case:
        #
        # Check if sleep mode is unavailable on this module/firmware
        # combination:
        if not self.__is_sleep_mode_available():
            if self.__sleep_mode == SM_DISABLED:
                # This sleep block has been filled out with sleeping
                # disabled however sleep configuration is not available:
                # mark this block as complete.
                self.__tracer.debug('sleep mode unsupported and SM_DISABLED'
                                    ' given, block complete.')
                return AbstractXBeeConfigBlockDDO.apply_config(self)
            else:
                # We are unable to apply this block, mark it as a
                # block application failure:
                self.__tracer.warning('sleep mode unsupported'
                                      ' but sleep parameters given,'
                                      ' block FAILED. Please disable '
                                      'sleeping on this device.')
                return False

        # Configure the node:
        pending_mnemonics = self.__pending_parameters.keys()

        for mnemonic in pending_mnemonics:
            # NOTE: this message is duplicated in the XBeeConfigBlockDDO source
            self.__tracer.debug("Apply_config: trying '%s' = '%s' to '%s'",
                             mnemonic,
                             format_hexrepr(
                                 self.__pending_parameters[mnemonic]),
                             AbstractXBeeConfigBlockDDO.ext_addr_get(self))
            try:
                AbstractXBeeConfigBlockDDO.configurator_get(self).\
                    ddo_set_param(
                        AbstractXBeeConfigBlockDDO.ext_addr_get(self),
                        mnemonic,
                        self.__pending_parameters[mnemonic],
                        retries=DDO_RETRY_ATTEMPTS)
            except Exception, e:
                self.__tracer.error("'%s' = '%s' to '%s' failed (%s)",
                                mnemonic,
                                format_hexrepr(
                                    self.__pending_parameters[mnemonic]),
                                AbstractXBeeConfigBlockDDO.ext_addr_get(self),
                                str(e))
                return False
            del(self.__pending_parameters[mnemonic])

        # NOTE: We do NOT apply changes here.  All config block
        # changes will be applied when the final 'WR' is performed
        # This is called when all the settings have been successfully
        # applied.
        return AbstractXBeeConfigBlockDDO.apply_config(self)


    def sleep_mode_set(self, sleep_mode):
        """
        Set the sleep mode for the adapter.

        This clears all existing configuration parameters on this config block
        and resets its state.

        Valid sleep modes are:

        * :py:const:`SM_DISABLED`: sleep mode disabled.
        * :py:const:`SM_PIN_HIBERNATE`: pin hibernation mode
        * :py:const:`SM_CYCLIC_SLEEP`: cyclic sleep mode
        * :py:const:`SM_CYCLIC_SLEEP_PIN_WAKE`: cycle sleep mode with pin-wake

        Parameters:
            * **sleep_mode**: a valid integer constant sleep mode

        Return type:
            * None

        """
        self.__parameters = {}
        self.reset()

        if sleep_mode not in SLEEP_MODES:
            raise ValueError('invalid sleep mode specified')

        self.__sleep_mode = sleep_mode
        if sleep_mode == SM_DISABLED:
            self.__sleep_period_ms = 0
        self._add_parameter('SM', sleep_mode)

    def sleep_mode_get(self):
        '''
        Returns the currently configured sleep mode.

        Return type:
            * integer constant sleep mode value
              (see: :py:meth:`sleep_mode_set`)
        '''
        return self.__sleep_mode

    def sleep_enabled(self):
        '''
        Indicates if sleep is enabled on this block.

        Return type:
            * bool
        '''
        return (self.__sleep_mode != SM_DISABLED and \
                self.__sleep_mode != DM_SUPPORT)

    def sleep_period_ms_get(self):
        '''
        Returns the configured sleep period in milliseconds.

        Return type:
            * integer
        '''
        return self.__sleep_period_ms

    def sleep_cycle_set(self, time_awake_ms, time_asleep_ms,
                            enable_pin_wake=False, predelay=None):
        '''
        Set the sleep cycle for this adapter.  This clears all existing
        configuration parameters on this config block and resets its
        state.

        If the `enable_pin_wake` parameter is set to True, the pin sleep
        control line (module pin 9) will be monitored on the module to
        also control its sleep cycle.

        If `time_asleep_ms` is so large that it requires the "extended"
        sleep mode of the device, sleep options on the device will be
        used to ensure that the device is awake for the entire
        `time_awake_ms` duration.

        When extended sleep is used a longer (~1 second) `time_awake_ms`
        is recommended in order to give the gateway system adequate time
        to address the unit and reconfigure it if necessary.

        Parameters:
            * **time_awake_ms**: integer in milliseconds
            * **time_asleep_ms**: integer in milliseconds
            * **enable_pin_wake**: bool

        Return type:
            * None
        '''
        if enable_pin_wake:
            self.sleep_mode_set(SM_CYCLIC_SLEEP_PIN_WAKE)
        else:
            self.sleep_mode_set(SM_CYCLIC_SLEEP)

        if (time_awake_ms < TIME_AWAKE_MIN_MS or
                time_awake_ms > TIME_AWAKE_MAX_MS):
            raise ValueError('time_awake must be 1 <= x <= 65534 ms')

        if time_asleep_ms < CYCLIC_SLEEP_MIN_MS:
            raise ValueError('time_asleep_ms too small, must be >= %d' \
                                    % (CYCLIC_SLEEP_MIN_MS))

        if time_asleep_ms > CYCLIC_SLEEP_EXT_MAX_MS:
            raise ValueError('time_asleep_ms too large, must be <= %d' \
                                    % (CYCLIC_SLEEP_EXT_MAX_MS))

        # Store configuration:
        self.__sleep_period_ms = time_asleep_ms

        # Set time awake:
        self._add_parameter('ST', time_awake_ms)

        if time_asleep_ms <= CYCLIC_SLEEP_MAX_MS:
            ## Simple sleep mode:
            # Set sleep options (no always wake, no extended sleep):
            self._add_parameter('SO', 0)

            # Set sleep period objects:
            self._add_parameter('SN', 1)
            self._add_parameter('SP', (time_asleep_ms / 10))

        else:
            ## Extended sleep mode:
            # Set sleep options (always wake, extended sleep):
            self._add_parameter('SO', (0x02 | 0x04))

            vals = generate_sn_sp(time_asleep_ms)
            self.__parameters.update(vals)
            self.__pending_parameters.update(vals)

            if predelay != None:
                self._add_parameter('WH', predelay)


class XBeeConfigNetworkSleep(XBeeConfigBlockSleep):
    """
        Use this class to emulate a sleep block, but you don't actually want
        the sleep parameters to be sent to the device.

        In these cases, the device does NOT want the XBee Device Manager
        to send the 'SP' and 'SN' parameters, yet the XBee Device Manager
        needs some hints on how long the device intends its sleep to be,
        so that it can tell the coordinator and all the routers about how
        long the device will appear to be gone off the network.

        This class very useful for certain devices that do not directly
        use the 'SP' and 'SN' parameters to set their sleep modes.
        The device might have its own protocol that defines and sets the
        sleep modes on the radio by itself, or the device might be set to
        'pin hiberate', where it might not use these parameters.

    """

    def __init__(self, ext_addr):
        XBeeConfigBlockSleep.__init__(self, ext_addr)

    def sleep_hint(self, time_asleep_ms):
        ''' Convenience function for sleep_cycle_set. '''
        XBeeConfigBlockSleep.sleep_cycle_set(self, 1, time_asleep_ms)

    def apply_config(self):
        """
        Apply the configuration actions to the node targeted by this object.

        After this method has been called the
        :py:meth:`~devices.xbee.xbee_config_blocks.xbee_config_block.XBeeConfigBlock.is_complete`
        method will return True.

        See :py:class:`~devices.xbee.xbee_config_blocks.xbee_config_block.XBeeConfigBlock`.
        """
        # This is called when all the settings have been successfully applied:
        return AbstractXBeeConfigBlockDDO.apply_config(self)


# internal functions & classes
