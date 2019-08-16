############################################################################
#                                                                          #
# Copyright (c)2010, Digi International (Digi). All Rights Reserved.       #
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
    Local XBee AIO driver for the Combined Local IO DIA Driver.
"""

# imports
import types

import digihw
from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_local_io.xbee_local_constants \
    import AIO_HW_MODE_TENV, AIO_HW_MODE_CURRENTLOOP, XBEE_SERIES2_AIO_MODE
from channels.channel_source_device_property import *
from common.digi_device_info import get_platform_name
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *

# constants

# exception classes

# interface functions

# classes

class XBeeLocalAIO:
    """
    This class defines all the methods and functions required to set
    up an XBee based local AIO channel.

    """

    LOCAL_AIO_CONTROL_LINES = [ "D0", "D1", "D2", "D3" ]

    LOCAL_AIO_MODE_CURRENTLOOP = "currentloop"
    LOCAL_AIO_MODE_TENV = "tenv"

    LOCAL_AIO_LOOP_R_OHMS = 51.3
    LOCAL_AIO_TENV_SCALE = 3.3 / 28.2

    def __init__(self, name, parent, channel, mode):
        self.__name = name
        self.__parent = parent
        self.__channel = channel
        self.__mode = mode

        ## Local State Variables:
        self.__dia_device_obj = self.__parent.get_parent()
        self.__xbee_manager   = self.__parent.get_xbee_manager()


    def name(self):
        """
        Returns the name of the channel, as given by DIA.

        """
        return self.__name


    def channel(self):
        """
        Returns the channel number, as allocated when created.

        """
        return self.__channel


    def mode(self):
        """
        Returns the current channel mode.

        """
        return self.__mode


    def start(self, xbee_ddo_cfg):
        """
        Start up our channel and configure it to our initial parameters.

        .. note: This function will take the passed in 'xbee_ddo_cfg' variable,
            and add parameters to it as needed to configure the channel
            into the proper mode.

        Returns bool.

        """

        self.__dia_device_obj.add_property(
            ChannelSourceDeviceProperty(name = "channel%d_value" % (self.__channel + 1),
            type = float,
            initial = Sample(timestamp = 0, unit = "V", value = 0.0),
            perms_mask = DPROP_PERM_GET|DPROP_PERM_REFRESH,
            options = DPROP_OPT_AUTOTIMESTAMP,
            refresh_cb = self.__parent.refresh))

        if self.__mode == self.LOCAL_AIO_MODE_CURRENTLOOP:
            digihw.configure_channel(self.__channel, AIO_HW_MODE_CURRENTLOOP)
        elif self.__mode == self.LOCAL_AIO_MODE_TENV:
            digihw.configure_channel(self.__channel, AIO_HW_MODE_TENV)

        xbee_ddo_cfg.add_parameter(self.LOCAL_AIO_CONTROL_LINES[self.__channel],
                                   XBEE_SERIES2_AIO_MODE)
        return True


    def stop(self):
        """
        Stop the channel and possibly unconfigures it as well.

        Returns bool.

        """
        return True


    def configure_channel(self, mode):
        """
        Configure/Reconfigure our channel to the given mode.

        The mode is assumed checked and correct before calling
        this function.

        """

        # Ensure that we are NOT in calibration mode.
        self.turn_off_calibration_series2()

        if mode == self.LOCAL_AIO_MODE_CURRENTLOOP:
            digihw.configure_channel(self.__channel, AIO_HW_MODE_CURRENTLOOP)
        elif mode == self.LOCAL_AIO_MODE_TENV:
            digihw.configure_channel(self.__channel, AIO_HW_MODE_TENV)

        self.__xbee_manager.xbee_device_ddo_set_param(None,
            self.LOCAL_AIO_CONTROL_LINES[self.__channel], XBEE_SERIES2_AIO_MODE,
                                                          apply = True)
        self.__mode = mode


    def turn_on_calibration_series2(self):
        """
        Turn on calibration mode for the channel when using a
        XBee Series 2 Radio (ZNet 2.5, ZB).

        On all supported products, the channel must be changed
        to either TenV or CurrentLoop mode first.
        Since DIA requires all the AIO channels to be defined to a mode
        during configuration, we can assume here that the channel
        has been configured to either TenV or CurrentLoop already,
        and so we do NOT need to set a channel mode here.

        Then based on the product, to have the unit read the known
        "calibrated" values of .6V and 1V respectively, you must do:

            On X3-based products, the GPIO pin 0 must be set to 0.

            On nds-based products, the device uses 2 GPIO pins on
            the XBee radio for switching to and from the calibrated values.
            Thus, we need to issue 2 XBee DDO commands that will tell
            the XBee radio to swap its reads for that channel.
            Channel 0: DDO P2 -> 4
            Channel 1: DDO D4 -> 4

        """

        # X3-based product calibration
        # Set GPIO 0 = 0
        if get_platform_name() == 'digix3':
            digihw.gpio_set_value(0, 0)

        # nds-based product calibration
        # Issue the special XBee DDO commands to swap inputs to known values
        elif get_platform_name() == 'digiconnect':
            if self.__channel == 0:
                self.__xbee_manager.xbee_device_ddo_set_param(None, 'P2', 4,
                                    apply = True)
            elif self.__channel == 1:
                self.__xbee_manager.xbee_device_ddo_set_param(None, 'D4', 4,
                                    apply = True)


    def turn_off_calibration_series2(self):
        """
        Turn off calibration mode for the channel when using a
        XBee Series 2 Radio (ZNet 2.5, ZB).

        This function reverses the process of what the function
        'turn_off_calibration_series2' did, and sets us back into
        normal operating mode.

        To do this:

            On X3-based products, the GPIO pin 0 must be set to 1.

            On nds-based products, the device uses 2 GPIO pins on
            the XBee radio for switching to and from the calibrated values.
            Thus, we need to issue 2 XBee DDO commands that will tell
            the XBee radio to swap its reads back for that channel.
            Channel 0: DDO P2 -> 5
            Channel 1: DDO D4 -> 5
        """

        # X3-based product calibration
        #
        # Set GPIO 0 = 1
        if get_platform_name() == 'digix3':
            digihw.gpio_set_value(0, 1)

        # nds-based product calibration
        #
        # Issue the special XBee DDO commands to swap inputs to known values
        elif get_platform_name() == 'digiconnect':
            if self.__channel == 0:
                self.__xbee_manager.xbee_device_ddo_set_param(None, 'P2', 5,
                                    apply = True)
            elif self.__channel == 1:
                self.__xbee_manager.xbee_device_ddo_set_param(None, 'D4', 5,
                                    apply = True)


    def turn_on_calibration_series1(self):
        """
        Turn on calibration mode for the channel when using a
        XBee Series 1 Radio.

        Currently these radios are ONLY supported on nds-based products.
        (The X3-based do NOT support Series 1 radios!)

        The channel must be changed to either TenV or CurrentLoop mode first.
        Since DIA requires all the AIO channels to be defined to a mode
        during configuration, we can assume here that the channel
        has been configured to either TenV or CurrentLoop already,
        and so we do NOT need to set a channel mode here.

        Next, on nds-based products, the device uses 1 GPIO pin on
        the XBee radio for switching to and from the calibrated values.
        Thus, we need to issue 1 XBee DDO command that will tell
        the XBee radio to swap its reads for that channel.

            Channel 1: DDO D4 -> 4
        """

        self.__xbee_manager.xbee_device_ddo_set_param(None, 'D4', 4,
                                                      apply = True)


    def turn_off_calibration_series1(self):
        """
        Turn off calibration mode for the channel when using a
        XBee Series 1 Radio.

        Currently these radios are ONLY supported on nds-based products.
        (The X3-based do NOT support Series 1 radios!)

        This function reverses the process of what the function
        'turn_on_calibration_series2' did, and sets us back into
        normal operating mode.

        On nds-based products, the device uses 1 GPIO pin on
        the XBee radio for switching to and from the calibrated values.
        Thus, we need to issue 1 XBee DDO command that will tell
        the XBee radio to swap its reads back for that channel.

            Channel 1: DDO D4 -> 5

        """

        self.__xbee_manager.xbee_device_ddo_set_param(None, 'D4', 5,
                                                      apply = True)


    def decode_sample(self, io_sample, scale, offset):
        """
        Given a IO sample taken from the local XBee radio, this function
        will convert the data it owns in the IO sample, into a DIA Sample()
        and which takes into consideration the type of input the
        channel is, as well as any scaling or offset that might
        need to be implied the resulting data.

        """
        decoded_sample = None

        aio_name = "AD%d" % (self.__channel)
        # Return early if our channel isn't in the IO sample.
        if aio_name not in io_sample:
            return

        if isinstance(io_sample[aio_name], types.BooleanType):
            # parse_is() returns 'AD0':True, (etc) if that pin is digital.
            # So we need to ignore an analog value if type Boolean
            return

        # Parse out our sample, and convert it based on scale.
        raw_value = (io_sample[aio_name]) * scale

        # Don't reduce the raw_value by the offset if the raw_value is 1023+.
        if offset != 0.0 and raw_value < 1023.0:
            raw_value = raw_value - offset

        # Round off the float value into an int.
        raw_value = int(round(raw_value))

        # Convert the raw AIO value to what our mode value dictates.
        if self.__mode == self.LOCAL_AIO_MODE_CURRENTLOOP:
            mV = raw_value * 1200.0 / 1023
            mA = mV / self.LOCAL_AIO_LOOP_R_OHMS
            # If we have gone negative by a tiny bit, which can happen
            # because of scaling, just set us back to 0.0.
            mA = max(mA, 0.0)
            # Round off resulting value to 8 decimal places.
            # This is because the climb between each
            # distinct raw value is 7 spots (about .0228659),
            # while throwing in one extra spot for the user to
            # do their own rounding as they see fit.
            mA = round(mA, 7)
            decoded_sample = Sample(0, mA, "mA")
        elif self.__mode == self.LOCAL_AIO_MODE_TENV:
            V = float(raw_value) * 10.25 / 1024.0
            # Round off resulting value to 3 decimal places.
            # This is because the climb between each distinct raw value is
            # is 2 decmimal spots (ie, 10.25 / 1024 = 0.01V), while throwing
            # in 1 extra spot for the user to round as they see fit.
            V = round(V, 3)
            decoded_sample = Sample(0, V, "V")

        return decoded_sample



#internal functions & classes
