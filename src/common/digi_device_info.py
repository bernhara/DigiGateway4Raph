#!/usr/bin/python

############################################################################
#                                                                          #
# Copyright (c)2008-2012 Digi International (Digi). All Rights Reserved.   #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,	and the following  #
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

# imports
import sys
import digitime
from digi_ElementTree import ElementTree
from core.tracing import get_tracer

# optional imports
try:
    try:
        from rci import process_request as process_rci_request
    # old-style x2e support
    except ImportError:
        from rci_nonblocking import process_request as process_rci_request
except:
    pass

# local variables
_tracer = get_tracer("digi_device_info")


def rci_available():
    """\
    Returns True or False if RCI is available on this device.
    """
    return ('process_rci_request' in globals())


def simple_rci_query(query_string):
    """\
    Perform an RCI query and return raw RCI response.

    This query uses only socket operations to POST the HTTP request,
    it does not rely on any other external libraries.
    """

    return process_rci_request(query_string)


def _query_state_rci(state):
    """\
    Parse an RCI response via ElementTree.

    Present limitations:

        o Only returns tags in the first level below "state".

        o Appends any tag attributes to the tag name, but the order may
            change since ElementTree sorts them.  Best to use only one
            attribute per tag.
    """

    query_string = """\
<rci_request version="1.1">
    <query_state>
        <%s/>
    </query_state>
</rci_request>""" % state

    state_tree = ElementTree().parsestring("<" + state + " />")

    state_xml = simple_rci_query(query_string)
    tree = ElementTree().parsestring(state_xml)
    root_list = tree.findall(state_tree.tag)
    return root_list


def query_state(state):
    ''' return query_state if rci is available, otherwise return None '''
    if rci_available():
        return _query_state_rci(state)

    return None


def get_platform_name():
    """\
        Returns the name of the underlying platform
    """
    return sys.platform


def get_firmware_version():
    """\
Returns a tuple of the Device firmware version using RCI.

The tuple is an n-tuple of the form (p, q, r, ..) where the original
version string was p.q.r..

For example the version string "2.8.1" will return (2, 8, 1).

This call is often required to determine future system behavior,
therefore it will retry until it completes successfully.
"""

    i = 3

    while i > 0:
        try:
            device_info = query_state("device_info")
            i = -1
        except Exception, e:
            i -= 1
            _tracer.error("get_firmware_version(): WARNING, query_state() failed: %s",
                str(e))
            digitime.sleep(1)
        if i == 0:
            _tracer.critical("get_firmware_version(): fatal exception caught!  Halting execution.")

    for item in device_info:
        firmwaresoftrevstr = item.find('firmwaresoftrevstr')
        if firmwaresoftrevstr != None:
            firmwaresoftrevstr = firmwaresoftrevstr.text
            break
    else:
        firmwaresoftrevstr = ""

    fw_version = firmwaresoftrevstr.split('.')
    fw_version = map(lambda d: int(d), fw_version)

    return tuple(fw_version)


def device_firmware_gte_to(version_tuple):
    """\
Returns Boolean value if firmware version is greater than the version
supplied within version_tuple.
    """

    device_version = get_firmware_version()

    return device_version >= version_tuple


def get_device_id():
    """\
        Retrieves the Device ID from the Digi device.
    """
    value = ""
    query_base = '<rci_request version="1.1"><%s><%s/>' \
                 '</%s></rci_request>'
    try:
        query = query_base % ('query_setting', 'mgmtglobal', 'query_setting')
        raw_data = process_rci_request(query)
        setting_tree = ElementTree().parsestring(raw_data)
        device_id = setting_tree.find('deviceId')
        value = device_id.text
    except AttributeError:
        # PLATFORM: this might be an x2e
        query = query_base % ('query_state', 'device_info', 'query_state')
        raw_data = process_rci_request(query)
        setting_tree = ElementTree().parsestring(raw_data)
        device_id = setting_tree.find('deviceid')
        value = device_id.text

        # normalize to the old NDS format
        if not value.startswith('0x'):
            value = ''.join(('0x', value))
        value = value.replace('-', '')
    except:
        _tracer.error("get_device_id(): Unable to retrieve Device ID")
        raise

    return value

def get_ethernet_mac_string():
    """\
        Returns the Ethernet MAC address as a string, using RCI 'device_info'
        
        Example: "00:40:9D:6A:72:F6"
    """
   
    if sys.platform == 'digiconnect':
        # in Connect/ConnectPort, looking for:
        # <device_info>
        #    <mac>00:40:9d:52:1d:6e</mac>
        # </device_info>
        info = query_state("device_info")
        for item in info:
            mac = item.find('mac')
            if mac != None:
                return mac.text
                
    elif sys.platform == 'linux2':
        # in X2e ZB/3G, looking for
        # <interface_info name="eth0">
        #    <mac>00:40:9d:52:1d:6e</mac>
        # </interface_info>
        
        response = process_rci_request(
            '<rci_request version="1.1"><query_state /></rci_request>')
        
        # there may be a cleaner method, but we have multiple possible nodes
        # like <interface_info name="eth0"> and <interface_info name="wlan0">
        # I couldn't find a cleaner way to find <interface_info name="eth0"> if
        # it is NOT the first interface_info
        root = ElementTree().parsestring(response)
        inf_list = root.findall('interface_info')
        
        interface_node = None
        for node in inf_list:
            if interface_node is None:
                # save the very first 'interface_info' we find, but keep going
                interface_node = node
                
            if node.attrib['name'] in ('eth0'):
                # break and use this one
                interface_node = node
                break

        # this will return string like '00:40:9d:5c:1b:05" or None
        if interface_node is not None:
            return interface_node.findtext('mac')
            
    return None

def get_ethernet_mac_long():
    """\
        Returns the Ethernet MAC address as a long int, using RCI 'device_info'
        
        Example: 0x409D6A72F6 (from string '00:40:9D:6A:72:F6')
    """

    mac = get_ethernet_mac_string()
    if mac != None and len(mac) >= 17:
        mac = '0x' + mac[0:2] + mac[3:5] + mac[6:8] + \
                     mac[9:11] + mac[12:14] + mac[15:17]
        return long(mac, 16)
    return None
    