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

"""\
A Generic DIA XBee Serial Driver


To Use:
-------

This XBee Serial class is intended to be used by deriving a new class based
on this class.

This driver attempts to shield the user from the low level details
on how to set various serial settings that use cryptic AT commands.

The function calls that are intended to be used by the driver writer are:

* :py:func:`~XBeeSerial.initialize_xbee_serial`
* :py:func:`~XBeeSerial.write`
* :py:func:`~XBeeSerial.set_baudrate`
* :py:func:`~XBeeSerial.get_baudrate`
* :py:func:`~XBeeSerial.set_parity`
* :py:func:`~XBeeSerial.get_parity`
* :py:func:`~XBeeSerial.set_stopbits`
* :py:func:`~XBeeSerial.get_stopbits`
* :py:func:`~XBeeSerial.set_hardwareflowcontrol`
* :py:func:`~XBeeSerial.get_hardwareflowcontrol`

When deriving from this class, the user should be aware of 2 things:

1. During your 'start' function, you should declare a ddo config block,
   then pass that config block into the
   :py:func:`~XBeeSerial.initialize_xbee_serial` function.

   This class will add commands to your config block to set up the
   serial parameters.

   For example::

       xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)
       XBeeSerial.initialize_xbee_serial(self, xbee_ddo_cfg)
       self._xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

2. The user needs to declare a 'read_callback' function.
   Whenever serial data is received, this driver will forward this data
   to the derived class that has this function declared.


Settings:
---------

* **baudrate:** Optional parameter. Acceptable integer baud rates are from
  8 through 921600. If not set, the default value of 9600 will be used.
* **parity:** Optional parameter. Acceptable parity values are the follow
  strings:

    * none
    * even
    * odd
    * mark

    If not set, the default value of 'none' will be used.
* **stopbits:** Optional parameter. Acceptable stopbit values are:

    * 1
    * 2

    If not set, the default value of 1 will be used.

    .. Note::
        Not all XBee/ZigBee firmware supports setting the stop bit
        value. In these cases, the stop bit will always be 1.

* **hardwareflowcontrol:** Optional parameter. Acceptable hardware flow
  control values are:

    * **True:** Will enable full RTS/CTS flow control.
    * **False:** Will turn OFF RTS/CTS flow control.
    * **RTS:** Enable DCE-RTS input only, Disable CTS
    * **CTS:** Enable DCE-CTS output only, Disable RTS
    * **rs485:** Set for RS-485 half-duplex control

    If not set, the default value of False will be used.

"""

# imports
import struct
import traceback
import types

from core.tracing import get_tracer
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
import devices.xbee.common.bindpoints as bindpoints
from channels.channel_source_device_property import *
from common.types.boolean import Boolean, STYLE_ONOFF
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *
from devices.xbee.common.io_sample import parse_is
from devices.xbee.common.prodid import *

# constants

# exception classes

# interface functions

# classes
class XBeeSerial(XBeeBase):
    """\
        A Generic XBee Serial base class.

        This class allows a user to build upon it to create their
        own driver for an XBee serial based device.

        Keyword arguments:

            * **name:** The name of the XBee device instance.
            * **core_services:** The Core Services instance.
            * **settings:** The list of settings.
            * **properties:** The list of properties.

    """

    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [bindpoints.SERIAL, bindpoints.SAMPLE]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [ PROD_DIGI_XB_ADAPTER_RS232, PROD_DIGI_XB_ADAPTER_RS485, ]

    BAUD_RATES = {
        1200:   0,
        2400:   1,
        4800:   2,
        9600:   3,
        19200:  4,
        38400:  5,
        57600:  6,
        115200: 7,
        230400: 8,
        }

    LIMITS = {
        MOD_XB_802154: (0, 7, True),
        MOD_XB_ZNET25: (0, 7, True),
        MOD_XB_ZB: (0, 7, True),
        MOD_XB_DIGIMESH900: (0, 8, True),
        MOD_XB_DIGIMESH24: (0, 8, True),
        MOD_XB_868: (0, 8, True),
        MOD_XB_DP900: (0, 8, True),
        MOD_XTEND_DM900: (0, 6, True),
        MOD_XB_80211: (0, 8, True),
        MOD_XB_S2C_ZB: (0, 7, True),
        MOD_XB_S3C_DIGIMESH900: (0, 8, True),
        MOD_XB_868_DIGIMESH: (0, 8, True),
        }


    # language is DCE here (like XBee)
    # D6 = RTS input, D7 = CTS output or RS-485
    HWFLOW = {  # D6, D7
        'true'  : (1, 1),
        'false' : (0, 0),
        'rts'   : (1, 0),
        'cts'   : (0, 1),
        'rs485'   : (0, 7),
        }

    # default settings - allows derived class to over-ride
    DEF_BAUDRATE = 9600
    DEF_PARITY = 'none'
    DEF_STOPBITS = 1
    DEF_HWFLOW = 'false'

    def __init__(self, name, core_services, set_in=None, prop_in=None):

        # DeviceBase will create:
        #   self._name, self._core, self._tracer,
        # XBeeBase will create:
        #   self._xbee_manager, self._extended_address

        ## Local State Variables:

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='baudrate', type=int, required=False,
                default_value=self.DEF_BAUDRATE,
                verify_function=self.__verify_baudrate),
            Setting(
                name='parity', type=str, required=False,
                default_value=self.DEF_PARITY,
                verify_function=self.__verify_parity),
            # NOTE: SB/Stop-bits is not available in all XBEE
            Setting(
                name='stopbits', type=int, required=False,
                default_value=self.DEF_STOPBITS,
                verify_function=self.__verify_stopbits),
            Setting(
                name='hardwareflowcontrol', type=str, required=False,
                default_value=self.DEF_HWFLOW,
                verify_function=self.__verify_hwflow),
                
            # These setting is for legacy compatibility & ignored.
            # Having it here is not appropriate given this driver is commonly
            # used with third party XBee products.
            Setting(
                name='enable_low_battery', type=Boolean, required=False,
                default_value=False),
        ]
        # Add our settings_list entries into the settings passed to us.
        set_in = self.merge_settings(set_in, settings_list)

        ## Channel Properties Definition:
        # property_list = []
        # Add our property_list entries into the properties passed to us.
        # prop_in = self.merge_properties(prop_in, property_list)

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, name, core_services, set_in, prop_in)

        self._tracer.calls("XBeeSerial.__init__()")


    ## Functions which must be implemented to conform to the XBeeSerial
    ## interface:

    def read_callback(self):
        raise NotImplementedError, "virtual function"


    ## Functions which must be implemented to conform to the XBeeBase
    ## interface:

    @staticmethod
    def probe():
        """\
            Collect important information about the driver.

            .. Note::

                * This method is a static method.  As such, all data returned
                  must be accessible from the class without having a instance
                  of the device created.

            Returns a dictionary that must contain the following 2 keys:
                    1) address_table:
                       A list of XBee address tuples with the first part of the
                       address removed that this device might send data to.
                       For example: [ 0xe8, 0xc105, 0x95 ]
                    2) supported_products:
                       A list of product values that this driver supports.
                       Generally, this will consist of Product Types that
                       can be found in 'devices/xbee/common/prodid.py'
        """
        probe_data = XBeeBase.probe()

        for address in XBeeSerial.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeSerial.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    # use XBeeBase.apply_settings()

    def start(self):
        """Start the device driver.  Returns bool."""

        self._tracer.calls("XBeeSerial.start()")

        # init self._xbee_manager and self._extended_address
        # register ourself with our Xbee manager
        # create the self.running_indication callback
        XBeeBase.pre_start(self)

        self.initialize_xbee_serial()

        # we've no more to config, indicate we're ready to configure.
        return XBeeBase.start(self)


    # use XBeeBase.stop()

    ## Locally defined functions:

    def initialize_xbee_serial(self, xbee_ddo_cfg=None):
        """\
        Creates a DDO command sequence of the user selected serial settings.

        .. Note::
            * This routine does everything EXCEPT calling for final configuration
            * It will add its own ddo config block
            * The caller can add another after the return

        For example::
            XBeeSerial.initialize_xbee_serial(self)
            my_ddo_cfg = XBeeConfigBlockDDO(self._extended_address)
            my_ddo_cfg.add_parameter('IR', 60000)
            self._xbee_manager.xbee_device_config_block_add(self, my_ddo_cfg)
            self._xbee_manager.xbee_device_configure(self)

        Returns True if successful, False on failure.
        """

        self._tracer.calls("XBeeSerial.initialize_xbee_serial()")

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:

        self._xbee_manager.register_serial_listener(self,
                        self._extended_address, self.__read_callback)

        # callback for cb_set(self.__running_indication) is in xbee_base()

        # Create a DDO configuration block for this device:
        if xbee_ddo_cfg is None:
            xbee_ddo_cfg = XBeeConfigBlockDDO(self._extended_address)

        # Set up the baud rate for the device.
        try:
            baud = SettingsBase.get_setting(self, "baudrate")
        except:
            baud = self.DEF_BAUDRATE
        baud = self.__derive_baudrate(baud)
        xbee_ddo_cfg.add_parameter('BD', baud)

        # Set up the parity for the device.
        try:
            parity = SettingsBase.get_setting(self, "parity")
        except:
            parity = self.DEF_PARITY
        parity = self.__derive_parity(parity)
        xbee_ddo_cfg.add_parameter('NB', parity)

        if self._xbee_manager.is_zigbee():
            # Set up the stop bits for the device.
            try:
                stopbits = SettingsBase.get_setting(self, "stopbits")
            except:
                stopbits = self.DEF_STOPBITS
            stopbits = self.__derive_stopbits(stopbits)
            # The SB command is new.
            # It may or may not be supported on the XBee Serial Device/Adapter.
            # If its not supported, then we know the device
            # is simply at 1 stop bit, and we can ignore the failure.
            xbee_ddo_cfg.add_parameter('SB', stopbits,
                                       failure_callback=self.__ignore_if_fail)
        # else skip it for 802.15.4 or DigiMesh

        # Set up the hardware flow control mode for the device.
        try:
            hwflow = SettingsBase.get_setting(self, "hardwareflowcontrol")
        except:
            hwflow = self.DEF_HWFLOW
        d6, d7 = self.__derive_hardwareflowcontrol(hwflow)
        xbee_ddo_cfg.add_parameter('D6', d6)
        xbee_ddo_cfg.add_parameter('D7', d7)

        self._xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        return True

    def read_callback(self, buf, addr=None):
        # your routine can over-ride
        return

    def __read_callback(self, buf, addr):
        if self._tracer.debug():
            # this if-then cuts performance cost since str() is always
            # performed - even when not debugging
            self._tracer.debug("Received Data from: %s, len %d.",
                            str(addr[0]), len(buf))

        return self.read_callback(buf)


    # use XBeeBase.running_indication()


    def write(self, data):
        """\
        Writes a buffer of data out the XBee.

        Returns True if successful, False on failure.
        """

        if self._tracer.debug():
            # this if-then cuts performance cost since str() is always
            # performed - even when not debugging
            self._tracer.debug("Send Data to: %s, len %d.",
                            str(self._extended_address), len(data))

        ret = False
        addr = (self._extended_address, 0xe8, 0xc105, 0x11)
        try:
            self._xbee_manager.xbee_device_xmit(0xe8, data, addr)
            ret = True
        except:
            self._tracer.warning(traceback.format_exc())
            
        return ret

    def set_baudrate(self, baud):
        """\
Sets the baud rate.

.. Note::
    * Acceptable values are 8 through 921600.
    * Direct values are the following:

        * 1200
        * 2400
        * 4800
        * 9600
        * 19200
        * 38400
        * 57600
        * 115200
    * If a baud rate is specified that is NOT in the above list,
      the XBee firmware will pick the closest baud rate that it
      is able to support.
    * A call to get_baudrate() will allow the caller to determine
      the real value the firmware was able to support.

Returns True if successful, False on failure.
        """

        ret = False
        baud = self.__derive_baudrate(baud)
        try:
            self._xbee_manager.xbee_device_ddo_set_param(
                    self._extended_address, 'BD', baud)
            ret = True
        except:
            pass
        return ret

    def get_baudrate(self):
        """\
Returns the baud rate the device is currently set to, 0 on failure.
        """

        try:
            baud = self._xbee_manager.xbee_device_ddo_get_param(
                    self._extended_address, 'BD')
            baud = self.__decode_baudrate(baud)
        except:
            self._tracer.error("Failed to retrieve baudrate from device.")
            baud = 0
        return baud

    def set_parity(self, parity):
        """\
Sets the parity.

.. Note::
    Acceptable parity values are:
    * none
    * even
    * odd
    * mark

Returns True if successful, False on failure.
        """

        ret = False
        parity = self.__derive_parity(parity)
        try:
            self._xbee_manager.xbee_device_ddo_set_param(
                        self._extended_address, 'NB', parity)
            ret = True
        except:
            pass
        return ret

    def get_parity(self):
        """\
Returns the parity value the device is currently set to.
        """

        try:
            par = self._xbee_manager.xbee_device_ddo_get_param(
                        self._extended_address, 'NB')
            par = self.__decode_parity(par)
        except:
            self._tracer.error("Failed to retrieve parity value from device.")
            par = 'none'
        return par

    def set_stopbits(self, stopbits):
        """\
Sets the number of stop bits.

.. Note::
    * Acceptable parity values are 1 or 2.
    * The SB command is new.
    * It may or may not be supported on the XBee Serial Device/Adapter.
    * If its not supported, then we know the device is simply at
      1 stop bit, and we can ignore the failure.

Returns  True if successful, False on failure.
        """

        ret = True
        if self._xbee_manager.is_zigbee():
            ret = False
            stopbits = self.__derive_stopbits(stopbits)
            try:
                self._xbee_manager.xbee_device_ddo_set_param(
                        self._extended_address, 'SB', stopbits)
                ret = True
            except:
                pass
        return ret

    def get_stopbits(self):
        """\
Returns the number of stop bits the device is currently set to.

.. Note::
    * The SB command is new.
    * It may or may not be supported on the XBee Serial Device/Adapter.
    * If its not supported, then we know the device is simply at
      1 stop bit, and we can ignore the failure.

Returns 1 or 2 on success, 1 on failure.
        """

        try:
            sb = self._xbee_manager.xbee_device_ddo_get_param(
                        self._extended_address, 'SB')
            sb = self.__decode_stopbits(sb)
        except:
            self._tracer.error("Failed to retrieve stopbits " \
                                "value from device.")
            sb = 1
        return sb

    def set_hardwareflowcontrol(self, hwflow):
        """\
        Sets whether hardware flow control (RTS and CTS) should be set.

        .. Note::
           Acceptable parity values are:
           * True
           * False

           Returns True if successful, False on failure.
        """

        ret = False
        d6, d7 = self.__derive_hardwareflowcontrol(hwflow)

        try:
            self._xbee_manager.xbee_device_ddo_set_param(
                        self._extended_address, 'D6', d6)
            self._xbee_manager.xbee_device_ddo_set_param(
                        self._extended_address, 'D7', d7)
            ret = True
        except:
            pass

        return ret

    def get_hardwareflowcontrol(self):
        """\
Returns whether the device is currently set to do hardware flow
control, False on failure
        """

        try:
            rts = self._xbee_manager.xbee_device_ddo_get_param(
                        self._extended_address, 'D6')
            cts = self._xbee_manager.xbee_device_ddo_get_param(
                        self._extended_address, 'D7')
            hwflow = self.__decode_hardwareflowcontrol(rts, cts)
        except:
            self._tracer.error("Failed to retrieve hardware flowcontrol " +
                                "value from device.")
            hwflow = False
        return hwflow

    # Internal class functions - Not to be used outside of this class.

    def __verify_baudrate(self, baud):
        if baud > 7 and baud <= 921600:
            return
        raise ValueError("Invalid baud rate '%s': The value must be above " \
                         "7 and equal or less than 921600" % (baud))

    def __verify_parity(self, parity):
        p = parity.lower()
        if p == 'none' or p == 'even' or p != 'odd' or p != 'mark':
            return
        raise ValueError("Invalid parity '%s': The value must one of: " \
                         "'none', 'even', 'odd', 'mark'")

    def __verify_stopbits(self, stopbits):
        if stopbits == 1 or stopbits == 2:
            return
        raise ValueError("Invalid stopbits '%s': The value must be either "\
                         "'1' or '2'")

    def __verify_hwflow(self, hwflow):
        '''convert setting into (D6,D7) values'''
        try:
            hwflow = hwflow.lower()
            if self.HWFLOW.has_key(hwflow):
                return

        except:
            traceback.print_exc()
            pass

        raise ValueError("Invalid hardwareflow '%s': must be in ("\
                         "'true','false','rts','cts','rs485')" % hwflow)

    def __derive_baudrate(self, baud):
        # Attempt to figure out the baud rate as one of the direct bauds the
        # firmware supports.
        # If we can't, we can tell the unit the baud rate we really want,
        # and it will attempt to pick the closest baud rate it can actually do.
        try:
            baud = self.BAUD_RATES[baud]
        except:
            pass
        return baud

    def __decode_baudrate(self, baud):
        baud = struct.unpack("I", baud)
        baud = baud[0]

        # If baud is above 8, we have the actual baud rate already.
        if baud > 8:
            return baud

        # Otherwise, the baud has to be looked up in our table.
        for i, j in self.BAUD_RATES.iteritems():
            if j == baud:
                return i

        return baud

    def __derive_parity(self, parity):
        parity = parity.lower()
        if parity == 'none':
            parity = 0
        elif parity == 'even':
            parity = 1
        elif parity == 'odd':
            parity = 2
        elif parity == 'space':
            parity = 3
        else:
            parity = 0
        return parity

    def __decode_parity(self, parity):
        parity = struct.unpack("B", parity)
        parity = parity[0]
        if parity == 0:
           return 'none'
        elif parity == 1:
           return 'even'
        elif parity == 2:
           return 'odd'
        elif parity == 3:
           return 'space'
        else:
           return 'none'


    def __derive_stopbits(self, stopbits):
        if stopbits == 1:
           stopbits = 0
        elif stopbits == 2:
           stopbits = 1
        else:
           stopbits = 0
        return stopbits


    def __decode_stopbits(self, stopbits):
        stopbits = struct.unpack("B", stopbits)
        stopbits = stopbits[0]
        if stopbits == 0:
           return 1
        elif stopbits == 1:
           return 2
        else:
           return 1


    def __derive_hardwareflowcontrol(self, hwflow):
        '''convert setting into (D6,D7) values'''
        if isinstance(hwflow, types.BooleanType):
            hwflow = str(hwflow)

        try:
            hwflow = hwflow.lower()
            d6,d7 = self.HWFLOW[hwflow]
            self._tracer.debug('Derive HWFlow(%s) as D6=%d D7=%d',
                    hwflow, d6, d7)
            return d6,d7

        except:
            raise ValueError("Invalid hardwareflow '%s': must be in ("\
                         "'true','false','rts','cts','rs485')" % hwflow)


    def __decode_hardwareflowcontrol(self, d6, d7):
        d6 = struct.unpack("B", d6)[0]
        d7 = struct.unpack("B", d7)[0]
        if d7 == 7:
            return 'rs485'
        elif d6 == 1:
            if d7 == 1:
                return 'true'
            else:
                return 'rts'
        elif d6 == 0:
            if d7 == 1:
                return 'cts'
            else:
                return 'false'

        return 'error'

    def __ignore_if_fail(self, mnemonic, value):
        return True



# internal functions & classes
