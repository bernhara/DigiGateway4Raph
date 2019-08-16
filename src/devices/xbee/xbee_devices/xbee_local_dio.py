############################################################################
#                                                                          #
# Copyright (c)2009, Digi International (Digi). All Rights Reserved.       #
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
A DIA Driver for the XBee Digital IO on the Coordinator
"""

# imports
import digihw
from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.types.boolean import Boolean, STYLE_ONOFF, STYLE_TF

from devices.xbee.common.prodid \
    import MOD_XB_802154, MOD_XB_ZNET25, MOD_XB_ZB, MOD_XB_S2C_ZB, parse_dd
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep \
    import CYCLIC_SLEEP_EXT_MAX_MS, SM_DISABLED, XBeeConfigBlockSleep
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *

from devices.xbee.common.io_sample import parse_is

# constants

# exception classes

# interface functions

# classes
class XBeeLocalDIO(XBeeBase):
    """\
        This class extends one of our base classes and is intended as an
        example of a concrete, example implementation, but it is not itself
        meant to be included as part of our developer API. Please consult the
        base class documentation for the API and the source code for this file
        for an example implementation.

    """
    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Local State Variables:
        self.__xbee_manager = None

        # Settings
        #  xbee_device_manager: must be set to the name of an XBeeDeviceManager
        #                       instance.
        # sample_rate_ms: the sample rate of the XBee adapter.
        # channel1_dir: Operating I/O mode for pin 1 of the adapter.
        #               Must be a string value comprised of one of the following:
        #                   "In" - pin is configured to be an input.
        #                   "Out" - pin is configured to be an output.
        # channel2_dir: Operating I/O mode for pin 2 of the adapter.
        #               See channel2_dir for valid setting information.  
        # channel3_dir: Operating I/O mode for pin 3 of the adapter.
        #               See channel3_dir for valid setting information.
        # channel4_dir: Operating I/O mode for pin 4 of the adapter.  
        #               See channel4_dir for valid setting information.
        # channel1_source: If channel1_dir is configed as an output, this
        #                  option setting may be specified to a
        #                  "device.channel" channel name.  The Boolean value
        #                  of this channel will specify to logic state for
        #                  pin 1 on the adapter.
        # channel2_source: Configures output value source channel for pin 2
        #                  of the adapter.
        #                  See channel1_source setting information.
        # channel3_source: Configures output value source channel for pin 3
        #                  of the adapter.
        #                  See channel1_source setting information.
        # channel4_source: Configures output value source channel for pin 4
        #                  of the adapter.
        #                  See channel1_source setting information.

        settings_list = [
            Setting(
                name='extended_address', type=str, required=False,
                default_value=''),
            Setting(
                name='sample_rate_ms', type=int, required=True,
                default_value=60000,
                verify_function=lambda x: x >= 0 and x <= CYCLIC_SLEEP_EXT_MAX_MS),
           Setting(
                name='channel1_dir', type=str, required=True),
            Setting(
                name='channel1_source', type=str, required=False,
                default_value=''),
            Setting(
                name='channel2_dir', type=str, required=True),
            Setting(
                name='channel2_source', type=str, required=False,
                default_value=''),   
            Setting(
                name='channel3_dir', type=str, required=True),  
            Setting(
                name='channel3_source', type=str, required=False,
                default_value=''),
            Setting(
                name='channel4_dir', type=str, required=True),
            Setting(
                name='channel4_source', type=str, required=False,
                default_value=''),
        ]

        ## Channel Properties Definition:
        property_list = [
            ChannelSourceDeviceProperty(
                name='channel1_input', type=bool,
                initial=Sample(timestamp=0, value=False, unit='bool'),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                name='channel2_input', type=bool,
                initial=Sample(timestamp=0, value=False, unit='bool'),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                name='channel3_input', type=bool,
                initial=Sample(timestamp=0, value=False, unit='bool'),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                name='channel4_input', type=bool,
                initial=Sample(timestamp=0, value=False, unit='bool'),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
        ]
                                            
        self.DIO_CONTROL_LINES = [ "d0", "d1", "d2", "d3" ]
        self.INPUT_CHANNEL_TO_PIN = [ 0, 1, 2, 3 ]
        self.DIO_MODE_INPUT = 3
        self.DIO_MODE_OUTPUT_HIGH = 3
        self.DIO_MODE_OUTPUT_LOW = 4

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)
 

    ## Functions which must be implemented to conform to the XBeeBase
    ## interface:

    @staticmethod
    def probe():
        #   Collect important information about the driver.
        #
        #   .. Note::
        #
        #       This method is a static method.  As such, all data returned
        #       must be accessible from the class without having a instance
        #       of the device created.
        #
        #   Returns a dictionary that must contain the following 2 keys:
        #           1) address_table:
        #              A list of XBee address tuples with the first part of the
        #              address removed that this device might send data to.
        #              For example: [ 0xe8, 0xc105, 0x95 ]
        #           2) supported_products:
        #              A list of product values that this driver supports.
        #              Generally, this will consist of Product Types that
        #              can be found in 'devices/xbee/common/prodid.py'

        return XBeeBase.probe()


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

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self, "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        # Create a callback specification that calls back this driver when
        # our device has left the configuring state and has transitioned
        # to the running state:
        xbdm_running_event_spec = XBeeDeviceManagerRunningEventSpec()
        xbdm_running_event_spec.cb_set(self.running_indication)
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                                        xbdm_running_event_spec)

        extended_address = None
   
        my_address = ':'.join(["%02x"%ord(b) for b in ''.join(gw_extended_address_tuple())])
        my_address = '[' + my_address + ']!'

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec.cb_set(self.sample_indication)
        xbdm_rx_event_spec.match_spec_set((my_address,
                0xe8, 0xc105, 0x92), (False, True, True, True))
        self.__xbee_manager.xbee_device_event_spec_add(self, xbdm_rx_event_spec)


        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)

        # Get the gateway's extended address:
        gw_xbee_sh, gw_xbee_sl = gw_extended_address_tuple()

        # Set the destination for I/O samples to be the gateway:
        xbee_ddo_cfg.add_parameter('DH', gw_xbee_sh)
        xbee_ddo_cfg.add_parameter('DL', gw_xbee_sl)

        # Configure pins DIO0 .. DIO3 for digital input:
        pr = 0xe1 # DIO0-3 pullups off, all else on
        ic = 0

        for io_pin in range(4):
            dir = SettingsBase.get_setting(self, 'channel%d_dir' % (io_pin+1) ) 
            dir = dir.lower()

            # Enable input on all pins:
            xbee_ddo_cfg.add_parameter(self.DIO_CONTROL_LINES[io_pin], 3)

            # Build our change detection mask for all io pins:
            ic |= 1 << self.INPUT_CHANNEL_TO_PIN[io_pin]

            if dir == 'in':
                # Disable sinking driver output:
                pass

            elif dir == 'out':
                # Create the output channel for this IO pin:
                self.add_property(
                    ChannelSourceDeviceProperty(
                        name='channel%d_output' % (io_pin+1), type=bool,
                        initial=Sample(timestamp=0, value=False, unit='bool'),
                        perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                        options=DPROP_OPT_AUTOTIMESTAMP,
                        set_cb=lambda sample, io=io_pin: \
                                self.set_output(sample, io) )
                    )

                # Set initial value of output to low:
                digihw.configure_channel(io_pin, self.DIO_MODE_OUTPUT_LOW)

                # If set, subscribe to the channel that drives our output logic:
                source = SettingsBase.get_setting(self, 'channel%d_source'
                                                  % (io_pin+1))

                if len(source):
                    if source == "True":
                        sample = Sample(digitime.time(), Boolean(True, style=STYLE_TF))
                        self.set_output(sample, io_pin)
                    elif source == "False":
                        sample = Sample(digitime.time(), Boolean(False, style=STYLE_TF))
                        self.set_output(sample, io_pin)
                    else:
                        cm = self.__core.get_service("channel_manager")
                        cp = cm.channel_publisher_get()
                        cp.subscribe(source,
                                     lambda chan, io=io_pin: self.update(chan, io))
                
        # Enable I/O line monitoring on pins DIO0 .. DIO3 &
        # enable change detection on DIO11:
        #       
        # 0x   8    0    0
        #   1000 0000 0000 (b)
        #   DDDD DDDD DDDD
        #   IIII IIII IIII
        #   OOOO OOOO OOOO
        #   1198 7654 3210
        #   10
        #
        xbee_ddo_cfg.add_parameter('IC', ic)

        # Disable any periodic I/O sampling:
        xbee_ddo_cfg.add_parameter('IR', 0)

        # Register this configuration block with the XBee Device Manager:
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        return True

    def stop(self):

        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)

        return True


    def make_request(self):
        self.__tracer.debug("make_request")

        try:
            sample = self.__xbee_manager.xbee_device_ddo_get_param(None, 'IS')
            self.__decode_sample(sample)
            self.__tracer.debug("Successfully retrieved and decoded sample.")
        except:
            self.__tracer.warning("Xmission failure, will retry.")
            pass

        # Schedule another heart beat poll.
        self.__schedule_request()
        self.__reschedule_retry_watchdog()


    def __schedule_request(self):
        self.__tracer.debug("scheduling request")
        sample_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")
        self.__xbee_manager.xbee_device_schedule_after(
            sample_rate_ms / 1000, self.make_request)


    def __reschedule_retry_watchdog(self):
        self.__tracer.debug("__reschedule_retry_watchdog")
        sample_rate_ms = SettingsBase.get_setting(self, "sample_rate_ms")
        try:
            if self.__retry_event:
                self.__xbee_manager.xbee_device_schedule_cancel(
                    self.__retry_event)
        except:
            pass

        self.__retry_event = \
            self.__xbee_manager.xbee_device_schedule_after(
                sample_rate_ms * 1000 * 1.5, self.retry_request)


    def retry_request(self):
        self.__tracer.debug("retry request.")
        self.make_request()
        self.__reschedule_retry_watchdog()

    def running_indication(self):
        # Go retrieve the current samples manually.
        # NOTE: make_request queues up the next poll.
        self.make_request()


    def sample_indication(self, buf, addr):
        self.__tracer.info("Got sample indication from: %s, buf is len %d.",
                           str(addr), len(buf))
        self.__decode_sample(buf)

    def __decode_sample(self, buf):
        io_sample = parse_is(buf)

        for io_pin in range(4):
            key = 'DIO%d' % self.INPUT_CHANNEL_TO_PIN[io_pin]
            if io_sample.has_key(key):  
                val = bool(io_sample[key])
                name = "channel%d_input" % (io_pin+1)
                try:
                    self.property_set(name,  Sample(0, val, "bool"))
                except:
                    pass

    def set_output(self, sample, io_pin):
        new_val = False
        try:
            new_val = bool(sample.value)
        except:
            pass

        ddo_val = self.DIO_MODE_OUTPUT_LOW
        if new_val:
            ddo_val = self.DIO_MODE_OUTPUT_HIGH

        try:
            digihw.configure_channel(io_pin, ddo_val)
        except:
            self.__tracer.error("Error setting output '%s'", str(e))

        property = "channel%d_output" % (io_pin + 1)
        self.property_set(property, Sample(0, new_val, "bool"))


    def update(self, channel, io_pin):
        sample = channel.get()
        self.set_output(sample, io_pin)



# internal functions & classes

