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
import os, os.path

from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

# constants
DEFAULT_FILENAME_BASE = "dia"

# classes
class SettingsDevice(DeviceBase):
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
                
        self.__settings_ctx = \
            core_services.get_service("settings_base").get_context()
    
        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)
    
        ## Settings Table Definition:
        settings_list = [ ]
    
        ## Channel Properties Definition:
        property_list = [
            # gettable and settable settings
            ChannelSourceDeviceProperty(name="format", type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.chan_set_format),

            ChannelSourceDeviceProperty(name="binding", type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.chan_set_binding),
    
            ChannelSourceDeviceProperty(name="pending_settings", type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=(DPROP_OPT_AUTOTIMESTAMP|DPROP_OPT_DONOTDUMPDATA),
                set_cb=self.chan_set_pending_settings),
                
            ChannelSourceDeviceProperty(name="filename", type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.chan_set_filename),

            # gettable only settings
            ChannelSourceDeviceProperty(name="serializers", type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="running_settings", type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=DPROP_PERM_GET,
                options=(DPROP_OPT_AUTOTIMESTAMP|DPROP_OPT_DONOTDUMPDATA)),
                
            ChannelSourceDeviceProperty(name="application_result", type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=DPROP_PERM_GET,
                options=DPROP_OPT_AUTOTIMESTAMP),
                
            # settable only settings
            ChannelSourceDeviceProperty(name="apply", type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=DPROP_PERM_SET,
                set_cb=self.chan_set_apply),
                
            ChannelSourceDeviceProperty(name="save_file", type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=DPROP_PERM_SET,
                set_cb=self.chan_set_save_file),                   
        ]
                                            
        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):
        
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        if len(rejected) or len(not_found):
            self.__tracer.error("Settings rejected/not found: %s %s",
                                rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):

        # Initialize the list of available serializers:
        self.chan_update_serializers()
        
        # Grab the first serializer from this list and make it the device
        # default channel settings format:
        default_format = (self.property_get("serializers")
                            .value
                            .split(',')[0])
        self.chan_set_format(Sample(0, default_format))

        
        self.chan_update_pending_settings()
        self.chan_update_running_settings()
        
        return True

    def stop(self):

        return True

    def chan_update_serializers(self):
        
        serializers_list = self.__settings_ctx.get_serializers()
        serializers_list = ','.join(serializers_list)
        self.property_set("serializers", Sample(0, serializers_list))

    def chan_update_running_settings(self):
        
        serializer_name = self.property_get("format").value        
        serialized_settings = self.__settings_ctx.serialize_running_registry(
                            serializer_name)
        self.property_set("running_settings", Sample(0, serialized_settings))
    
    def chan_update_pending_settings(self):
        
        serializer_name = self.property_get("format").value
        serialized_settings = self.__settings_ctx.serialize_pending_registry(
                            serializer_name)
        self.property_set("pending_settings", Sample(0, serialized_settings))    

    def chan_set_format(self, sample):
        
        serializer = sample.value
        if serializer not in self.__settings_ctx.get_serializers():
            # attempt to load the serializer
            self.__core.conditional_settings_serializer_load(
                suffix=serializer)
            # re-initialize the internal serializers list
            self.chan_update_serializers()
            
        # update the current format:
        self.property_set("format", sample)
        
        # on a format change, also update the default filename and path:
        file_ext = self.__core.serializer_file_ext_lookup(serializer)
        file_path = "%s.%s" % (DEFAULT_FILENAME_BASE, file_ext)
        file_path = os.path.join(os.getcwd(), file_path)
        self.property_set("filename", Sample(0, file_path))
        
        # re-format the displayed settings:
        self.chan_update_pending_settings()
        self.chan_update_running_settings()        
                        
    def chan_set_binding(self, sample):
        
        binding_tuple = ()
        if len(sample.value) != 0:
            binding_tuple = tuple(sample.value.split('.'))
        self.__settings_ctx.set_current_binding(binding_tuple)
        self.chan_update_pending_settings()
        self.chan_update_running_settings()
        self.property_set("binding", sample)

    def chan_set_pending_settings(self, sample):
        
        self.__settings_ctx.update_pending_registry(
            self.property_get("format").value, sample.value)
        self.chan_update_pending_settings()
  
    def chan_set_apply(self, ignored_sample):
        
        serializer_name = self.property_get("format").value
        result = self.__settings_ctx.apply_settings(serializer_name)
        # publish the result of the application of settings:
        self.property_set("application_result", Sample(0, result))
        # refresh our settings channels:
        self.chan_update_pending_settings()
        self.chan_update_running_settings() 

    def chan_set_filename(self, sample):
        
        self.property_set("filename", sample)
        
    def chan_set_save_file(self, ignored_sample):
        
        filename = self.property_get("filename").value
        serializer_name = self.property_get("format").value
        flo = open(filename, 'w')
        self.__settings_ctx.save(serializer_name, flo)
        flo.close()

        return
