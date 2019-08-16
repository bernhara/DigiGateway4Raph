import urllib
import urllib2


MsgLen = input("MsgLen?")
message_body = "this message is l"
while len(message_body) < int(MsgLen) - 2:
    message_body += "o"
message_body += "ng"
print message_body
print len(message_body)
proxy_support = urllib2.ProxyHandler({"http":"http://proxy:3128"})
opener = urllib2.build_opener(proxy_support)
urllib2.install_opener(opener)
req = urllib2.Request("http://ipgwy.orbcomm.net/Authenticate?LOGIN=PangooOrbcomm&PSSWD=pangoo&VERSION=2")
handle = urllib2.urlopen(req)
retour = handle.read()
SESSION_ID = str(retour[retour.find("<SESSION_ID>") + len("<SESSION_ID>"):retour.find("</SESSION_ID>") ])
print "SESSION_ID:" + SESSION_ID

req = urllib2.Request("http://ipgwy.orbcomm.net/SendMessage?SESSION_ID=" + SESSION_ID + "&NETWORK_ID=3&MESSAGE_SUBJECT=size" + str(len(message_body)) + "&MESSAGE_BODY_TYPE=0&MESSAGE_BODY=" + message_body + "&MESSAGE_PRIORITY=1&DEVICE_ID=pangoom10879")   
print req
handle = urllib2.urlopen(req)
print handle.read()
    
req = urllib2.Request("http://ipgwy.orbcomm.net/Logout?SESSION_ID=" + SESSION_ID)
handle = urllib2.urlopen(req)
print handle.read()

fin = raw_input("Type any key to exit")
