# $Id: digicli.py 1355 2014-11-27 13:57:32Z orba6563 $

import sys

def digicli (cli_command):
    print >> sys.stderr, "CROSSDEV emulation configuration for CLI. Should execute: %s " % cli_command
    return (True, 'CLI command simulation OK')
    