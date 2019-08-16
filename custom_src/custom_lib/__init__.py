# $Id: __init__.py 1091 2014-06-03 11:27:21Z orba6563 $

#
# Since the module is not located in its usual place, we have to alter the PYTHONPATH to use the module 
# with the original "import" statements
# TODO: check if this is a right way to do things
#

import sys
import os
import traceback

# search for "custom_src" path element to extend it with with the path element where this module is located

custom_src_path_elements = [x for x in sys.path if x.endswith ("custom_src")]

if len(custom_src_path_elements) == 0:
    print >> sys.stderr, "FATAL ERROR while loading %s module: could not find any custom_src path element to extend PYTHONPATH" % __file__
    print >> sys.stderr, traceback.format_exc()
else:
    print >> sys.stderr, "Extending path after loading of module \"%s\" for package relocation" % __file__
    
    # relocation of simplejson
    new_path_element = os.path.join (custom_src_path_elements[0], 'custom_lib', 'json')
    sys.path.insert(0, new_path_element)
    
    # relocation of mod_pywebsocket
    new_path_element = os.path.join (custom_src_path_elements[0], 'custom_lib', 'websocket', 'mod_pywebsocket_ext_lib')
    sys.path.insert(0, new_path_element)    