############################################################################
#                                                                          #
# Copyright (c)2008, 2009 Digi International (Digi). All Rights Reserved.  #
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
Hello World presentation sample.

Modify the presentations section of dia.yml, adding the following:

presentations:
  - name: hello_world
    driver: presentations.hello_world.hello_world:HelloWorld
    settings:
        output: "Hello, World!"
"""

# imports
from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase
from core.tracing import get_tracer

import threading

# constants

# exception classes

# interface functions

# classes
class HelloWorld(PresentationBase, threading.Thread):

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

        self.__tracer = get_tracer(name)

         # Settings
         # output: the message to output to stdout

        settings_list = [
           Setting(
              name='output', type=str, required=False,
              default_value="Hello, World!"),
        ]

        PresentationBase.__init__(self, name=name,
                                   settings_list=settings_list)
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)
    
    def start(self):
        threading.Thread.start(self)
        self.apply_settings()
        return True

    def stop(self):
        return True

    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # There were problems with settings, terminate early:
            self.__tracer.error("Settings rejected/not found: %s %s",
                                rejected, not_found)
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)
        return (accepted, rejected, not_found)

    def run(self):
        print SettingsBase.get_setting(self, "output")
