#!/usr/bin/env python 
#portable serial port access with python
#this is a wrapper module for different platform implementations
#
# (C)2001-2002 Chris Liechti <cliechti@gmx.net>
# this is distributed under a free software license, see license.txt

VERSION = '2.4'

import sys

if sys.platform == 'cli':
    from serialcli import *
elif sys.platform == 'digiconnect' or sys.platform == 'digix3' or \
                                      sys.platform == 'digiSarOS':
    from serialdigi import *
else:
    import os
    #chose an implementation, depending on os
    if os.name == 'nt': #sys.platform == 'win32':
        # Attempt to catch the case where the user is loading Dia on a PC,
        # and might not have pywin32 package installed yet.
        try:
            from serialwin32 import *
        except ImportError, e:
            if str(e) == 'No module named win32file':
                print "**********************************************************"
                print "* It appears you are trying to run Dia on a Windows PC.  *"
                print "*                                                        *"
                print "* Dia is unable to find the required library on this PC. *"
                print "* The library is part of the 'pywin32' package.          *"
                print "*                                                        *"
                print "* You can download this library from SourceForge here:   *"
                print "*     http://sourceforge.net/projects/pywin32/           *"
                print "**********************************************************"
                raise
        except Exception, e:
            print "Unable to import the Serial library: %s" % (str(e))
            raise
    elif os.name == 'posix':
        from serialposix import *
    elif os.name == 'java':
        from serialjava import *
    else:
        raise Exception("Sorry: no implementation for your platform ('%s') available" % os.name)

