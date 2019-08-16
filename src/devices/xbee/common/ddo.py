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
    Helper functions related to performing ddo requests.
"""

# imports
try:
    import xbee
except:
    import zigbee as xbee

# constants
GLOBAL_DDO_TIMEOUT = 30.0
GLOBAL_DDO_RETRY_ATTEMPTS = 1

# class definitions
class DDOTimeoutException(Exception):
    pass

# function declarations

def retry_ddo_set_param(retries, ext_addr, param, value = '',
                    timeout = GLOBAL_DDO_TIMEOUT,
                    order = None, apply = None):
    """\
        Attempt to set a DDO param on an XBee device.

        This function will attempt to send a DDO command/parameter
        to a local or remote XBee device.
        It will attempt to send the command/parameter up to 'retries' times.

        Returns the result, or None on failure.

    """

    result = None
    while 1:
        try:
            if order is not None or apply is not None:
                # new style (ConnectPort version > 2.8.3) parameters:
                result = xbee.ddo_set_param(ext_addr, param, value, timeout,
                            order = order, apply = apply)
            else:
                # old style parameters:
                result = xbee.ddo_set_param(ext_addr, param, value, timeout)
            break
        except:
            retries -= 1
            if retries > 0:
                continue
            raise DDOTimeoutException, "could not set '%s' on '%s'" % (param,
                                                                    ext_addr)

    return result


def retry_ddo_get_param(retries, ext_addr, param, timeout = GLOBAL_DDO_TIMEOUT):
    """\
        Attempt to get a DDO param from an XBee device.

        This function will attempt to get a DDO command/parameter
        from a local or remote XBee device.
        It will attempt to get the command/parameter up to 'retries' times.

        Returns the result, or None on failure.

    """

    result = None
    while 1:
        try:
            result = xbee.ddo_get_param(ext_addr, param, timeout)
            break
        except:
            retries -= 1
            if retries > 0:
                continue
            raise DDOTimeoutException('could not get "%s" from "%s"' % (
                (param, ext_addr)))
    return result
