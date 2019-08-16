#!/usr/bin/python2.4
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

import sys, os, os.path

from src.settings.settings_serializer_yaml import SettingsSerializerYaml
from src.settings.settings_serializer_py import SettingsSerializerPy

SETTINGS_SERIALIZERS_MAP = {
    'yml': SettingsSerializerYaml(),
    'yaml': SettingsSerializerYaml(),
    'pyr': SettingsSerializerPy(),
}

SETTINGS_SERIALIZERS_DESC_MAP = {
    'yml': "YAML - Yet Another Markup Language",
    'yaml': "YAML - Yet Another Markup Language",
    'pyr': "Python Representation",
}

def transform(input_path, output_path):

    input_suffix = os.path.splitext(input_path)[1][1:]
    output_suffix = os.path.splitext(output_path)[1][1:]

    if not input_suffix in SETTINGS_SERIALIZERS_MAP:
        raise Exception, "unknown serializer %s" % input_suffix
    if not output_suffix in SETTINGS_SERIALIZERS_MAP:
        raise Exception, "unknown serializer %s" % output_suffix

    input_serializer = SETTINGS_SERIALIZERS_MAP[input_suffix]
    output_serializer = SETTINGS_SERIALIZERS_MAP[output_suffix]

    input_flo = open(input_path, 'r')
    output_flo = open(output_path, 'w')

    parsed_settings = input_serializer.load(input_flo)
    output_serializer.save(output_flo, parsed_settings)

    input_flo.close()
    output_flo.close()

    return True


def get_driver_list(input_path):
    
    input_suffix = os.path.splitext(input_path)[1][1:]
    if not input_suffix in SETTINGS_SERIALIZERS_MAP:
        raise Exception, "unknown serializer %s" % input_suffix
    input_serializer = SETTINGS_SERIALIZERS_MAP[input_suffix]
    input_flo = open(input_path, 'r')

    parsed_settings = input_serializer.load(input_flo)
    input_flo.close()

    driver_list = [ ]
    def _recurse_settings(settings):
        if not settings:
            return
        elif isinstance(settings, list):
            for setting in settings:
                _recurse_settings(setting)
            return
        elif not isinstance(settings, dict):
            return

        if 'driver' in settings:
            if ':' in settings['driver']:
                driver_list.insert(0, settings['driver'].split(':')[0])

        for setting in settings:
            _recurse_settings(settings[setting])

    _recurse_settings(parsed_settings)

    return driver_list

