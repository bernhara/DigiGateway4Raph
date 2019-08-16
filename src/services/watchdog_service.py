############################################################################
#                                                                          #
# Copyright (c)2009, Digi International (Digi). All Rights Reserved.       #
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
**DIA Watchdog Service**
"""

# imports
from services.service_base import ServiceBase
from settings.settings_base import SettingsBase, Setting
from core.tracing import get_tracer
import digi_ElementTree as etree
import digitime

import string

try:
    from rci import process_request
except:
    _tracer = get_tracer(name="Watchdog Service")
    _tracer.debug("DEBUG RCI IN PLACE, are you running on a PC?")
    mem = 500000
    # For debugging on a PC
    def process_request(s):
        global mem
        _tracer.info(s)
        mem -= 100000
        _tracer.info(mem)
        return '''\
<rci_reply version="1.1">
    <query_state>
        <device_stats>
            <cpu>3</cpu>
            <uptime>3307</uptime>
            <datetime>Mon Sep 28 10:59:38 2009</datetime>
            <totalmem>16777216</totalmem>
            <freemem>%d</freemem>
        </device_stats>
    </query_state>
</rci_reply>''' % mem

try:
    import digiwdog
    _watchdog_available = True
except:
    _watchdog_available = False

# constants

# exception classes

# interface functions

# classes

class WatchdogService(ServiceBase):
    """
    Checks system conditions for failure states.
    
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.

    """

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        self.wd = None
        self.restart_counter = 0

        self.__tracer = get_tracer(name)
		
        # Settings

        # watchdog_interval: defines how often to stroke the watchdog in seconds
        # low_memory_threshold: reboot if below memory threshold (bytes)
        # auto_restart_interval: how long the device should run
        #     before auto-restart in seconds.
        
        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='watchdog_interval', type=int, required=True, 
                default_value=120,
                verify_function=lambda x: x >= 60 and x <= 3600),
            Setting(
                name='low_memory_threshold', type=long, required=False,
                verify_function=lambda x: x >= 40960),
            Setting(
                name='auto_restart_interval', type=long, required=False, 
                verify_function=lambda x: x >= 600), 
        ]

        ## Initialize the ServiceBase interface:
        ServiceBase.__init__(self, self.__name, settings_list)



    ## Functions which must be implemented to conform to the ServiceBase
    ## interface:

    def apply_settings(self):
        """
            Called when new configuration settings are available.
       
            Must return tuple of three dictionaries: a dictionary of
            accepted settings, a dictionary of rejected settings,
            and a dictionary of required settings that were not
            found.
        """
        
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        if len(rejected) or len(not_found):
            self.__tracer.error("Settings rejected/not found: %s %s", rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        watchdog_interval = SettingsBase.get_setting(self,
                                                     "watchdog_interval")

        if (_watchdog_available):
            self.wd = digiwdog.Watchdog(watchdog_interval, "Force reset")

        self.__sched = self.__core.get_service("scheduler")
        self.schedule()

        return True

    def stop(self):
        self.__sched = self.__core.get_service("scheduler")
        self.__sched.cancel(self.__nextrun)
        self.wd = None
        return True

    ## Locally defined functions:

    def schedule(self):
        watchdog_interval = SettingsBase.get_setting(self,
                                                     "watchdog_interval")
        # the "-10" gives us a bit of fudge in case of a
        # preemptive processing delay
        # increment the restart_counter with the current watchdog_interval
        # (less 10 seconds)
        self.restart_counter = self.restart_counter + (watchdog_interval-10) 

        self.__nextrun = self.__sched.schedule_after(watchdog_interval - 10, 
                                                      self.check)

    def get_free_memory(self):
        response = process_request('''\
<rci_request><query_state><device_stats /></query_state></rci_request>''')

        response = etree.XML(response)

        freeMemory = int(response.find('freemem').text)
            
        return freeMemory

    def reset(self):
        process_request('<rci_request><reboot /></rci_request>')
        # Give us some time to reboot.  We should not return.
        while True:
            digitime.sleep(60)

    def stroke(self):
        if (_watchdog_available):
            self.wd.stroke()

    def _do_auto_restart(self):
        # see if the user requested an auto_restart_interval
        try:
            auto_restart_interval = SettingsBase.get_setting(
                self,"auto_restart_interval")
            auto_restart_check = True
        except:
            auto_restart_check = False

        # check for auto_restart first
        if (auto_restart_interval and auto_restart_check):
            if (self.restart_counter >= auto_restart_interval):
                self.__tracer.info("Auto-restart")
                self.reset()

    def _do_low_memory(self):
        # see if the user requested a low_memory_threshold check
        try:
            low_memory_threshold = SettingsBase.get_setting(
                self,"low_memory_threshold")
            low_memory_check = True
        except:
            low_memory_check = False

        # if low_memory_check is set, get system info and then
        # compare to required minimum memory mark
        if (low_memory_check):
            try:
                freeMemory = self.get_free_memory()
            except Exception, e:
                # We expect to be able to get memory stats.  The fact
                # we can't is troubling enough that we should probably
                # reboot.
                self.reset()

                # Should not get here.  If we do, bail.
                assert False

            # only stroke if we meet the conditions for free memory
            if (freeMemory < low_memory_threshold):
                self.__tracer.warning("memory low")
                self.reset()
        
    # Threading related functions:
    def check(self):
        # Performs watchdog service checks

        # perform checks, they don't return (we reboot) if they fail
        self._do_auto_restart()
        self._do_low_memory()

        # The checks have passed, we're free to stroke and stay alive
        self.stroke()

        self.schedule()

# internal functions & classes
