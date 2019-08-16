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
    The scheduler provides a centralized scheduler resource to
    minimize the number of thread resources devoted simply to time-keeping
    between periodic or otherwise timed operations.

    The scheduler is appropriate to use if your periodic operations
    will not perform blocking operations.  This is not enforced in the
    code.  Any blocking operations will degrade the performance of the
    entire system and cause delays in the execution of scheduled tasks
    throughout. 
"""

# imports
from common.sched_async import SchedAsync

# constants

# interface functions

# classes

class Scheduler(SchedAsync):
    """\
        DIA core service which provides centralized scheduling resources
    
        Rather than require all modules in the system to have to spawn
        threads to perform periodic operations, the scheduler operation
        allows these work items to be scheduled.

        Parameters:

        * `core_services` - The
          :py:class:`~core.core_services.CoreServices`
          object of the system

        The main scheduler for the system is created by the system.
        It is not necessary to create additional schedulers to
        schedule periodic tasks.

        The `Scheduler` class primarily exists to wrap the
        functionality of the generic
        :py:class:`~common.sched_async.SchedAsync` base class and
        register as a core service.  See the public members of that
        class for more detail on the scheduling interface.
        
    """
    def __init__(self, core_services):
        # TODO: should we parameterize the service name?
        self.__core = core_services
        self.__core.set_service("scheduler", self)
        SchedAsync.__init__(self, name="scheduler", core=core_services)

        self.start()

# internal functions & classes

