#! /usr/bin/env python

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

'''
SMTP/ESMTP client class.

This should follow RFC 821 (SMTP) and RFC 1869 (ESMTP).

Notes:

Please remember, when doing ESMTP, that the names of the SMTP service
extensions are NOT the same thing as the option keywords for the RCPT
and MAIL commands!

Example:

  >>> import smtplib
  >>> s=smtplib.SMTP("localhost")
  >>> print s.help()
  This is Sendmail version 8.8.4
  Topics:
      HELO    EHLO    MAIL    RCPT    DATA
      RSET    NOOP    QUIT    HELP    VRFY
      EXPN    VERB    ETRN    DSN
  For more info use "HELP <topic>".
  To report bugs in the implementation send email to
      sendmail-bugs@sendmail.org.
  For local information send email to Postmaster at your site.
  End of HELP info
  >>> s.putcmd("vrfy","someone@here")
  >>> s.getreply()
  (250, "Somebody OverHere <somebody@here.my.org>")
  >>> s.quit()
'''

# Author: The Dragon De Monsyne <dragondm@integral.org>
# ESMTP support, test code and doc fixes added by
#     Eric S. Raymond <esr@thyrsus.com>
# Better RFC 821 compliance (MAIL and RCPT, and CRLF in data)
#     by Carey Evans <c.evans@clear.net.nz>, for picky mail servers.
# Digi device compliance (replace getfqdn* calls with get_host calls
# when on digi platform)
#     by Max Kotasek (mkotasek@digi.com)
# This was modified from the Python 1.5 library HTTP lib.

import socket
import re
import rfc822
import sys

__all__ = ["SMTPException", "SMTPServerDisconnected",
           "SMTPResponseException", "SMTPSenderRefused",
           "SMTPRecipientsRefused", "SMTPDataError",
           "SMTPConnectError", "SMTPHeloError", "quoteaddr",
           "quotedata", "SMTP"]

SMTP_PORT = 25
CRLF = "\r\n"


# Exception classes used by this module.
class SMTPException(Exception):
    """Base class for all exceptions raised by this module."""


class SMTPServerDisconnected(SMTPException):
    """Not connected to any SMTP server.

    This exception is raised when the server unexpectedly disconnects,
    or when an attempt is made to use the SMTP instance before
    connecting it to a server.
    """


class SMTPResponseException(SMTPException):
    """Base class for all exceptions that include an SMTP error code.

    These exceptions are generated in some instances when the SMTP
    server returns an error code.  The error code is stored in the
    `smtp_code` attribute of the error, and the `smtp_error` attribute
    is set to the error message.
    """

    def __init__(self, code, msg):
        self.smtp_code = code
        self.smtp_error = msg
        self.args = (code, msg)


class SMTPSenderRefused(SMTPResponseException):
    """Sender address refused.
    In addition to the attributes set by on all SMTPResponseException
    exceptions, this sets `sender` to the string that the SMTP refused.
    """

    def __init__(self, code, msg, sender):
        self.smtp_code = code
        self.smtp_error = msg
        self.sender = sender
        self.args = (code, msg, sender)


class SMTPRecipientsRefused(SMTPException):
    """All recipient addresses refused.
    The errors for each recipient are accessible through the attribute
    'recipients', which is a dictionary of exactly the same sort as
    SMTP.sendmail() returns.
    """

    def __init__(self, recipients):
        self.recipients = recipients
        self.args = (recipients,)


class SMTPDataError(SMTPResponseException):
    """The SMTP server didn't accept the data."""


class SMTPConnectError(SMTPResponseException):
    """Error during connection establishment."""


class SMTPHeloError(SMTPResponseException):
    """The server refused our HELO reply."""


def quoteaddr(addr):
    """Quote a subset of the email addresses defined by RFC 821.

    Should be able to handle anything rfc822.parseaddr can handle.
    """
    m = None
    try:
        m = rfc822.parseaddr(addr)[1]
    except AttributeError:
        pass
    if not m:
        #something weird here.. punt -ddm
        return addr
    else:
        return "<%s>" % m


def quotedata(data):
    """Quote data for email.

    Double leading '.', and change Unix newline '\\n', or Mac '\\r' into
    Internet CRLF end-of-line.
    """
    return re.sub(r'(?m)^\.', '..',
        re.sub(r'(?:\r\n|\n|\r(?!\n))', CRLF, data))


def get_host():
  import digicli
  (flag, response) = digicli.digicli('set host')

  if flag:
    for line in response:
      line = line.strip()
      line = line.lower()

      if line.startswith('name'):
        hostname = line.split(':', 1)[1]
        hostname = hostname.strip()

        ##Special string indicating hostname was not set
        if hostname == '(not set)' or len(hostname) == 0:
          return None

        return hostname
    else:
      raise ValueError("Unable to locate the hostname field in the returned response")
  else:
    raise ValueError("Received error when querying device for hostname")


class SMTP:
    """
    This class manages a connection to an SMTP or ESMTP server.
    SMTP Objects:
        SMTP objects have the following attributes:
            helo_resp
                This is the message given by the server in response to the
                most recent HELO command.

            ehlo_resp
                This is the message given by the server in response to the
                most recent EHLO command. This is usually multiline.

            does_esmtp
                This is a True value _after you do an EHLO command_*, if the
                server supports ESMTP.

            esmtp_features
                This is a dictionary, which, if the server supports ESMTP,
                will _after you do an EHLO command_*, contain the names of the
                SMTP service extensions this server supports, and their
                parameters (if any).

                Note, all extension names are mapped to lower case in the
                dictionary.

        See each method's docstrings for details.  In general, there
        is a method of the same name to perform each SMTP command.
        There is also a method called 'sendmail' that will do an
        entire mail transaction.
        """
    debuglevel = 0
    file = None
    helo_resp = None
    ehlo_resp = None
    does_esmtp = 0

    def __init__(self, host = '', port = 0, localhost = None):
        """Initialize a new instance.

        If specified, `host` is the name of the remote host to which to
        connect.  If specified, `port` specifies the port to which to connect.
        By default, smtplib.SMTP_PORT is used.  An SMTPConnectError is raised
        if the specified `host` doesn't respond correctly.

        """

        if localhost is not None:
          self.localhost = localhost
        else:
          fqdn = socket.getfqdn()
          if '.' in fqdn:
            self.localhost = fqdn
          else:
            addr = '127.0.0.1'
          try:
            addr = socket.gethostbyname(socket.gethostname())
          except socket.gaierror:
            pass
          self.localhost = '[%s]' % addr

        self.esmtp_features = {}
        if host:
            (code, msg) = self.connect(host, port)
            if code != 220:
                raise SMTPConnectError(code, msg)

    def set_debuglevel(self, debuglevel):
        """Set the debug output level.

        A non-false value results in debug messages for connection and for all
        messages sent to and received from the server.

        """
        self.debuglevel = debuglevel

    def connect(self, host='localhost', port = 0):
        """Connect to a host on a given port.

        If the hostname ends with a colon (`:`) followed by a number, and
        there is no port specified, that suffix will be stripped off and the
        number interpreted as the port number to use.

        Note: This method is automatically invoked by __init__, if a host is
        specified during instantiation.

        """
        if not port:
            i = host.find(':')
            if i >= 0:
                host, port = host[:i], host[i+1:]
                try: port = int(port)
                except ValueError:
                    raise socket.error, "nonnumeric port"
        if not port: port = SMTP_PORT
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.debuglevel > 0: print 'connect:', (host, port)
        try:
            self.sock.connect((host, port))
        except socket.error:
            self.close()
            raise
        (code,msg)=self.getreply()
        if self.debuglevel >0 : print "connect:", msg
        return (code,msg)

    def send(self, str):
        """Send `str` to the server."""
        if self.debuglevel > 0: print 'send:', `str`
        if self.sock:
            try:
                sendptr = 0
                while sendptr < len(str):
                    sendptr = sendptr + self.sock.send(str[sendptr:])
            except socket.error:
                raise SMTPServerDisconnected('Server not connected')
        else:
            raise SMTPServerDisconnected('please run connect() first')

    def putcmd(self, cmd, args=""):
        """Send a command to the server."""
        if args == "":
            str = '%s%s' % (cmd, CRLF)
        else:
            str = '%s %s%s' % (cmd, args, CRLF)
        self.send(str)

    def getreply(self):
        """Get a reply from the server.

        Returns a tuple consisting of:

          - server response code (e.g. '250', or such, if all goes well)
            Note: returns -1 if it can't read response code.

          - server response string corresponding to response code (multiline
            responses are converted to a single, multiline string).

        Raises SMTPServerDisconnected if end-of-file is reached.
        """
        resp=[]
        if self.file is None:
            self.file = self.sock.makefile('rb')
        while 1:
            line = self.file.readline()
            if line == '':
                self.close()
                raise SMTPServerDisconnected("Connection unexpectedly closed")
            if self.debuglevel > 0: print 'reply:', `line`
            resp.append(line[4:].strip())
            code=line[:3]
            # Check that the error code is syntactically correct.
            # Don't attempt to read a continuation line if it is broken.
            try:
                errcode = int(code)
            except ValueError:
                errcode = -1
                break
            # Check if multiline response.
            if line[3:4]!="-":
                break

        errmsg = "\n".join(resp)
        if self.debuglevel > 0:
            print 'reply: retcode (%s); Msg: %s' % (errcode,errmsg)
        return errcode, errmsg

    def docmd(self, cmd, args=""):
        """Send a command, and return its response code."""
        self.putcmd(cmd,args)
        return self.getreply()

    # std smtp commands
    def helo(self, name=''):
        """SMTP 'helo' command.
        Hostname to send for this command defaults to the FQDN of the local
        host.
        """

        self.putcmd("helo", name or self.localhost)
        (code,msg)=self.getreply()
        self.helo_resp=msg
        return (code,msg)

    def ehlo(self, name=''):
        """ SMTP 'ehlo' command.
        Hostname to send for this command defaults to the FQDN of the local
        host.
        """
        self.putcmd("ehlo", name or self.localhost)
        (code,msg)=self.getreply()
        # According to RFC1869 some (badly written)
        # MTA's will disconnect on an ehlo. Toss an exception if
        # that happens -ddm
        if code == -1 and len(msg) == 0:
            raise SMTPServerDisconnected("Server not connected")
        self.ehlo_resp=msg
        if code != 250:
            return (code,msg)
        self.does_esmtp=1
        #parse the ehlo response -ddm
        resp=self.ehlo_resp.split('\n')
        del resp[0]
        for each in resp:
            m=re.match(r'(?P<feature>[A-Za-z0-9][A-Za-z0-9\-]*)',each)
            if m:
                feature=m.group("feature").lower()
                params=m.string[m.end("feature"):].strip()
                self.esmtp_features[feature]=params
        return (code,msg)

    def has_extn(self, opt):
        """Does the server support a given SMTP service extension?"""
        return self.esmtp_features.has_key(opt.lower())

    def help(self, args=''):
        """SMTP 'help' command.
        Returns help text from server."""
        self.putcmd("help", args)
        return self.getreply()

    def rset(self):
        """SMTP 'rset' command -- resets session."""
        return self.docmd("rset")

    def noop(self):
        """SMTP 'noop' command -- doesn't do anything :>"""
        return self.docmd("noop")

    def mail(self,sender,options=[]):
        """SMTP 'mail' command -- begins mail xfer session."""
        optionlist = ''
        if options and self.does_esmtp:
            optionlist = ' ' + ' '.join(options)
        self.putcmd("mail", "FROM:%s%s" % (quoteaddr(sender) ,optionlist))
        return self.getreply()

    def rcpt(self,recip,options=[]):
        """SMTP 'rcpt' command -- indicates 1 recipient for this mail."""
        optionlist = ''
        if options and self.does_esmtp:
            optionlist = ' ' + ' '.join(options)
        self.putcmd("rcpt","TO:%s%s" % (quoteaddr(recip),optionlist))
        return self.getreply()

    def data(self,msg):
        """SMTP 'DATA' command -- sends message data to server.

        Automatically quotes lines beginning with a period per rfc821.
        Raises SMTPDataError if there is an unexpected reply to the
        DATA command; the return value from this method is the final
        response code received when the all data is sent.
        """
        self.putcmd("data")
        (code,repl)=self.getreply()
        if self.debuglevel >0 : print "data:", (code,repl)
        if code != 354:
            raise SMTPDataError(code,repl)
        else:
            q = quotedata(msg)
            if q[-2:] != CRLF:
                q = q + CRLF
            q = q + "." + CRLF
            self.send(q)
            (code,msg)=self.getreply()
            if self.debuglevel >0 : print "data:", (code,msg)
            return (code,msg)

    def verify(self, address):
        """SMTP 'verify' command -- checks for address validity."""
        self.putcmd("vrfy", quoteaddr(address))
        return self.getreply()
    # a.k.a.
    vrfy=verify

    def expn(self, address):
        """SMTP 'verify' command -- checks for address validity."""
        self.putcmd("expn", quoteaddr(address))
        return self.getreply()

    # some useful methods
    def sendmail(self, from_addr, to_addrs, msg, mail_options=[],
                 rcpt_options=[]):
        """This command performs an entire mail transaction.

        The arguments are:
            - from_addr    : The address sending this mail.
            - to_addrs     : A list of addresses to send this mail to.  A bare
                             string will be treated as a list with 1 address.
            - msg          : The message to send.
            - mail_options : List of ESMTP options (such as 8bitmime) for the
                             mail command.
            - rcpt_options : List of ESMTP options (such as DSN commands) for
                             all the rcpt commands.

        If there has been no previous EHLO or HELO command this session, this
        method tries ESMTP EHLO first.  If the server does ESMTP, message size
        and each of the specified options will be passed to it.  If EHLO
        fails, HELO will be tried and ESMTP options suppressed.

        This method will return normally if the mail is accepted for at least
        one recipient.  It returns a dictionary, with one entry for each
        recipient that was refused.  Each entry contains a tuple of the SMTP
        error code and the accompanying error message sent by the server.

        This method may raise the following exceptions:

         SMTPHeloError
           The server didn't reply properly to
           the helo greeting.

         SMTPRecipientsRefused
           The server rejected ALL recipients
           (no mail was sent).

         SMTPSenderRefused
           The server didn't accept the from_addr.

         SMTPDataError
           The server replied with an unexpected
           error code (other than a refusal of
           a src/recipient).

        Note: the connection will be open even after an exception is raised.

        Example:

         >>> import smtplib
         >>> s=smtplib.SMTP("localhost")
         >>> tolist=["one@one.org","two@two.org","three@three.org","four@four.org"]
         >>> msg = '''
         ... From: Me@my.org
         ... Subject: testin'...
         ...
         ... This is a test '''
         >>> s.sendmail("me@my.org",tolist,msg)
         { "three@three.org" : ( 550 ,"User unknown" ) }
         >>> s.quit()

        In the above example, the message was accepted for delivery to three
        of the four addresses, and one was rejected, with the error code
        550.  If all addresses are accepted, then the method will return an
        empty dictionary.

        """
        if self.helo_resp is None and self.ehlo_resp is None:
            if not (200 <= self.ehlo()[0] <= 299):
                (code,resp) = self.helo()
                if not (200 <= code <= 299):
                    raise SMTPHeloError(code, resp)
        esmtp_opts = []
        if self.does_esmtp:
            # Hmmm? what's this? -ddm
            # self.esmtp_features['7bit']=""
            if self.has_extn('size'):
                esmtp_opts.append("size=" + `len(msg)`)
            for option in mail_options:
                esmtp_opts.append(option)

        (code,resp) = self.mail(from_addr, esmtp_opts)
        if code != 250:
            self.rset()
            raise SMTPSenderRefused(code, resp, from_addr)
        senderrs={}
        if isinstance(to_addrs, str):
            to_addrs = [to_addrs]
        for each in to_addrs:
            (code,resp)=self.rcpt(each, rcpt_options)
            if (code != 250) and (code != 251):
                senderrs[each]=(code,resp)
        if len(senderrs)==len(to_addrs):
            # the server refused all our recipients
            self.rset()
            raise SMTPRecipientsRefused(senderrs)
        (code,resp) = self.data(msg)
        if code != 250:
            self.rset()
            raise SMTPDataError(code, resp)
        #if we got here then somebody got our mail
        return senderrs


    def close(self):
        """Close the connection to the SMTP server."""
        if self.file:
            self.file.close()
        self.file = None
        if self.sock:
            self.sock.close()
        self.sock = None


    def quit(self):
        """Terminate the SMTP session."""
        self.docmd("quit")
        self.close()


# Test the sendmail method, which tests most of the others.
# Note: This always sends to localhost.
if __name__ == '__main__':
    import sys

    def prompt(prompt):
        sys.stdout.write(prompt + ": ")
        return sys.stdin.readline().strip()

    fromaddr = prompt("From")
    toaddrs  = prompt("To").split(',')
    print "Enter message, end with ^D:"
    msg = ''
    while 1:
        line = sys.stdin.readline()
        if not line:
            break
        msg = msg + line
    print "Message length is " + `len(msg)`

    server = SMTP('localhost')
    server.set_debuglevel(1)
    server.sendmail(fromaddr, toaddrs, msg)
    server.quit()
