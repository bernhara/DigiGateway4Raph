############################################################################
#                                                                          #
# Copyright (c)2008, Digi International (Digi). All Rights Reserved.       #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice, and the following   #
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
Custom Boolean Type
"""

# imports

# constants
STYLE_TF = 0
STYLE_ONOFF = 1
STYLE_ONEZERO = 2
STYLE_YESNO = 3

# exception classes

# interface functions

# classes

class Boolean(object):
    _STR_YES = ('t', 'true', 'on', '1', 'y', 'yes')
    _STYLES = {STYLE_TF: ('False', 'True'),
               STYLE_ONOFF: ('Off', 'On'),
               STYLE_ONEZERO: ('0', '1'),
               STYLE_YESNO: ('No', 'Yes')}

    def __init__(self, val=0, style=STYLE_TF):
        # Setup string coercion style:
        self.__style = style

        if isinstance(val, str):
            val = val.lower()
            val = val in Boolean._STR_YES

        self.__value = False
        if val:
            self.__value = True

    def __str__(self):
        return Boolean._STYLES.get(self.__style,
                    STYLE_TF)[int(self.__value)]

    # Quote the 'str' string.  Makes things like the 'py' serializer happy.
    def __repr__(self):
        return "'" + self.__str__() + "'"

    def __int__(self):
        return int(self.__value)

    def __bool__(self):
        return self.__value

    def __and__(self, other):
        return bool(self) and other

    __rand__ = __and__

    def __invert__(self):
        return not bool(self)

    def __nonzero__(self):
        return self.__value

    def __or__(self, other):
        return bool(self) | other

    __ror__ = __or__

    def __xor__(self, other):
        return bool(self) ^ other

    __rxor__ = __xor__

    def __eq__(self, other):
        return bool(self) == other

    def __ne__(self, other):
        return bool(self) != other

    def __lt__(self, other):
        return bool(self) < other

    def __le__(self, other):
        return bool(self) <= other

    def __gt__(self, other):
        return bool(self) > other

    def __ge__(self, other):
        return bool(self) >= other


# internal functions & classes

def _a_test(c, style, x, expected):

    y = c(val=x, style=style)

    if isinstance(x, str):
        x = '"' + x +'"'

    print "%s(%s, %s) = '%s' should be '%s'" % \
          (repr(c), x, style, y, expected)


def main():
    _a_test(Boolean, STYLE_TF, False, "False")
    _a_test(Boolean, STYLE_TF, True, "True")
    _a_test(Boolean, STYLE_TF, 0, "False")
    _a_test(Boolean, STYLE_TF, 1, "True")
    _a_test(Boolean, STYLE_ONOFF, 0, "Off")
    _a_test(Boolean, STYLE_ONOFF, 1, "On")
    _a_test(Boolean, STYLE_ONEZERO, 0, "0")
    _a_test(Boolean, STYLE_ONEZERO, 1, "1")

    print "0 & 1 = %d" % (Boolean(0) & Boolean(1))
    print "1 & 1 = %d" % (Boolean(1) & Boolean(1))
    print "~ 0 = %d" % (~Boolean(0))
    print "not 0 = %d" % (not Boolean(0))
    print "True == 1 = %s" % (True == Boolean(1))
    print "True == 0 = %s" % (True == Boolean(0))
    print "False == 1 = %s" % (False == Boolean(1))
    print "False == 0 = %s" % (False == Boolean(0))

if __name__ == '__main__':
    import sys
    status = main()
    sys.exit(status)

