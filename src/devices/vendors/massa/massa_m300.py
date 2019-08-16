############################################################################
#                                                                          #
# Copyright (c)2008-2011, Digi International (Digi). All Rights Reserved.  #
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
Massa M-300 Driver Connected to XBee 485 Adapter Driver

Supports a Massa M-300 device connected to a XBee 485 driver.  The following
Massa M-300 devices are supported:

    M-300/95 (min 12 in. / max. 180 in.)
    M-300/150 (min 7 in. / max. 96 in.)
    M-300/210 (min 4 in. / max. 50 in.)

Wiring information:

    M-300 Brown --> XBee 485 Pin 1 (485 Port B {+})
    M-300 Green --> XBee 485 Pin 2 (485 Port A {-})
    M-300 Black --> XBee 485 Pin 5 (GND)
    M-300 Red   --> XBee 485 Pin 6 (+12 DC)
    M-300 White --> Not Connected

XBee RS-485 DIP Switch Configuration:

    Pins 2, 3, 4 = ON (RS-485 Mode)
    Pins 5, 6    = OFF (Disable Bias, Termination)

DIA Configuration and Setup:

    By default the Massa M300 product comes from the factory set to operate
    at a baud rate of 19200, 8 character bits, 1 stop bit and no parity.

    An example configuration in DIA should look something like::

        - name: massa_m300
          driver: devices.vendors.massa.massa_m300:MassaM300
          settings:
              xbee_device_manager: xbee_device_manager
              extended_address: "00:13:a2:00:40:52:e1:93!"
              baudrate: 19200
              stopbits: 1
              parity: none
              poll_rate_sec: 60

NOTE: this driver at present does not support any sleep modes.

"""

# imports
import struct
import digitime

from core.tracing import get_tracer
from devices.xbee.xbee_devices.xbee_serial import XBeeSerial
from settings.settings_base import SettingsBase, Setting
from common.types.boolean import Boolean, STYLE_ONOFF, STYLE_YESNO
from channels.channel_source_device_property import *

from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.prodid import PROD_DIGI_XB_ADAPTER_RS485

from devices.vendors.massa.massa_m300_sensor import MassaM300_Sensor

# constants
# this is used for internal testing only
M300_DO_TRIGGER = False

# exception classes

# interface functions

# classes
class MassaM300(XBeeSerial):

    # Our base class defines all the addresses we care about.
    ADDRESS_TABLE = [ ]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [ PROD_DIGI_XB_ADAPTER_RS485, ]

    MODE_IDLE = 0
    MODE_WAIT_RSP = 1

    def __init__(self, name, core_services):

            ## These will be created by XBeeSerial
        # self._name = name
        # self._core = core_services
        # self._tracer = get_tracer(name)
        # self._xbee_manager = None
        # self._extended_address = None

        ## Local State Variables:
        self.__response_buffer = ""
        self.__request_event = None
        self.__mode = self.MODE_IDLE
        self.__req_cnt = 0
        self.__rsp_cnt = 0
        self.__sensor = None

        ## Over-ride our parent's settings
        self.DEF_BAUDRATE = 19200
        self.DEF_PARITY = 'none'
        self.DEF_STOPBITS = 1
        self.DEF_HWFLOW = '485'

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='poll_rate_sec', type=int, required=False,
                default_value=5,
                verify_function=lambda x: x >= 1),
            Setting(
                name='bus_id', type=int, required=False,
                default_value=1,
                verify_function=lambda x: x >= 0),
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="strength", type=int,
                initial=Sample(timestamp=0, value=0, unit="%"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="target_detected", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(False, style=STYLE_YESNO)),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="error_flag", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(False, style=STYLE_YESNO)),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="range", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="in"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="temperature", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="C"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="availability", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="prc"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]

        ## Initialize the DeviceBase interface:
        ## Initialize the XBeeSerial interface:
        XBeeSerial.__init__(self, name, core_services,
                                settings_list, property_list)

        self._tracer.calls("MassaM300.__init__()")


    ## Functions which must be implemented to conform to the XBeeSerial
    ## interface:

    def read_callback(self, buf):
        
        self.message_indication(buf)

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
        probe_data = XBeeSerial.probe()

        for address in MassaM300.ADDRESS_TABLE:
            probe_data['address_table'].append(address)

        # We don't care what devices our base class might support.
        # We do not want to support all of those devuces, so we will
        # wipe those out, and instead JUST use ours instead.
        probe_data['supported_products'] = []

        for product in MassaM300.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    # use XBeeSerial.apply_settings()

    def start(self):
        """Start the device driver.  Returns bool."""

        self._tracer.calls("MassaM300.start()")

        # create our M300 object
        bus_id = SettingsBase.get_setting(self, "bus_id")
        self.__sensor = MassaM300_Sensor(bus_id)
        # if bus_id isn't 0, treat as multi-drop
        self.__sensor.set_mode_multidrop(bus_id != 0)

        # init self._xbee_manager and self._extended_address
        # register ourself with our Xbee manager
        # create the self.running_indication callback
        # XBeeBase.pre_start(self)
        self.pre_start()

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(self._extended_address)

        # Enable +12v output terminal on RS-485 adapter pin 6:
        xbee_ddo_cfg.add_parameter('D2', 5)

        # Register configuration blocks with the XBee Device Manager:
        self._xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Call the XBeeSerial function to add the initial set up of our device.
        # This will set up the destination address of the devidce, and also set
        # the default baud rate, parity, stop bits and flow control.
        return XBeeSerial.start(self)

    # use XBeeSerial.stop()
    def stop(self):
        """Stop the device driver.  Returns bool."""

        # cancel any out-standing events
        try:
            self._xbee_manager.xbee_device_schedule_cancel(self.__request_event)
        except:
            pass
        self.__request_event = None

        return XBeeSerial.stop(self)


    ## Locally defined functions:
    def running_indication(self):
        """\
            DIA will call this function when it has finished sending the
            preliminary DDO command blocks to the M300 device.
            At this point, the M300 is correctly configured at the XBee level
            to be able to accept data from us.
        """
        self._tracer.calls("running_indication")
        self._tracer.info("Configuration complete - device is now running")
        self.__schedule_request(1.0)
        return

    def make_request(self):
        self._tracer.calls("make_request")

        # first thing, RE-SCHEDULE so we keep running despite a fault
        self.__schedule_request()

        self.__req_cnt += 1
        self.__response_buffer = ""
        if self.__mode == self.MODE_WAIT_RSP:
            self._tracer.warning("Last Poll never finished")
            self.update_availability()

        if M300_DO_TRIGGER:
            # for testing only
            buf = self.__sensor.req_software_trigger_1()
            self.write(buf)
            digitime.sleep(0.1)

        buf = self.__sensor.req_status_3()

        try:
            ret = self.write(buf)
            if ret == False:
                raise Exception, "write failed"
            self.__mode = self.MODE_WAIT_RSP

        except:
            # try again later:
            self._tracer.error("xmission failure.")
            self.__mode = self.MODE_IDLE

        return

    def __schedule_request(self, delay=0):

        self._tracer.calls("__schedule_request")

        # Attempt to Cancel pending requests
        if self.__request_event is not None:
            try:
                self._xbee_manager.xbee_device_schedule_cancel(self.__request_event)
            except:
                pass

        # Request a new event at our poll rate in the future.
        if delay == 0:
            # then use setting
            delay = SettingsBase.get_setting(self, "poll_rate_sec")

        self.__request_event = self._xbee_manager.xbee_device_schedule_after(
            delay, self.make_request)

    def message_indication(self, buf):
        self._tracer.calls("message indication.")

        self.__response_buffer += buf

        if len(self.__response_buffer) < 6:
            # Response may have been fragmented, so wait for more pieces
            self._tracer.debug("Received incomplete data")
            return

        # we have our response, move state to IDLE
        self.__mode = self.MODE_IDLE

        dct = self.__sensor.ind_status_3(buf)
        if self._tracer.debug:
            self._tracer.debug('parsed ind: %s', str(dct))
            
        now = digitime.time()
        if dct.has_key('error'):
            # then the indication failed
            self.__response_buffer = ""
            
        else:
            # Update our channels:
            self.__rsp_cnt += 1
            self.property_set("strength", 
                Sample(now, dct['strength'], "%"))
            self.property_set("target_detected",
                Sample(now, Boolean(dct['target_detected'], STYLE_YESNO)))
            self.property_set("error_flag",
                Sample(now, Boolean(dct['sensor_error'], STYLE_YESNO)))
            self.property_set("range", 
                Sample(now, dct['range'], "in"))
            self.property_set("temperature", 
                Sample(now, dct['temperature'], "C"))

            if self._tracer.info:
                self._tracer.info("temp=%0.1fC range=%0.1fin strength=%d%%",
                    dct['temperature'], dct['range'], dct['strength'])

        self.update_availability(now)
        return

    def update_availability(self, now=0):

        if self.__req_cnt == 0:
            avail = 0.0
        else:
            avail = (self.__rsp_cnt * 100.0) / self.__req_cnt

        if self.__req_cnt > 10000:
            # reset the ints
            self.__req_cnt = 1000
            self.__rsp_cnt = int(avail) * 10
            
        self.property_set("availability", Sample(now, avail, "prc"))

        self._tracer.debug("Availability = %d%%", int(avail))

        return

# internal functions & classes

