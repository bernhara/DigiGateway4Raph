#!/usr/bin/env python
# Python Serial Port Extension for Win32, Linux, BSD, Jython
# module for serial IO for POSIX compatible systems, like Linux
# see __init__.py
#
# (C) 2001-2008 Chris Liechti <cliechti@gmx.net>
# this is distributed under a free software license, see license.txt
#
# parts based on code from Grant B. Edwards  <grante@visi.com>:
#  ftp://ftp.visi.com/users/grante/python/PosixSerial.py
# references: http://www.easysw.com/~mike/serial/serial.html


import sys, os, termios, struct, select, errno
from serialutil import *

TERMIOS = termios

def device(port):
    return '/com/%d' % port


class Serial(SerialBase):
    """Serial port class POSIX implementation. Serial port configuration is 
    done with termios and fcntl. Runs on Linux and many other Un*x like
    systems."""

    def open(self):
        """Open port with current settings. This may throw a SerialException
           if the port cannot be opened."""
        if self._port is None:
            raise SerialException("Port must be configured before it can be used.")
        self.fd = None
        self.mout = 0
        #open
        try:
            self.fd = os.open(self.portstr, os.O_RDWR|os.O_NONBLOCK)
        except Exception, msg:
            self.fd = None
            raise SerialException("could not open port %s: %s" % (self._port, msg))
        #~ fcntl.fcntl(self.fd, FCNTL.F_SETFL, 0)  #set blocking
        
        try:
            self._reconfigurePort()
        except:
            os.close(self.fd)
            self.fd = None
        else:
            self._isOpen = True
        #~ self.flushInput()
        
        
    def _reconfigurePort(self):
        """Set communication parameters on opened port."""
        if self.fd is None:
            raise SerialException("Can only operate on a valid port handle")
        custom_baud = None
        
        vmin = vtime = 0                #timeout is done via select
        if self._interCharTimeout is not None:
            vmin = 1
            vtime = int(self._interCharTimeout * 10)
        try:
            iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(self.fd)
        except termios.error, msg:      #if a port is nonexistent but has a /dev file, it'll fail here
            raise SerialException("Could not configure port: %s" % msg)

        #set up raw mode / no echo / binary
        iflag &= ~(TERMIOS.IGNBRK)
        iflag &= ~TERMIOS.PARMRK
        
        #setup baudrate
        try:
            ispeed = ospeed = getattr(TERMIOS,'B%s' % (self._baudrate))
        except AttributeError:
            ispeed = ospeed = getattr(TERMIOS, 'B38400')
            custom_baud = int(self._baudrate) # store for later
        
        #setup char len
        cflag &= ~TERMIOS.CSIZE
        if self._bytesize == 8:
            cflag |= TERMIOS.CS8
        elif self._bytesize == 7:
            cflag |= TERMIOS.CS7
        elif self._bytesize == 6:
            cflag |= TERMIOS.CS6
        elif self._bytesize == 5:
            cflag |= TERMIOS.CS5
        else:
            raise ValueError('Invalid char len: %r' % self._bytesize)
        #setup stopbits
        if self._stopbits == STOPBITS_ONE:
            cflag &= ~(TERMIOS.CSTOPB)
        elif self._stopbits == STOPBITS_TWO:
            cflag |=  (TERMIOS.CSTOPB)
        else:
            raise ValueError('Invalid stopit specification: %r' % self._stopbits)
        #setup parity
        iflag &= ~(TERMIOS.INPCK|TERMIOS.ISTRIP)
        if self._parity == PARITY_NONE:
            cflag &= ~(TERMIOS.PARENB|TERMIOS.PARODD)
        elif self._parity == PARITY_EVEN:
            cflag &= ~(TERMIOS.PARODD)
            cflag |=  (TERMIOS.PARENB)
        elif self._parity == PARITY_ODD:
            cflag |=  (TERMIOS.PARENB|TERMIOS.PARODD)
        else:
            raise ValueError('Invalid parity: %r' % self._parity)
        #setup flow control
        #xonxoff
        if hasattr(TERMIOS, 'IXANY'):
            if self._xonxoff:
                iflag |=  (TERMIOS.IXON|TERMIOS.IXOFF) #|TERMIOS.IXANY)
            else:
                iflag &= ~(TERMIOS.IXON|TERMIOS.IXOFF|TERMIOS.IXANY)
        else:
            if self._xonxoff:
                iflag |=  (TERMIOS.IXON|TERMIOS.IXOFF)
            else:
                iflag &= ~(TERMIOS.IXON|TERMIOS.IXOFF)
        #rtscts
        if self._rtscts:
            cflag |=  (TERMIOS.CRTSCTS)
        else:
            cflag &= ~(TERMIOS.CRTSCTS)
        
        #buffer

        #vmin "minimal number of characters to be read. = for non blocking"
#        if vmin < 0 or vmin > 255:
#            raise ValueError('Invalid vmin: %r ' % vmin)
#        cc[TERMIOS.VMIN] = vmin

        #vtime
#        if vtime < 0 or vtime > 255:
#            raise ValueError('Invalid vtime: %r' % vtime)
#        cc[TERMIOS.VTIME] = vtime

        #activate settings
        termios.tcsetattr(self.fd, TERMIOS.TCSANOW, [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])
        
        # apply custom baud rate, if any
        if custom_baud is not None:
            raise ValueError('Failed to set custom baud rate: %r' % self._baudrate)

    def close(self):
        """Close port"""
        if self._isOpen:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            self._isOpen = False

    def makeDeviceName(self, port):
        return device(port)

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    def inWaiting(self):
        """returns the number of bytes waiting to be read"""
        raise NotImplementedError  

    def read(self, size=1):
        """Read size bytes from the serial port. If a timeout is set it may
           return less characters as requested. With no timeout it will block
           until the requested number of bytes is read."""
        if self.fd is None: raise portNotOpenError
        read = ''
        inp = None
        if size > 0:
            while len(read) < size:
                #print "\tread(): size",size, "have", len(read)    #debug
                ready,_,_ = select.select([self.fd],[],[], self._timeout)
                if not ready:
                    break   #timeout
                buf = os.read(self.fd, size-len(read))
                read = read + buf
                if (self._timeout >= 0 or self._interCharTimeout > 0) and not buf:
                    break  #early abort on timeout
        return read

    def write(self, data):
        """Output the given string over the serial port."""
        if self.fd is None: raise portNotOpenError
        if not isinstance(data, str):
            raise TypeError('expected str, got %s' % type(data))
        t = len(data)
        d = data
        n = None
        while t > 0:
            try:
                if self._writeTimeout is not None and self._writeTimeout > 0:
                    _,ready,_ = select.select([],[self.fd],[], self._writeTimeout)
                    if not ready:
                        raise writeTimeoutError
                n = os.write(self.fd, d)
                if self._writeTimeout is not None and self._writeTimeout > 0:
                    _,ready,_ = select.select([],[self.fd],[], self._writeTimeout)
                    if not ready:
                        raise writeTimeoutError
                d = d[n:]
                t = t - n
            except OSError,v:
                if v.errno != errno.EAGAIN:
                    raise
        return n

    def flush(self):
        """Flush of file like objects. In this case, wait until all data
           is written."""
        self.drainOutput()

    def flushInput(self):
        """Clear input buffer, discarding all that is in the buffer."""
        if self.fd is None:
            raise portNotOpenError
        termios.tcflush(self.fd, TERMIOS.TCIFLUSH)

    def flushOutput(self):
        """Clear output buffer, aborting the current output and
        discarding all that is in the buffer."""
        if self.fd is None:
            raise portNotOpenError
        termios.tcflush(self.fd, TERMIOS.TCOFLUSH)

    def sendBreak(self, duration=0.25):
        """Send break condition. Timed, returns to idle state after given duration."""
        if self.fd is None:
            raise portNotOpenError
        termios.tcsendbreak(self.fd, int(duration/0.25))

    def setBreak(self, level=1):
        """Set break: Controls TXD. When active, to transmitting is possible."""
        # Not implemented on this platform
        raise NotImplementedError  
#        if self.fd is None: raise portNotOpenError
#        if level:
#            fcntl.ioctl(self.fd, TIOCSBRK)
#        else:
#            fcntl.ioctl(self.fd, TIOCCBRK)

    def setRTS(self, level=1):
        """Set terminal status line: Request To Send"""
        if self.fd is None: raise portNotOpenError
        if level:
            self.mout |= (termios.MS_RTS)
        else:
            self.mout &= ~(termios.MS_RTS)
        termios.tcsetsignals(self.fd, self.mout)

    def setDTR(self, level=1):
        """Set terminal status line: Data Terminal Ready"""
        if self.fd is None: raise portNotOpenError
        if level:
            self.mout |= (termios.MS_DTR)
        else:
            self.mout &= ~(termios.MS_DTR)
        termios.tcsetsignals(self.fd, self.mout)

    def getCTS(self):
        """Read terminal status line: Clear To Send"""
        if self.fd is None: raise portNotOpenError
        s = termios.tcgetstats(self.fd)[1]
        return s & termios.MS_CTS != 0

    def getDSR(self):
        """Read terminal status line: Data Set Ready"""
        if self.fd is None: raise portNotOpenError
        s = termios.tcgetstats(self.fd)[1]
        return s & termios.MS_DSR != 0

    def getRI(self):
        """Read terminal status line: Ring Indicator"""
        if self.fd is None: raise portNotOpenError
        s = termios.tcgetstats(self.fd)[1]
        return s & termios.MS_RI != 0

    def getCD(self):
        """Read terminal status line: Carrier Detect"""
        if self.fd is None: raise portNotOpenError
        s = termios.tcgetstats(self.fd)[1]
        return s & termios.MS_DCD != 0

    # - - platform specific - - - -

    def drainOutput(self):
        """internal - not portable!"""
        if self.fd is None: raise portNotOpenError
        termios.tcdrain(self.fd)

    def fileno(self):
        """For easier of the serial port instance with select.
           WARNING: this function is not portable to different platforms!"""
        if self.fd is None: raise portNotOpenError
        return self.fd

if __name__ == '__main__':
    s = Serial(0,
                 baudrate=19200,        #baudrate
                 bytesize=EIGHTBITS,    #number of databits
                 parity=PARITY_EVEN,    #enable parity checking
                 stopbits=STOPBITS_ONE, #number of stopbits
                 timeout=3,             #set a timeout value, None for waiting forever
                 xonxoff=0,             #enable software flow control
                 rtscts=0,              #enable RTS/CTS flow control
               )
    s.setRTS(1)
    s.setDTR(1)
    s.flushInput()
    s.flushOutput()
    s.write('hello')
    print repr(s.read(5))
    print s.inWaiting()
    del s

