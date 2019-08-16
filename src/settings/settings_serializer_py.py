############################################################################
#                                                                          #
# Copyright (c)2008, Digi International (Digi). All Rights Reserved.       #
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
Python Representation Settings Serializer for DIA.
"""

# imports
from copy import copy
from settings_serializer_base import SettingsSerializerBase
from pprint import pformat, isreadable

# constants

# exception classes

# interface functions

# classes
class SettingsSerializerPy(SettingsSerializerBase):
    """
    Implements interface specified by
    :class:`~settings.settings_serializer_base.SettingsSerializerBase`
    for a saved Python syntax representation of settings.

    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.

    """
    
    def __is_instance_list(self, suspect_list):
        # Is this a list?
        if not isinstance(suspect_list, list):
            return False

        # If the list is empty, then it cannot possibly be an Instance List.
        if len(suspect_list) == 0:
            return False

        # Does each list item contain a dictionary with a key called name?
        if not reduce(lambda t, d: t and \
                        isinstance(d, dict) and "name" in d,
                            suspect_list, True):
            return False

        return True

    def __reparse_instances(self, input_tree):
        """
        Transforms a raw settings tree from the parser into one
        suitable for use in the settings system.  Returns a new tree.

        The raw settings tree may contain lists of dictionaries all
        containing the key "name".  Such lists are known as
        "instance lists" as they define an instance which will be
        instantiated in the running system.

        When an instance list is encountered it will be re-rooted
        to be inside of a dictionary with a single key called
        'instance_list'.

        To describe this another way, this:

        {
            'devices': \
                 [
                     {
                         'name': 'template',
                         'driver': TemplateDevice,
                         'settings: \
                             {
                                 'count_init': 0,
                                 'update_rate': 1.0
                             }
                     },

                     {
                         'name': 'template2',
                         'driver': TemplateDevice,
                         'settings: \
                             {
                                 'count_init': 1024,
                                 'update_rate': 10,
                             }
                     }
                 ]
        }

        Will be transformed to:
        {
            'devices': \
                 {
                     'instance_list': \
                         {
                             {
                                 'name': 'template',
                                 'driver': TemplateDevice,
                                 'settings: \
                                     {
                                         'count_init': 0,
                                         'update_rate': 1.0
                                     }
                             },

                             {
                                 'name': 'template2',
                                 'driver': TemplateDevice,
                                 'settings: \
                                     {
                                         'count_init': 1024,
                                         'update_rate': 10,
                                     }
                             }
                         }
                 }
        }
        """

        def recursive_parse(input_tree_ref):
            if isinstance(input_tree_ref, dict):
                output_subtree = { }
                for key in input_tree_ref:
                    if self.__is_instance_list(input_tree_ref[key]):
                        output_subtree[key] = { }
                        output_subtree[key]["instance_list"] = [ ]
                        for instance in input_tree_ref[key]:
                            output_subtree[key]["instance_list"].append(
                                recursive_parse(instance))

                    else:
                        # Absolutely, positively assert that all strings
                        # are non-unicode:
                        if isinstance(input_tree_ref[key], unicode):
                            input_tree_ref[key] = str(input_tree_ref[key])
                        output_subtree[key] = \
                            recursive_parse(input_tree_ref[key])

                return output_subtree
            elif isinstance(input_tree_ref, list):
                # detect a bare instance_list object:
                if self.__is_instance_list(input_tree_ref):
                    return { 'instance_list': input_tree_ref }
                else:
                    return input_tree_ref
            else:
                return input_tree_ref

        return recursive_parse(input_tree)

    
    def __remove_instances(self, input_tree):
        """
        This function will transform all 'instance_list' instances
        back into raw lists for re-serialization by the serializer.
        It will return a new tree.

        This is the inverse function to __reparse_instances().
        """

        def recursive_parse(input_tree_ref):
            if isinstance(input_tree_ref, dict):
                output_object = None
                if 'instance_list' in input_tree_ref:
                    output_object = [ ]
                    for instance in input_tree_ref['instance_list']:
                        output_object.append(recursive_parse(instance))
                else:
                    output_object = { }
                    for key in input_tree_ref:
                        output_object[key] = \
                            recursive_parse(input_tree_ref[key])
                return output_object
            else:
                return input_tree_ref

        return recursive_parse(input_tree)
            

    # SettingsSerializerBase interface functions
    
    def loads(self, a_string):
        # It has been observed that mixed-line endings cause trouble,
        # this is the easiest way to ensure only one line ending style
        # is in use:
        a_string = a_string.replace('\r\n', '\n')
        exec a_string in globals()  # side-effect, creates settings variable
        parsed_obj = self.__reparse_instances(settings)

        return parsed_obj

    def saves(self, dict_of_dicts):
        return ("settings = (" +
                    pformat(self.__remove_instances(dict_of_dicts)) +
                    ")")

    def serialize_application_result(self, application_result):
        return repr(application_result)

    # End SettingsSerializerBase interface functions
    
# internal functions & classes
