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
DigiWeb Embedded Web presentation
"""

# imports
from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase
import sys, traceback
import digiweb
from StringIO import StringIO
from string import Template
import time
import cgi 
from presentations.embedded_web.index_page import raw_html
import presentations.embedded_web.pyhtml as pyhtml

class Web(PresentationBase):
    
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
		
        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        # Settings:
        #
        # page: The path location to access this presentation.
        # exclude: List of strings. Channels matching the strings will not be
        #    displayed.  
        
        settings_list = [
            Setting(
                name='page', type=str, required=False,
                default_value='/idigi_dia'),
            Setting(
                name='exclude', type=list, required=False, default_value=[]),
        ]

        ## Initialize settings:
        PresentationBase.__init__(self, name=name,
                                    settings_list=settings_list)

    def apply_settings(self):    

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)
        if len(rejected) or len(not_found):
            self.__tracer.error("Settings rejected/not found: %s %s", 
                                rejected, not_found)

        if accepted['page'].startswith('/'):
            # trim leading / if present:
            accepted['page'] = accepted['page'][1:]

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        self._cb_handle = digiweb.Callback(self.cb)

    def stop(self):
        del self._cb_handle

    def cb(self, typer, path, headers, args):

       tmp = {}
       if typer=="POST" or typer=="post":
           tmp = cgi.parse_qs(args)
           args=tmp
           for key in args:
               args[key] = args[key][0]
       page_setting = SettingsBase.get_setting(self, 'page')
       if path != ('/' + page_setting):
            return None
       try:
        if args==None or args["controller"]==None or args["controller"]=="index":
            return (digiweb.TextHtml,raw_html)

        cm = self.__core.get_service("channel_manager").channel_database_get()
        channel_list = cm.channel_list()
        channel_list.sort()
        table = dict()
        for entry in channel_list:
            if entry in SettingsBase.get_setting(self, 'exclude'):
                continue
            device, channel_name = entry.split('.')
            channel = cm.channel_get(entry)

            if not table.has_key(device):
                table[device] = list()
                
            try:
                sample = channel.get()
                table[device].append((channel_name, sample.value, channel))
            except:
                table[device].append((channel_name, "(N/A)", "", "",))
        sorted_table = list()
        for key in table.keys():
            sorted_table.append((key, table[key]))
            sorted_table.sort(key = lambda x: x[0])

        py_code= getattr(pyhtml,args["controller"])(locals())
        return (digiweb.TextHtml,py_code.getvalue())
       except Exception,e:
         import traceback
         return (digiweb.TextHtml,traceback.format_exc())
