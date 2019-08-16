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
Console TCP Server
"""

# imports
import SocketServer
from presentations.console.console_interface import ConsoleInterface
from select import select
import socket
import threading

# constants

## Telnet constants:
## Characters gleaned from the various (and conflicting) RFCs

NULL =            chr(0)  # No operation.
LF   =           chr(10)  # Moves the printer to the
                          # next print line, keeping the
                          # same horizontal position.
CR =             chr(13)  # Moves the printer to the left
                          # margin of the current line.
BEL =             chr(7)  # Produces an audible or
                          # visible signal (which does
                          # NOT move the print head).
BS  =             chr(8)  # Moves the print head one
                          # character position towards
                          # the left margin.
HT  =             chr(9)  # Moves the printer to the
                          # next horizontal tab stop.
                          # It remains unspecified how
                          # either party determines or
                          # establishes where such tab
                          # stops are located.
VT =             chr(11)  # Moves the printer to the
                          # next vertical tab stop.  It
                          # remains unspecified how
                          # either party determines or
                          # establishes where such tab
                          # stops are located.
FF =             chr(12)  # Moves the printer to the top
                          # of the next page, keeping
                          # the same horizontal position.
SE =            chr(240)  # End of subnegotiation parameters.
NOP=            chr(241)  # No operation.
DM =            chr(242)  # "Data Mark": The data stream portion
                          # of a Synch.  This should always be
                          # accompanied by a TCP Urgent
                          # notification.
BRK=            chr(243)  # NVT character Break.
IP =            chr(244)  # The function Interrupt Process.
AO =            chr(245)  # The function Abort Output
AYT=            chr(246)  # The function Are You There.
EC =            chr(247)  # The function Erase Character.
EL =            chr(248)  # The function Erase Line
GA =            chr(249)  # The Go Ahead signal.
SB =            chr(250)  # Indicates that what follows is
                          # subnegotiation of the indicated
                          # option.
WILL =          chr(251)  # Indicates the desire to begin
                          # performing, or confirmation that
                          # you are now performing, the
                          # indicated option.
WONT =          chr(252)  # Indicates the refusal to perform,
                          # or continue performing, the
                          # indicated option.
DO =            chr(253)  # Indicates the request that the
                          # other party perform, or
                          # confirmation that you are expecting
                          # the other party to perform, the
                          # indicated option.
DONT =          chr(254)  # Indicates the demand that the
                          # other party stop performing,
                          # or confirmation that you are no
                          # longer expecting the other party
                          # to perform, the indicated option.
IAC =           chr(255)  # Data Byte 255.

## Features

ECHO =          chr(1)    # User-to-Server:  Asks the server to send
                          # echos of the transmitted data.

                          # Server-to User:  States that the server is
                          # sending echos of the transmitted data.
                          # Sent only as a reply to ECHO or NO ECHO.

SUPGA =         chr(3)    # Supress Go Ahead
LINEMODE =      chr(34)   # Line mode negotiation, and options.
MODE   =        chr(1)
EDIT   =        chr(1)
TRAPSIG   =     chr(2)
FORWARDMASK =   chr(2)

NOECHO =        chr(131)  # User-to-Server:  Asks the server not to
                          # return echos of the transmitted data.
                          # 
                          # Server-to-User:  States that the server is
                          # not sending echos of the transmitted data.
                          # Sent only as a reply to ECHO or NO ECHO,
                          # or to end the hide your input.

# exception classes

# interface functions

# classes
class TelnetRecvDiscipline(socket.SocketType):
    STATE_INIT      = 0x0
    STATE_IN_IAC_1  = 0x1
    STATE_IN_IAC_2  = 0x2
    STATE_IN_SB     = 0x3

    def __init__(self, fromsocket, stopevent=None):
        self._sock = fromsocket
        self.__state = self.STATE_INIT
        self.stopevent = stopevent

    def recv(self, bufsize, flags=0):
        output_buf = ""
        while 1:
            r, w, e = select([self._sock], [], [], 1.0)

            # check shutdown status
            if self.stopevent and self.stopevent.isSet():
                buf = ''
                break

            if not r:
                continue
                
            buf = self._sock.recv(bufsize, flags)
            # If recv() comes back with an empty string, this indicates EOF.
            if buf == '':
                break

            # strip telnet options message from rx data stream:
            for ch in buf:
                if self.__state == self.STATE_INIT:
                    if ch == IAC:
                        self.__state = self.STATE_IN_IAC_1
                    else:
                        output_buf += ch
                elif self.__state == self.STATE_IN_IAC_1:
                    if ch == SB:
                        self.__state = self.STATE_IN_SB
                    else:
                        self.__state = self.STATE_IN_IAC_2
                elif self.__state == self.STATE_IN_IAC_2:
                    self.__state = self.STATE_INIT
                elif self.__state == self.STATE_IN_SB:
                    if ch == SE:
                        self.__state = self.STATE_INIT
            if len(output_buf):
                break
        buf = output_buf
        return buf

    def __getattr__(self, item):
        try:
            return self.__dict__[item]
        except:
            return getattr(self._sock, item)


class ConsoleTcpServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_addr, request_handler_class,
                 core, stopevent=None):
        self.__core = core
        self.stopevent = stopevent
        self.lock = threading.RLock()
        self.handlers = set()
        SocketServer.TCPServer.__init__(self, server_addr, request_handler_class)

    def get_core(self):
        return self.__core


class ConsoleTcpRequestHandler(SocketServer.BaseRequestHandler):
    def __init__(self, request, client_addr, server):
        SocketServer.BaseRequestHandler.__init__(self,
                                            request, client_addr, server)
        self.server = server

    def handle(self):
        self.server.lock.acquire()
        try:
            self.server.handlers.add(self)
        finally:
            self.server.lock.release()
        
        # Assume we have a telnet client and send some initialization:
        self.request.send(IAC+WILL+SUPGA)
        self.request.send(IAC+DO+SUPGA)
        self.request.send(IAC+WILL+ECHO)
        self.request.send(IAC+DO+LINEMODE)
        # For raw character mode, trapping signals on the client side:
        # Line endings *should be* 0x0d 0x00, but MS does not conform
        # correctly to the RFC:
        self.request.send(IAC+SB+LINEMODE+MODE+TRAPSIG+IAC+SE)
        self.request.send(IAC+SB+DONT+FORWARDMASK+IAC+SE)

        telnet_ld = TelnetRecvDiscipline(self.request, self.server.stopevent)
        cli = ConsoleInterface(input=telnet_ld, output=telnet_ld,
                                core=self.server.get_core())
        try:
            cli.cmdloop()
        except EOFError:
            pass
        except socket.error:
            pass

        self.request.close()

        self.server.lock.acquire()
        try:
            self.server.handlers.remove(self)
        finally:
            self.server.lock.release()

    def finish(self):
        # No special termination handling required.
        pass
 
# internal functions & classes

