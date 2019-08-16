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
Digi Web Presentation
"""

# imports
import sys
import traceback  # , cgi #os.path
import digitime
import time  # we need this for strftime and localtime
#import SocketServer

# TODO: Try to segment imports.  If using digiweb, we don't need a lot of this.
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import socket

from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase
from StringIO import StringIO
import presentations.web.web_files as web_files
from presentations.web.stylesheet import stylesheet_css
from presentations.web.jsonify import mkJson as json
try:
    from digiweb import *
except:
    pass
from channels.channel import \
    PERM_GET, PERM_SET, PERM_REFRESH, \
    OPT_AUTOTIMESTAMP, OPT_DONOTLOG, OPT_DONOTDUMPDATA
from samples.sample import Sample
import threading
from select import select

REFRESHALL = 'refresh_all'

class WebRequestHandler(BaseHTTPRequestHandler):
    """
    Handles web requests from digiweb or from own hosted HTTP server.
    """

    def do_GET(self):
        """
        Function is invoked when you do a GET request.
        It gets channels list and writes html with data on page.
        """
        try:
            is_digi = False  # sys.platform.startswith('digi')
            page = self.server.get_page()

            if self.path.endswith(page) or \
                not is_digi and self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Expires', '-1')
                self.end_headers()
                self.wfile.write(web_files.html % {"page": page,
                                        "title": self.server.get_title()})
            elif not is_digi and self.path.endswith("stylesheet.css"):
                self.send_response(200)
                self.send_header('Content-type', 'text/css')
                self.end_headers()
                self.wfile.write(stylesheet_css)
            elif not is_digi and self.path.find('?') > 0:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Expires', '-1')
                self.end_headers()
                self.wfile.write(self.server.get_table(
                    self.path[self.path.find('?') + 1:]))
            return
        except IOError:
            self.send_error(404, 'File Not Found: %s' % self.path)


def gethostbyaddr(ip_addr):
    #Workaround for no 'gethostbyaddr()' on the ConnectPort
    return ip_addr, [], [ip_addr]

socket.gethostbyaddr = gethostbyaddr

class Web(PresentationBase, HTTPServer, threading.Thread):
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

        import core.tracing as tracing
        self.__tracer = tracing.get_tracer(name)

        # Settings:
        #
        # page: name of presented web page
        # port: port to use.  digiweb ignores this and uses port 80.
        # polling: how frequently to request an update from the server
        #     (passed to javascript in the browser)
        # use_default_httpserver: use digiweb on the ConnectPort,
        #     BaseHTTPServer on other platforms.  If false, always use
        #     BaseHTTPServer.
        # title: set the title of the web page

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='page', type=str, required=False, default_value='index'),
            Setting(
                name='port', type=int, required=False, default_value=8001),
            Setting(
                name='polling', type=int, required=False, default_value=0),
            Setting(
                name='use_default_httpserver',
                type=bool, required=False, default_value=True),
            Setting(
                name='title', type=str, required=False,
                        default_value='DIA Web Presentation'),
        ]
        ## Initialize settings:
        PresentationBase.__init__(self, name=name,
                        settings_list=settings_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    def start(self):

        # If the use_default_httpserver setting is specified,
        # the presentation will  start own http server on the specified port.
        isDefault = SettingsBase.get_setting(self, 'use_default_httpserver')
        if not globals().has_key('Callback'):
            isDefault = False

        if isDefault:
            self._cb_handle = Callback(self.cb)
            self.__tracer.info("using web page %s and"
                   " using digiweb", self.get_page())
        else:
            self._cb_handle = self.get_channels
            try:
                port = SettingsBase.get_setting(self, 'port')
                self.__tracer.info("using port %d and BaseHTTPServer", port)

                HTTPServer.__init__(self, ('', port), WebRequestHandler)
            except Exception:
                self.__tracer.debug(traceback.format_exc())
                self.socket.close()
            # Only start a thread if the Python web-server is
            # used:
            threading.Thread.start(self)

    def stop(self):
        self.__stopevent.set()
        return True

    def run(self):
        try:
        # Poll the stop event flag at a minimum of each second:
            while not self.__stopevent.isSet():
                rl, wl, xl = select([self.socket], [], [], 1.0)
                if self.socket in rl:
                    self.handle_request()
        except Exception, e:
            self.__tracer.error("Exception occurred during http request: %s",
                    str(e))
            self.__tracer.debug(traceback.format_exc())

        if hasattr(self, 'socket') and self.socket is not None:
            self.socket.close()
        del self._cb_handle

    def cb(self, type, path, headers, args):
        page = self.get_page()
        if path.endswith(page) and not args:
            return(TextHtml, '\r\n'.join(
                (web_files.html % {"page":page,
                                   "title":self.get_title()}
                 ).split('\n')))
        elif path.endswith(page) and args:
            refresh_all = self.handle_args_list(args)
            return (TextPlain, self.get_table(refresh_all))
        else:
            return None

    def iso_date(self, t=None):

        # Optional argument 't' is a string with the date in seconds,
        # which defaults to the current time if not specified.

        if t is None:
            t = digitime.time()
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))

        return time_str

    def get_title(self):
        return SettingsBase.get_setting(self, 'title')

    def get_page(self):
        return SettingsBase.get_setting(self, 'page')

    def get_channel(self, channel_name):
        try:
            cm = self.__core.get_service("channel_manager")
            cdb = cm.channel_database_get()
            channel = cdb.channel_get(channel_name)
            return channel.get()
        except Exception:
            self.__tracer.debug(traceback.format_exc())

    def set_channel(self, channel_name, value):
        try:
            cm = self.__core.get_service("channel_manager")
            cdb = cm.channel_database_get()
            channel = cdb.channel_get(channel_name)
            try:
                typing_value = channel.type()(value)
            except Exception:
                self.__tracer.debug(traceback.format_exc())
                return
            channel.consumer_set(Sample(digitime.time(), typing_value))
        except Exception:
            self.__tracer.debug(traceback.format_exc())

    def refresh_channel(self, channel_name):
        try:
            cm = self.__core.get_service("channel_manager")
            cdb = cm.channel_database_get()
            channel = cdb.channel_get(channel_name)
            channel.consumer_refresh()
        except Exception:
            self.__tracer.debug(traceback.format_exc())

    def get_channels(self):
        table = []
        cm = self.__core.get_service("channel_manager")
        cdb = cm.channel_database_get()
        channel_list = cdb.channel_list()
        channel_list.sort()
        for channel_name in channel_list:
            sample = { 'channel_name': channel_name }
            try:
                channel = cdb.channel_get(channel_name)
                if channel.options_mask() & OPT_DONOTDUMPDATA:
                    raise Exception, "honoring do not dump"
                sample_val = channel.get()
                sample['timestamp'] = sample_val.timestamp
                sample['value'] = sample_val.value
                sample['permission'] = channel.perm_mask()
            except Exception:
                sample['timestamp'] = 0
                sample['value'] = "Not Available"
                sample['permission'] = 0x0
            if sample['timestamp'] > 0:
                sample['timestamp'] = self.iso_date(sample['timestamp'])
            else:
                sample['timestamp'] = "None"

            table.append(sample)
        return table

    def handle_args_list(self, args):
        for channel, value in args.items():
            retval = ''
            if channel:
                try:
                    self.set_channel(channel, args[channel])
                except:
                    self.__tracer.debug(traceback.format_exc())
            elif value == REFRESHALL:
                retval = '=%s' % REFRESHALL
        return retval

    def get_table(self, args):
        
        def unescape(txt):
            words = txt.split('%')
            for i in range(1, len(words)):
                char = chr(int(words[i][:2],16))
                words[i] = char + words[i][2:].replace('+', ' ')
            return ''.join(words)

        refresh_all = False
        if args:
            argpairs = [s2 for s1 in args.split('&') for s2 in s1.split(';')]
            argslist = [tuple(kv.split('=')) for kv in argpairs]
            for kv in argslist:
                if len(kv) == 2:
                    key, val = kv
                elif len(kv) == 1:
                    key, = kv
                    val = ''
                else:
                    key, val = "", "kv: len==%d, should be 1 or 2" % len(kv)
                if key:
                    channel = unescape(key)
                    value = unescape(val)
                    self.set_channel(channel, value)
                else:
                    refresh_all = val == REFRESHALL
                        
        data_table = {'settings': {}}
        try:
            data_table['settings']['polling'] =\
                SettingsBase.get_setting(self, 'polling')
        except:
            data_table['settings']['polling'] = 0
        cm = self.__core.get_service("channel_manager")
        cdb = cm.channel_database_get()
        channel_list = cdb.channel_list()
        channel_list.sort()
        old_device = ''
        devices = []
        data_table['devices'] = devices
        for channel_name in channel_list:
            #sample = { 'channel_name': channel_name }
            device, name = channel_name.split('.', 1)
            if device != old_device:
                old_device = device
                devices.append({})
                db,=devices[-1:]
                db['name'] = device
                db['channels'] = []
            try:
                channel = cdb.channel_get(channel_name)
                perm = channel.perm_mask()
                options = channel.options_mask()
                if (perm & PERM_GET and
                    not options & OPT_DONOTDUMPDATA):
                    sample = channel.get()
                else:
                    sample = Sample(0, 0)
                if refresh_all and (perm & PERM_REFRESH):
                    self.refresh_channel(channel_name)
                if sample.timestamp > 0:
                    timestr = self.iso_date(sample.timestamp)
                else:
                    timestr = "None"
                db['channels'].append({'name':name,
                    'value':sample.value,
                    'time':timestr,
                    'perm':channel.perm_mask(),
                    'unit':sample.unit})
            except Exception:
                self.__tracer.error("exception on channel_name '%s': %s",
                                    channel_name, traceback.format_exc())

        return json(data_table.__repr__() + '\n')

        # Structure of returned dict is as follows::
        #
        #    {
        #        'settings': {'polling': 1, ...}, # Other to be defined
        #        'devices': [
        #            {
        #                'name': 'foo_device',
        #                'channels': [
        #                    {'name': 'foo', 'value': 'Bar',
        #                    'time': '2002-01-01 00:36:49',
        #                    'perm': 7 # from permissions mask, OPT*
        #                },
        #                ...
        #            },
        #            ...
        #        ]
        #    }
