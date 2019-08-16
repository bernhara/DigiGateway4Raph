import time
import urllib
import urllib2
import base64

NB_MESSAGES = input("NB_MESSAGES?")
i = 0
proxy_support = urllib2.ProxyHandler({"http":"http://proxy:3128"})
opener = urllib2.build_opener(proxy_support)
urllib2.install_opener(opener)
req = urllib2.Request("http://ipgwy.orbcomm.net/Authenticate?LOGIN=PangooOrbcomm&PSSWD=pangoo&VERSION=2")
handle = urllib2.urlopen(req)
retour = handle.read()
SESSION_ID = str(retour[retour.find("<SESSION_ID>") + len("<SESSION_ID>"):retour.find("</SESSION_ID>") ])
print "SESSION_ID:" + SESSION_ID

while i < NB_MESSAGES:
    DATE = str(time.time())
    message = str(i) + "test_msg_body"
    message= base64.b64encode(message)
    req = urllib2.Request("http://ipgwy.orbcomm.net/SendMessage?SESSION_ID=" + SESSION_ID + "&NETWORK_ID=3&MESSAGE_SUBJECT=my_subject&MESSAGE_BODY_TYPE=1&MESSAGE_BODY=" + message + "&MESSAGE_PRIORITY=1&DEVICE_ID=pangoom10879")   
    handle = urllib2.urlopen(req)
    print handle.read()
    i += 1
    
req = urllib2.Request("http://ipgwy.orbcomm.net/Logout?SESSION_ID=" + SESSION_ID)
handle = urllib2.urlopen(req)
print handle.read()

fin = raw_input("Type any key to exit")
