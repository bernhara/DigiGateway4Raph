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


# imports
import digihw
import traceback

from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_local_io.xbee_local_io import XBeeLocalIO
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.digi_device_info import get_platform_name
from common.types.boolean import Boolean, STYLE_ONOFF

# constants


# exception classes

# interface functions

# classes
class LocalIO(DeviceBase):
    """
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.

    """

    LOCAL_AIO_MODE_CURRENTLOOP = "CurrentLoop"
    LOCAL_AIO_MODE_TENV = "TenV"
    IO_MAX_CHANNELS = 10
    IO_TYPE_NONE = 0
    IO_TYPE_ANALOG = 1
    IO_TYPE_DIGITAL = 2

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        ## Local State Variables:
        self.__xbee_aio_driver = None
        self.__xbee_dio_driver = None

        self.__analog_channels = []
        self.__digital_channels = []

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Settings Table Definition:

        settings_list = [
            Setting(name = 'power', type = Boolean, required = False,
                    default_value = Boolean("On", STYLE_ONOFF),
                    verify_function = self.__verify_power_setting),
            Setting(name = 'sample_rate_ms', type = int, required = False,
                   default_value = 60000,
                   verify_function = lambda x: x >= 100 and x <= 6000000),
            Setting(name = 'calibration_rate_ms', type = int, required = False,
                   default_value = 900000,
                   verify_function = lambda x: x >= 0),
        ]

        ## Channel Properties Definition:
        property_list = []

        # Dynamically create the rest of our settings based on what the device supports.
        for ch in range(0, self.IO_MAX_CHANNELS):

            # Attempt to get the channel type.
            # If we try to go beyond the amount of supported channels,
            # we will get a ValueError exception.  If we do, stop our loop.
            try:
                type = digihw.get_channel_type(ch)
                
            except ValueError:
                # we'll hit this once we go past valid count since we support 10
                # channels, but likely device like X4H only has 4
                # traceback.print_exc()
                break
                
            except:
                traceback.print_exc()

            if type == self.IO_TYPE_ANALOG:
                self.__tracer.info("Detected IO channel %d is Analog", 
                                        ch + 1)
                self.__analog_channels.append(ch)

                settings_list.append(Setting(
                    name = 'channel%d_mode' % (ch + 1), 
                    type=str, required=False,
                    verify_function = _verify_aio_channel_mode,
                    default_value = self.LOCAL_AIO_MODE_TENV))

            elif type == self.IO_TYPE_DIGITAL:
                self.__tracer.info("Detected IO channel %d is Digital", 
                                        ch + 1)
                self.__digital_channels.append(ch)

                settings_list.append(Setting(
                    name = 'channel%d_dir' % (ch + 1), type = str,
                    required=False,
                    default_value='in'))
                settings_list.append(Setting(
                    name = 'channel%d_source' % (ch + 1), type = str,
                    required = False,
                    default_value=''))
                    
            else:
                raise "Unknown IO hardware type channel %d, is %d" % \
                            ((ch + 1), type)

        # Finally, on some platforms, the AIO and DIO support is done by
        # the XBee radio inside the unit.
        #
        # If this is the case, we will need to also have the
        # 'xbee_device_manager' setting provided to us as well.
        if get_platform_name() == 'digix3':
            settings_list.append(Setting(name='xbee_device_manager',
                                         type = str, required = True))
            self.__xbee_aio_driver = self.__xbee_dio_driver = \
                                     XBeeLocalIO(self, core_services,
                                         self.__analog_channels,
                                         self.__digital_channels)
        elif get_platform_name() == 'digiconnect':
            settings_list.append(Setting(name='xbee_device_manager',
                                         type = str, required = True))
            self.__xbee_aio_driver = self.__xbee_dio_driver = \
                                     XBeeLocalIO(self, core_services,
                                         self.__analog_channels,
                                         self.__digital_channels)

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)


    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # there were problems with settings, terminate early:
            self.__tracer.error("Settings rejected/not found: %s %s",
                                rejected, not_found)
            return (accepted, rejected, not_found)

        # Walk each setting, and verify the physical channel type
        # is the same type the user specified in their config.
        for setting in accepted.copy():
            if setting[0:7] == "channel":
                try:
                    channel = setting[7]
                    operation = setting[9:]
                    type = digihw.get_channel_type(int(channel) - 1)
                    if type == self.IO_TYPE_ANALOG:
                        if operation != "mode":
                           raise ValueError, "Channel mode is not correct"
                    elif type == self.IO_TYPE_DIGITAL:
                        if operation != "dir" and operation != "source":
                           raise ValueError, "Channel mode is not correct"
                    else:
                           raise ValueError, "Channel mode is not correct"
                except Exception, e:
                    self.__tracer.error("Unable to parse settings: %s", e)
                    rejected[setting] = accepted[setting]
                    del accepted[setting]

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):

        for ch in self.__analog_channels:
            pass

        for ch in self.__digital_channels:
            pass

        self.__xbee_aio_driver.start()
        #self.__xbee_dio_driver.start()


        return True

    def stop(self):

        return True


    def refresh(self):

        return

    def __verify_power_setting(self, power):
        # The power option is ONLY supported on the X3 product.
        # So assume power is always on, and is intended to be always on.
        # Only do real checking for the False case.
        if power == Boolean(True, style = STYLE_ONOFF):
            return True
        elif power == Boolean(False, style=STYLE_ONOFF):
            if get_platform_name() == 'digix3':
                return True
            else:
                self.__tracer.error("Turning IO power off " +
                                    "on this device is not supported!")
                return False

        return False


# internal functions & classes

def _verify_aio_channel_mode(mode):
    pass

def _verify_dio_channel_direction(mode):
    pass

def _verify_dio_channel_source(mode):
    pass
