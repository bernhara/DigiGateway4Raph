############################################################################
#                                                                          #
# Copyright (c)2012, Digi International (Digi). All Rights Reserved.       #
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
Debug DigiMesh Device Manager

This module provides the DebugDigiMeshDeviceManager, which adds two
additional settings and an additional channel to the standard
DigiMeshDeviceManager.

It allows switching  between two sleep/wake cycle configurations via
a channel toggle (called 'debug_mode').
'''

import threading

from common.types.boolean import Boolean
from channels.channel_source_device_property import DPROP_PERM_GET, \
     DPROP_OPT_AUTOTIMESTAMP, ChannelSourceDeviceProperty, Sample, \
     DPROP_PERM_SET

from xbee_device_manager import Setting, SettingsBase

from digimesh_device_manager import DigiMeshDeviceManager


class DebugDigiMeshDeviceManager(DigiMeshDeviceManager):
    '''
    This class implements the Debug DigiMesh Device Manager.

    Settings:

    * **debug_sleep_time:** Time in ms for each sleep cycle in debug mode.
    * **debug_wake_time:** Time in ms for each wake cycle in debug mode.

    Channels:

    * **debug_mode:** Set to true to use debug sleep and wake times.
    '''
    def __init__(self, name, core_services):
        settings_list = [
            Setting(
                name='debug_sleep_time', type=int, required=False,
                default_value=50,
                verify_function=lambda x: 10 <= x <= 14400000),
            Setting(
                name='debug_wake_time', type=int, required=False,
                default_value=20000,
                verify_function=lambda x: 69 <= x <= 3600000), ]

        property_list = [
            ChannelSourceDeviceProperty(
                name='debug_mode', type=Boolean,
                initial=Sample(timestamp=0, value=Boolean(False),
                               unit='bool'),
                perms_mask=DPROP_PERM_GET | DPROP_PERM_SET,
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.__handle_debug), ]

        # network debug mode flag
        self.__debug = False
        self.__debug_lock = threading.RLock()

        DigiMeshDeviceManager.__init__(self, name, core_services,
                                       settings_list, property_list)

    def get_debug_mode(self):
        '''
        Return True if debug mode is currently enabled.
        '''
        try:
            self.__debug_lock.acquire()
            return self.__debug

        finally:
            self.__debug_lock.release()

    def __handle_debug(self, value):
        '''
        handle a call from the channel
        '''
        value = Boolean(value.value)
        self.property_set('debug_mode', Sample(0,
                                               value=value,
                                               unit='bool'))
        self.set_debug_mode(value)

    def set_debug_mode(self, enabled):
        '''
        enabled=True sets debug mode
        enabled=False disables debug mode

        True is returned if the debug mode changed, False is returned
        if it remained the same.
        '''
        try:
            self.__debug_lock.acquire()
            if self.__debug == enabled:
                return False

            if enabled:
                sleep_ms = SettingsBase.get_setting(self, 'debug_sleep_time')
                wake_ms = SettingsBase.get_setting(self, 'debug_wake_time')
            else:
                sleep_ms = SettingsBase.get_setting(self, 'sleep_time')
                wake_ms = SettingsBase.get_setting(self, 'wake_time')

            self._set_sleep_wake(sleep_ms, wake_ms)
            self.__debug = enabled
            return True

        finally:
            self.__debug_lock.release()
