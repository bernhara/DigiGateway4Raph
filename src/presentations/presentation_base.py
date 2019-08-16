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
** DIA Presentation Base**

A Presentation is an DIA module which is responsible for 
gathering sample data from channels and re-presenting the data in another 
format. Presentation_base provides a class (PresentationBase) which defines
the necessary initialization and execution methods that such a presentation
would need to implement. 

"""
# imports
from settings.settings_base import SettingsBase

# constants

# exception classes

# interface functions

# classes

class PresentationBase(SettingsBase):
    
    """
    Presentation base class.
    
    Extends :class:`~settings.settings_base.SettingsBase` to provide
    the core interface methods for an DIA presentation. All DIA
    presentations should begin by importing PresentationBase, i.e.::

        from presentations.presentation_base import PresentationBase

    At minimum, all DIA presentation modules must implement the 
    `__init__`, `start`, and `stop` methods defined below.
    
    Methods: `__init__`, `get_name`, `start`, `stop`
        
    Instance Variables: `name`
    """
    
    def __init__(self, name, settings_list):
        """Create a presentation instance, given a name and settings list."""
        self.__name = name

        ## Initialize settings:
        SettingsBase.__init__(self, 
            binding=('presentations', (name,), 'settings'),
            setting_defs=settings_list)

    ## These functions are inherited by derived classes and need not be changed:
    def get_name(self):
        """Return the name of the presentation instance."""
        return self.__name

    def start(self):
        """
        Start the presentation driver.

        Returns bool.

        """
        raise NotImplementedError, "virtual function"

    def stop(self):
        """
        Stop the presentation driver.

        Returns bool.

        """
        raise NotImplementedError, "virtual function"

 
# internal functions & classes
