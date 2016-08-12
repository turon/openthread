#!/usr/bin/python
""" 
spinel-cli.py

vailable commands (type help <name> for more information):
============================================================
channel            diag-sleep  ifconfig          q                     
child              diag-start  ipaddr            quit                  
childtimeout       diag-stats  keysequence       releaserouterid       
clear              diag-stop   leaderdata        rloc16                
contextreusedelay  discover    leaderweight      route                 
counter            eidcache    masterkey         router                
debug              enabled     mode              routerupgradethreshold
debug-term         exit        netdataregister   scan                  
diag               extaddr     networkidtimeout  state                 
diag-channel       extpanid    networkname       thread                
diag-power         h           panid             v                     
diag-repeat        help        ping              version               
diag-send          history     prefix            whitelist      
"""

__copyright__   = "Copyright (c) 2016 Nest Labs, Inc."
__version__     = "0.1.0"


FEATURE_USE_HDLC = 1

DEBUG_ENABLE = 0

DEBUG_LOG_TX = 0
DEBUG_LOG_RX = 0
DEBUG_LOG_PKT = DEBUG_ENABLE
DEBUG_LOG_PROP = DEBUG_ENABLE
DEBUG_TERM = 0
DEBUG_CMD_RESPONSE = 0

gWpanApi = None

import os
import sys
import time
import threading
import traceback

import blessed

import optparse
from optparse import OptionParser, Option, OptionValueError

import string
import shlex
import base64
import textwrap

import logging
import logging.config
import logging.handlers
import traceback
import subprocess
import Queue

import serial
import socket

from cmd import Cmd
from copy import copy
from struct import pack
from struct import unpack


MASTER_PROMPT  = "spinel-cli"

DEFAULT_NODE_TYPE = 2    

logging.config.dictConfig({
    'version': 1,              
    'disable_existing_loggers': False, 

    'formatters': {
        'minimal': {
            'format': '%(message)s'
        },
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'console': {
            #'level':'INFO',    
            'level':'DEBUG',    
            'class':'logging.StreamHandler',
        },  
        #'syslog': {
        #    'level':'DEBUG',    
        #    'class':'logging.handlers.SysLogHandler',
        #    'address': '/dev/log'
        #},  
    },
    'loggers': {
        '': {                  
            'handlers': ['console'], #,'syslog'],        
            'level': 'DEBUG',  
            'propagate': True  
        }
    }
})

logger = logging.getLogger(__name__)


# Terminal macros

class Color:
    END          = '\033[0m'
    BOLD         = '\033[1m'
    DIM          = '\033[2m'
    UNDERLINE    = '\033[4m'
    BLINK        = '\033[5m'
    REVERSE      = '\033[7m'

    CYAN         = '\033[96m'
    PURPLE       = '\033[95m'
    BLUE         = '\033[94m'
    YELLOW       = '\033[93m'
    GREEN        = '\033[92m'
    RED          = '\033[91m'

    BLACK        = "\033[30m"
    DARKRED      = "\033[31m"
    DARKGREEN    = "\033[32m"
    DARKYELLOW   = "\033[33m"
    DARKBLUE     = "\033[34m"
    DARKMAGENTA  = "\033[35m"
    DARKCYAN     = "\033[36m"
    WHITE        = "\033[37m"


SPINEL_RSSI_OVERRIDE            = 127

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
SPINEL_PROP_NET_ENABLED          = SPINEL_PROP_NET__BEGIN + 1 #< [b]
SPINEL_PROP_NET_STATE            = SPINEL_PROP_NET__BEGIN + 2 #< [C]
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
SPINEL_PROP_THREAD_EXT__END        = 0x1600,


SPINEL_PROP_IPV6__BEGIN          = 0x60
SPINEL_PROP_IPV6_LL_ADDR         = SPINEL_PROP_IPV6__BEGIN + 0 #< [6]
SPINEL_PROP_IPV6_ML_ADDR         = SPINEL_PROP_IPV6__BEGIN + 1 #< [6C]
SPINEL_PROP_IPV6_ML_PREFIX       = SPINEL_PROP_IPV6__BEGIN + 2 #< [6C]
SPINEL_PROP_IPV6_ADDRESS_TABLE   = SPINEL_PROP_IPV6__BEGIN + 3 #< array(ipv6addr,prefixlen,valid,preferred,flags) [A(T(6CLLC))]
SPINEL_PROP_IPV6_ROUTE_TABLE     = SPINEL_PROP_IPV6__BEGIN + 4 #< array(ipv6prefix,prefixlen,iface,flags) [A(T(6CCC))]
SPINEL_PROP_IPV6__END            = 0x70

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

kDeviceRoleDisabled = 0  #< The Thread stack is disabled.
kDeviceRoleDetached = 1  #< Not currently in a Thread network/partition.
kDeviceRoleChild = 2     #< The Thread Child role.
kDeviceRoleRouter = 3    #< The Thread Router role.
kDeviceRoleLeader = 4    #< The Thread Leader role.

THREAD_STATE_MAP = {
    kDeviceRoleDisabled: "disabled",
    kDeviceRoleDetached: "detached",
    kDeviceRoleChild: "child",
    kDeviceRoleRouter: "router",
    kDeviceRoleLeader: "leader",
}

THREAD_STATE_NAME_MAP = {
    "disabled": kDeviceRoleDisabled,
    "detached": kDeviceRoleDetached,
    "child": kDeviceRoleChild,
    "router": kDeviceRoleRouter,
    "leader": kDeviceRoleLeader,
}

#=========================================

class DiagsTerminal(blessed.Terminal):
    def print_title(self, strings=[]):
        clr = term.green_reverse
        title = term.white_reverse("  spinel-cli  ")
        with term.location(x=0, y=0):
            print (clr + term.center(title+clr))
            for string in strings:
                print (term.ljust(string))
            print (term.ljust(" ") + term.normal)

term = DiagsTerminal()

#=========================================
    
def hexify_chr(s): return "%02X" % ord(s)
def hexify_int(i): return "%02X" % i
def hexify_bytes(data): return str(map(hexify_chr,data))
def hexify_str(s,delim=':'): 
    return delim.join(x.encode('hex') for x in s)

def asciify_int(i): return "%c" % (i)

def hex_to_bytes(s):
    result = ''
    for i in xrange(0, len(s), 2):
        (b1, b2) = s[i:i+2]
        hex = b1+b2
        v = int(hex, 16)
        result += chr(v)
    return result

def print_stack():
    for line in traceback.format_stack():
        print line.strip()

#=========================================

class IStream():
    def read(self, size): pass
    def write(self, data): pass
    def close(self): pass

class StreamSerial(IStream):
    def __init__(self, dev, baudrate=115200):
        comm = serial.Serial(dev, baudrate, timeout=1)
        logger.debug("TX Raw: (%d) %s" % (len(data), hexify_bytes(data)))

    def read(self, size=1):
        b = self.sock.recv(size)
        if DEBUG_LOG_RX:
            logger.debug("RX Raw: "+hexify_bytes(b))        
        return b

class StreamPipe(IStream):
    def __init__(self, filename):        
        """ Create a stream object from a piped system call """
        self.pipe = subprocess.Popen(filename, shell = True,
                                     stdin = subprocess.PIPE,
                                     stdout = subprocess.PIPE)

    def write(self, data):
        if DEBUG_LOG_TX:
            logger.debug("TX Raw: (%d) %s" % (len(data), hexify_bytes(data)))
        self.pipe.stdin.write(data)

    def read(self, size=1):
        """ Blocking read on stream object """
        for b in iter(lambda: self.pipe.stdout.read(size), ''):
            if DEBUG_LOG_RX:
                logger.debug("RX Raw: "+hexify_bytes(b))        
            return ord(b)

    def close(self):
        self.pipe.kill()

def StreamOpen(type, descriptor):
    """ 
    Factory function that creates and opens a stream connection.

    type:
        'u' = uart (/dev/tty#)
        's' = socket (port #)
        'p' = pipe (stdin/stdout)

    descriptor:
        uart - filename of device (/dev/tty#)
        socket - port to open connection to on localhost
        pipe - filename of command to execute and bind via stdin/stdout
    """

    if (type == 'p'): 
        print "Opening pipe to "+str(descriptor)
        return StreamPipe(descriptor)

    elif (type == 's'):
        port = int(descriptor)
        hostname = "localhost"
        print "Opening socket to "+hostname+":"+str(port)
        return StreamSocket(hostname, port)

    elif (type == 'u'):        
        dev = str(descriptor)
        baudrate = 115200
        print "Opening serial to "+dev+" @ "+str(baudrate)
        return StreamSerial(dev, baudrate)
    
    else:
        return None

#=========================================

HDLC_FLAG     = 0x7e
HDLC_ESCAPE   = 0x7d

# RFC 1662 Appendix C

HDLC_FCS_INIT = 0xFFFF
HDLC_FCS_POLY = 0x8408
HDLC_FCS_GOOD = 0xF0B8

def mkfcstab():
    P = HDLC_FCS_POLY

    def valiter():
        for b in range(256):
            v = b
            i = 8
            while i:
                v = (v >> 1) ^ P if v & 1 else v >> 1
                i -= 1

            yield v & 0xFFFF

    return tuple(valiter())

fcstab = mkfcstab()


def fcs16(byte, fcs):
    fcs = (fcs >> 8) ^ fcstab[(fcs ^ byte) & 0xff]
    return fcs


class Hdlc(IStream):
    def __init__(self, stream):
        self.stream = stream
                    
    def collect(self):
        fcs = HDLC_FCS_INIT
        packet = []

        # Synchronize
        while 1:
            b = self.stream.read()
            if (b == HDLC_FLAG): break

        # Read packet, updating fcs, and escaping bytes as needed
        while 1:
            b = self.stream.read()
            if (b == HDLC_FLAG): break
            if (b == HDLC_ESCAPE):
                b = self.stream.read()
                b ^= 0x20
            packet.append(b)
            fcs = fcs16(b, fcs)
            #print("State: "+str(b)+ "  FCS: 0x"+hexify_int(fcs))

        #print("Fcs: 0x"+hexify_int(fcs))

        if (fcs != HDLC_FCS_GOOD):
            packet = None

        return packet


    def encode(self, payload = ""):
        fcs = HDLC_FCS_INIT
        packet = []
        packet.append(HDLC_FLAG)
        for b in payload:  
            b = ord(b)
            fcs = fcs16(b, fcs)
            if (b == HDLC_ESCAPE) or (b == HDLC_FLAG):
                packet.append(HDLC_ESCAPE)
                packet.append(b ^ 0x20)
            else:
                packet.append(b)

        fcs ^= 0xffff;
        packet.append(fcs & 0xFF)
        packet.append(fcs >> 8)
        packet.append(HDLC_FLAG)
        packet = pack("%dB" % len(packet), *packet)
        return packet

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
    def parse_U(self, payload): return payload[:-2]   # remove FCS16 from end
    def parse_D(self, payload): return payload[:-2]   # remove FCS16 from end

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
        dispath_map = {
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
            return dispatch_map[format[0]](payload)
        except:
            print_stack()
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

    def encode(self, cmd_id, payload = None):
        """ Encode the given payload as a Spinel frame. """
        header = pack(">B", 0x80)
        cmd = self.encode_i(cmd_id)
        pkt = header + cmd + payload
        return pkt


#=========================================

class SpinelPropertyHandler(SpinelCodec):

    def LAST_STATUS(self, payload):           return self.parse_i(payload)[0]
    def PROTOCOL_VERSION(self, payload):      pass
    def NCP_VERSION(self, payload):           return self.parse_U(payload)
    def INTERFACE_TYPE(self, payload):        return self.parse_i(payload)[0]
    def VENDOR_ID(self, payload):             return self.parse_i(payload)[0]
    def CAPS(self, payload):                  pass
    def INTERFACE_COUNT(self, payload):       return self.parse_C(payload)
    def POWER_STATE(self, payload):           return self.parse_C(payload)
    def HWADDR(self, payload):                return self.parse_E(payload)
    def LOCK(self, payload):                  return self.parse_b(payload)

    def HBO_MEM_MAX(self, payload):           return self.parse_L(payload)
    def HBO_BLOCK_MAX(self, payload):         return self.parse_S(payload)

    def PHY_ENABLED(self, payload):           return self.parse_b(payload)
    def PHY_CHAN(self, payload):              return self.parse_C(payload)
    def PHY_CHAN_SUPPORTED(self, payload):    pass
    def PHY_FREQ(self, payload):              return self.parse_L(payload)
    def PHY_CCA_THRESHOLD(self, payload):     return self.parse_c(payload)
    def PHY_TX_POWER(self, payload):          return self.parse_c(payload)
    def PHY_RSSI(self, payload):              return self.parse_c(payload)

    def MAC_SCAN_STATE(self, payload):        return self.parse_C(payload)
    def MAC_SCAN_MASK(self, payload):         return self.parse_U(payload)
    def MAC_SCAN_PERIOD(self, payload):       return self.parse_S(payload)
    def MAC_SCAN_BEACON(self, payload):       return self.parse_U(payload)
    def MAC_15_4_LADDR(self, payload):        return self.parse_E(payload)
    def MAC_15_4_SADDR(self, payload):        return self.parse_S(payload)
    def MAC_15_4_PANID(self, payload):        return self.parse_S(payload)
    def MAC_RAW_STREAM_ENABLED(self, payload):return self.parse_b(payload)
    def MAC_FILTER_MODE(self, payload):       return self.parse_C(payload)

    def MAC_WHITELIST(self, payload):         pass
    def MAC_WHITELIST_ENABLED(self, payload): return self.parse_b(payload)

    def NET_SAVED(self, payload):             return self.parse_b(payload)
    def NET_ENABLED(self, payload):           return self.parse_b(payload)
    def NET_STATE(self, payload):             return self.parse_C(payload)
    def NET_ROLE(self, payload):              return self.parse_C(payload)
    def NET_NETWORK_NAME(self, payload):      return self.parse_U(payload)
    def NET_XPANID(self, payload):            return self.parse_D(payload)
    def NET_MASTER_KEY(self, payload):        return self.parse_D(payload)
    def NET_KEY_SEQUENCE(self, payload):      return self.parse_L(payload)
    def NET_PARTITION_ID(self, payload):      return self.parse_L(payload)

    def THREAD_LEADER_ADDR(self, payload):    return self.parse_6(payload)
    def THREAD_PARENT(self, payload):         pass
    def THREAD_CHILD_TABLE(self, payload):    pass

    def THREAD_LEADER_RID(self, payload):     return self.parse_C(payload)
    def THREAD_LEADER_WEIGHT(self, payload):  return self.parse_C(payload)
    def THREAD_LOCAL_LEADER_WEIGHT(self, payload): return self.parse_C(payload)

    def THREAD_NETWORK_DATA(self, payload):          pass
    def THREAD_NETWORK_DATA_VERSION(self, payload):  pass
    def THREAD_STABLE_NETWORK_DATA(self, payload):   pass
    def THREAD_STABLE_NETWORK_DATA_VERSION(self, payload): pass
    def THREAD_ON_MESH_NETS(self, payload):          pass
    def THREAD_LOCAL_ROUTES(self, payload):          pass
    def THREAD_ASSISTING_PORTS(self, payload):       pass
    def THREAD_ALLOW_LOCAL_NET_DATA_CHANGE(self, payload): pass
    def THREAD_MODE(self, payload):            return self.parse_C(payload)

    def THREAD_CHILD_TIMEOUT(self, payload):   return self.parse_L(payload)
    def THREAD_RLOC16(self, payload):          return self.parse_S(payload)

    def THREAD_ROUTER_UPGRADE_THRESHOLD(self, payload): 
        return self.parse_C(payload)

    def THREAD_CONTEXT_REUSE_DELAY(self, payload):   
        return self.parse_L(payload)

    def IPV6_LL_ADDR(self, payload):          return self.parse_6(payload)
    def IPV6_ML_ADDR(self, payload):          return self.parse_6(payload)
    def IPV6_ML_PREFIX(self, payload):        return self.parse_E(payload)

    def IPV6_ADDRESS_TABLE(self, payload):    pass
    def IPV6_ROUTE_TABLE(self, payload):      pass

    def STREAM_DEBUG(self, payload):          return self.parse_U(payload)
    def STREAM_RAW(self, payload):            pass
    def STREAM_NET(self, payload):            pass
    def STREAM_NET_INSECURE(self, payload):   pass


#=========================================

class SpinelCommandHandler(SpinelCodec):

    def handle_prop(self, name, payload): 
        global gWpanApi

        (prop_op, prop_len) = self.parse_i(payload)

        try:
            handler = SPINEL_PROP_DISPATCH[prop_op]
            prop_name = handler.__name__
            prop_value = handler(payload[prop_len:])
                
            if DEBUG_LOG_PROP:
                logger.debug("PROP_VALUE_"+name+": "+prop_name+
                             " = "+str(prop_value))

            if gWpanApi: 
                gWpanApi.queue_add(prop_op, prop_value)
            else:
                print "no wpanApi"

        except:
            prop_name = "Property Unknown"
            logger.info ("\n%s (%i): " % (prop_name, prop_op))
            print traceback.format_exc()            


    def PROP_VALUE_IS(self, payload): 
        self.handle_prop("IS", payload)

    def PROP_VALUE_INSERTED(self, payload):
        self.handle_prop("INSERTED", payload)

    def PROP_VALUE_REMOVED(self, payload):
        self.handle_prop("REMOVED", payload)


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
    SPINEL_PROP_NET_ENABLED:           wpanPropHandler.NET_ENABLED,
    SPINEL_PROP_NET_STATE:             wpanPropHandler.NET_STATE,
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
    SPINEL_PROP_THREAD_ON_MESH_NETS: wpanPropHandler.THREAD_STABLE_NETWORK_DATA,
    SPINEL_PROP_THREAD_LOCAL_ROUTES: wpanPropHandler.THREAD_LOCAL_ROUTES,
    SPINEL_PROP_THREAD_ASSISTING_PORTS: wpanPropHandler.THREAD_ASSISTING_PORTS,
    SPINEL_PROP_THREAD_ALLOW_LOCAL_NET_DATA_CHANGE: wpanPropHandler.THREAD_ALLOW_LOCAL_NET_DATA_CHANGE,
    SPINEL_PROP_THREAD_MODE: wpanPropHandler.THREAD_MODE,
    SPINEL_PROP_THREAD_CHILD_TIMEOUT: wpanPropHandler.THREAD_CHILD_TIMEOUT,
    SPINEL_PROP_THREAD_RLOC16: wpanPropHandler.THREAD_RLOC16,
    SPINEL_PROP_THREAD_ROUTER_UPGRADE_THRESHOLD: wpanPropHandler.THREAD_ROUTER_UPGRADE_THRESHOLD,
    SPINEL_PROP_THREAD_CONTEXT_REUSE_DELAY: wpanPropHandler.THREAD_CONTEXT_REUSE_DELAY,

    SPINEL_PROP_IPV6_LL_ADDR:          wpanPropHandler.IPV6_LL_ADDR,
    SPINEL_PROP_IPV6_ML_ADDR:          wpanPropHandler.IPV6_ML_ADDR,
    SPINEL_PROP_IPV6_ML_PREFIX:        wpanPropHandler.IPV6_ML_PREFIX,
    SPINEL_PROP_IPV6_ADDRESS_TABLE:    wpanPropHandler.IPV6_ADDRESS_TABLE,
    SPINEL_PROP_IPV6_ROUTE_TABLE:      wpanPropHandler.IPV6_ROUTE_TABLE,

    SPINEL_PROP_STREAM_DEBUG:          wpanPropHandler.STREAM_DEBUG,
    SPINEL_PROP_STREAM_RAW:            wpanPropHandler.STREAM_RAW,
    SPINEL_PROP_STREAM_NET:            wpanPropHandler.STREAM_NET,
    SPINEL_PROP_STREAM_NET_INSECURE:   wpanPropHandler.STREAM_NET_INSECURE,
}
       
        
class WpanApi(SpinelCodec):
    """ Helper class to format wpan command packets """

    def __init__(self, stream, useHdlc=FEATURE_USE_HDLC):

        self.serial = stream

        self.useHdlc = useHdlc
        if self.useHdlc:
            self.hdlc = Hdlc(self.serial)

        # PARSER state
        self.rx_pkt = []

        # Fire up threads
        self.__is_queue = Queue.Queue()
        self.__start_reader()

    def __start_reader(self):
        """Start reader thread"""
        self._reader_alive = True
        # start serial->console thread
        self.receiver_thread = threading.Thread(target=self.serial_rx)
        self.receiver_thread.setDaemon(True)
        self.receiver_thread.start()

    def transact(self, cmd_id, payload = ""):
        pkt = self.encode(cmd_id, payload)
        if DEBUG_LOG_PKT:
            msg = "TX Pay: (%i) %s " % (len(pkt), hexify_bytes(pkt))
            logger.debug(msg)

        if self.useHdlc: pkt = self.hdlc.encode(pkt)
        self.serial_tx(pkt)

    def parse_rx(self, pkt):
        if DEBUG_LOG_PKT:
            msg = "RX Pay: (%i) %s " % (len(pkt), str(map(hexify_int,pkt)))
            logger.debug(msg)

        if not pkt: return

        length = len(pkt) - 2
        if (length < 0): return

        spkt = "".join(map(chr, pkt))
        hdr = spkt[:2]
        payload = spkt[2:]

        (header, mgmt_cmd) = unpack(">BB", hdr)

        try:
            handler = SPINEL_COMMAND_DISPATCH[mgmt_cmd]
            cmd_name = handler.__name__
            handler(payload)
            
        except:
            print traceback.format_exc()            
            cmd_name = "CB_Unknown"
            logger.info ("\n%s (%i): " % (cmd_name, mgmt_cmd))

        if DEBUG_CMD_RESPONSE:
            logger.info ("\n%s (%i): " % (cmd_name, mgmt_cmd))
            logger.info ("===> %s" % hexify_str(payload))
        
         
    def serial_tx(self, pkt):
        # Encapsulate lagging and Framer support in self.serial class.
        self.serial.write(pkt)


    def serial_rx(self):
        # Recieve thread and parser

        while 1:
            if self.useHdlc:
                self.rx_pkt = self.hdlc.collect()

            self.parse_rx(self.rx_pkt)

            # Output RX status window
            if DEBUG_TERM:
                msg = str(map(hexify_int,self.rx_pkt))
                term.print_title(["RX: "+msg])

    class PropertyItem(object):
        """ Queue item for NCP response to property commands. """
        def __init__(self, prop, value):
            self.prop = prop
            self.value = value

    def queue_add(self, prop, value):
        #print "Q add: "+str(prop)
        item = self.PropertyItem(prop, value)
        self.__is_queue.put_nowait(item)
        
    def queue_clear(self):
        with self.__is_queue.mutex:
            self.__is_queue.queue.clear()

    def queue_wait_for_prop(self, prop, timeout=1):
        try:
            item = self.__is_queue.get(True, timeout)
        except:
            return None

        while (item):
            #print "Q item: "+str(item)
            if item.prop == prop:
                return item
            if (self.__is_queue.empty()):
                return None
            else:
                item = self.__is_queue.get_nowait()
        return None

    
def DecodeBase64Option(option, opt, value):
    try:
        return base64.standard_b64decode(value)
    except TypeError:
        raise OptionValueError(
            "option %s: invalid base64 value: %r" % (opt, value))

def DecodeHexIntOption(option, opt, value):
    try:
        return int(value, 16)
    except ValueError:
        raise OptionValueError(
            "option %s: invalid value: %r" % (opt, value))

#=========================================

class ExtendedOption (Option):
    TYPES = Option.TYPES + ("base64", "hexint", )
    TYPE_CHECKER = copy(Option.TYPE_CHECKER)
    TYPE_CHECKER["base64"] = DecodeBase64Option
    TYPE_CHECKER["hexint"] = DecodeHexIntOption
 

#=========================================


class WpanDiagsCmd(Cmd, SpinelCodec):
    
    def __init__(self, device, *a, **kw):
        Cmd.__init__(self, a, kw)

        Cmd.identchars = string.ascii_letters + string.digits + '-'

        if (sys.stdin.isatty()):
            self.prompt = MASTER_PROMPT+" > "
        else:
            self.use_rawinput = 0
            self.prompt = ""
        
        WpanDiagsCmd.command_names.sort()
            
        self.historyFileName = os.path.expanduser("~/.spinel-cli-history")

        self.wpanApi = WpanApi(device)

        global gWpanApi
        gWpanApi = self.wpanApi

        try:
            import readline
            if 'libedit' in readline.__doc__:
                readline.parse_and_bind("bind ^I rl_complete")
            readline.set_completer_delims(' ')
            try:
                readline.read_history_file(self.historyFileName)
            except IOError:
                pass
        except ImportError:
            pass


 
    command_names = [
        # Shell commands
        'exit',
        'quit',
        'clear',
        'history',
        'debug',
        'debug-term',

        'v',
        'h',
        'q',
        
        # OpenThread CLI commands
        'help', 
        'channel', 
        'child', 
        'childtimeout', 
        'contextreusedelay', 
        'counter', 
        'discover', 
        'eidcache', 
        'extaddr', 
        'extpanid', 
        'ifconfig', 
        'ipaddr', 
        'keysequence', 
        'leaderdata', 
        'leaderweight', 
        'masterkey', 
        'mode', 
        'netdataregister', 
        'networkidtimeout', 
        'networkname', 
        'panid', 
        'ping', 
        'prefix', 
        'releaserouterid', 
        'rloc16', 
        'route', 
        'router', 
        'routerupgradethreshold', 
        'scan', 
        'state', 
        'thread', 
        'version', 
        'whitelist', 

        # OpenThread Diagnostics Module CLI
        'diag', 
        'diag-start', 
        'diag-channel', 
        'diag-power', 
        'diag-send', 
        'diag-repeat', 
        'diag-sleep', 
        'diag-stats', 
        'diag-stop', 

        # OpenThread Spinel-specific commands
        'enabled', 

    ]


    def log(self,text) :
        logger.info(text)

    def parseline(self, line):
        cmd, arg, line = Cmd.parseline(self, line)
        if (cmd):
            cmd = self.shortCommandName(cmd)
            line = cmd + ' ' + arg
        return cmd, arg, line
        
    def completenames(self, text, *ignored):
        return [ name + ' ' for name in WpanDiagsCmd.command_names \
                 if name.startswith(text) \
                 or self.shortCommandName(name).startswith(text) ]

    def shortCommandName(self, cmd):
        return cmd.replace('-', '')

    def precmd(self, line):
        if (not self.use_rawinput and line != 'EOF' and line != ''):
            #logger.info('>>> ' + line)
            self.log('>>> ' + line)
        return line
        
    def postcmd(self, stop, line):
        if (not stop and self.use_rawinput):
            self.prompt = MASTER_PROMPT+" > "
        return stop
    
    def postloop(self):
        try:
            import readline
            try:
                readline.write_history_file(self.historyFileName)
            except IOError:
                pass
        except ImportError:
            pass


    def prop_get_value(self, prop_id):
        """ Blocking routine to get a property value over Spinel. """
        self.wpanApi.queue_clear()

        pay = self.encode_i(prop_id)
        self.wpanApi.transact(SPINEL_CMD_PROP_VALUE_GET, pay)

        result = self.wpanApi.queue_wait_for_prop(prop_id)
        if result: 
            return result.value
        else:
            return None

    def __prop_change_value(self, cmd, prop_id, value, format='B'):
        """ Utility routine to change a property value over Spinel. """
        self.wpanApi.queue_clear()

        pay = self.encode_i(prop_id)
        if format != None:
            pay += pack(format, value)
        self.wpanApi.transact(cmd, pay)

        result = self.wpanApi.queue_wait_for_prop(prop_id)
        if result:
            return result.value
        else:
            return None

    def prop_set_value(self, prop_id, value, format='B'):
        """ Blocking routine to set a property value over Spinel. """
        return self.__prop_change_value(SPINEL_CMD_PROP_VALUE_SET, prop_id, 
                                        value, format)

    def prop_insert_value(self, prop_id, value, format='B'):
        """ Blocking routine to insert a property value over Spinel. """
        return self.__prop_change_value(SPINEL_CMD_PROP_VALUE_INSERT, prop_id, 
                                        value, format)
        
    def prop_remove_value(self, prop_id, value, format='B'):
        """ Blocking routine to remove a property value over Spinel. """
        return self.__prop_change_value(SPINEL_CMD_PROP_VALUE_REMOVE, prop_id, 
                                        value, format)

    def prop_get_or_set_value(self, prop_id, line, format='B'):
        """ Helper to get or set a property value based on line arguments. """
        if line:
            value = self.prop_set_value(prop_id, int(line), format)
        else:    
            value = self.prop_get_value(prop_id)
        return value

    def prep_line(self, line):
        """ Convert a line argument to proper type """
        if line != None: 
            line = int(line)
        return line

    def prop_get(self, prop_id, format='B'):
        """ Helper to get a propery and output the value with Done or Error. """
        value = self.prop_get_value(prop_id)
        if value == None:
            print "Error"
            return None
            
        if (format == 'D') or (format == 'E'):
            print hexify_str(value,'')
        else:
            print str(value)
        print "Done"

        return value

    def prop_set(self, prop_id, line, format='B'):        
        """ Helper to set a propery and output Done or Error. """
        arg = self.prep_line(line)
        value = self.prop_set_value(prop_id, arg, format)

        if (value == None):
            print "Error"
        else:
            print "Done"

        return value

    def handle_property(self, line, prop_id, format='B', output=True):
        value = self.prop_get_or_set_value(prop_id, line, format)
        if not output: return value

        if value == None:
            print "Error"
            return None

        if not line:
            # Only print value on PROP_VALUE_GET
            if (format == 'D') or (format == 'E'):
                print hexify_str(value,'')
            else:
                print str(value)

        print "Done"
        return value


    def do_help(self, line):
        if (line):
            cmd, arg, unused = self.parseline(line)
            try:
                doc = getattr(self, 'do_' + cmd).__doc__
            except AttributeError:
                doc = None
            if doc:
                self.log("%s\n" % textwrap.dedent(doc))
            else:
                self.log("No help on %s\n" % (line))
        else:
            self.print_topics("\nAvailable commands (type help <name> for more information):", WpanDiagsCmd.command_names, 15, 80)
            
        
    def do_v(self, line):
        """
        version
            Shows detailed version information on spinel-cli tool:
        """
        logger.info(MASTER_PROMPT+" ver. "+__version__)
        logger.info(__copyright__)


    def do_clear(self, line):
        """ Clean up the display. """
        os.system('reset')


    def do_history(self, line):
        """
        history
          
          Show previously executed commands.
        """

        try:
            import readline
            h = readline.get_current_history_length()
            for n in range(1,h+1):
                logger.info(readline.get_history_item(n))
        except ImportError:
            pass


    def do_h(self, line):
        self.do_history(line)


    def do_exit(self, line):
        logger.info("exit")
        return True

    
    def do_quit(self, line):
        logger.info("quit")
        return True


    def do_q(self, line):
        return True


    def do_EOF(self, line):
        self.log("\n")
        return True


    def emptyline(self):
        pass


    def default(self, line):
        if line[0] == "#":
            logger.debug(line)
        else:
            logger.info(line + ": command not found")
            #exec(line)


    def diags_cmd_parse(self, line):
        args = shlex.split(line)
        optParser = OptionParser(usage=optparse.SUPPRESS_USAGE, 
                                 option_class=ExtendedOption)
        optParser.add_option("-n", "--name", action="store", 
                             dest="nodeName", type="string")
        optParser.add_option("-l", "--log", action="store_true", dest="log")
        optParser.add_option("-q", "--quiet", action="store_true", dest="quiet")
        optParser.add_option("-v", "--verbose", action="store_true",
                             dest="verbose")

        try:
            (options, remainingArgs) = optParser.parse_args(args)
        except SystemExit:
            return

        # First argument is <nodeName>, then <["cmd with args"]>
        if (remainingArgs): 
            options.nodeName = remainingArgs[0]
            options.cmd = subprocess.list2cmdline(remainingArgs[1:])

        # Merge default options
        nodeName = options.nodeName
        if not nodeName: return options

        return options

    def do_debug(self, line):
        """
        Enables detail logging of bytes over the wire to the radio modem.
        Usage: debug <1=enable | 0=disable>
        """
        global DEBUG_ENABLE, DEBUG_LOG_PKT, DEBUG_LOG_PROP
        global DEBUG_LOG_TX, DEBUG_LOG_RX

        if line: line = int(line)
        if line:
            DEBUG_ENABLE = 1
        else:
            DEBUG_ENABLE = 0
        #DEBUG_LOG_TX = DEBUG_ENABLE
        DEBUG_LOG_PKT = DEBUG_ENABLE
        DEBUG_LOG_PROP = DEBUG_ENABLE
        print "DEBUG_ENABLE = "+str(DEBUG_ENABLE)

    def do_debugterm(self, line):
        """
        Enables a debug terminal display in the title bar for viewing 
        raw NCP packets.
        Usage: debug_term <1=enable | 0=disable>
        """
        global DEBUG_TERM
        if line: line = int(line)
        if line: 
            DEBUG_TERM = 1
        else:
            DEBUG_TERM = 0


    def do_channel(self, line):
        """
        \033[1mchannel\033[0m

            Get the IEEE 802.15.4 Channel value.
        \033[2m
            > channel
            11
            Done
        \033[0m
        \033[1mchannel <channel>\033[0m

            Set the IEEE 802.15.4 Channel value.        
        \033[2m
            > channel 11
            Done
        \033[0m
        """
        self.handle_property(line, SPINEL_PROP_PHY_CHAN)

    def do_child(self, line): 
        """\033[1m
        child list
        \033[0m
            List attached Child IDs
        \033[2m
            > child list
            1 2 3 6 7 8
            Done
        \033[0m\033[1m
        child <id>
        \033[0m
            Print diagnostic information for an attached Thread Child. 
            The id may be a Child ID or an RLOC16.
        \033[2m
            > child 1
            Child ID: 1
            Rloc: 9c01
            Ext Addr: e2b3540590b0fd87
            Mode: rsn
            Net Data: 184
            Timeout: 100
            Age: 0
            LQI: 3
            RSSI: -20
            Done        
        \033[0m
        """
        pass

    def do_childtimeout(self, line): 
        """\033[1m
        childtimeout
        \033[0m
            Get the Thread Child Timeout value.
        \033[2m
            > childtimeout
            300
            Done
        \033[0m\033[1m
        childtimeout <timeout>
        \033[0m
            Set the Thread Child Timeout value.
        \033[2m
            > childtimeout 300
            Done
        \033[0m
        """
        self.handle_property(line, SPINEL_PROP_THREAD_CHILD_TIMEOUT, 'L')

    def do_contextreusedelay(self, line):
        """
        contextreusedelay

            Get the CONTEXT_ID_REUSE_DELAY value.

            > contextreusedelay
            11
            Done

        contextreusedelay <delay>

            Set the CONTEXT_ID_REUSE_DELAY value.

            > contextreusedelay 11
            Done
        """
        self.handle_property(line, SPINEL_PROP_THREAD_CONTEXT_REUSE_DELAY, 'L')

    def do_counter(self, line): 
        """
        counter

            Get the supported counter names.

            >counter
            mac
            Done

        counter <countername>
        
            Get the counter value.

            >counter mac
            TxTotal: 10
            TxAckRequested: 4
            TxAcked: 4
            TxNoAckRequested: 6
            TxData: 10
            TxDataPoll: 0
            TxBeacon: 0
            TxBeaconRequest: 0
            TxOther: 0
            TxRetry: 0
            TxErrCca: 0
            RxTotal: 11
            RxData: 11
            RxDataPoll: 0
            RxBeacon: 0
            RxBeaconRequest: 0
            RxOther: 0
            RxWhitelistFiltered: 0
            RxDestAddrFiltered: 0
            RxErrNoFrame: 0
            RxErrNoUnknownNeighbor: 0
            RxErrInvalidSrcAddr: 0
            RxErrSec: 0
            RxErrFcs: 0
            RxErrOther: 0
        """
        pass 

    def do_discover(self, line):
        """
        discover [channel]

             Perform an MLE Discovery operation.

        channel: The channel to discover on. If no channel is provided, the discovery will cover all valid channels.
        > discover
        | J | Network Name     | Extended PAN     | PAN  | MAC Address      | Ch | dBm | LQI |
        +---+------------------+------------------+------+------------------+----+-----+-----+
        | 0 | OpenThread       | dead00beef00cafe | ffff | f1d92a82c8d8fe43 | 11 | -20 |   0 |
        Done
        """
        pass 

    def do_eidcache(self, line): 
        """
        eidcache

            Print the EID-to-RLOC cache entries.

            > eidcache
            fdde:ad00:beef:0:bb1:ebd6:ad10:f33 ac00
            fdde:ad00:beef:0:110a:e041:8399:17cd 6000
            Done
        """
        pass 

    def do_extaddr(self, line):
        """
        extaddr

            Get the IEEE 802.15.4 Extended Address.

            > extaddr
            dead00beef00cafe
            Done

        extaddr <extaddr>

            Set the IEEE 802.15.4 Extended Address.

            > extaddr dead00beef00cafe
            dead00beef00cafe
            Done
        """
        self.handle_property(line, SPINEL_PROP_MAC_15_4_LADDR, 'E')

    def do_extpanid(self, line):
        """
        extpanid

            Get the Thread Extended PAN ID value.

            > extpanid
            dead00beef00cafe
            Done

        extpanid <extpanid>
        
            Set the Thread Extended PAN ID value.
        
            > extpanid dead00beef00cafe
            Done        
        """
        self.handle_property(line, SPINEL_PROP_NET_XPANID, 'D')

    def do_ifconfig(self, line): 
        """
        ifconfig up
        
            Bring up the IPv6 interface.
        
            > ifconfig up
            Done

        ifconfig down
        
            Bring down the IPv6 interface.
        
            > ifconfig down
            Done

        ifconfig
        
            Show the status of the IPv6 interface.
        
            > ifconfig
            down
            Done
        """

        IFCONFIG_MAP_VALUE = {
            0: "down",
            1: "up",
            2: "up",
            3: "up",
        }

        IFCONFIG_MAP_NAME = {
            "down": 0,
            "up": 1,
        }

        if line:
            try:
                # remap string state names to integer
                line = IFCONFIG_MAP_NAME[line]
            except:
                print("Error")
                return

        result = self.prop_get_or_set_value(SPINEL_PROP_NET_STATE, line)
        if result != None:
            if not line:
                print IFCONFIG_MAP_VALUE[result]
            print("Done")
        else:
            print("Error")

    def do_ipaddr(self, line): 
        """
        ipaddr

            List all IPv6 addresses assigned to the Thread interface.

            > ipaddr
            fdde:ad00:beef:0:0:ff:fe00:0
            fe80:0:0:0:0:ff:fe00:0
            fdde:ad00:beef:0:558:f56b:d688:799
            fe80:0:0:0:f3d9:2a82:c8d8:fe43
            Done

        ipaddr add <ipaddr>
        
            Add an IPv6 address to the Thread interface.

            > ipaddr add 2001::dead:beef:cafe
            Done

        ipaddr del <ipaddr>
        
            Delete an IPv6 address from the Thread interface.
        
            > ipaddr del 2001::dead:beef:cafe
            Done
        """
        self.handle_property(line, SPINEL_PROP_IPV6_LL_ADDR)
        self.handle_property(line, SPINEL_PROP_IPV6_ML_ADDR)

    def do_keysequence(self, line): 
        """
        keysequence

            Get the Thread Key Sequence.

            > keysequence
            10
            Done

        keysequence <keysequence>

            Set the Thread Key Sequence.

            > keysequence 10
            Done
        """
        self.handle_property(line, SPINEL_PROP_NET_KEY_SEQUENCE)

    def do_leaderdata(self, line): 
        pass 

    def do_leaderweight(self, line):
        """
        leaderweight

            Get the Thread Leader Weight.

            > leaderweight
            128
            Done

        leaderweight <weight>
        
            Set the Thread Leader Weight.
        
            > leaderweight 128
            Done
        """
        self.handle_property(line, SPINEL_PROP_THREAD_LEADER_WEIGHT)

    def do_masterkey(self, line): 
        """
        masterkey
        
            Get the Thread Master Key value.
        
            > masterkey
            00112233445566778899aabbccddeeff
            Done

        masterkey <key>
        
            Set the Thread Master Key value.
        
            > masterkey 00112233445566778899aabbccddeeff
            Done
        """
        pass 

    def do_mode(self, line): 
        """
        mode
        
            Get the Thread Device Mode value.
        
              r: rx-on-when-idle
              s: Secure IEEE 802.15.4 data requests
              d: Full Function Device
              n: Full Network Data

            > mode
            rsdn
            Done

        mode [rsdn]

            Set the Thread Device Mode value.

              r: rx-on-when-idle
              s: Secure IEEE 802.15.4 data requests
              d: Full Function Device
              n: Full Network Data

            > mode rsdn
            Done
        """
        THREAD_MODE_MAP_VALUE = {
            0x00: "0",
            0x01: "n",
            0x02: "d",
            0x03: "dn",
            0x04: "s",
            0x05: "sn",
            0x06: "sd",
            0x07: "sdn",
            0x08: "r",
            0x09: "rn",
            0x0A: "rd",
            0x0B: "rdn",
            0x0C: "rs",
            0x0D: "rsn",
            0x0E: "rsd",
            0x0F: "rsdn",
        }

        THREAD_MODE_MAP_NAME = {
            "0": 0x00,
            "n": 0x01,
            "d": 0x02,
            "dn": 0x03,
            "s": 0x04,
            "sn": 0x05,
            "sd": 0x06,
            "sdn": 0x07,
            "r": 0x08,
            "rn": 0x09,
            "rd": 0x0A,
            "rdn": 0x0B,
            "rs": 0x0C,
            "rsn": 0x0D,
            "rsd": 0x0E,
            "rsdn": 0x0F
        }

        if line:
            try:
                # remap string state names to integer
                line = THREAD_MODE_MAP_NAME[line]
            except:
                print("Error")
                return

        result = self.prop_get_or_set_value(SPINEL_PROP_THREAD_MODE, line)
        if result != None:
            if not line:
                print THREAD_MODE_MAP_VALUE[result]
            print("Done")
        else:
            print("Error")


    def do_netdataregister(self, line): 
        """
        netdataregister

            Register local network data with Thread Leader.

            > netdataregister
            Done
        """
        pass 

    def do_networkidtimeout(self, line): 
        """
        networkidtimeout

            Get the NETWORK_ID_TIMEOUT parameter used in the Router role.

            > networkidtimeout
            120
            Done

        networkidtimeout <timeout>
        
            Set the NETWORK_ID_TIMEOUT parameter used in the Router role.
        
            > networkidtimeout 120
            Done
        """
        pass 

    def do_networkname(self, line): 
        """
        networkname

            Get the Thread Network Name.

            > networkname
            OpenThread
            Done

        networkname <name>
        
            Set the Thread Network Name.
        
            > networkname OpenThread
            Done
        """
        pass 

    def do_panid(self, line):
        """
        panid

            Get the IEEE 802.15.4 PAN ID value.

            > panid
            0xdead
            Done
        
        panid <panid>
        
            Set the IEEE 802.15.4 PAN ID value.
        
            > panid 0xdead
            Done
        """
        self.handle_property(line, SPINEL_PROP_MAC_15_4_PANID, 'H')

    def do_ping(self, line): 
        """
        ping <ipaddr> [size] [count] [interval]

            Send an ICMPv6 Echo Request.

            > ping fdde:ad00:beef:0:558:f56b:d688:799
            16 bytes from fdde:ad00:beef:0:558:f56b:d688:799: icmp_seq=1 hlim=64 time=28ms
        """
        pass 

    def do_prefix(self, line): 
        """
        prefix add <prefix> [pvdcsr] [prf]
        
            Add a valid prefix to the Network Data.
        
              p: Preferred flag
              a: Stateless IPv6 Address Autoconfiguration flag
              d: DHCPv6 IPv6 Address Configuration flag
              c: DHCPv6 Other Configuration flag
              r: Default Route flag
              o: On Mesh flag
              s: Stable flag
              prf: Default router preference, which may be 'high', 'med', or 'low'.
            > prefix add 2001:dead:beef:cafe::/64 paros med
            Done

        prefix remove <prefix>
        
            Invalidate a prefix in the Network Data.

            > prefix remove 2001:dead:beef:cafe::/64
            Done
        """
        pass 

    def do_releaserouterid(self, line): 
        """
        releaserouterid <routerid>

            Release a Router ID that has been allocated by the device in the Leader role.
        
            > releaserouterid 16
            Done
        """
        pass 

    def do_rloc16(self, line):
        """
        rloc16

            Get the Thread RLOC16 value.

            > rloc16
            0xdead
            Done
        """
        self.handle_property(line, SPINEL_PROP_THREAD_RLOC16, 'H')

    def do_route(self, line):
        """
        route add <prefix> [s] [prf]

            Add a valid prefix to the Network Data.

              s: Stable flag
              prf: Default Router Preference, which may be: 'high', 'med', or 'low'.

            > route add 2001:dead:beef:cafe::/64 s med
            Done

        route remove <prefix>
        
            Invalidate a prefix in the Network Data.

            > route remove 2001:dead:beef:cafe::/64
            Done
        """
        pass 

    def do_router(self, line): 
        """
        router list

            List allocated Router IDs
        
            > router list
            8 24 50
            Done

        router <id>
        
            Print diagnostic information for a Thread Router. The id may be a Router ID or an RLOC16.

            > router 50
            Alloc: 1
            Router ID: 50
            Rloc: c800
            Next Hop: c800
            Link: 1
            Ext Addr: e2b3540590b0fd87
            Cost: 0
            LQI In: 3
            LQI Out: 3
            Age: 3
            Done

            > router 0xc800
            Alloc: 1
            Router ID: 50
            Rloc: c800
            Next Hop: c800
            Link: 1
            Ext Addr: e2b3540590b0fd87
            Cost: 0
            LQI In: 3
            LQI Out: 3
            Age: 7
            Done
        """
        pass 

    def do_routerupgradethreshold(self, line):
        """
        routerupgradethreshold

            Get the ROUTER_UPGRADE_THRESHOLD value.

            > routerupgradethreshold
            16
            Done

        routerupgradethreshold <threshold>
        
            Set the ROUTER_UPGRADE_THRESHOLD value.
        
            > routerupgradethreshold 16
            Done        
        """
        self.handle_property(line, SPINEL_PROP_THREAD_ROUTER_UPGRADE_THRESHOLD)

    def do_scan(self, line):
        """
        scan [channel]
        
            Perform an IEEE 802.15.4 Active Scan.
        
              channel: The channel to scan on. If no channel is provided, the active scan will cover all valid channels.

            > scan
            | J | Network Name     | Extended PAN     | PAN  | MAC Address      | Ch | dBm | LQI |
            +---+------------------+------------------+------+------------------+----+-----+-----+
            | 0 | OpenThread       | dead00beef00cafe | ffff | f1d92a82c8d8fe43 | 11 | -20 |   0 |
        Done
        """
        # Initial mock-up of scan
        self.handle_property("15", SPINEL_PROP_MAC_SCAN_MASK)
        self.handle_property("4", SPINEL_PROP_MAC_SCAN_PERIOD, 'H')
        self.handle_property("1", SPINEL_PROP_MAC_SCAN_STATE)
        import time
        time.sleep(5) 
        self.handle_property("", SPINEL_PROP_MAC_SCAN_BEACON, 'U')
        

    def do_enabled(self, line): 
        """ Specifies whether Thread Network interface is enabled. """
        self.handle_property(line, SPINEL_PROP_NET_ENABLED)

    def do_thread(self, line):
        """
        thread start

            Enable Thread protocol operation and attach to a Thread network.

            > thread start
            Done

        thread stop
        
            Disable Thread protocol operation and detach from a Thread network.
        
            > thread stop
            Done
        """
        ARG_MAP_VALUE = {
            0: "stop",
            1: "start",
            2: "start",
            3: "start",
        }

        ARG_MAP_NAME = {
            "stop": "0",
            "start": "2",
        }

        if line:
            try:
                # remap string state names to integer
                line = ARG_MAP_NAME[line]
            except:
                print("Error")
                return

        result = self.prop_get_or_set_value(SPINEL_PROP_NET_STATE, line)
        if result != None:
            if not line:
                print ARG_MAP_VALUE[result]
            print("Done")
        else:
            print("Error")

    def do_state(self, line): 
        ROLE_MAP_VALUE = {
            0: "detached",
            1: "child",
            2: "router",
            3: "leader",
        }

        ROLE_MAP_NAME = {
            "disabled": "0",
            "detached": "0",
            "child": "1",
            "router": "2",
            "leader": "3",
        }

        if line:
            try:
                # remap string state names to integer
                line = ROLE_MAP_NAME[line]
            except:
                print("Error")
                return

        result = self.prop_get_or_set_value(SPINEL_PROP_NET_ROLE, line)
        if result != None:
            if not line:
                state = ROLE_MAP_VALUE[result] 
                # TODO: if state="disabled": get NET_STATE to determine 
                #       whether "disabled" or "detached"
                print state
            print("Done")
        else:
            print("Error")

    def do_version(self, line):
        """
        version

            Print the build version information.
        
            > version
            OPENTHREAD/gf4f2f04; Jul  1 2016 17:00:09
            Done
        """
        self.handle_property(line, SPINEL_PROP_NCP_VERSION, 'U')

    def do_whitelist(self, line):
        """
        whitelist

            List the whitelist entries.

            > whitelist
            Enabled
            e2b3540590b0fd87
            d38d7f875888fccb
            c467a90a2060fa0e
            Done

        whitelist add <extaddr>
        
            Add an IEEE 802.15.4 Extended Address to the whitelist.
        
            > whitelist add dead00beef00cafe
            Done

        whitelist clear
        
            Clear all entries from the whitelist.
        
            > whitelist clear
            Done

        whitelist disable
        
            Disable MAC whitelist filtering.
        
            > whitelist disable
            Done

        whitelist enable
        
            Enable MAC whitelist filtering.
        
            > whitelist enable
            Done

        whitelist remove <extaddr>
        
            Remove an IEEE 802.15.4 Extended Address from the whitelist.
        
            > whitelist remove dead00beef00cafe
            Done
        """
        ARG_MAP_VALUE = {
            0: "Disabled",
            1: "Enabled",
        }

        args = line.split(" ")

        if args[0] == "":
            value = self.prop_get_value(SPINEL_PROP_MAC_WHITELIST_ENABLED)
            if value != None:
                print ARG_MAP_VALUE[value]
            value = self.prop_get_value(SPINEL_PROP_MAC_WHITELIST)

        elif args[0] == "enable":
            self.prop_set(SPINEL_PROP_MAC_WHITELIST_ENABLED, '1')
            return

        elif args[0] == "disable":
            self.prop_set(SPINEL_PROP_MAC_WHITELIST_ENABLED, '0')
            return

        elif args[0] == "clear":
            value = self.prop_insert_value(SPINEL_PROP_MAC_WHITELIST, None, 
                                           None)

        elif args[0] == "add":
            arr = hex_to_bytes(args[1])            
            arr += pack('b', SPINEL_RSSI_OVERRIDE)
            value = self.prop_insert_value(SPINEL_PROP_MAC_WHITELIST, arr, 
                                           str(len(arr))+'s')

        elif args[0] == "remove":
            arr = hex_to_bytes(args[1])
            arr += pack('b', SPINEL_RSSI_OVERRIDE)
            value = self.prop_remove_value(SPINEL_PROP_MAC_WHITELIST, arr,
                                           str(len(arr))+'s')
        
        print("Done")


    def do_diag(self, line):
        """
        diag

            Show diagnostics mode status.

            > diag
            diagnostics mode is disabled
        """
        pass

    def do_diagstart(self, line):
        """
        diag-start

            Start diagnostics mode.

            > diag-start
            start diagnostics mode
            status 0x00
        """
        pass
        
    def do_diagchannel(self, line):
        """
        diag-channel

            Get the IEEE 802.15.4 Channel value for diagnostics module.
        
            > diag-channel
            channel: 11

        diag-channel <channel>
        
            Set the IEEE 802.15.4 Channel value for diagnostics module.
        
            > diag-channel 11
            set channel to 11
            status 0x00
        """
        pass

    def do_diagpower(self, line):
        """
        diag-power

            Get the tx power value(dBm) for diagnostics module.

            > diag-power
            tx power: -10 dBm

        diag-power <power>
        
            Set the tx power value(dBm) for diagnostics module.
        
            > diag-power -10
            set tx power to -10 dBm
            status 0x00
        """
        pass

    def do_diagsend(self, line):
        """
        diag-send <packets> <length>

            Transmit a fixed number of packets with fixed length.
        
            > diag-send 20 100
            sending 0x14 packet(s), length 0x64
            status 0x00
        """
        pass

    def do_diagrepeat(self, line):
        """
        diag-repeat <delay> <length>

            Transmit packets repeatedly with a fixed interval.

            > diag repeat 100 100
            sending packets of length 0x64 at the delay of 0x64 ms
            status 0x00

        diag-repeat stop

            Stop repeated packet transmission.
        
            > diag-repeat stop
            repeated packet transmission is stopped
            status 0x00
        """
        pass

    def do_diagsleep(self, line):
        """
        diag-sleep

            Enter radio sleep mode.
        
            > diag-sleep
            sleeping now...
        """
        pass

    def do_diagstats(self, line):
        """
        diag-stats

            Print statistics during diagnostics mode.
        
            > diag-stats
            received packets: 10
            sent packets: 10
            first received packet: rssi=-65, lqi=101
        """
        pass

    def do_diagstop(self, line):
        """
        diag stop

            Stop diagnostics mode and print statistics.
        
            > diag-stop
            received packets: 10
            sent packets: 10
            first received packet: rssi=-65, lqi=101
        
            stop diagnostics mode
            status 0x00
        """
        pass



import atexit
@atexit.register
def goodbye():
    print "Warning: some lingering processes may exist.  Goodbye."

if __name__ == "__main__":

    args = sys.argv[1:] 

    optParser = OptionParser()

    optParser = OptionParser(usage=optparse.SUPPRESS_USAGE, 
                             option_class=ExtendedOption)
    optParser.add_option("-u", "--uart", action="store", 
                         dest="uart", type="string")
    optParser.add_option("-p", "--pipe", action="store", 
                         dest="pipe", type="string")
    optParser.add_option("-s", "--socket", action="store", 
                         dest="socket", type="string")
    optParser.add_option("-n", "--nodeid", action="store", 
                         dest="nodeid", type="string")
    optParser.add_option("-q", "--quiet", action="store_true", dest="quiet")
    optParser.add_option("-v", "--verbose", action="store_false",dest="verbose")

    (options, remainingArgs) = optParser.parse_args(args)
        

    # Set default stream to pipe
    streamType = 'p'
    streamDescriptor = "../../examples/apps/ncp/ot-ncp 1"
            
    if options.uart: 
        streamType = 'u'
        streamDescriptor = options.uart
    elif options.socket:
        streamType = 's'
        streamDescriptor = options.socket
    elif options.pipe:
        streamType = 'p'
        streamDescriptor = options.pipe
        if options.nodeid: streamDescriptor += " "+str(options.nodeid)
    else:
        if len(args) > 0: 
            streamDescriptor = " ".join(remainingArgs)

    stream = StreamOpen(streamType, streamDescriptor)
    shell = WpanDiagsCmd(stream)

    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        logger.info('\nQuitting')

    shell.wpanApi.serial.close()
