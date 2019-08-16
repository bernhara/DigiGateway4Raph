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

# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
import sys
import traceback
from pprint import pformat

# constants

# exception classes


class TransformInitError(Exception):
    pass


# interface functions

# classes


class Dummy(object):
    pass


class Transform:
    """
    Allows a set of input channels to be transformed using simple expressions.

    Transform will return a single new channel that is the result of the
    application of an expression applied to a list of channels given as
    an input. In this implementation, transform is called from the
    **TransformsDevice**, and the list of channels and the expression supplied
    from a DIA configuration file.

    """

    #TODO: A transform should probably bind to the settings tree so
    #that we can let the settings code do some of the validation for
    #us.
    def __init__(self, parent, core_services, **kw):
        self.__parent = parent
        self.__core = core_services
        self.__name = kw['name']
        try:
            self.__unit = kw['unit']
        except:
            self.__unit = ""

        try:
            channels = kw['channels']
        except:
            raise TransformInitError\
                ("Missing required transform setting channels")

        try:
            self.expr = kw['expr']
        except:
            raise TransformInitError("Missing required transform setting expr")

        from core.tracing import get_tracer
        self.__tracer = get_tracer("Transform." + self.__name)

        cm = self.__core.get_service("channel_manager")

        self.__channel_names = []
        for chan in channels:
            try:
                parent.cdb.channel_get(chan)
            except:
                self.__tracer.warning("channel '%s' does not exist yet.", chan)
            self.__channel_names.append(chan)

        # subscribe to all the channels that drive our logic
        cp = cm.channel_publisher_get()
        for channel_name in self.__channel_names:
            #TODO: Might it be a good idea to have a worker thread to
            #queue transform updates to rather than directly in the
            #callback from each channels update function?
            cp.subscribe(channel_name, self.update)

        # try to create the device property with the proper type
        try:
            self.__create_property()
        except:
            self.__tracer.warning("Failed to create property, will " + 
                                  "retry on update")
            exc = sys.exc_info()
            self.__tracer.error(
                "".join(traceback.format_exception_only(exc[0], exc[1])))

    def __create_property(self):
        """
        This procedure accesses the parent of this object to add the property
        that this object will service.
        """
        val = self.eval()

        self.__parent.add_property(
            ChannelSourceDeviceProperty(
                name=self.__name, type=type(val),
                initial=Sample(timestamp=0, value=val, unit=self.__unit),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP)
            )

    def eval(self):
        """
        This procedure evaluates the Python expression in the DIA settings
        that defines how to transform the channels.

        This is accomplished by creating a set of local variables to pass
        to Python's built-in eval(), and then returns the result of
        running eval() on the expression.

        """

        # Compute initial value of channel, also gives us the type
        cdb = self.__parent.cdb
        # `c`  contains the Sample values for the channels specified in
        # template device's settings. c[0] refers to the first channel
        # listed in the settings (YML) file, and so forth.
        c = []
        # A dictionary containing the local variables to have when
        # evaluating the Python expression that transforms
        # the other channels
        d = {}

        try:

            for channel_name in self.__channel_names:
                chan = cdb.channel_get(channel_name)
                sample = chan.get()
                object_name, attrname = channel_name.split('.', 1)

                if not object_name in d:
                    d[object_name] = Dummy()

                setattr(d[object_name], attrname, sample)

                c.append(sample.value)

        except:
            raise ValueError\
                ("Transform(%s): WARNING: failed to perform get" + \
                 " on all channels" % self.__name)

        d["c"] = c

        try:
            value = eval(self.expr, {}, d)
        except:
            exc = sys.exc_info()
            raise ValueError\
                ("Transform(%s): ERROR: failed to evaluate expression:\n%s" \
                % (self.__name,
                    "".join(traceback.format_exception_only(exc[0], exc[1]))))

        return value

    def update(self, channel):
        """
        This checks the parent TransformsDevice object if it contains
        the property that the Transform object is defined for. If the
        property does not exist, update() creates it.

        Then it calls Transform.eval() to create a value for the
        TransformsDevice property. If this new value is different than
        the existing value, the property is updated.
        """
        if not self.__parent.property_exists(self.__name):
            try:
                self.__create_property()
            except Exception, e:
                self.__tracer.warning(
                    "cannot update property, it may not exist yet")
                self.__tracer.error("Error: %s" % str(e))
                return

        val = self.eval()
        old_val = self.__parent.property_get(self.__name).value
        if val != old_val:
            self.__parent.property_set(self.__name, Sample(value=val,
                                                           unit=self.__unit))


class TransformsDevice(DeviceBase):
    """
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.

    """

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        self.tlist = []

        cm = self.__core.get_service("channel_manager")
        self.cdb = cm.channel_database_get()

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Settings Table Definition:
        settings_list = [
            Setting(name='instance_list', type=list, required=True),
        ]

        ## Channel Properties Definition:
        ## Properties are added dynamically based on configured transforms
        property_list = []

        ## Initialize the Devicebase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):
        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        transforms = SettingsBase.get_setting(self, "instance_list")

        for t in transforms:
            try:
                self.tlist.append(Transform(self, self.__core, **t))
            except:
                self.__tracer.error("%s", sys.exc_info()[1])
                self.__tracer.error("Transform was %s", pformat(t))

        return True

    def stop(self):
        return True


    ## Locally defined functions:



# internal functions & classes
