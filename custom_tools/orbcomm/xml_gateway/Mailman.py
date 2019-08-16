import time
import urllib
import urllib2

proxy_support = urllib2.ProxyHandler({"http":"http://proxy:3128"})
opener = urllib2.build_opener(proxy_support)
urllib2.install_opener(opener)
req = urllib2.Request("http://ipgwy.orbcomm.net/Authenticate?LOGIN=PangooOrbcomm&PSSWD=pangoo&VERSION=2")
handle = urllib2.urlopen(req)
retour = handle.read()
SESSION_ID = str(retour[retour.find("<SESSION_ID>") + len("<SESSION_ID>"):retour.find("</SESSION_ID>") ])
print "SESSION_ID:" + SESSION_ID

MSG_FLAG = input("MSG_FLAG?")
while MSG_FLAG < 4:
    req = urllib2.Request("http://ipgwy.orbcomm.net/RetrieveMessages?SESSION_ID=" + SESSION_ID + "&NETWORK_ID=3&MSG_FLAG=" + str(MSG_FLAG) + "&SET_FLAG=0&MSG_STATUS=0&MESSAGE_ID=0&MESSAGE=1&MTAG=0")
    handle = urllib2.urlopen(req)
    list = handle.read()
    print list
    MSG_FLAG = input("MSG_FLAG?")
if MSG_FLAG == 4:
    MSG_FLAG = 2
    req = urllib2.Request("http://ipgwy.orbcomm.net/RetrieveMessages?SESSION_ID=" + SESSION_ID + "&NETWORK_ID=3&MSG_FLAG=" + str(MSG_FLAG) + "&SET_FLAG=0&MSG_STATUS=0&MESSAGE_ID=0&MESSAGE=1&MTAG=0")
    handle = urllib2.urlopen(req)
    list = handle.read()
    tab_conf = []
    while len(list) != 0:
        a = list.find("<CONF_NUM>")
        if a == -1:
            break
        cn = str(list[a + len("<CONF_NUM>"): list.find("</CONF_NUM>")])
        tab_conf.append(cn)         
        list = list[list.find("</CONF_NUM>") + len("<CONF_NUM>"):len(list)]
        print len(list)               
    
    for conf_num in tab_conf:
        req = urllib2.Request("http://ipgwy.orbcomm.net/DeleteMessage?SESSION_ID=" + SESSION_ID + "&CONF_NUM=" + str(conf_num))
        handle = urllib2.urlopen(req)
        print handle.read()
    
req = urllib2.Request("http://ipgwy.orbcomm.net/Logout?SESSION_ID=" + SESSION_ID)
handle = urllib2.urlopen(req)
print handle.read()
fin=raw_input("Type any key to exit")