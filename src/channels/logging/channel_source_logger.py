############################################################################
#                                                                          #
# Copyright (c)2008, Digi International (Digi). All Rights Reserved.	   #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its	   #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,	and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. Contact Product Management, Digi International, Inc., 11001 Bren   #
# Road East, Minnetonka, MN, +1 952-912-3444, for commercial licensing	   #
# opportunities for non-Digi products.                                     #
#                                                                          #
# DIGI SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED   #
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A          #
# PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, #
# PROVIDED HEREUNDER IS PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND. #
# DIGI HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES,         #
# ENHANCEMENTS, OR MODIFICATIONS.                                          #
#                                                                          #
# IN NO EVENT SHALL DIGI BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,	   #
# SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS,   #
# ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF   #
# DIGI HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.                #
#                                                                          #
############################################################################

"""\
The ChannelSourceLogger uses a logger as its source.  As a log is stepped
through, the log produces samples that are passed to the channel source.
"""

# imports
from copy import copy
from exceptions import Exception
from channels.channel_source import ChannelSource
from samples.sample import Sample

# constants
from channels.channel import PERM_GET, OPT_NONE 

# exception classes
class LoggingChannelError(Exception):
    pass

# interface functions

# classes
class ChannelSourceLogger(ChannelSource):
    def __init__(self, initial=Sample(timestamp=0, value=0)):
        """\
        Create a ChannelSourceLogger; it implements the ChannelSource
        interface.
        """

        # channel meta-information
        self.type = ChannelSource._type_remap(self, type(initial.value))
        self.perms_mask = PERM_GET
        self.options = OPT_NONE

    	# the current sample for this channel:
    	self.__sample = initial


    def producer_get(self):
        """\
        Return a copy of the current sample object.
        
        This function should only be called by a DeviceProperties object.
        """
        return self.__sample

    def producer_set(self, sample):
        """\
        Update the current sample object.
        
        This function should only be called by a logging object.
        """
        self.type = ChannelSource._type_remap(self, type(sample.value))
        self.__sample = sample

    def consumer_get(self):
        """\
        Called from a channel wishing to read this property's data.
        
        Returns a copy of the current sample value.
        """
        if self.__sample is None:
            raise LoggingChannelError, "sample not available"
        
        return copy(self.__sample)

    def consumer_set(self, sample):
        """\
        Called from a channel wishing to write this property's data.
        
        Calls device driver set callback registered for this property
        before returning.
        """

        raise LoggingChannelError, "can't set sample for log channel"

    def consumer_refresh(self):
        """\
        Called from a channel wishing to have this property's value
        refreshed now.
        
        Calls the device driver refresh callback registered for this property.
        """

        raise LoggingChannelError, "can't refresh log channel"


# internal functions & classes

