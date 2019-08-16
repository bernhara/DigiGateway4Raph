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

"""\
    The XBee sensor interface base class.

    All XBee sensor drivers in DIA should derive from this class.

"""

# imports
from core.tracing import get_tracer
import devices.xbee.common.bindpoints as bindpoints
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.ddo import GLOBAL_DDO_TIMEOUT


# constants

# exception classes

# interface functions


# classes
class XBeeBase(DeviceBase):

    """\
        Defines the XBee Interface base class.

        Keyword arguments:
            * **name:** the name of the device instance.
            * **core_services:** the core services instance.
            * **settings:** the list of settings.
            * **properties:** the list of properties.

    """
    # Define a set of default endpoints that devices will send in on.
    # When a XBee Node Joins our network, it will come in on 0x95.
    ADDRESS_TABLE = [bindpoints.JOIN]

    # Empty list of supported products.
    SUPPORTED_PRODUCTS = []

    def __init__(self, name, core_services, settings, properties):

        # DeviceBase will create:
        # self._name, self._core, self._tracer,

        self._xbee_manager = None
        self._extended_address = None

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='xbee_device_manager', type=str, required=True),
            Setting(
                name='extended_address', type=str, required=True),
        ]

        # Add our settings_list entries into the settings passed to us.
        settings = self.merge_settings(settings, settings_list)

        ## Channel Properties Definition:
        property_list = [

        ]

        # Add our property_list entries into the properties passed to us.
        properties = self.merge_properties(properties, property_list)

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, name, core_services, settings, properties)

        self._tracer.calls("XBeeBase.__init__()")

    # use DeviceBase.apply_settings(self)

    def start(self):
        """\
            Start the device driver.
        """
        self._tracer.calls("XBeeBase.start()")

        # Indicate that we have no more configuration to add:
        self._xbee_manager.xbee_device_configure(self)

        return DeviceBase.start(self)


    def pre_start(self):
        """\
            Do initial base class set up required before start, such as
            initialize self._xbee_manager and self._extended_address
        """
        
        if self._xbee_manager is None:
            # then initialize things
            
            self._tracer.calls("XBeeBase.pre_start()")

            # Fetch the XBee Manager name from the Settings Manager:
            dm = self._core.get_service("device_driver_manager")
            self._xbee_manager = dm.instance_get(
                    SettingsBase.get_setting(self, "xbee_device_manager"))

            # Register ourselves with the XBee Device Manager instance:
            self._xbee_manager.xbee_device_register(self)

            # Get the extended address of the device:
            self._extended_address = SettingsBase.get_setting(self, "extended_address")

            # Create a callback specification that calls back this driver when
            # our device has left the configuring state and has transitioned
            # to the running state:
            xbdm_running_event_spec = XBeeDeviceManagerRunningEventSpec()
            xbdm_running_event_spec.cb_set(self.running_indication)
            self._xbee_manager.xbee_device_event_spec_add(self,
                                                    xbdm_running_event_spec)

        # else do nothing
        
        return


    def stop(self):
        """\
            Stop the device driver.
        """
        self._tracer.calls("XBeeBase.stop()")

        # Unregister ourselves with the XBee Device Manager instance:
        if self._xbee_manager is not None:
            self._xbee_manager.xbee_device_unregister(self)

        self._xbee_manager = None
        self._extended_address = None

        return DeviceBase.stop(self)

    @staticmethod
    def probe():
        """\
            Collect important information about the driver.

            .. Note::

                This method is a static method.  As such, all data returned
                must be accessible from the class without having a instance
                of the device created.

            Returns a dictionary that must contain the following 2 keys:
                    1) address_table:
                       A list of XBee address tuples with the first
                       part of the address removed that this device
                       might send data to.  For example: [ bindpoints.JOIN ]
                       See 'devices/xbee/common/bindpoints.py' for details.

                    2) supported_products:
                       A list of product values that this driver supports.
                       Generally, this will consist of Product Types that
                       can be found in 'devices/xbee/common/prodid.py'

        """

        probe_data = dict(address_table=[], supported_products=[])

        for address in XBeeBase.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeBase.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    def running_indication(self):
        """
            Indicate that we have completed config and are running
        """
        self._tracer.info("Configuration is Complete. Running indication.")
        return

    def ddo_get_param(self, param,
                        timeout=GLOBAL_DDO_TIMEOUT, use_cache=False):
        '''
        Chain DDO GET to our Xbee Manager with our addrress

        '''
        return self._xbee_manager.xbee_device_ddo_get_param(
                    self._extended_address, param, timeout, use_cache)

    def ddo_set_param(self, param, value,
                       timeout=GLOBAL_DDO_TIMEOUT, order=False, apply=False):
        '''
        Chain DDO GET to our Xbee Manager with our addrress

        '''
        return self._xbee_manager.xbee_device_ddo_set_param(
                    self._extended_address, param, value, timeout,
                    order, apply)

    def xbee_device_config_block_add(self, instance, config_block):
        '''
        Chain to our Xbee Manager
        '''
        return self._xbee_manager.xbee_device_config_block_add(instance, config_block)
                    
# internal functions & classes
