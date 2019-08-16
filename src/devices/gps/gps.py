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


#NMEA-0183 based GPS stream device driver.
#
#   Settings:
#
#   serial_device: The device that will be used. (default value: "/gps/0").
#
#   serial_baud: The baud rate that should be used when attempting to talk
#   with the GPS device.  (default value: 115200).  NOTE:  Due to differences in
#   hardware implementation, this value is ignored when the DIA is used on an
#   ConnectPort X3 based platform.
#
#   sample_rate_sec: The rate, in seconds, in which the GPS should be queried
#   and have the resulting data be parsed.  (default value: 60)  NOTE:  Due to
#   hardware limitations, it is HIGHLY recommended keeping this value at or above
#   60 seconds on an ConnectPort X3 based platform.  On non-ConnectPort X3 based
#   platforms, this setting is ignored, and the GPS is instead polled
#   once a second.

# imports
import threading
import digitime
import serial
import nmea
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.types.boolean import Boolean
from common.digi_device_info import get_platform_name
from common.shutdown import SHUTDOWN_WAIT

from pprint import pprint

# constants

# exception classes

# interface functions

# classes

class GPS(DeviceBase, threading.Thread):
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

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='serial_device', type=str, required=False, 
                default_value="/gps/0"),
            Setting(
                name='serial_baud', type=int, required=False, default_value=4800,
                  verify_function=lambda x: x > 0.0),
            Setting(
                name='sample_rate_sec', type=int, required=False, default_value=60,
                  verify_function=lambda x: x > 0.0),
        ]

        ## Channel Properties Definition:

        # Feel free to create a channel here for any item that the
        # nmea module can extract from a valid sentence.  The
        # property_setter routine will populate correctly.  You may
        # need to extend the sentence templates in nmea.py to teach
        # the library about non position based sentences and types.
        property_list = [
            # gettable properties
           
            ChannelSourceDeviceProperty(name="fix_time", type=str,
                initial=Sample(timestamp=0, value=""),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="fix_good", type=Boolean,
                initial=Sample(timestamp=0, value=Boolean(False)),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            
            ChannelSourceDeviceProperty(name="latitude_degrees", type=float,
                initial=Sample(timestamp=0, value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            
            ChannelSourceDeviceProperty(name="latitude_hemisphere", type=str,
                initial=Sample(timestamp=0, value=""),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            
            ChannelSourceDeviceProperty(name="longitude_degrees", type=float,
                initial=Sample(timestamp=0, value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            
            ChannelSourceDeviceProperty(name="longitude_hemisphere", type=str,
                initial=Sample(timestamp=0, value=""),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            
            ChannelSourceDeviceProperty(name="speed_over_ground", type=float,
                initial=Sample(timestamp=0, value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            
            ChannelSourceDeviceProperty(name="course_over_ground", type=float,
                initial=Sample(timestamp=0, value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            
            ChannelSourceDeviceProperty(name="fix_date", type=str,
                initial=Sample(timestamp=0, value=""),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        
            ChannelSourceDeviceProperty(name="num_satellites", type=int,
                initial=Sample(timestamp=0, value=0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="altitude", type=float,
                initial=Sample(timestamp=0, value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
             
            ChannelSourceDeviceProperty(name="hdop", type=float,
                initial=Sample(timestamp=0, value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]
                                            
        ## Initialize the Devicebase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)


    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def start(self):

        threading.Thread.start(self)

        return True

    def stop(self):

        if get_platform_name() == 'digix3':
            self.__tracer.info("May take up to %02f seconds", 
                            SettingsBase.get_setting(self, "sample_rate_sec"))
        
        self.__stopevent.set()
        return True
        

    ## Locally defined functions:
    # Property callback functions:

    # Threading related functions:
    def run(self):
       
        serial_device = SettingsBase.get_setting(self, "serial_device")
        baud_rate = SettingsBase.get_setting(self, "serial_baud")

        # The way we read the NMEA-0183 data stream is different between
        # the nds-based products and the X3 products.
        #
        # The nds-based product has the data stream coming in over
        # a serial port, so we need to be able to set the baud rate.
        #
        # The X3-based product has the data stream coming in over I2C,
        # which does not require setting any sort of baud rate.
        # Also, the X3 platform is slower than the nds based platforms,
        # so we offer a way to delay reading the stream, so that parsing
        # the stream doesn't monopolize the cpu.

        if get_platform_name() == 'digix3':
            sample_rate_sec = SettingsBase.get_setting(self, "sample_rate_sec")
        else:
            sample_rate_sec = 0

        _serial = serial.Serial(port=serial_device,
                                baudrate=baud_rate,
                                timeout=SHUTDOWN_WAIT)

        nmea_obj = nmea.NMEA()
        
        while 1:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                _serial.close()
                break

            # 16384 is a MAGIC NUMBER that came into existence
            # before my time...  my (extremely limited) testing
            # has shown that this number makes for clean cut-offs
            # in talker strings (as defined by the NMEA 0183
            # Protocol definition (v3))
            #
            # In other words, you always get the full last line
            # up to and including the line-terminating '\r\n'.
            #
            # This makes the nmea parser joyful.

            # this returns '' on a timeout
            data = _serial.read(size=16384)
            
            # Read in the NMEA-0183 stream data, and parse it
            if data and len(data) > 0:
                
                self.__tracer.debug(data)
                nmea_obj.feed(data, self.property_setter)

                digitime.sleep(sample_rate_sec)
            

    def property_setter(self, prop, val):

        if self.property_exists(prop):
            if prop in nmea.units:
                unit = nmea.units[prop]
            else:
                unit = ""

            self.property_set(prop, Sample(0, val, unit))
            
