############################################################################
#                                                                          #
# Copyright (c)2008-2013, Digi International (Digi). All Rights Reserved.  #
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
Trap Commissioning Button presses
"""

# imports
import struct
import digitime

from devices.device_base import DeviceBase
from devices.xbee.common.addressing import binstr_to_address
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *

# constants

# exception classes

# interface functions

# classes
class XBeeTrapCB(DeviceBase):
    """\
        This class extends one of our base classes and is intended as an
        example of a concrete, example implementation, but it is not itself
        meant to be included as part of our developer API. Please consult the
        base class documentation for the API and the source code for this file
        for an example implementation.

    """

    def __init__(self, name, core_services):
        # DeviceBase will create:
        # self._name, self._core, self._tracer, 

        # Settings
        #
        # xbee_device_manager: must be set to the name of an XBeeDeviceManager
        #                      instance.

        settings_list = [
            Setting(
                name='xbee_device_manager', type=str, required=True),
            ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="button", type=str,
                initial=Sample(timestamp=0, value=''),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="cb_trigger", type=bool,
                initial=Sample(timestamp=0, value=False),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self,  name, core_services,
                                settings_list, property_list)

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    # use DeviceBase.apply_settings()
    
    def start(self):

        # init self._xbee_manager and self._extended_address
        # register ourself with our Xbee manager
        # create the self.running_indication callback
        XBeeBase.pre_start(self)

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec.cb_set(self.button_press)
        xbdm_rx_event_spec.match_spec_set(
            (None, 0xe8, 0xc105, 0x95),
            (False, True, True, True))
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                xbdm_rx_event_spec)

        # we've no more to config, indicate we're ready to configure.
        return XBeeBase.start(self)

    # use XBeeBase.stop()

    ## Locally defined functions:

    def button_press(self, buf, addr):

        now = digitime.time()

        self._tracer.info('Commissioning Button from %s at %s', addr[0],
            digitime.strftime("%Y-%m-%d %H:%M:%S", digitime.localtime(now)) )

        dct = parse_node_identification(buf)

        if dct is not None:
            x = dct['event']
            if x == 'pushbutton':
                msg = 'CB ' + dct['addr64']
                if self.property_get("cb_trigger").value == True:
                    self.property_set("cb_trigger", Sample(now, False))
                self.property_set("cb_trigger", Sample(now, True))
                self.property_set("cb_trigger", Sample(now, False))
            elif x == 'join':
                msg = 'JN ' + dct['addr64']
            elif x == 'power_cycle':
                msg = 'PWR ' + dct['addr64']
            else:
                self._tracer.warning('Unknown Source Event:0x%02X', x)
                return None

            if dct.has_key('dev_dd'):
                # append the lower device DD value
                msg += ' DD:0x%04X' % dct['dev_dd']

            self.property_set("button", Sample(now, msg))
            self._tracer.debug('channel=\"%s\"', msg)

        return

# internal functions & classes
def parse_node_identification(buf):

    if len(buf) < 12:
        return None

    dct = { 'addr16':struct.unpack('H', buf[:2])[0],
            'addr64':binstr_to_address(buf[2:10]) }

    if (buf[10] == ' ') and (buf[11] == '\x00'):
        # special case - default name is ' '
        buf = buf[12:]

    elif (buf[10] == '\x00'):
        # special case - name is null
        buf = buf[11:]

    else:
        n = buf.find('\x00', 10)
        if n >= 0:
            dct.update({'ni':buf[10:n]})
        else:
            n = 9
        buf = buf[n+1:]

    if len(buf) >= 8:

        if (buf[0] != '\xFF') and (buf[1] != '\xFE'):
            dct.update({'parent':struct.unpack('>H', buf[:2])[0]})

        x = ord(buf[2])
        if x == 0x00:
            x = 'coordinator'
        elif x == 0x01:
            x = 'router'
        elif x == 0x02:
            x = 'end_device'
        else:
            x = '0x%02X' % x
        dct.update({'type':x})

        x = ord(buf[3])
        if x == 0x01:
            x = 'pushbutton'
        elif x == 0x02:
            x = 'join'
        elif x == 0x03:
            x = 'power_cycle'
        elif x == 0x41: # from DM?
            x = 'pushbutton'
        else:
            x = '0x%02X' % x
        dct.update({'event':x})

        x,y = struct.unpack('>HH', buf[4:8])
        dct.update({'profile':x, 'manuf':y})

        if len(buf) >= 12:
            # then DD value is attached
            x,y = struct.unpack('>HH', buf[8:12])
            dct.update({'xbee_dd':x, 'dev_dd':y})

    return dct

