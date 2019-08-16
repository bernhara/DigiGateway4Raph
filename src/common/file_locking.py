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
"""
This module contains the file locking class (FileLocking), the exception
that it raises (LockingFailure), and code to test if our current running
platform is SarOS (is_saros).

See their respective docstrings for further documentation.
"""
import sys
import os
import errno
USE_SOCKET = True
try:
    import socket
except ImportError:
    USE_SOCKET = False


def is_saros():
    """
    Returns true if the current platform is SarOS. Currently
    SarOS is the only platform that needs platform-specific file-locking
    code.
    """
    return sys.platform == "digiSarOS"


class LockingFailure(Exception):
    """
    Exception class for when we have failed to create a file or
    socket lock. This is generally raised when an IOError or OSError
    is caught, but we want to distinguish the error as having come from
    the locking mechanism when we propagate it up the call stack.
    """
    def __init__(self, value):
        self.value = value
        self.args = [self.value]

    def __str__(self):
        return repr(self.value)


class FileLocking:
    """
    This class provides file locking abilities for the purpose of
    detecting other running instances of DIA--this way, we can ensure
    that only one instance of DIA is ever running on one device.

    This file locking class is designed to support Windows and Linux
    desktops, as well as Linux, NDS, and SarOS devices. This has required
    a few compromises in its design.

    Usage of the file locking class is simple:
        1) Create an instance of the class. inst = FileLocking()
        2) When DIA is loaded, run inst.lock()
        3) When DIA is about to exit, run inst.unlock()

    """

#==============================================================================
#     A typical user of this file locking class will not need to worry
#     about the below implementation details, which are given in order
#     to explain the design decisions involved in the creation of this
#     class.
#
#     There are three types of locks that can be created by this class:
#         1) Fully-atomic socket based locks
#         2) Fully-atomic SarOS library locks
#         3) Fully-atomic file locks
#         4) Non-atomic file locks
#
#     For most operating systems, lock() will create a socket-based lock,
#     where a socket is created and bound to localhost on port 9999.
#     This relies on the fact that one cannot bind two sockets to the
#     same host and port--so the second running instance of DIA will
#     fail to bind the socket. This informs us of the existence of an
#     already-running instance of DIA. This method of locking is
#     fully atomic.
#
#     However, socket-based implementations have their flaws. Some
#     devices have very few sockets available, and some operating
#     systems have socket implementations that allow the binding
#     of two sockets to the same host and port--leaving no fully atomic
#     way to use sockets. As of this time of writing, both of these
#     conditions apply to most SarOS devices.
#
#     New versions of SaroS will come with a fully atomic locking library
#     of its own, and this class will use that library if it exists.
#     However, for older versions of SaroS, file-based locking is still
#     available.
#
#     To remedy this, an atomic method of file-based locking is provided
#     using the low-level `os.open` function--which is used to create
#     a new lockfile or return an error if a lockfile already exists.
#
#     However, as of this time of writing, SarOS does not support
#     `os.open` either. Thus this class provides a flawed, non-atomic
#     method of file locking on SarOS. First `os.stat` is used to check
#     the existence of a lockfile, and if the file does not exist,
#     the Python built-in `open` is used to create one. This method
#     of creating a lockfile is subject to a time-of-check-to-time-of-use
#     (TOCTTOU) race condition. This should only be used on operating
#     systems that do not have a socket implementation worthy of locking
#     and also are missing `os.open`.
#
#     In addition, on SarOS systems, this class will create the lockfile
#     as a temporary file, which should disappear upon reboot. If
#     something happens and the DIA process is killed without cleaning
#     up the lockfile, a reboot should restore normal operation with
#     locking. This should also apply to socket-based locks, but is
#     not guaranteed for file-based locks on non-SarOS systems.
#     SarOS is only able to create ten of these files, but given
#     that many SarOS systems are short on sockets (and lack a
#     typically-behaving SarOS implementation), file locks are the
#     best option on these limited devices.
#
#     Another reason to use a temporary file is that the file is stored
#     in RAM, and this avoids potentially wearing out the device's flash
#     memory with continuous locking and unlocking. This could potentially
#     be an issue for Linux and NDS devices as well, as socket information
#     is stored as an open file. At the time of this writing, a specific
#     concern about the wearing out of the flash memory on a Linux or
#     NDS device has yet to be documented.
#
#     Finally, all of these details are automatically managed by the
#     program. The best method of locking is always selected out
#     of the three types of locking, based on the running platform
#     and the available resources.
#==============================================================================
    use_socket = True
    # Keep the filename short. Some operating systems do not have support
    # for... longer... filenames.
    lock_file_name = "DIALOCK"
    lock_file_contents = "1"
    lock_socket = None
    lock_file = None
    lock_saros = None
    socket_tuple = ('127.0.0.1', 9999)
    _lock_type = None
    SOCKET_LOCK = 1
    ATOMIC_FILE_LOCK = 2
    NONATOMIC_FILE_LOCK = 3

    def __init__(self, debug=False, force_file_locking=False):
        """
        The parameter `force_file_locking` allows the user of this class
        to force the use of file-based locking rather than socket-based
        locking.
        """
        # Use file-locking in these three conditions:
        # - The user has demanded it
        # - We have failed to import the socket libraries
        # - We are running on a SarOS system
        self.debug = debug
        if force_file_locking == True:
            self.__dbg("File locking force. use_socket = False")
            self.use_socket = False

        elif USE_SOCKET == False:
            self.__dbg("Socket library not found. use_socket = False")
            self.use_socket = False

        elif is_saros():
            self.__dbg("Running on SarOS. use_socket = False")
            self.use_socket = False
            # This sets the lock file to use the /tmp virtual directory
            # on SarOS.
            self.lock_file_name = "/tmp/" + self.lock_file_name
            self.__dbg("Lock filename: ", self.lock_file_name)

        else:
            self.__dbg("use_socket = True")
            self.use_socket = True

        if not is_saros():
            # NDS devices, when opening an atomic file lock, will crash
            # if not given an absolute path.

            # That said, though, NDS devices in the real world should be
            # using a socket lock. File locks are only for operating
            # systems with poor socket implementations or few sockets
            # available.
            self.lock_file_name = os.getcwd() + os.sep + self.lock_file_name

    def lock(self):
        """
        Creates a file lock, using either a socket or file lock,
        based on whether or not our current configuration supports
        running a socket lock.
        """
        if is_saros():
            return self._make_saros_lock()
        else:
            if self.use_socket:
                return self._make_socket_lock()
            else:
                return self._make_file_lock()

    def unlock(self):
        """
        Determine what method of lock was opened, and subsequently
        close it.
        """
        self.__dbg("Begin unlocking")
        if self.lock_saros is not None:
            del self.lock_saros
        if self.lock_file is not None:
            self.__dbg("Attempt file unlocking")
            try:
                # I have not found an OS with a Python where os.remove
                # does not exist. Hopefully this works in all operating systems
                os.remove(self.lock_file_name)
            except Exception, error_msg:
                self.__dbg("Encountered exception while unlocking file lock")
                self.__dbg(error_msg)
        if self.lock_socket is not None:
            self.__dbg("Attempt socket unlocking")
            try:
                self.lock_socket.close()
            except Exception, error_msg:
                self.__dbg("Encountered exception while unlocking socket lock")
                self.__dbg(error_msg)

    def _make_socket_lock(self):
        """
        This is an internal function, not to be used by external code.

        This creates a socket-based lock. This is the default type of
        locking mechanism, and should work for every operating system
        with a normally-behaving socket implementation. This is
        verified to work on Linux and NDS.

        This procedure works by creating a socket and binding it to
        a port on localhost. The binding will fail if the socket exists
        already, which makes this a fully atomic method of locking.
        """
        self._lock_type = self.SOCKET_LOCK
        self.__dbg("Begin making a socket lock")
        self.lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__dbg("Created the socket lock")
        try:
            self.lock_socket.bind(self.socket_tuple)
        except socket.error, error_msg:
            # If the socket address is already in use
            # This means there is another instance of DIA running
            if error_msg.args[0] == errno.EADDRINUSE:
                self.__dbg("Socket address is already in use")
                return False
            else:
                self.__dbg("Encountered an unknown type of socket.error:",
                           error_msg)
                raise LockingFailure(str(error_msg))
        else:
            # This command allows you to also check if the socket exists
            # by attempting to connect a client to a potentially-existing
            # server socket. This is not an atomic way of guaranteeing locking,
            # but this would work on SarOS.
            self.lock_socket.listen(1)
            self.__dbg("Successfully bound the socket lock")
            return True

    def _make_saros_lock(self):
        """
        This is an internal function, not to be used by external code.

        New versions of SarOS will come with a special locking library
        that offers a superior locking functionality than file-based locking.

        This procedure is to be used on SarOS systems that come with
        this special library.

        This code cannot be tested until a SarOS device has a release
        with a new library.
        """
        try:
            import digilock
        except ImportError:
            return self._make_file_lock()
        try:
            self.lock_saros = digilock.Lock("dia")
        # Lock creation failed
        except ValueError:
            return False
        # Unknown error...
        except Exception, e:
            self.__dbg("Lock creation failed: ", e)
            return False
        # At this point, we must be successful?
        return True

    def _make_file_lock(self):
        """
        This is an internal function, not to be used by external code.

        This procedure determines whether or not our system has the ability
        to run fully-atomic file locking code, which relies on the
        existence of `os.open`.
        """
        if 'open' in dir(os):
            return self._make_file_lock_atomic()
        else:
            return self._make_file_lock_nomatomic()

    def _make_file_lock_atomic(self):
        """
        This is an internal function, not to be used by external code.

        This function uses `os.open` to create a fully atomic
        file locking mechanism.  This is to be used on operating
        systems where sockets cannot be used for locking, but
        we have access to `os.open`.

        At the time of this writing, there is no platform that fits
        the above characteristics, so this procedure would go unused.
        However, this is here in the hopes that SarOS Python will
        come with `os.open`, allowing full atomicity in lockfiles
        for the platform.

        This function works by passing flags to `os.open` to
        ensure that it will fail to create a lockfile if
        the file already exists.
        """
        self._lock_type = self.ATOMIC_FILE_LOCK
        self.__dbg("Creating an atomic file lock")
        try:
            try:
                self.lock_file = os.open(self.lock_file_name,
                              # These flags make sure that a new
                              # file is created, and will raise
                              # an OSError
                              # if a file with the same name
                              # already exists. Prevents race
                              # conditions.
                              os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except OSError, error_msg:
                # If the file already exists. This means there is
                # another instance of DIA running.
                if error_msg.args[0] == errno.EEXIST:
                    self.__dbg("Creation failed. Lock file already exists.")
                    return False
                else:
                    self.__dbg("Creation failed. Unknown error.")
                    raise LockingFailure(str(error_msg))
            except IOError, error_msg:
                # SarOS Python gives this error code when it has
                # run out of space for virtual/temporary files
                # Only ten such files are available
                if error_msg.args[0] == 0:
                    self.__dbg("Creation failed. Probably ran out of space",
                               "for temporary files")
                raise LockingFailure(str(error_msg))
            else:
                return self._write_for_verification()
        except:
            self._emergency_cleanup()
            raise

    def _make_file_lock_nomatomic(self):
        """
        This is an internal function, not to be used by external code.
l
        On some operating systems (such as Digi SarOS), we may not have
        atomic file creation because `os.open` is missing AND the socket
        implementation is not suitable for use for file locking.

        This is an implementation of a non-atomic file locking system
        to use as a backup in those scenarios. This relies only on
        the existence of the Python built-in `open()` function.

        """
#==============================================================================
#         This procedure works by opening the lockfile for reading--which
#         should fail if the file does not exist. Upon failure, it creates
#         the lockfile by opening it for writing. We write a short string
#         to the file--this forces the device's operating system to
#         actually write the file to its permanent memory. Upon verification
#         that the string was written, we return True; the lockfile
#         has been created successfully.
#
#         If the initial read was successful, then we know that another
#         running instance of DIA created a lockfile, so return False
#         to signify that this instance of DIA should not keep running.
#==============================================================================
        self._lock_type = self.NONATOMIC_FILE_LOCK
        self.__dbg("Creating a nonatomic file lock")
        try:
            try:
                os.stat(self.lock_file_name)
            # File... probably... does not exist. Not sure
            # of the SarOS error code for this.
            except (OSError, IOError), error_msg:
                self.__dbg("Received an (expected) IOError/OSerror:", error_msg)
                self.__dbg("Lockfile must not exist. Attempting to create.")
                try:
                    self.lock_file = open(self.lock_file_name, 'w')
                except (OSError, IOError), error_msg:
                    self.__dbg("Lockfile creation failed.")
                    raise LockingFailure(str(error_msg))
                else:
                    return self._write_for_verification()
            else:
                self.__dbg("Lockfile seems to exist. Returning false.")
                # File exists
                return False
        except LockingFailure:
            self._emergency_cleanup()
            raise

    def _possible_no_space_exception(self, error_msg):
        """
        This handles the exception for when SarOS (probably) ran out
        of temporary files to allocate.
        """
        self.__dbg("Lockfile creation failed.")
        if error_msg.args[0] == 0 and\
            error_msg.__class__.__name__ == "IOError":
            self.__dbg("Exception raised, but error code is ambiguous.")
            self.__dbg("Probably ran out of space for temporary files")
        raise LockingFailure(str(error_msg))

    def _write_for_verification(self):
        """
        Some device operating systems will discard the lockfile we
        create if we were to leave it empty. That is why we write to
        the lockfile.
        """
        self.__dbg("Lockfile created. Begin writing for verification.")
        try:
            if type(self.lock_file) == int:
                os.write(self.lock_file, self.lock_file_contents)
                os.fsync(self.lock_file)
                os.close(self.lock_file)
            else:
                self.lock_file.write(self.lock_file_contents)
                self.lock_file.close()
        except (OSError, IOError), error_msg:
            self.__dbg("Failed to write/close the newly created",
                       "lock file")
            raise LockingFailure(str(error_msg))
        else:
            return self._verify_file_written()

    def _verify_file_written(self):
        """
        After we have created a file and written to it, we read
        the file to make sure that the contents we have written to
        it have been written successfully.
        """
        try:
            test = open(self.lock_file_name, 'r').read()
        except (OSError, IOError), error_msg:
            self.__dbg("Failed to verify that lockfile write",
                       "succeeded")
            raise LockingFailure(str(error_msg))
        else:
            if test == self.lock_file_contents:
                self.__dbg("Everything verified. Lockfile created",
                           "SUCCESSFULLY.")
                return True
            else:
                self.__dbg("Expected file contents:",
                         self.lock_file_contents)
                self.__dbg("Actual file contents:",
                           test)
                raise LockingFailure(
                    "Lockfile write verification failed")

    def _emergency_cleanup(self):
        """
        Use this when you have written a file and want to guard against
        raised exceptions leaving lockfiles that still exist after
        this instance of DIA quits.
        """
        try:
            os.remove(self.lock_file_name)
        except Exception, error_msg:
            self.__dbg("Encountered exception while attempting",
                       "emergency cleanup:")
            self.__dbg(str(error_msg))

    def __dbg(self, *msg):
        """
        Internal debugging function. If debugging is enabled, the
        program will print debug messages.
        """
        if self.debug:
            print ' '.join([str(part) for part in msg])
