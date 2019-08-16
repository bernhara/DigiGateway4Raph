# $Id: uploadVersionToGWOverIDigi.py 8153 2013-01-15 11:58:59Z orba6563 $

traceFlagSet = False

def trace (msg):
    if (traceFlagSet):
        print msg

from optparse import OptionParser
import httplib
import urllib
import urllib2
import base64 
import sys


_UK_IDIGI_HOST = "my.idigi.co.uk"
_UK_IDIGI_PORT = 80
_DEFAULT_PROXY_URL = "http://proxy.rd.francetelecom.fr:3128"

# The following lines require manual changes 
_DEFAULT_USERNAME = "pangoocagnes"
_DEFAULT_PASSWORD = "Pangoo@06921"
_DEFAULT_FILE_LIST = ["dia.py", "dia.zip", "dia-pangoo-ao5072.yml", "dia-pangoo-idigi.yml", "PangooDiaGW.py"]
_DEFAULT_IDIGI_TAG = "PangooCagnes"


def main():
    parser = OptionParser()
    parser.add_option("--iDigiHost", dest="iDigiHost", type="string", default=_UK_IDIGI_HOST, help="iDigi cloud host name")
    parser.add_option("--iDigiPort", dest="iDigiPort", type="int", default=_UK_IDIGI_PORT, help="iDigi cloud host port number")
    parser.add_option("--iDigiUser", dest="iDigiUser", type="string", default=_DEFAULT_USERNAME, help="iDigi cloud login username")
    parser.add_option("--iDigiPassword", dest="iDigiPassword", type="string", default=_DEFAULT_PASSWORD, help="iDigi cloud login password")
    
    parser.add_option("--gateway", dest="gatewayList", action="append", type="string", help="target gateway(s) to send files to")
    parser.add_option("--file", dest="fileList", action="append", type="string", help="file(s) to send to gateway(s)")
    parser.add_option("--basedir", dest="basedir", type="string", help="base directory on iDigi file storage")
    parser.add_option("--iDigiTag", dest="iDigiTag", type="string", help="Targets devices with TAG as fixed in iDigi")

    
    parser.add_option("--noProxy", action="store_false", dest="noProxy", help="if set, uses the HTTP proxy configuration")    
    
    parser.add_option("--proxyUrl", dest="proxyUrl", type="string", default=_DEFAULT_PROXY_URL, help="Url of HTTP proxy to use")
    
    parser.add_option("--debug", action="store_true", dest="debugFlag",
                      help="if set, activate traces")    
    
    (options, args) = parser.parse_args()
    
    bad_args = False
    if (not options.basedir):
        bad_args = True
        
    # at leat iDigiTag arg ot gatewayList must be specified
    if (not options.gatewayList) and (not options.iDigiTag):
        bad_args = True
    
    if (len(args) != 0 or bad_args):
        parser.print_help()
        sys.exit (1)
    
    traceFlagSet = (options.debugFlag == True)
    
    trace (options)
    trace (args)
    
    sciTargetList = None
    if not sciTargetList and options.iDigiTag:
        sciTargetList = "<device tag=\"%s\"/>" % options.iDigiTag

    if not sciTargetList and options.gatewayList:
        sciTargetList = ""
        for gw in options.gatewayList:
            sciTargetList += "<device id=\"%s\"/>" % gw     
        
    if not options.fileList:
        fileList = _DEFAULT_FILE_LIST
    else:
        fileList = options.fileList
        
    sciCommandList = ""
    for file_name in fileList:
        sciCommandList += "<put_file path=\"/WEB/python/" + file_name + "\"> <file>" + options.basedir + "/" + file_name + "</file> </put_file>"

    # message to send to server
    message = """<sci_request version="1.0">
      <file_system>
        <targets>
        """ \
        + sciTargetList \
        + """
        </targets>
        <commands>
        """ \
        + sciCommandList \
        + """
         </commands>
      </file_system>
    </sci_request>"""
            
    iDigiUrl = "http://%s:%d" % (options.iDigiHost, options.iDigiPort)
    iDigiSciUrl = iDigiUrl + "/ws/sci"
    
    opener = urllib2.build_opener()

    if options.noProxy:
        pass
    else:
        proxy_handler = urllib2.ProxyHandler({'http': options.proxyUrl})
        opener.add_handler (proxy_handler)
    
    # ...and install it globally so it can be used with urlopen.
    urllib2.install_opener(opener)
    
    req_headers = {"Content-type" : "text/xml; charset=\"UTF-8\""}
    
    request = urllib2.Request (url = iDigiSciUrl, data = message)
    
    # Content-Type
    request.add_header("Content-type", "text/xml; charset=\"UTF-8\"")
    
    # Authorization
    auth = base64.encodestring("%s:%s"%(options.iDigiUser,options.iDigiPassword))[:-1]                
    request.add_header("Authorization", "Basic %s"%auth)    

    try:
        print "Start operation"
        f = urllib2.urlopen(request)
        print "operation done"
        print "Result: %s" % f.read()
    except urllib2.HTTPError, e:
        print >> sys.stderr, "Error: %s" % e
        print >> sys.stderr,  e.read()
        sys.exit (1)
                   
    return (0)

#
# Main
#          
            
if __name__ == '__main__':
    status = main()
    sys.exit(status)
