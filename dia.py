#!/usr/bin/python

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
To run this, use command line: python dia.py [config.yml]
"""

# imports
import sys
try:
    import os.path
except ImportError:
    # os comes from python.zip on our gateways.
    print """\
Unable to import 'os' module. Check that your system has a 'python.zip' file,\r
and that it is the correct one for your device.\r
"""
    sys.exit(1)

import gc
import time
# constants
BOOTSTRAP_VERSION = "2.3.1.1"
GC_COLLECTION_INTERVAL = 60 * 15  # fifteen minutes

# internal functions & classes


def spin_forever(core):
    """
    This routine prevents the main thread from exiting when the
    framework is run directly from __main__.
    """
    try:
        while not core.shutdown_requested():
            collected_items = gc.collect()
            if collected_items:
                # only print if something accomplished
                print ("GarbageCollector: collected %d objects."
                       % collected_items)
            core.wait_for_shutdown(GC_COLLECTION_INTERVAL)
    finally:
        core._shutdown()
        locker.unlock()
        print "dia.py is exiting...\n"


def setup_path_and_zip():
    """  Sets up the paths to import from the appropriate locations.
    Also detects if a zip file is present and returns the path to the
    archive
    """
    #Does the dia.zip exist in our local directory?
    expected_zip_path = os.path.join(os.path.abspath('.'), 'dia.zip')
    if os.path.exists(expected_zip_path):
        #Yes, add it to the path:
        sys.path.append(expected_zip_path)
        #Add the paths internal to the zip file
        for lib_path in ['lib', 'src']:
            sys.path.insert(0, os.path.join(expected_zip_path, lib_path))

        return expected_zip_path

    else:
        #We may be operating in a environment that doesn't need dia.zip
        #find files, like /src/core/core_services.py
        if not os.path.exists(os.path.join('src', 'core', 'core_services.py')):
            raise RuntimeError("Unable to find dia.zip or core libraries"
                               ", please load dia.zip and try again")
        else:
            #We're running in the root of the source tree, directly add the
            #/src and /lib directories, insert them, so they are imported
            #before base libraries, in case of conflict
            for lib_path in ['lib', 'src']:
                sys.path.insert(0, lib_path)

        return None


def locate_configuration_file(expected_zip_path):
    """ Locates the settings file, returns the settings in a file like object,
    returns the source name of the settings (the file name used),
    and returns the destination of where the settings could be saved.

    The source and destination will differ if the source is the dia.zip file.
    """
    settings_file = None
    settings_flo = None
    dest_file = None

    #To locate the settings file, parse command line
    if sys.argv and len(sys.argv) > 1:
        #Use the one supplied by the args
        settings_file = sys.argv[1]

        if not os.path.exists(settings_file):
            #Try again for NDS, doesn't have concept of local directory
            settings_file = os.path.abspath(settings_file)
            if not os.path.exists(settings_file):
                raise RuntimeError("Settings file: %s given, but not found"
                                   " in path" % (settings_file))

        #settings file found, read it in
        settings_flo = open(settings_file, 'r')
        dest_file = settings_file
    else:
        #No direction from args to find settings file
        #Search local path for dia.pyr, dia.yml in order

        for possible_fname in ['dia.pyr', 'dia.yml']:
            if os.path.exists(os.path.abspath(possible_fname)):
                dest_file = settings_file = os.path.abspath(possible_fname)
                settings_flo = open(settings_file, 'r')
                break

    if (expected_zip_path is not None) and (settings_flo is None):
        #Previous attempts at finding the configuration are unsuccessful
        #Search the dia.zip archive for the settings file, dia.pyr/dia.yml

        import zipfile
        import StringIO

        dia_zip_flo = open(expected_zip_path, 'rb')
        dia_zip = zipfile.ZipFile(dia_zip_flo)

        #Find the fname, then break
        for possible_fname in ['dia.pyr', 'dia.yml']:
            if possible_fname in dia_zip.namelist():
                #Set the flo object to the file buffer in the zip file

                #Provide an alternative location, we cannot overwrite the
                #configuration in the zipfile
                settings_file = os.path.join(expected_zip_path, possible_fname)
                dest_file = os.path.join(os.path.abspath('.'), possible_fname)
                settings_flo = StringIO.StringIO(dia_zip.read(possible_fname))
                dia_zip_flo.close()
                dia_zip.close()
                break
    return settings_file, settings_flo, dest_file


def do_slowdown_check():
    """ Performs the slow down check and if true, slows down the startup of
    the Dia.  This is done to prevent platforms that have an auto restart on
    exit of the Dia from spinning fast enough to prevent modification of the
    platform if something causes the startup to fail immediately.
    """

    #Check for the file that enables this feature
    stop_fname = os.path.join(os.path.abspath("."), "nospin.txt")
    if not os.path.exists(stop_fname):
        print "Dia auto-detect of rapid reboot DISABLED"
        return
    print "Dia auto-detect of rapid reboot ENABLED"

    #Continue, check the timestamp file for entries
    slowdown = False

    ts_file = open(stop_fname, 'r')
    entries = ts_file.readlines()
    ts_file.close()

    ##Remove all non-float compatible entries
    for ent in entries[:]:
        try:
            float(ent)
        except ValueError:
            entries.remove(ent)

    #If more than 9 entries, find average of last 10 entries
    if len(entries) >= 10:
        curr_time = time.time()
        avg_time = sum(float(x.strip()) for x in entries[-10:]) / 10.0

        #Compare them to the current time, and if less than 20 minutes
        #mark us ready for slow down
        diff_time = curr_time - avg_time
        if diff_time < 1200:
            print ("Initiating slow down in order to prevent the Dia from "
                   "spinning too fast")
            slowdown = True

    #Cycle out old timestamps

    entries.append(str(time.time()) + os.linesep)
    ts_file = open(stop_fname, "w")
    ts_file.writelines(entries[-10:])
    ts_file.close()

    #If need to slow down, do so here
    if slowdown:
        print "Slowing down, pausing for 10 minutes"
        time.sleep(600)
        print "Done slowing down."


def main():
    """  Acts as the startup script for the Dia.  Sets up the environment
    (sys.path) and loads the configuration file for use by the core services
    to load the rest of the system
    """
    #Perform slow down check in case of reboot cycle
    do_slowdown_check()

    #File name of the settings being used
    settings_file = None

    #File object derived from opening the settings file
    settings_flo = None

    #If using a zip file, will return path to zip
    expected_zip_path = setup_path_and_zip()

    #We've found the library files, verify matching version
    try:
        from src.common.dia_version import DIA_VERSION
    except Exception:
        if expected_zip_path:
            print ("Error reading from Zipfile: %s  Common cause for error "
                   "is that the files inside the zip file were compiled with "
                   "the incorrect version of python." % expected_zip_path)
        else:
            print ("No dia.zip found and unable to locate the file "
                   "src/common/dia_version.py in the local path.")
        raise

    # Check that there are no other running instances of DIA
    from src.common.file_locking import FileLocking
    global locker
    locker = FileLocking()
    dia_exists = not locker.lock()
    if dia_exists:
        print "An instance of DIA was already detected as running."
        sys.exit()

    if DIA_VERSION != BOOTSTRAP_VERSION:
        raise RuntimeError("Library files found, but bootstrap and library "
                           "versions do not match! Expected: %s, Found: %s"
                           % (BOOTSTRAP_VERSION, DIA_VERSION))

    #Locate the settings file that we use for starting up
    settings_file, settings_flo, dest_file = \
                    locate_configuration_file(expected_zip_path)

    if settings_file is None or settings_flo is None:
        raise RuntimeError("Unable to locate settings file in local directory,"
                           " from command line input, or dia.zip.  Please "
                           "provide a configuration file in one of these "
                           "locations.")

    print "Running in environment: %s" % sys.platform
    print "Device Integration Application Version %s" % DIA_VERSION
    print "Source settings file: %s" % settings_file
    print "Destination settings file: %s" % dest_file

    from core.core_services import CoreServices

    core = CoreServices(settings_flo=settings_flo,
                        settings_filename=dest_file)

    if __name__ == "__main__":
        # Don't exit.  If not __main__ then the caller needs to guarantee this.
        spin_forever(core)

    return core

if __name__ == "__main__":
    main()
