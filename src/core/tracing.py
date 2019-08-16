############################################################################
#                                                                          #
# Copyright (c)2008-2012, Digi International (Digi). All Rights Reserved.  #
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
'''
The tracing module contains all functionality for handling tracing.

Users of this module should create a single TracingManager instance
(via TracingManager(core)), and then use tracing.get_tracer(name) for
getting Tracer objects.

The TracingManager is a core service in the DIA framework. Any code running
under the framework can simply do this::

    from tracing import get_tracer
    tracer = get_tracer('some name')

    tracer.calls('A low-level debug message for simply entering a routine!')
    tracer.debug('A debug message!')
    tracer.info('A info message!')
    tracer.warning('A warning message!')
    tracer.error('A error message!')
    tracer.critical('A critical message!')

'''

# imports
import sys
import threading
import os
import traceback
import types
# import digitime - not used yet

from Queue import Queue, Full, Empty
from common.utils import wild_match

# constants

# stolen from 16.6.2. Logging Levels in Python 2.6.5 library ref
LEVELS = {'CRITICAL': 50,
          'ERROR': 40,
          'WARNING': 30,
          'INFO': 20,
          'DEBUG': 10,
          'CALLS': 5,  # call-trace of parent/derived chaining
          'XBEE': 1,   # low=level chatter from for example DM waking
          'NOTSET': 0}

# add some min/max - not sure what is intended
LEVEL_MIN = 0
LEVEL_MAX = 100

# reverse lookups
LEVELS_REV = dict(zip(LEVELS.values(), LEVELS.keys()))

# internal tracing manager instance
_TM = None

# internal tracing manager thread
_TMT = None
_QUEUE_SIZE = 64  # (Number by Travis)

# internal functions


####################################################
############# making Python complete ###############
####################################################


def _andmap(func, _iter):
    # '''
    # Apply fn to each item in iter in turn, stopping
    # as soon as fn returns False. If fn ever returns False,
    # this function returns False. Otherwise, it returns True.
    # '''
    for i in _iter:
        if not func(i):
            return False
    return True


def _ormap(func, _iter):
    # '''
    # Apply fn to each item in iter in turn, stopping as
    # soon as fn returns True. If fn returns True, this function
    # returns True. Otherwise, it returns False.
    # '''
    for i in _iter:
        if func(i):
            return True
    return False


def _ensure_list(maybe_list):
    # '''
    # Helper method to wrap singletons into a list.
    # '''
    if maybe_list == None:
        return []
    elif not isinstance(maybe_list, list):
        return [maybe_list]
    else:
        return maybe_list


def _remove_quotes(_str):
    # '''
    # _strip the quotes from a string (iff an identical quote character
    # is the first and last character.)
    # '''
    if _str[0] == '\'':
        if _str[-1] == '\'':
            return _str[1:-1]
        else:
            raise BadParseException('unmatched ending \' ' +
                                    'character in %s' % (_str))
    elif _str[0] == '"':
        if _str[-1] == '"':
            return _str[1:-1]
        else:
            raise BadParseException('unmatched ending " ' +
                                    'character in %s' % (_str))
    else:
        return _str


def _parse_boolean(val):
    # '''
    # Turn a string into a boolean value.
    # '''
    if isinstance(val, bool):
        return val
    elif isinstance(val, int):
        return bool(val)

    elif not isinstance(val, basestring):
        raise BadParseException('_parse_boolean called on ' +
                                'non-string: %s' % (val))

    val = _remove_quotes(val.upper())

    if val == '0' or val.startswith('F'):
        return False
    elif val == '1' or val.startswith('T'):
        return True
    else:
        raise BadParseException('_parse_boolean cannot ' +
                                'interpret this: %s' % (val))


######################### filter parsing ########################


def _generate_filter(level_str, msg_str):
    '''
    Generates a function that returns true if a passed TraceEvent
    matches the given level_str and msg_str.

    :param level_str:
    '''

    # nothing to match!
    if not level_str and not msg_str:
        return lambda x: True

    # just a msg string
    elif not level_str:
        return lambda x: _parse_msg_string(msg_str)(x.msg)

    # just a level
    elif not msg_str:
        return lambda x: _parse_lvl_string(level_str)(x.level)

    # both
    else:
        return lambda x: _parse_lvl_string(level_str)(x.level) and \
               _parse_msg_string(msg_str)(x.msg)


def _parse_lvl_string(level_str):
    # Parse a level string and return a function that
    # takes a TraceEvent and returns a boolean.

    blocks = level_str.split(' or ')

    # TODO: could simplify silly rules after parsing
    funcs = map(_parse_slevel, blocks)

    return lambda x: _ormap(lambda y: y(x), funcs)


def __bad_parse_slevel(slevel):
    # handle bad parse
    print "\tbad slevel definition: %s\n\tIgnoring it." % \
                  (slevel)
    return lambda x: True


def _parse_slevel(slevel):
    # Turn an <slevel> from BNF in Filter's __init__
    # doc into a function.

    # remove syntactic sugar
    if slevel[0:2] == '>=':
        slevel = slevel[2:]
    if slevel[0] != '=':
        # make sure this level exists
        if not slevel.upper() in LEVELS:
            return __bad_parse_slevel(slevel)
        else:
            lvl = LEVELS[slevel.upper()]
            return lambda x: x >= lvl
    elif slevel[0] == '=':
        slevel = slevel[1:]
        # make sure this level exists
        if not slevel.upper() in LEVELS:
            __bad_parse_slevel(slevel)
        else:
            lvl = LEVELS[slevel.upper()]
            return lambda x: x == lvl
    else:
        __bad_parse_slevel(slevel)


def _parse_msg_string(msg_str):
    and_blocks = msg_str.split(' and ')

    funcs = map(_parse_or_blocks, and_blocks)

    return lambda x: _andmap(lambda y: y(x), funcs)


def _parse_or_blocks(or_block):
    blocks = or_block.split(' or ')

    # TODO: could simplify silly rules after parsing
    funcs = map(_parse_msg_block, blocks)

    return lambda x: _ormap(lambda y: y(x), funcs)


def _parse_msg_block(block):
    return lambda x: wild_match(block, x)


def _parse_filter(filter_dict, default_handlers):
    # '''
    # Parse a filter dict into a Filter object.

    # Returns a tuple (name_str, Filter_obj)
    # '''
    if not isinstance(filter_dict, dict):
        raise BadParseException('filter entry is not a dict!')

    if not ('name' in filter_dict or 'level' in filter_dict):
        raise BadParseException('filter dict needs at least ' +
                                'one of "name" and "level" fields')

    if 'name' in filter_dict:
        name = _remove_quotes(filter_dict['name'])
    else:
        name = '*'

    # default event values
    level_str = None
    msg_str = None
    handlers = default_handlers
    stop = True

    if 'level' in filter_dict:
        level_str = filter_dict['level']
    if 'msg' in filter_dict:
        msg_str = filter_dict['msg']
    if 'handlers' in filter_dict:
        handlers = _ensure_list(filter_dict['handlers'])
    if 'stop' in filter_dict:
        stop = _parse_boolean(filter_dict['stop'])

    return name, Filter(level_str, msg_str, handlers, stop)


############# dia specific things ################
def _parser_hack(yaml_list):
    # '''
    # Unwrap a single-entry list (which the parser
    # wraps in a dict) transparently. If the parsed list
    # is already actually a list, nothing is done.
    # '''
    if isinstance(yaml_list, dict):
        # sanity checks
        if 'instance_list' in yaml_list and \
            len(yaml_list) == 1:
            return yaml_list['instance_list']
        else:
            # throw up
            raise Exception('this doesn\'t look like a yaml list: %s' %
                                            (yaml_list))
    else:
        return yaml_list


def _get_tracing_dict(core_services):
    # Get the 'tracing:' block from the yaml, or fake it.

    # this shouldn't happen
    if not 'tracing' in core_services._settings_global_pending_registry:
        print 'no config found... using defaults.'
        return TracingManager.defaults

    ret = core_services._settings_global_pending_registry['tracing']

    # if no 'tracing:' block  exists, this is where it will catch
    if ret == []:
        print 'no config found... using defaults.'
        return TracingManager.defaults

    print ''  # finish the Starting Tracing Manager... line

    if not isinstance(ret, dict):
        print '\t\'tracing:\' entry is badly formed....',
        print 'using defaults.'
        return TracingManager.defaults
    else:
        return ret

# exception classes

# class FileExistsException(Exception):
#     '''
#     Raised when a log file is requested with file clobbering disabled.
#     '''
#     pass


class BadParseException(Exception):
    '''
    Raised when a parsing element is passed improper input.
    '''
    pass


class TracerThreadAlreadyStartedException(Exception):
    '''
    Raised when more than one instance of the Tracer thread is
    created.
    '''
    pass


# helper functions


def warn(msg):
    '''
    Send a message to wherever stderr points.
    '''
    sys.stderr.write(msg)


# interface functions


def get_tracer(name, level=LEVELS['WARNING']):
    '''
    This is the only function client drivers should call.

    Returns the tracing object with the given argument name, creating
    it if necessary.

    If the TracingManager was not instantiated, then we return a
    Tracer that prints TraceEvents at at argument level or higher to
    stderr.
    '''

    if not _TM:
        # raise Exception('get_tracer() called before TracingManager' +
        #                 ' instantiated.')
        return Tracer(name, level=level,
                      handlers=(Handler('sys.stderr'),),
                      filters=None)
    else:
        return _TM._get_tracer(name)


def add_filter(name_wildcard, filter_object):
    '''
    Add a filter to the TracingManager.

    This function only needs to be used if the TracingManager is being
    configured programmatically (outside of DIA). In this case,
    use the function to collect the list of Handlers for a new Filter's
    argument, like this::

        # instatiate the singular TracingManager (without any arguments)
        tm = TracingManager()

        # create a filter that writes all warning messages to the
        # handlers, and then stop processing
        filter = Filter('=warning', '*', ('file=something.log', 'stderr'),
                        stop=True)

        # add this to the TracingManager's stack, and match every Tracer
        add_filter("*", filter)

        tracer = get_tracer('test1')

        # This message is printed to stderr and logged to something.log
        tracer.warning('This is a warning!')


    The filter will only apply to to Tracer objects which are
    obtained via tracing.get_tracer(name) *after* the add_filter call.
    Furthermore, the name passed to get_tracer must match the
    name_wildcare passed here.

    This function is NOT idempotent. Repeated calls will add repeated
    copies of the filter to the Tracing Manager's stack. Depending on
    the particular settings of the Filter (in particular, the 'stop'
    setting), this may or may not result in duplicate message logging.

    '''
    if not _TM:
        raise Exception('add_filter() called before TracingManager' +
                        ' instantiated.')

    _TM._filter_pairs.append((name_wildcard, filter_object))


def _get_handler(name):
    '''
    Return a handler from the store (creating it if necessary).
    '''
    key = _parse_handler_string(name)

    if not _TM:
        # if there is no manager, create a standalone item
        return Handler(key)

    if not key in _TM.handler_registry:
        _TM.handler_registry[key] = Handler(key)

    return _TM.handler_registry[key]


#classes
class TracingManagerThread(threading.Thread):
    '''
    Handles writing from queue.
    '''
    def __init__(self, queue_size=_QUEUE_SIZE, print_overflow=True):
        '''
        Queue size is max number of trace messages can be buffered.

        If we try to add more (and print_overflow=True), then we
        print an overflow warning and print the original message our.
        '''
        self._warn = print_overflow
        self._stopevent = threading.Event()

        self._queue = Queue(queue_size)

        global _TMT
        if _TMT != None:
            raise TracerThreadAlreadyStartedException('Previous instance: ' \
                                                          '%s' % _TMT)
        _TMT = self
        threading.Thread.__init__(self)

    def start(self):
        threading.Thread.start(self)

    def stop(self):
        ''' stop the thread '''
        self._stopevent.set()

        # unblock the run thread
        self._queue.put((Handler.DummyFlo('dummy'),
                         'tracing should be stopped'))

    def run(self):
        '''
        Send messages to their respective homes until stop is called.
        '''
        while not self._stopevent.isSet():
            work = self._queue.get()
            # did we break because of exit?
            if self._stopevent.isSet():
                break
            try:
                work[0].write(str(work[1]))
                # this is enabled here so you can 'tail -f' log files
                work[0].flush()
            except Exception, e:
                warn('Exception when executing tracing write: %s' \
                         % (str(e)))

    def add(self, flo, trace_event):
        '''
        Add to the queue, or throw an error message if the buffer is full.
        '''
        try:
            self._queue.put((flo, trace_event))
        except Full:
            if self._warn:
                warn('Buffer overflow: could not add message: %s\n' % (
                        str(trace_event)))


class TracingManager(object):
    '''
    Manages global tracing behavior.

    This class serves as the tracing core. All calls to tracer.(info...)
    wind up here.

    This is a cheap semi-clone of standard Python's "logging" module.
    '''
    # default settings if "tracing" block is not present in yaml config
    defaults = {'default_level': 'debug',
                'default_handlers': 'stderr'}

    def __init__(self, core_services=None, def_dict=None):
        '''
        TracingManager must be created exactly once.

        If the core argument (a DIA CoreServices object) is passed,
        then then this object is initialized using the information
        available.

        If the def_dict argument is provided (and the core argument is
        not), then this object will parse those settings. (The settings
        format is identical to the parseable yaml version. The
        TracingManager can also be configured using the add_handler() and
        add_filter() methods.)
        '''
        global _TM

        if _TM == None:
            _TM = self
        else:
            # We have a manager already.  If this is due to a new
            # instance of Dia running in the same interpreter (happens
            # w/ the unit tests), we want to restart, otherwise error
            if core_services:
                try:
                    tm = core_services.get_service('tracing_manager')
                except:
                    _TM = self
            else:
                raise Exception('Tracing manager instantiated twice!')

        # all handler devices (by output name)
        self.handler_registry = {}

        self.__tracer_registry = {}

        # default master settings
        self.__default_handlers = []

        # list of (wildcard_string, Filter_object)
        self._filter_pairs = []

        # filterless object message cut-off
        self.trace_level = LEVELS['WARNING']

        # master message cut-off
        self.master_level = LEVELS['NOTSET']

        # if we are running in DIA, set things up using the core
        if core_services:
            core_services.set_service('tracing_manager', self)
            def_dict = _get_tracing_dict(core_services)

        if def_dict:
            self._read_settings(def_dict)

        # start the marking thread
        self._tracing_thread = TracingManagerThread()
        self._tracing_thread.start()

    def __repr__(self):
        '''
        simple representation
        '''
        return '<TracingManager %s>' % str(self.get_config())

    def get_config(self):
        '''
        Return a dictionary of the current configuration. This may
        be useful for runtime inspection.
        '''
        return {'handlers': self.handler_registry,
                'tracers': self.__tracer_registry,
                'default_handlers': self.__default_handlers,
                'trace_level': self.trace_level,
                'master_level': self.master_level,
                'filter_pairs': self._filter_pairs}

    def stop(self):
        '''
        This should only be called by dia.py after
        shutting down everything else.
        '''
        global _TMT
        if _TMT:
            _TMT.stop()
            _TMT = None

        for i in self.handler_registry.values():
            i.close()

    def _read_settings(self, def_dict):
        '''
        Try to read settings from a def_dict.

        (1) Initialize default settings.

        (2) Generate all filters

        Ordering of filters is preserved.
        '''
        filter_pairs = ()  # false appendable iterable

        # parsing settings
        for key in def_dict:
            # default handlers
            if key == 'default_handler' or key == 'default_handlers':
                _list = _ensure_list(def_dict[key])
                self.__default_handlers = _parse_handlers(_list)
            elif key == 'default_level':
                try:
                    self.trace_level = _parse_single_level(def_dict[key])
                except BadParseException:
                    print ('\tbad default level %s... should be one of %s') % (
                          def_dict[key], LEVELS.keys())
                    print ('\tUsing "warning" for default_level.')
                    self.trace_level = LEVELS['WARNING']
            elif key == 'master_level':
                try:
                    self.master_level = _parse_single_level(def_dict[key])
                except BadParseException:
                    print ('\tbad master_level %s... should be one of %s') % (
                                                def_dict[key], LEVELS.keys())
                    print '\tUsing \"notset\" for master_level.'
                    self.master_level = LEVELS['NOTSET']

            elif key == 'filters':
                filter_pairs = self._parse_filters(def_dict[key])

            else:
                print '\ttracing: doesn\'t understand key \"%s\"' % (key)

        self._filter_pairs = filter_pairs

    def _make_tracer(self, name, filters):
        '''
        Create and return a Tracer.

        The key difference is that if a particular
        device-ish matches at least one filter,
        its cut-off level is set to self.master_level,
        so that TraceEvents can be reached by its filters.

        Otherwise, a filterless Tracer uses the maximum level
        of self.trace_level and self.master_level
        for its cut-off.
        '''
        if filters:
            return Tracer(name, self.master_level,
                          self.__default_handlers,
                          filters)
        else:
            return Tracer(name, max(self.trace_level,
                                    self.master_level),
                          self.__default_handlers,
                          False)

    def _get_tracer(self, name):
        '''
        Use tracing.get_tracer(name) for grabbing Tracer objects
        outside of this model.

        If a tracer with 'name' does not exist, the list of filters is
        checked and applied.

        This means that special tracers (like the scheduler's)
        can still have filter rules written for them, because
        the filter registry is build before any other part of
        the system comes up.
        '''
        if not name in self.__tracer_registry:

            # check all potential filters for a match
            filters = []

            for i, j in self._filter_pairs:
                if wild_match(i, name):
                    filters.append(j)

            self.__tracer_registry[name] = \
                self._make_tracer(name, filters or None)

        return self.__tracer_registry[name]

    def _parse_filters(self, filter_list):
        '''
        Parse the yaml 'filters:' entry into a list of tuples
        with the format:
        (name_str, Filter_obj),

        (where name_str is a dbe used for matching device names
        to filters)
        '''
        ret = []

        #
        # HACK: This is a workaround for the yaml parser currently
        #       used by the DIA framework.
        #
        #       If a yml file is a list of dictionaries,
        #       and all dictionaries contain a 'name' key, then
        #       the parser transforms this into a dictionary with
        #       'instance_list' as the single key and the list of
        #       dictionaries as the value.
        #
        filter_list = _parser_hack(filter_list)

        for i in filter_list:
            try:
                ret.append(_parse_filter(i, self.__default_handlers))
            except BadParseException:
                print "\tignoring mangled filter entry: %s" % i

        return ret


def _parse_handlers(handlers):
    '''
    Argument handlers is a string or list of strings.
    If handlers='', then [] is returned.

    Returns a list of handler references.
    '''
    strs = _ensure_list(handlers)
    ret = []
    for i in strs:
        try:
            ret.append(_get_handler(i))
        except NotImplementedError:
            print "\tignoring unknown handler %s" % i
        except IOError:
            print "\tignoring %s (file error)" % i

    return ret


def _parse_single_level(levels_str):
    '''
    Parse a *simple* level string and return its number.
    This is probably only used for reading the default level.
    '''
    _str = levels_str.upper()

    if _str in LEVELS:
        return LEVELS[_str]
    else:
        raise BadParseException


def __get_handler(handler_string):
    '''
    Add a Handler to the TracingManager if it doesn't already exist and
    return a reference to the Handler.


    This function is idempotent.
    '''
    if not _TM:
        raise Exception('__get_handler() called before TracingManager' +
                        ' instantiated.')

    key, _ = _parse_handler_string(handler_string)

    #TODO: use key_type as a hook for new handler types

    if not key in _TM.handler_registry:
        val = Handler(key)
        _TM.handler_registry[key] = val

    return _TM.handler_registry[key]


class Tracer(object):
    '''
    An object which exposes five functions to the world for logging.

    Instances should be grabbed by calling tracing.get_tracer(name).
    '''

    def __init__(self, name, level, handlers, filters):
        self.name = name
        self.level = level
        self.handlers = handlers
        self.filters = filters

    def __repr__(self):
        ''' simple repr '''
        return '<Tracer %s>' % str(self.get_config())

    def get_config(self):
        '''
        encapsulation of all things
        '''
        return {'name': self.name,
                'level': self.level,
                'handlers': self.handlers,
                'filters': self.filters}

    def set_level(self, arg):
        '''
        Set the level of the Tracer.

        arg must be a string, None, or a bool
        If arg == None, the level is not changed

        If arg is a bool,
            True -> "debug"
            False -> "critical"

        acceptable string arguments (case insensitive):
        * any level (debug, info, ...)
        * ""            -> no change
        * "off"/"false" -> "critical"
        * "on"/"true"   -> "debug"
        '''
        if arg == None:
            return

        elif isinstance(arg, types.BooleanType):
            # handle simple want/don't want settings
            if arg:
                self.level = LEVELS['DEBUG']
            else:
                self.level = LEVELS['CRITICAL']

        elif isinstance(arg, types.IntType):
            # assume is an integer value, example direct copy from another
            if arg < LEVEL_MIN or arg > LEVEL_MAX:
                raise ValueError('Bad argument to set_level(%d) - must be %d to %d' \
                    % (arg,LEVEL_MIN,LEVEL_MAX))
            else:
                # at present we don't seem to have a MAX
                self.level = arg
 
        else:
            arg = arg.upper()
            if arg in LEVELS:
                self.level = LEVELS[arg]
            elif arg == '':
                # then no change
                return
            elif arg in ('ON', 'TRUE'):
                self.level = LEVELS['DEBUG']
            elif arg in ('OFF', 'FALSE'):
                self.level = LEVELS['CRITICAL']
            else:
                raise ValueError('Bad argument to set_level: %s' \
                                     % (arg))

    def log(self, level, msg, *args):
        '''
        All other exposed Tracer methods call this method with their
        respective numerical values as the level argument.

        '''
        # basic cut-off
        if self.level > level:
            return False

        if msg == None:
            return True

        trace_event = TraceEvent(self.name, level, msg, args)

        default_write = not bool(self.filters)

        if self.filters:
            # check if some filter accepts it
            for i in self.filters:
                ret = i.examine(trace_event)
                if ret == Filter.NO_MATCH:
                    continue
                elif ret == Filter.CONTINUE:
                    default_write = True
                    continue
                elif ret == Filter.MATCH:
                    default_write = True
                    break
                elif ret == Filter.DONE:
                    default_write = False
                    break

        if default_write:
            for i in self.handlers:
                i.write(trace_event)

    def critical(self, msg=None, *args):
        '''
        Send a message at the critical level.
        '''
        return self.log(LEVELS['CRITICAL'], msg, *args)

    def error(self, msg=None, *args):
        '''
        Send a message at the error level.
        '''
        return self.log(LEVELS['ERROR'], msg, *args)

    def warning(self, msg=None, *args):
        '''
        Send a message at the warning level.
        '''
        return self.log(LEVELS['WARNING'], msg, *args)

    def info(self, msg=None, *args):
        '''
        Send a message at the info level.
        '''
        return self.log(LEVELS['INFO'], msg, *args)

    def debug(self, msg=None, *args):
        '''
        Send a message at the debug level.
        '''
        return self.log(LEVELS['DEBUG'], msg, *args)

    def calls(self, msg=None, *args):
        '''
        Send a message at the call-stack level.
        '''
        return self.log(LEVELS['CALLS'], msg, *args)

    def xbee(self, msg=None, *args):
        '''
        Send a message at the xbee level.
        '''
        return self.log(LEVELS['XBEE'], msg, *args)

# internal functions & classes


def _parse_handler_string(_str):
    '''
    Parse a handler string (from a yaml) and returns a unique string
    name.

    The format is::
       handlers:
         - file="haha"
         - stdout
         - stderr
         - file=hey_i_have_no_quotes

    TODO: this should be extended for more output types
    '''

    if _str.lower() == 'stdout':
        return 'sys.stdout'
    elif _str.lower() == 'stderr':
        return 'sys.stderr'
    elif _str.startswith('file='):
        fname = os.path.abspath(_remove_quotes(_str[5:]))
        return 'file=%s' % (fname)
    else:
        raise NotImplementedError


class Handler(object):
    '''
    Manages access to a single flo.

    The `key` argument is either 'sys.stdout',
    'sys.stderr', or some filename.

    If a filename is given, it will be opened and the current
    file contents will be clobbered.

    TODO: this should be extended to handle
          writing to different types
    '''

    def __init__(self, key):
        self._lock = threading.RLock()
        self._key = key
        self._needs_close = False
        self._closed = False

        if key == 'sys.stdout':
            self.flo = sys.stdout
        elif key == 'sys.stderr':
            self.flo = sys.stderr
        elif key.startswith("file="):
            # refuse to clobber
            # TODO: improve file handling
            # if os.path.exists(key[5:]):
            #     raise FileExistsException
            self._needs_close = True
            self.flo = open(key[5:], 'w')
        else:
            raise NotImplementedError

    def __repr__(self):
        ''' simple representation '''
        return '<Handler ' + str({'key': self._key}) + '>'

    def write(self, trace_event):
        '''
        Write output in a thread-safe manner.
        '''
        # in the case of no managing thread
        if not _TMT:
            self._lock.acquire()
            try:
                self.flo.write(str(trace_event))
                # this is enabled here so you can 'tail -f' log files
                self.flo.flush()
            finally:
                self._lock.release()
        else:
            _TMT.add(self.flo, trace_event)

    def close(self):
        '''
        Close the flo this handler controls and replace the
        connection with a DummyFlo.
        '''
        if not self._closed and self._needs_close:
            self._lock.acquire()
            self.flo.close()
            self.flo = self.DummyFlo(self._key)
            self._closed = True
            self._lock.release()

    class DummyFlo(object):
        '''
        Stub flo writing output that all TracingManager.__handlers
        are connected to after closing.

        This should never be used.
        '''

        def __init__(self, key):
            self.__key = key

        def write(self, trace_event):
            '''
            Stub write method used by Handler after calling close.
            '''
            print ('WARNING: writing to closed Handler "%s"!' +
                   '\t(This is probably an error... was the ' +
                   'TracingManager killed early?)\n\tTrace event ' +
                   'was: (%s)') % (self.__key, str(trace_event))

        def flush(self):
            '''
            Stub flush method. This should never be called.
            '''
            pass


class TraceEvent(object):
    '''
    Encapsulation of log level, message, and potentially other things.
    This is what is generated and passed through the system when
    someone calls (log()|debug()|...) on a Tracer object.


    '''
    def __init__(self, tracer_name, level, msg, args):
        self.tracer = tracer_name
        self.level = level
        self.msg = msg
        self.args = args

        # TODO: implement lazy evaluation, so we can do this later...
        try:
            self.expanded_msg = self.msg % self.args
        except TypeError, e:
            entries = traceback.extract_stack()
            try:
                entry = entries[-4]
            except Exception:
                entry = ('??', -1, '??', '??')
            print 'Formatting error in %s, line %s ' \
                                '(str "%s", args %s):' \
                '\n%s' % (entry[0], entry[1], self.msg, self.args, str(e))
            self.expanded_msg = 'Broken message: "%s", args: %s' % (
                self.msg, self.args)

        # TODO: expand this to include time, etc...

    def __str__(self):
        lvl_str = ''
        try:
            lvl_str = LEVELS_REV[self.level]
        except:
            lvl_str = str(self.level)

        # TODO: HOOK: do message formatting here
        return "%s:%s:%s\n" % (lvl_str,
                               self.tracer,
                               self.expanded_msg)


################################################################
###################### Filter and friends ######################
################################################################
class Filter(object):
    '''
    A Tracer can have zero or more Filters in a list.  When a method
    is called on the Tracer, a TraceEvent is generated.  The
    TraceEvent is passed to each Filter in the Tracer's list until a
    Filter.MATCH or Filter.DONE is returned.

    In the simplest case, a filter simply returns a
    Filter.MATCH or Filter.NO_MATCH. If the Filter returns
    Filter.MATCH, the Filter's parent Tracer writes the
    TraceEvent to its default handlers, and life goes on.

    But a Filter can also completely handle all output by itself,
    because it can have its own Handlers. If this is true, and
    the filter matches, it will return Filter.DONE, which tells
    the Tracer that everything has been taken care of.

    The *final* case is if a Filter does some output handling
    and then wants its parent Tracer to continue down its
    Filter's list. In this case, the Filter returns
    Filter.CONTINUE. If a CONTINUE has been returned by a Filter
    and not followed by a DONE, the TraceEvent will also
    be written to the default handlers.

    A Tracer stops trying a message against its filters in
    3 different ways.

    (1) a MATCH is returned: Tracer writes message to default handlers
    (2) a DONE is returned
    (3) the end of the filter list is reached
           - if a CONTINUE was ever returned, Tracer writes the message
             to default handlers
    '''

    # return codes for filters
    NO_MATCH = 0  # Tracer tries next filter
    MATCH = 1  # Tracer writes TraceEvent to its handlers and stops
    DONE = 2  # Tracer stops trying
    CONTINUE = 3  # Tracer tries next filter

    def __init__(self, level, msg, handlers, stop):
        '''
        :param msg: a string with the following format:

           <msg> ::= <expr_or> | <expr_or>(" and "<expr_or>)*
           <exprs_or> ::= <string> | <string>(" or "<expr>)*
           <string> ::= <python_string> | "\""<string with spaces>"\""


        :param level: a string with the following format:
            <level> ::= <slevel> | <slevel>(" or "<slevel>)*
            <slevel> ::= <type> | ">="<type> | "="<type>
            <type> ::= any key defined in the dict LEVELS located
                       in this module

        :param handlers: a list of strings, each one of the following:
                1) 'stdout'
                2) 'stderr'
                3) 'file=<some filename>'

        :param stop: boolean specifying whether or not processing should
                     continue after a match

        '''
        # save all raw configuration for human examination
        self._config = {'level': level, 'msg': msg, 'handlers': handlers,
                        'stop': stop}

        parsed_handlers = _parse_handlers(handlers)

        self.__filter_func = _generate_filter(level, msg)
        self.__handlers = parsed_handlers
        self.__stop = stop

    def __repr__(self):
        ''' simple representation '''
        return '<Filter ' + str(self.get_config()) + '>'

    def get_config(self):
        ''' Return internal configuration as a dictionary. '''
        return self._config

    def examine(self, trace_event):
        '''
        Process a trace event (and possibly writing to Handlers).
        '''
        if self.__filter_func(trace_event):
            # if this Filter has personal handlers, use them
            if isinstance(self.__handlers, list):  # [] means no output
                for i in self.__handlers:
                    i.write(trace_event)
                if self.__stop:
                    return Filter.DONE
                else:
                    return Filter.CONTINUE
            # otherwise, just notify the Tracer
            else:
                return Filter.MATCH
        else:
            return Filter.NO_MATCH


from core.tracing import get_tracer
_tracer = get_tracer("tracing")

################### testing ####################
def __test__parse_boolean():
    '''
    Ensure _parse_boolean sanity.
    '''
    assert _parse_boolean(True)
    assert not _parse_boolean(False)
    assert _parse_boolean(1)
    assert not _parse_boolean(0)
    assert _parse_boolean('1')
    assert not _parse_boolean('0')
    assert _parse_boolean('"t"')
    assert not _parse_boolean('"f"')


def __test__remove_quotes():
    '''
    Ensure _remove_quotes sanity.
    '''
    assert _remove_quotes('"name"') == 'name'
    assert _remove_quotes('name"') == 'name"'
    assert _remove_quotes('\'name\'') == 'name'
    assert _remove_quotes('name\'') == 'name\''


def __test__andmap():
    # Basic _andmap sanity checks.

    assert _andmap(lambda x: x, [True]*5)
    assert not _andmap(lambda x: x, [True]*5 + [False])


def __test__ormap():
    # Basic _ormap sanity checks.

    assert not _ormap(lambda x: x, [False]*7)
    assert _ormap(lambda x: x, [False]*4 + [True])


##################### parsing tests ##################
def __test_parse_filter1():
    # Sanity check of filter parsing with no stop.
    def_dict = {'level': 'warning', 'name': 'test3'}

    name, filt = _parse_filter(def_dict, None)

    assert name == 'test3'
    assert filt.get_config()['level'] == 'warning'
    assert filt.get_config()['stop']


def __test_parse_filter2():
    # Sanity check of filter parsing with stop.
    def_dict = {'level': 'warning', 'name': 'test3', 'stop': False}

    name, filt = _parse_filter(def_dict, None)

    assert name == 'test3'
    assert filt.get_config()['level'] == 'warning'
    assert not filt.get_config()['stop']


def __test_parse_or_blocks():
    # message 'or' testing
    func = _parse_or_blocks('*eve or cs?aslk or asl')

    assert not func('even')
    assert func('eve')
    assert func('cs9aslk')
    assert func('asl')


def __test_parse_msg_string():
    # message 'or' and 'and' testing
    func = _parse_msg_string('*hi* and bl?ank* or red*')

    assert func('redaplhi')
    assert func('blzankhi')
    assert not func('high')
    assert not func('blaank')
    assert not func('redsphere')


def __test_parse_lvl_string():
    # sanity check for level strings
    func = _parse_lvl_string('warning or debug or >=error')

    assert func(LEVELS['warning'.upper()])
    assert func(LEVELS['error'.upper()])

    func = _parse_lvl_string('=debug')

    assert not func(LEVELS['warning'.upper()])
    assert not func(LEVELS['error'.upper()])
    assert func(LEVELS['debug'.upper()])
