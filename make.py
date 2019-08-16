#!/usr/bin/python2.4

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


## make.py

# top-level imports:
import sys, os, os.path
import distutils.sysconfig
import subprocess

# constants

ARGV0_DIRNAME, ARGV0_BASENAME = os.path.split(sys.argv[0])
if ARGV0_DIRNAME == '':
    ARGV0_DIRNAME = os.getcwd()

DIGI_PYTHON_VERSIONS = (
    (2, 4, 3),
    (2, 6, 1),
    (2, 7, 1),
)

# Maps major Python version number to __import__ positional args:
CUSTOM_VERSION_COMPILER_MAP = {
    (2, 4): ("tools.build.custom_compiler24", (), (), ["compile"]),
}

PYTHON_LIB = distutils.sysconfig.get_python_lib(False,True)

DEFAULT_TARGET = os.path.join(ARGV0_DIRNAME, "bin/dia.zip")
DEFAULT_SOURCE = "dia.py"
DEFAULT_BUILD_DATE_FILE = 'zip_build_date.py'
DEFAULT_SETTINGS_BASENAME = 'dia'
DEFAULT_SETTINGS_FORMAT = 'pyr'
DEFAULT_OPTIONAL_TASKS = (
    # (Python task path, optional description string)
    (' '.join((sys.executable,
               "src/presentations/embedded_web/build_pyhtml.py")),
     "building embedded_web pyhtml"),
    )

ALWAYS_ANALYZE = (
                os.path.join(sys.path[0], DEFAULT_SOURCE),
                os.path.join(PYTHON_LIB, "encodings/utf_8.py"),
    )

EXCLUDE_FILES = (
                  os.path.join(sys.path[0], DEFAULT_SOURCE),
    )

INCLUDE_PATHS = (
                  distutils.sysconfig.get_python_lib(False,True),
                  os.path.join(ARGV0_DIRNAME, 'lib'),
                  os.path.join(ARGV0_DIRNAME, 'src'),
                  os.getcwd(),
    )

REWRITE_RULES = (
                  (distutils.sysconfig.get_python_lib(False,True), ""),
                  (os.path.join(ARGV0_DIRNAME, 'lib'), os.path.join('lib', '')),
                  (os.path.join(ARGV0_DIRNAME, 'src'), os.path.join('src', '')),
                  (os.getcwd(), ""),
    )

# add project include paths to system path:
for include_path in INCLUDE_PATHS:
    sys.path.append(include_path)

# imports

import getopt
import tempfile
import zipfile
import time
from copy import copy
from pprint import pformat

import tools.build.settings as settings
import tools.build.build_zip as build_zip

def usage(exit_code=0):
    print """\
Usage: %s [options] input_settings_file

Options:
    -h,             --help:             show this message.

    -o <path>,      --output_file:      path where the output archive will
                                        be generated.  The default is:
                                        "%s"

    -i <path>,     --append_include:    append include path to the list of
                                        module search paths used by the
                                        build process.  This option may be
                                        specified multiple times.
                                        paths where the build process
                                        should search for include modules.

    -I <path>,      --insert_include:   insert an include path in the list
                                        module search paths used by the
                                        build process.  Compare to -i.

    -r <rule>,      --append_rewrite:   append a path rewriting rule to
                                        the list of path rewriting rules.
                                        Re-writing rules are given in the
                                        format "input_path,output_path"
                                        and control how modules found
                                        in the include paths will be placed
                                        in the output archive file.

                                        If a rewrite rule is not given for
                                        a specified include path, the include
                                        path prefix will be removed from the
                                        module path before it is placed in
                                        the output file archive.

    -s <format>,    --settings_format:  format to which given input settings
                                        file will be transformed do.
                                        Omitting this parameter will cause
                                        the settings to be transformed to the
                                        default settings format: "%s"

    -v,             --verbose:          enable verbose print statements

    -c,             --compile:          compile the modules before adding
                                        them to the zip file. True by default.
                                        Specify "-c False" to disable this
                                        option.

    -x,             --custom_compiler:  enable custom compiler which
                                        strips docstrings for additional
                                        memory savings.

Advanced:
    -e,             --execute_tasks:    execute optional Python tasks (such
                                        as web-page code regeneration) before
                                        building main project.

    -t <task>,      --task:             add optional python task to execute
                                        before building main project.  Implies
                                        -e.  This task may be specified
                                        multiple times.  Tasks are executed
                                        in the order given on the command-
                                        line.


""" % (ARGV0_BASENAME, DEFAULT_TARGET, DEFAULT_SETTINGS_FORMAT)
    sys.exit(exit_code)


def version_tuple_to_str(version_tuple):
    return '.'.join(map(lambda i: str(i), version_tuple[0:3]))


def make_dummy_script(settings_path, verbose=False):
    """\
Properly parse a settings file and generate a dummy python
script which contains import statements for each driver
module referenced in the settings file.

Returns the filename of the dummy script generated.
    """

    drivers = settings.get_driver_list(settings_path)
    if verbose:
        print "Project will include the following driver files:"
        if len(drivers) == 0:
            print "   (none)"
        for driver in drivers:
            print "   * %s" % driver
        print ""

    (dummy_fd, dummy_filename) = tempfile.mkstemp(suffix='.py')
    for driver in drivers:
        os.write(dummy_fd, "import %s\n" % driver)
    os.close(dummy_fd)

    return dummy_filename


def main():

    # Check Python version:
    # This script is meant to be run on a PC, not on a Digi device.
    if sys.platform.startswith('digi'):
        raise Exception("Error: This script expects to run on a PC")
    else:
        # Check PC Python version vs. what the output may run upon:
        system_version = sys.version_info[0:3]
        system_version_str = version_tuple_to_str(system_version)
        digi_versions_str = ' or '.join([
                                version_tuple_to_str(v) for v in
                                DIGI_PYTHON_VERSIONS])
        major_system_version = system_version[0:2]
        major_version_map = {}
        for complete_version in DIGI_PYTHON_VERSIONS:
            major_version = complete_version[0:2]
            major_version_map[major_version] = complete_version

        if system_version not in DIGI_PYTHON_VERSIONS:
            if major_system_version not in major_version_map:
                raise Exception("FATAL: build version mismatch: " + \
                                  "PC=%s, Digi=%s" % (system_version_str,
                                                       digi_versions_str))
            else:
                digi_version = major_version_map[major_system_version]
                print ("WARNING: minor version mis-match: " + \
                       "PC=%s, Digi=%s") % (system_version_str,
                                            version_tuple_to_str(digi_version))

        # Parse options:
        options = {}

        if len(sys.argv) < 2:
            print "ERROR: not enough command line arguments specified."
            usage(-1)

        try:
            opts, args = getopt.getopt(sys.argv[1:], "o:i:I:r:s:vc:et:x", (
                                            "output_file=",
                                            "append_include=",
                                            "insert_include=",
                                            "append_rewrite=",
                                            "settings_format=",
                                            "verbose",
                                            "compile=",
                                            "execute_tasks",
                                            "task=",
                                            "custom_compiler",
                                            )
                                      )
        except getopt.GetoptError:
            usage(-1)

        options["output_file"] = os.path.normpath(DEFAULT_TARGET)
        options["include_paths"] = list(INCLUDE_PATHS)
        options["exclude_files"] = list(EXCLUDE_FILES)
        options["rewrite_rules"] = list(REWRITE_RULES)
        options["settings_format"] = DEFAULT_SETTINGS_FORMAT
        options["verbose"] = False
        options["compile"] = True
        options["optional_tasks"] = list(DEFAULT_OPTIONAL_TASKS)
        options["execute_tasks"] = False
        options["custom_compiler"] = False

        for o, a in opts:
            if o in ("-h", "--help"):
                usage(0)
            elif o in ("-o", "--output_file"):
                options["output_file"] = os.path.normpath(a)
            elif o in ("-i", "--append_include"):
                paths = a.split(",")
                for path in paths:
                    options["include_paths"].append(os.path.normpath(path))
            elif o in ("-I", "--insert_include"):
                paths = a.split(",")
                for path in paths:
                    options["include_paths"].insert(0, os.path.normpath(path))
            elif o in ("-r", "--append_rewrite"):
                rewrite_rules = a.split(';')
                for rewrite_r in rewrite_rules:
                    try:
                        rewrite_rule = rewrite_r.split(",")
                        rewrite_rule = (os.path.normpath(rewrite_rule[0]),
                                        rewrite_rule[1])
                        options["rewrite_rules"].append(rewrite_rule)
                    except Exception, e:
                        print "invalid rewrite rule: %s (%s)" % (a, str(e))
                        sys.exit(-1)
            elif o in ("-s", "--settings_format"):
                options["settings_format"] = a
            elif o in ("-v", "--verbose"):
                options["verbose"] = True
            elif o in ("-c", "--compile"):
                if a == "False":
                    options["compile"] = False
            elif o in ("-e", "--execute_tasks"):
                options["execute_tasks"] = True
            elif o in ("-t", "--task"):
                options["optional_tasks"].append((a, ''))
                options["execute_tasks"] = True
            elif o in ("-x", "--custom_compiler"):
                options["custom_compiler"] = True

        options["input_settings"] = os.path.normpath(sys.argv[len(sys.argv)-1])

        if not os.path.exists(options["input_settings"]):
            raise Exception("cannot find settings file '%s'" % (
                options["input_settings"]))

        format_err_str = ""
        input_suffix = os.path.splitext(options["input_settings"])[1][1:]
        if input_suffix not in settings.SETTINGS_SERIALIZERS_MAP:
            format_err_str = "invalid input settings format '%s'" % (input_suffix)
        if options["settings_format"] not in settings.SETTINGS_SERIALIZERS_MAP:
            format_err_str = "invalid output settings format '%s'" % (
                                options["settings_format"])
        if len(format_err_str):
            print format_err_str
            print "Valid settings formats are:"
            for format in sorted(settings.SETTINGS_SERIALIZERS_DESC_MAP):
                print "    %4s: %s" % (
                    format, settings.SETTINGS_SERIALIZERS_DESC_MAP[format])
            print ""
            raise Exception(format_err_str)
        del(format_err_str)

        if options["verbose"]:
            print """\

    Parsed options:

        input_settings:     %s
        output_file:        %s
        include_paths:      %s
        exclude_files:      %s
        rewrite_rules:      %s
        settings_format:    %s
        verbose:            %s
        compile:            %s
        execute_optional_tasks:      %s
        optional_tasks:     %s
        custom_compiler:    %s

    """ % (options["input_settings"],
           options["output_file"],
           pformat(options["include_paths"]),
           pformat(options["exclude_files"]),
           pformat(options["rewrite_rules"]),
           options["settings_format"],
           pformat(options["verbose"]),
           pformat(options["compile"]),
           pformat(options["execute_tasks"]),
           pformat(options["optional_tasks"]),
           pformat(options["custom_compiler"]))

        print "Project make started."

        # Add include paths:
        for include_path in options["include_paths"]:
            if include_path not in sys.path:
                sys.path.append(include_path)

        # Optional tasks:
        if options["execute_tasks"]:
            for task, desc in options["optional_tasks"]:
                print "Executing '%s': %s" % (task, desc)
                task = task.split()
                subprocess.call(task)

        try:
            # Make dummy script:
            dummy_filename = \
                make_dummy_script(options["input_settings"], options["verbose"])
            if options["verbose"]:
                print "Created dummy script '%s'..." % dummy_filename

            # Create build descriptor:
            bzd = build_zip.BuildZipDescriptor()
            bzd.input_script = dummy_filename
            bzd.always_analyze = copy(ALWAYS_ANALYZE)
            bzd.output_file = copy(options['output_file'])
            bzd.include_paths = copy(options['include_paths'])
            bzd.exclude_files = copy(options['exclude_files'])
            bzd.exclude_modules = copy(build_zip.EXCLUDE_MODS)
            bzd.rewrite_rules = copy(options['rewrite_rules'])
            bzd.verbose = copy(options['verbose'])
            bzd.compile = copy(options['compile'])

            major_system_version = sys.version_info[0:2]
            if (options["custom_compiler"] and
                major_system_version in CUSTOM_VERSION_COMPILER_MAP):
                print "Using custom compiler."
                module = __import__(
                    *CUSTOM_VERSION_COMPILER_MAP[major_system_version])
                bzd.compiler = module.compile
            elif options["verbose"]:
                print "Using default compiler."


            # Generate output archive using build descriptor:
            build_zip.build_zip(bzd)

        finally:
            if options["verbose"]:
                print "Removing dummy script '%s'..." % dummy_filename
            try:
                # Remove dummy script:
                os.unlink(dummy_filename)
            except:
                print "WARNING: unable to remove dummy script."

    # Add configuration to output archive:
    (settings_fd, settings_filename) = tempfile.mkstemp(suffix = (
                                            '.'+options['settings_format']))
    os.close(settings_fd)
    try:
        print "Transforming settings file '%s' to '%s' format..." % (
            options["input_settings"], options['settings_format'])
        settings.transform(options["input_settings"], settings_filename)
        output_filename = os.path.normpath(DEFAULT_SETTINGS_BASENAME +
                            '.' + options['settings_format'])
        print "Adding transformed settings as '%s' to '%s'..." % (
            output_filename, options["output_file"])
        output_zip = zipfile.ZipFile(options["output_file"], 'a', zipfile.ZIP_DEFLATED)
        output_zip.write(settings_filename, output_filename)
        
        # save Dia ZIP build date
        time_now = time.time()
        tmpf = open(DEFAULT_BUILD_DATE_FILE,'w')
        
        tmpf.write("# time saved when Dia make.py was last run\r\n")
        
        time_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time_now))
        data = "DIA_ZIP_BUILD_DATE = \"%s\"\r\n" % time_str
        tmpf.write(data)
        
        data = "DIA_ZIP_BUILD_DATE_RAW = %f\r\n" % time_now
        tmpf.write(data)
        
        tmpf.close()
        output_zip.write(DEFAULT_BUILD_DATE_FILE)
        
        output_zip.close()
    finally:
        if options["verbose"]:
            print "Removing temporary settings file '%s'..." % settings_filename
        # Remove dummy script:
        os.unlink(settings_filename)


    print "Project make completed successfully."

    sys.exit(0)

if __name__ == "__main__":
    main()
