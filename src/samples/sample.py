############################################################################
#                                                                          #
# Copyright (c)2008-2013, Digi International (Digi). All Rights Reserved.  #
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

# imports
import traceback
import digitime

# import status

# constants

# exception classes

# interface functions

# classes

class Sample(object):
    """
    Core object for the representation of data in DIA.  Typically
    produced by :class:`device drivers
    <devices.device_base.DeviceBase>`, stored in the :class:`channel
    database <channels.channel_database.ChannelDatabase>`, logged by
    :class:`loggers <channels.logging.logger_base.LoggerBase>` and
    communicated outside the system by :class:`presentations
    <presentations.presentation_base.PresentationBase>`

    Contains the following public attributes:

    .. py:attribute:: timestamp

       Time value at which the sample was acquired

    .. py:attribute:: value

       Object representing the sampled data

    .. py:attribute:: unit

       A string that annotates any possible units that may apply to
       the `value`

    .. py:attribute:: quality

       An integer defining trustworthiness or quality of the `value`

    """

    # Using slots saves memory by keeping __dict__ undefined.
    __slots__ = ["timestamp", "value", "unit", "status"]

    def __init__(self, timestamp=0, value=0, unit="", status=0):
        self.timestamp = timestamp
        self.value = value
        self.unit = unit
        self.status = status
        # self.status = status.DataStatus(stat)

    def __repr__(self):
        # Certain types, like tuples, will not properly convert to
        # a string when using Python's "%" string formatting.
        # In order to avoid a TypeError, we wrap `self.value` in
        # str(), which successfully converts the type to a string.
        st = ['<Sample: %s' % str(self.value)]

        if len(self.unit) > 0:
            st.append(self.unit)

        if self.status:
            if self.status != 0x80000000:
                st.append(' sts:0x%08X' % self.status)
            else:
                st.append(' sts:OK')

        try:
            st.append( " at %s>" % digitime.form_iso_date_str(self.timestamp))

        except:
            traceback.print_exc()
            st.append( " at %d>" % self.timestamp)

        return "".join(st)

# internal functions & classes
