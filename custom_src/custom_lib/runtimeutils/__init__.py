# $Id: __init__.py 7435 2012-01-09 15:47:15Z orba6563 $
"""TODO: describe module"""

_on_digi_board_ = None

_runtime_env_inited_ = False

from sys import path, platform
import time

def _setup_runtime_env():
    
    global _runtime_env_inited_
    global _on_digi_board_
    
    if (not _runtime_env_inited_):

        # compute platform descriptors and specific configuration
        if platform.startswith('digi'):
            _on_digi_board_ = True
            
            _setup_digi_pythonpath_ ()
        else:
            _on_digi_board_ = False
            
        _runtime_env_inited_ = True
            
def _setup_digi_pythonpath_ ():
    pass

def on_digi_board ():
    
    global _on_digi_board_
    return (_on_digi_board_)

def get_time_seconds_since_epoch ():
    """ Return the current time in seconds since epoch."""
    if (on_digi_board()):
        seconds_since_epoch = time.clock()
    else:
        seconds_since_epoch = time.time()
    return seconds_since_epoch

# call runtime setup as package is loaded.
_setup_runtime_env ()

