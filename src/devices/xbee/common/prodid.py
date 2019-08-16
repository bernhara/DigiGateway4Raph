############################################################################
#                                                                          #
# Copyright (c)2008-2011, Digi International (Digi). All Rights Reserved.  #
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
    Product Identification for Digi Wireless devices.

    This file declares the Digi Device types and related functions to
    identify various Digi Wireless devices.

    Digi Device Type Introduction (DD):
        A Digi Device Type field is being supported to indicate what product
        a given wireless device is operating on.

        The Digi Device Type field is a 4 byte value.
        The top 2 bytes specify the wireless module type.
        The lower 2 bytes specify the end product type.
"""

# imports
import struct

# globals

# Module Types
MOD_UNSPECIFIED        = 0x0000
MOD_XB_802154          = 0x0001
MOD_XB_ZNET25          = 0x0002
MOD_XB_ZB              = 0x0003
MOD_XB_DIGIMESH900     = 0x0004
MOD_XB_DIGIMESH24      = 0x0005
MOD_XB_868             = 0x0006
MOD_XB_DP900           = 0x0007
MOD_XTEND_DM900        = 0x0008
MOD_XB_80211           = 0x0009
MOD_XB_S2C_ZB          = 0x000A
MOD_XB_S3C_DIGIMESH900 = 0x000B
MOD_XB_868_DIGIMESH    = 0x000C

MOD_NAME_MAP = {
    MOD_UNSPECIFIED: "Unspecified",
    MOD_XB_802154: "XBee 802.15.4",
    MOD_XB_ZNET25: "XBee ZNet 2.5",
    MOD_XB_ZB: "XBee ZB",
    MOD_XB_DIGIMESH900: "XBee DigiMesh 900 MHz",
    MOD_XB_DIGIMESH24: "XBee DigiMesh 2.4 GHz",
    MOD_XB_868: "XBee 868 MHz",
    MOD_XB_DP900: "XBee DP 900",
    MOD_XTEND_DM900: "XTend DigiMesh 900 MHz",
    MOD_XB_80211: "XBee 802.11",
    MOD_XB_S2C_ZB: "XBee ZB on S2C",
    MOD_XB_S3C_DIGIMESH900: "XBee DigiMesh 900 MHz on S3B",
    MOD_XB_868_DIGIMESH: "XBee DigiMesh 868 MHz",
}

# Convenient module declarations:
# Modules with explicit receive frames (and endpoint support with
# separate applications running on endpoints 0xe8 and 0xe6).
MOD_XBS_WITH_EXPLICIT_RX = (MOD_XB_ZNET25, MOD_XB_ZB,
                             MOD_XB_DIGIMESH900, MOD_XB_DIGIMESH24)
# Modules without explicit receive frames:
MOD_XBS_NO_EXPLICIT_RX = (MOD_XB_802154, MOD_XB_868)

# Product Types

# Digi-Branded Products:
PROD_DIGI_UNSPECIFIED           = 0x0000
PROD_DIGI_CPX8                  = 0x0001
PROD_DIGI_CPX4                  = 0x0002
PROD_DIGI_CPX2                  = 0x0003
PROD_DIGI_COMMISSIONING_TOOL    = 0x0004
PROD_DIGI_XB_ADAPTER_RS232      = 0x0005
PROD_DIGI_XB_ADAPTER_RS485      = 0x0006
PROD_DIGI_XB_ADAPTER_SENSOR     = 0x0007
PROD_DIGI_XB_WALL_ROUTER        = 0x0008
PROD_DIGI_XB_RS232_PH           = 0x0009
PROD_DIGI_XB_ADAPTER_DIO        = 0x000a
PROD_DIGI_XB_ADAPTER_AIO        = 0x000b
PROD_DIGI_XSTICK                = 0x000c
PROD_DIGI_XB_SENSOR_LTH         = 0x000d
PROD_DIGI_XB_SENSOR_LT          = 0x000e
PROD_DIGI_XB_RPM_SMARTPLUG      = 0x000f
PROD_DIGI_XB_USB_DONGLE         = 0x0010
PROD_DIGI_XB_DISPLAY            = 0x0011
PROD_DIGI_CPX5                  = 0x0013
PROD_DIGI_EMBEDDED_GW           = 0x0014
PROD_DIGI_CPX3                  = 0x0015
PROD_NET_OS_DEVICE              = 0x0016
PROD_DIGI_XG3_GATEWAY           = 0x0017
PROD_DIGI_LTS_GATEWAY           = 0x0018
PROD_DIGI_CC3G_GATEWAY          = 0x0019
PROD_DIGI_X2_ULC_GATEWAY        = 0x001A

# Rabbit-Branded Products (0x0100 - 0x01FF):
PROD_RABBIT_GENERIC             = 0x0100
PROD_RABBIT_RCM4510W            = 0x0101
PROD_RABBIT_BL4S1XX             = 0x0102
PROD_RABBIT_BL4S230             = 0x0103
PROD_RABBIT_CUSTOMER_USE_RANGE  = (0x01f0, 0x01ff)

# Vendor Products (0x200-0x2FF):
# Massa
PROD_MASSA_M3                   = 0x0201
# B&B Electronics
PROD_BB_ELECTRONICS_LDVDS_XB    = 0x0210
#SSI Embedded Systems Programming
PROD_SSI_EM_SYS_PSU_SENSOR_M    = 0x0220
PROD_SSI_EM_SYS_PSU_SENSOR_O    = 0x0221
# Point Six Wireless
PROD_POINT6_TEMPERATURE         = 0x0231
PROD_DD0231_TEMPERATURE         = 0x0231
# Bejouled Solar Inverters  0x02b0 - 0x02bf
PROD_BEJOULED_SOLAR_INVERTER    = 0x02b0
# Southwest Windpower 0x02c0 - 0x02cF
PROD_WINDPOWER_TEST_RADIO       = 0x02c0

# Robust DataComm Pte Ltd
PROD_ROBUSTMESH                 = 0x02D0
PROD_ROBUSTMESH_232             = 0x02D1
PROD_ROBUSTMESH_485             = 0x02D2

# GE Energy / Sensors
PROD_GE_TEST_DEVICE             = 0x02E0
PROD_GE_VENTOSTAT               = 0x02E1

# Customer Private Use
PROD_CUSTOMER_USE_RANGE         = (0xff00, 0xffff)

PROD_NAME_MAP = {

    # Digi-Branded Products:
    PROD_DIGI_UNSPECIFIED: "Unspecified",
    PROD_DIGI_CPX8: "Digi ConnectPort X8",
    PROD_DIGI_CPX4: "Digi ConnectPort X4",
    PROD_DIGI_CPX2: "Digi ConnectPort X2",
    PROD_DIGI_COMMISSIONING_TOOL: "Digi Commissioning Tool",
    PROD_DIGI_XB_ADAPTER_RS232: "Digi XBee RS-232 Adapter",
    PROD_DIGI_XB_ADAPTER_RS485: "Digi XBee RS-485 Adapter",
    PROD_DIGI_XB_ADAPTER_SENSOR: "Digi XBee Sensor (1-wire) Adapter",
    PROD_DIGI_XB_WALL_ROUTER: "Digi XBee Wall Router",
    PROD_DIGI_XB_RS232_PH: "Digi RS-232 Power Harvester Adapter",
    PROD_DIGI_XB_ADAPTER_DIO: "Digi XBee Digital I/O Adapter",
    PROD_DIGI_XB_ADAPTER_AIO: "Digi XBee Analog I/O Adapter",
    PROD_DIGI_XSTICK: "Digi XStick",
    PROD_DIGI_XB_SENSOR_LTH: "Digi XBee Sensor /L/T/H",
    PROD_DIGI_XB_SENSOR_LT: "Digi XBee Sensor /L/T",
    PROD_DIGI_XB_RPM_SMARTPLUG: "Digi XBee RPM SmartPlug",
    PROD_DIGI_XB_USB_DONGLE: "Digi XBee USB Dongle",
    PROD_DIGI_XB_DISPLAY: "Digi XBee Display",
    PROD_DIGI_CPX5: "Digi ConnectPort X5",
    PROD_DIGI_EMBEDDED_GW: "Digi Embedded Gateway",
    PROD_DIGI_CPX3: "Digi ConnectPort X3",
    PROD_NET_OS_DEVICE: "NET+OS Device",
    PROD_DIGI_XG3_GATEWAY: "Digi XG3 Gateway",
    PROD_DIGI_LTS_GATEWAY: "Digi LTS Gateway",
    PROD_DIGI_CC3G_GATEWAY: "Digi CC3G Gateway",
    PROD_DIGI_X2_ULC_GATEWAY: "Digi X2 ULC Gateway",

    # Rabbit-Branded Products:
    PROD_RABBIT_GENERIC: "Generic Rabbit-Branded Product",
    PROD_RABBIT_RCM4510W: "Rabbit RCM4510W",
    PROD_RABBIT_BL4S1XX: "Rabbit BL4S1xx",
    PROD_RABBIT_BL4S230: "Rabbit BL4S230",

    # Vendor Products:
    PROD_MASSA_M3: "Massa M3",
    PROD_BB_ELECTRONICS_LDVDS_XB: "B&B Electronics LDVDS-XB",
    PROD_SSI_EM_SYS_PSU_SENSOR_M: "SSI Embedded Systems Programming - PSU Sensor M",
    PROD_SSI_EM_SYS_PSU_SENSOR_O: "SSI Embedded Systems Programming - PSU Sensor O",
    PROD_DD0231_TEMPERATURE     : "Wireless Temperature Device",
    PROD_BEJOULED_SOLAR_INVERTER: "Bejouled Solar Inverters",
    PROD_WINDPOWER_TEST_RADIO   : "Southwest Windpower",
    PROD_ROBUSTMESH     : "RobustMesh",
    PROD_ROBUSTMESH_232 : "RobustMesh 232",
    PROD_ROBUSTMESH_485 : "RobustMesh 485",
    PROD_GE_TEST_DEVICE : "GE Test Device",
    PROD_GE_VENTOSTAT : "GE Ventostat",
}

# Firmware version constants:
FW_FUNCSET_XB_ZB_COORD_AT       = 0x20
FW_FUNCSET_XB_ZB_COORD_API      = 0x21
FW_FUNCSET_XB_ZB_ROUTER_AT      = 0x22
FW_FUNCSET_XB_ZB_ROUTER_API     = 0x23
FW_FUNCSET_XB_ZB_ADAPTER_SENSOR = 0x24
FW_FUNCSET_XB_ZB_END_DEVICE_PH  = 0x25
FW_FUNCSET_XB_ZB_ADAPTER_AIO    = 0x26
FW_FUNCSET_XB_ZB_END_DEVICE_AT  = 0x28
FW_FUNCSET_XB_ZB_ADAPTER_DIO    = 0x27
FW_FUNCSET_XB_ZB_END_DEVICE_API = 0x29

# interface functions

def parse_dd(dd):
    """\
        Parse a Digi Device type value.

        Parses a given Digi Device type value gotten from a DDO DD command,
        into a tuple of (module_id, product_id).
        The top 2 bytes specify the wireless module type.
        The lower 2 bytes specify the end product type.

    """

    if isinstance(dd, str):
        try:
            # pad to four
            ln = len(dd)
            if ln > 4:
                raise ValueError("Value too long!")
            dd = '\x00' * (4 - ln) + dd
            dd = struct.unpack(">I", dd)[0]
        except:
            from core.tracing import get_tracer
            _tracer = get_tracer('prodid')
            _tracer.warning("Unable to determine device type, dd = \'" + \
                        dd + "\'. Check Xbee firmware.")
            dd = 0x00 # unspecified device/product

    if not isinstance(dd, (int, long)):
        raise TypeError("dd must be given as a string or int (given %s)" %
                        (str(type(dd))))

    module_id = dd >> 16
    product_id = dd & 0xffff

    return (module_id, product_id)

def format_dd(module_id, product_id):
    """\
        Construct a DD payload suitable for sending via ddo_set_param from given
        module_id and product_id integers.

    """

    return struct.pack(">HH", module_id, product_id)


def module_name(module_id):
    """\
        Returns a string for a given module id.

    """

    if module_id in MOD_NAME_MAP:
        return MOD_NAME_MAP[module_id]

    return "Unknown Module ID"


def product_name(product_id):
    """\
        Returns a string for a given product id.

    """

    if product_id in PROD_NAME_MAP:
        return PROD_NAME_MAP[product_id]
    elif product_id in PROD_RABBIT_CUSTOMER_USE_RANGE or \
         product_id in PROD_CUSTOMER_USE_RANGE:
        return "Private Customer Product ID"

    return "Unknown Product ID"


def parse_vr(vr):
    """
    Parse a given version value gotten from a DDO VR command,
    into a tuple of (fw_funcset, fw_version).
    """

    if isinstance(vr, str):
        vr = struct.unpack(">H", vr)[0]

    if not isinstance(vr, (int, long)):
        raise TypeError("vr must be given as a string or int (given %s" % \
            (str(type(vr))))

    fw_funcset = vr >> 8
    fw_version = vr & 0xff

    return (fw_funcset, fw_version)
