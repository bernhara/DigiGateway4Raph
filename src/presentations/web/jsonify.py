############################################################################
#                                                                          #
# Copyright (c)2009, Digi International (Digi). All Rights Reserved.       #
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
Cleanse python lists, objects, tuples, etc. into valid JSON.

Use regular expressions to tokenize valid structures, such as singly and
doubly quoted strings, integers and floats.  Anything that doesn't match
an integer, float, or double-quoted string is converted to a double-quoted
string -- single quotes around strings are converted to double quotes.
Additionally, a valid token must be followed by a valid separator: [{,}]
and : for hashes.  Tuples are converted to lists.  JSON recognizes certain
control characters (\\n, \\r, etc.), and these are also represented
correctly.

Triple single and double quoted strings are not recognized, although they
could be added easily.

Also, the list of accepted "afters" should really only include ,]}:.
"""
import re

from core.tracing import get_tracer
_tracer = get_tracer("jsonify")

# Hash, list, or tuple character:
JRE_HLCHR = r'][{:,}()'

JRE_HLFOLLOWS = r'(?=\s*['+JRE_HLCHR+'])'

# Numbers and strings
# Number
JRE_NUM = r'(?:[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)'
# Single/double quoted string
JRE_SQUO = r"'(?:\\'|[^'])*'"
JRE_DQUO = r'"(?:\\"|[^"])*"'
# Triple quoted strings: representation not needed
JRE_TSQUO = r"'''(?:\\'|[^'])*'''"
JRE_TDQUO = r'"""(?:\\"|[^"])*"""'
# Number or single/double-quoted string
JRE_NSTR = r'(?:'+JRE_SQUO+'|'+JRE_DQUO+'|'+JRE_NUM+')'+JRE_HLFOLLOWS
re_NSTR = re.compile(JRE_NSTR)

# Other (non-quoted) strings without hash or list characters:
#JRE_OSTR = r'[^][{:,}]+[^][{:,}\s]'
JRE_OSTR = r'(?:[^'+JRE_HLCHR+r']|\s)+'+JRE_HLFOLLOWS

# Tokenize a hash/list/tuple/... combo:
JRE_TOKEN = '((?:\s+)|(?:\()|'+JRE_NSTR+'|'+JRE_OSTR+'|['+JRE_HLCHR+'])'
re_TOKEN = re.compile(JRE_TOKEN)

def mkJson(obj):
   stack = []
   def islist():
      return len(stack) and stack[-1] == '['
   def isdict():
      return len(stack) and stack[-1] == '{'
   def istuple():
      return len(stack) and stack[-1] == '('

   if not isinstance(obj, str):
      obj_str = str(obj)
   else:
      obj_str = obj
   tlist = re_TOKEN.split(obj_str)
   for i in range(0, len(tlist)):
      t = tlist[i]
      #if not t: continue
      # '' will be eliminated in the join
      if t == '' or t[0].isspace():
         tlist[i] = ''
         continue
      if t in '{[(':
         stack.append(t)
         if t == '(':
            tlist[i] = '['
         continue
      if t in '}])':
         if t == '}' and isdict() or t == ']' and islist() or \
               t == ')' and istuple():
            stack.pop()
         else:
            _tracer.warning("mismatched enclosure '%s', expecting '%s'", t, stack[-1])
         if t == ')':
            tlist[i] = ']'
         continue
      if (t == ':' and isdict()) or t in ',{}[]()':
         continue
      if t[0].isdigit() or t[0] in '+-\'"':
         nstr_match = re_NSTR.match(t+',')
         if nstr_match and nstr_match.group(0) == t:
            if t[0] == '+':   # +1 is not valid JSON
               tlist[i] = t[1:]
            if t[0] == "'":
               tlist[i] = '"'+t[1:-1]+'"'
            continue
      # Boolean, None, etc.
      if t == 'True' or t == 'False':
         tlist[i] = t.lower()
         continue
      if t == 'None':
         tlist[i] = 'null'
         continue
      # Quote ", \, /, and control characters, wrap result in ""
      for q, u in [ (r'\\','\\'), (r'\"','\"'), (r'\/','/'), (r'\b','\b'), 
            (r'\f','\f'), (r'\n','\n'), (r'\r','\r'), (r'\t','\t'), 
            (r'\u',r'\\u'), # oops, undo \\u :)
            ]:
         t = q.join(t.split(u))
      tlist[i] = '"'+str(t)+'"'
   return ''.join(tlist)

if __name__ == '__main__':
   class UnQuoted:
      def __init__(self, name):
         self.name = name
      def __getattr__(self, attr_name):
         _tracer.info("getattr: %s", attr_name)
         return lambda *args: lambda str_attr=attr_name: str.str_attr(*args)
      def __repr__(self):
         return str(self.name)
      def __coerce__(self, other):
         return type(other)(self.name), other

   d = [{
         1: -2, 
         2: 'abc', 
         3: +3, 
         4:(1,2), 
         5:[1, 'a', 3.125], 
         6:{1:'a', 2:'b'},
         7: UnQuoted('123a'), # Non-quoted string
         8: UnQuoted('+3.1'),  # same
         9: bool, # unquoted <type \'bool\'>: embedded quotes and spaces!
         10: UnQuoted('"4"5\u1234 \t6\n7b'), # This one causes all sorts of trash
         11: None,   # becomes null
         12: False,
         UnQuoted('foo')+'bar': 13,  # becomes false
      }, 2, ]
   _tracer.info("\nTesting mkJson:\nInput is ")
   _tracer.info(repr(d))
   _tracer.info("\nOutput is ")
   _tracer.info(mkJson(d))
