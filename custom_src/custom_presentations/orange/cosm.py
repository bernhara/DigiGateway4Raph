# $Id: cosm.py 8242 2013-01-28 10:40:49Z orba6563 $

"""
COSM Presentation: https://cosm.com

"""
# imports
import threading
import digitime
import digi_httplib as httplib
import urllib

from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase

# constants

# classes
class Cosm(PresentationBase, threading.Thread):
    
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
     
        self.__stopevent = threading.Event()
        
        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)
        
        self.use_proxy = None
        self.proxy_host = None
        self.proxy_port = None
        
        # Configuration Settings:

        settings_list = [
                Setting(name="cosm_host", type=str, required=False, default_value="api.cosm.com"),
                Setting(name="cosm_key", type=str, required=True),
                Setting(name="cosm_feed_id0", type=str, required=True),                
                Setting(name="channel0", type=str, required=True),
                Setting(name="cosm_datastream0", type=str, required=True),
                Setting(name="use_proxy", type=bool, required=False, default_value=False),
                Setting(name="proxy_host", type=str, required=False),                   
                 Setting(name="proxy_port", type=int, required=False, default_value=3128),              
        ]
                                                 
        PresentationBase.__init__(self, name=name, settings_list=settings_list)
        
        self.use_proxy = SettingsBase.get_setting (self, "use_proxy")
        if self.use_proxy:
            self.proxy_host = SettingsBase.get_setting (self, "proxy_host")
            self.proxy_port = SettingsBase.get_setting (self, "proxy_port")    
            if not self.proxy_host:
                self.__tracer.warning("proxy_host configuration parameter not set. Will ignore use_proxy to false")
                self.use_proxy = False

        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)
        
        return
    
    
    def start(self):
        threading.Thread.start(self)
        return True
 
    def stop(self):
        self.__stopevent.set()
        return True

    def run(self):

        self.subscribe_write_channels()
               
        while not self.__stopevent.isSet():
            digitime.sleep(3.0)
            
        return

    def subscribe_write_channels(self):

        # 'sio' is a file-like object which reads/writes to a string
        # buffer, as seen in StringIO.py.

        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        channel0 = SettingsBase.get_setting(self, "channel0")
        
        cp.subscribe (channel0, self.cb_data_available)
        return
           
    def cb_data_available(self, channel):


        monitored_sample = channel.get()
                        
        if monitored_sample.value:
            
            self.send_to_cosm (channel.name(), monitored_sample.value)
            
        return
            
    def send_to_cosm (self, channel_name, value):
        
        self.__tracer.debug("Reveived a new sample from channel: %s" % channel_name)        

        cosm_host = SettingsBase.get_setting (self, "cosm_host")        
        cosm_key = SettingsBase.get_setting (self, 'cosm_key')
        cosm_feed_id0 = SettingsBase.get_setting (self, 'cosm_feed_id0')
        cosm_datastream0 = SettingsBase.get_setting(self, 'cosm_datastream0')
        
        if type(value) == type(float()):
            cosm_value = str(value)
        elif type(value) == type(str()):
            cosm_value = value
        elif type(value) == type(int()):
            cosm_value = str(value)
        elif type(value) == type(tuple()):
            cosm_value = urllib.quote (str(value))
        else:
            self.__tracer.error("Value type not handled: %s" % type(value))
            return

        feed_uri = "v2/feeds/%s/datastreams/%s/datapoints.csv" % (cosm_feed_id0, cosm_datastream0)

        if self.use_proxy:
            conn = httplib.HTTPConnection(host=self.proxy_host, port=self.proxy_port)
            cosm_update_url = "http://%s/%s" % (cosm_host, feed_uri)
            self.__tracer.info("Calling COSM with URL %s over http proxy %s:%d" % (cosm_update_url, self.proxy_host, self.proxy_port))
        else:
            conn = httplib.HTTPConnection(host=cosm_host)
            cosm_update_url = "/%s" % feed_uri
            self.__tracer.info("Calling COSM with URL: %s" % cosm_update_url)                   
            
        try:
            conn.putrequest('POST', url = cosm_update_url)
    
            conn.putheader('X-ApiKey', cosm_key)
            clen = len(cosm_value)
            conn.putheader('Content-Length', `clen`)
            conn.endheaders()
            

            conn.send(cosm_value)
        
            response = conn.getresponse()
            errcode = response.status
            errmsg = response.reason
            headers = response.msg
            conn.close()
        
            if errcode != 200 and errcode != 201:  
                self.__tracer.error("Request ERROR: %d %s" % (errcode, errmsg))
            else:
                self.__tracer.info("Request result: %s" % errmsg)
        except Exception, msg:
            self.__tracer.error ('Exception raised during request. Exception was: %s'%(msg))
        
        return