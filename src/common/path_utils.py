############################################################################
#                                                                          #
# Copyright (c)2012 Digi International (Digi). All Rights Reserved.        #
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
Platform path abstraction tools.

Provides

create_full_path(arg)

so relative paths may be passed to create_full_path() to create absolute
paths in a platform-independent manner.
'''

import sys
import os


class BadPathException(Exception):
    ''' Raised when a bad absolute path is given as an argument. '''
    pass


NDS = 0
SAROS = 1
LTS = 2
WINDOWS = 3
LINUX = 4
X2E = 5
X3 = 6
UNKNOWN = 9

# this platform type
_THIS = None


_BASE_DIR = {
    NDS: '/WEB/python/',
    SAROS: '/user/',
    LTS: '/initrd/tmp/',
    X3: '/WEB/python/',
    WINDOWS: None,
    LINUX: None,
    X2E: '/userfs/WEB/python/',
    UNKNOWN: ''}


def get_platform():
    '''
    Returns an enumerated value (one of NDS, SAROS, TRANSPORT, X3,
    WINDOWS, LINUX, UNKNOWN).
    '''
    # memoize
    global _THIS
    if _THIS != None:
        return _THIS

    if sys.platform == 'digiconnect':
        _THIS = NDS
    elif sys.platform == 'digix3':
        _THIS = X3
    elif sys.platform == 'linux2':
        try:
            import uptime
            _THIS = X2E
        except Exception:
            _THIS = LINUX
    elif sys.platform == 'win32':
        _THIS = WINDOWS
    elif sys.platform == 'digiSarOS':
        _THIS = SAROS
    else:
        _THIS = UNKNOWN
    return _THIS


def get_base_dir():
    '''
    Return the base directory (including the trailing path separator)
    for this platform.

    In the case of Linux or Windows, the current working directory is
    returned.
    '''
    bdir = _BASE_DIR[get_platform()]
    if bdir != None:
        return bdir

    # for linux and windows, assume the current directory
    return os.getcwd() + os.path.sep


def create_full_path(arg, fix=True):
    '''
    Transform the given path into an absolute path for the underlying
    system.

    If an absolute path is given and it is correct for the
    underlying system, it is returned unchanged.

    If a non-matching absolute path is given and fix == False, a
    BadPathException is raised. If fix == True, the path is mangled to
    match the underlying system. Note that this may not do *exactly*
    what you want.
    '''
    if len(arg) == 0:
        return get_base_dir()

    # were we actually passed a full path?
    if arg[0] == os.path.sep or '/':
        if not fix:
            if arg.find(get_base_dir()) == -1:
                raise BadPathException('Refusing to create an absolute ' \
                                       'path from an absolute path. (%s)' \
                                       % arg)
            else:
                return arg
        else:
            # stick the file onto the base file name
            return get_base_dir() + os.path.split(arg)[1]

    # assuming this is a relative path
    # ... but first, checking for the sin that is "WEB/python/"
    sin_prefix = 'WEB/python/'
    if arg.startswith(sin_prefix):
        return get_base_dir() + arg[len(sin_prefix):]

    # finally, if the user actually called this correctly...
    return get_base_dir() + arg
