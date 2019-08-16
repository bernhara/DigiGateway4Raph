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
Digi customizeded scheduler module.  Derived from Python standard
library `sched` module. Interface and API are nearly identical with
changes made to support cleaner execution on Digi devices.
"""

# 2008/09/18 Enhanced by Landon Bouma and
# Jordan Husney <jordanh@digi.com> to use a condition variable
# to allow for pre-emption.  "timefunc" and "delayfunc" were
# removed from the __init__ routine as a consequence.

import heapq
from time import time as timefunc
from threading import Condition
from core.tracing import get_tracer

import traceback

__all__ = ["scheduler"]

class scheduler:
    """
    A generally useful event scheduler class.

    Each instance of this class manages its own queue.
    No multi-threading is implied; you are supposed to hack that
    yourself, or use a single instance per application.

    Each instance is parametrized with two functions, one that is
    supposed to return the current time, one that is supposed to
    implement a delay.  You can implement real-time scheduling by
    substituting time and sleep from built-in module time, or you can
    implement simulated time by writing your own functions.  This can
    also be used to integrate scheduling with STDWIN events; the delay
    function is allowed to modify the queue.  Time can be expressed as
    integers or floating point numbers, as long as it is consistent.

    Events are specified by tuples (time, priority, action, argument).
    As in UNIX, lower priority numbers mean higher priority; in this
    way the queue can be maintained as a priority queue.  Execution of the
    event means calling the action function, passing it the argument.
    Remember that in Python, multiple function arguments can be packed
    in a tuple.   The action function may be an instance method so it
    has another way to reference private data (besides global variables).
    Parameterless functions or methods cannot be used, however.
    """

    def __init__(self):
        """Initialize a new instance"""
        self.queue = []
        self.__preemption_condition = Condition()

        self.__tracer = get_tracer('digi_sched')

    def enterabs(self, time, priority, action, argument):
        """Enter a new event in the queue at an absolute time.

        Parameters:

        * time - time as provided by `time.time()` when the event
          should occur

        * priority - Priority relative to other events to determine
          simultaneous execution order.

        * action - Event to perform

        * argument - parameter to pass to action

        Returns an ID for the event which can be used to remove it,
        if necessary.

        """
        event = time, priority, action, argument
        self.__preemption_condition.acquire()
        try:
            heapq.heappush(self.queue, event)
            self.__preemption_condition.notify()
        finally:
            self.__preemption_condition.release()

        return event # The ID

    def enter(self, delay, priority, action, argument):
        """A variant that specifies the time as a relative time.

        Identical to `enterabs`, except replacing `time` with
        `delay`. `delay` is the relative offset from the present to
        schedule `action`

        """
        time = timefunc() + delay
        return self.enterabs(time, priority, action, argument)

    def cancel(self, event):
        """Remove an event from the queue.

        This must be presented the ID as returned by enter().
        If the event is not in the queue, this raises ValueError.

        """
        self.__preemption_condition.acquire()
        try:
            self.queue.remove(event)
            heapq.heapify(self.queue)
            self.__preemption_condition.notify()
        finally:
            self.__preemption_condition.release()

    def empty(self):
        """Check whether the queue is empty."""
        return not self.queue

    def run(self):
        """Execute events until the queue is empty.

        When there is a positive delay until the first event, the
        delay function is called and the event is left in the queue;
        otherwise, the event is removed from the queue and executed
        (its action function is called, passing it the argument).  If
        the delay function returns prematurely, it is simply
        restarted.

        It is legal for both the delay function and the action
        function to to modify the queue or to raise an exception;
        exceptions are not caught but the scheduler's state remains
        well-defined so run() may be called again.

        A questionable hack is added to allow other threads to run:
        just after an event is executed, a delay of 0 is executed, to
        avoid monopolizing the CPU when other threads are also
        runnable.

        """
        q = self.queue
        while True:
            self.__preemption_condition.acquire()
            if not q:
                self.__preemption_condition.release()
                break

            # we fetch the FIRST event, and since the events are queued in
            # future time order, this is the next even to run. Events after
            # it have either the SAME start time, or a later start time
            time, _, action, argument = checked_event = q[0]
            now = timefunc()
            if now < time:
                # then not yet time to run, this ends our cycle since all
                # events queued after this will also not be ready.
                self.__preemption_condition.wait(time - now)
                self.__preemption_condition.release()
            else:
                # else the scheduled time is OLDER than NOW
                try:
                    event = heapq.heappop(q)
                    # Verify that the event was not removed or altered
                    # by another thread after we last looked at q[0].
                    if event == None or not isinstance(event, tuple):
                        pass
                    elif event is checked_event:
                        self.__preemption_condition.release()
                        try:
                            action(*argument)
                        except Exception:
                            self.__tracer.error(
                                ('Exception calling %s with args: \'%s\'.' +
                                 '\n\tDeleting scheduled event.')
                                 % (action, argument))

                            self.__tracer.debug(traceback.format_exc())

                        self.__preemption_condition.acquire()
                        del event
                    else:
                        heapq.heappush(q, event)
                finally:
                    self.__preemption_condition.release()
