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
The XBee configuration block base class definition module.

Contained in this module is the definition of the :class:`XBeeConfigBlock`
class.  Objects are derived from :class:`XBeeConfigBlock` and created in
XBee device drivers and registered with the
:py:class:`~devices.xbee.xbee_device_manager.xbee_device_manager.XBeeDeviceManager`
in order to be executed on the XBee device node at configuration time.

"""

# imports
from devices.xbee.common.addressing import normalize_address
from devices.xbee.common.prodid import parse_dd
from devices.xbee.common.ddo import \
    GLOBAL_DDO_RETRY_ATTEMPTS as DDO_RETRY_ATTEMPTS

# exception classes

# interface functions


# classes
class XBeeConfigBlock:
    """
    :py:class:`XBeeConfigBlock` base class definition.

    :py:class:`XBeeConfigBlock` instances are executed in registered order by the
    :py:class:`~devices.xbee.xbee_device_manager.xbee_device_manager.XBeeDeviceManager`.
    This is done by calling each derived
    :py:class:`XBeeConfigBlock` instance's :py:meth:`apply_config` method to attempt
    to transition the configuration block into its completed state.  When all
    XBee configuration blocks test as complete via the :py:meth:`is_complete`
    method the target XBee node is considered to be configured and it is
    transitioned to the running state by the
    :py:class:`~devices.xbee.xbee_device_manager.xbee_device_manager.XBeeDeviceManager`.

    :py:class:`XBeeConfigBlock` instances also carry a framework for only applying
    configuration to nodes which match a set of module or product
    identification information.  This functionality is intended to be utilized
    by XBee drivers initializing the configuration block by calling one of the
    :py:meth:`apply_only_to_modules`, :py:meth:`apply_except_to_modules`,
    :py:meth:`apply_only_to_products`, or :py:meth:`apply_except_to_products` and
    then testing the fitness of the block by calling the
    :py:meth:`~devices.xbee.xbee_config_blocks.xbee_config_block._is_applicable`
    method from a :py:meth:`apply_config` method of a
    derived class.  See :py:meth:`apply_config` for more information.

    """

    CONFIG_INCOMPLETE = 0
    CONFIG_COMPLETE = 1

    APPLICABILITY_ALL = 0
    APPLICABILITY_ONLY = 1
    APPLICABILITY_EXCEPT = 2

    def __init__(self, ext_addr):
        """
        Instantiate a :py:class:`XBeeConfigBlock`.

        Parameters:
            * **ext_addr**: the extended address of the node to which this
                            configuration will be applied.

        """

        ## State information:
        # The extended address of the target node to be configured:
        self._ext_addr = ext_addr
        # A reference to the appropriate XBeeDeviceManagerConfigurator:
        self.__configurator = None
        # Applicable/un-applicable modules identifiers:
        self.__modules = ( )
        # Applicable/un-applicable product identifiers:
        self.__products = ( )
        # Applicability modes:
        self.__module_applicability = self.APPLICABILITY_ALL
        self.__product_applicability = self.APPLICABILITY_ALL

        if self._ext_addr != None:
            self._ext_addr = normalize_address(ext_addr)

        # Initialization:
        self.reset()

    def ext_addr_get(self):
        """Get the extended address of the node assigned to this block."""
        return self._ext_addr

    def ext_addr_set(self, ext_addr):
        """Set the extended address of the node assigned to this block.

           Calling this function resets the state of the configuration
           block to its incomplete state.

           Parameters:
               * **ext_addr**: the extended address of the node to be assigned
                               to this block
           Return type:
               * None

        """
        if ext_addr != None:
            self._ext_addr = ext_addr.lower()
        else:
            self._ext_addr = ext_addr
        self.reset()

    def configurator_set(self, configurator):
        """Set the reference to the XBeeDeviceManagerConfigurator instance."""
        self.__configurator = configurator

    def configurator_get(self):
        """Get the reference to the XBeeDeviceManagerConfigurator instance."""
        return self.__configurator

    def xbee_device_manager_get(self):
        """
        Get the reference to the XBeeDeviceManager instance.

        This method uses the reference to the
        :py:class:`~devices.xbee.xbee_device_manager.xbee_device_manager_configurator.XBeeDeviceManagerConfigurator`.
        Set by the
        :meth:`configurator_set` method.

        Return type:
            * :py:class:`~devices.xbee.xbee_device_manager.xbee_device_manager_configurator.XBeeDeviceManagerConfigurator`
              instance or None

        """

        return self.__configurator.xbee_device_manager_get()

    def apply_config(self):
        """
        Apply the configuration actions to the node targeted by this object.

        This method is intended to be extended by derived classes in order
        to perform a list of actions on the target node.  This method
        should be called by the derived method in order to advance the
        state machine of the object to its completed state.

        After this method has been called the :meth:`is_complete` method
        will return True.

        It is expected that an extended version of this function will
        begin by calling
        :meth:`_is_applicable`
        in order to test if
        the configuration is valid for the current XBee module and product
        combination.  An example apply_config() implementation would be::

            def apply_config(self):
                if not XBeeConfigBlock._is_applicable(self):
                    # If the block is not applicable, mark this block as complete:
                    return XBeeConfigBlock.apply_config(self)

                # else, do work to apply configuration to XBee

                # finally:
                return XBeeConfigBlock.apply_config(self)

        Return type:
            * bool

        """

        self.__state = self.CONFIG_COMPLETE
        return True

    def reset(self):
        """
        Reset the state of this object.

        This will cause :meth:`is_complete` to return False.

        This method should be extended by derived classes in order to
        reset any state information.  This method will be called when the
        :py:class:`~devices.xbee.xbee_device_manager.xbee_device_manager.XBeeDeviceManager`
        desires to reconfigure

        """

        self.__state = self.CONFIG_INCOMPLETE

    def is_complete(self):
        """
        Returns whether or not the configuration block had been successfully
        applied.

        If the :meth:`apply_config` method was successful, this function will
        return True.

        Return type:
            * bool

        """

        return self.__state == self.CONFIG_COMPLETE

    def __iter_test(self, item):
        """
        Internal convenience function to test if a given item is a sequence.

        """

        try:
            iter(item)
        except:
            raise TypeError, "argument must be iterable sequence"

    def apply_only_to_modules(self, module_seq):
        """
        Marks this configuration block to only be applicable for the
        given sequence of module_ids.

        See :py:mod:`~devices.xbee.common.prodid` for a list of valid
        module_ids.

        .. note:: One may not mix the :meth:`apply_only_to_modules`
                  and :meth:`apply_except_to_modules` methods.  Only
                  one may be used on a given object at a time.

                  Additionally, only one type of exclusion style may
                  be used if mixing module and product id filtering.
                  That is to say, if both types of filtering are being
                  used then only :meth:`apply_only_to_modules` and
                  :meth:`apply_only_to_products` or
                  :meth:`apply_except_to_modules` and
                  :meth:`apply_except_to_prodcuts` may be used together.
                  You may not mix :meth:`apply_only_to_modules` and
                  :meth:`apply_except_to_prodcuts`, for example.

        Parameters:
            * **module_seq**: a sequence of module_id integers

        Return type:
            * None

        """
        self.__iter_test(module_seq)
        self.__modules = module_seq
        self.__module_applicability = self.APPLICABILITY_ONLY

    def apply_except_to_modules(self, module_seq):
        """
        Marks this configuration block to only be applicable for modules
        not given in the sequence of module_ids.

        See :py:mod:`~devices.xbee.common.prodid` for a list of valid
        module_ids.

        .. note:: One may not mix the :meth:`apply_only_to_modules`
                  and :meth:`apply_except_to_modules` methods.  Only
                  one may be used on a given object at a time.

                  Additionally, only one type of exclusion style may
                  be used if mixing module and product id filtering.
                  That is to say, if both types of filtering are being
                  used then only :meth:`apply_only_to_modules` and
                  :meth:`apply_only_to_products` or
                  :meth:`apply_except_to_modules` and
                  :meth:`apply_except_to_prodcuts` may be used together.
                  You may not mix :meth:`apply_only_to_modules` and
                  :meth:`apply_except_to_prodcuts`, for example.

        Parameters:
            * **module_seq**: a sequence of module_id integers

        Return type:
            * None

        """
        self.__iter_test(module_seq)
        self.__modules = module_seq
        self.__module_applicability = self.APPLICABILITY_EXCEPT

    def apply_only_to_products(self, product_seq):
        """
        Marks this configuration block to only be applicable for products
        given in the sequence of product_ids.

        See :mod:`~devices.xbee.common.prodid` for a list of valid
        module_ids.

        .. note:: One may not mix the :meth:`apply_only_to_products`
                  and :meth:`apply_except_to_products` methods.  Only
                  one may be used on a given object at a time.

                  Additionally, only one type of exclusion style may
                  be used if mixing module and product id filtering.
                  That is to say, if both types of filtering are being
                  used then only :meth:`apply_only_to_modules` and
                  :meth:`apply_only_to_products` or
                  :meth:`apply_except_to_modules` and
                  :meth:`apply_except_to_prodcuts` may be used together.
                  You may not mix :meth:`apply_only_to_modules` and
                  :meth:`apply_except_to_prodcuts`, for example.

        Parameters:
            * **product_seq**: a sequence of product_id integers

        Return type:
            * None

        """
        self.__iter_test(product_seq)
        self.__products = product_seq
        self.__module_applicability = self.APPLICABILITY_ONLY

    def apply_except_to_products(self, product_seq):
        """
        Marks this configuration block to only be applicable for products
        not given in the sequence of product_ids.

        See :mod:`~devices.xbee.common.prodid` for a list of valid
        module_ids.

        .. note:: One may not mix the :meth:`apply_only_to_products`
                  and :meth:`apply_except_to_products` methods.  Only
                  one may be used on a given object at a time.

                  Additionally, only one type of exclusion style may
                  be used if mixing module and product id filtering.
                  That is to say, if both types of filtering are being
                  used then only :meth:`apply_only_to_modules` and
                  :meth:`apply_only_to_products` or
                  :meth:`apply_except_to_modules` and
                  :meth:`apply_except_to_prodcuts` may be used together.
                  You may not mix :meth:`apply_only_to_modules` and
                  :meth:`apply_except_to_prodcuts`, for example.

        Parameters:
            * **product_seq**: a sequence of product_id integers

        Return type:
            * None

        """
        self.__iter_test(product_seq)
        self.__products = product_seq
        self.__module_applicability = self.APPLICABILITY_EXCEPT

    def _is_applicable(self, xbee_dd_ddo_value=None):
        """
        Test if this XBee configuration block is applicable given
        combinations of apply_except_* and apply_only_* filters.

        This method is intended to be used by derived classes in order
        to test applicability before allowing :meth:`apply_config` to
        perform any actions.  See :meth:`apply_config` for a code
        example.

        This method may be hinted with `xbee_dd_ddo_value` in order to
        avoid this method from attempting to access the network (or
        hit the DDO parameter cache) to determine which module_id
        and product_id are valid for the extended address of the node
        this XBee configuration block will act upon.

        Parameters:
            * **xbee_dd_ddo_value**: an XBee DD DDO value that will be decoded
                                     to a module_id and product_id.
        Return type:
            * bool

        """
        if not xbee_dd_ddo_value:
            xbee_dd_ddo_value = self.__configurator.ddo_get_param(
                                    self._ext_addr,
                                    'DD',
                                    retries=DDO_RETRY_ATTEMPTS,
                                    use_cache=True)

        module_id, product_id = parse_dd(xbee_dd_ddo_value)

        applicability = True

        if self.__module_applicability == self.APPLICABILITY_ONLY:
            applicability &= module_id in self.__modules
        elif self.__module_applicability == self.APPLICABILITY_EXCEPT:
            applicability &= module_id not in self.__modules

        if self.__product_applicability == self.APPLICABILITY_ONLY:
            applicability &= product_id in self.__products
        elif self.__product_applicability == self.APPLICABILITY_EXCEPT:
            applicability &= product_id not in self.__products

        return applicability


# internal functions & classes
