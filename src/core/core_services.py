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

"""
This module contains the epoch for the Device Integration Application.
"""

# imports
import digitime
import sys
import traceback
import os.path
import socket
import gc
import threading

from common.abstract_service_manager import AbstractServiceManager
from core.tracing import TracingManager
from devices.device_driver_manager import DeviceDriverManager
from channels.channel_manager import ChannelManager
from presentations.presentation_manager import PresentationManager
from services.service_manager import ServiceManager
from core.scheduler import Scheduler

from settings.settings_base import SettingsBase, Setting, REG_PENDING


# exception classes
class CoreSettingsException(Exception):
    ''' raised for general errors within core services '''
    pass


class CoreSettingsFileNotFound(Exception):
    ''' raised when the settings file cannot be located '''
    pass


class CoreSettingsInvalidSerializer(Exception):
    '''
    raised when a valid serializer for settings data cannot
    be located
    '''
    pass


class CoreServiceNotFound(KeyError):
    ''' raised when a bad core service is requested '''
    pass


# classes
class CoreServices(SettingsBase):
    """
    Core object for system traversal and service access

    The `CoreServices` object acts as a central clearing house for
    access to the wide variety of objects present in a running DIA
    instance.

    Using this object you may:

    * Access and manage settings for the entire system
    * Retrieve device, presentation and service instances from the
      system
    * Initialize a new running DIA system.

    When run through an interactive session, a `CoreServices` object
    is returned from the `main()` routine.

    Example::

        >>> import dia
        >>> core_obj = dia.main()
        Determining platform type... PC host environment assumed.

        Python version mismatch! Digi='2.4.3 or 2.6.1', Current='2.4.5'
        Device Integration Application Version 1.3.8
        Using settings file: dia.yml
        Core: initial garbage collection of 0 objects.
        Core: post-settings garbage collection of 28 objects.
        Starting Scheduler...
        Starting Channel Manager...
        Starting Device Driver Manager...
        Starting Presentation Manager...
        Web Presentation (web0): using port 8001 and BaseHTTPServer
        XMLRPC(xmlrpc): starting server on port 8080
        Starting Services Manager...
        Core services started.
        >>> print core_obj
        <core.core_services.CoreServices instance at 0xb7744e2c>
        >>>

    Parameters:

    * `settings_flo` - An object implementing the Python file API to
      provide access to settings content.
    * `settings_filename` - The filename to use for saving settings.
      This may be the same as the file used to provide `settings_flo`
    * `shutdown_event` - A threading.Event object used to signal final
      shutdown to the main thread dia.py (so it may be interrupted from
      sleeping between garbage collections).

    """
    def __init__(self, settings_flo, settings_filename):
        # Provides self.settings and serialization:
        settings_list = [
            Setting(
                name='devices', type=list, required=False, default_value=[]),
            Setting(
                name='loggers', type=list, required=False, default_value=[]),
            Setting(
                name='presentations', type=list, required=False,
                default_value=[]),
            Setting(
                name='services', type=list, required=False, default_value=[]),
            Setting(
                name='tracing', type=list, required=False, default_value=[]),
        ]
        SettingsBase.__init__(self, binding=(), setting_defs=settings_list)

        self.__settings_filename = settings_filename
        self.__service_map = {}
        self.__serializer_ext_map = {}
        self.__sleep_req = None  # STUB: seconds to wait before power-off
        self.__shutdown_event = threading.Event()

        # TODO: core may become a thread so we can monitor services and
        #       attempt to restart them when they fail.
        try:
            self.epoch(settings_flo)
        except KeyboardInterrupt:  # pragma: no cover
            raise KeyboardInterrupt
        except CoreSettingsException:
            print "Core: Initial settings invalid, aborting start up..."
            sys.exit()
        except:
            print "Core: Fatal exception caught!  Halting execution."
            self.request_shutdown()

    def __wait_until_system_ready(self):
        """Waits until subsystems indicate they are ready.  Returns None."""

        # Python executes on the Digi device before all subsystems
        # are fully initialized, some simple checks should be performed
        # in order to simplify the number of exceptions that would
        # otherwise need to be tested for during driver initialization.

        # Test to see if the TCP/IP stack is available.
        tcpip_stack_ready = False
        for portnum in xrange(54146, 65535):
            try:
                sd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sd.bind(('', portnum))
                sd.close()
            except Exception, e:
                # Embedded TCP/IP stack not ready or trial port in use.
                # Sleep for one second...
                traceback.print_exc()
                print "Core: Waiting for network (port tested: %d, e: %s)..." % \
                        (portnum, str(e))
                digitime.sleep(1)
                # ...and try another port.
                continue

            # Test succeeded, exit loop.
            tcpip_stack_ready = True
            break

        if tcpip_stack_ready is False:
            raise Exception("TCP/IP stack not ready!")

        # Success
        return


    def get_service(self, name):
        """
        Retrieve a handle to a core service instance.

        Core services are built-in services intended to be used by a
        DIA developer to provide common functionality of wide
        applicability in the system.  These are not to be confused
        with services developed as sub-classes of the `ServiceBase`
        class.

        Core services that may be requested:

        * :py:class:`channel_manager
          <channels.channel_manager.ChannelManager>` - Allows run-time
          access to the channel database

        * :py:class:`device_driver_manager
          <devices.device_driver_manager.DeviceDriverManager>` -
          Allows run-time access to devices running in the system

        * :py:class:`presentation_manager
          <presentations.presentation_manager.PresentationManager>` -
          Allows run-time access to presentations running in the
          system.

        * :py:class:`scheduler <core.scheduler.Scheduler>` - Allows
          scheduling of events to be run in the future

        * :py:class:`service_manager
          <services.service_manager.ServiceManager>` - Allows run-time
          access to `ServiceBase` services running in the system.

        * :py:class:`settings_base
          <settings.settings_base.SettingsBase>` - Root `SettingsBase`
          object in the system.  This happens to be the `CoreServices`
          object itself, but that may change in the future.

        * :py:class:`tracing_manager
          <core.tracing.TracingManager>` - Allows run-time access
          to tracing configuration.

        """
        if name not in self.__service_map:
            raise CoreServiceNotFound("service '%s' not found." % \
                (name))

        return self.__service_map[name]


    def set_service(self, name, obj):
        """
        Sets a handle to a core service.

        In unusual cases, it may be desirable to add objects as
        globally accessible services to the `CoreServices` object.
        `set_service` will add a service to those retrievable by the
        `get_service` call.

        Parameters:

        * name - The key to be used to retrieve this service.
        * obj - the object to be returned when requested

        """
        self.__service_map[name] = obj


    def conditional_settings_serializer_load(self,
            settings_filename="", suffix=""):
        """
        Infer which serializer should be loaded and used.

        Parameters:

        * `settings_filename` - Filename to use to determine
          serializer
        * `suffix` - Suffix of filename used to determine serializer

        Only one of `settings_filename` or `suffix` need be specified
        """

        if len(settings_filename):
            suffix = os.path.splitext(settings_filename)[1][1:]
        elif not len(suffix):
            raise CoreSettingsInvalidSerializer

        if suffix in [ 'yml', 'yaml' ]:
            from settings.settings_serializer_yaml import SettingsSerializerYaml
            SettingsBase.register_serializer(self, "yaml",
                                             SettingsSerializerYaml())
            self.__serializer_ext_map["yaml"] = "yml"
            return 'yaml'
        if suffix == 'pyr':
            from settings.settings_serializer_py import SettingsSerializerPy
            SettingsBase.register_serializer(self, 'pyr',
                                             SettingsSerializerPy())
            self.__serializer_ext_map['pyr'] = 'pyr'
            return 'pyr'
        else:
            raise CoreSettingsInvalidSerializer(
                "unsupported serializer '%s'" % suffix )

    def serializer_file_ext_lookup(self, serializer_name):
        """Given a serializer name, return the default file extension."""

        if serializer_name not in self.__serializer_ext_map:
            raise CoreSettingsInvalidSerializer(
                "unsupported serializer or serializer not loaded.")

        return self.__serializer_ext_map[serializer_name]

    def load_settings(self, settings_filename, settings_flo=None):
        """
Load settings from `settings_filename`.

If the optional parameter `setting_flo` is specified, that file-like object
will be used as the source of settings data.  `settings_filename` is always
used in order to infer the settings serializer used to interpret the
settings as given by a extension-to-type mapping table defined as a constant
in the core service.
        """

        serializer_name = self.conditional_settings_serializer_load(
                            settings_filename=settings_filename)

        if not settings_flo:
            if not os.path.exists(settings_filename):
                raise CoreSettingsFileNotFound

            try:
                settings_flo = open(settings_filename, 'r')
            except:
                raise CoreSettingsFileNotFound

        try:
            SettingsBase.load(self, settings_flo, serializer_name)
        except Exception, e:
            try:
                print "Core: Unable to load settings: %s" % (str(e))
            except:
                print "Core: Unable to load settings: reason unavailable"
            raise CoreSettingsException

    def save_settings(self):
        """Commit active settings to non-volatile storage"""

        # We save the pending set because we want to preserve the
        # settings provided by the user, even if there were
        # errors. We're also using this path for persistence and want
        # to ensure we copy the full setting set regardless of whether
        # we've validated it.

        serializer_name = self.conditional_settings_serializer_load(
            self.__settings_filename)

        flo = open(self.__settings_filename, 'w')
        SettingsBase.save(self, flo, serializer_name, REG_PENDING)
        flo.close()

    def epoch(self, settings_flo):
        """After initialization, execution begins here.

        This is called by the `main` routine in `dia.py`.  It should
        not be necessary for this to be called by any other code.
        """

        # Delay further initialization until the system is fully available:
        self.__wait_until_system_ready()

        print "Core: initial garbage collection of %d objects." % (gc.collect())

        # Allow the core to stand in as the global SettingsBase instance:
        self.set_service("settings_base", self)

        # Load initial settings:
        self.load_settings(self.__settings_filename, settings_flo)
        settings_flo.close()

        try:
            print "Core: post-settings garbage " + \
                   "collection of %d objects." % (gc.collect())
            print "Core: Starting Tracing Manager...", # <- the ',' belongs there
            TracingManager(core_services=self)
            print "Core: Starting Scheduler..."
            Scheduler(core_services=self)
            print "Core: Starting Channel Manager..."
            ChannelManager(core_services=self)
            print "Core: Starting Device Driver Manager..."
            DeviceDriverManager(core_services=self)
            print "Core: Starting Presentation Manager..."
            PresentationManager(core_services=self)
            print "Core: Starting Services Manager..."
            ServiceManager(core_services=self)

            ##### DOCUMENTATION REMINDER: #########################
            # If you add objects as core services to the system,
            # please remember to add them to the get_service docstring.
            #######################################################

        except KeyboardInterrupt:  # pragma: no cover
            print "Core: Caught keyboard interrupt. Stopping..."
            self._shutdown()
            return  # don't print "Core services started."
        except:
            print "Core: Exception during core initialization:"
            traceback.print_exc()
            raise Exception("Fatal exception during initialization.")
        print "Core services started."

    def _shutdown(self):
        """
        Called by dia.py after a shutdown_request() call from a device
        or presentation.
        """
        # Request component shutdown from active drivers
        managers = filter(lambda svc: isinstance(svc, AbstractServiceManager),
                          self.__service_map.values())
        cm = self.get_service('channel_manager')
        # Add logging manager
        managers.append(cm.channel_logging_manager_get())

        for service in managers:
            for driver in service.instance_list():
                print "Core: Stopping %s" % (driver)
                try:
                    service.instance_stop(driver)
                except Exception, e:
                    print ("Core: Unable to stop %s, continuing" +
                                          " shutdown requests") % (driver)
                    print str(e)
                    traceback.print_exc()

        # Terminate any scheduling operations
        print "Stopping scheduler...",
        self.get_service('scheduler').stop()
        print "done."

        # close all outputs
        # At this point, we shouldn't have any more messages...
        print "Core: Stopping tracing_manager...",
        self.get_service('tracing_manager').stop()
        print "done."

        other_threads = _get_other_threads()
        count_sleeps = 0
        while other_threads:
            if count_sleeps % 10 == 0:
                print ('Core: Threads still running (%s).'
                       '\nWaiting for them '
                       'to terminate... ') % (str(other_threads))
            digitime.sleep(1)
            count_sleeps += 1
            other_threads = _get_other_threads()

        print "Core: All threads stopped."

        # STUB: add sleep code
        if hasattr(self, '__sleep_req') and self.__sleep_req:
            print "Core: sleeping not implemented"
            print "\t(%d seconds requested)" % self.__sleep_req

    def wait_for_shutdown(self, timeout=None):
        """
        Blocks the current thread for optional `timeout` seconds while
        waiting for a shutdown request. If `timeout` is not given,
        this call will block indefinitely until another thread
        calls request_shutdown()
        """

        # polling is cheaper than waiting
        # on a threading.Condition object
        if timeout is None:
            while not self.shutdown_requested():
                digitime.sleep(1)
        else:
            for i in range(timeout):
                if self.shutdown_requested():
                    break
                else:
                    digitime.sleep(1)

    def shutdown_requested(self):
        ''' returns True if a shutdown is currently pending '''
        return self.__shutdown_event.isSet()

    def request_shutdown(self, sleep=None):
        '''
        Called to exit DIA

        Allows components in the system to request that DIA shut down
        and exit.  If the optional `sleep` parameter is specified, the
        final action of the system will be to attempt to power-off
        using the power control module and request reactivation after
        `sleep` seconds.
        '''
        self.__sleep_req = sleep
        self.__shutdown_event.set()

# internal functions & classes

def _get_other_threads():
    '''\
    Return a list of Thread objects that would prevent a normal shutdown.

    This means all threads who are not the calling thread.
    '''
    return filter(lambda x: x != threading.currentThread(),
                  threading.enumerate())
