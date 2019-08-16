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

"""
The settings base class.

Any objects in the system that wish to have their settings serialized
in the system-standard way should inherit from the
:class:`SettingsBase` class which is defined in this module.

Regardless of the serialization used, the configuration files consist
of a tree-like representation of the settings specified for the
system.  The following sections will attempt to introduce some
concepts and internal representation used by the :class:`SettingsBase`
and :class:`SettingsContext` classes.

.. _instance_lists:

Instance Lists
====================

The tree-like representation of the settings specified by the
configuration files can have branches specified essentially as
`dictionary` or `sequence` types.  Traversing a dictionary of
dictionaries can be done by specifying only the keys used to perform
the traversal.  However, sequences can have multiple alternate meaning
as a portion of the settings tree.

One meaning is that of a leaf setting.  The sequence itself is
intended to be consumed as an entire setting by the
:class:`SettingsBase` object that will consume it.  Examples of this
include the `channels` setting in the
:doc:`iDigi DB </user/presentations/idigi_db>` presentation or the
`exclude` settings of the :doc:`Embedded Web
</user/presentations/embedded_web>` presentation.

However, for convenience and cleanliness of the saved representation,
some sequences are really better located by a symbolic key rather than
as a complete sequence.  This is where the settings infrastructure of
the system introduces the concept of an *instance list*.

During the translation of a serialized representation into the
run-time representation, the settings code recognizes sequences of
dictionaries in the settings tree where the dictionaries have a `name`
key and converts them to a modified form.  This modified form is
inserted into the run-time representation of the settings as an
`instance_list` setting.  This allows for the list to be retrieved by
name the same as all other settings in the system and provides a
consistent means to specify a path for settings traversal to deeper
nodes of the settings tree.

Some drivers may wish to access this list as a whole; for example the
:doc:`Transforms </user/devices/transforms>` device retrieves its
entire settings block as an instance list for additional processing.

Most of the time however, these instance lists act as a convenience
for traversing the tree by specifying the traversal as a :ref:`binding
<bindings>`

.. _bindings:

Bindings
====================

A :class:`SettingsBase` binding is a sequence.  Each element of
the sequence specifies a path in the settings registry that can be
used to locate a sub-tree of the whole.

Strings at the top level of the binding sequence select a literal
string specified path in the settings.  These are items that are
specified as dictionary keys in the settings serialization.  Examples
are the top-level `devices`, `services`, `presentations` or `loggers`
keys used to organize the configuration file or the `settings` key
present for the standard representation of the top level settings
block of each component.

If the top level of the binding sequence is also a sequence, this is
used to identify the member of an :ref:`instance_list
<instance_lists>`.

Example
--------------------
Consider the following very simple YAML document

dia.yml::

  devices:
  - name: template
    driver: devices.template_device:TemplateDevice
    settings:
        update_rate: 5.0

To locate the settings for the template device on the settings tree,
the following binding would be used::

  ('devices', ('template',), 'settings')

Thankfully, in most instances, bindings will be managed by the system.


"""

# imports
import sys, traceback
from copy import copy, deepcopy
from threading import RLock

# constants
REG_PENDING = 0
REG_RUNNING = 1

# exception classes
class SettingNotFound(KeyError):
    """Exception thrown when a setting cannot be found in the registry"""
    pass

class SettingBindingDefinitionError(AttributeError):
    """Exception thrown when an invalid settings binding is specified"""
    pass

class SettingsRegistryError(Exception):
    """Generic exception on errors interacting with the Settings registry"""
    pass

# interface functions

# classes
class Setting:
    """
    Represents a single setting in the Settings registry

    Keyword arguments:

    * **name:** the name of the configuration item
    * **type:** a type constructor to create the item from a string
    * **parser:** a function to convert any given value to a value of
      the setting type or raise an exception on failure
    * **required:** bool specifying if this option is required
      (default False)
    * **default_value:** the default value for this item (default
        None)
    * **verify_function:** a function to call to verify this item
      after it has been created.

    """
    def __init__(self, name, type, parser=None, required=False,
                    default_value=None, verify_function=lambda i: True):
        self.name = name
        self.type = type
        self.parser = parser
        self.required = required
        self.default_value = default_value
        self.verify_function = verify_function

    def try_value(self, value):
        """
        Internal helper function

        `try_value` is used during settings validation to properly
        coerce strings from the settings serializers into their
        defined types as well as to perform validation using the
        `verify_function` specified in the :class:`Setting`
        constructor.

        It is not necessary to call `try_value`.  Calls will be
        arranged by the settings infrastructure.

        """
        if value is None:
            # V32243 - None passed in here is "special".  We need to
            # preserve the meaning that the setting was not
            # specified.  The None object should never be used as a
            # true setting value.
            return None

        parsed_value = value

        if self.parser:
            parsed_value = self.parser(value)

        if not isinstance(parsed_value, self.type):
            try:
                parsed_value = self.type(value)
            except:
                raise AttributeError, \
                    "'%s' cannot be instantiated as '%s'" % \
                        (value, self.type.__name__)

        try:
            verified = self.verify_function(parsed_value)
        except Exception, e:
            msg = "'%s' fails verification function: %s" % \
                (value, str(e))
            raise AttributeError, msg
        else:
            if type(verified) == bool and not verified:
                msg = "'%s' verification function returns false" % \
                    (value)
                raise AttributeError, msg


        return parsed_value


class SettingsBase(object):
    """
    A settings implementation, base class.

    Classes which wish to have their settings preserved must inherit
    from this class and call the class constructor.

    `settings_binding` is a sequence representing a settings path.  As new
    settings are applied to the system, paths to settings registry data
    are matched against a binding list.  When a path is found matching
    a `settings_binding`, the object which made the binding's `apply_settings()`
    method is called.

    Typically `settings_binding` creation and management will be
    performed in the system automatically by the appropriate
    :py:class:`~devices.device_base.DeviceBase`,
    :py:class:`~presentations.presentation_base.PresentationBase`, or
    :py:class:`~services.service_base.ServiceBase` instance.

    `settings_defs` is a list of objects of type :class:`Setting`
    which define the individual allowable settings for the module
    sub-classing from :class:`SettingsBase`.

    A :class:`SettingsContext` is a friend to a :class:`SettingsBase`
    class and is fully aware of its internals.
    :class:`SettingsContext` objects are used to view and manipulate
    other components, while :class:`SettingsBase` objects are intended
    to allow a component access to its own settings.

    """
    _settings_global_pending_registry = {}  # all pending settings
    _settings_global_running_registry = {}  # all active settings
    _settings_global_bindings = {}          # bindings -> settings instances
    _settings_global_pending_bindings = [ ] # bindings with changed settings
    _settings_global_serializers = {}       # serializer name -> serializer
    _settings_global_lock = RLock()         # global lock

    def __init__(self, binding=(), setting_defs = []):
        # Add the binding:
        if binding in self._settings_global_bindings:
            if not self in self._settings_global_bindings:
                self._settings_global_bindings[binding].append(self)
        else:
            self._settings_global_bindings[binding] = [self]

        # Local (non-shared state) variables:
        self._settings_binding = binding
        self._settings_definitions = { }
        self._settings_running_registry = \
            self._settings_global_running_registry
        self._settings_pending_registry = \
            self.__get_local_registry_ref(
                self._settings_global_pending_registry, binding)
        self._settings_running_registry = \
            self.__get_local_registry_ref(
                self._settings_global_running_registry, binding)

        from core.tracing import get_tracer
        self.__tracer = get_tracer("SettingsBase")

        # Load settings into self._settings_definitions:
        for setting in setting_defs:
            self._settings_definitions[setting.name] = setting

        # Attempt to apply current pending settings:
        accepted, rejected, not_found = self.apply_settings()

        if rejected:
            raise ValueError, "ERROR: Invalid settings: %s" % rejected

        if not_found:
            raise SettingNotFound, "ERROR: Missing settings: %s" % not_found

    def __print_refs(self, registry="root"):
        self.__tracer.info("%s: 0x%08x", path, id(registry))
        if isinstance(registry, dict):
            for k in registry:
                self.__print_refs(registry[k], path + "." + k)
        elif isinstance(registry, list):
            for i in registry:
                if isinstance(i, dict) and 'name' in i:
                    self.__print_refs(i, path + "." + i['name'])

    def __get_local_registry_ref(self, registry, binding):
        for component in binding:
            if not isinstance(registry, dict):
                raise SettingsRegistryError, \
                  "when finding local registry reference, non-dict encountered."

            # Does the binding component indicate an indirect instance list
            # binding?
            if isinstance(component, tuple):
                if len(component) > 1:
                    raise SettingBindingDefinitionError, \
                        "binding '%s' indicates instance_list but len > 1" % \
                            (str(component))

                component = component[0]

                # Does the instance list exist in the target registry?
                if ('instance_list' in registry and
                    isinstance(registry['instance_list'], list)):

                    instance = None
                    for instance_list_member in registry['instance_list']:
                        if isinstance(instance_list_member, dict) and \
                          'name' in instance_list_member and \
                          instance_list_member['name'] == component:
                            instance = instance_list_member
                            break

                    if instance:
                        registry = instance
                        continue
                else:
                    registry['instance_list'] = [ ]

                # No instance, create template instance registry entry:
                new_instance = { 'name': component }
                registry['instance_list'].append(new_instance)
                registry = new_instance

            # Is the binding a direct binding, but does not exist?
            elif ((component not in registry) or
                  (component in registry and not
                   isinstance(registry[component], dict))):
                # create empty template registry for binding:
                registry[component] = { }
                # progress to new nested registry:
                registry = registry[component]
            else:
                # direct binding exists, progress to nested registry:
                registry = registry[component]

        return registry

    @staticmethod
    def binding_to_str(binding_tuple):
        """Return a string representation of a binding tuple."""

        def _recurse(l, obj):
            if isinstance(obj, str):
                l.append(obj)
            elif isinstance(obj, tuple):
                for i in obj:
                    _recurse(l, i)
            else:
                l.append('?')

        l = [ ]
        _recurse(l, binding_tuple)
        return '.'.join(l)

    def get_pending_setting(self, name):
        """Return a setting value from the pending settings registry."""

        if name not in self._settings_definitions or \
            name not in self._settings_pending_registry:
            raise SettingNotFound, "setting '%s' not found" % (name)

        return self._settings_pending_registry[name]

    def set_pending_setting(self, name, value):
        """
        Attempt to load a setting into the pending settings registry for
        this object.

        In order for this call to succeed, the setting name must have
        been defined in the constructor and it must pass that
        individual setting's type and range validations.

        """
        if name not in self._settings_definitions:
            raise SettingNotFound, "setting '%s' not found" % (name)

        self._settings_definitions[name].try_value(value)
        self._settings_pending_registry[name] = value
        if self._settings_binding not in self._settings_global_pending_bindings:
            self._settings_global_pending_bindings.append(self._settings_binding)

    def get_setting(self, name):
        """Return a setting value from the active settings registry."""

        if name not in self._settings_definitions or \
            name not in self._settings_running_registry:
            raise SettingNotFound, "setting '%s' not found" % (name)

        return self._settings_running_registry[name]

    def get_setting_definition(self, name):
        """
        Returns the definition for an individual setting.

        This is an object of type :class:`Setting`

        """

        if name not in self._settings_definitions or \
            name not in self._settings_running_registry:
            raise SettingNotFound, "setting '%s' not found" % (name)

        return self._settings_definitions[name]

    def get_settings_definitions(self):
        """
        Returns the dictionary of active :class:`Setting` definitions.

        """

        return self._settings_definitions

    def remove_binding(self):
        """Remove the binding for ourselves"""

        if self._settings_binding in self._settings_global_bindings:
            del self._settings_global_bindings[self._settings_binding]
            self._settings_binding = ()

    def apply_settings(self):
        """
        Transfers all settings from the pending settings group to the
        running settings group.

        This function may be extended by child classes in order to
        define validations which combine multiple settings or other
        more complicated validations.

        This function must return a tuple of three dictionaries: a
        dictionary of settings accepted, a dictionary of settings
        rejected, and a dictionary of required settings which were not
        found.

        """
        self.merge_settings()
        accepted, rejected, not_found = self.verify_settings()
        if len(rejected) or len(not_found):
            self.__tracer.error("settings rejected/not found: %s/%s",
                                rejected, not_found)

        # Commit the accepted settings to the running settings list;
        # N.B. this implies that by default, no settings verification
        # failures are exceptions.  They are only noted.
        self.commit_settings(accepted)

        return (accepted, rejected, not_found)

    def commit_settings(self, accepted_settings):
        """Copies `accepted_settings` to the running settings
        registry.

        Typically called in an implementation of
        :meth:`apply_settings` when that method has been extended.

        """

        self._settings_global_lock.acquire()
        try:
            # For each accepted settting:
            for setting_name in accepted_settings:
                if setting_name != 'instance_list':
                    # Place setting in running registry:
                    self._settings_running_registry[setting_name] = \
                        accepted_settings[setting_name]
                else:
                    # Special commit processing for instance lists:
                    if ('instance_list' not in
                        self._settings_running_registry):
                        # Create a new list in the running registry if one
                        # did not previously exist:
                        self._settings_running_registry['instance_list'] = \
                                                                         []
                    # Create variable references for convenience:
                    target_instance_list = \
                        self._settings_running_registry['instance_list']
                    source_instance_list = accepted_settings['instance_list']
                    for source_instance in source_instance_list:
                        target_instance_match = None
                        # Find if this instance already exists:
                        for target_instance in target_instance_list:
                            if (target_instance['name'] ==
                                source_instance['name']):
                                target_instance_match = target_instance
                                break
                        if target_instance_match is None:
                            # New instance, create:
                            target_instance_list.append(source_instance)
                        else:
                            # Update the instance list member by only
                            # copying over registry keys which are not
                            # bound:
                            bound_sites = []
                            binding_prefix = (
                                self._settings_binding +
                                    (("%s" % target_instance['name'],),))
                            for binding in self._settings_global_bindings:
                                if (binding[0:len(binding_prefix)] ==
                                    binding_prefix):
                                    bound_sites.append(binding)
                            keys_not_to_update = ['name']
                            for binding in bound_sites:
                                binding = binding[len(binding_prefix):]
                                if len(binding):
                                    keys_not_to_update.append(binding[0])
                            for key in source_instance:
                                if key in keys_not_to_update:
                                    continue
                                target_instance_match[key] = \
                                    source_instance[key]
            if self._settings_binding in \
                   self._settings_global_pending_bindings:
                # Mark these settings as having been applied:
                self._settings_global_pending_bindings.remove(
                    self._settings_binding)
        finally:
            self._settings_global_lock.release()

    def merge_settings(self):
        """
        Merge the local running and pending settings registries to the
        local pending settings registry.

        Typically used when implementing an extended
        :meth:`apply_settings` to prepare the registry for complete
        validation.

        """

        self._settings_global_lock.acquire()

        # creates independent copies (removes references) from running reg.
        running_reg_copy = deepcopy(self._settings_running_registry)

        for key in running_reg_copy:
            if key not in self._settings_pending_registry:
                self._settings_pending_registry[key] = \
                    running_reg_copy[key]

        self._settings_global_lock.release()

    def verify_settings(self):
        """
        Verifies the current pending settings and applies default
        values.

        Returns a tuple of three dictionaries: accepted settings,
        rejected settings, and required settings which were not found.

        Typically used by an extended :meth:`apply_settings` to
        perform :class:`Setting` object individual verification prior
        to performing more complex validation steps.

        """
        accepted, rejected, not_found = {}, {}, {}

        # Attempt to apply pending values:
        for pending_setting_name in self._settings_pending_registry:
            if pending_setting_name not in self._settings_definitions:
                rejected[pending_setting_name] = \
                    'unknown setting name "%s"' % (pending_setting_name)
                continue

            parsed_value = None
            try:
                parsed_value = \
                  self._settings_definitions[pending_setting_name].try_value(
                    self._settings_pending_registry[pending_setting_name])
                accepted[pending_setting_name] = parsed_value
            except Exception, e:
                rejected[pending_setting_name] = \
                    '%s' % (str(e))

        # Apply defaults or complain about required items not found:
        for setting_name in self._settings_definitions:
            if setting_name not in accepted:
                if self._settings_definitions[setting_name].required:
                    not_found[setting_name] = "required item not given"
                else:
                    accepted[setting_name] = \
                        self._settings_definitions[setting_name].default_value

        return (accepted, rejected, not_found)

    def register_serializer(self, name, serializer):
        """
        Register a serializer object with the settings system.

        The serializer must implement
        :class:`~settings.settings_serializer_base.SettingsSerializerBase`

        """
        self._settings_global_serializers[name] = serializer

    def unregister_serializer(self, name):
        """
        Register a serializer object with the settings system.

        The serializer must implement
        :class:`~settings.settings_serializer_base.SettingsSerializerBase`.

        """
        del self._settings_global_serializers[name]

    def get_serializers(self):
        """
        Get a list of valid serializer names.

        """

        return self._settings_global_serializers.keys()

    def get_context(self):
        """
        Return a :class:`SettingsContext` object.

        A :class:`SettingsContext` object is used when you wish to
        manipulate **another** objects settings.  If you wish to
        manipulate your own settings, you would inherit from this
        class (:class:`SettingsBase`) directly.

        """

        return SettingsContext(self)

    def globally_apply_settings(self):
        """
        Ask the system to apply all changed pending settings for all
        settings object instances system-wide.

        Settings will be applied breadth first.  Will return a dictionary of
        dictionary of accepted settings, rejected settings, and required
        settings not found in the following format::

            {
               'dot.delimited.binding.0': {
                 'accepted': { ... },
                 'rejected': { ... },
                 'notfound': { ... }
               },
               'dot.delimited.binding.1': { ... },
            }

        """

        return_dict = { }

        self._settings_global_lock.acquire()
        try:
            self._settings_global_pending_bindings.sort(lambda p, q: cmp(len(p),len(q)))
            # the pending bindings list will be modified by commit_settings,
            # so we must create a copy of it here for our iteration:
            pending_bindings = copy(self._settings_global_pending_bindings)
            for binding in pending_bindings:
                binding_name = self.binding_to_str(binding)
                if binding not in self._settings_global_bindings:
                    continue
                for settings_obj in self._settings_global_bindings[binding]:
                    return_dict[binding_name] = {}
                    try:
                        (return_dict[binding_name]["accepted"],
                         return_dict[binding_name]["rejected"],
                         return_dict[binding_name]["notfound"]) = \
                             settings_obj.apply_settings()
                    except Exception, e:
                        return_dict[binding_name] = "error"
                        self.__tracer.error("caught exception while " +
                                 " processing settings on '%s': %s", \
                                   binding_name, str(e))
                        self.__tracer.debug(traceback.format_exc())
        finally:
            self._settings_global_lock.release()

        return return_dict

    def __do_load(self, raw_settings):
        def _recursive_load(to_registry, from_registry):
            if isinstance(from_registry, dict):
                for key in from_registry:
                    if key in to_registry and isinstance(to_registry[key], dict):
                        to_registry[key].update(from_registry[key])
                    else:
                        to_registry[key] = from_registry[key]
                    _recursive_load(to_registry[key], from_registry[key])

        self._settings_global_lock.acquire()
        try:
            # This load will preserve existing references, which is
            # important for classes sharing this module to keep their
            # presently bound view on their settings:
            _recursive_load(self._settings_global_pending_registry,
                                raw_settings)

            # Assume all settings have been changed, dirty all bindings:
            for binding in self._settings_global_bindings:
                if binding not in self._settings_global_pending_bindings:
                    self._settings_global_pending_bindings.append(binding)

            # Apply the settings, breadth first:
            self.globally_apply_settings()
        finally:
            self._settings_global_lock.release()


    def load(self, flo, serializer_name):
        """
        Globally Load serialized settings from a file like object using a
        serializer.

        Parameters:

        * `flo`: file like object
        * `serializer_name`: name of registered serializer to use

        """
        serializer = self._settings_global_serializers[serializer_name]
        raw_settings = serializer.load(flo)
        self.__do_load(raw_settings)

    def loads(self, string, serializer_name):
        """
        Globally Load serialized settings from a string using a serializer.

        Parameters:

        * `string`: a string of serialized settings
        * `serializer_name`: name of registered serializer to use

        """
        serializer = self._settings_global_serializers[serializer_name]
        raw_settings = serializer.loads(string)
        self.__do_load(raw_settings)

    def save(self, flo, serializer_name, registry_def=REG_RUNNING):
        """
        Save all system settings to a file like object using a
        serializer.

        Parameters:

        * `flo`: file like object
        * `serializer_name`: name of registered serializer to use
        * `registry_def`: Which version of the registry to save
          :const:`REG_RUNNING` or :const:`REG_PENDING`

        """
        serializer = self._settings_global_serializers[serializer_name]

        if registry_def == REG_RUNNING:
            serializer.save(flo, self._settings_global_running_registry)
        elif registry_def == REG_PENDING:
            serializer.save(flo, self._settings_global_pending_registry)
        else:
            raise ValueError("Invalid registry_def value %s" % registry_def)

    def saves(self, serializer_name, registry_def=REG_RUNNING):
        """
        Save all system settings to a file like string using a
        serializer.

        Parameters:

        * `serializer_name`: name of registered serializer to use
        * `registry_def`: Which version of the registry to save
          :const:`REG_RUNNING` or :const:`REG_PENDING`

        Returns settings string

        """
        serializer = self._settings_global_serializers[serializer_name]
        if registry_def == REG_RUNNING:
            return serializer.saves(self._settings_global_running_registry)
        elif registry_def == REG_PENDING:
            return serializer.saves(self._settings_global_pending_registry)
        else:
            raise ValueError("Invalid registry_def value %s" % registry_def)

class SettingsContext:
    """
    A :class:`SettingsContext` object is used to manipulate settings
    of other objects in the system.

    If an object wishes to manipulate its own settings, it should
    inherit from :class:`SettingsBase` and use its own inherited
    functions.

    :ref:`Bindings` are treated differently when using a
    :class:`SettingsContext` than when using bindings with
    :class:`SettingsBase`.  The :class:`SettingsContext` uses more
    liberally specified binding tuples.  If :ref:`instance_list
    <instance_lists>` indirection is used in the binding, it is
    automatically resolved to the appropriate binding tuple and used
    internally when interacting with a :class:`SettingsBase` instance.
    This simplifies specification and the resulting potential
    ambiguity does not arise in real-life practice.

    In order to fetch the resolved binding tuple call the
    :meth:`get_current_binding` method.

    """

    def __init__(self, settings_base_instance):
        """Create a new SettingsContext object."""

        self.__settings_base_instance = settings_base_instance
        sbi = self.__settings_base_instance

        self.__cur_binding = ()
        self.__cur_pending_registry = sbi._settings_global_pending_registry
        self.__cur_running_registry = sbi._settings_global_running_registry

    def __recursive_locate(self, binding_tuple, registry, actual_binding=()):
        if len(binding_tuple) == 0:
            return registry, actual_binding
        component, binding_tuple = binding_tuple[0], binding_tuple[1:]
        # flatten all binding components for evaluation here:
        while isinstance(component, tuple):
            component = component[0]
        if 'instance_list' in registry:
            for instance_list_member in registry['instance_list']:
                if (isinstance(instance_list_member, dict) and
                    'name' in instance_list_member and
                    instance_list_member['name'] == component
                    ):

                    registry = instance_list_member
                    # instance lists are nested tuples:
                    actual_binding += ((component,),)
                    break
            else:
                raise KeyError("Binding component not found: %s" % component)
        else:
            try:
                registry = registry[component]
                actual_binding += (component,)
            except KeyError:
                raise KeyError("Binding component not found: %s" % component)
        return self.__recursive_locate(binding_tuple, registry, actual_binding)

    def _locate_binding(self, binding_tuple, registry):
        # Internal method to resolve a binding tuple into a proper
        # binding tuple used by :class:`SettingsBase`.
        return self.__recursive_locate(binding_tuple, registry)

    def get_serializers(self):
        """
        Get a list of all valid serializer formats registered with
        the settings sub-system.

        """
        return self.__settings_base_instance.get_serializers()

    def set_current_binding(self, binding_tuple):
        """
        Sets the current :ref:`binding <bindings>` of this settings context.

        Updates the pending and running registries viewed by this
        :class:`SettingsContext` instance.

        """
        sbi = self.__settings_base_instance
        settings_global_pending_registry = sbi._settings_global_pending_registry
        settings_global_running_registry = sbi._settings_global_running_registry
        (self.__cur_pending_registry,
         actual_binding)  = self._locate_binding(binding_tuple,
                                        settings_global_pending_registry)
        (self.__cur_running_registry,
         actual_binding) = self._locate_binding(binding_tuple,
                                        settings_global_running_registry)
        self.__cur_binding = actual_binding

    def get_current_binding(self):
        """
        Gets the current :ref:`binding <bindings>` of this settings
        context as a tuple.

        """
        return self.__cur_binding

    def update_pending_registry(self, serializer_name, input_settings):
        """
        Load new values into the pending registry at the current
        :ref:`binding <bindings>`.

        Parameters:

        * serializer_name: a valid serializer name string
        * input_settings: a string of settings given in the format
                               dictated by `serializer_name`

        """
        sbi = self.__settings_base_instance
        raw_settings = None
        if serializer_name is not None:
            serializer = sbi._settings_global_serializers[serializer_name]
            raw_settings = serializer.loads(input_settings)
        else:
            raw_settings = input_settings
        update_to = self.__cur_pending_registry

        if isinstance(raw_settings, dict):
            # standard-case, update pending dictionary:
            sbi._settings_global_lock.acquire()
            try:
                update_to.update(raw_settings)
                # dirty pending settings binding:
                if self.__cur_binding not in \
                  sbi._settings_global_pending_bindings:
                    sbi._settings_global_pending_bindings.append(
                      self.__cur_binding)
            finally:
                sbi._settings_global_lock.release()
            return

        # Corner case: if our presumed current context's binding takes us to
        # a leaf-value (i.e. a non-dictionary), then we must unwind out
        # a level in order to perform the settings merge without clobbering
        # the existing setting's Python object reference:
        penultimate_binding = \
            self.__cur_binding[0:len(self.__cur_binding)-1]
        (update_to, ignored) = self._locate_binding(penultimate_binding,
                        sbi._settings_global_pending_registry)
        key = self.__cur_binding[len(self.__cur_binding)-1]

        sbi._settings_global_lock.acquire()
        try:
            update_to[key] = raw_settings
            # dirty the appropriate binding:
            if penultimate_binding not in sbi._settings_global_pending_bindings:
                sbi._settings_global_pending_bindings.append(
                  penultimate_binding)
            # update our local reference to new object:
            self.__cur_pending_registry = update_to[key]
        finally:
            sbi._settings_global_lock.release()

    def __binding_contains_instance_list(self):
        # Returns True if the current binding contains an instance list.

        # Instance list operations are only valid on instance list bindings.

        try:
            settings_instances_at_binding = (
                self.__settings_base_instance._settings_global_bindings[(
                    self.__cur_binding)])
        except:
            return False

        instance_list_found = False
        for settings_instance in settings_instances_at_binding:
            try:
                sd = settings_instance.get_setting_definition('instance_list')
                instance_list_found = sd.type is list
            except SettingNotFound:
                continue

        return instance_list_found

    def pending_instance_list_append(self, instance_settings):
        """
        Append `instance_settings` to the pending registry at the
        current :ref:`binding <bindings>`.

        This function may be used, for example, to add new instances to a
        manager class.  The format of `instance_settings` must be a dictionary
        with a key called `name`.  Other common keys include `driver` and
        `settings`.

        If the current :ref:`binding <bindings>` does not point to an
        :ref:`instance list <instance_lists>`, this function will
        raise an exception.

        Parameters:

        * `instance_settings`: a dictionary of settings

        """

        if not self.__binding_contains_instance_list():
            raise Exception, "no instance list bound at %s" % \
                repr(self.__cur_binding)

        self.__cur_pending_registry['instance_list'].append(instance_settings)

    def pending_instance_list_remove_instance(self, name):
        """
        Removes an instance from the :ref:`instance list
        <instance_lists>` at the current :ref:`binding <bindings>` by
        name.

        Parameter:

        * name: string name of instance to be removed

        Raises:

        * Exception: if the current :ref:`binding <bindings>` does not
          contain an :ref:`instance list <instance_lists>`.

        * KeyError: if the :ref:`instance list <instance_lists>` does
          not contain the instance named by `name`.

        """
        if not self.__binding_contains_instance_list():
            raise Exception, "no instance list bound at %s" % \
                repr(self.__cur_binding)

        self.__settings_base_instance._settings_global_lock.acquire()
        try:
            tgt_instances = filter(lambda i: 'name' in i and i['name'] == name,
                                   self.__cur_pending_registry['instance_list'])
            for instance in tgt_instances:
                self.__cur_pending_registry['instance_list'].remove(instance)
        finally:
            self.__settings_base_instance._settings_global_lock.release()

    def get_pending_registry_copy(self):
        """
        Get a deepcopy of the current pending registry.

        """
        return deepcopy(self.__cur_pending_registry)

    def get_running_registry_copy(self):
        """
        Get a deepcopy of the current running registry.

        """
        return deepcopy(self.__cur_running_registry)

    def __serialize_registry(self, serializer_name, registry_def):
        sbi = self.__settings_base_instance
        serializer = sbi._settings_global_serializers[serializer_name]
        registry = self.__cur_pending_registry
        if registry_def == REG_RUNNING:
            registry = self.__cur_running_registry
        return serializer.saves(registry)

    def serialize_pending_registry(self, serializer_name):
        """
        Generate a serialized representation of the current pending
        registry.

        * serializer_name: string name of a valid serializer

        Returns a string of the serialized settings

        """
        return self.__serialize_registry(serializer_name, REG_PENDING)

    def serialize_running_registry(self, serializer_name):
        """
        Generate a serialized representation of the current running
        registry.

        Parameter:

        * `serializer_name`: string name of a valid serializer

        Returns a string of the serialized settings

        """
        return self.__serialize_registry(serializer_name, REG_RUNNING)

    def apply_settings(self, serializer_name):
        """
        Globally apply any pending settings.

        Each :ref:`binding <bindings>` with changed settings will have
        its `apply_settings()` method called.  After the settings have
        been applied any accepted and commited settings will be moved
        to the running settings registry.

        The format for the return of this function is defined in the
        :meth:`~SettingsBase.globally_apply_settings()` method of the
        :class:`SettingsBase` class.

        Parameters:

        * `serializer_name`: string name of a valid serializer

        Returns a dictionary of dictionaries representing the
        application result.

        """
        retval = self.__settings_base_instance.globally_apply_settings()
        # If we are on a leaf node binding, we may have a reference to
        # a leaf object, refresh our context in order to let go:
        self.set_current_binding(self.__cur_binding)

        sbi = self.__settings_base_instance
        serializer = sbi._settings_global_serializers[serializer_name]

        return serializer.serialize_application_result(retval)

    def save(self, serializer_name, flo, registry_def=REG_RUNNING):
        """
        Save a serialized representation of the running settings to a
        file-like object.

        Parameters:

        * `serializer_name`: string name of a valid serializer
        * `flo`: a file-like object
        """

        sbi = self.__settings_base_instance
        serializer = sbi._settings_global_serializers[serializer_name]
        sbi._settings_global_lock.acquire()
        try:
            if (registry_def == REG_RUNNING):
                serializer.save(flo, sbi._settings_global_running_registry)
            elif (registry_def == REG_PENDING):
                serializer.save(flo, sbi._settings_global_pending_registry)
            else:
                raise ValueError("Invalid registry_def value %s" % registry_def)


        finally:
            sbi._settings_global_lock.release()

# internal functions & classes
