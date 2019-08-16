############################################################################
#                                                                          #
# Copyright (c)2008,2009 Digi International (Digi). All Rights Reserved.   #
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

import digitime
import itertools
import Queue
import threading

from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from core.tracing import get_tracer
from common.types.boolean import Boolean

try:
    import rci
except ImportError:
    tracer = get_tracer("led_control")
    tracer.error("Unable to import rci, is this supported on this platform?")
    raise

try:
    from digihw import user_led_set
except ImportError:
    tracer = get_tracer("led_control")
    tracer.error(
        "Unable to import digihw.user_led_set, is this "
        "supported on this platform?")
    raise


class LEDBlinkPattern(object):
    def __init__(self, pattern, supported_leds):
        if not LEDControl.verify_pattern(pattern, supported_leds):
            raise ValueError("Input of: %s is invalid pattern." % pattern)

        self.pattern = pattern

    def get_pattern(self):
        return self.pattern


class LEDControl(DeviceBase, threading.Thread):
    def __init__(self, name, core_services):
        self.tracer = get_tracer(name)

        # Learn about the environment
        self.OS_LED_CONTROL = self.take_led_control()
        self.supported_leds = self.get_supported_leds()
        self.stop_event = threading.Event()
        self.clear_event = threading.Event()

        ## Thread initialization:
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)
        self.queue = Queue.Queue()

        self.core = core_services

        ## Settings Table Definition:
        settings_list = [
            Setting(name='cleared_state',
                    type=Boolean,
                    required=False,
                    default_value=False,
                    )
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties

            ChannelSourceDeviceProperty(name="repeat_pattern",
                                        type=str,
                                        initial=Sample(timestamp=0, value=""),
                                        perms_mask=DPROP_PERM_SET,
                                        options=DPROP_OPT_AUTOTIMESTAMP,
                                        set_cb=self.set_blink_pattern),

            ChannelSourceDeviceProperty(name="clear_pattern",
                                        type=bool,
                                        initial=Sample(timestamp=0,
                                                       value=False),
                                        perms_mask=DPROP_PERM_SET,
                                        options=DPROP_OPT_AUTOTIMESTAMP,
                                        set_cb=self.clear_led_blinks),
        ]

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, name, self.core,
                            settings_list, property_list)

    def start(self):
        threading.Thread.start(self)
        return True

    def stop(self):
        self.stop_event.set()
        self.queue.put("Empty")

        # Return control back to the OS
        self.return_led_control()

        return True

    def run(self):
        while not self.stop_event.is_set():
            cleared_state = SettingsBase.get_setting(self, "cleared_state")
            for led in self.supported_leds:
                user_led_set(cleared_state, led)

            item = self.queue.get(True)
            self.tracer.debug("Blink pattern received by thread.")
            if self.stop_event.is_set():
                self.tracer.debug("Thread told to quit")
                break

            self.clear_event.clear()
            pattern = item.get_pattern()
            self.tracer.debug(str(pattern))
            while not (self.clear_event.is_set() or self.stop_event.is_set()):
                self.do_blink_pattern(pattern)

            if self.clear_event.is_set():
                self.tracer.debug("Clear event triggered, resetting")
                self.clear_event.clear()

    @staticmethod
    def get_supported_leds():
        for v in itertools.count(1):
            try:
                user_led_set(False, v)
            except:
                return range(1, v)

    @staticmethod
    def verify_pattern(pattern, supported_leds):
        tracer = get_tracer("led_control")
        if type(pattern) is not list:
            tracer.warning("LED pattern: %s is not of type list"
                           % str(pattern))
            return False

        if len(pattern) == 0:
            tracer.warning("LED pattern has 0 elements")
            return False

        for item in pattern:
            if len(item) != 2:
                tracer.warning(
                    "Item: %s in pattern: %s has should have two elements" %
                    (item, pattern))
                return False

            try:
                duration = float(item[0])
            except ValueError:
                tracer.warning(
                    ("Item: %s in pattern: %s first element should "
                     "be of type float") % (str(item), str(pattern)))
                return False

            try:
                led = int(item[1])
            except ValueError:
                tracer.warning(
                    ("Item: %s in pattern: %s second element should "
                     "be of type int") % (str(item), str(pattern)))
                return False

            if led not in supported_leds:
                tracer.warning(
                    "LED indicator: %s in item: %s in pattern: %s is invalid"
                    % (item[1], item, str(pattern)))
                tracer.warning("Valid LEDs are: %s" % supported_leds)
                return False

        return True

    def clear_led_blinks(self, ignored_sample):
        self.clear_event.set()

    def set_blink_pattern(self, sample):
        v = sample.value
        l = []
        for raw in v.split(")"):
            item = raw.strip("()[], ")

            if len(item) == 0:
                continue

            try:
                elem1, elem2 = item.split(',')
            except ValueError:
                self.tracer.error(
                    "Item: %s in pattern: %s contains wrong number of elements"
                    % (raw, v))
                return

            l.append((elem1.strip(), elem2.strip()))

        p = LEDBlinkPattern(l, self.supported_leds)
        self.clear_event.set()
        self.queue.put(p)

    def do_blink_pattern(self, pattern):
        d = {}
        for led in self.supported_leds:
            d[led] = False

        for (duration, led) in pattern:
            duration = float(duration)
            led = int(led)

            if self.stop_event.is_set() or self.clear_event.is_set():
                return

            d[led] = not d[led]
            user_led_set(d[led], led)
            digitime.sleep(duration)

    def take_led_control(self):
        '''
        Take control from the OS for the LEDs, if needed.
        Returns whether we need to return control when done.

        '''
        self.tracer.info("Testing for OS Control of the LED")
        request = """
            <rci_request version="1.1">
              <query_setting>
                <led_control/>
              </query_setting>
            </rci_request>"""
        resp = rci.process_request(request)
        if resp.find("Setting group unknown") != -1:
            ## This is a platform that doesn't have OS control of the user LED.
            self.tracer.info("OS doesn't have control of LED.")
            return False
        else:
            self.tracer.info(
                "OS controls LED, configuring to be user controlled.")
            set_request = """
                <rci_request version="1.1">
                  <set_setting>
                    <led_control>
                      <network_connectivity>user</network_connectivity>
                    </led_control>
                  </set_setting>
                </rci_request>"""

            ##Disabling OS control of user LED for now.
            set_resp = rci.process_request(set_request)
            return True

    def return_led_control(self):
        if self.OS_LED_CONTROL:
            self.tracer.debug("Returning control of LED to OS")
            os_control_request = """
                <rci_request version="1.1">
                  <set_setting>
                    <led_control>
                      <network_connectivity>os</network_connectivity>
                    </led_control>
                  </set_setting>
                </rci_request>"""
            rci.process_request(os_control_request)


if __name__ == '__main__':
    p = [(.5, 1), (.5, 1), (.5, 2), (.5, 2)]
    LEDControl.verify_pattern(p)
    while 1:
        LEDControl.do_blink_pattern(p)
