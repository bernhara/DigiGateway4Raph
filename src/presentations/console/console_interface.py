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
Console Interface
"""

# imports
import sys, traceback

import digi_cmd as cmd
import socket
import digitime
import shlex
import getopt
from StringIO import StringIO

from samples.sample import Sample
from common.helpers.format_channels import dump_channel_db_as_text, iso_date
from common.helpers.format_logging_events import \
    format_logging_events_iterator
from channels.channel_database_interface import \
    LOG_SEEK_SET, LOG_SEEK_CUR, LOG_SEEK_END, LOG_SEEK_REC
from channels.channel import \
    PERM_GET, PERM_SET, PERM_REFRESH, \
    OPT_AUTOTIMESTAMP, OPT_DONOTLOG, OPT_DONOTDUMPDATA
from core.core_services import CoreSettingsInvalidSerializer
from common.dia_proc import get_drivers


# constants
VALUE_TYPE = {0:"int",1:"Boolean",2:"float",3:"str",255:"undefined"}
EVENT_TYPE = {0:"Ch. Dump Init",1:"Channel Dump",2:"New Channel",
              3:"Channel Update"}

# exception classes

# interface functions

# classes
class ConsoleInterface(cmd.Cmd):
    
    def __init__(self, input, output, core):

        ## cmd.Cmd Initialization
        self.prompt = '=>> '
        self.intro  = 'Welcome to the Device Integration \
Application CLI.'
        cmd.Cmd.__init__(self, stdin=input, stdout=output)
		
        from core.tracing import get_tracer
        self.__tracer = get_tracer("ConsoleInterface")

        # Local Initialization
        self.__input = input
        self.__output = output
        self.__core = core
        self.__cdb = core.get_service("channel_manager").channel_database_get()
        self.__logger = None
        self.__logger_cdb = None

    def read(self):

        if isinstance(self.__input, socket.SocketType):
            return self.__input.recv(128)
        else:
            return self.__input.read(128)

    def write(self, buf):

        if isinstance(self.__output, socket.SocketType):
            return self.__output.send(buf)
        else:
            return self.__output.write(buf)
        
    ## cmd.Cmd Hooks:
    def emptyline(self):
        pass


    # Command help
    helptext = {
"channel_dump":

"""
Dump the channel values for all devices.

Syntax::

    channel_dump [prefix]
""",
# ---
"channel_get":
"""
Get the current sample value from a channel.

Syntax::

    channel_get channel_name
""",
#---
"channel_set":
"""
Set a channel with a given value.

Syntax::

    channel_set channel_name value [unit]
""",
#---
"channel_info":
"""
Get channel meta-information from a given channel.

Returns two lists:

* A list of channel permissions.
* A list of channel options.

Syntax::

    channel_info channel_name
""",
#---
"channel_refresh":
"""
Perform a refresh request upon a given channel.

Syntax::

    channel_refresh channel_name
""",
#---
"logger_set":
"""
Sets the logger database for this console to use.

Syntax::

    logger_set logger_name
""",
#---
"logger_dump":
"""
Dump all values for the current logger at the point of the current
sample in the log file.

Syntax::

    logger_dump [prefix]
""",
#---
"logger_list":
"""
List all configured loggers in the system.  A single logger from
this list is used with the logger_set command.


Syntax::

    logger_list
""",
#---
"logger_next":
"""
Advance the current logger database instance to the next record.

Syntax::

    logger_next
""",
#---
"logger_prev":
"""
Obtain the previous record from current position.

Syntax::

    logger_prev
""",
#---
"logger_rewind":
"""
Seek to the first logged record.

Syntax::

    logger_rewind
""",
#---
"logger_seek":
"""
Seek the current logger to position.

'offset' is an integer

'whence' is given as a string and may be of the following values:

* **set:** seek 'offset' records from the earliest record in the log
* **cur:** seek 'offset' records from the current record in the log
* **end:** seek 'offset' records from the last record in the log
* **rec:** seek to an absolute record number given by 'record_number'
  and then seek 'offset' records from that mark.
         
'record_number' is an absolute record number which only applies when
'whence' is rec.

Syntax::

    logger_seek offset whence [record_number]
""",
#---
"logger_pos":
"""
    Report the current log position.
    
    Syntax::

        logger_pos
""",
#---
"logger_iterate":
"""
    Iterate between two points in the active logger and print logging
    events as they are encountered.  Logging events are reported from
    a 'start' to 'end' inclusively.  If 'end' is omitted, the log will
    continue seeking to the last record.
    
    Calling this function will modify that current position of the
    active logger.
    
    Syntax::

        logger_iterate start [end]
""",
#---
"device_dump":
"""
    Report the name and driver of all current running devices,
    presentations, services, and loggers.
    
    Syntax::

        device_dump
""",
#---
"quit":
"""
Disconnect from the CLI.

Syntax::

    quit|q|exit
""",
#---
"exit":
"""
Disconnect from the CLI.

Syntax::

    quit|q|exit
""",
#---
"q":
"""
Disconnect from the CLI.

Syntax::

    quit|q|exit
""",
#---
"shutdown":
"""
Shutdown the Device Integration Application.

Syntax::

    shutdown
""",
}
      # END of command help

    ## Commands:
    def do_help(self, arg):
        if arg:
            # XXX check arg syntax
            try:
                func = getattr(self, 'help_' + arg)
            except AttributeError:
                try:
                    doc= ConsoleInterface.helptext[arg]
                    doc = '\r\n'.join(doc.splitlines())
                    if doc:
                        self.stdout.write("%s\r\n"%str(doc))
                        self.stdout.flush()
                        return
                except KeyError:
                    pass
                self.stdout.write("%s\r\n"%str(self.nohelp % (arg,)))
                self.stdout.flush()
                return
            func()
        else:
            names = self.get_names()
            cmds_doc = []
            cmds_undoc = []
            help = {}
            for name in names:
                if name[:5] == 'help_':
                    help[name[5:]]=1
            names.sort()
            # There can be duplicates if routines overridden
            prevname = ''
            for name in names:
                if name[:3] == 'do_':
                    if name == prevname:
                        continue
                    prevname = name
                    cmd=name[3:]
                    if cmd in help:
                        cmds_doc.append(cmd)
                        del help[cmd]
                    elif getattr(self, name).__doc__:
                        cmds_doc.append(cmd)
                    elif cmd in ConsoleInterface.helptext:
                        cmds_doc.append(cmd)
                    else:
                        cmds_undoc.append(cmd)
            self.stdout.write("%s\r\n"%str(self.doc_leader))
            self.stdout.flush()
            self.print_topics(self.doc_header,   cmds_doc,   15,80)
            self.print_topics(self.misc_header,  help.keys(),15,80)
            self.print_topics(self.undoc_header, cmds_undoc, 15,80)

    def do_channel_dump(self, arg):
        try:
            args = parse_line(arg)
        except:
            self.write("invalid syntax.\r\n")
            return 0
        startswith = ""
        if len(args) == 1:
            startswith = args[0]
        elif len(args) > 1:
            self.write("invalid argument(s) specified.\r\n")
            return 0
        self.__write_channel_database(self.__cdb, startswith)

    def do_chdu(self, arg):
        return self.do_channel_dump(arg)

    def complete_channel_dump(self, text, line, begidx, endidx):
        matches = []

        sio = StringIO(line)
        shlexer = shlex.shlex(sio)
        arg_num = 1
        while 1:
            try:
                token = shlexer.get_token()
            except:
                token = shlexer.eof
            if token == shlexer.eof:
                break
            
            if arg_num == 1 and sio.tell()+1 >= begidx: 
                matches = filter(lambda name: name.startswith(text),
                                    self.__cdb.channel_list())
            
            arg_num += 1

        return matches


    def do_channel_get(self, arg):
        try:
            args = parse_line(arg)
        except:
            self.write("invalid syntax.\r\n")
            return 0
        if len(args) != 1:
            self.write("invalid argument(s) specified.\r\n")
            self.do_help("channel_get")
            return 0

        channel_name = args[0]

        if not self.__cdb.channel_exists(channel_name):
            self.write("unknown channel '%s'\r\n" % (channel_name))
            return 0

        channel = self.__cdb.channel_get(channel_name)
        value = "(value unavailable)"
        unit = "(unit unavailable)"
        time_str = "(time unavailable)"
        try:
            sample = channel.get()
            value = str(sample.value)
            unit = sample.unit
            time_str = iso_date(sample.timestamp)
        except:
            pass

        if '\n' in value:
            value = value.replace('\n','\r\n')
            value = '\r\n' + value

        self.write("\t%s: %s (%s) @ %s\r\n" % 
            (channel_name, value, unit, time_str))

        return 0
        
    def do_chgt(self, arg):
        return self.do_channel_get(arg)

    def complete_channel_get(self, text, line, begidx, endidx):
        matches = []

        arg_num = 1
        
        sio = StringIO(line)
        shlexer = shlex.shlex(sio)
        arg_num = 1
        while 1:
            try:
                token = shlexer.get_token()
            except:
                token = shlexer.eof
            if token == shlexer.eof:
                break

            if arg_num == 1 and sio.tell()+1 >= begidx:
                matches = filter(lambda name: name.startswith(text),
                                    self.__cdb.channel_list())
            arg_num += 1

        return matches


    def do_channel_set(self, arg):
        try:
            args = parse_line(arg)
        except:
            self.write("invalid syntax.\r\n")
            return 0
        channel_name = ""
        value = None
        unit = ""
        if len(args) < 2 or len(args) > 3:
            self.write("invalid argument(s) specified.\r\n")
            return 0
        if len(args) > 1:
            channel_name = args[0]
            value = args[1]
        if len(args) > 2:
            unit = args[2]
            self.__tracer.info("have unit: %s", unit)


        if not self.__cdb.channel_exists(channel_name):
            self.write("unknown channel '%s'\r\n" % (channel_name))
            return 0

        channel = self.__cdb.channel_get(channel_name)

        sample = None
        try:
            sample = Sample(digitime.time(), channel.type()(value), unit)
        except Exception, e:
            self.write("unable to parse '%s': %s\r\n" % (value, str(e)))
            self.write("type expected: %s\r\n" % (channel.type()))
            return 0

        try:
            channel.set(sample)
        except Exception, e:
            self.write("unable to set: %s\r\n" % (str(e)))
            self.__tracer.error("unable to set: %s", str(e))
            self.__tracer.debug(traceback.format_exc())
            return 0

        value = "(value unavailable)"
        unit = "(unit unavailable)"
        time_str = "(time unavailable)"
        try:
            sample = channel.get()
            value = str(sample.value)
            if '\n' in value:
                value = value.replace('\n','\r\n')
                value = '\r\n' + value
            unit = sample.unit
            time_str = iso_date(sample.timestamp)
        except:
            pass
        self.write("\t%s: %s (%s) @ %s\r\n" % 
            (channel_name, value, unit, time_str))

        return 0


    def complete_channel_set(self, text, line, begidx, endidx):
        matches = []

        arg_num = 1
        sio = StringIO(line)
        shlexer = shlex.shlex(sio)
        arg_num = 1
        while 1:
            try:
                token = shlexer.get_token()
            except:
                token = shlexer.eof
            if token == shlexer.eof:
                break
            # match channel name
            if arg_num == 1 and sio.tell()+1 >= begidx:
                matches = filter(lambda name: name.startswith(text),
                                    self.__cdb.channel_list())
            arg_num += 1

        return matches


    complete_channel_info = complete_channel_get

    def do_channel_info(self, arg):
        try:
            args = parse_line(arg)
        except:
            self.write("invalid syntax.\r\n")
            return 0
        if len(args) != 1:
            self.write("invalid argument(s) specified.\r\n")
            self.do_help("channel_info")
            return 0

        channel_name = args[0]

        if not self.__cdb.channel_exists(channel_name):
            self.write("unknown channel '%s'\r\n" % (channel_name))
            return 0

        channel = self.__cdb.channel_get(channel_name)
        perms_table = {
            PERM_GET: "get",
            PERM_SET: "set",
            PERM_REFRESH: "refresh",
        }
        options_table = {
            OPT_AUTOTIMESTAMP: "auto timestamp",
            OPT_DONOTLOG: "data not logged",
            OPT_DONOTDUMPDATA: "data not dumped",
        }

        self.write("\r\nChannel information for %s:\r\n\r\n" % channel.name())
        for title, tbl, mask in (
                ("Permissions", perms_table, channel.perm_mask()),
                ("Options", options_table, channel.options_mask()) ):
            keys = tbl.keys()
            keys.sort()
            self.write("    %s:\r\n" % title)
            none_flag = True
            for k in keys:
                if k & mask:
                    self.write("        * %s\r\n" % tbl[k])
                    none_flag = False
            if none_flag:
                self.write("        NONE\r\n")
            self.write("\r\n")
        self.write("\r\n")

        return 0

    def do_channel_refresh(self, arg):
        try:
            args = parse_line(arg)
        except:
            self.write("invalid syntax.\r\n")
            return 0
        if len(args) != 1:
            self.write("invalid argument(s) specified.\r\n")
            return 0

        channel_name = args[0]

        if not self.__cdb.channel_exists(channel_name):
            self.write("unknown channel '%s'\r\n" % (channel_name))
            return 0

        channel = self.__cdb.channel_get(channel_name)

        try:
            channel.refresh()
        except Exception, e:
            self.write("unable to refresh: %s\r\n" % (str(e)))
            return 0

        return 0


    complete_channel_refresh = complete_channel_get

    def completedefault(self, text, line, begidx, endidx):
#        self.__tracer.info("completedefault()"
#        self.__tracer.info("""
#              text: %s
#              line: %s
#            begidx: %s
#            endidx: %s
#        """, text, line, begidx, endidx)

        return [text]


    def do_logger_set(self, arg):

        try:
            args = parse_line(arg)
        except:
            self.write("invalid syntax.\r\n")
            return 0
        if len(args) != 1:
            self.write("invalid argument(s) specified.\r\n")
            return 0

        logger_name = args[0]

        cm = self.__core.get_service("channel_manager")

        if not cm.channel_logger_exists(logger_name):
            self.write("unknown logger '%s'\r\n" % (logger_name))
            return 0

        self.__logger = cm.channel_logger_get(logger_name)
        self.__logger_cdb = self.__logger.channel_database_get()
        
        self.write("\tLogger set to %s\r\n" % logger_name)


    def complete_logger_set(self, text, line, begidx, endidx):
        matches = []

        cm = self.__core.get_service("channel_manager")

        arg_num = 1
        sio = StringIO(line)
        shlexer = shlex.shlex(sio)
        arg_num = 1
        while 1:
            try:
                token = shlexer.get_token()
            except:
                token = shlexer.eof
            if token == shlexer.eof:
                break

            # match channel name
            if arg_num == 1 and sio.tell()+1 >= begidx:
                matches = filter(lambda name: name.startswith(text),
                                    cm.channel_logger_list())
            arg_num += 1

        return matches


    def do_logger_dump(self, arg):

        
        if self.__logger is None:
            self.write("\tNo logger currently selected\r\n")
            return 0
        
        try:
            args = parse_line(arg)
        except:
            self.write("invalid syntax.\r\n")
            return 0
        startswith = ""
        if len(args):
            startswith = args[0]
        try:
            log_pos = self.__logger_cdb.log_position()
            logger_name = self.__logger.get_name()
            self.write("\r\nChannel Database for logger %s with log "
                        "position %s" % (logger_name, log_pos))
            self.__write_channel_database(self.__logger_cdb, startswith)
        except Exception,e:
            self.write("\r\n\tError during logger_dump: %s\r\n" % str(e))
        
    #complete_logger_dump = complete_channel_dump

    def do_logger_list(self, arg):
  
        cm = self.__core.get_service("channel_manager")
        logger_list = cm.channel_logger_list()
        
        for logger_name in logger_list:
            self.write("%s " % logger_name)
        self.write("\r\n")
               
    def do_logger_next(self, arg):

        if self.__logger is None:
            self.write("\tNo logger currently selected\r\n")
            return 0

        try:
            self.__logger_cdb.log_next()
        except Exception, e:
            self.write("\r\n\tUnable to proceed to next record: %s\r\n" % 
                        str(e))
    
    def do_logger_prev(self, arg):
  
        if self.__logger is None:
            self.write("\tNo logger currently selected\r\n")
            return 0

        try:
            self.__logger_cdb.log_prev()
        except Exception, e:
            self.write("\r\n\tUnable to proceed to previous record: %s\r\n" % 
                        str(e))
            
    def do_logger_rewind(self, arg):

        
        if self.__logger is None:
            self.write("\tNo logger currently selected\r\n")
        else:
            try:
                self.__logger_cdb.log_rewind()
            except Exception,e:
                self.write("\r\n\tCould not rewind logger: %s\r\n" % str(e))

    def do_logger_seek(self, arg):
    
        if self.__logger is None:
            self.write("\tNo logger currently selected\r\n")
            return 0
        
        try:
            args = parse_line(arg)
        except:
            self.write("invalid syntax.\r\n")
            return 0
        offset, whence, record_number = (None,) * 3
        if len(args) > 0:
            try:
                offset = int(args[0])
            except:
                self.write("invalid offset '%s', must be integer\r\n" 
                            % repr(args[0]))
        if len(args) > 1:
            try:
                whence_map = { 'set': LOG_SEEK_SET,
                               'cur': LOG_SEEK_CUR,
                               'end': LOG_SEEK_END,
                               'rec': LOG_SEEK_REC, }
                whence = whence_map[args[1].lower()]
            except:
                self.write(
                   "invalid whence '%s', must be set, cur, end, or rec\r\n" % (
                        repr(args[1])))
        if len(args) > 2:
            try:
                record_number = int(args[2])
            except:
                self.write("invalid record_number '%s', must be integer\r\n" % 
                        repr(args[2]))
        if record_number is None:
            record_number = 0

        try:
                self.__logger_cdb.log_seek(offset, whence, record_number)
        except Exception, e:
            self.write("\r\n\tSeek failed: %s\r\n" % str(e))

    def complete_logger_seek(self, text, line, begidx, endidx):
        matches = []
        sio = StringIO(line)
        try:
            shlexer = shlex.shlex(sio)
            arg_num = 0
            for token in shlexer:
                if shlexer.instream.tell() >= begidx:
                    arg_num += 1
                
                if arg_num == 1:
                    # offset
                    pass
                if arg_num == 2:
                    matches.extend(filter(lambda t: t.startswith(text),
                                    ("set", "cur", "end", "rec")))
                if arg_num == 3:
                    # record_number
                    pass
                
                arg_num += 1
        except:
            pass
        
        return matches
    
    def do_logger_pos(self, arg):
 
        try:
            args = parse_line(arg)
            if len(args) > 0:
                raise Exception
        except:
            self.write("invalid syntax.\r\n")
            return 0
        
        if self.__logger is None:
            self.write("\tNo logger currently selected\r\n")
            return 0
        
        logger_name = self.__logger.get_name()
        try:
            pos = self.__logger_cdb.log_position()
        except Exception,e:
            self.write("\r\n\tError while getting logger position: %s\r\n" % str(e))
            return 0
            
        if pos is None:
            self.write("\tPosition for '%s' is not set.\r\n" % logger_name)
        else:
            self.write("\tPosition for '%s' logger is %d.\r\n" % (logger_name, pos))
        
        return 0

    def do_logger_iterate(self, arg):

        try:
            args = parse_line(arg)
        except Exception, e:
            self.write("invalid syntax: %s\r\n" % str(e)) 
            return 0

        if self.__logger is None:
            self.write("\tNo logger currently selected\r\n")
            return 0
        
        from_record, to_record = (None,) * 2
        
        if not len(args):
            self.write("logger_iterate requires at least one argument.\r\n")
            return 0
        try:
            from_record = int(args[0])
        except:
            self.write("invalid starting record number: %s\r\n" %
                        repr(args[0]))
        if len(args) > 1:
            try:
                to_record = int(args[1])
                if to_record < 0:
                    to_record = None
            except:
                self.write("invalid ending record number: %s\r\n" % 
                            repr(args[1]))
        
        
        logger_name = self.__logger.get_name()
        to_record_name = repr(to_record)
        if to_record is None:
            to_record_name = "end"
        try:
            pos = self.__logger_cdb.log_position()
            self.write("\r\nIterating from %s to %s on logger '%s'.\r\n\r\n" % 
                        (from_record, to_record_name, logger_name))
            for line in format_logging_events_iterator(
                self.__logger_cdb.log_event_iterator(from_record, to_record)):
                self.write(line + "\r\n")
            self.write("\r\nIteration complete.\r\n")  
        except Exception,e:
            self.write("\r\n\tException during log iteration: %s\r\n" % str(e))

    def do_device_dump(self, arg):
        name_device_pairs = get_drivers(self.__core)

        for _ in name_device_pairs:
            self.write(_[0] + ": " + _[1] + '\r\n')
    
    def do_quit(self, arg):
        return -1

    # shortcuts
    do_q = do_quit
    do_exit = do_quit

    def do_shutdown(self, arg):
        self.write("Shutting down DIA...")
        self.__core.request_shutdown()
        return -1


    def do_EOF(self, arg):
        self.write("Shutdown in process, exiting...\r\n")
        return -1

    def help_help(self):
        """
        """
 
    def __write_channel_database(self, cdb, startswith=""):
        if len(cdb.channel_list()) > 0:
            self.write(dump_channel_db_as_text(cdb, startswith))
        else:
            self.write("\r\n\tChannelDatabase is empty.\r\n")


# internal functions & classes

def parse_line(arg):
    _shlex = shlex.shlex(arg, posix=True)
    _shlex.escape = [] # disable all escape characters
    _shlex.whitespace_split = True
    return list(_shlex)

