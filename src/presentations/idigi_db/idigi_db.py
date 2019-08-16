############################################################################
#                                                                          #
# Copyright (c)2008, 2009 Digi International (Digi). All Rights Reserved.  #
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
Database Synchronization Module
"""

# imports
from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase
from common.helpers.format_channels import iso_date
from common.digi_device_info import get_platform_name
from core.tracing import get_tracer
from channels.channel_source_device_property import DPROP_PERM_GET

import threading
import digitime
import cStringIO

# Because the idigi_data module can be external to DIA, we should try/except
# around it, just in case the user does not have the module for some reason.
try:
    import idigi_data
except:
    _tracer = get_tracer("idigi_db")
    _tracer.critical("Unable to import idigi_data!")
    raise


# constants
ENTITY_MAP = {
    "<": "&lt;",
    ">": "&gt;",
    "&": "&amp;",
    "\"": "&quot;",
    "'": "&apos;",
}

# exception classes

# interface functions

# classes
class iDigi_DB(PresentationBase, threading.Thread):

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
        self.__stopevent = core_services

        self.__tracer = get_tracer(name)

         # Settings
         # initial_upload: is the number of seconds before the first initial
         #     upload.  If it is not specified, initial upload is disabled.
         # interval: is the maximum interval in seconds that this module waits
         #     before sending data to the Device Cloud Manager Database.  If it is
         #     equal to 0, the feature is disabled.
         # sample_threshold: is the mininum number of samples required before
         #     sending data to the Device Cloud Manager Database.  If it is equal to
         #     0, the feature is disabled.
         # collection: is the collection on the database where the data will
         #     be stored.
         # file_count: the number of unique files we will keep on Device Cloud.
         # filename: the name of the xml file we will push to Device Cloud, with
         #     a number appended to the end (cycling from 1 to file_count)
         # channels: is the list of channels the module is subscribed to.
         #     If no channels are listed, all channels are subscribed to.
         # compact_xml: (when set to True) will produce output XML with the
         #     information stored as attributes to the sample node instead of
         #     separately tagged, resulting in smaller XML output.

        settings_list = [
           Setting(
              name='initial_upload', type=int, required=False,
              default_value=None),
           Setting(
              name='interval', type=int, required=False,
              default_value=60),
           Setting(
              name='sample_threshold', type=int, required=False,
              default_value=10),
           Setting(
              name='collection', type=str, required=False,
              default_value=""),
           Setting(
              name="channels", type=list, required=False,
              default_value=[]),
           Setting(
              name='file_count', type=int, required=False,
              default_value=20),
           Setting(
              name='filename', type=str, required=False,
              default_value="sample"),
           Setting(
              name='secure', type=bool, required=False,
              default_value=True),
           Setting(
              name='compact_xml', type=bool, required=False,
              default_value=False),
        ]

        PresentationBase.__init__(self, name=name,
                                   settings_list=settings_list)
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    def start(self):

        # Verify that the user has a reasonable Device Cloud host set on their device.
        if hasattr(idigi_data, 'get_idigi_values'):
            host, token, path, port, secureport = idigi_data.get_idigi_values()
            if host == None or host == "" or host == " ":
                self.__tracer.error("Host '%s' is not a valid value. " +
                      "Please check your device and set the Host value " +
                      "appropriately", host)
                raise ValueError("name must be a non-empty string")

        # Start by appending 1 to filename of pushed data
        self.__current_file_number = 1

        # Event to use for notification of meeting the sample threshold
        self.__threshold_event = threading.Event()

        # Count of samples since last data push
        self.__sample_count = 0

        # Here we grab the channel publisher
        channels = SettingsBase.get_setting(self, "channels")
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()

        # And subscribe to receive notification about new samples
        # as long as sample_threshold is not 0
        sample_threshold = SettingsBase.get_setting(self, "sample_threshold")
        if sample_threshold:
            if len(channels) > 0:
                for channel in channels:
                    cp.subscribe(channel, self.receive)
            else:
                cp.subscribe_to_all(self.receive)

        threading.Thread.start(self)
        self.apply_settings()
        return True


    def stop(self):
        self.__stopevent.set()
        return True

    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # There were problems with settings, terminate early:
            self.__tracer.error("Settings rejected/not found: %s %s",
                                rejected, not_found)
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)
        return (accepted, rejected, not_found)

    def receive(self, channel):
        # Check how many samples it takes to meet the sample threshold
        sample_threshold = SettingsBase.get_setting(self, "sample_threshold")
        self.__sample_count += 1
        # self.__tracer.info("idigi_db (%s): Received sample %i", \
        #       self.__name, self.__sample_count)

        # If we have exceeded the sample threshold, notify the thread
        # responsible for pushing up data
        if self.__sample_count >= sample_threshold:
            self.__tracer.debug("Reached threshold of %i, setting event flag",
                               sample_threshold)
            self.__sample_count = 0
            self.__threshold_event.set()

    def run(self):

        interval = SettingsBase.get_setting(self, "initial_upload")
        if interval is None:
            interval = SettingsBase.get_setting(self, "interval")
        self.__last_upload_clock = 0
        self.__last_upload_time = 0
        while not self.__stopevent.isSet():
            try:
                # 32 bit modulo math to account for an NDS bug :-(
                now = int(digitime.real_clock()) & 0xffffffff
                time_passed = (now - self.__last_upload_clock) & 0xffffffff
                interval_met = (interval > 0 and
                                time_passed > interval)
                threshold_met = self.__threshold_event.isSet()
                if interval_met:
                    interval = SettingsBase.get_setting(self, "interval")
                    self.__sample_count = 0
                    self.__threshold_event.clear()
                    self.__upload_data()
                elif threshold_met:
                    interval = SettingsBase.get_setting(self, "interval")
                    self.__threshold_event.clear()
                    self.__upload_data()
                digitime.sleep(1)
            except Exception, e:
                self.__tracer.error("exception while uploading: %s", str(e))

        self.__tracer.warning("Out of run loop.  Shutting down...")

        # Clean up channel registration
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        cp.unsubscribe_from_all(self.receive)

    def __upload_data(self):

        xml = cStringIO.StringIO()

        xml.write("<?xml version=\"1.0\"?>")
        compact_xml = SettingsBase.get_setting(self, "compact_xml")
        if compact_xml:
            xml.write("<idigi_data compact=\"True\">")
        else:
            xml.write("<idigi_data>")

        cm = self.__core.get_service("channel_manager")
        cdb = cm.channel_database_get()

        channel_list = SettingsBase.get_setting(self, "channels")
        if len(channel_list) == 0:
            channel_list = cdb.channel_list()

        new_sample_count = 0

        for channel_name in channel_list:
            try:
                channel = cdb.channel_get(channel_name)
                if not (channel.perm_mask() & DPROP_PERM_GET):
                    # skip ungettable things
                    continue
                sample = channel.get()
                if sample.timestamp >= self.__last_upload_time:
                    self.__tracer.debug("Channel %s was updated since last " +
                           "push", channel_name)
                    new_sample_count += 1
                    compact_xml = SettingsBase.get_setting(self, "compact_xml")
                    if compact_xml:
                        xml.write(self.__make_compact_xml(channel_name,
                                                          sample))
                    else:
                        xml.write(self.__make_xml(channel_name, sample))
                else:
                    self.__tracer.debug("Channel %s was not updated since " +
                          "last push", channel_name)
            except Exception, e:
                # Failed to retrieve the data
                self.__tracer.warning("Exception in getting sample data: %s",
                                    str(e))

        xml.write("</idigi_data>")

        if new_sample_count > 0:
            self.__tracer.debug("Starting upload to Device Cloud")
            # Due to an NDS issue, clock may roll over, we'll just
            # keep track modulo 32-bit to allow for that.
            self.__last_upload_clock = int(digitime.real_clock()) & 0xffffffff
            self.__last_upload_time = digitime.time()

            success = self.__send_to_idigi(xml.getvalue())
            if success == True:
                self.__tracer.debug("Finished upload to Device Cloud")
            else:
                self.__tracer.debug("Upload failed to Device Cloud")
        else:
            self.__tracer.debug("No new Sample data to send to Device Cloud")

        xml.close()

    def __make_xml(self, channel_name, sample):

        data = "<sample>"
        data += "<name>%s</name>"
        data += "<value>%s</value>"
        data += "<unit>%s</unit>"
        data += "<timestamp>%s</timestamp>"
        data += "</sample>"

        return data % (channel_name, self.__escape_entities(sample.value),
                       sample.unit, iso_date(sample.timestamp))


    def __make_compact_xml(self, channel_name, sample):

        data = "<sample name=\"%s\" value=\"%s\" unit=\"%s\" timestamp=\"%s\" />"

        return data % (channel_name, self.__escape_entities(sample.value),
                       sample.unit, iso_date(sample.timestamp))


    def __send_to_idigi(self, data):

        success = False
        filename = SettingsBase.get_setting(self, "filename")
        filename = filename + "%i.xml" % self.__current_file_number
        collection = SettingsBase.get_setting(self, "collection")
        secure = SettingsBase.get_setting(self, "secure")
        try:
            self.__tracer.debug("Attempting to upload %s to Device Cloud", filename)
            success, err, errmsg = idigi_data.send_idigi_data(data, filename,
                                                           collection, secure)
            if success == True:
                self.__tracer.debug("Successfully uploaded %s to Device Cloud",
                                    filename)
            else:
                self.__tracer.error("Unsuccessfully uploaded %s to Device Cloud." +
                      "(Err: %s Errmsg: %s)",
                       filename, str(err), str(errmsg))
        except Exception, e:
            self.__tracer.error("Took an Exception during upload of %s to " +
                  "Device Cloud: %s", filename, str(e))

        self.__current_file_number += 1

        max_files = SettingsBase.get_setting(self, "file_count")

        if self.__current_file_number >= max_files + 1:
            self.__current_file_number = 1

        return success

    def __escape_entities(self, sample_value):

        if not isinstance(sample_value, str):
            return sample_value
        for ch in ENTITY_MAP:
            sample_value = sample_value.replace(ch, ENTITY_MAP[ch])

        return sample_value
