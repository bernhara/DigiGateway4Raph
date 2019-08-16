############################################################################
#                                                                          #
# Copyright (c)2009-2012, Digi International (Digi). All Rights Reserved.  #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice, and the following   #
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
** RCI Handler**

The RCIHandler presentation layer allows for interaction with the
DIA through RCI.

The only configurable option is the target_name, which is the target you
specify in your RCI request so that it gets forwarded to this handler.

**Sample Config**::

    presentations:
      - name: rci_handler
        driver: presentations.rci.rci_handler:RCIHandler
        settings:
            target_name: idigi_dia

##########################################################################

The RCIHandler allows for channel dumps, querying a channel, and setting
a channel. It also includes several requests to interact with the logging
sub-system to read and move inside of a determined log file.

The RCIHandler parses an incoming XML formatted message
to determine what you wish to do.  The messages are shown below.  If
an error is encountered, the request you sent will have a child error
element specifying the error information.

**Settings**:

* **target_name**: Target specified in RCI request. Requests will be
  forwarded to this handler.

Channel Dump
------------
**Request** code::

    <channel_dump/>

**Response** code::

    <channel_dump>
        <device name="...">
            <channel name="..." value="..." units="..." timestamp="..."/>
            ...
        </device>
        ...
    </channel_dump>

Channel Get
-----------
**Request** code::

    <channel_get name="..."/>

**Response** code::

    <channel_get name="..." value="..." units="..." timestamp="..."/>

Channel Refresh
---------------
**Request** code::

    <channel_refresh name="..."/>

**Response** code::

    <channel_refresh name="..." />

Channel Set
-----------
**Request** code::

    <channel_set name="..." value="..."/>

**Response** code::

    <channel_set name="..." value="..." units="..." timestamp="..."/>

Channel Info
------------
**Request** code::

    <channel_info name="..."/>

**Response** code::

    <channel_info name="...">
        <permissions>
            <get/>
            <set/>
            <refresh/>
        <permissions>
        <options>
            <auto_timestamp/>
            <do_not_log_data/>
        <options>
    </channel_info>

Logger List
-----------
**Request** code::

    <logger_list/>

**Response** code::

    <logger_list>
        <logger name="..."/>
        ...
    </logger_list>

Logger Set
----------
**Request** code::

    <logger_set name"...">

**Response** code::

    <logger_set name="...">
    </logger_set>

Logger Dump
-----------
**Request** code::

    <logger_dump/>

**Response** code::

    <logger_dump name="...">
        <device name="...">
            <channel name="..." value="..." units="..." timestamp="..."/>
            ...
        </device>
        ...
    </logger_dump>

Logger Next
-----------
**Request** code::

    <logger_next/>

**Response** code::

    <logger_next name="...">
    </logger_next>

Logger Previous
---------------
**Request** code::

    <logger_prev/>

**Response** code::

    <logger_prev name="...">
    </logger_prev>

Logger Rewind
-------------
**Request** code::

    <logger_rewind/>

**Response** code::

    <logger_rewind name="...">
    </logger_rewind>

Logger Seek
-----------
**Request** code::

    <logger_seek offset="0" whence="end" />

**Response** code::

    <logger_seek name="...">
    </logger_seek>


Device Dump
-----------
**Request** code::

    <device_dump />

**Response** code::

    <device_dump>
       <device name="..." driver="..." />
    </device_dump>

Shutdown
--------
**Request** code::

    <shutdown/>

**Response** code::

    <shutdown>
      [<error>Error message</error>]
    </shutdown>
"""

# History:
# 2012-10-26: LAL changed to support subclassing

# imports
import xml.parsers.expat
import threading
import time
try:
    import rci
    if 'RciCallback' in dir(rci):
        RCI_NONBLOCKING = True
    else:
        RCI_NONBLOCKING = False
except ImportError:
    import rci_nonblocking as rci
    RCI_NONBLOCKING = True
import sys, traceback

from settings.settings_base import SettingsBase, Setting
from presentations.presentation_base import PresentationBase
from channels.channel import \
    PERM_GET, PERM_SET, PERM_REFRESH, \
    OPT_AUTOTIMESTAMP, OPT_DONOTLOG, OPT_DONOTDUMPDATA
from samples.sample import Sample
from StringIO import StringIO
from common.helpers.format_channels import iso_date
from channels.channel_database_interface import \
    LOG_SEEK_SET, LOG_SEEK_CUR, LOG_SEEK_END, LOG_SEEK_REC
from common.dia_proc import get_drivers

from core.tracing import get_tracer

# constants
ENTITY_MAP = {
    "<": "&lt;",
    ">": "&gt;",
    "&": "&amp;",
}

# classes

class RCIHandler(PresentationBase):
    ERR_PARSE_ERROR = '<error>Parse Error</error>'
    ERR_MISSING_ATTRIBUTE = '<error>Missing Attribute</error>'
    ERR_MISSING_ELEMENT = '<error>Missing Element</error>'
    ERR_UNKNOWN_CHANNEL = '<error>Unknown Channel</error>'
    ERR_INVALID_SAMPLE_VALUE = '<error>Invalid Sample Value</error>'
    ERR_SET_FAILED = '<error>Unable To Set Channel</error>'
    ERR_UNKNOWN_LOGGER = '<error>Unknown Logger</error>'
    ERR_UNSELECTED_LOGGER = '<error>No Logger Selected</error>'
    ERR_REFRESH = '<error>Refresh Error</error>'

    __logger = None
    __logger_cdb = None

    def __init__(self, name, core_services, settings=None):
        """
        Create an instance of the RCIHandler.

        If the target_name is not specified, it will default to 'idigi_dia'.
        """

        self._name = name
        self._core = core_services
        self._handle = None
        self._tracer = get_tracer(name)

        settings_list = [
                         Setting(
                                 name='target_name', type=str,
                                 required=False, default_value='idigi_dia'),
                        ]
                        
        if settings is not None:
            settings.extend(settings_list)
        else:
            settings = settings_list

        ## Initialize settings:
        PresentationBase.__init__(self, name=name, settings_list=settings)

    def start(self):
        """Start listening for messages on the specified target"""

        target_name = SettingsBase.get_setting(self, 'target_name')

        if not RCI_NONBLOCKING:     
            add_callback = lambda name=target_name: rci.add_rci_callback(
                                name, self.__rci_callback)

            self._handle = threading.Thread(name="RCI Handler",
                                             target=add_callback)
            self._handle.start()
        else:
            self._handle = rci.RciCallback(target_name, self.__rci_callback)

    def stop(self):
        """Stop listening for messages"""

        if not RCI_NONBLOCKING:
            target_name = SettingsBase.get_setting(self, 'target_name')
            rci.stop_rci_callback(target_name)
        else:
            if self._handle:
                del self._handle
                self._handle = None

        return True

    def __escape_entities(self, sample_value):
        if not isinstance(sample_value, str):
            return sample_value
        for ch in ENTITY_MAP:
            sample_value = sample_value.replace(ch, ENTITY_MAP[ch])

        return sample_value

    def __unescape_entities(self, sample_value):
        if not isinstance(sample_value, str):
            return sample_value
        inv_entity_map = dict(zip(ENTITY_MAP.values(), ENTITY_MAP.keys()))
        for pat in inv_entity_map:
            sample_value = sample_value.replace(pat, inv_entity_map[pat])

        return sample_value

    def __rci_callback(self, message):
        """
        Called whenever there is an incoming RCI message with
        our specified target.

        Keyword arguments:
            message - the value that is intended for us from RCI.

        Returns the reply as a string.
        """

        self._tracer.debug("Req: %s", message)
        
        self.__parser = xml.parsers.expat.ParserCreate()
        self.__parser.StartElementHandler = self._handle_start_element
        self.__parser.EndElementHandler = self._handle_end_element
        self._reply = ""

        start_wrapper = "<hidden_rci_callback_xml_wrapper_tag>"
        end_wrapper = "</hidden_rci_callback_xml_wrapper_tag>"
        message = start_wrapper + message + end_wrapper

        try:
            self.__parser.Parse(message)
        except xml.parsers.expat.ExpatError:
            self._reply = RCIHandler.ERR_PARSE_ERROR
        except Exception, e:
            self._tracer.error("exception during RCI processing: %s",
                str(e))
            self._tracer.debug(traceback.format_exc())

        self._tracer.debug("Rsp: %s", self._reply)

        reply_string = str(self._reply).\
            replace(start_wrapper, "").replace(end_wrapper, "")

        return reply_string

    def _handle_start_element(self, name, attrs):
        """
        Called whenever we encounter the start of an XML element.

        Keyword arguments:
            name -- the name of the element.
            attrs -- dictionary of attributes.
        """

        if name == "channel_dump":
            self._reply += self.__do_channel_dump(attrs)
        elif name == "channel_get":
            self._reply += self.__do_channel_get(attrs)
        elif name == "channel_set":
            self._reply += self.__do_channel_set(attrs)
        elif name == "channel_refresh":
            self._reply += self.__do_channel_refresh(attrs)
        elif name == "channel_info":
            self._reply += self.__do_channel_info(attrs)
        elif name == "logger_list":
            self._reply += self.__do_logger_list(attrs)
        elif name == "logger_set":
            self._reply += self.__do_logger_set(attrs)
        elif name == "logger_dump":
            self._reply += self.__do_logger_dump(attrs)
        elif name == "logger_next":
            self._reply += self.__do_logger_next(attrs)
        elif name == "logger_prev":
            self._reply += self.__do_logger_prev(attrs)
        elif name == "logger_rewind":
            self._reply += self.__do_logger_rewind(attrs)
        elif name == "logger_seek":
            self._reply += self.__do_logger_seek(attrs)
        elif name == "logger_pos":
            self._reply += self.__do_logger_pos(attrs)
        elif name == "device_dump":
            self._reply += self.__do_device_dump(attrs)
        elif name == "shutdown":
            self._reply += self.__do_dia_shutdown(attrs)
        else:
            self._reply += "<" + name + ">"

    def _handle_end_element(self, name):
        """
        Add appropriate opening and closing punctuation to the reply.

        Keyword arguments:
            name -- the name of the end element
        """

        self._reply += "</" + str(name) + ">"

    def __do_channel_dump(self, attrs):
        """
        Build a response for a channel dump request.

        Keyword arguments:
            attrs - Any attributes that might be passed in
        """

        # Variables
        device_string = StringIO()

        device_string.write('<channel_dump>')

        cdb = (self._core.get_service("channel_manager")
                .channel_database_get())
        device_string.write(self.__generate_channel_database(cdb))

        return device_string.getvalue()

    def __do_channel_get(self, attrs):
        """
        Build a response for a channel get request.

        Keyword arguments:
            attrs -- dictionary of attributes, should have 'name'

        Returns a channel_get XML element with the channel_name,
        value, units, and timestamp.

        If the 'name' attribute is missing, an empty '<channel_get>'
        element is returned, along with an ERR_MISSING_ATTRIBUTE error.
        If the specified channel doesn't seem to exist, only the name
        is included in the response element, along with an ERR_UNKNOWN_CHANNEL.
        """

        try:
            channel_name = attrs['name']
        except KeyError:
            return '<channel_get>' + RCIHandler.ERR_MISSING_ATTRIBUTE

        cdb = self._core.get_service("channel_manager").\
        channel_database_get()

        if not cdb.channel_exists(channel_name):
            return ('<channel_get name="%s">' % channel_name +
                    RCIHandler.ERR_UNKNOWN_CHANNEL)

        channel = cdb.channel_get(channel_name)
        value = "(n/a)"
        units = ""
        timestamp = ""
        try:
            sample = channel.get()
            value = self.__escape_entities(sample.value)
            units = sample.unit
            timestamp = time.asctime(time.localtime(sample.timestamp))
        except:
            pass

        return ('<channel_get name="%s" value="%s" units="%s"'
                 ' timestamp="%s">' % (channel_name, value, units, timestamp))

    def __do_channel_refresh(self, attrs):
        """
        Build a response for a channel refresh request.

        Keyword arguments:
            attrs -- dictionary of attributes, should have 'name'

        Returns a channel_refresh XML element with the channel_name.

        If the 'name' attribute is missing, an empty '<channel_refresh>'
        element is returned, along with an ERR_MISSING_ATTRIBUTE error.
        If the specified channel doesn't seem to exist, only the name
        is included in the response element, along with an ERR_UNKNOWN_CHANNEL.
        If the channel refresh cannot be completed, an empty '<channel_refresh>'
        element is returned, along with an ERR_REFRESH.
        """

        try:
            channel_name = attrs['name']
        except KeyError:
            return '<channel_refresh>' + RCIHandler.ERR_MISSING_ATTRIBUTE

        cdb = self._core.get_service("channel_manager").\
        channel_database_get()

        if not cdb.channel_exists(channel_name):
            return ('<channel_refresh name="%s">' % channel_name +
                    RCIHandler.ERR_UNKNOWN_CHANNEL)

        channel = cdb.channel_get(channel_name)

        try:
            sample = channel.refresh()
        except:
            return '<channel_refresh>' + RCIHandler.ERR_REFRESH

        return '<channel_refresh name="%s">' % (channel_name)

    def __do_channel_info(self, attrs):
        """
        Build a response for a channel info request.

        Keyword arguments:
            attrs -- dictionary of attributes, should have 'name'

        Returns a channel_info XML element, which starts with the channel name
        and includes any additional info as iteratively filled elements.

            If the 'name' attribute is missing, an empty '<channel_info>'
        element is returned, along with an ERR_MISSING_ATTRIBUTE error.
            If the specified channel doesn't seem to exist, only the name
        is included in the response element, along with an ERR_UNKNOWN_CHANNEL.

        """

        try:
            channel_name = attrs['name']
        except KeyError:
            return '<channel_info>' + RCIHandler.ERR_MISSING_ATTRIBUTE

        cdb = self._core.get_service("channel_manager").channel_database_get()

        if not cdb.channel_exists(channel_name):
            return ('<channel_info name="%s">' % channel_name +
                    RCIHandler.ERR_UNKNOWN_CHANNEL)

        channel = cdb.channel_get(channel_name)
        perms_table = {
            PERM_GET: "<get/>",
            PERM_SET: "<set/>",
            PERM_REFRESH: "<refresh/>",
        }
        options_table = {
            OPT_AUTOTIMESTAMP: "<auto_timestamp/>",
            OPT_DONOTLOG: "<do_not_log_data/>",
            OPT_DONOTDUMPDATA: "<do_not_dump_data/>",
        }

        resp = '<channel_info name="%s">' % channel_name
        for tag, tbl, mask in (
                ("permissions", perms_table, channel.perm_mask()),
                ("options", options_table, channel.options_mask()) ):
            if not mask:
                resp += "<%s/>" % tag
                continue
            keys = tbl.keys()
            keys.sort()
            resp += "<%s>" % tag
            for k in keys:
                if k & mask:
                    resp += tbl[k]
            resp += "</%s>" % tag

        return resp

    def __do_channel_set(self, attrs):
        """
        Build a response for a channel set request.

        Keyword arguments:
            attrs -- dictionary of attributes, should have 'name' and 'value'

        Returns a channel_set XML element which includes the name, value, and
        units of the specified channel, along with a timestamp.

        If the 'name' attribute is missing, an empty '<channel_set>'
        element is returned, along with an ERR_MISSING_ATTRIBUTE error.

        If the specified channel doesn't seem to exist, only the name
        is included in the response element, along with an
        ERR_UNKNOWN_CHANNEL.

        If the sample value cannot be correctly parsed, a channel_set
        element is returned with the channel_name and an
        ERR_INVALID_SAMPLE_VALUE.

        If the channel set operation fails, a channel_set element
        is returned with the channel_name and an ERR_SET_FAILED.
        """

        try:
            channel_name = attrs['name']
            value = self.__unescape_entities(attrs['value'])
        except KeyError:
            return '<channel_set>' + RCIHandler.ERR_MISSING_ATTRIBUTE

        cdb = self._core.get_service("channel_manager").\
        channel_database_get()

        if not cdb.channel_exists(channel_name):
            return ('<channel_set name="%s">' % channel_name +
                    RCIHandler.ERR_UNKNOWN_CHANNEL)

        channel = cdb.channel_get(channel_name)

        sample = None
        try:
            sample = Sample(time.time(), channel.type()(str(value)))
        except Exception, e:
            self._tracer.error("unable to parse '%s': %s\r\n", value, str(e))
            self._tracer.error("type expected: %s\r\n", channel.type())
            return '<channel_set name="%s"/>' % channel_name \
            + RCIHandler.ERR_INVALID_SAMPLE_VALUE

        try:
            channel.set(sample)
        except Exception, e:
            return ('<channel_set name="%s">' % channel_name +
                    RCIHandler.ERR_SET_FAILED)

        value = "(n/a)"
        units = ""
        timestamp = ""
        try:
            retrieved_sample = channel.get()
            value = retrieved_sample.value
            units = retrieved_sample.unit
            timestamp = time.asctime(time.localtime(sample.timestamp))
        except:
            pass

        return ('<channel_set name="%s" value="%s" units="%s" timestamp="%s">'
                % (channel_name, value, units, timestamp))

    def __do_logger_list(self, attrs):
        """
        Build a response for a 'logger_list' request.

        Keyword arguments:
            attrs -- Dictionary of attributes.

        Returns the complete list of channel loggers, obtained from the
        core presentation services instance.
        """

        cm = self._core.get_service("channel_manager")
        logger_list = cm.channel_logger_list()

        list_response = StringIO()

        list_response.write('<logger_list>')

        for logger_name in logger_list:
            list_response.write('<logger name="%s"/>' % logger_name)

        return list_response.getvalue()

    def __do_logger_set(self, attrs):
        """
        Build a response for a 'logger_set' request.

        Keyword arguments:
            attrs -- Dictionary of attributes. Should have 'name'.

        Returns a logger_set XML element with the logger_name.

            If the 'name' attribute is missing, an empty '<logger_set>'
        element is returned, along with an ERR_MISSING_ATTRIBUTE error.
            If the specified logger doesn't seem to exist, only the name
        is included in the response element, along with an ERR_UNKNOWN_LOGGER.
        """

        try:
            logger_name = attrs['name']
        except KeyError:
            return '<logger_set>' + RCIHandler.ERR_MISSING_ATTRIBUTE

        cm = self._core.get_service("channel_manager")

        if not cm.channel_logger_exists(logger_name):
            return '<logger_set name="%s">%s' % (
                logger_name, RCIHandler.ERR_UNKNOWN_LOGGER)

        try:
            self.__logger = cm.channel_logger_get(logger_name)
            self.__logger_cdb = self.__logger.channel_database_get()
        except Exception, e:
            return '<logger_set name="%s"><error>Exception: %s</error>' % (
                logger_name, str(e))

        return '<logger_set name="%s">' % logger_name

    def __do_logger_dump(self, attrs):
        """
        Build a response for a 'logger_dump' request.

        Keyword arguments:
            attrs -- Dictionary of attributes.

        Returns a logger_dump XML element with the logger name.

            If no logger is selected, an ERR_UNSELECTED_LOGGER error will
        be written, along with an empty <logger_dump> element.
        """

        # Variables
        dump_response = StringIO()

        if self.__logger is None:
            dump_response.write('<logger_dump>')
            dump_response.write(RCIHandler.ERR_UNSELECTED_LOGGER)
        else:
            logger_name = self.__logger.get_name()
            dump_response.write('<logger_dump name="%s">'
                                % (logger_name))
            dump_response.write(self.__generate_channel_database
                                (self.__logger_cdb))

        return dump_response.getvalue()

    def __do_logger_next(self, attrs):
        """
        Build a response for a 'logger_next' request.

        Keyword arguments:
            attrs -- Dictionary of attributes.

        Returns a logger_next XML element with the logger name.

            If no logger is selected, an ERR_UNSELECTED_LOGGER error will
        be returned, along with an empty <logger_next> element.
            If the log_next() operation is unsuccessful, a logger_next
        element is returned with the logger name and an XML <error>
        element, which should contain the relevant exception.
        """

        if self.__logger is None:
            return '<logger_next>%s' % RCIHandler.ERR_UNSELECTED_LOGGER

        logger_name = self.__logger.get_name()

        try:
            self.__logger_cdb.log_next()
        except Exception, e:
            return '<logger_next name="%s"><error>Exception: %s</error>' % (
                logger_name, str(e))

        return '<logger_next name="%s">' % logger_name

    def __do_logger_prev(self, attrs):
        """
        Build a response for a 'logger_prev' request.

        Keyword arguments:
            attrs -- Dictionary of attributes.

        Returns a logger_prev XML element with the logger name.

            If no logger is selected, an ERR_UNSELECTED_LOGGER error will
        be returned, along with an empty <logger_prev> element.
            If the log_prev() operation is unsuccessful, a logger_prev element
        is returned with the logger name and an XML <error> element
        which should contain the relevant exception.
        """

        if self.__logger is None:
            return '<logger_prev>%s' % RCIHandler.ERR_UNSELECTED_LOGGER

        logger_name = self.__logger.get_name()

        try:
            self.__logger_cdb.log_prev()
        except Exception, e:
            return '<logger_prev name="%s"><error>Exception: %s</error>' % (
                logger_name, str(e))

        return '<logger_prev name="%s">' % logger_name

    def __do_logger_rewind(self, attrs):
        """
        Build a response for a 'logger_rewind' request.

        Keyword arguments:
            attrs -- Dictionary of attributes.

        Returns a logger_rewind XML element with the logger name.

            If no logger is selected, an ERR_UNSELECTED_LOGGER error will
        be returned, along with an empty <logger_rewind> element.
            If the log_rewind() operation is unsuccessful, a logger_rewind element
        is returned with the logger name, along with an XML <error> element
        which should contain the relevant exception.
        """

        if self.__logger is None:
            return '<logger_rewind>%s' % RCIHandler.ERR_UNSELECTED_LOGGER

        logger_name = self.__logger.get_name()

        try:
            self.__logger_cdb.log_rewind()
        except Exception, e:
            return '<logger_rewind name="%s"><error>Exception: %s</error>' % (
                logger_name, str(e))

        return '<logger_rewind name="%s">' % logger_name

    def __do_logger_seek(self, attrs):
        """
        Build a response for a 'logger_seek' request.

        Keyword arguments:
            attrs -- Dictionary of attributes. Should contain 'offset' and
                     'whence'.

        Returns a logger_seek XML element with the logger name.

            If no logger is selected, an ERR_UNSELECTED_LOGGER error will
        be written, along with an empty <logger_seek> element.
            If the log_seek() operation is unsuccessful, a logger_seek element
        is returned with the logger name, along with an XML <error> element
        which should contain the relevant exception.
            If the 'name' attribute is missing, an empty '<logger_seek>'
        element is returned, along with an ERR_MISSING_ATTRIBUTE error.


        **Request** code::

            <logger_seek offset={num] whence={cur, set, end, rec} [record={num]>

        **Response** code::

            <logger_seek name={name}>[<error></error>]</logger_seek>
        """

        whence_map = { 'set': LOG_SEEK_SET,
                       'cur': LOG_SEEK_CUR,
                       'end': LOG_SEEK_END,
                       'rec': LOG_SEEK_REC, }

        if self.__logger is None:
            return '<logger_seek>%s' % RCIHandler.ERR_UNSELECTED_LOGGER

        logger_name = self.__logger.get_name()

        try:
            offset = int(attrs['offset'])
            whence = attrs['whence']
        except KeyError:
            return '<logger_seek name="%s">%s' % (
                logger_name, RCIHandler.ERR_MISSING_ATTRIBUTE)

        if whence not in whence_map:
            return ('<logger_seek name="%s"><error>Bad whence "%s", '
                      'must be set, cur, end or rec</error>') % (
                logger_name, str(whence))

        try:
            record_number = int(attrs['record_number'])
        except KeyError:
            record_number = 0

        try:
            self.__logger_cdb.log_seek(offset,
                                       whence_map[whence],
                                       record_number)
        except Exception, e:
            return '<logger_seek name="%s"><error>Exception: %s</error>' % (
                logger_name, str(e))

        return '<logger_seek name="%s">' % logger_name

    def __do_logger_pos(self, attrs):
        """
        Build a response for a 'logger_pos' request.

        Keyword arguments:
            attrs -- Dictionary of attributes.

        Returns a logger_pos XML element, with the logger name as
        an attribute.

            If no logger is selected, an ERR_UNSELECTED_LOGGER error will
        be returned, along with an empty <logger_pos> element.
            If the log_position() operation is unsuccessful, a logger_pos element
        is returned with the logger name, along with an XML <error> element
        which should contain the relevant exception.
        """

        if self.__logger is None:
            return '<logger_pos>%s' % RCIHandler.ERR_UNSELECTED_LOGGER

        logger_name = self.__logger.get_name()

        try:
            pos = self.__logger_cdb.log_position()
            if pos == None:
                raise Exception, "Position not set"
        except Exception, e:
            return '<logger_pos name="%s"><error>Exception: %s</error>' % (
                logger_name, str(e))

        return '<logger_pos name="%s">%s' % (logger_name, pos)

    def __do_device_dump(self, attrs):
        """
        Build a response for a 'device_dump' request.

        """
        name_driver_pairs = get_drivers(self._core)

        return '<device_dump>' + ''.join(map(lambda x:
                                             ('<device name="%s" ' +
                                             'driver="%s" />') % \
                                             (x[0], x[1]),
                                             name_driver_pairs))


    def __do_dia_shutdown(self, attrs):
        """
        Build a response for a 'shutdown' request.

        Keyword arguments:
            attrs -- Dictionary of attributes.

        Returns a shutdown XML element. (No attributes are supported.)
        """

        self._core.request_shutdown()

        return "<shutdown>"


    def __generate_channel_database(self, cdb):

        channel_list = cdb.channel_list()
        channel_list.sort()

        devices = {}

        for entry in channel_list:
            device, channel_name = entry.split('.')
            channel = cdb.channel_get(entry)

            if not devices.has_key(device):
                devices[device] = []

            try:
                if (not (channel.perm_mask() & PERM_GET) or
                    channel.options_mask() & OPT_DONOTDUMPDATA):
                    raise Exception
                sample = channel.get()
                devices[device].append((channel_name,
                                        sample.value,
                                        sample.unit,
                                        time.asctime(
                                                     time.localtime
                                                     (sample.timestamp)),
                                        str(channel.type().__name__)))
            except Exception, e:
                devices[device].append((channel_name, "(N/A)", "", "", ""))

        device_string = StringIO()

        for device in devices.keys():
            device_string.write('<device name="%s">' % device)
            for channel in devices[device]:
                value = self.__escape_entities(channel[1])
                device_string.write('<channel name="%s" value="%s"'
                    ' units="%s" timestamp="%s"'
                    ' type="%s"/>' % (channel[0], value, channel[2],
                                        channel[3], channel[4]))
            device_string.write('</device>')

        return device_string.getvalue()
