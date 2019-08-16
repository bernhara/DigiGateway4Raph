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
"""

# imports
from settings.settings_base import SettingsBase

# constants

# exception classes

# interface functions

# classes

class LoggerBase(SettingsBase):
    def __init__(self, name, settings_list):
        self.__name = name

        ## Initialize settings:
        SettingsBase.__init__(self, binding=('loggers', (name,), 'settings'),
            setting_defs=settings_list)

    ## These functions are inherited by derived classes and need not be changed:
    def get_name(self):
        return self.__name

    ## These functions must be implemented by the logger writer:
    def apply_settings(self):
        """\
            Called when new configuration settings are available.
       
            Must return tuple of three dictionaries: a dictionary of
            accepted settings, a dictionary of rejected settings,
            and a dictionary of required settings that were not
            found.
        """
        raise NotImplementedError, "virtual function"
 
    def start(self):
        """Start the logger driver.  Returns bool."""
        raise NotImplementedError, "virtual function"

    def stop(self):
        """Stop the logger driver.  Returns bool."""
        raise NotImplementedError, "virtual function"

    def log_event(self, logging_event):
        """Handle a new event notification"""
        raise NotImplementedError, "virtual function"

    def channel_database_get(self):
        """Return a reference to the channel database."""
        raise NotImplementedError, "virtual function"
 
# internal functions & classes

