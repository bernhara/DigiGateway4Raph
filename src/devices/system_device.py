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

# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.digi_device_info import query_state
from samples.sample import Sample
from common.shutdown import SHUTDOWN_WAIT
import threading
import digitime

class SystemDevice(DeviceBase, threading.Thread):
    """
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

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='update_rate', type=float, required=False, default_value=1.0,
                  verify_function=lambda x: x > 0.0)
        ]

        property_list = [
            ChannelSourceDeviceProperty(name="uptime", type=int,
                  initial=Sample(timestamp=0, value=-1, unit="sec"),
                  perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="cpu_utilization", type=int,
                  initial=Sample(timestamp=0, value=0, unit="%"),
                  perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="free_memory", type=int,
                  initial=Sample(timestamp=0, value=-1, unit="bytes"),
                  perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="used_memory", type=int,
                  initial=Sample(timestamp=0, value=-1, unit="bytes"),
                  perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="total_memory", type=int,
                  initial=Sample(timestamp=0, value=-1, unit="bytes"),
                  perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]


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

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        if len(rejected) or len(not_found):
            self.__tracer.error("Settings rejected/not found: %s %s",
                                rejected, not_found)

        if (('update_rate' in accepted) and
            (accepted['update_rate'] > SHUTDOWN_WAIT)):
            self.__tracer.warning("Long update_rate setting may " +
                                  "interfere with shutdown of DIA")

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):

        threading.Thread.start(self)
        return True

    def stop(self):

        self.__stopevent.set()
        return True


    # Threading related functions:
    def run(self):

        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break

            try:
                device_stats = query_state("device_stats")

                for stat in ['uptime', 'cpu', 'freemem', 'usedmem', 'totalmem']:
                    for item in device_stats:
                        data = item.find(stat)
                        if data != None:
                            data = data.text
                            break
                    else:
                        continue

                    if stat == 'uptime':
                        self.property_set("uptime",
                            Sample(0, int(float(data)), unit="sec"))
                    elif stat == 'cpu':
                        self.property_set("cpu_utilization",
                            Sample(0, int(data), unit="%"))
                    elif stat == 'freemem':
                        self.property_set("free_memory",
                            Sample(0, int(data), unit="bytes"))
                    elif stat == 'usedmem':
                        self.property_set("used_memory",
                            Sample(0, int(data), unit="bytes"))
                    elif stat == 'totalmem':
                        self.property_set("total_memory",
                            Sample(0, int(data), unit="bytes"))

            except Exception, e:
                self.__tracer.error("Unable to update stat: %s", str(e))

            digitime.sleep(SettingsBase.get_setting(self,"update_rate"))



# internal functions & classes
