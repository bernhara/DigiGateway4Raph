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
from core.tracing import get_tracer
from common.utils import wild_subscribe, wild_unsubscribe, wild_match

# classes


class CSVDevice(DeviceBase):
    """\

  - name: CSVDevice
    driver: devices.csv_device:CSVDevice
    settings:
        channel_pattern: "*.csv_input"
        delimiter: ','
        column_names:
            - "timestamp"
            - "status"
            - "error_msg"


    CSVDevice is a virtual device that parsed a delimited stream of data.
    The delimited data is then returned to the source's parent driver as
    new properties named by the 'column_names' setting.  All properties
    created are of type 'str'.

    The source is determined by the 'channel_pattern' setting.  This setting
    supports ? and * tokens to identify multiple channels.

    channel_pattern - Name of the channels that will be subscribed to.

    delimiter - Symbol to split the sample by. Default is ','.

    column_names - How to name each column that results from the split.
                   If more columns appear than names give, names are generated
                   as 'column_1', 'column_2', depending on position in the
                   split sample.

    """

    anon = {}  # For unsubscribing

    def __init__(self, name, core_services):
        """
        Standard device init function.
        """
        from core.tracing import get_tracer
        self.__tracer = get_tracer("CSVDevice")
        self.__tracer.info("Initializing CSVDevice")
        self.name = name
        self.core = core_services
        self.tracer = get_tracer(name)

        self.tdict = {}
        self.prop_names = []
        self.dm = self.core.get_service("device_driver_manager")
        self.channel_manager = self.core.get_service('channel_manager')
        self.channel_database = self.channel_manager.channel_database_get()
        settings_list = [
            Setting(name='channel_pattern', type=str, required=True),
            Setting(name='delimiter', type=str, required=False,
                    default_value=','),
            Setting(name='column_names', type=list, default_value=[],
                    required=False),
        ]

        ##No properties defined at first
        property_list = [
        ]

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.name, self.core,
                                settings_list, property_list)

    def start(self):
        """
        This procedure processes that match the pattern, then subscribes
        to those channels to continue processing upon updates.
        """
        self.__tracer.info("Officially starting device")
        patt = SettingsBase.get_setting(self, "channel_pattern")
        # Initially process each channel. Relying solely on the callback
        # does not work because some channels (such as the ones from InfoDevice)
        # may never update beyond their initial setting.
        for channel_name in self.channel_database.channel_list():
            if wild_match(patt, channel_name):
                channel = self.channel_database.channel_get(channel_name)
                self.process_channel(channel)
        # Now that the CSVDevice has created the new channels, keep them
        # updated through subscription.
        self.anon[patt] = wild_subscribe(self.core,
                                         patt,
                                         self.process_channel)
        self.__tracer.info("Subscribed to all of the relevant channels")

        return True

    def stop(self):
        """
        Stops the driver.
        Unsubscribes from any channels subscribed to.
        """
        self.__tracer.info("Stopping device")
        if len(self.anon):
            patt = SettingsBase.get_setting(self, "channel_pattern")
            wild_unsubscribe(self.core,
                             patt,
                             self.anon[patt],
                             self.process_channel)
            self.__tracer.info("Completed unsubscribing")
        else:
            self.__tracer.info("No channels to unsubscribe from")
        return True

    def process_channel(self, channel):
        """
        Processes the given channel's sample.

        """
        channel_name = channel.name()
        column_names = SettingsBase.get_setting(self, "column_names")
        delimiter = SettingsBase.get_setting(self, "delimiter")

        channel_val = str(channel.get().value)

        fields = channel_val.split(delimiter)

        #If we don't know about this channel
        if not self.tdict.has_key(channel_name):
            ## Create property
            instance_name = channel_name.split(".", 1)[0]
            if not instance_name in self.dm.instance_list():
                self.tracer.error("Unable to place name: %s in list: %s" %
                                  (instance_name,
                                   str(self.dm.instance_list())))

            #Get the instance
            driver_instance = self.dm.instance_get(instance_name)

            #Assign the dictionary the driver_instance
            self.tdict[channel_name] = driver_instance
        else:
            driver_instance = self.tdict[channel_name]

        #Get the column names
        columns = CSVDevice.get_column_names(column_names, fields)

        #For each value, name, if the property doesn't exist,
        #Create it, otherwise just set it using the driver instance
        for value, column_name in zip(fields, columns):
            if not driver_instance.property_exists(column_name):
                driver_instance.add_property(
                      ChannelSourceDeviceProperty(
                          name=column_name,
                          type=str,
                          initial=Sample(timestamp=0, value=value),
                          perms_mask=DPROP_PERM_GET,
                          options=DPROP_OPT_AUTOTIMESTAMP)
                      )
            else:
                driver_instance.property_set(column_name, Sample(0, value))
        #endfor

    @staticmethod
    def get_column_names(column_names, fields):
        """
        Returns a list of the assigned column names based on setting,
        supplementing this with names as needed based on which position the
        field is in.

        """
        columns = []
        column_base = 'column_%d'
        for pos in range(len(fields)):
            # column_names will be None if the user did not specify
            # any column names in the YAML
            if column_names is None or len(column_names[pos:]) == 0:
                columns.append(column_base % (pos + 1))
            else:
                columns.append(column_names[pos])
        return columns
