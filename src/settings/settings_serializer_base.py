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
The settings serializer base class.

This class should be inherited from by other settings serializers if
other, custom settings serialization methods (e.g. XML, JSON, Python,
etc.) wish to be used.
"""

# imports

# constants

# exception classes

# interface functions

# classes
class SettingsSerializerBase: 
    """
    Defines the base interface class for implementing settings serializer
    objects.

    The result of load operations :meth:`load` and :meth:`loads` should
    produce a dictionary of dictionaries that may be consumed by the
    :class:`~settings.settings_base.SettingsBase` class.

    An example of this intermediary format is given below::

       {
           'devices': 
                {
                    'instance_list': 
                        [
                            {
                                'name': 'template',
                                'driver': 'TemplateDevice',
                                'settings': 
                                    {
                                        'count_init': 0,
                                        'update_rate': 1.0
                                    }
                            },

                            {
                                'name': 'template2',
                                'driver': 'TemplateDevice',
                                'settings': 
                                    {
                                        'count_init': 1024,
                                        'update_rate': 10,
                                    }
                            }
                        ]
                }
        }

        This is essentially a tree representation of the settings in
        the system.  For more information see the
        :meth:`~settings.settings_base` module.

        When performing serialization operations, it is the
        responsibility of each serializer to recognize and transform
        sequences that conform to the :ref:`instance list
        <instance_lists>` definition.
        
        """
    def load(self, flo):
        """
        Load serialized settings from a file like object.

        Returns dictionary of dictionaries.
        """
        return self.loads(flo.read())

    def loads(self, string):
        """
        Load serialized settings from a string.

        Returns dictionary of dictionaries.
        """
        raise NotImplementedError, "virtual function"

    def save(self, flo, dict_of_dicts):
        """
        Save settings to a file like object.
        """
        flo.write(self.saves(dict_of_dicts))
        flo.flush()

    def saves(self, dict_of_dicts):
        """
        Save settings to a string.
        """
        raise NotImplementedError, "virtual function"
        
    def serialize_application_result(self, application_result):
        """
        Returns a serialized representation of type str for a given
        dictionary-of-dictionaries result from
        :class:`~settings.settings_base.SettingsBase`
        :meth:`~settings.settings_base.SettingsBase.globally_apply_settings`
        method or a :class:`~settings.settings_base.SettingsContext`
        :meth:`~settings.settings_base.SettingsContext.apply_settings`
        method.
        
        """
        raise NotImplementedError, "virtual function"

# internal functions & classes
