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
A dynamic class loader.

Returns any object from a desired module, including within nested modules.

Based on concepts from v1.3 of
http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/223972
by Robert Brewer.

"""

import sys, types

class ClassloaderObjectNotFound(Exception):
    """Exception raised when we fail to load the requested object"""
    pass

def classloader(module_name, object_name):
    """
    Retrieve `object_name` from `module_name`, importing the module if
    necessary.

    Allows for more run-time control of the objects that are brought
    into the running system. Primarily used in the
    :class:`~common.abstract_service_manager.AbstractServiceManager`
    objects to pull in objects that they own specified by the
    settings.
    
    """
    # Get a reference to a given module...
    a_module = None
    if module_name in sys.modules:
        # ...from one that has been loaded:
        a_module = sys.modules[module_name]
    else:
        # ...by loading it dynamically:
        a_module = __import__(module_name, globals(), locals(), [''])

    obj = a_module.__dict__.get(object_name)
    if obj is None:
        raise ClassloaderObjectNotFound, \
            "cannot find '%s' in module '%s'" % (object_name, module_name)

    return obj

