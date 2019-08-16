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
    The Xbee Device Manager Event Specs base class, as well as
    a few various classes built upon the base class.


    An event spec is a tuple:
    (addr, endpoint, profile_id, cluster_id)

    The mask is an (inverted) Boolean, so True means check this field.

    (True, False, False, True) means addr and cluster_id must match.

"""

# imports
import string

from devices.xbee.common.addressing import addresses_equal

# constants

# exception classes

# interface functions

# classes

class XBeeDeviceManagerEventSpec:
    """\
        The Event Spec base class.

        This class is the foundation class to build various different
        Event Spec classes around.

    """
    def __init__(self):
        self.__cb = None

    def cb_set(self, cb):
        self.__cb = cb


    def cb_get(self):
        return self.__cb


    def match_spec_set(self, *args, **kwargs):
        """\
        This function's calling interface is allowed to change, it is
        never called by the device manager.

        """
        raise NotImplementedError("virtual function")


    def match_spec_test(self, candidate):
        raise NotImplementedError("virtual function")


class XBeeDeviceManagerRxEventSpec(XBeeDeviceManagerEventSpec):
    """\
        The Rx Event Spec class.

        XBeeDeviceManagerRxEventSpec is called when data comes
        in from a specific XBee device that matches the given
        specs.

    """
    def __init__(self):
        self._match_spec = None
        self._match_mask = None
        self._listen_endpoint = None

        XBeeDeviceManagerEventSpec.__init__(self)

    def get_listen_endpoint(self):
        if self._listen_endpoint != None:
            return self._listen_endpoint
        else:
            return self._match_spec[1]

    def _check_addr(self, addr, varname="addr"):
        if not (isinstance(addr, tuple) and len(addr) >= 4):
            raise AttributeError(
                "bad %s, must be tuple of >= length 4. (%s given)" \
                % (varname, addr))

        if not isinstance(addr[0], str) and addr[0] != None:
            raise AttributeError(
                "bad %s, first item must be string or None" % (varname))

        if not reduce(lambda p, q: p and isinstance(q, int), addr[1:4], True):
            raise AttributeError(
                "bad %s, [1:4] must be integers." % (varname))

    def match_spec_set(self, match_spec, match_mask, listen_endpoint=None):

        self._check_addr(match_spec, "match_spec")

        # is our listen endopoint different than the one passed in
        # the match spec?    (0 is a valid endpoint)
        if listen_endpoint != None:
            self._listen_endpoint = listen_endpoint

        if not (isinstance(match_mask, tuple) and len(match_mask) == 4):
            raise AttributeError("bad match_mask, must be tuple of length 4.")

        if not reduce(lambda p, q: p and \
                      isinstance(q, bool), match_mask, True):
            raise AttributeError("bad match_spec, [0:4] must be booleans.")

        if match_spec[0] != None:
            addr = match_spec[0].lower()
        else:
            addr = match_spec[0]
        final_match_spec = (addr, match_spec[1], match_spec[2], match_spec[3])

        self._match_spec = final_match_spec
        self._match_mask = match_mask


    def match_spec_get(self):
        return (self._match_spec, self._match_mask)


    def match_spec_test(self, candidate, mac_prematch=False):
        if not mac_prematch:
            self._check_addr(candidate, "candidate")

        # TODO: move stripping logic into common addressing helper lib:
        if self._match_mask[0] and \
               not addresses_equal(self._match_spec[0], candidate[0]):
            return False

      ##Couple of points to make here.  We only match elements 1-3, and allow
      ##Short circuiting the if comparison. spec and mask are moved into local
      ##scope for performance boost instead of being class variables.

      ##Return False if not matched,
      ##Return True if matched.

        spec = self._match_spec
        mask = self._match_mask

        if not ((not mask[1] or (candidate[1] == spec[1])) and
                (not mask[2] or (candidate[2] == spec[2])) and
                (not mask[3] or (candidate[3] == spec[3]))):
            return False
        return True


class XBeeDeviceManagerRxConfigEventSpec(XBeeDeviceManagerRxEventSpec):
    """
    The Rx Config Event Spec class.

    XBeeDeviceManagerRxConfigEventSpec is a XBeeDeviceManagerRxEventSpec
    except that its callbacks get processed when a device is in the
    config state instead of the running state.

    """
    pass


class XBeeDeviceManagerRunningEventSpec(XBeeDeviceManagerEventSpec):
    """
    The Running Event Spec class.

    XBeeDeviceManagerRunningEventSpec is called when a device enters
    the running state.

    """
    def match_spec_set(self):
        pass


    def match_spec_test(self):
        pass
