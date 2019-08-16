from socket import *
import struct
import sys
import time
import digicli

TIME1970 = 2208988800L      # Thanks to F.Lundh

def GetTimeFromSNTPserver(SNTPserver):
    """Uses the SNTP protocol (as specified in RFC 2030) to contact the 
    server specified in the command line and report the time as returned
    by that server. 
    """
    client = socket(AF_INET, SOCK_DGRAM)
    data = '\x1b' + 47 * '\0'
    client.sendto( data, ( SNTPserver, 123 ))
    data, address = client.recvfrom( 1024 )
    if data:
        print 'Response received from:', address    
        t = struct.unpack( '!12I', data )[10]
        t -= TIME1970
        
    return t

def MakeDigiSetTimeString(secsSinceEpoch):
    """Given secsSinceEpoch, create string required for DigiCli SET TIME
    such as "set time date=02.29.08 time=15:23:56"
    """
    try:
        timtup = time.localtime(secsSinceEpoch)
        # yr4, mon, day, hr, min, sec, wekdy
        st = 'set time date=%02d.%02d.%02d ' % (timtup[1],timtup[2],(timtup[0]%100))
        st += 'time=%02d:%02d:%02d' % (timtup[3],timtup[4],timtup[5])
        return st
    except:
        return ""
    
def SetTimeUnix(secsSinceEpoch):
    """\
    Like time.time(), but returns int (not float) plus allows spoofing time
    """
    try:
        st = MakeDigiSetTimeString(secsSinceEpoch)
        print "st ", st
        if( sys.platform[:4] == 'digi'):
            success, response = digicli.digicli(st)
            # print 'digicli.success = ', success
            # print 'digicli.response = ', response
        else:
            print st
        return True
    except:
        return False
            
def main():

    time.sleep(5)
    
    SNTPserver = sys.argv[1]
    
    t = GetTimeFromSNTPserver(SNTPserver)
    
    success = SetTimeUnix(t)
    
    print time.ctime()
    
if __name__ == "__main__":
    main()
