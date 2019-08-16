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
A special XBee Config block which performs a simulated commissioning
button press to wake up potentially sleeping nodes.
"""

# TODO/FIXME, Question: Rather than a CB=1, perhaps we could wake up for the
# entire sequence by doing a SM=0?  We would need immediate apply, but
# not necessarily WR.  That gives us more time and may have less
# visible side-effects.  Needs consideration.

# The con to modifying SM is that it won't get reset unless there's a
# sleep block following us.  That may not happen.

# imports
from copy import copy
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo import \
    AbstractXBeeConfigBlockDDO
from devices.xbee.common.ddo import \
    GLOBAL_DDO_RETRY_ATTEMPTS as DDO_RETRY_ATTEMPTS

# classes

class XBeeConfigBlockWakeup(AbstractXBeeConfigBlockDDO):
    """\
    XBee DDO Configuration Block
    
    Implements an 
    :py:class:`~devices.xbee.xbee_config_blocks.xbee_config_block_ddo.AbstractXBeeConfigBlockDDO`
    for proper sequencing by the 
    :py:class:`~devices.xbee.xbee_device_manager.xbee_device_manager.XBeeDeviceManager`.

    This class will automatically be placed at the beginning of the chain of
    :py:class:`~devices.xbee.xbee_config_blocks.xbee_config_block.XBeeConfigBlock`
    objects by the
    :py:class:`~devices.xbee.xbee_device_manager.xbee_device_manager.XBeeDeviceManager`.
    It's purpose is to perform a
    commissioning button press on a node that is about to be fully
    configured.  This should result in the node being awake for 30
    seconds.  If this is a sleeping node, this increased window of
    wake time increases the ability to fully configure nodes.
    """  
    def __init__(self, ext_addr):
        """\
        Create an XBeeConfigBlockWakeup object.
        
        See :py:class:`~devices.xbee.xbee_config_blocks.xbee_config_block.XBeeConfigBlock`.
        """
        AbstractXBeeConfigBlockDDO.__init__(self, ext_addr)

    def apply_config(self):
        """\
        Apply the configuration actions to the node targeted by this object.
        
        After this method has been called the 
        :py:meth:`~devices.xbee.xbee_config_blocks.xbee_config_block.XBeeConfigBlock.is_complete`
        method will return True.
        
        See :py:class:`~devices.xbee.xbee_config_blocks.xbee_config_block.XBeeConfigBlock`.

        """

        try:
            if not AbstractXBeeConfigBlockDDO._is_applicable(self):
                # If the block is not applicable, mark this block as complete:
                return AbstractXBeeConfigBlockDDO.apply_config(self)
        except Exception, e:
            # trace message will be printed by _is_applicable() or
            # apply_config() upon exception.
            return False

        from core.tracing import get_tracer
        __tracer = get_tracer('XBeeConfigBlockWakeup')

        try:
            __tracer.debug("Trying 'CB=1' to '%s'",
                AbstractXBeeConfigBlockDDO.ext_addr_get(self))
            AbstractXBeeConfigBlockDDO.configurator_get(self).ddo_set_param(
                AbstractXBeeConfigBlockDDO.ext_addr_get(self),
                'CB', 1,
                retries=DDO_RETRY_ATTEMPTS)
        except Exception, e:
            __tracer.error("Trying 'CB=1' to '%s' failed (%s)",
                          AbstractXBeeConfigBlockDDO.ext_addr_get(self),
                          str(e))
            return False

        # This is called when all the settings have been successfully applied:
        return AbstractXBeeConfigBlockDDO.apply_config(self)


# internal functions & classes

