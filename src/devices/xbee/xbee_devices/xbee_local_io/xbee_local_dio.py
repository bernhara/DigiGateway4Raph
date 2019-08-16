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
    Local XBee DIO driver for the Combined Local IO DIA Driver.
"""

# imports
import digihw
from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_local_io.xbee_local_constants import \
    XBEE_SERIES2_DIGITAL_INPUT_MODE, XBEE_SERIES2_DIGITAL_OUTPUT_LOW_MODE, \
    XBEE_SERIES2_DIGITAL_OUTPUT_HIGH_MODE, DIO_HW_MODE_INPUT, \
    DIO_HW_MODE_OUTPUT_HIGH, DIO_HW_MODE_OUTPUT_LOW
from channels.channel_source_device_property import *
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *


# constants

# exception classes

# interface functions

# classes


"""\
    This class defines all the methods and functions required to
    set up an XBee based local DIO channel.
"""
class XBeeLocalDIO:

    LOCAL_DIO_CONTROL_LINES = [ "D0", "D1", "D2", "D3" ]
    LOCAL_INPUT_CHANNEL_TO_PIN = [ 0, 1, 2, 3 ]

    def __init__(self, name, parent, channel, mode, source):
        self.__name = name
        self.__parent = parent
        self.__channel = channel
        self.__mode = mode
        self.__source = source

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Local State Variables:
        self.__dia_device_obj = self.__parent.get_parent()
        self.__xbee_manager   = self.__parent.get_xbee_manager()


    def name(self):
        """\
            Returns the name of the channel, as given by DIA.
        """
        return self.__name


    def channel(self):
        """\
            Returns the channel number, as allocated when created.
        """
        return self.__channel


    def mode(self):
        """\
            Returns the current channel mode (direction).
        """
        return self.__mode


    def start(self, xbee_ddo_cfg):
        """\
            Start up our channel and configure it to our initial parameters.

            .. note:
               This function will take the passed in 'xbee_ddo_cfg' variable,
               and add parameters to it as needed to configure the channel
               into the proper mode.

            Returns bool.
        """

        # For all XBee-based DIO channels, they all can and do report their
        # input value, regardless of whether the channels is set to input
        # or output.
        self.__dia_device_obj.add_property(
            ChannelSourceDeviceProperty(
            name = 'channel%d_input' % (self.__channel + 1), type = bool,
            initial = Sample(timestamp = 0, value = False, unit = 'bool'),
            perms_mask = DPROP_PERM_GET,
            options = DPROP_OPT_AUTOTIMESTAMP))

        if self.__mode == 'in':
            digihw.configure_channel(self.__channel, DIO_HW_MODE_INPUT)
            xbee_ddo_cfg.add_parameter(self.LOCAL_DIO_CONTROL_LINES[self.__channel],
                                   XBEE_SERIES2_DIGITAL_INPUT_MODE)
        elif self.__mode == 'out':
            self.__dia_device_obj.add_property(
                ChannelSourceDeviceProperty(
                name = 'channel%d_output' % (self.__channel + 1), type = bool,
                initial = Sample(timestamp = 0, value = False, unit = 'bool'),
                perms_mask = (DPROP_PERM_GET | DPROP_PERM_SET),
                options = DPROP_OPT_AUTOTIMESTAMP,
                set_cb = lambda sample, io = self.__channel: self.set_output(sample, io)))

            # If set, subscribe to the channel that drives our output logic:
            if len(self.__source):
                cm = self.__dia_device_obj.__core.get_service("channel_manager")
                cp = cm.channel_publisher_get()
                cp.subscribe(source, lambda chan, io = self.__channel: self.update(chan, io))

        return True


    def stop(self):
        """\
            Stop the channel and possibly unconfigures it as well.
            Returns bool.
        """
        return True


    def configure_channel(self, mode):
        """\
            Configure/Reconfigure our channel to the given mode.
            The mode is assumed checked and correct before calling
            this function.
        """

        self.__mode = mode


    def turn_on_calibration_series2(self):
        """\
            There is no calibration required for a DIO channel.
        """
        pass


    def turn_off_calibration_series2(self):
        """\
            There is no calibration required for a DIO channel.
        """
        pass


    def turn_on_calibration_series1(self):
        """\
            There is no calibration required for a DIO channel.
        """
        pass


    def turn_off_calibration_series1(self):
        """\
            There is no calibration required for a DIO channel.
        """
        pass


    def decode_sample(self, io_sample, scale, offset):
        """\
            Given a IO sample taken from the local XBee radio, this function
            will convert the data it owns in the IO sample, into a DIA Sample()
        """
        decoded_sample = None
        key = 'DIO%d' % self.LOCAL_INPUT_CHANNEL_TO_PIN[self.__channel]
        if io_sample.has_key(key):
            val = bool(io_sample[key])
            decoded_sample = Sample(0, val, "bool")

        return decoded_sample


    def set_output(self, sample, io_pin):
        """\
            This callback function sets whether our output mode
            is High (True), or Low (False).
        """
        new_val = False

        # Attempt to convert the give sample to a bool.
        # If we take an Exception, simply don't change anything,
        # and leave.
        try:
            new_val = bool(sample.value)
        except:
            return

        # Decide upon our output mode.  High = True, Low = False.
        if new_val == True:
            hw_val  = DIO_HW_MODE_OUTPUT_HIGH
            ddo_val = XBEE_SERIES2_DIGITAL_OUTPUT_HIGH_MODE
        else:
            hw_val  = DIO_HW_MODE_OUTPUT_LOW
            ddo_val = XBEE_SERIES2_DIGITAL_OUTPUT_LOW_MODE

        # Attempt the mode change now.
        try:
            digihw.configure_channel(self.__channel, hw_val)
            self.__xbee_manager.xbee_device_ddo_set_param(None,
                self.LOCAL_DIO_CONTROL_LINES[self.__channel],
                ddo_val, apply = True)
        except:
            self.__tracer.error("Exception setting output '%s'", str(e))


        property = "channel%d_output" % (self.__channel + 1)
        self.__dia_device_obj.property_set(property,
            Sample(0, new_val, "bool"))


    def update(self, channel, io_pin):
        """\
            This callback function allows for output (High/Low) to be
            changed on-the-fly by the value of a given channel value.
        """
        sample = channel.get()
        self.set_output(sample, io_pin)



#internal functions & classes


