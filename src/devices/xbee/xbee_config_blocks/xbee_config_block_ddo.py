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
The XBee Config Block DDO module, definitions for abstract and concrete
implementations of configuration blocks which set remote parameters on
XBee modules via Digi Device Objects ("DDO").

.. py:data:: DDO_SET_PARAM
        Set a DDO Parameter

.. py:data:: DDO_GET_PARAM
        Get a DDO Parameter

"""

# imports
from copy import copy
from common.helpers.format_strings import format_hexrepr
from devices.xbee.xbee_config_blocks.xbee_config_block import XBeeConfigBlock
from devices.xbee.common.ddo import \
    GLOBAL_DDO_RETRY_ATTEMPTS as DDO_RETRY_ATTEMPTS

# constants
DDO_SET_PARAM = 0x1
DDO_GET_PARAM = 0x2


# exception classes
class XBeeConfigBlockDDOInvalidParameter(ValueError):
    pass

# classes
class AbstractXBeeConfigBlockDDO(XBeeConfigBlock):
    """\
    Abstract XBee DDO Configuration Block

    All configuration blocks which send DDO commands _must_ inherit from
    this class so they may be properly sequenced by the XBee Device
    Manager.
    """
    def __init__(self, ext_addr):
        XBeeConfigBlock.__init__(self, ext_addr)


class XBeeConfigBlockDDO(AbstractXBeeConfigBlockDDO):
    """\
    XBee DDO Configuration Block

    Implements an
    :py:class:`~devices.xbee.xbee_config_blocks.xbee_config_block_ddo.AbstractXBeeConfigBlockDDO`
    for proper sequencing by the
    :py:class:`~devices.xbee.xbee_device_manager.xbee_device_manager.XBeeDeviceManager`.

    This class collects a number of parameters to be applied to a
    remote XBee node via the :py:meth:`add_parameter`
    method when called by the XBee driver implementation and then
    applies them to the node when :meth:`apply_config` is called
    indirectly from the
    :py:class:`~devices.xbee.xbee_device_manager.xbee_device_manager.XBeeDeviceManager`.

    """

    def __init__(self, ext_addr):
        # format for below: { 'XX': (value, method, failure_callback), ... }
        self.__parameters = {}
        self.__pending_parameters = {}

        from core.tracing import get_tracer
        self.__tracer = get_tracer('XBeeConfigBlockDDO')

        AbstractXBeeConfigBlockDDO.__init__(self, ext_addr)

    def __len__(self):
        return len(self.__pending_parameters)

    def __str__(self):
        return '<pending: %s  applied: %s>' % (str(self.__pending_parameters),
                                               str(self.__parameters))

    def add_parameter(self, mnemonic, value,
                        method=DDO_SET_PARAM, failure_callback=None):
        """\
        Add a DDO parameter to be applied to the remote node.

        Sleep related parameters may not be added to this configuration
        block.  Instead a
        :py:class:`~devices.xbee.xbee_config_blocks.xbee_config_block_sleep.XBeeConfigBlockSleep`.
        configuration block must be used.

        For the `method` :py:const:`DDO_GET_PARAM`
        it is useful to have the given
        parameter be stored in the system DDO parameter cache.

        if a `failure_callback` is specified, the function will be called
        if the individual parameter should fail.  The function will be called
        with two parameters: the mnemonic that failed and the value that
        failed.

        If the `failure_callback` returns True then the DDO
        parameter failure will be ignored and the configuration block will
        continue to apply its parameters.  This functionality may be used
        to ignore specific parameter application failures within driver
        implementations.

        Parameters:
            * **mnemonic**: string of a two-letter DDO mnemonic
            * **value**: int or string value to be set for the given DDO mnemonic
            * **method**: :py:const:`DDO_SET_PARAM` or :py:const:`DDO_GET_PARAM`.
            * **failure_callback**: a function reference

        """

        if not isinstance(mnemonic, str) and len(mnemonic) == 2:
            raise AttributeError, "mnemonic must be a string of length 2"

        if mnemonic in ['SP', 'SN', 'SP', 'ST', 'SO']:
            # We cannot set sleep related parameters here:
            raise XBeeConfigBlockDDOInvalidParameter, \
                "sleep options must be controled with sleep config block."

        if (method == DDO_SET_PARAM and value is None):
            raise XBeeConfigBlockDDOInvalidParameter, \
                "method may not be DDO_SET_PARAM if value is None."

        if (method == DDO_GET_PARAM and value is not None):
            raise XBeeConfigBlockDDOInvalidParameter, \
                "method may not be DDO_GET_PARAM if value is not None."

        self.__parameters[mnemonic] = (value, method, failure_callback)
        self.__pending_parameters[mnemonic] = (value, method, failure_callback)

    def reset(self):
        """\
        Reset the state of this configuration block object.

        See :py:class:`~devices.xbee.xbee_config_blocks.xbee_config_block.XBeeConfigBlock`.

        """

        self.__pending_parameters = copy(self.__parameters)
        # Complete the state reset:
        AbstractXBeeConfigBlockDDO.reset(self)

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
            self.__tracer.warning('Could not communicate with %s... ' \
                                  'postponing configuration.', self._ext_addr)
            return False

        pending_mnemonics = self.__pending_parameters.keys()
        for mnemonic in pending_mnemonics:
            value, method, callback = self.__pending_parameters[mnemonic]
            try:
                if method == DDO_SET_PARAM:
                    self.__tracer.debug("Apply_config: trying " +
                                        "SET '%s' = '%s' to '%s'",
                                        mnemonic,
                                        format_hexrepr(value),
                                        AbstractXBeeConfigBlockDDO.\
                                        ext_addr_get(self))

                    (AbstractXBeeConfigBlockDDO
                       .configurator_get(self).ddo_set_param(
                           AbstractXBeeConfigBlockDDO.ext_addr_get(self),
                           mnemonic, value, retries=DDO_RETRY_ATTEMPTS))
                else:
                    # DDO_GET_PARAM
                    self.__tracer.debug("Trying GET '%s' from '%s'",
                                        mnemonic,
                                        AbstractXBeeConfigBlockDDO.\
                                        ext_addr_get(self))

                    AbstractXBeeConfigBlockDDO\
                       .configurator_get(self)\
                         .ddo_get_param(
                           AbstractXBeeConfigBlockDDO.ext_addr_get(self),
                           mnemonic, retries=DDO_RETRY_ATTEMPTS,
                           use_cache=False)
            except Exception, e:
                self.__tracer.warning("Req to '%s' of '%s' failed (%s)",
                                      AbstractXBeeConfigBlockDDO.\
                                      ext_addr_get(self),
                                      mnemonic,
                                      str(e))

                # If a callback on failure was specified, the caller wants to
                # know about the failure, and decide whether it doesn't care
                # if the DDO failed.
                # If the caller returns True in the callback, this means that
                # the caller wants us to ignore the failure, and thus,
                # we should NOT throw an exception.
                # On the other hand, if there is no callback specified,
                # of if the callback function returns False, then raise the
                # exception like usual.
                if callback != None:
                    ret = callback(mnemonic, value)
                    if ret == True:
                        self.__tracer.warning('Ignore previous warning')
                    else:
                        raise
                else:
                    raise

            del(self.__pending_parameters[mnemonic])

        # NOTE: We do NOT apply changes here.  All config block
        # changes will be applied when the final 'WR' is performed

        # This is called when all the settings have been successfully applied:
        return AbstractXBeeConfigBlockDDO.apply_config(self)


# internal functions & classes
