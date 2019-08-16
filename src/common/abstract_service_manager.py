############################################################################
#                                                                          #
# Copyright (c)2008, 2009, Digi International (Digi). All Rights Reserved. #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,  and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. ContactProduct Management, Digi International, Inc., 11001 Bren    #
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

"""
An implementation of an abstract modular dynamic class loading service.

The :class:`AbstractServiceManager` is used to implement several core system
services including the :class:`DeviceDriverManager`,
:class:`LoggingManager`, :class:`PresentationManager`, and others.  The
:class:`AbstractServiceManager` defines an interface for these services to
conform to as well as implement several helper functions to facilitate the
dynamic loading of module code, start and stop class instances, and manage
child services.
"""

# imports
import traceback

from common.classloader import classloader
from settings.settings_base import SettingsBase, Setting

# constants

# exception classes
class ASMClassLoadError(Exception):
    pass

class ASMClassNotFound(Exception):
    pass

class ASMInstanceError(Exception):
    pass

class ASMInstanceNotFound(Exception):
    pass

class ASMInstanceCannotStop(Exception):
    pass

# interface functions

# internal functions

# classes
class AbstractServiceManager(SettingsBase):
    def __init__(self, core, settings_binding, additional_settings=None):
        """
        Creates a new :class:`AbstractServiceManager` instance.

        `core` must be a reference to the core service manager
        (see :mod:`~src.core.core_services`).

        `settings_binding` must be a valid settings binding tuple.  This
        determines at what point in the settings registry the service
        will locate and receive its settings.  If we wished to create a
        service manager which received its settings in a binding off the
        registry root called "devices" the `settings_binding` would be
        given as a one element tuple ('devices',).

        `additional_settings` is a list of :class:`Setting` objects
        which define additional settings, aside from the implied instance
        list that all :class:`AbstractServiceManager` instances have.
        """
        if additional_settings == None:
            additional_settings = []

        # Core reference:
        self._core = core
        # Maps instance name (str) -> service instance (object)
        self._name_instance_map = {}
        # Maps service name (str) -> service instance (object)
        self._loaded_services = {}

        from core.tracing import get_tracer
        self.__tracer = get_tracer('AbstractServiceManager')

        # Initialize settings infrastructure:
        settings_list = [
            Setting(
                name='instance_list', type=list, required=False,
                default_value=[]),
        ]
        settings_list.extend(additional_settings)

        SettingsBase.__init__(self, binding=settings_binding,
                              setting_defs=settings_list)

    def apply_settings(self):
        """
        Apply new settings on this abstract service manager instance.

        This function is called by the settings sub-system when there are
        new settings available.  This method may be overridden.  The
        default implementation accepts all settings and then calls the
        local private function self._reenumerate_services() in order to
        start new services.  Changes in settings are then committed
        to the settings running registry.
        """
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        self._reenumerate_services()

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def _reenumerate_services(self):
        """
        Starts new services found in the pending setting registry's
        "instance_list" setting.

        If a new service is found it determines which driver is needed
        and loads the driver dynamically if it has not been loaded already.
        The instance is then created and started.

        This function does not yet handle the dynamic stopping of system
        services.
        """
        try:
            services = SettingsBase.get_pending_setting(self, "instance_list")
        except:
            # no instances found
            return

        service_names = set()
        for service in services:
            if "driver" in service and "name" in service:
                if service['name'] in service_names:
                    self.__tracer.error("Duplicate item: %s", service['name'])
                    raise KeyError

                if not self._service_loaded(service["driver"]):
                    self.service_load(service["driver"])
                if not self.instance_exists(service["name"]):
                    self.instance_new(service["driver"], service["name"])
                    self.instance_start(service["name"])

                service_names.add(service['name'])

    def get_service(self, classname):
        """."""
        if classname not in self._loaded_services:
            raise ASMClassNotFound("service '%s' not loaded." % (classname))
        return self._loaded_services[classname]

    def _service_loaded(self, name):
        """Determines if a service driver module has been loaded yet."""
        return name in self._loaded_services

#     def service_add(self, name, filename):
#          """Extend the services known to the system."""
#          self._service_map[name] = filename

    def service_load(self, name):
        """
        Loads a service dynamically.

        If the service has not been loaded previously, an unconfigured
        instance of the service will be created and managed by the
        AbstractServiceManager.  If the service has already been loaded
        nothing will be done.  In either case, this function will
        return True.

        If the service cannot be loaded for any reason, an exception
        will be raised.
        """
        if name in self._loaded_services:
            return True

        try:
            module_path, class_name = name.split(':')
        except:
            raise ASMClassLoadError("Invalid driver syntax, must " \
                                    "be path.to.file:ClassName")

        # attempt to load the service:
        service_class = None
        self.__tracer.info("loading '%s' from '%s'", class_name,
                           module_path)
        try:
            service_class = classloader(module_path, class_name)
        except Exception, e:
            self.__tracer.error("Exception during dynamic class " +
                                "load: %s", traceback.format_exc())
            raise ASMClassLoadError("unable to load '%s': %s:%s" % (
                name, e.__class__, str(e)))

        self._loaded_services[name] = service_class

        return True

    def instance_exists(self, instancename):
        """Determines if a named instance already exists."""
        return instancename in self._name_instance_map

    def instance_get(self, instancename):
        """Method to find a given service instance by `instancename`."""
        if not self.instance_exists(instancename):
            raise ASMInstanceNotFound("service instance named '%s'" \
                                      "does not exist." % (instancename))

        return self._name_instance_map[instancename]

    def instance_new(self, classname, instancename):
        """Create a new instance of a loaded service class."""

        if classname not in self._loaded_services:
            raise ASMClassNotFound("service '%s' not loaded." % (classname))

        if self.instance_exists(instancename):
            raise ASMInstanceError("service instance name '%s' already " \
                                   "exists." % (instancename))

        # Create a new instance and store it by instance name:
        service_class = self._loaded_services[classname]
        service_instance = service_class(name=instancename,
                                        core_services=self._core)
        self._name_instance_map[instancename] = service_instance

        return True

    def instance_list(self):
        """Returns a list of all service instances."""
        return [name for name in self._name_instance_map]

    def instance_settings_get(self, instancename):
        """Get the settings of a given service instance."""
        service_instance = self.instance_get(instancename)
        return service_instance.get_settings()

    def instance_setting_set(self, instancename, settingname, settingvalue):
        """
        Set a setting on a given instance name, the setting will go
        into the instance's pending settings registry.
        """
        service_instance = self.instance_get(instancename)
        service_instance.set_pending_setting(settingname, settingvalue)
        return True

    def instance_settings_apply(self, instancename):
        """Apply all pending settings on a given instance."""
        service_instance = self.instance_get(instancename)
        return service_instance.apply_settings()

    def instance_properties_get(self, instancename):
        """Get the properties of a given service instance."""
        service_instance = self.instance_get(instancename)
        return service_instance.get_properties()

    def instance_start(self, instancename):
        """
        Start a given service instance by `instancename`.

        Service instances are started by calling their start() method.
        """
        service_instance = self.instance_get(instancename)
        return service_instance.start()

    def instance_stop(self, instancename):
        """
        Stop a given service instance by `instancename`.

        Service instances are stopped by calling their stop() method.
        """
        service_instance = self.instance_get(instancename)

        # this is possible if we died early in system startup
        if service_instance == None:
            return True
        return service_instance.stop()

    def instance_remove(self, instancename):
        """
        Remove a given service instance by `instancename`.

        The instance will first attempted to be stopped before being removed.
        If the instance does not exist ASMInstanceNotFound will be raised.
        If the service instance signaled that it cannot be stopped (i.e. False
        was returned from the instance's stop() method) ASMInstanceCannotStop
        will be raised.

        If the instance raises an exception, the exception will be propagated.

        If an any exception is raised, the service instance will not be
        removed.

        Removing the last instance loaded driver will not result in the
        service instance's driver to be unloaded from memory.
        """

        if not self.instance_exists(instancename):
            raise ASMInstanceNotFound

        # Try to stop it, if its still running.
        if not self.instance_stop(instancename):
            raise ASMInstanceCannotStop("cannot stop %s" % (instancename))
        # Remove it.
        del self._name_instance_map[instancename]
