############################################################################
#                                                                          #
# Copyright (c)2012 Digi International (Digi). All Rights Reserved.        #
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
File system utils.

Provides

total_blocks()

blocks_remaining()

total_bytes()

bytes_remaining()

percent_remaining()

for reasoning about file system usage.

Note: These functions only work on the directory (or partition) that
the DIA is running on. For devices (like the x2 and x2e), it does the
*right thing*. For a linux or windows box, it returns the amount remaining
for the partition that the DIA is executing on.
'''

import os
from common.path_utils import get_base_dir


def total_blocks():
    '''
    Return the total number of blocks remaining.
    '''
    return os.statvfs(get_base_dir()).f_blocks


def blocks_remaining():
    '''
    Return the total number of blocks available.
    '''
    return os.statvfs(get_base_dir()).f_bavail


def total_bytes():
    '''
    Return the size of the file system in bytes.
    '''
    stats = os.statvfs(get_base_dir())
    return stats.f_frsize * stats.f_blocks


def bytes_remaining():
    '''
    Return the number of bytes available on the system.
    '''
    stats = os.statvfs(get_base_dir())
    return stats.f_frsize * stats.f_bavail


def percent_remaining():
    '''
    Return the percent (as a number between 0 and 1)
    available for writing on the file system.
    '''
    stats = os.statvfs(get_base_dir())
    return 1.0 * stats.f_bavail / stats.f_blocks


def percent_used():
    '''
    Return the percent (as a number between 0 and 1)
    of the blocks currently used.
    '''
    return 1.0 - percent_remaining()
