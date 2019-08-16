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

"""\
A limited pure Python implementation of readline and raw_input.
"""

# imports
import sys, os
import socket
from select import select
import threading
from traceback import print_stack
from lib.serial import Serial

# constants, currently set to NVT defaults:
CHAR_NUL = '\x00'
CHAR_CTRLH = '\x08'
CHAR_LF = '\x0a'
CHAR_CR = '\x0d'
CHAR_ESC = '\x1b'
CHAR_DEL = '\x7e'
CHAR_BS = '\x7f'
CHAR_CSI = '\x9b'

# exception classes

# interface functions

def get_completer():
    global __readline_ctx
    return __readline_ctx.completer

def set_completer(function=None):
    global __readline_ctx
    if not function:
        function = lambda p, q: None
    __readline_ctx.completer = function

def get_completer_delims():
    global __readline_ctx
    return __readline_ctx.completer_delims

def set_completer_delims(string):
    global __readline_ctx
    __readline_ctx.completer_delims = [ c for c in string ]

def parse_and_bind(string):
    # not implemented
    pass

def get_line_buffer():
    global __readline_ctx
    return __readline_ctx.line_buffer
        
def get_begidx():
    global __readline_ctx
    return __readline_ctx.begidx
        
def get_endidx():
    global __readline_ctx
    return __readline_ctx.endidx

def clear_history():
    global __readline_ctx
    __readline_ctx.history.clear()

def get_history_length():
    global __readline_ctx
    return __readline_ctx.max_history

def set_history_length(length):
    global __readline_ctx
    __readline_ctx.max_history = length

def get_current_history_length():
    global __readline_ctx
    return len(__readline_ctx.history)

def get_history_item(index):
    global __readline_ctx
    return __readline_ctx.history[index]

def remove_history_item(pos):
    global __readline_ctx
    __readline_ctx.history.pop(pos)

def replace_history_item(pos, line):
    global __readline_ctx
    __readline_ctx.history[pos] = line

def add_history(line):
    global __readline_ctx
    __readline_ctx.history.insert(line, 0)
    while (len(__readline_ctx.history) > __readline_ctx.max_history):
         __readline_ctx.history.pop()

def raw_input(prompt, stdin=None, stdout=None):
    global __input_ctx

    if stdin is not None:
        __input_ctx.stdin = stdin
    else:
        __input_ctx.stdin = sys.stdin
    if stdout is not None:
        __input_ctx.stdout = stdout
    else:
        __input_ctx.stdout = sys.stdout
    __input_ctx.prompt = prompt

    line_buffer = __input_ctx.getline()

    return line_buffer

def socket_input(prompt, sd_in, sd_out):
    global __input_ctx

    __input_ctx.stdin = sd_in
    __input_ctx.stdout = sd_out
    __input_ctx.prompt = prompt

    line_buffer = __input_ctx.getline()

    return line_buffer

# internal functions & classes
class __ReadlineContext(threading.local):
    def __init__(self):
        self.max_history = 32
        self.default_state()
        self.saved_line = ''
        threading.local.__init__(self)

    def __common_prefix(self, string_list):
        if not len(string_list):
            return ""

        common_prefix = ""
        for c in string_list[0]:
            prefix = common_prefix + c
            still_common = True
            for string in string_list:
                if not string.startswith(prefix):
                    still_common = False
                    break
            if not still_common:
                break
            common_prefix = prefix
        return common_prefix

    def __completion_context_rescan(self):
        # work backward in string until
        # the begining of string or a completer_delim
        # is hit:
        #print "lb: %s" % (self.line_buffer)
        #print "begidx: %d" % (self.begidx)
        #print "endidx: %d" % (self.endidx)
        #print "curpos: %d" % (self.curpos)
        self.begidx = 0
        for i in range(self.curpos-1, 0, -1):
            if self.line_buffer[i] in self.completer_delims:
                self.begidx = i+1
                break

        self.endidx = len(self.line_buffer)
        for i in range(self.curpos, len(self.line_buffer)-1, 1):
            if self.line_buffer[i] in self.completer_delims:
                self.endidx = i
                break

    def default_state(self):
        self.completer = lambda p,q: None
        self.completer_delims = [' ']
        self.completion_chars = ['\t']
        self.history = list()
        self.hist_idx = -1
        self.newline_state()

    def newline_state(self):
        self.completion_matches = []
        self.line_buffer = ""
        # current completion context
        self.begidx = 0
        self.endidx = 1
        # current character position in line:
        self.curpos = self.begidx

    def event_completion_key(self, prompt):
        if self.curpos == len(self.line_buffer):
            buf = ""
            if not len(self.completion_matches):
                text = self.line_buffer[self.begidx:self.endidx]
                state = 0
                while 1:
                    match = self.completer(text, state)
                    if not isinstance(match, str):
                        break
                    if not match in self.completion_matches:
                        self.completion_matches.append(match)
                    state += 1
                if not len(self.completion_matches):
                    return ""
                self.completion_matches.sort()
                common_prefix = self.__common_prefix(self.completion_matches)
                buf += common_prefix[self.endidx - self.begidx:]
                self.line_buffer = \
                    self.line_buffer[0:self.begidx] + \
                        common_prefix
                self.endidx = self.begidx + len(common_prefix) - 1
                self.curpos = self.endidx + 1
            else:
                buf += "\r\n"
                for match in self.completion_matches:
                    buf += "%s " % (match)
                buf += "\r\n" + prompt + self.line_buffer
            return buf
        return ''

    def event_destructive_backspace(self):
        #print "BS ",
        # Invalidate completion matches:
        self.completion_matches = []
        if len(self.line_buffer) and self.curpos > 0:
            self.curpos -= 1
            self.line_buffer = self.line_buffer[:self.curpos] + self.line_buffer[self.curpos+1:]
            self.__completion_context_rescan()
            
            # Move cursor back, overwrite existing text, add trailing space,
            # Then move the cursor all the way back again
            result = ['\b', self.line_buffer[self.curpos:], ' ']
            result += ['\b' * (len(self.line_buffer) - self.curpos + 1)]
            return ''.join(result)
        return ''

    def event_delete(self):
        #print "DEL ",
        if (self.curpos != len(self.line_buffer)):
            self.completion_matches = []
            
            result = ' ' * (len(self.line_buffer) - self.curpos)
            result += '\b' * (len(self.line_buffer) - self.curpos)
            
            # Remove character at cursor position
            self.line_buffer = self.line_buffer[0:self.curpos] \
                               + self.line_buffer[self.curpos+1:len(self.line_buffer)]
            
            result += self.line_buffer[self.curpos:len(self.line_buffer)]
            
            result += '\b' * (len(self.line_buffer) - self.curpos)
            
            self.__completion_context_rescan()

            return result
        return ''

    def event_left(self):
        #print "LEFT ",
        if self.curpos > 0:
            # Invalidate completion matches:
            self.completion_matches = []
            
            self.curpos -= 1
            self.__completion_context_rescan()
            return '\b'
        return ''
    
    def event_right(self):
        #print "RIGHT ",
        if (self.curpos < len(self.line_buffer)):
            # Invalidate completion matches:
            self.completion_matches = []
            
            self.curpos += 1
            self.__completion_context_rescan()
            return self.line_buffer[self.curpos - 1]
        return ''

    def event_home(self):
        #print "HOME ",
        if self.curpos > 0:
            self.completion_matches = []
            
            # Return one backspace for each character
            # before the cursor
            result = '\b' * self.curpos
             
            self.curpos = 0
            self.__completion_context_rescan()
            
            return result
        return ''
    
    def event_end(self):
        #print "END ",
        if (self.curpos < len(self.line_buffer)):
            # Invalidate completion matches:
            self.completion_matches = []
            
            result = self.line_buffer[self.curpos:len(self.line_buffer)]
            
            self.curpos = len(self.line_buffer)
            self.__completion_context_rescan()
            return result
        return ''
    
    def __clear_line(self):
        #print "CLEAR(lbl=%d,cpos=%d) " % (len(self.line_buffer), self.curpos, ),
        self.completion_matches = []
        length = len(self.line_buffer)
        result = '\b' * self.curpos
        result += ' ' * length
        result += '\b' * length
        
        self.line_buffer = ''
        self.curpos = 0
        self.__completion_context_rescan()
        return result
    
    def event_clear(self):
        return self.__clear_line()
    
    def __show_history(self, index):
        #print "HIST(lh=%d,hidx=%d,idx=%d) " % (len(self.history), self.hist_idx, index, ),
        if (index < len(self.history) and index >= -1):
            # Save the current line buffer so we can redisplay it later
            if (self.hist_idx == -1):
                self.saved_line = self.line_buffer.rstrip(' \t')
                
            # Clear the line
            result = self.__clear_line()
            
            if (index != -1):
                # Reset the current line buffer to the appropriate
                # history line
                self.line_buffer = self.history[index]
            else:
                self.line_buffer = self.saved_line
                
            result += self.line_buffer
            
            self.hist_idx = index
            self.curpos = len(self.line_buffer)
            
            self.__completion_context_rescan()
            
            return result
        return ''
        
    def event_pgup(self):
        #print "PGUP ",
        return self.__show_history(len(self.history) - 1)
    
    def event_pgdn(self):
        #print "PGDN ",
        return self.__show_history(-1)
    
    def event_up(self):
        #print "UP ",
        return self.__show_history(self.hist_idx + 1)
    
    def event_down(self):
        #print "DOWN ",
        return self.__show_history(self.hist_idx - 1)
    
    def event_insert(self):
        #print "INSERT ",
        return ''

    def event_ascii_control(self, char):
        #print "ASCII(char=%r)" % (char,),
        self.line_buffer += char
        self.curpos += 1
        return char

    def event_enter(self):
        #print "ENTER "
        if (len(self.history) == self.max_history):
            self.history.pop()
        
        if (self.line_buffer.rstrip(' \t') != ''):
            self.history.insert(0, self.line_buffer.rstrip(' \t'))
        
        self.hist_idx = -1
        
        self.line_buffer += '\r\n'
        return '\r\n'

    def event_normalkey(self, key):
        #print "NK(char=%r) " % (key,),
        # Invalidate completion matches:
        self.completion_matches = []
        if (self.curpos == len(self.line_buffer)):
            self.line_buffer += key
        
        # TODO: Add insert/replace selection logic
        elif True:
            # Insert key at current position
            self.line_buffer = self.line_buffer[0:self.curpos] \
                               + key \
                               + self.line_buffer[self.curpos:len(self.line_buffer)]
            
            key = self.line_buffer[self.curpos:len(self.line_buffer)]
            key += '\b' * (len(key)-1)
        else:
            # Replace key at current position
            self.line_buffer = self.line_buffer[0:self.curpos] \
                               + key \
                               + self.line_buffer[self.curpos+1:len(self.line_buffer)]
        self.curpos += 1
        self.__completion_context_rescan()
        return key


class __InputContext(threading.local):
    # keycode constants
    KEY_NONE = None
    KEY_PRINTABLE = 0
    KEY_ANSI_GENERIC = 1
    KEY_ASCII_CONTROL = 2
    KEY_ENTER = ord('\x0d')
    KEY_ESC = ord('\x1b')
    KEY_DELETE = ord('\x7e')
    KEY_BACKSPACE = ord('\x7f')
    

    # getkey() state machine states:
    STATE_START = 0
    STATE_ANSI_CSI1 = 1
    STATE_ANSI_CSI2 = 2
    STATE_ANSI_N = 3
    STATE_ANSI_SEMI = 4
    STATE_ANSI_M = 5

    # other constants
    ESCSEQ_TIMEOUT = 0.125

    def __init__(self, prompt="", stdin=None, stdout=None):
        readline_ctx = globals()['__readline_ctx']

        self.stdin, self.stdout = stdin, stdout
        self.prompt = prompt
        self.__readline = readline_ctx
        threading.local.__init__(self)

    def _read(self):
        if self.stdin is None:
            raise Exception, "input uninitialized"

        if isinstance(self.stdin, socket.SocketType):
            return self.stdin.recv(1)
        elif isinstance(self.stdin, Serial):
            return self.stdin.read(1)
        else:
            return os.read(self.stdin.fileno(), 1)

    def _write(self, buf):
        if self.stdout is None:
            raise Exception, "output uninitialized"

        if isinstance(self.stdout, socket.SocketType):
            return self.stdout.send(buf)
        elif isinstance(self.stdin, Serial):
            return self.stdout.write(buf)
        else:
            return os.write(self.stdout.fileno(), buf)

    def _getkey(self):
        state = self.STATE_START
        char_buffer = ""
        key_code = self.KEY_NONE

        while 1:
            # STATE_START
            #    |  |
            #    |  +---------(\x9b)-----------|
            #    v (\x1b)                      v
            #    STATE_ANSI_CSI1 --('[')-->STATE_ANSI_CSI2
            # +---+ (not '[')                  |
            # |                                |
            # +-+ (non-numeric and not ';')    |
            # | | +--(0-9)---------------------+
            # | | |        ^
            # | | v        |
            # | STATE_ANSI_N----(';')--->STATE_ANSI_SEMI
            # |    |                      |    |
            # |    |                      |    |
            # +----+ (non-semicolon)      |    |
            # |                           |    |
            # +---(non-numeric)-----------+    |
            # |                                |
            # |    +--(0-9)--------------------+
            # |    |       ^
            # |    |       |
            # | STATE_ANSI_M---(non-numeric)------+
            # |                                   |
            # +-----------------+-----------------+
            #                   |
            #                   V

            if state == self.STATE_START:
                ch = self._read()
                if ch == '':
                    raise EOFError
                                    
                if ch in CHAR_NUL + CHAR_LF + '\xff':
                    # ignore
                    continue
                
                char_buffer += ch
                if ch == CHAR_ESC:
                    state = self.STATE_ANSI_CSI1
                    continue
                
                elif ch == CHAR_CSI:
                    state = self.STATE_ANSI_CSI2
                    continue
                
                # ASCII control char range 
                elif ord(ch) in range(0x20): 
                    key_code = self.KEY_ASCII_CONTROL
                    break
                
                else:
                    key_code = self.KEY_PRINTABLE
                    break
                
            elif state == self.STATE_ANSI_CSI1:
                sr = select([self.stdin],[],[],self.ESCSEQ_TIMEOUT)
                
                if sr == ([self.stdin],[],[]):
                    ch = self._read()
                    char_buffer += ch
                    if ch == '[':
                        state = self.STATE_ANSI_CSI2
                        continue
                    
                    else:
                        # invalid escape sequence, char dropped
                        pass
                    
                # ESC pressed
                key_code = self.KEY_ESC
                break
            
            elif state == self.STATE_ANSI_CSI2:
                ch = self._read()
                char_buffer += ch
                
                if ord(ch) in range(0x30, 0x3A):
                    state = self.STATE_ANSI_N
                    continue
                
                else:
                    # single character ANSI command
                    key_code = self.KEY_ANSI_GENERIC
                    break
                
            elif state == self.STATE_ANSI_N:
                ch = self._read()
                char_buffer += ch
                
                if ord(ch) in range(0x30, 0x3A):
                    continue
                
                elif ch == ';':
                    state = self.STATE_ANSI_SEMI
                    continue
                
                else:
                    # single character ANSI command w/numeric arg
                    key_code = self.KEY_ANSI_GENERIC
                    break
                
            elif state == self.STATE_ANSI_SEMI:
                ch = self._read()
                char_buffer += ch
                
                # '0'->'9'
                if ord(ch) in range(0x30, 0x3A):
                    state = self.STATE_ANSI_M
                    continue
                
                else:
                    # goofy (mal-formed?) ANSI sequence
                    key_code = self.KEY_ANSI_GENERIC
                    break
                
            elif state == self.STATE_ANSI_M:
                ch = self._read()
                char_buffer += ch
                if ord(ch) in range(0x30, 0x3A):
                    continue
                
                else:
                    # termination of ANSI command
                    key_code = self.KEY_ANSI_GENERIC
                    break
            else:
                # invalid state!
                break

        if key_code == self.KEY_PRINTABLE or \
           key_code == self.KEY_ASCII_CONTROL:
            ch = char_buffer[0]
            if ch == CHAR_CR:
                key_code = self.KEY_ENTER
            elif ch == CHAR_BS or ch == CHAR_CTRLH:
                key_code = self.KEY_BACKSPACE
            elif ch == CHAR_DEL:
                key_code = self.KEY_DELETE
                
        return (key_code, char_buffer)

    def getline(self):
        edit_buf = ""
        self.__readline.newline_state()
        self._write(self.prompt)

        while 1:
            key, char_buffer = self._getkey()
            ch = char_buffer[0]
            
            if ch in self.__readline.completion_chars:
                edit_buf = self.__readline.event_completion_key(self.prompt)
            elif key == self.KEY_BACKSPACE:
                edit_buf = self.__readline.event_destructive_backspace()
            elif key == self.KEY_DELETE:
                edit_buf = self.__readline.event_delete()
            elif key == self.KEY_ANSI_GENERIC:
                ansi_cmd = char_buffer[len(char_buffer)-1]
                if ansi_cmd == 'A':
                    edit_buf = self.__readline.event_up() 
                elif ansi_cmd == 'B':
                    edit_buf = self.__readline.event_down()
                elif ansi_cmd == 'C':
                    edit_buf = self.__readline.event_right()
                elif ansi_cmd == 'D':
                    edit_buf = self.__readline.event_left()
                elif ansi_cmd == '~':
                    ctl_code = char_buffer[len(char_buffer)-2]     
                    if (ctl_code == '1'):
                        edit_buf = self.__readline.event_home()
                    elif (ctl_code == '2'):
                        edit_buf = self.__readline.event_insert() 
                    elif (ctl_code == '3'):
                        edit_buf = self.__readline.event_delete() 
                    elif (ctl_code == '4'):
                        edit_buf = self.__readline.event_end()
                    elif (ctl_code == '5'):
                        edit_buf = self.__readline.event_pgup()
                    elif (ctl_code == '6'):
                        edit_buf = self.__readline.event_pgdn()
                    
            elif key == self.KEY_ENTER:
                edit_buf = self.__readline.event_enter()
                self._write(edit_buf)
                break
            elif key == self.KEY_PRINTABLE:
                edit_buf = self.__readline.event_normalkey(ch)
            elif key == self.KEY_ASCII_CONTROL:
                # Convert to control key -- e.g., 0x03 => Ctrl+C
                ch = chr(ord(ch) + 0x40)
                
                if (ch == 'C'):
                    edit_buf = self.__readline.event_clear()
                else:
                    edit_buf = self.__readline.event_ascii_control(ch)
            else:
                # invalid!
                continue

            if edit_buf:
                self._write(edit_buf)

        return self.__readline.line_buffer



def __print_char(ch):
    if isinstance(ch, int):
        ch = chr(ch)
    ch_ord = ord(ch)
    ch_repr = ch
    if ch_ord < 0x20 or ch_ord > 0x7e:
        ch_repr = "\\x%02x" % (ch_ord)
    print "got: '%s' (0x%02x)" % (ch_repr, ch_ord)

# Module initialization:
__readline_ctx = __ReadlineContext()
__input_ctx = __InputContext()

