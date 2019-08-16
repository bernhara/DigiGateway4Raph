############################################################################
#                                                                          #
# Copyright (c)2008-2010, Digi International (Digi). All Rights Reserved.  #
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
from common.abstract_service_manager import AbstractServiceManager

# constants

# exception classes

# interface functions

# classes

class DeviceDriverManager(AbstractServiceManager):
    """
    Manages the loading and instances of individual rivers.

    The DeviceDriverManager allows for the dynamic loading of device
    drivers as well as the ability to retrieve an instance of a device
    driver by name. The DeviceDriverManager also provides an interface to
    query a device for its configuration parameters and device properties.

    """
    
    def __init__(self, core_services):
        self.__core = core_services
        self.__core.set_service("device_driver_manager", self)

        # Initialize our base class:
        AbstractServiceManager.__init__(self, core_services, ('devices',))

    def driver_load(self, name):
        """
        Loads a driver dynamically.

        If the driver has not been loaded previously, an unconfigured
        instance of the driver will be created and managed by the
        DeviceDriverManager. If the driver has already been loaded
        nothing will be done. In either case, this function will
        return True. If the driver cannot be loaded for any reason, an
        exception will be raised.
        
        """
        
        return AbstractServiceManager.service_load(self, name)

    def instance_properties_get(self, instancename):
        """Get the properties of a given driver instance."""
        
        driver_instance = self.instance_get(instancename)
        return driver_instance.get_properties()


# internal functions & classes
