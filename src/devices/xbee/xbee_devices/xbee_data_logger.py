############################################################################
#                                                                          #
# Copyright (c)2011, Digi International (Digi). All Rights Reserved.       #
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
DIA XBee data logger.

This driver listens to incoming data.

It logs size of data to INFO and data itself to DEBUG.

This is used for testing.
'''

# imports
from core.tracing import get_tracer
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase
from channels.channel_source_device_property import *
from common.types.boolean import Boolean, STYLE_ONOFF
import devices.xbee.common.bindpoints as bindpoints
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *
from devices.xbee.common.io_sample import parse_is
from devices.xbee.common.prodid import PROD_DIGI_XB_ADAPTER_RS232, \
    PROD_DIGI_XB_ADAPTER_RS485

class XBeeDataLogger(XBeeBase):
    '''
    Test device.
    '''
    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [bindpoints.SERIAL, bindpoints.SAMPLE]

    # The list of supported products that this driver supports.

    # (I'm cheating here... any digi product should work!)
    SUPPORTED_PRODUCTS = range(0x1a)

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        self.__tracer = get_tracer(name)
        self.__xbee_manager = None

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, self.__name, self.__core, [], [])

    def start(self):
        xbee_manager_name = SettingsBase.get_setting(self,
                                                     "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Get the extended address of the device:
        extended_address = SettingsBase.get_setting(self, "extended_address")

        self.__xbee_manager.xbee_device_register(self)

        ddo_block = self.__xbee_manager.get_ddo_block(extended_address)
        sleep_block = self.__xbee_manager.get_sleep_block(extended_address,
                                                          sleep=True)

        self.__xbee_manager.xbee_device_config_block_add(self, ddo_block)
        self.__xbee_manager.xbee_device_config_block_add(self, sleep_block)

        self.__xbee_manager.register_serial_listener(self,
                                                 extended_address,
                                                 self.__read_callback)

        self.__xbee_manager.register_sample_listener(self, extended_address,
                                                     self.__read_callback2)
        self.__xbee_manager.xbee_device_configure(self)

        return True

    def stop(self):
        return True

    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # there were problems with settings, terminate early:
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

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

        probe_data = XBeeBase.probe()

        for address in XBeeDataLogger.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeDataLogger.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    def __read_callback(self, data, addr):
        self.__tracer.info('got %d bytes from profile 0xc105, ' \
                           'cluster 17 %s', len(data), addr)
        self.__tracer.debug(str(data))

    def __read_callback2(self, data, addr):
        self.__tracer.info('got %d bytes from profile 0, ' \
                           'cluster 146 %s', len(data), addr)
        self.__tracer.debug(str(data))
