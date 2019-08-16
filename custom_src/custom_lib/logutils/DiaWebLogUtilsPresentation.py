"""This module contains a Dia presentation driver capable of serving a web
page containing the log messages in the :class:`logging.SmartHandler` buffer.
"""

# imports
from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase
from custom_lib import logutils
import logging

logutils.basicConfig(filename='WEB/python/log.txt')
logger = logging.getLogger()
import digiweb #@UnresolvedImport

class WebLogUtils(PresentationBase):
    """This is a Dia presentation driver that makes the log messages in a
    :class:`logging.SmartHandler` handler available in a color-coded
    web page.
    
    Settings::
    
        +--------------+------+----------+---------+-------------------------+
        | Name         | Type | Required | Default | Description             |
        +==============+======+==========+=========+=========================|
        | log_url      | str  | False    | logging | The web page URL        |
        |              |      |          |         | ex: http:\\<ip>\logging |                   
        +--------------+------+----------+---------+-------------------------+
        | refresh_rate | int  | False    | 10      | The rate which the page |
        |              |      |          |         | should refresh itself in|
        |              |      |          |         | seconds                 |
        +--------------+------+----------+---------+-------------------------+
        
    Channels:
    
        None

    """
    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        self.web_cb_handle = None

        settings_list = [
            Setting(
                name='log_url', type=str, required=False, default_value='logging'),
            Setting(
                name='refresh_rate', type=int, required=False, default_value=10),
        ]

        ## Initialize settings:
        PresentationBase.__init__(self, name=name,
                                    settings_list=settings_list)

    def apply_settings(self):
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        """Registers a callback with the built-in web server for the page 
        specified by the *log_url* setting.
        """
        global web_cb_handle
        web_cb_handle = digiweb.Callback(self.page_handler)
        self.apply_settings()
        return True

    def stop(self):
        """Unregisters the callback with the built-in web server.
        """
        self.web_cb_handle = None
        return True

    def page_handler(self, type, path, headers, args):
        """The callback function that we pass the digiweb handler. 
        All web requests go through here.
        """
        url = SettingsBase.get_setting(self, 'log_url')
        if path.startswith('/'+url):
            return self.log_page(type, path, headers, args)
        return None
    
    def log_page(self, type, path, headers, args):
        """Prepares the HTML log page.
        """
        refresh_rate = SettingsBase.get_setting(self, 'refresh_rate')
        log = self.format_log()
        my_html = """<HTML><HEAD><TITLE>Gateway Log File</TITLE><META http-equiv="refresh" content="%d">
    <STYLE TYPE="text/css">div.DEBUG{color:C0C0C0}div.INFO{color:0000FF}div.WARNING{color:FFFF00}
    div.ERROR{color:FFA500}div.CRITICAL{color:FF0000}</STYLE></HEAD>
    <BODY><H1>Log Info</H1><P>%s</P></BODY></HTML>""" % (refresh_rate, log)
        return (digiweb.TextHtml, my_html)
        
    def format_log(self):
        """Formats the buffer of log messages in the :class:`SmartHandler`
        handler, if there is one installed.
        """
        rstr = ""
        formatter = logging.Formatter('<div class="%(levelname)s">%(asctime)s - %(name)s - %(message)s</div>')
        for handler in logger.handlers:
            if handler.__class__ == logutils.SmartHandler:
                for line in handler.get_formatted_buffer(formatter):
                    rstr += line
        return rstr
