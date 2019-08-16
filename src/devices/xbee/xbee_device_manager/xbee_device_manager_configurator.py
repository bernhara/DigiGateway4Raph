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
XBee Device Manager Configurator

This file implements all the things needed to support the
XBee Device Manager in configuring an XBee Device.

"""

# imports
import threading
from copy import copy
import Queue

from devices.xbee.xbee_device_manager.xbee_device_manager import \
    BEHAVIOR_HAS_ATOMIC_DDO  # BEHAVIOR_NONE

from devices.xbee.common.ddo import \
    GLOBAL_DDO_TIMEOUT, retry_ddo_get_param, retry_ddo_set_param

from devices.xbee.xbee_device_manager.xbee_ddo_param_cache import \
    XBeeDDOParamCacheMissNodeNotFound, XBeeDDOParamCacheMissParamNotFound

from core.tracing import get_tracer


MAX_BLOCK = 5.0  # # of seconds to sit on a lock before checking conditions

# classes
class XBeeDeviceManagerConfigurator(object):
    '''
    XBee Device Manager Configurator class.

    This class implements all the things needed to support the
    XBee Device Manager in configuring an XBee Device.

    Keyword arguments:

    * **xbee_device_manager:** the xbee device mananger instance
    * **num_ddo_resources:** the max number of parallel DDO requests
    '''
    def __init__(self, xbee_device_manager, num_ddo_resources=1):
        self.__xbee_device_manager = xbee_device_manager

        # Allocate two semaphores, both equal to the number of parallel
        # DDO requests which are allowed to simultaneously execute on the
        # system:
        self.__worker_semaphore = threading.Semaphore(num_ddo_resources)
        self.__ddo_semaphore = threading.Semaphore(num_ddo_resources)

        # Create an equal number of worker threads to the number of
        # allowed parallel DDO requests:
        self.__workers = [XBeeDeviceManagerConfiguratorWorker() for i \
                            in range(num_ddo_resources)]
        self.__allworkers = copy(self.__workers)

        self.__tracer = get_tracer('XBeeDeviceManagerConfigurator')

        self.__running = True
        for worker in self.__workers:
            worker.start()

    def stop(self):
        self.__running = False
        for worker in self.__allworkers:
            worker.stop()

    ## Public API:
    def ddo_get_param(self, dest, param, timeout=GLOBAL_DDO_TIMEOUT,
                      retries=3, use_cache=False, blocking=True):
        """
        Work with the XBee Device Manager Configurator to schedule a pending
        DDO get request.  Working with the manager--as opposed to performing
        a request directly with xbee.ddo_get_param--ensures that requests
        are scheduled in an optimal manner.

        If use_cache is True, the parameter will first be sought in the
        DDO parameter cache.  If the parameter is not found in the cache
        it will be set from a successful network request.

        Returns the DDO parameter value.

        Returns False if blocking=False and the method would block.

        Note: if blocking calls are used in a Digimesh network, they
        could block for an entire sleep period.
        """

        result = None

        if use_cache:
            try:
                result = \
                  self.__xbee_device_manager._xbee_device_ddo_param_cache_get(
                    dest, param)
            # Non-fatal exception - Just a cache miss.
            except XBeeDDOParamCacheMissNodeNotFound:
                pass
            # Non-fatal exception - Just a cache miss.
            except XBeeDDOParamCacheMissParamNotFound:
                pass
            except:
                raise

            if result is not None:
                return result

        if dest is not None:
            if blocking:
                # block until awake
                while not self.__xbee_device_manager._awakeEvent.isSet():
                    # kill signal
                    if not self.__running:
                        return False
                    self.__xbee_device_manager._awakeEvent.wait(MAX_BLOCK)
            else:
                # in non-blocking, if the node is not awake, simply
                # return False
                if not self.__xbee_device_manager._awakeEvent.isSet():
                    return False

        blocked = self.__ddo_semaphore.acquire(blocking=blocking)
        if not blocked:
            # didn't want to block
            return False

        # HACK: wait for running network discovery call to finish
        while not self.__xbee_device_manager.NETWORK_DISCOVER_HACK.isSet():
            # killed
            if not self.__running:
                return False
            self.__xbee_device_manager.NETWORK_DISCOVER_HACK.wait(MAX_BLOCK)

        try:
            result = retry_ddo_get_param(retries, dest, param, timeout)
            # Update the parameter cache:
            self.__xbee_device_manager._xbee_device_ddo_param_cache_set(
                dest, param, result)
        finally:
            self.__ddo_semaphore.release()

        return result

    def ddo_set_param(self, dest, param, value='', timeout=GLOBAL_DDO_TIMEOUT,
                        order=False, apply=False, retries=3, blocking=True):
        """
        Work with the XBee Device Manager Configurator to schedule a pending
        DDO set request.  Working with the manager--as opposed to performing
        a request directly with xbee.ddo_set_param--ensures that requests
        are scheduled in an optimal manner.

        A side-effect of calling this function is that the internal DDO
        parameter cache will be updated if setting the parameter was
        successful.

        Returns the DDO parameter value.


        Returns False if blocking=False and the method would block.

        Note: if blocking calls are used in a Digimesh network, they
        could block for an entire sleep period.
        """

        result = None

        if dest is not None:
            if blocking:
                # block until awake
                while not self.__xbee_device_manager._awakeEvent.isSet():
                    # kill signal
                    if not self.__running:
                        return False
                    self.__xbee_device_manager._awakeEvent.wait(MAX_BLOCK)
            else:
                # in non-blocking, if the node is not awake, simply
                # return False
                if not self.__xbee_device_manager._awakeEvent.isSet():
                    return False

        blocked = self.__ddo_semaphore.acquire(blocking=blocking)
        if not blocked:
            # didn't want to block
            return False

        # HACK: wait for running network discovery call to finish
        while not self.__xbee_device_manager.NETWORK_DISCOVER_HACK.isSet():
            # killed
            if not self.__running:
                return False
            self.__xbee_device_manager.NETWORK_DISCOVER_HACK.wait(MAX_BLOCK)

        behavior_flags = self.__xbee_device_manager._get_behavior_flags()
        try:
            if (behavior_flags & BEHAVIOR_HAS_ATOMIC_DDO):
                result = retry_ddo_set_param(retries,
                            dest, param, value, timeout,
                            order=order, apply=apply)
            elif apply and param != 'AC':
                # No atomic DDO support, perform in two steps:
                result = retry_ddo_set_param(retries,
                            dest, param, value, timeout)
                result = retry_ddo_set_param(retries,
                            dest, 'AC', '', timeout)
            else:
                # Simple non-atomic DDO:
                result = retry_ddo_set_param(retries,
                            dest, param, value, timeout)

            # Update the DDO parameter cache:
            self.__xbee_device_manager._xbee_device_ddo_param_cache_set(
                dest, param, value)
        finally:
            self.__ddo_semaphore.release()

        return result

    def configure(self, xbee_state):
        # print ("XBeeDeviceManagerConfigurator: request to" +
        #                " configure node '%s'") % \
        #                     (xbee_state.ext_addr_get())
        self.__xbee_device_manager._state_lock()
        try:
            # Increment the number of config attempts in the state object:
            config_attempts = xbee_state.config_attempts_get()
            xbee_state.config_attempts_set(config_attempts + 1)

            if xbee_state.is_config_active():
                # Some other worker is already working on this thread,
                # this item does not need to be entered for configuration
                # again at this time.
                return False

            xbee_state.goto_config_active()
        finally:
            self.__xbee_device_manager._state_unlock()

        # Attempt to grab the worker thread resource:
        if self.__worker_semaphore.acquire(False):
            # A worker is a available, get it:
            worker = self.__workers.pop()
            # Hand it its task:
            worker.configure(xbee_state, self._configuration_done)
            self.__tracer.info("Worker assigned to '%s'",
                (xbee_state.ext_addr_get()))
            # The worker semaphore is released in the configuration_done() method.
        else:
            # The worker is not available, we will queue this configuration
            # request:
            self.__tracer.info("Worker unavailable, deferring " +
                               "configuration for node '%s'",
                               xbee_state.ext_addr_get())

            self.__xbee_device_manager._xbee_device_configuration_defer(
                                            xbee_state)

    def xbee_device_manager_get(self):
        """Returns the reference to the XBeeDeviceManager instance."""
        return self.__xbee_device_manager

    # Private API:
    def _configuration_done(self, by_worker, xbee_state):
        # Our worker has called us back, indicating that it has finished:
        self.__workers.append(by_worker)
        self.__worker_semaphore.release()

        # Pass this information up to the XBee Device Manager:
        self.__xbee_device_manager.\
                    _xbee_device_configuration_done(xbee_state)


class XBeeDeviceManagerConfiguratorWorker(threading.Thread):
    """
    Implements the worker functions for configuring an XBee device.
    Each instance of this class creates a thread.
    """
    def __init__(self):
        ## Thread initialization:
        self.__stopevent = threading.Event()
        self.__queue = Queue.Queue(1)
        name = "XBeeDeviceManagerConfiguratorWorker"
        self.__tracer = get_tracer(name)
        threading.Thread.__init__(self, name=name)

    def stop(self):
        """Stop the worker."""
        self.__stopevent.set()
        return True

    def configure(self, xbee_state, cb):
        """
        This function is called by the Device Manager Configurator to tell
        our thread to start configuring the device that is in the
        xbee_state variable.
        """
        # Communicate the work item to the worker thread:
        work_item = (self.do_configure, (xbee_state,), cb)
        self.__queue.put(work_item, True)

    def do_configure(self, xbee_state):
        """
        Go and actually start configuring the device that is stored
        in the xbee_state variable.
        This function is called internally only by our own class.
        """

        # Iterate over each block and attempt to apply its configuration:
        self.__tracer.debug("(%s): have %d config blocks",
                           xbee_state.ext_addr_get(),
                            len(xbee_state.config_block_list()))

        for config_block in xbee_state.config_block_list():
            if config_block.is_complete():
                # This block has already been applied, skip it:
                self.__tracer.debug("(%s): skipping complete block %s",
                                   xbee_state.ext_addr_get(),
                                   repr(config_block))
                continue

            # Try to apply the config:
            self.__tracer.debug("(%s): applying block %s",
                               xbee_state.ext_addr_get(),
                                str(config_block))

            try:
                if not config_block.apply_config():
                #print "Worker(%s): application of block %s FAILED" % \
                #    (xbee_state.ext_addr_get(), repr(config_block))
                    break
            except Exception, e:
                # Raising an exception beyond this point would kill the
                # worker entirely and leave the worker semaphore dead
                self.__tracer.warning("Failed attempt - will retry, %s",
                                      str(e))
                break

            self.__tracer.debug("(%s): application of block %s SUCCEEDED",
                               xbee_state.ext_addr_get(),
                                str(config_block))

        return xbee_state

    def run(self):
        """
            This function is the entry into starting the worker thread.
            It will watch its internal queue for any jobs submitted to it,
            and when it sees something come on the queue, it will run the
            method, and possible do a callback to let the caller know
            that the function finished as well as the return value of the
            function.

        """
        while True:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break

            method, args, complete_cb = (None, None, None)
            try:
                method, args, complete_cb = self.__queue.get(True, 5.0)
            except Queue.Empty:
                continue

            if not (method and args):
                continue

            return_val = method(*args)

            if complete_cb:
                complete_cb(self, return_val)
