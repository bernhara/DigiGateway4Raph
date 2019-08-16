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
XMLRPC Server Presentation for DIA
"""

# imports
import sys, traceback
from select import select
import threading
import digitime
import types
from SimpleXMLRPCServer import SimpleXMLRPCServer, \
                            SimpleXMLRPCRequestHandler, SimpleXMLRPCDispatcher

from settings.settings_base import SettingsBase, Setting
from channels.channel import \
    PERM_GET, PERM_SET, PERM_REFRESH, \
    OPT_AUTOTIMESTAMP, OPT_DONOTLOG, OPT_DONOTDUMPDATA
from presentations.presentation_base import PresentationBase
from samples.sample import Sample
from common.helpers.format_channels import iso_date
from channels.channel_database_interface import \
    LOG_SEEK_SET, LOG_SEEK_CUR, LOG_SEEK_END, LOG_SEEK_REC
from common.types.boolean import Boolean
from common.dia_proc import get_drivers

try:
    import digiweb
except:
    pass

from core.tracing import get_tracer

# constants

# exception classes

# interface functions

# classes
class CustomXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):

    def do_POST(self):
        clientIP, port = self.client_address
#		 _tracer = get_tracer("xmlrpc.CustomXMLRPCRequestHandler")
#        _tracer.info('Client IP: %s - Port: %s', clientIP, port)

        response = None
        try:
            # get arguments
            data = self.rfile.read(int(self.headers["content-length"]))
            # Log client request
#			  _tracer = get_tracer("xmlrpc.CustomXMLRPCRequestHandler")
#             _tracer.info('Client request: \n%s\n', data)
            response = self.server._marshaled_dispatch(
                data, getattr(self, '_dispatch', None))

#			  _tracer = get_tracer("xmlrpc.CustomXMLRPCRequestHandler")
#             _tracer.info('Server response: \n%s\n', response)
        except:
            # This should only happen if the module is buggy
            # internal error, report as HTTP server error
            _tracer = get_tracer("CustomXMLRPCRequestHandler")
            _tracer.error("Exception occured during XMLRPC request: %s",
                          traceback.format_exc())
            self.send_response(500)
            self.end_headers()
            return

        # got a valid XML RPC response
        self.send_response(200)
        self.send_header("Content-type", "text/xml")
        self.send_header("Content-length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

        # shut down the connection
        self.wfile.flush()
        self.connection.shutdown(1)


class DigiWebXMLRPCRequestHandler(SimpleXMLRPCDispatcher):
    def __init__(self):
        try:
            # older Pythons like 2.4.3 demand a single parameter
            # newest Python versions handle 1, 2 or 3 parameters
            # supplying defaults for the 2nd and 3rd
            SimpleXMLRPCDispatcher.__init__(self)
        except:
            # some mid-age Python versions demand 3 parameters without
            # offering default values for the 2nd and 3rd
            SimpleXMLRPCDispatcher.__init__(self, False, None)

class XMLRPCAPI:

    # Public Methods: device_instance_list, channel_list,
    # channel_get, channel_set, channel_dump, channel_info,
    # channel_refresh, logger_list, logger_set, logger_next,
    # logger_prev, logger_rewind, logger_seek, logger_dump,
    # logger_channel_get, logger_pos, device_dump, shutdown

    # Instance Variables:
    #     __core
    #        Core Services.
    #     __cdb

    #        Channel Database instance, retrieved from the channel
    #        manager.

    ERR_UNSELECTED_LOGGER = 'Error: No logger currently selected'
    ERR_UNKNOWN_LOGGER = 'Error: Unknown logger'

    __logger = None
    __logger_cdb = None

    def __init__(self, core_services):

        self.__core = core_services
        self.__cdb = (self.__core.get_service("channel_manager")
                       .channel_database_get())

    def device_instance_list(self):

        dm = self.__core.get_service("device_driver_manager")
        return dm.instance_list()

    def channel_list(self, startswith=""):

        channel_list = self.__cdb.channel_list()
        if len(startswith) > 0:
            channel_list = filter(lambda li: li.startswith(startswith),
                                  channel_list)

        return channel_list

    def _marshal_sample(self, sample):
        """
        Marshal a :class:`Sample` object for XML-RPC representation.

        Returns a dictionary suitable for processing by the
        :class:`SimpleXMLRPCRequestHandler` class.

        This is an internal method which special-cases the attributes
        of the :class:`Sample` object.  Attributes on :class:`Sample`
        objects are type-mapped for representation in the following
        manner:

          * The internal type :class:`Boolean` will be mapped to its
            string value.
          * All other values shall be mapped to their string representation
            by calling the Python built-in :func:`repr` function.

        """
        return_dict = { }
        for member in filter(lambda m: not m.startswith('__'), dir(sample)):
            return_dict[member] = getattr(sample, member)
            # attempt to marshall complex instance types to their string reps:
            try:
                if isinstance(return_dict[member], Boolean):
                    return_dict[member] = bool(return_dict[member])
                elif type(return_dict[member]) == types.InstanceType:
                    return_dict[member] = repr(return_dict[member])
            except:
                return_dict[member] = "unrepresentable object"

        return return_dict

    def __write_channel_database(self, chdb, channel_prefix=""):

        channel_list = filter(lambda c: c.startswith(channel_prefix),
                              chdb.channel_list())
        channels = { }
        for channel_name in channel_list:
            try:
                sample = chdb.channel_get(channel_name).get()
            except Exception, e:
                sample = Sample(value="(N/A)")
            channels[channel_name] = self._marshal_sample(sample)

        return channels

    def channel_get(self, channel_name):

        channel = self.__cdb.channel_get(channel_name)
        sample = channel.get()
        return_dict = self._marshal_sample(sample)

        return return_dict

    def channel_set(self, channel_name,
                    timestamp, value, unit = "", autotimestamp = False):

        if autotimestamp:
            timestamp = digitime.time()
        channel = self.__cdb.channel_get(channel_name)
        try:
            sample = Sample(timestamp, channel.type()(value), unit)
        except Exception, e:
            raise Exception, "unable to coerce value '%s' to type '%s'" % \
                (value, repr(channel.type()))

        channel.set(sample)

        return True

    def channel_dump(self, channel_prefix=""):

        return self.__write_channel_database(self.__cdb)

    def channel_info(self, channel_name):

        channel = self.__cdb.channel_get(channel_name)
        return_dict = {
            'permissions': {
                'get': False,
                'set': False,
                'refresh': False,
            },
            'options': {
                'auto_timestamp': False,
                'do_not_log_data': False,
            }
        }
        perms_table = {
            PERM_GET: "get",
            PERM_SET: "set",
            PERM_REFRESH: "refresh",
        }
        options_table = {
            OPT_AUTOTIMESTAMP: "auto_timestamp",
            OPT_DONOTLOG: "do_not_log_data",
            OPT_DONOTDUMPDATA: "do_not_dump_data",
        }
        for section, tbl, mask in (
                ('permissions', perms_table, channel.perm_mask()),
                ('options', options_table, channel.options_mask())):
           for k in tbl:
               if k & mask:
                   return_dict[section][tbl[k]] = True

        return return_dict


    def channel_refresh(self, channel_name):

        channel = self.__cdb.channel_get(channel_name)
        channel.consumer_refresh()

        return True

    def logger_list(self):

        # Obtain the list of loggers
        cm = self.__core.get_service("channel_manager")
        return cm.channel_logger_list()

    def logger_set(self, logger_name=''):

        # This initiates possible shared state between multiple XML-RPC
        # clients.  If using multiple logging instances, this simple method
        # may not be sufficient to provide access.

        cm = self.__core.get_service("channel_manager")

        # Check if given logger exists, else return False
        if not cm.channel_logger_exists(logger_name):
            raise Exception, "Error: unknown logger '%s'" % logger_name

        # Set our local logger
        try:
            self.__logger = cm.channel_logger_get(logger_name)
            self.__logger_cdb = self.__logger.channel_database_get()
        except Exception, e:
            raise Exception, "Error: Can't set logger %s (%s)" % (
                logger_name, str(e))

        return True

    def logger_next(self):

        if self.__logger is None:
            raise Exception, ERR_UNSELECTED_LOGGER

        try:
            self.__logger_cdb.log_next()
        except Exception, e:
            raise Exception, "Error: Unable to proceed to next record: %s" \
                  % str(e)

        return True

    def logger_prev(self):

        if self.__logger is None:
            raise Exception, ERR_UNSELECTED_LOGGER

        try:
            self.__logger_cdb.log_prev()
        except Exception, e:
            raise Exception, "Error: Unable to proceed to previous record: %s" \
                  % str(e)

        return True

    def logger_rewind(self):

        if self.__logger is None:
            raise Exception, ERR_UNSELECTED_LOGGER

        try:
            self.__logger_cdb.log_rewind()
        except Exception, e:
            raise Exception, "Error: Unable to rewind: %s" % str(e)

        return True

    def logger_seek(self, offset, whence="set", record_number=0):

        if self.__logger is None:
            raise Exception, ERR_UNSELECTED_LOGGER

        whence_map = { 'set': LOG_SEEK_SET,
                       'cur': LOG_SEEK_CUR,
                       'end': LOG_SEEK_END,
                       'rec': LOG_SEEK_REC, }
        if whence not in whence_map:
            raise Exception, \
                  "Error: Bad whence '%s', must be set, cur, end or rec" % (
                     repr(whence))
        try:
            self.__logger_cdb.log_seek(offset,
                                       whence_map[whence],
                                       record_number)
        except Exception, e:
            raise Exception, "Error: Unable to seek: %s" % str(e)

        return True

    def logger_dump(self):

        # Check if there is a logger set
        if self.__logger is None:
            return self.ERR_UNSELECTED_LOGGER
        else:
            return self.__write_channel_database(self.__logger_cdb)

    def logger_channel_get(self, channel_name):

        # Check if there is a logger set
        if self.__logger is None:
            return self.ERR_UNSELECTED_LOGGER

        channel = self.__logger_cdb.channel_get(channel_name)
        sample = channel.get()
        return self._marshal_sample(sample)

    def logger_pos(self):
        # Check if there is a logger set
        if self.__logger is None:
            raise Exception, self.ERR_UNSELECTED_LOGGER

        position = self.__logger_cdb.log_position()
        if position == None:
            raise Exception, "Error: No currently active position"

        return position

    def device_dump(self):
        return get_drivers(self.__core)

    def shutdown(self):

        self.__core.request_shutdown()
        return "shutting down..."


class XMLRPC(PresentationBase, threading.Thread):

    """
    This class extends one of our base classes and is intended as an
    example of a concrete, example implementation, but it is not itself
    meant to be included as part of our developer API. Please consult the
    base class documentation for the API and the source code for this file
    for an example implementation.
    """

    # Public methods: apply_settings, start, stop, update_display,
    # digiweb_cb, run.

    # Instance Variables:
    #     __name
    #        Stores the name of the XBeeDisplaySmall presentation instance.
    #     __core
    #        Core Presentation services.
    #     __digiweb_cb_handle
    #        Used to register the Digiweb callback.
    #     __digiweb_xmlrpc
    #        Stores an instance of Digi's XML RPC request handler, if
    #        the default webserver is used.

    def __init__(self, name, core_services):

        self.__name = name
        self.__core = core_services

        self.__digiweb_cb_handle = None
        self.__digiweb_xmlrpc = None

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        settings_list = [
            Setting(
              name='port', type=int, required=False, default_value=80),
            Setting(
              name='use_default_httpserver', type=bool, required=False,
              default_value=True),
        ]


        ## Initialize settings:
        PresentationBase.__init__(self, name=name,
                                  settings_list=settings_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)

    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        is_default = SettingsBase.get_setting(self, 'use_default_httpserver')
        # Always start a separate server on systems without digiweb's Callback
        if not globals().has_key('digiweb'):
            is_default = False
        if is_default:
            # Register digiweb callback:
            self.__digiweb_cb_handle = digiweb.Callback(self.digiweb_cb)
            self.__digiweb_xmlrpc = DigiWebXMLRPCRequestHandler()
            self.__digiweb_xmlrpc.register_introspection_functions()
            self.__digiweb_xmlrpc.register_instance(XMLRPCAPI(self.__core))
        else:
            # Only start a thread if the Python web-server is used:
            threading.Thread.start(self)
        return True

    def stop(self):
        self.__stopevent.set()
        if self.__digiweb_cb_handle:
            self.__digiweb_cb_handle = None
        if self.__digiweb_xmlrpc:
            self.__digiweb_xmlrpc = None
        return True

    def digiweb_cb(self, http_req_type, path, headers, args):
        if not path.endswith('/RPC2'):
            return None

        response = None
        try:
            response = self.__digiweb_xmlrpc._marshaled_dispatch(
                         args,
                         getattr(self.__digiweb_xmlrpc, "_dispatch", None))
        except:
            self.__tracer.error("Exception occured during " +
                                "XMLRPC request: %s",
                                traceback.format_exc())
            return (None, '')

        return (digiweb.TextXml, response)


    def run(self):

        port = SettingsBase.get_setting(self, "port")
        self.__tracer.info("starting server on port %d", port)

        if sys.version_info >= (2, 5):
            xmlrpc_server = SimpleXMLRPCServer(
                                addr = ('', port),
                                requestHandler = CustomXMLRPCRequestHandler,
                                logRequests = 0,
                                allow_none = True)

        else:
            xmlrpc_server = SimpleXMLRPCServer(
                                addr = ('', port),
                                requestHandler = CustomXMLRPCRequestHandler,
                                logRequests = 0)

        xmlrpc_server.register_introspection_functions()
        xmlrpc_server.register_instance(XMLRPCAPI(self.__core))

        try:
            # Poll the stop event flag at a minimum of each second:
            while not self.__stopevent.isSet():
                rl, wl, xl = select([xmlrpc_server.socket], [], [], 1.0)
                if xmlrpc_server.socket in rl:
                    xmlrpc_server.handle_request()
        except:
            self.__tracer.error("Exception occured during XMLRPC request:")
            self.__tracer.debug(traceback.format_exc())


# internal functions & classes
