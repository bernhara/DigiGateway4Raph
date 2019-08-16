############################################################################
#                                                                          #
# Copyright (c)2010, Digi International (Digi). All Rights Reserved.       #
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
    -------------------------------------------------------------------------
    |             XBee Series 2 - Analog and Digital IO Lines               |
    -------------------------------------------------------------------------
    | Pin Command Parameter | Description                                   |
    -------------------------------------------------------------------------
    | 0                     | Unmonitored digital input                     |
    | 1                     | Reserved for pin-specific alternate functions |
    | 2                     | Analog input, single ended (A/D pins only)    |
    | 3                     | Digital input, monitored                      |
    | 4                     | Digital output, default low                   |
    | 5                     | Digital output, default high                  |
    | 6 - 9                 | Alternate functionalities, where applicable   |
    -------------------------------------------------------------------------
"""
XBEE_SERIES2_UNMONITORED_MODE         = 0
XBEE_SERIES2_RESERVED1_MODE           = 1
XBEE_SERIES2_AIO_MODE                 = 2
XBEE_SERIES2_DIGITAL_INPUT_MODE       = 3
XBEE_SERIES2_DIGITAL_OUTPUT_LOW_MODE  = 4
XBEE_SERIES2_DIGITAL_OUTPUT_HIGH_MODE = 5
XBEE_SERIES2_RESERVED6_MODE           = 6
XBEE_SERIES2_RESERVED7_MODE           = 7
XBEE_SERIES2_RESERVED8_MODE           = 8
XBEE_SERIES2_RESERVED9_MODE           = 9


"""\
    nds and X3 constants for configuring a channel:
    (ie, the digihw.configure_channel() call)

    'mode' is 1 for analog 0-20 ma current loop
    'mode' is 2 for analog 0-10 VDC voltage sensor
    'mode' is 3 for digital input or high output
    'mode' is 4 for digital low output
"""
AIO_HW_MODE_CURRENTLOOP = 1
AIO_HW_MODE_TENV        = 2
DIO_HW_MODE_INPUT       = 3
DIO_HW_MODE_OUTPUT_HIGH = 3
DIO_HW_MODE_OUTPUT_LOW  = 4

