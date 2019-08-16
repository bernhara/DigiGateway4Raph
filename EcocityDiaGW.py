#!/usr/bin/python2.4

# $Id: PangooDiaGW.py 8114 2013-01-07 18:07:32Z orba6563 $

'''
Calls the standard DIA runtime with application specific Python path
'''

import sys
import os.path
# force to call make located in the same folder
sys.path.insert(0, '.')

import dia

_DIGI_DIA_ARCHIVE = "dia.zip"

def include_project_runtime_path_elements ():
    # build Ecocity specific path
    custom_path_list = ["."]
    
    if (sys.platform.startswith('digi')):
        # we are on a Digi platform.
        # We assume that the code is contained in the DIGI_DIA_ARCHIVE file
        path_prefix = os.path.join(os.path.abspath('.'), _DIGI_DIA_ARCHIVE)
        custom_path_list += [ "custom_src" ]
    else:
        # Development platform
        # use file system path
        
        path_prefix = '.'
        custom_path_list += ["custom_src" ]
        
        custom_path_list += ["src"]
        custom_path_list += ["lib"]
        
        
        
    # build runtime path
    path_entension = []
    for path in custom_path_list:
        path_element = os.path.join(path_prefix,path)
        path_entension.append(path_element)
        
    print >> sys.stderr, "Adding path element: %s" % ', '.join(path_entension)
    new_path = path_entension
    new_path.extend(sys.path)
    sys.path=new_path
    
    
    # Import of custom_lib changes os.path, since some external packages must be relocate
    import custom_lib
    print >> sys.stderr, "Sys path is now: %s" % ', '.join(map(str, sys.path))
    

def main ():
    
    # should have a least 1 arg
    # argv[1]: YML configuration file
    # argv[2]: optional new root dir to change to
    
    
    
    if sys.argv and (len(sys.argv) < 2 or len(sys.argv) > 3):
         raise RuntimeError("Argument error: YML file [new home dir]")

    settings_file = sys.argv[1]
    
    if len(sys.argv) == 3:
        new_home_dir = sys.argv[2]

        # test if new home dir exists and go to it
        os.chdir(new_home_dir)
     
        print >> sys.stderr, "New home dir: %s" % os.getcwd()

    include_project_runtime_path_elements ()

    # Initialize runtime environment
    if (sys.platform.startswith('digi')):
        # target
        pass
    else:
        
        # development environment
        
        # extend path with "crossdev_src"
        sys.path.insert(0, 'crossdev_src')
        print >> sys.stderr, "Added \"crossdev_src\" to path"
        print >> sys.stderr, "Path is now: %s" % ', '.join(map(str, sys.path))    
        

        # preload simulation files and overload packages 
        #!! import idigi_pc as _idigi
        import emul_idigi_pc as _idigi
        host, token, path, port, securePort = _idigi._get_ws_parms()
        print >> sys.stderr, "DEV emulation configuration. Idigi client configuration is: host=%s, token=%s, path=%s, port=%s, securePort=%s" % (host, token, path, port, securePort)
        
        #
        # File system access
        #
        import win32_file_utils
        import common.file_utils
        replacing_package = sys.modules ["win32_file_utils"]
        sys.modules ["common.file_utils"] = replacing_package
        from common.file_utils import percent_remaining, blocks_remaining
        print >> sys.stderr, "DEV emulation configuration. Test of common.file_utils.percent_remaining() and blocks_remaining: %s, %s" % (percent_remaining(), blocks_remaining())     

        #
        # Idigi data builder
        #        
        import idigidata 
        
        #
        # XBEE serial interface wrapper
        #
        import xbee # xbee emulation with serial
        # put the xbee library in debug mode, so that all ZigBee frames are dump on stderr
        xbee.MESH_TRACEBACK = True

            
    # Launch original DIA framework
    core = dia.main ()
    dia.spin_forever(core)
    
if __name__ == "__main__":
    main()
