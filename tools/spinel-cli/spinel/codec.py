#!/usr/bin/python
#
#  Copyright (c) 2016, The OpenThread Authors.
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#  1. Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#  2. Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#  3. Neither the name of the copyright holder nor the
#     names of its contributors may be used to endorse or promote products
#     derived from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
#  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
#  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
#  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
#  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
#  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
#  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
#  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
#  POSSIBILITY OF SUCH DAMAGE.
#

FEATURE_USE_HDLC = 1
FEATURE_USE_SLACC = 1

TIMEOUT_PROP = 2

import os
import sys
import time
import string
import logging
import threading
import traceback

import textwrap
import ipaddress
import binascii

import Queue

from copy import copy
from struct import pack
from struct import unpack
from collections import namedtuple
from collections import defaultdict

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
from scapy.layers.inet6 import IPv6
from scapy.layers.inet6 import ICMPv6EchoRequest
from scapy.layers.inet6 import ICMPv6EchoReply

import spinel.util as util
import spinel.config as CONFIG
from spinel.hdlc import Hdlc

#=========================================
#   Spinel
#=========================================

SPINEL_RSSI_OVERRIDE            = 127

SPINEL_HEADER_ASYNC             = 0x80
SPINEL_HEADER_DEFAULT           = 0x81
SPINEL_HEADER_EVENT_HANDLER     = 0x82

# Spinel Commands

SPINEL_CMD_NOOP                 = 0
SPINEL_CMD_RESET                = 1
SPINEL_CMD_PROP_VALUE_GET       = 2
SPINEL_CMD_PROP_VALUE_SET       = 3
SPINEL_CMD_PROP_VALUE_INSERT    = 4
SPINEL_CMD_PROP_VALUE_REMOVE    = 5

SPINEL_RSP_PROP_VALUE_IS        = 6
SPINEL_RSP_PROP_VALUE_INSERTED  = 7
SPINEL_RSP_PROP_VALUE_REMOVED   = 8

SPINEL_CMD_NET_SAVE             = 9
SPINEL_CMD_NET_CLEAR            = 10
SPINEL_CMD_NET_RECALL           = 11

SPINEL_RSP_HBO_OFFLOAD          = 12
SPINEL_RSP_HBO_RECLAIM          = 13
SPINEL_RSP_HBO_DROP             = 14

SPINEL_CMD_HBO_OFFLOADED        = 15
SPINEL_CMD_HBO_RECLAIMED        = 16
SPINEL_CMD_HBO_DROPPED          = 17

SPINEL_CMD_NEST__BEGIN          = 15296
SPINEL_CMD_NEST__END            = 15360

SPINEL_CMD_VENDOR__BEGIN        = 15360
SPINEL_CMD_VENDOR__END          = 16384

SPINEL_CMD_EXPERIMENTAL__BEGIN  = 2000000
SPINEL_CMD_EXPERIMENTAL__END    = 2097152

# Spinel Properties

SPINEL_PROP_LAST_STATUS             = 0        #< status [i]
SPINEL_PROP_PROTOCOL_VERSION        = 1        #< major, minor [i,i]
SPINEL_PROP_NCP_VERSION             = 2        #< version string [U]
SPINEL_PROP_INTERFACE_TYPE          = 3        #< [i]
SPINEL_PROP_VENDOR_ID               = 4        #< [i]
SPINEL_PROP_CAPS                    = 5        #< capability list [A(i)]
SPINEL_PROP_INTERFACE_COUNT         = 6        #< Interface count [C]
SPINEL_PROP_POWER_STATE             = 7        #< PowerState [C]
SPINEL_PROP_HWADDR                  = 8        #< PermEUI64 [E]
SPINEL_PROP_LOCK                    = 9        #< PropLock [b]
SPINEL_PROP_HBO_MEM_MAX             = 10       #< Max offload mem [S]
SPINEL_PROP_HBO_BLOCK_MAX           = 11       #< Max offload block [S]

SPINEL_PROP_PHY__BEGIN              = 0x20
SPINEL_PROP_PHY_ENABLED             = SPINEL_PROP_PHY__BEGIN + 0 #< [b]
SPINEL_PROP_PHY_CHAN                = SPINEL_PROP_PHY__BEGIN + 1 #< [C]
SPINEL_PROP_PHY_CHAN_SUPPORTED      = SPINEL_PROP_PHY__BEGIN + 2 #< [A(C)]
SPINEL_PROP_PHY_FREQ                = SPINEL_PROP_PHY__BEGIN + 3 #< kHz [L]
SPINEL_PROP_PHY_CCA_THRESHOLD       = SPINEL_PROP_PHY__BEGIN + 4 #< dBm [c]
SPINEL_PROP_PHY_TX_POWER            = SPINEL_PROP_PHY__BEGIN + 5 #< [c]
SPINEL_PROP_PHY_RSSI                = SPINEL_PROP_PHY__BEGIN + 6 #< dBm [c]
SPINEL_PROP_PHY__END                = 0x30

SPINEL_PROP_MAC__BEGIN             = 0x30
SPINEL_PROP_MAC_SCAN_STATE         = SPINEL_PROP_MAC__BEGIN + 0 #< [C]
SPINEL_PROP_MAC_SCAN_MASK          = SPINEL_PROP_MAC__BEGIN + 1 #< [A(C)]
SPINEL_PROP_MAC_SCAN_PERIOD        = SPINEL_PROP_MAC__BEGIN + 2 #< ms-per-channel [S]
SPINEL_PROP_MAC_SCAN_BEACON        = SPINEL_PROP_MAC__BEGIN + 3 #< chan,rssi,(laddr,saddr,panid,lqi),(proto,xtra) [CcT(ESSC.)T(i).]
SPINEL_PROP_MAC_15_4_LADDR         = SPINEL_PROP_MAC__BEGIN + 4 #< [E]
SPINEL_PROP_MAC_15_4_SADDR         = SPINEL_PROP_MAC__BEGIN + 5 #< [S]
SPINEL_PROP_MAC_15_4_PANID         = SPINEL_PROP_MAC__BEGIN + 6 #< [S]
SPINEL_PROP_MAC_RAW_STREAM_ENABLED = SPINEL_PROP_MAC__BEGIN + 7 #< [C]
SPINEL_PROP_MAC_FILTER_MODE        = SPINEL_PROP_MAC__BEGIN + 8 #< [C]
SPINEL_PROP_MAC__END               = 0x40

SPINEL_PROP_MAC_EXT__BEGIN         = 0x1300
# Format: `A(T(Ec))`
# * `E`: EUI64 address of node
# * `c`: Optional fixed RSSI. -127 means not set.
SPINEL_PROP_MAC_WHITELIST          = SPINEL_PROP_MAC_EXT__BEGIN + 0
SPINEL_PROP_MAC_WHITELIST_ENABLED  = SPINEL_PROP_MAC_EXT__BEGIN + 1  #< [b]
SPINEL_PROP_MAC_EXT__END           = 0x1400

SPINEL_PROP_NET__BEGIN           = 0x40
SPINEL_PROP_NET_SAVED            = SPINEL_PROP_NET__BEGIN + 0 #< [b]
SPINEL_PROP_NET_IF_UP            = SPINEL_PROP_NET__BEGIN + 1 #< [b]
SPINEL_PROP_NET_STACK_UP         = SPINEL_PROP_NET__BEGIN + 2 #< [C]
SPINEL_PROP_NET_ROLE             = SPINEL_PROP_NET__BEGIN + 3 #< [C]
SPINEL_PROP_NET_NETWORK_NAME     = SPINEL_PROP_NET__BEGIN + 4 #< [U]
SPINEL_PROP_NET_XPANID           = SPINEL_PROP_NET__BEGIN + 5 #< [D]
SPINEL_PROP_NET_MASTER_KEY       = SPINEL_PROP_NET__BEGIN + 6 #< [D]
SPINEL_PROP_NET_KEY_SEQUENCE     = SPINEL_PROP_NET__BEGIN + 7 #< [L]
SPINEL_PROP_NET_PARTITION_ID     = SPINEL_PROP_NET__BEGIN + 8 #< [L]
SPINEL_PROP_NET__END             = 0x50

SPINEL_PROP_THREAD__BEGIN          = 0x50
SPINEL_PROP_THREAD_LEADER_ADDR     = SPINEL_PROP_THREAD__BEGIN + 0 #< [6]
SPINEL_PROP_THREAD_PARENT          = SPINEL_PROP_THREAD__BEGIN + 1 #< LADDR, SADDR [ES]
SPINEL_PROP_THREAD_CHILD_TABLE     = SPINEL_PROP_THREAD__BEGIN + 2 #< [A(T(ES))]
SPINEL_PROP_THREAD_LEADER_RID      = SPINEL_PROP_THREAD__BEGIN + 3 #< [C]
SPINEL_PROP_THREAD_LEADER_WEIGHT   = SPINEL_PROP_THREAD__BEGIN + 4 #< [C]
SPINEL_PROP_THREAD_LOCAL_LEADER_WEIGHT = SPINEL_PROP_THREAD__BEGIN + 5 #< [C]
SPINEL_PROP_THREAD_NETWORK_DATA    = SPINEL_PROP_THREAD__BEGIN + 6 #< [D]
SPINEL_PROP_THREAD_NETWORK_DATA_VERSION = SPINEL_PROP_THREAD__BEGIN + 7 #< [S]
SPINEL_PROP_THREAD_STABLE_NETWORK_DATA  = SPINEL_PROP_THREAD__BEGIN + 8 #< [D]
SPINEL_PROP_THREAD_STABLE_NETWORK_DATA_VERSION = SPINEL_PROP_THREAD__BEGIN + 9  #< [S]
SPINEL_PROP_THREAD_ON_MESH_NETS    = SPINEL_PROP_THREAD__BEGIN + 10 #< array(ipv6prefix,prefixlen,stable,flags) [A(T(6CbC))]
SPINEL_PROP_THREAD_LOCAL_ROUTES    = SPINEL_PROP_THREAD__BEGIN + 11 #< array(ipv6prefix,prefixlen,stable,flags) [A(T(6CbC))]
SPINEL_PROP_THREAD_ASSISTING_PORTS = SPINEL_PROP_THREAD__BEGIN + 12 #< array(portn) [A(S)]
SPINEL_PROP_THREAD_ALLOW_LOCAL_NET_DATA_CHANGE = SPINEL_PROP_THREAD__BEGIN + 13 #< [b]
SPINEL_PROP_THREAD_MODE            = SPINEL_PROP_THREAD__BEGIN + 14
SPINEL_PROP_THREAD__END            = 0x60

SPINEL_PROP_THREAD_EXT__BEGIN      = 0x1500
SPINEL_PROP_THREAD_CHILD_TIMEOUT   = SPINEL_PROP_THREAD_EXT__BEGIN + 0  #< [L]
SPINEL_PROP_THREAD_RLOC16          = SPINEL_PROP_THREAD_EXT__BEGIN + 1  #< [S]
SPINEL_PROP_THREAD_ROUTER_UPGRADE_THRESHOLD = SPINEL_PROP_THREAD_EXT__BEGIN + 2 #< [C]
SPINEL_PROP_THREAD_CONTEXT_REUSE_DELAY = SPINEL_PROP_THREAD_EXT__BEGIN + 3 #< [L]
SPINEL_PROP_THREAD_NETWORK_ID_TIMEOUT =  SPINEL_PROP_THREAD_EXT__BEGIN + 4 #< [b]
SPINEL_PROP_THREAD_ACTIVE_ROUTER_IDS = SPINEL_PROP_THREAD_EXT__BEGIN + 5 #< [A(b)]
SPINEL_PROP_THREAD_RLOC16_DEBUG_PASSTHRU = SPINEL_PROP_THREAD_EXT__BEGIN + 6 #< [b]
SPINEL_PROP_THREAD_ROUTER_ROLE_ENABLED = SPINEL_PROP_THREAD_EXT__BEGIN + 7 #< [b]
SPINEL_PROP_THREAD_ROUTER_DOWNGRADE_THRESHOLD = SPINEL_PROP_THREAD_EXT__BEGIN + 8 #< [C]
SPINEL_PROP_THREAD_ROUTER_SELECTION_JITTER = SPINEL_PROP_THREAD_EXT__BEGIN + 9 #< [C]

SPINEL_PROP_THREAD_EXT__END        = 0x1600

SPINEL_PROP_MESHCOP_EXT__BEGIN      = 0x1600
SPINEL_PROP_MESHCOP_JOINER_ENABLE = SPINEL_PROP_MESHCOP_EXT__BEGIN + 0 #< [b]
SPINEL_PROP_MESHCOP_JOINER_CREDENTIAL = SPINEL_PROP_MESHCOP_EXT__BEGIN + 1 #< [D]
SPINEL_PROP_MESHCOP_JOINER_URL = SPINEL_PROP_MESHCOP_EXT__BEGIN + 2 #< [U]
SPINEL_PROP_MESHCOP_BORDER_AGENT_ENABLE = SPINEL_PROP_MESHCOP_EXT__BEGIN + 3 #< [b]
SPINEL_PROP_MESHCOP_EXT__END        = 0x1700


SPINEL_PROP_IPV6__BEGIN          = 0x60
SPINEL_PROP_IPV6_LL_ADDR         = SPINEL_PROP_IPV6__BEGIN + 0 #< [6]
SPINEL_PROP_IPV6_ML_ADDR         = SPINEL_PROP_IPV6__BEGIN + 1 #< [6C]
SPINEL_PROP_IPV6_ML_PREFIX       = SPINEL_PROP_IPV6__BEGIN + 2 #< [6C]
SPINEL_PROP_IPV6_ADDRESS_TABLE   = SPINEL_PROP_IPV6__BEGIN + 3 #< array(ipv6addr,prefixlen,valid,preferred,flags) [A(T(6CLLC))]
SPINEL_PROP_IPV6_ROUTE_TABLE     = SPINEL_PROP_IPV6__BEGIN + 4 #< array(ipv6prefix,prefixlen,iface,flags) [A(T(6CCC))]
SPINEL_PROP_IPv6_ICMP_PING_OFFLOAD = SPINEL_PROP_IPV6__BEGIN + 5 #< [b]

SPINEL_PROP_STREAM__BEGIN       = 0x70
SPINEL_PROP_STREAM_DEBUG        = SPINEL_PROP_STREAM__BEGIN + 0 #< [U]
SPINEL_PROP_STREAM_RAW          = SPINEL_PROP_STREAM__BEGIN + 1 #< [D]
SPINEL_PROP_STREAM_NET          = SPINEL_PROP_STREAM__BEGIN + 2 #< [D]
SPINEL_PROP_STREAM_NET_INSECURE = SPINEL_PROP_STREAM__BEGIN + 3 #< [D]
SPINEL_PROP_STREAM__END         = 0x80

# UART Bitrate
# Format: `L`
SPINEL_PROP_UART_BITRATE    = 0x100

# UART Software Flow Control
# Format: `b`
SPINEL_PROP_UART_XON_XOFF   = 0x101

SPINEL_PROP_15_4_PIB__BEGIN     = 1024
SPINEL_PROP_15_4_PIB_PHY_CHANNELS_SUPPORTED = SPINEL_PROP_15_4_PIB__BEGIN + 0x01 #< [A(L)]
SPINEL_PROP_15_4_PIB_MAC_PROMISCUOUS_MODE   = SPINEL_PROP_15_4_PIB__BEGIN + 0x51 #< [b]
SPINEL_PROP_15_4_PIB_MAC_SECURITY_ENABLED   = SPINEL_PROP_15_4_PIB__BEGIN + 0x5d #< [b]
SPINEL_PROP_15_4_PIB__END       = 1280

SPINEL_PROP_CNTR__BEGIN        = 1280

# Counter reset behavior
# Format: `C`
SPINEL_PROP_CNTR_RESET             = SPINEL_PROP_CNTR__BEGIN + 0

# The total number of transmissions.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_TX_PKT_TOTAL      = SPINEL_PROP_CNTR__BEGIN + 1

# The number of transmissions with ack request.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_TX_PKT_ACK_REQ    = SPINEL_PROP_CNTR__BEGIN + 2

# The number of transmissions that were acked.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_TX_PKT_ACKED      = SPINEL_PROP_CNTR__BEGIN + 3

# The number of transmissions without ack request.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_TX_PKT_NO_ACK_REQ = SPINEL_PROP_CNTR__BEGIN + 4

# The number of transmitted data.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_TX_PKT_DATA       = SPINEL_PROP_CNTR__BEGIN + 5

# The number of transmitted data poll.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_TX_PKT_DATA_POLL  = SPINEL_PROP_CNTR__BEGIN + 6

# The number of transmitted beacon.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_TX_PKT_BEACON     = SPINEL_PROP_CNTR__BEGIN + 7

# The number of transmitted beacon request.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_TX_PKT_BEACON_REQ = SPINEL_PROP_CNTR__BEGIN + 8

# The number of transmitted other types of frames.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_TX_PKT_OTHER      = SPINEL_PROP_CNTR__BEGIN + 9

# The number of retransmission times.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_TX_PKT_RETRY      = SPINEL_PROP_CNTR__BEGIN + 10

# The number of CCA failure times.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_TX_ERR_CCA        = SPINEL_PROP_CNTR__BEGIN + 11

# The total number of received packets.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_PKT_TOTAL      = SPINEL_PROP_CNTR__BEGIN + 100

# The number of received data.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_PKT_DATA       = SPINEL_PROP_CNTR__BEGIN + 101

# The number of received data poll.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_PKT_DATA_POLL  = SPINEL_PROP_CNTR__BEGIN + 102

# The number of received beacon.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_PKT_BEACON     = SPINEL_PROP_CNTR__BEGIN + 103

# The number of received beacon request.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_PKT_BEACON_REQ = SPINEL_PROP_CNTR__BEGIN + 104

# The number of received other types of frames.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_PKT_OTHER      = SPINEL_PROP_CNTR__BEGIN + 105

# The number of received packets filtered by whitelist.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_PKT_FILT_WL    = SPINEL_PROP_CNTR__BEGIN + 106

# The number of received packets filtered by destination check.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_PKT_FILT_DA    = SPINEL_PROP_CNTR__BEGIN + 107

# The number of received packets that are empty.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_ERR_EMPTY      = SPINEL_PROP_CNTR__BEGIN + 108

# The number of received packets from an unknown neighbor.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_ERR_UKWN_NBR   = SPINEL_PROP_CNTR__BEGIN + 109

# The number of received packets whose source address is invalid.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_ERR_NVLD_SADDR = SPINEL_PROP_CNTR__BEGIN + 110

# The number of received packets with a security error.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_ERR_SECURITY   = SPINEL_PROP_CNTR__BEGIN + 111

# The number of received packets with a checksum error.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_ERR_BAD_FCS    = SPINEL_PROP_CNTR__BEGIN + 112

# The number of received packets with other errors.
# Format: `L` (Read-only) */
SPINEL_PROP_CNTR_RX_ERR_OTHER      = SPINEL_PROP_CNTR__BEGIN + 113

#=========================================

SPINEL_LAST_STATUS_MAP = {
    0: "STATUS_OK: Operation has completed successfully.",
    1: "STATUS_FAILURE: Operation has failed for some undefined reason.",
    2: "STATUS_UNIMPLEMENTED: The given operation has not been implemented.",
    3: "STATUS_INVALID_ARGUMENT: An argument to the given operation is invalid.",
    4: "STATUS_INVALID_STATE : The given operation is invalid for the current state of the device.",
    5: "STATUS_INVALID_COMMAND: The given command is not recognized.",
    6: "STATUS_INVALID_INTERFACE: The given Spinel interface is not supported.",
    7: "STATUS_INTERNAL_ERROR: An internal runtime error has occured.",
    8: "STATUS_SECURITY_ERROR: A security or authentication error has occured.",
    9: "STATUS_PARSE_ERROR: An error has occured while parsing the command.",
    10: "STATUS_IN_PROGRESS: The operation is in progress and will be completed asynchronously.",
    11: "STATUS_NOMEM: The operation has been prevented due to memory pressure.",
    12: "STATUS_BUSY: The device is currently performing a mutually exclusive operation.",
    13: "STATUS_PROPERTY_NOT_FOUND: The given property is not recognized.",
    14: "STATUS_PACKET_DROPPED: The packet was dropped.",
    15: "STATUS_EMPTY: The result of the operation is empty.",
    16: "STATUS_CMD_TOO_BIG: The command was too large to fit in the internal buffer.",
    17: "STATUS_NO_ACK: The packet was not acknowledged.",
    18: "STATUS_CCA_FAILURE: The packet was not sent due to a CCA failure.",

    112: "STATUS_RESET_POWER_ON",
    113: "STATUS_RESET_EXTERNAL",
    114: "STATUS_RESET_SOFTWARE",
    115: "STATUS_RESET_FAULT",
    116: "STATUS_RESET_CRASH",
    117: "STATUS_RESET_ASSERT",
    118: "STATUS_RESET_OTHER",
    119: "STATUS_RESET_UNKNOWN",
    120: "STATUS_RESET_WATCHDOG",

    0x4000: "kThreadError_None",
    0x4001: "kThreadError_Failed",
    0x4002: "kThreadError_Drop",
    0x4003: "kThreadError_NoBufs",
    0x4004: "kThreadError_NoRoute",
    0x4005: "kThreadError_Busy",
    0x4006: "kThreadError_Parse",
    0x4007: "kThreadError_InvalidArgs",
    0x4008: "kThreadError_Security",
    0x4009: "kThreadError_AddressQuery",
    0x400A: "kThreadError_NoAddress",
    0x400B: "kThreadError_NotReceiving",
    0x400C: "kThreadError_Abort",
    0x400D: "kThreadError_NotImplemented",
    0x400E: "kThreadError_InvalidState",
    0x400F: "kThreadError_NoTasklets",

}

#=========================================

kThreadPrefixPreferenceOffset  = 6
kThreadPrefixPreferredFlag     = 1 << 5
kThreadPrefixSlaacFlag         = 1 << 4
kThreadPrefixDhcpFlag          = 1 << 3
kThreadPrefixConfigureFlag     = 1 << 2
kThreadPrefixDefaultRouteFlag  = 1 << 1
kThreadPrefixOnMeshFlag        = 1 << 0

#=========================================

#  0: DATATYPE_NULL
#'.': DATATYPE_VOID: Empty data type. Used internally.
#'b': DATATYPE_BOOL: Boolean value. Encoded in 8-bits as either 0x00 or 0x01. All other values are illegal.
#'C': DATATYPE_UINT8: Unsigned 8-bit integer.
#'c': DATATYPE_INT8: Signed 8-bit integer.
#'S': DATATYPE_UINT16: Unsigned 16-bit integer. (Little-endian)
#'s': DATATYPE_INT16: Signed 16-bit integer. (Little-endian)
#'L': DATATYPE_UINT32: Unsigned 32-bit integer. (Little-endian)
#'l': DATATYPE_INT32: Signed 32-bit integer. (Little-endian)
#'i': DATATYPE_UINT_PACKED: Packed Unsigned Integer. (See section 7.2)
#'6': DATATYPE_IPv6ADDR: IPv6 Address. (Big-endian)
#'E': DATATYPE_EUI64: EUI-64 Address. (Big-endian)
#'e': DATATYPE_EUI48: EUI-48 Address. (Big-endian)
#'D': DATATYPE_DATA: Arbitrary Data. (See section 7.3)
#'U': DATATYPE_UTF8: Zero-terminated UTF8-encoded string.
#'T': DATATYPE_STRUCT: Structured datatype. Compound type. (See section 7.4)
#'A': DATATYPE_ARRAY: Array of datatypes. Compound type. (See section 7.5)

class SpinelCodec():
    def parse_b(self, payload): return unpack("<B", payload[:1])[0]
    def parse_c(self, payload): return unpack("<b", payload[:1])[0]
    def parse_C(self, payload): return unpack("<B", payload[:1])[0]
    def parse_s(self, payload): return unpack("<h", payload[:2])[0]
    def parse_S(self, payload): return unpack("<H", payload[:2])[0]
    def parse_l(self, payload): return unpack("<l", payload[:4])[0]
    def parse_L(self, payload): return unpack("<L", payload[:4])[0]

    def parse_6(self, payload): return payload[:16]
    def parse_E(self, payload): return payload[:8]
    def parse_e(self, payload): return payload[:6]
    def parse_U(self, payload): return payload
    def parse_D(self, payload): return payload

    def parse_i(self, payload):
        """ Decode EXI integer format. """
        op = 0
        op_len = 0
        op_mul = 1

        while op_len < 4:
            b = ord(payload[op_len])
            op += (b & 0x7F) * op_mul
            if (b < 0x80): break
            op_mul *= 0x80
            op_len += 1

        return (op, op_len+1)

    def parse_field(self, payload, format):
        DECODE_MAP = {
            'b': self.parse_b,
            'c': self.parse_c,
            'C': self.parse_C,
            's': self.parse_s,
            'S': self.parse_S,
            'L': self.parse_L,
            'l': self.parse_l,
            '6': self.parse_6,
            'E': self.parse_E,
            'e': self.parse_e,
            'U': self.parse_U,
            'D': self.parse_D,
            'i': self.parse_i,
        }
        try:
            return DECODE_MAP[format[0]](payload)
        except:
            print traceback.format_exc()
            return None

    def encode_i(self, data):
        """ Encode EXI integer format. """
        result = ""
        while (data):
            v = data & 0x7F
            data >>= 7
            if data: v |= 0x80
            result = result + pack("<B", v)
        return result

    def encode_b(self, v): return pack( 'B', v)
    def encode_c(self, v): return pack( 'B', v)
    def encode_C(self, v): return pack( 'B', v)
    def encode_s(self, v): return pack('<h', v)
    def encode_S(self, v): return pack('<H', v)
    def encode_l(self, v): return pack('<l', v)
    def encode_L(self, v): return pack('<L', v)
    def encode_6(self, v): return v[:16]
    def encode_E(self, v): return v[:8]
    def encode_e(self, v): return v[:6]
    def encode_U(self, v): return v+'\0'
    def encode_D(self, v): return v

    def encode_field(self, code, value):
        ENCODE_MAP = {
            'b': self.encode_b,
            'c': self.encode_c,
            'C': self.encode_C,
            's': self.encode_s,
            'S': self.encode_S,
            'L': self.encode_L,
            'l': self.encode_l,
            '6': self.encode_6,
            'E': self.encode_E,
            'e': self.encode_e,
            'U': self.encode_U,
            'D': self.encode_D,
            'i': self.encode_i,
        }
        try:
            return ENCODE_MAP[code](value)
        except:
            print traceback.format_exc()
            return None

    def next_code(self, format):
        code = format[0]
        format = format[1:]
        # TODO: Handle T() and A()
        return code, format

    def encode_fields(self, format, *fields):
        packed = ""
        for field in fields:
            code, format = self.next_code(format)
            if not code: break
            packed += self.encode_field(code, field)
        return packed

    def encode_packet(self, commandId, payload = None, tid=SPINEL_HEADER_DEFAULT):
        """ Encode the given payload as a Spinel frame. """
        header = pack(">B", tid)
        cmd = self.encode_i(commandId)
        pkt = header + cmd + payload
        return pkt


#=========================================

class SpinelPropertyHandler(SpinelCodec):

    def LAST_STATUS(self, wpanApi, payload):      return self.parse_i(payload)[0]
    def PROTOCOL_VERSION(self, wpanApi, payload): pass
    def NCP_VERSION(self, wpanApi, payload):      return self.parse_U(payload)
    def INTERFACE_TYPE(self, wpanApi, payload):   return self.parse_i(payload)[0]
    def VENDOR_ID(self, wpanApi, payload):        return self.parse_i(payload)[0]
    def CAPS(self, wpanApi, payload):             pass
    def INTERFACE_COUNT(self, wpanApi, payload):  return self.parse_C(payload)
    def POWER_STATE(self, wpanApi, payload):      return self.parse_C(payload)
    def HWADDR(self, wpanApi, payload):           return self.parse_E(payload)
    def LOCK(self, wpanApi, payload):             return self.parse_b(payload)

    def HBO_MEM_MAX(self, wpanApi, payload):        return self.parse_L(payload)
    def HBO_BLOCK_MAX(self, wpanApi, payload):      return self.parse_S(payload)

    def PHY_ENABLED(self, wpanApi, payload):        return self.parse_b(payload)
    def PHY_CHAN(self, wpanApi, payload):           return self.parse_C(payload)
    def PHY_CHAN_SUPPORTED(self, wpanApi, payload): pass
    def PHY_FREQ(self, wpanApi, payload):           return self.parse_L(payload)
    def PHY_CCA_THRESHOLD(self, wpanApi, payload):  return self.parse_c(payload)
    def PHY_TX_POWER(self, wpanApi, payload):       return self.parse_c(payload)
    def PHY_RSSI(self, wpanApi, payload):           return self.parse_c(payload)

    def MAC_SCAN_STATE(self, wpanApi, payload):     return self.parse_C(payload)
    def MAC_SCAN_MASK(self, wpanApi, payload):      return self.parse_U(payload)
    def MAC_SCAN_PERIOD(self, wpanApi, payload):    return self.parse_S(payload)
    def MAC_SCAN_BEACON(self, wpanApi, payload):    return self.parse_U(payload)
    def MAC_15_4_LADDR(self, wpanApi, payload):     return self.parse_E(payload)
    def MAC_15_4_SADDR(self, wpanApi, payload):     return self.parse_S(payload)
    def MAC_15_4_PANID(self, wpanApi, payload):     return self.parse_S(payload)
    def MAC_FILTER_MODE(self, wpanApi, payload):    return self.parse_C(payload)
    def MAC_RAW_STREAM_ENABLED(self, wpanApi, payload):
        return self.parse_b(payload)

    def MAC_WHITELIST(self, wpanApi, payload):      pass
    def MAC_WHITELIST_ENABLED(self, wpanApi, payload): 
        return self.parse_b(payload)

    def NET_SAVED(self, wpanApi, payload):          return self.parse_b(payload)
    def NET_IF_UP(self, wpanApi, payload):          return self.parse_b(payload)
    def NET_STACK_UP(self, wpanApi, payload):       return self.parse_C(payload)
    def NET_ROLE(self, wpanApi, payload):           return self.parse_C(payload)
    def NET_NETWORK_NAME(self, wpanApi, payload):   return self.parse_U(payload)
    def NET_XPANID(self, wpanApi, payload):         return self.parse_D(payload)
    def NET_MASTER_KEY(self, wpanApi, payload):     return self.parse_D(payload)
    def NET_KEY_SEQUENCE(self, wpanApi, payload):   return self.parse_L(payload)
    def NET_PARTITION_ID(self, wpanApi, payload):   return self.parse_L(payload)

    def THREAD_LEADER_ADDR(self, wpanApi, payload): return self.parse_6(payload)
    def THREAD_PARENT(self, wpanApi, payload):      pass
    def THREAD_CHILD_TABLE(self, wpanApi, payload): return self.parse_D(payload)

    def THREAD_LEADER_RID(self, wpanApi, payload):  return self.parse_C(payload)
    def THREAD_LEADER_WEIGHT(self, wpanApi, payload):  
        return self.parse_C(payload)
    def THREAD_LOCAL_LEADER_WEIGHT(self, wpanApi, payload):
        return self.parse_C(payload)

    def THREAD_NETWORK_DATA(self, wpanApi, payload):
        return self.parse_D(payload)

    def THREAD_NETWORK_DATA_VERSION(self, wpanApi, payload):  pass
    def THREAD_STABLE_NETWORK_DATA(self, wpanApi, payload):   pass
    def THREAD_STABLE_NETWORK_DATA_VERSION(self, wpanApi, payload): pass

    def __init__(self):
        self.autoAddresses = set()

        self.__queue_prefix = Queue.Queue()
        self.prefix_thread = threading.Thread(target=self.__run_prefix_handler)
        self.prefix_thread.setDaemon(True)
        self.prefix_thread.start()

    def handle_ipaddr_remove(self, ipaddr):
        valid = 1
        preferred = 1
        flags = 0
        prefixLen = 64  # always use /64

        arr = self.encode_fields('6CLLC',
                                 ipaddr.ip.packed,
                                 prefixLen,
                                 valid,
                                 preferred,
                                 flags)

        self.wpanApi.prop_remove_async(SPINEL_PROP_IPV6_ADDRESS_TABLE,
                                   arr, str(len(arr))+'s',
                                   SPINEL_HEADER_EVENT_HANDLER)

    def handle_ipaddr_insert(self, prefix, prefixLen, stable, flags, isLocal):
        """ Add an ip address for each prefix on prefix change. """

        ipaddrStr = str(ipaddress.IPv6Address(prefix)) + str(self.wpanApi.nodeid)
        if CONFIG.DEBUG_LOG_PROP:
            print "\n>>>> new PREFIX add ipaddr: "+ipaddrStr

        valid = 1
        preferred = 1
        flags = 0
        ipaddr = ipaddress.IPv6Interface(unicode(ipaddrStr))
        self.autoAddresses.add(ipaddr)

        arr = self.encode_fields('6CLLC',
                                 ipaddr.ip.packed,
                                 prefixLen,
                                 valid,
                                 preferred,
                                 flags)

        self.wpanApi.prop_insert_async(SPINEL_PROP_IPV6_ADDRESS_TABLE,
                                   arr, str(len(arr))+'s',
                                   SPINEL_HEADER_EVENT_HANDLER)


    def handle_prefix_change(self, payload):
        """ Automatically ipaddr add / remove addresses for each new prefix. """
        # As done by cli.cpp Interpreter::HandleNetifStateChanged

        # First parse payload and extract slaac prefix information.
        pay = payload
        Prefix = namedtuple("Prefix", "prefix prefixlen stable flags isLocal")
        prefixes = []
        slaacPrefixSet = set()
        while (len(pay) >= 22):
            (structlen) = unpack('<H', pay[:2])
            pay = pay[2:]
            prefix = Prefix(*unpack('16sBBBB', pay[:20]))
            if (prefix.flags & kThreadPrefixSlaacFlag):
                net6 = ipaddress.IPv6Network(prefix.prefix)
                net6 = net6.supernet(new_prefix=prefix.prefixlen)
                slaacPrefixSet.add(net6)
                prefixes.append(prefix)
            pay = pay[20:]

        for prefix in prefixes:
            self.handle_ipaddr_insert(*prefix)

        if CONFIG.DEBUG_LOG_PROP:
            print "\n========= PREFIX ============"
            print "ipaddrs: "+str(self.autoAddresses)
            print "slaac prefix set: "+str(slaacPrefixSet)
            print "==============================\n"

        # ==> ipaddrs - query current addresses
        #
        # for ipaddr in ipaddrs:
        #     if lifetime > 0 and not in slaac prefixes
        #             ==> remove
        for ipaddr in self.autoAddresses:
            if not any(ipaddr in prefix for prefix in slaacPrefixSet):
                self.handle_ipaddr_remove(ipaddr)

        # for slaac prefix in prefixes:
        #     if no ipaddr with lifetime > 0 in prefix:
        #          ==> add


    def __run_prefix_handler(self):
        while 1:
            (wpanApi, payload) = self.__queue_prefix.get(True)
            self.wpanApi = wpanApi
            self.handle_prefix_change(payload)
            self.__queue_prefix.task_done()

    def THREAD_ON_MESH_NETS(self, wpanApi, payload):
        if FEATURE_USE_SLACC:
            # Kick prefix handler thread to allow serial rx thread to work.
            self.__queue_prefix.put_nowait((wpanApi, payload))

        return self.parse_D(payload)


    def THREAD_LOCAL_ROUTES(self, wpanApi, payload):          pass
    def THREAD_ASSISTING_PORTS(self, wpanApi, payload):       pass
    def THREAD_ALLOW_LOCAL_NET_DATA_CHANGE(self, wpanApi, payload):
        return self.parse_b(payload)

    def THREAD_MODE(self, wpanApi, payload):         return self.parse_C(payload)
    def THREAD_CHILD_TIMEOUT(self, wpanApi, payload):return self.parse_L(payload)
    def THREAD_RLOC16(self, wpanApi, payload):       return self.parse_S(payload)

    def THREAD_ROUTER_UPGRADE_THRESHOLD(self, wpanApi, payload):
        return self.parse_C(payload)

    def THREAD_ROUTER_DOWNGRADE_THRESHOLD(self, wpanApi, payload):
        return self.parse_C(payload)

    def THREAD_ROUTER_SELECTION_JITTER(self, wpanApi, payload):
        return self.parse_C(payload)

    def THREAD_CONTEXT_REUSE_DELAY(self, wpanApi, payload):
        return self.parse_L(payload)

    def THREAD_NETWORK_ID_TIMEOUT(self, wpanApi, payload): 
        return self.parse_C(payload)
    def THREAD_ACTIVE_ROUTER_IDS(self, wpanApi, payload): 
        return self.parse_D(payload)
    def THREAD_RLOC16_DEBUG_PASSTHRU(self, wpanApi, payload):
        return self.parse_b(payload)

    def MESHCOP_JOINER_ENABLE(self, wpanApi, payload):
        return self.parse_b(payload)
    def MESHCOP_JOINER_CREDENTIAL(self, wpanApi, payload):        
        return self.parse_D(payload)
    def MESHCOP_JOINER_URL(self, wpanApi, payload):               
        return self.parse_U(payload)
    def MESHCOP_BORDER_AGENT_ENABLE(self, wpanApi, payload):      
        return self.parse_b(payload)

    def IPV6_LL_ADDR(self, wpanApi, payload):        return self.parse_6(payload)
    def IPV6_ML_ADDR(self, wpanApi, payload):        return self.parse_6(payload)
    def IPV6_ML_PREFIX(self, wpanApi, payload):      return self.parse_E(payload)
    def IPV6_ADDRESS_TABLE(self, wpanApi, payload):  return self.parse_D(payload)
    def IPV6_ROUTE_TABLE(self, wpanApi, payload):    return self.parse_D(payload)
    def IPv6_ICMP_PING_OFFLOAD(self, wpanApi, payload): 
        return self.parse_b(payload)

    def STREAM_DEBUG(self, wpanApi, payload):        return self.parse_U(payload)
    def STREAM_RAW(self, wpanApi, payload):          return self.parse_D(payload)
    def STREAM_NET(self, wpanApi, payload):          return self.parse_D(payload)
    def STREAM_NET_INSECURE(self, wpanApi, payload): return self.parse_D(payload)


#=========================================

class SpinelCommandHandler(SpinelCodec):

    def handle_prop(self, wpanApi, name, payload, tid):
        (propId, prop_len) = self.parse_i(payload)

        try:
            handler = SPINEL_PROP_DISPATCH[propId]
            propName = handler.__name__
            propValue = handler(wpanApi, payload[prop_len:])

            if CONFIG.DEBUG_LOG_PROP:

                # Generic output
                if isinstance(propValue, basestring):
                    propValueStr = util.hexify_str(propValue)
                    logging.debug("PROP_VALUE_%s [tid=%d]: %s = %s" %
                                  (name, (tid & 0xF), propName, propValueStr))
                else:
                    propValueStr = str(propValue)

                    logging.debug("PROP_VALUE_%s [tid=%d]: %s = %s" %
                                  (name, (tid & 0xF), propName, propValueStr))

                # Extend output for certain properties.
                if (propId == SPINEL_PROP_LAST_STATUS):
                    logging.debug(SPINEL_LAST_STATUS_MAP[propValue])

            if CONFIG.DEBUG_LOG_PKT:
                if ((propId == SPINEL_PROP_STREAM_NET) or
                      (propId == SPINEL_PROP_STREAM_NET_INSECURE)):
                    logging.debug("PROP_VALUE_"+name+": "+propName)
                    pkt = IPv6(propValue[2:])
                    pkt.show()

                elif (propId == SPINEL_PROP_STREAM_DEBUG):
                    logging.debug("DEBUG: "+propValue)

            if wpanApi:
                wpanApi.queue_add(propId, propValue, tid)
            else:
                print "no wpanApi"

        except:
            propName = "Property Unknown"
            logging.info ("\n%s (%i): " % (propName, propId))
            print traceback.format_exc()


    def PROP_VALUE_IS(self, wpanApi, payload, tid):
        self.handle_prop(wpanApi, "IS", payload, tid)

    def PROP_VALUE_INSERTED(self, wpanApi, payload, tid):
        self.handle_prop(wpanApi, "INSERTED", payload, tid)

    def PROP_VALUE_REMOVED(self, wpanApi, payload, tid):
        self.handle_prop(wpanApi, "REMOVED", payload, tid)


wpanHandler = SpinelCommandHandler()

SPINEL_COMMAND_DISPATCH = {
    SPINEL_RSP_PROP_VALUE_IS: wpanHandler.PROP_VALUE_IS,
    SPINEL_RSP_PROP_VALUE_INSERTED: wpanHandler.PROP_VALUE_INSERTED,
    SPINEL_RSP_PROP_VALUE_REMOVED: wpanHandler.PROP_VALUE_REMOVED,
}

wpanPropHandler = SpinelPropertyHandler()

SPINEL_PROP_DISPATCH = {
    SPINEL_PROP_LAST_STATUS:           wpanPropHandler.LAST_STATUS,
    SPINEL_PROP_PROTOCOL_VERSION:      wpanPropHandler.PROTOCOL_VERSION,
    SPINEL_PROP_NCP_VERSION:           wpanPropHandler.NCP_VERSION,
    SPINEL_PROP_INTERFACE_TYPE:        wpanPropHandler.INTERFACE_TYPE,
    SPINEL_PROP_VENDOR_ID:             wpanPropHandler.VENDOR_ID,
    SPINEL_PROP_CAPS:                  wpanPropHandler.CAPS,
    SPINEL_PROP_INTERFACE_COUNT:       wpanPropHandler.INTERFACE_COUNT,
    SPINEL_PROP_POWER_STATE:           wpanPropHandler.POWER_STATE,
    SPINEL_PROP_HWADDR:                wpanPropHandler.HWADDR,
    SPINEL_PROP_LOCK:                  wpanPropHandler.LOCK,
    SPINEL_PROP_HBO_MEM_MAX:           wpanPropHandler.HBO_MEM_MAX,
    SPINEL_PROP_HBO_BLOCK_MAX:         wpanPropHandler.HBO_BLOCK_MAX,

    SPINEL_PROP_PHY_ENABLED:           wpanPropHandler.PHY_ENABLED,
    SPINEL_PROP_PHY_CHAN:              wpanPropHandler.PHY_CHAN,
    SPINEL_PROP_PHY_CHAN_SUPPORTED:    wpanPropHandler.PHY_CHAN_SUPPORTED,
    SPINEL_PROP_PHY_FREQ:              wpanPropHandler.PHY_FREQ,
    SPINEL_PROP_PHY_CCA_THRESHOLD:     wpanPropHandler.PHY_CCA_THRESHOLD,
    SPINEL_PROP_PHY_TX_POWER:          wpanPropHandler.PHY_TX_POWER,
    SPINEL_PROP_PHY_RSSI:              wpanPropHandler.PHY_RSSI,

    SPINEL_PROP_MAC_SCAN_STATE:        wpanPropHandler.MAC_SCAN_STATE,
    SPINEL_PROP_MAC_SCAN_MASK:         wpanPropHandler.MAC_SCAN_MASK,
    SPINEL_PROP_MAC_SCAN_PERIOD:       wpanPropHandler.MAC_SCAN_PERIOD,
    SPINEL_PROP_MAC_SCAN_BEACON:       wpanPropHandler.MAC_SCAN_BEACON,
    SPINEL_PROP_MAC_15_4_LADDR:        wpanPropHandler.MAC_15_4_LADDR,
    SPINEL_PROP_MAC_15_4_SADDR:        wpanPropHandler.MAC_15_4_SADDR,
    SPINEL_PROP_MAC_15_4_PANID:        wpanPropHandler.MAC_15_4_PANID,
    SPINEL_PROP_MAC_RAW_STREAM_ENABLED:wpanPropHandler.MAC_RAW_STREAM_ENABLED,
    SPINEL_PROP_MAC_FILTER_MODE:       wpanPropHandler.MAC_FILTER_MODE,

    SPINEL_PROP_MAC_WHITELIST:         wpanPropHandler.MAC_WHITELIST,
    SPINEL_PROP_MAC_WHITELIST_ENABLED: wpanPropHandler.MAC_WHITELIST_ENABLED,

    SPINEL_PROP_NET_SAVED:             wpanPropHandler.NET_SAVED,
    SPINEL_PROP_NET_IF_UP:             wpanPropHandler.NET_IF_UP,
    SPINEL_PROP_NET_STACK_UP:          wpanPropHandler.NET_STACK_UP,
    SPINEL_PROP_NET_ROLE:              wpanPropHandler.NET_ROLE,
    SPINEL_PROP_NET_NETWORK_NAME:      wpanPropHandler.NET_NETWORK_NAME,
    SPINEL_PROP_NET_XPANID:            wpanPropHandler.NET_XPANID,
    SPINEL_PROP_NET_MASTER_KEY:        wpanPropHandler.NET_MASTER_KEY,
    SPINEL_PROP_NET_KEY_SEQUENCE:      wpanPropHandler.NET_KEY_SEQUENCE,
    SPINEL_PROP_NET_PARTITION_ID:      wpanPropHandler.NET_PARTITION_ID,

    SPINEL_PROP_THREAD_LEADER_ADDR: wpanPropHandler.THREAD_LEADER_ADDR,
    SPINEL_PROP_THREAD_PARENT: wpanPropHandler.THREAD_PARENT,
    SPINEL_PROP_THREAD_CHILD_TABLE:  wpanPropHandler.THREAD_CHILD_TABLE,
    SPINEL_PROP_THREAD_LEADER_RID: wpanPropHandler.THREAD_LEADER_RID,
    SPINEL_PROP_THREAD_LEADER_WEIGHT: wpanPropHandler.THREAD_LEADER_WEIGHT,
    SPINEL_PROP_THREAD_LOCAL_LEADER_WEIGHT: wpanPropHandler.THREAD_LOCAL_LEADER_WEIGHT,
    SPINEL_PROP_THREAD_NETWORK_DATA: wpanPropHandler.THREAD_NETWORK_DATA,
    SPINEL_PROP_THREAD_NETWORK_DATA_VERSION: wpanPropHandler.THREAD_NETWORK_DATA_VERSION,
    SPINEL_PROP_THREAD_STABLE_NETWORK_DATA: wpanPropHandler.THREAD_STABLE_NETWORK_DATA,
    SPINEL_PROP_THREAD_STABLE_NETWORK_DATA_VERSION:wpanPropHandler.THREAD_STABLE_NETWORK_DATA_VERSION,
    SPINEL_PROP_THREAD_ON_MESH_NETS: wpanPropHandler.THREAD_ON_MESH_NETS,
    SPINEL_PROP_THREAD_LOCAL_ROUTES: wpanPropHandler.THREAD_LOCAL_ROUTES,
    SPINEL_PROP_THREAD_ASSISTING_PORTS: wpanPropHandler.THREAD_ASSISTING_PORTS,
    SPINEL_PROP_THREAD_ALLOW_LOCAL_NET_DATA_CHANGE: wpanPropHandler.THREAD_ALLOW_LOCAL_NET_DATA_CHANGE,
    SPINEL_PROP_THREAD_MODE: wpanPropHandler.THREAD_MODE,
    SPINEL_PROP_THREAD_CHILD_TIMEOUT: wpanPropHandler.THREAD_CHILD_TIMEOUT,
    SPINEL_PROP_THREAD_RLOC16: wpanPropHandler.THREAD_RLOC16,
    SPINEL_PROP_THREAD_ROUTER_UPGRADE_THRESHOLD: wpanPropHandler.THREAD_ROUTER_UPGRADE_THRESHOLD,
    SPINEL_PROP_THREAD_ROUTER_DOWNGRADE_THRESHOLD: wpanPropHandler.THREAD_ROUTER_DOWNGRADE_THRESHOLD,
    SPINEL_PROP_THREAD_ROUTER_SELECTION_JITTER: wpanPropHandler.THREAD_ROUTER_SELECTION_JITTER,
    SPINEL_PROP_THREAD_CONTEXT_REUSE_DELAY: wpanPropHandler.THREAD_CONTEXT_REUSE_DELAY,
    SPINEL_PROP_THREAD_NETWORK_ID_TIMEOUT: wpanPropHandler.THREAD_NETWORK_ID_TIMEOUT,
    SPINEL_PROP_THREAD_ACTIVE_ROUTER_IDS: wpanPropHandler.THREAD_ACTIVE_ROUTER_IDS,
    SPINEL_PROP_THREAD_RLOC16_DEBUG_PASSTHRU: wpanPropHandler.THREAD_RLOC16_DEBUG_PASSTHRU,

    SPINEL_PROP_MESHCOP_JOINER_ENABLE: wpanPropHandler.MESHCOP_JOINER_ENABLE,
    SPINEL_PROP_MESHCOP_JOINER_CREDENTIAL: wpanPropHandler.MESHCOP_JOINER_CREDENTIAL,
    SPINEL_PROP_MESHCOP_JOINER_URL: wpanPropHandler.MESHCOP_JOINER_URL,
    SPINEL_PROP_MESHCOP_BORDER_AGENT_ENABLE: wpanPropHandler.MESHCOP_BORDER_AGENT_ENABLE,


    SPINEL_PROP_IPV6_LL_ADDR:           wpanPropHandler.IPV6_LL_ADDR,
    SPINEL_PROP_IPV6_ML_ADDR:           wpanPropHandler.IPV6_ML_ADDR,
    SPINEL_PROP_IPV6_ML_PREFIX:         wpanPropHandler.IPV6_ML_PREFIX,
    SPINEL_PROP_IPV6_ADDRESS_TABLE:     wpanPropHandler.IPV6_ADDRESS_TABLE,
    SPINEL_PROP_IPV6_ROUTE_TABLE:       wpanPropHandler.IPV6_ROUTE_TABLE,
    SPINEL_PROP_IPv6_ICMP_PING_OFFLOAD: wpanPropHandler.IPv6_ICMP_PING_OFFLOAD,

    SPINEL_PROP_STREAM_DEBUG:           wpanPropHandler.STREAM_DEBUG,
    SPINEL_PROP_STREAM_RAW:             wpanPropHandler.STREAM_RAW,
    SPINEL_PROP_STREAM_NET:             wpanPropHandler.STREAM_NET,
    SPINEL_PROP_STREAM_NET_INSECURE:    wpanPropHandler.STREAM_NET_INSECURE,
}


class WpanApi(SpinelCodec):
    """ Helper class to format wpan command packets """

    def __init__(self, stream, nodeid, useHdlc=FEATURE_USE_HDLC):

        self.tunIf = None
        self.stream = stream
        self.nodeid = nodeid

        self.useHdlc = useHdlc
        if self.useHdlc:
            self.hdlc = Hdlc(self.stream)

        # PARSER state
        self.rx_pkt = []

        # Fire up threads
        self.tidFilter = set()
        self.__queue_prop = defaultdict(Queue.Queue)
        self.queue_register()
        self.__start_reader()

    def __del__(self):
        self._reader_alive = False

    def __start_reader(self):
        """Start reader thread"""
        self._reader_alive = True
        # start serial->console thread
        self.receiver_thread = threading.Thread(target=self.stream_rx)
        self.receiver_thread.setDaemon(True)
        self.receiver_thread.start()

    def transact(self, commandId, payload = "", tid=SPINEL_HEADER_DEFAULT):
        pkt = self.encode_packet(commandId, payload, tid)
        if CONFIG.DEBUG_LOG_SERIAL:
            msg = "TX Pay: (%i) %s " % (len(pkt), util.hexify_bytes(pkt))
            logging.debug(msg)

        if self.useHdlc: pkt = self.hdlc.encode(pkt)
        self.stream_tx(pkt)

    def parse_rx(self, pkt):
        if CONFIG.DEBUG_LOG_SERIAL:
            msg = "RX Pay: (%i) %s " % (len(pkt), str(map(util.hexify_int,pkt)))
            logging.debug(msg)

        if not pkt: return

        length = len(pkt) - 2
        if (length < 0): return

        spkt = "".join(map(chr, pkt))

        tid = self.parse_C(spkt[:1])
        (cmdId, cmdLength) = self.parse_i(spkt[1:])
        pay_start = cmdLength + 1
        payload = spkt[pay_start:]

        try:
            handler = SPINEL_COMMAND_DISPATCH[cmdId]
            cmdName = handler.__name__
            handler(self, payload, tid)

        except:
            print traceback.format_exc()
            cmdName = "CB_Unknown"
            logging.info ("\n%s (%i): " % (cmdName, cmdId))

        if CONFIG.DEBUG_CMD_RESPONSE:
            logging.info ("\n%s (%i): " % (cmdName, cmdId))
            logging.info ("===> %s" % util.hexify_str(payload))


    def stream_tx(self, pkt):
        # Encapsulate lagging and Framer support in self.stream class.
        self.stream.write(pkt)


    def stream_rx(self):
        """ Recieve thread and parser. """
        while self._reader_alive:
            if self.useHdlc:
                self.rx_pkt = self.hdlc.collect()

            self.parse_rx(self.rx_pkt)


    class PropertyItem(object):
        """ Queue item for NCP response to property commands. """
        def __init__(self, prop, value, tid):
            self.prop = prop
            self.value = value
            self.tid = tid

    def queue_register(self, tid=SPINEL_HEADER_DEFAULT):
        self.tidFilter.add(tid)
        return self.__queue_prop[tid]

    def queue_wait_prepare(self, propId, tid=SPINEL_HEADER_DEFAULT):
        self.queue_clear(tid)

    def queue_add(self, prop, value, tid):
        # Asynchronous handlers don't actually add to queue.
        if (prop == SPINEL_PROP_STREAM_NET):
            pkt = IPv6(value[2:])
            if ICMPv6EchoReply in pkt:
                timenow = int(round(time.time() * 1000)) & 0xFFFFFFFF
                timedelta = (timenow - unpack('>I', pkt.data)[0])
                print "\n%d bytes from %s: icmp_seq=%d hlim=%d time=%dms" % (
                    pkt.plen, pkt.src, pkt.seq, pkt.hlim, timedelta)
            return

        if (tid not in self.tidFilter): return
        item = self.PropertyItem(prop, value, tid)
        self.__queue_prop[tid].put_nowait(item)

    def queue_clear(self, tid):
        with self.__queue_prop[tid].mutex:
            self.__queue_prop[tid].queue.clear()

    def queue_wait_for_prop(self, prop, tid=SPINEL_HEADER_DEFAULT, timeout=TIMEOUT_PROP):
        try:
            item = self.__queue_prop[tid].get(True, timeout)
            self.__queue_prop[tid].task_done()
        except:
            item = None

        return item


    def if_up(self, nodeid='1'):
        if os.geteuid() == 0:
            self.tunIf = TunInterface(nodeid)
        else:
            print "Warning: superuser required to start tun interface."

    def if_down(self):
        if self.tunIf: self.tunIf.close()
        self.tunIf = None

    def ip_send(self, pkt):
        pay = self.encode_i(SPINEL_PROP_STREAM_NET)

        pkt_len = len(pkt)
        pay += pack("<H",pkt_len)          # Start with length of IPv6 packet

        pkt_len += 2                       # Increment to include length word
        pay += pack("%ds" % pkt_len, pkt)  # Append packet after length

        self.transact(SPINEL_CMD_PROP_VALUE_SET, pay)

    def prop_change_async(self, cmd, propId, value, format='B',
                          tid=SPINEL_HEADER_DEFAULT):
        pay = self.encode_i(propId)
        if format != None:
            pay += pack(format, value)
        self.transact(cmd, pay, tid)

    def prop_insert_async(self, propId, value, format='B',
                          tid=SPINEL_HEADER_DEFAULT):
        self.prop_change_async(SPINEL_CMD_PROP_VALUE_INSERT, propId,
                               value, format, tid)

    def prop_remove_async(self, propId, value, format='B',
                          tid=SPINEL_HEADER_DEFAULT):
        self.prop_change_async(SPINEL_CMD_PROP_VALUE_REMOVE, propId,
                               value, format, tid)

    def __prop_change_value(self, cmd, propId, value, format='B',
                            tid=SPINEL_HEADER_DEFAULT):
        """ Utility routine to change a property value over Spinel. """
        self.queue_wait_prepare(propId, tid)

        pay = self.encode_i(propId)
        if format != None:
            pay += pack(format, value)
        self.transact(cmd, pay, tid)

        result = self.queue_wait_for_prop(propId, tid)
        if result:
            return result.value
        else:
            return None

    def prop_get_value(self, propId, tid=SPINEL_HEADER_DEFAULT):
        """ Blocking routine to get a property value over Spinel. """
        if CONFIG.DEBUG_LOG_PROP:
            handler = SPINEL_PROP_DISPATCH[propId]
            propName = handler.__name__
            print "PROP_VALUE_GET [tid=%d]: %s" % (tid&0xF, propName)
        return self.__prop_change_value(SPINEL_CMD_PROP_VALUE_GET, propId,
                                        None, None, tid)

    def prop_set_value(self, propId, value, format='B',
                       tid=SPINEL_HEADER_DEFAULT):
        """ Blocking routine to set a property value over Spinel. """
        if CONFIG.DEBUG_LOG_PROP:
            handler = SPINEL_PROP_DISPATCH[propId]
            propName = handler.__name__
            print "PROP_VALUE_SET [tid=%d]: %s" % (tid&0xF, propName)
        return self.__prop_change_value(SPINEL_CMD_PROP_VALUE_SET, propId,
                                        value, format, tid)

    def prop_insert_value(self, propId, value, format='B',
                          tid=SPINEL_HEADER_DEFAULT):
        """ Blocking routine to insert a property value over Spinel. """
        if CONFIG.DEBUG_LOG_PROP:
            handler = SPINEL_PROP_DISPATCH[propId]
            propName = handler.__name__
            print "PROP_VALUE_INSERT [tid=%d]: %s" % (tid&0xF, propName)
        return self.__prop_change_value(SPINEL_CMD_PROP_VALUE_INSERT, propId,
                                        value, format, tid)

    def prop_remove_value(self, propId, value, format='B',
                          tid=SPINEL_HEADER_DEFAULT):
        """ Blocking routine to remove a property value over Spinel. """
        if CONFIG.DEBUG_LOG_PROP:
            handler = SPINEL_PROP_DISPATCH[propId]
            propName = handler.__name__
            print "PROP_VALUE_REMOVE [tid=%d]: %s" % (tid&0xF, propName)
        return self.__prop_change_value(SPINEL_CMD_PROP_VALUE_REMOVE, propId,
                                        value, format, tid)

    def get_ipaddrs(self, tid=SPINEL_HEADER_DEFAULT):
        v = self.prop_get_value(SPINEL_PROP_IPV6_ADDRESS_TABLE, tid)
        # TODO: clean up table parsing to be less hard-coded magic.
        if v == None: return None
        sz = 0x1B
        addrs = [v[i:i+sz] for i in xrange(0, len(v), sz)]
        ipaddrs = []
        for addr in addrs:
            addr = addr[2:18]
            ipaddrs.append(ipaddress.IPv6Address(addr))
        return ipaddrs



