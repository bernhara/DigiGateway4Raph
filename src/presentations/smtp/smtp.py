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
SMTP Presentation Object
"""

# imports

import threading
import re
import digi_smtplib as smtplib
import socket

from Queue import Queue
from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase
from channels.channel_publisher import ChannelDoesNotExist
from common.helpers.format_channels import dump_channel_db_as_text

# constants

# classes


class SMTPHandler(PresentationBase, threading.Thread):

    def __init__(self, name, core_services):

        self.__name = name
        self.__core = core_services

        self.queue = Queue()
        self.started_flag = False
        self.monitored_channel = None

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        # Configuration Settings:

        #     to_address: The email address to send the email to
        #     from_address: The from address of the email, defaults to:
        #         digi_dia@digi.com
        #     subject: The subject of the email, defaults to: iDigi Dia Alert
        #     server_address: The address of the SMTP server
        #     port: The port of the SMTP server, defaults to: 25
        #     monitored_channel: The Channel whose samples are monitored
        #          to determine queueing of the email message.

        settings_list = [Setting(name="to_address", type=str, required=True),
                             Setting(name="from_address", type=str, required=False,
                                             default_value="digi_dia@digi.com"),
                             Setting(name="subject", type=str, required=False,
                                             default_value="iDigi Dia Alert"),
                             Setting(name="server_address", type=str, required=True),
                             Setting(name="port", type=int, required=False,
                                             default_value=25),
                             Setting(name="monitored_channel", type=str, required=True)]

        PresentationBase.__init__(self, name=name, settings_list=settings_list)

        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    def apply_settings(self):

        email_reg = re.compile('[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}',
                               re.IGNORECASE)

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        ## Validate email addresses
        if not email_reg.search(accepted['to_address']):
            raise Exception("to_address was invalid: %s" % 
                            accepted['to_address'])
        if not email_reg.search(accepted['from_address']):
            raise Exception("from_address was invalid: %s" % 
                            accepted['from_address'])

        ## Validate port
        try:
            if int(accepted['port']) < 1 or (int(accepted['port']) > 65535):
                raise Exception("port is an invalid port number %s" %
                                accepted['port'])
        except ValueError:
            raise Exception("port is an invalid port number %s" %
                            accepted['port'])

        ## Get handle to channel manager, which gives us channel publisher
        channel_manager = self.__core.get_service("channel_manager")
        channel_publisher = channel_manager.channel_publisher_get()

        ##Unsubscribe to the 'old' channel if we have subscribed before
        if self.monitored_channel is not None:
            try:
                channel_publisher.unsubscribe(self.monitored_channel,
                                              self.queue_msg)
            except ChannelDoesNotExist:
                self.__tracer.error(
                "The channel %s does not exist, it cannot be unsubscribed to",
                self.monitored_channel)

        ## subscribe to monitored_channel
        self.monitored_channel = accepted['monitored_channel']
        channel_publisher.subscribe(self.monitored_channel, self.queue_msg)

        SettingsBase.commit_settings(self, accepted)
        return (accepted, rejected, not_found)

    def start(self):

        self.started_flag = True
        threading.Thread.start(self)
        self.apply_settings()
        return True

    def queue_msg(self, channel):

        monitored_sample = channel.get()

        if not self.started_flag:
            raise Exception("Cannot queue message, presentation is stopped")

        if monitored_sample.value:
            channel_manager = self.__core.get_service("channel_manager")
            channel_database = channel_manager.channel_database_get()

            frm = SettingsBase.get_setting(self, 'from_address')
            to = SettingsBase.get_setting(self, 'to_address')
            sbj = SettingsBase.get_setting(self, 'subject')
            msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n" % \
                                (frm, to, sbj)
            msg += dump_channel_db_as_text(channel_database)
            self.queue.put(msg)

    def run(self):

        while self.started_flag:
            msg = self.queue.get()

            if not self.started_flag:
                return

            host = SettingsBase.get_setting(self, 'server_address')
            port = SettingsBase.get_setting(self, 'port')
            frm = SettingsBase.get_setting(self, 'from_address')
            to = SettingsBase.get_setting(self, 'to_address')

            try:
                s = smtplib.SMTP(host, port)
            except Exception, e:
                self.__tracer.error("Failed to connect to SMTP server")
                self.__tracer.warning("If using a DNS name, " + \
                        "make sure the Digi device is configured" + \
                        " to use the correct DNS server")
                continue

            try:
                error_list = s.sendmail(frm, to, msg)
            except:
                self.__tracer.error(
                    "Failed to send messages, please double check server/port")
            else:
                for err in error_list:
                    self.__tracer.error(
                        "Failed to send message to %s address", err)
            s.quit()

    def stop(self):

        channel_manager = self.__core.get_service("channel_manager")
        channel_publisher = channel_manager.channel_publisher_get()
        channel_publisher.unsubscribe_from_all(self.queue_msg)

        if not self.started_flag:
                return False

        self.started_flag = False
        # Queuing anything with the start_flag set to False will
        # cause the thread running in the run() loop to terminate.
        self.queue.put("quit")
        return True
