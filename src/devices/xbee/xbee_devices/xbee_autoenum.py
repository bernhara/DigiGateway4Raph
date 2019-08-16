############################################################################
#                                                                          #
# Copyright (c)2009-2012, Digi International (Digi). All Rights Reserved.  #
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
A DIA Driver for Discovering and Auto Enumerating XBee Devices.

   Instead of defining an exact collection of DIA devices with fixed XBee MAC
   addresses, the user lists the type of adapters to support and their default
   configurations.  This driver then automatically imports and configures new
   adapters as seen on the XBee network.

   Device names default to the NI (node identifier) of the XBee.  If this value
   is not set or unavailable, then the device name shall be like
   'tag_[00:13:a2:00:40:52:e0:fc]!', where 'tag' is the string defined in the
   'devices' portion of the settings file as 'name: tag'

   While the driver runs, it will periodically issue an XBee discover out
   to the XBee network, attempting to find new devices to Auto-Enumerate.
   It will also listen into XBee traffic inbound in to the Gateway,
   and if it detects any traffic that any of the given devices set up might
   send in on, it will check to see if it is a new device, and if so, attempt
   to configure the device into DIA.

"""

# imports
import traceback
from copy import deepcopy

import threading
import Queue
import digitime

from settings.settings_base \
    import SettingsBase, Setting, SettingNotFound
from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_base import XBeeBase

from devices.xbee.common.prodid import parse_dd, product_name
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import XBeeDeviceManagerRxEventSpec
from devices.xbee.common.addressing import normalize_address

try:
    import xbee
except:
    import zigbee as xbee

# constants

# exception classes

# interface functions


# classes
class XBeeAutoEnum(DeviceBase, threading.Thread):
    """\
        XBee Auto Enumeration class.

        Keyword arguments:

        * **name:** the name of the device instance.
        * **core_services:** the core services instance.

    """
    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Local State Variables:
        self.__xbee_manager = None
        self.__settings_ctx = \
                    core_services.get_service("settings_base").get_context()
        self.__purgatory = []
        self.__callbacks = []

        ## Settings Table Definition:

        settings_list = [
            Setting(
                name='xbee_device_manager', type=str, required=True),

            # Contains the device driver settings for every device
            # that is intended to be auto enumerated.
            # The 'name: tag' is used as part of the new device name
            Setting(name='devices', type=dict, required=True,
                    default_value=[]),

            Setting(
                name='discover_rate', type=int, required=False,
                default_value=600,
                verify_function=lambda x: x >= 60 and x <= 86400),

            # Shortens the discovered device names, when NI is not used,
            # to only include the last two octets of the XBee MAC Address.
            # User must confirm uniqueness of these 2 octets.
            # Example: 'aio_[00:13:a2:00:40:52:e0:fc]!'
            # becomes just 'aio_E0_FC'
            Setting(name='short_names', type=bool, required=False,
                    default_value=False),
        ]

        ## Channel Properties Definition:
        property_list = [

        ]

        self.__add_device_queue = Queue.Queue()

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):
        """\
            Called when new configuration settings are available.

            Must return tuple of three dictionaries: a dictionary of
            accepted settings, a dictionary of rejected settings,
            and a dictionary of required settings that were not
            found.

        """
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
        """\
            Start the device driver.

            Returns True if the driver has been correctly started.
            Returns False if the driver has failed to be started.

        """
        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self,
                                                     'xbee_device_manager')
        dm = self.__core.get_service('device_driver_manager')
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        device_settings_list = self.get_setting('devices')
        try:
            device_settings_list = device_settings_list['instance_list']
        except:
            device_settings_list = []

        address_endpoints_to_watch = []
        self._auto_device_list = []
        for dev in device_settings_list:
            try:
                # Tell the device manager to load the driver into memory.
                dm.driver_load(dev['driver'])
                try:
                    obj = dm.get_service(dev['driver'])
                except Exception, e:
                    self.__tracer.error('Couldn\'t load driver: %s', str(e))
                    obj = None

                if obj != None:
                    try:
                        probe_data = obj.probe()
                        products = probe_data['supported_products']
                        address_table = probe_data['address_table']
                    except Exception, e:
                        self.__tracer.error('Couldn\'t probe driver: %s',
                                            str(e))
                        self.__tracer.debug(traceback.format_exc())
                        products = []
                        address_table = []
                else:
                    products = []
                    address_table = []

                # map the address_table into values for this xbee manager
                address_table = map(self.__xbee_manager.get_bindpoint,
                                    address_table)

                # Add the device address endpoints to our list of
                # "addresses to watch" for later use.
                for ep in address_table:
                    if ep not in address_endpoints_to_watch:
                        address_endpoints_to_watch.append(ep)

                # Now go and add a couple default settings that weren't
                # required as config options.
                if 'settings' not in dev or dev['settings'] == None:
                    dev['settings'] = {}

                if 'xbee_device_manager' not in dev['settings']:
                    dev['settings']['xbee_device_manager'] = xbee_manager_name

                if 'extended_address' not in dev['settings']:
                    dev['settings']['extended_address'] = ""

                entry = dict(userdata=dev, supported_products=products)
                self._auto_device_list.append(entry)

            except Exception, e:
                self.__tracer.error('Problem in start(): %s', str(e))

        # Create a callback specification for our device address, endpoints...
        for endpoint in address_endpoints_to_watch:
            # TODO: genericize this... currently depends on the fact that
            #       an address endpoint has 3 elements. (This will change
            #       once we support more that ZigBee and DigiMesh.)
            xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
            xbdm_rx_event_spec.cb_set(self.__sample_indication)
            self.__tracer.info("XBeeAutoEnum: Adding endpoint ('[*]!', "
                               "%s to watch", endpoint)
            xbdm_rx_event_spec.match_spec_set(("00:00:00:00:00:00:00:00!",
                                               endpoint['endpoint'],
                                               endpoint['profile_id'],
                                               endpoint['cluster_id']),
                    (False, True, True, True))
            self.__xbee_manager.xbee_device_event_spec_add(self,
                    xbdm_rx_event_spec)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        threading.Thread.start(self)
        return True

    def stop(self):
        """\
            Stop the device driver.

            Returns True if the driver has been correctly stopped.
            Returns False if the driver has failed to be stopped.

        """
        # Tell our discover thread to stop.
        self.__stopevent.set()
        return True

    def run(self):
        """\
            Runs the device driver.

            The main function of this driver.
            It shall run forever until it is told to stop by the stop function.

        """
        self.__tracer.info("XBeeAutoEnum: discover_thread start")

        discover_rate = SettingsBase.get_setting(self, "discover_rate")

        # Schedule the last discover time such that we will do our first
        # discover on the network 3 minutes after we started.
        # This allows the DIA to stabilize, configure any static XBee devices
        # and have things settle down a bit.
        last_discover_time = digitime.real_clock() - discover_rate + 180

        while True:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break

            # Check to see if we should do a network discover.
            if last_discover_time + discover_rate <= digitime.real_clock():
                try:
                    self.__discover_poll()
                except:
                    # Any exceptions taken here are not a problem.
                    # We will pick up any new devices next poll cycle.
                    pass
                last_discover_time = digitime.real_clock()

            # Try to a get a new device from the Queue, blocking for
            # up to 5 seconds.
            try:
                addr = self.__add_device_queue.get(True, 5.0)
            except Queue.Empty:
                continue

            if addr != None:
                already_in = self.__check_if_device_is_already_in_system(addr)
                if already_in == False:
                    self.__add_new_device(addr)
            else:
                digitime.sleep(1)

        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)
        self.__tracer.info("XBeeAutoEnum: discover_thread end")

    def __discover_poll(self):
        self.__tracer.info("XBeeAutoEnum: __discover_poll start")

        node_list = {}

        # Do Inital scan of XBee network...
        self.__tracer.info("XBeeAutoEnum: Please wait while any/all " +
                           "units are being discovered...")

        # Perform a node discovery:
        try:
            node_list = self.__xbee_manager.xbee_get_node_list(
                        refresh=True, clear=False)
        except Exception, e:
            self.__tracer.error("XBeeAutoEnum: Exception in get_node_list. " +
                                "%s: %s ",
                                e.__class__, str(e))
            node_list = None

        self.__tracer.info("XBeeAutoEnum:          Interface" +
                           "                      Hardware Address")
        self.__tracer.info("XBeeAutoEnum: ------------------------------" +
                           "    --------------------------")

        n = 0

        if node_list != None:
            for node in node_list:
                if node.type == 'coordinator':
                    continue

                already_in = self.__check_if_device_is_already_in_system(
                             node.addr_extended)
                if already_in == False:
                    self.__tracer.info("XBeeAutoEnum: "
                                       "discover_thread enqueue: %s",
                                       (node.addr_extended))
                    self.__add_device_queue.put(node.addr_extended)
                    # Uncomment when we go to Python 2.5+
                    # self.__add_device_queue.task_done()

    def add_new_device_callback(self, cbfnc):
        """\
        Any time a new device seen, notify other DIA modules. Single tuple is
        passed to callback with (name, product_type, product_name, ext_address)
        so for example: ('ain_cf_7d', 11L, 'Digi XBee Analog I/O Adapter',
                         '[00:13:a2:00:40:4e:cf:7d]!')

        Callbacks are kept in list, so any number from any source supported.

        # example usage::
          try:
              dm = self.__core.get_service("device_driver_manager")
              aenum = dm.instance_get("xbee_autoenum")
              aenum.add_new_device_callback(self.refresh_lists)
          except:
              traceback.print_exc()
        """
        self.remove_new_device_callback(cbfnc)
        self.__callbacks.append(cbfnc)

    def remove_new_device_callback(self, cbfnc):
        """Stop notifying a particular DIA module. No error if not found"""
        try:
            self.__callbacks.remove(cbfnc)
        except:
            # traceback.print_exc()
            pass

    def __sample_indication(self, buf, addr):
        # print "XBeeAutoEnum: Got sample indication from: %s, buf is
        # len %d." % (str(addr), len(buf))
        already_in = self.__check_if_device_is_already_in_system(addr[0])
        if already_in == False:
            self.__add_device_queue.put(addr[0])
            # Uncomment when we go to Python 2.5+
            # self.__add_device_queue.task_done()

    def __generate_running_xbee_devices_list(self):
        """\
            Create a list of the Device Objects running on the system.

        """
        dm = self.__core.get_service("device_driver_manager")
        instance_list = dm.instance_list()
        device_list = []
        for device in instance_list:
            obj = dm.instance_get(device)
            # Only add XBee-based devices to our list.
            if isinstance(obj, XBeeBase):
                device_list.append(obj)
        #print device_list
        return device_list

    def __check_if_device_is_already_in_system(self, new_address):
        """\
            Attempt to determine if the detected device is already
            configured or in purgatory.

            Parameters:
                * **new_address**: The XBee address of the new device.

            Return type:
                * bool

        """
        device_list = self.__generate_running_xbee_devices_list()

        # Search the device list to see if this is a device
        # we already know about...
        for device in device_list:
            try:
                existing_address = device.get_setting('extended_address')
            except Exception, e:
                # print e
                # print device
                continue

            if existing_address == None or existing_address == '':
                continue

            new_address = normalize_address(new_address)
            existing_address = normalize_address(existing_address)
            if existing_address == new_address:
                #print "XBeeAutoEnum:
                #      __check_if_device_is_already_in_system -"\ "
                #      DUPLICATE %s not re-adding." % (new_address)
                return True

        # Now walk through purgatory, and see if the device is listed in there.
        # If so, return True so that the system won't attempt to add it.
        for entry in self.__purgatory:
            if entry['extended_address'] == new_address:
                #print "XBeeAutoEnum:
                #      __check_if_device_is_already_in_system -"\ "
                #      DEVICE IN PURGATORY %s not re-adding." %
                #      (new_address)
                return True

        return False

    def __create_name(self, default_name, address, node_identifier):
        """\
            Create a new DIA name for this device.
        """

        # Only use the NI value if its not empty, or isn't just a single space.
        if node_identifier != "" and node_identifier != " ":
            # Walk the device list, to make sure we don't add a
            # duplicate name...
            count = 0
            device_list = self.__generate_running_xbee_devices_list()
            for i in device_list:
                l = len(node_identifier)
                if i.get_name()[0:l] == node_identifier:
                    count += 1
            if count == 0:
                name = node_identifier
            else:
                name = (node_identifier + " #" + str(count))
        else:
            if (SettingsBase.get_setting(self, 'short_names')):
                # then short name like 'aio_E0_FC'
                try:
                    # [00:13:a2:00:40:0a:06:c6]!
                    # 012345678901234567890123456789
                    # 0         1         2
                    name = '%s_%s_%s' % (default_name, address[19:21],
                                         address[22:24])
                except:
                    name = (default_name + "_" + address)
            else:
                # else long name like 'auto_aio_[00:13:a2:00:40:52:e0:fc]!'
                name = (default_name + "_" + address)

        return name

    def __get_device_data(self, address):

        product_type = None
        node_identifier = None

        try:
            device_data = self.__xbee_manager.xbee_device_ddo_get_param(\
                                 address, 'DD', use_cache=True)
        except:
            # On any exceptions, just bail.
            # The next discovery we will take another crack at it.
            self.__tracer.warning(('XBeeAutoEnum: __add_new_device. '
                                   'UNABLE to get DD from %s.'), address)
            return product_type, node_identifier

        _, product_type = parse_dd(device_data)

        # Now ask the device what its Node Identification is.
        try:
            node_identifier = self.__xbee_manager.xbee_device_ddo_get_param(\
                                     address, 'NI', use_cache=True)
        except:
            # On any exceptions, just bail.
            # The next discovery we will take another crack at it.
            self.__tracer.warning('XBeeAutoEnum: __add_new_device. '
                                  'UNABLE to get NI from %s.', address)
            return product_type, node_identifier

        return product_type, node_identifier

    def __banish_device_to_purgatory(self, product_type, extended_address):
        """\
            If a device is not responding, not responding correctly,
            or has no default configuration set up in DIA, then we cannot
            do anything with it.
            In these cases, we shouldn't attempt to continue to try to
            configure or use the device.
            So instead, let us banish it into a purgatory list.

        """
        #print "XBeeAutoEnum: BANISHING DEVICE INTO PURGATORY: %s" % \
        #                                                 (extended_address)
        entry = dict(product_type=product_type,
                     extended_address=extended_address)
        self.__purgatory.append(entry)

    def __add_new_device(self, new_extended_address):

        already_in_system = self.__check_if_device_is_already_in_system(
                          new_extended_address)
        if already_in_system == True:
            return

        # Device is new, and one we didn't have already configured in the
        # config file.  Ask the device what it is...
        product_type, node_identifier = self.__get_device_data(\
                                        new_extended_address)

        if node_identifier == None:
            # if NI is truly NULL, make empty-string instead
            node_identifier = ''

        # If we were unable to get important data about the device, bail early.
        # The next discovery we will take another crack at it.
        if product_type == None:
            return

        self.__tracer.info("XBeeAutoEnum: New Device Found: %-s%s%-s%s%-s",
                           product_name(product_type), " " * 4,
                           new_extended_address, " " * 4, node_identifier)

        instance_settings = None
        for dev in self._auto_device_list:
            if product_type in dev['supported_products']:
                instance_settings = deepcopy(dev['userdata'])
                break
        else:
            # If there is no default config for this device, there is
            # no reason to keep attempting to configure it the next
            # time we see it.
            #
            # So we will commit this device to a purgatory bin, in which
            # the device will remain until a later time, in which we might
            # have a new DIA config inserted into the running state of the
            # system that would provide us a default config.

            self.__tracer.warning("XBeeAutoEnum: No Default Config Found.")
            self.__banish_device_to_purgatory(product_type,
                                              new_extended_address)
            return

        if instance_settings == None:
            # If there is no instance settings for this device, there is no
            # reason to keep attempting to configure it the next time
            # we see it.
            #
            # So we will commit this device to a purgatory bin, in which
            # the device will remain until a later time, in which we might
            # have a new DIA config inserted into the running state of the
            # system that would provide us correct instance settings.
            entry = dict(product_type=product_type,
                         extended_address=new_extended_address)
            self.__purgatory.append(entry)
            return

        # Go create a custom name derived from the address and node identifier.
        name = self.__create_name(instance_settings['name'],
                    new_extended_address, node_identifier)
        instance_settings['name'] = name

        # Replace the extended address with our custom versions.
        instance_settings['settings']['extended_address'] = \
                                                          new_extended_address

        # Get the current instance list for the devices binding:
        self.__settings_ctx.set_current_binding(("devices", ))
        self.__settings_ctx.pending_instance_list_append(instance_settings)

        # Now attempt to start the new device, if it already hasn't been done.
        try:
            dm = self.__core.get_service("device_driver_manager")
            dm.driver_load(instance_settings['driver'])
            if instance_settings['name'] not in dm.instance_list():
                dm.instance_new(instance_settings['driver'],
                                instance_settings['name'])
                dm.instance_start(instance_settings['name'])

        except Exception, e:
            self.__tracer.error("XBeeAutoEnum: Exception during " +
                                 "driver load. %s: %s ",
                                e.__class__, str(e))
            self.__tracer.debug(traceback.format_exc())

            # If starting the instance failed, try to determine if the
            # failure was because the settings were bad, missing or
            # simply incorrect.
            # If they are, then there is no reason to attempt
            # configure the device again if/when it gets
            # discovered again.  So banish this device instance
            # to purgatory until the user fixes the settings they
            # gave us for the device.
            if e.__class__ == SettingNotFound or e.__class__ == ValueError:
                self.__banish_device_to_purgatory(product_type,
                                              new_extended_address)

            # Now attempt to remove the driver from DIA.
            # It is not harmful if it is unable to be removed.
            try:
                dm.instance_remove(instance_settings['name'])
            except Exception, e:
                self.__tracer.error('%s', str(e))

        # If here, then notify any DIA modules interested
        dat = (name, product_type, product_name(product_type),
               new_extended_address)
        for cbfnc in self.__callbacks:
            try:
                cbfnc(dat)
            except:
                self.__tracer.warning('XBeeAutoEnum: clients callback failed')
                self.__tracer.debug(traceback.print_exc())
