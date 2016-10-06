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
"""
spinel-cli.py

available commands (type help <name> for more information):
============================================================
channel            diag-sleep  keysequence       q
child              diag-start  leaderdata        quit
childtimeout       diag-stats  leaderweight      releaserouterid
clear              diag-stop   masterkey         rloc16
commissioner       discover    mode              route
contextreusedelay  eidcache    ncp-ll64          router
counter            exit        ncp-ml64          routerupgradethreshold
debug              extaddr     ncp-tun           scan
debug-mem          extpanid    netdataregister   state
diag               h           networkidtimeout  thread
diag-channel       help        networkname       tun
diag-power         history     panid             v
diag-repeat        ifconfig    ping              version
diag-send          ipaddr      prefix            whitelist
"""

__copyright__   = "Copyright (c) 2016 The OpenThread Authors."
__version__     = "0.1.0"

import os
import sys
import time
import traceback

import optparse

import string
import textwrap
import ipaddress
import binascii

import logging
import logging.config
import logging.handlers

from cmd import Cmd
from copy import copy
from struct import pack
from struct import unpack

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
from scapy.layers.inet6 import IPv6
from scapy.layers.inet6 import ICMPv6EchoRequest
from scapy.layers.inet6 import ICMPv6EchoReply

from spinel.codec import *
import spinel.util as util
import spinel.config as CONFIG
from spinel.stream import StreamOpen
from spinel.hdlc import Hdlc
from spinel.tun import TunInterface

MASTER_PROMPT  = "spinel-cli"

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


class SpinelCliCmd(Cmd, SpinelCodec):

    def __init__(self, device, nodeid, *a, **kw):

        self.wpanApi = WpanApi(device, nodeid)
        self.wpanApi.queue_register(SPINEL_HEADER_DEFAULT)

        Cmd.__init__(self)
        Cmd.identchars = string.ascii_letters + string.digits + '-'

        if (sys.stdin.isatty()):
            self.prompt = MASTER_PROMPT+" > "
        else:
            self.use_rawinput = 0
            self.prompt = ""

        SpinelCliCmd.command_names.sort()

        self.historyFileName = os.path.expanduser("~/.spinel-cli-history")

        try:
            import readline
            try:
                readline.read_history_file(self.historyFileName)
            except IOError:
                pass
        except ImportError:
            print "Module readline unavailable"
        else:
            import rlcompleter
            readline.parse_and_bind("tab: complete")
            if sys.platform == 'darwin':
                readline.parse_and_bind("bind ^I rl_complete")

        self.nodeid = kw.get('nodeid','1')
        self.prop_set_value(SPINEL_PROP_IPv6_ICMP_PING_OFFLOAD, 1)
        self.prop_set_value(SPINEL_PROP_THREAD_RLOC16_DEBUG_PASSTHRU, 1)


    command_names = [
        # Shell commands
        'exit',
        'quit',
        'clear',
        'history',
        'debug',
        'debug-mem',

        'v',
        'h',
        'q',

        # OpenThread CLI commands
        'help',
        'channel',
        'child',
        'childtimeout',
        'commissioner',
        'contextreusedelay',
        'counter',
        'discover',
        'eidcache',
        'extaddr',
        'extpanid',
        'ifconfig',
        'ipaddr',
        'joiner',
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
        'routerselectionjitter',
        'routerupgradethreshold',
        'routerdowngradethreshold',
        'scan',
        'state',
        'thread',
        'tun',
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
        'ncp-ml64',
        'ncp-ll64',
        'ncp-tun',

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
        return [ name + ' ' for name in SpinelCliCmd.command_names \
                 if name.startswith(text) \
                 or self.shortCommandName(name).startswith(text) ]

    def shortCommandName(self, cmd):
        return cmd.replace('-', '')

    def postloop(self):
        try:
            import readline
            try:
                readline.write_history_file(self.historyFileName)
            except IOError:
                pass
        except ImportError:
            pass

    def prop_get_value(self, propId):
        return self.wpanApi.prop_get_value(propId)

    def prop_set_value(self, propId, value, pyFormat='B'):
        return self.wpanApi.prop_set_value(propId, value, pyFormat)

    def prop_insert_value(self, propId, value, pyFormat='B'):
        return self.wpanApi.prop_insert_value(propId, value, pyFormat)

    def prop_remove_value(self, propId, value, pyFormat='B'):
        return self.wpanApi.prop_remove_value(propId, value, pyFormat)

    def prop_get_or_set_value(self, propId, line, format='B'):
        """ Helper to get or set a property value based on line arguments. """
        if line:
            value = self.prep_line(line, format)
            pyFormat = self.prep_format(value, format)
            value = self.prop_set_value(propId, value, pyFormat)
        else:
            value = self.prop_get_value(propId)
        return value

    def prep_line(self, line, format='B'):
        """ Convert a command line argument to proper binary encoding (pre-pack). """
        value = line
        if line != None:
            if format=='U':         # For UTF8, just a pass through line unmodified
                value = line.encode('utf-8')+'\0'
            elif format == 'D':     # Expect raw data to be hex string w/o delimeters
                value = util.hex_to_bytes(line)
            else:
                value = int(line)   # Most everything else is some type of integer
        return value

    def prep_format(self, value, format='B'):
        """ Convert a spinel format to a python pack format. """
        pyFormat = format
        if value == "":
            pyFormat = '0s'
        elif format=='D' or format=='U':
            pyFormat = str(len(value))+'s'
        return pyFormat

    def prop_get(self, propId, format='B'):
        """ Helper to get a propery and output the value with Done or Error. """
        value = self.prop_get_value(propId)
        if value == None:
            print("Error")
            return None

        if (format == 'D') or (format == 'E'):
            print util.hexify_str(value,'')
        else:
            print str(value)
        print("Done")

        return value

    def prop_set(self, propId, line, format='B'):
        """ Helper to set a propery and output Done or Error. """
        value = self.prep_line(line, format)
        pyFormat = self.prep_format(value, format)
        result = self.prop_set_value(propId, value, pyFormat)

        if (result == None):
            print("Error")
        else:
            print("Done")

        return result

    def handle_property(self, line, propId, format='B', output=True):
        value = self.prop_get_or_set_value(propId, line, format)
        if not output: return value

        if value == None or value == "":
            print("Error")
            return None

        if line == None or line == "":
            # Only print value on PROP_VALUE_GET
            if (format == '6'):
                print str(ipaddress.IPv6Address(value))
            elif (format == 'D') or (format == 'E'):
                print util.hexify_str(value,'')
            else:
                print str(value)

        print("Done")
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
            self.print_topics("\nAvailable commands (type help <name> for more information):", SpinelCliCmd.command_names, 15, 80)


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
        #goodbye()
        return True


    def emptyline(self):
        pass

    def default(self, line):
        if line[0] == "#":
            logger.debug(line)
        else:
            logger.info(line + ": command not found")
            #exec(line)


    def do_debug(self, line):
        """
        Enables detail logging of bytes over the wire to the radio modem.
        Usage: debug <1=enable | 0=disable>
        """

        if line != None and line != "":
            level = int(line)
        else:
            level = 0
        
        CONFIG.DebugSetLevel(level)

    def do_debugmem(self, line):
        from guppy import hpy
        h = hpy()
        print h.heap()
        print
        print h.heap().byrcs


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

    def do_commissioner(self, line):
        """
        These commands are enabled when configuring with --enable-commissioner.

        \033[1m
        commissioner start
        \033[0m
            Start the Commissioner role on this node.
        \033[2m
            > commissioner start
            Done
        \033[0m\033[1m
        commissioner stop
        \033[0m
            Stop the Commissioner role on this node.
        \033[2m
            > commissioner stop
            Done
        \033[0m\033[1m
        commissioner panid <panid> <mask> <destination>
        \033[0m
            Perform panid query.
        \033[2m
            > commissioner panid 57005 4294967295 ff33:0040:fdde:ad00:beef:0:0:1
            Conflict: dead, 00000800
            Done
        \033[0m\033[1m
        commissioner energy <mask> <count> <period> <scanDuration>
        \033[0m
            Perform energy scan.
        \033[2m
            > commissioner energy 327680 2 32 1000 fdde:ad00:beef:0:0:ff:fe00:c00
            Energy: 00050000 0 0 0 0
            Done
        \033[0m
        """
        pass

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


    def do_joiner(self, line):
        """
        These commands are enabled when configuring with --enable-joiner.

        joiner start <pskd> <provisioningUrl>

            Start the Joiner role.

            * pskd: Pre-Shared Key for the Joiner.
            * provisioningUrl: Provisioning URL for the Joiner (optional).

            This command will cause the device to perform an MLE Discovery and
            initiate the Thread Commissioning process.

            > joiner start PSK
            Done

        joiner stop

            Stop the Joiner role.

            > joiner stop
            Done
        """
        PSKd = ""

        args = line.split(" ")
        if (len(args) > 0): subCommand = args[0]
        if (len(args) > 1): PSKd = args[1]

        PSKd = self.prep_line(PSKd, 'U')

        if subCommand == "":
            pass

        elif subCommand == "start":
            pyFormat = self.prep_format(PSKd, 'U')
            value = self.prop_set_value(SPINEL_PROP_MESHCOP_JOINER_CREDENTIAL,
                                        PSKd, pyFormat)
            value = self.prop_set_value(SPINEL_PROP_MESHCOP_JOINER_ENABLE, 1)
            print "Done"
            return

        elif subCommand == "stop":
            value = self.prop_set_value(SPINEL_PROP_MESHCOP_JOINER_ENABLE, 0)
            print "Done"
            return

        print "Error"

    def complete_ifconfig(self, text, line, begidx, endidx):
        _SUB_COMMANDS = ('up', 'down')
        return [i for i in _SUB_COMMANDS if i.startswith(text)]

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

        args = line.split(" ")

        if args[0] == "":
            value = self.prop_get_value(SPINEL_PROP_NET_IF_UP)
            if value != None:
                ARG_MAP_VALUE = {
                    0: "down",
                    1: "up",
                }
                print ARG_MAP_VALUE[value]

        elif args[0] == "up":
            self.prop_set(SPINEL_PROP_NET_IF_UP, '1')
            return

        elif args[0] == "down":
            self.prop_set(SPINEL_PROP_NET_IF_UP, '0')
            return

        print("Done")

    def complete_ipaddr(self, text, line, begidx, endidx):
        _SUB_COMMANDS = ('add', 'remove')
        return [i for i in _SUB_COMMANDS if i.startswith(text)]

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
        args = line.split(" ")
        valid = 1
        preferred = 1
        flags = 0
        prefixLen = 64  # always use /64, as prefix.network.prefixlen returns /128.

        num = len(args)
        if (num > 1):
            ipaddr = args[1]
            prefix = ipaddress.IPv6Interface(unicode(ipaddr))
            arr = prefix.ip.packed

        if args[0] == "":
            addrs = self.wpanApi.get_ipaddrs()
            for addr in addrs:
                print str(addr)

        elif args[0] == "add":
            arr += self.wpanApi.encode_fields('CLLC',
                                              prefixLen,
                                              valid,
                                              preferred,
                                              flags)

            value = self.prop_insert_value(SPINEL_PROP_IPV6_ADDRESS_TABLE,
                                           arr, str(len(arr))+'s')
            if self.wpanApi.tunIf:
                self.wpanApi.tunIf.addr_add(ipaddr)

        elif args[0] == "remove":
            arr += self.wpanApi.encode_fields('CLLC',
                                              prefixLen,
                                              valid,
                                              preferred,
                                              flags)

            value = self.prop_remove_value(SPINEL_PROP_IPV6_ADDRESS_TABLE,
                                           arr, str(len(arr))+'s')
            if self.wpanApi.tunIf:
                self.wpanApi.tunIf.addr_del(ipaddr)

        print("Done")

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
        self.handle_property(line, SPINEL_PROP_NET_KEY_SEQUENCE, 'L')

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
        self.handle_property(line, SPINEL_PROP_THREAD_LOCAL_LEADER_WEIGHT)

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
        self.handle_property(line, SPINEL_PROP_NET_MASTER_KEY, 'D')

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
        self.prop_set_value(SPINEL_PROP_THREAD_ALLOW_LOCAL_NET_DATA_CHANGE, 1)
        self.handle_property("0", SPINEL_PROP_THREAD_ALLOW_LOCAL_NET_DATA_CHANGE)

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
        self.handle_property(line, SPINEL_PROP_THREAD_NETWORK_ID_TIMEOUT)

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
        self.handle_property(line, SPINEL_PROP_NET_NETWORK_NAME, 'U')

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
        args = line.split(" ")
        addr = "::1"
        size = "56"
        count = "1"
        interval = "1"
        if (len(args) > 0): addr = args[0]
        if (len(args) > 1): size = args[1]
        if (len(args) > 2): count = args[2]
        if (len(args) > 3): interval = args[3]

        try:
            # Generate local ping packet and send directly via spinel.
            ML64 = self.prop_get_value(SPINEL_PROP_IPV6_ML_ADDR)
            ML64 = str(ipaddress.IPv6Address(ML64))
            timenow = int(round(time.time() * 1000)) & 0xFFFFFFFF
            timenow = pack('>I', timenow)
            ping_req = str(IPv6(src=ML64, dst=addr)/ICMPv6EchoRequest()/timenow)
            self.wpanApi.ip_send(ping_req)
            # Let handler print result
        except:
            print "Fail"
            print traceback.format_exc()

    def complete_prefix(self, text, line, begidx, endidx):
        _SUB_COMMANDS = ('add', 'remove')
        return [i for i in _SUB_COMMANDS if i.startswith(text)]

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
        args = line.split(" ")
        stable = 0
        flags = 0
        arr = ""

        num = len(args)
        if num > 1:
            prefix = ipaddress.IPv6Interface(unicode(args[1]))
            arr = prefix.ip.packed
        if num > 2:
            for c in args[2]:
                if c == 'p': flags |= kThreadPrefixPreferredFlag
                if c == 'a': flags |= kThreadPrefixSlaacFlag
                if c == 'd': flags |= kThreadPrefixDhcpFlag
                if c == 'c': flags |= kThreadPrefixConfigureFlag
                if c == 'r': flags |= kThreadPrefixDefaultRouteFlag
                if c == 'o': flags |= kThreadPrefixOnMeshFlag
                if c == 's': stable = 1  # Stable flag
        if num > 3:
            ARG_MAP_NAME = {
                "high": 2,
                "med": 1,
                "low": 0,
            }
            prf = ARG_MAP_NAME[args[3]]
            flags |= (prf << kThreadPrefixPreferenceOffset)

        if args[0] == "":
            value = self.prop_get_value(SPINEL_PROP_THREAD_ON_MESH_NETS)

        elif args[0] == "add":
            arr += self.wpanApi.encode_fields('CbC',
                                              prefix.network.prefixlen,
                                              stable,
                                              flags)

            self.prop_set_value(SPINEL_PROP_THREAD_ALLOW_LOCAL_NET_DATA_CHANGE,1)
            value = self.prop_insert_value(SPINEL_PROP_THREAD_ON_MESH_NETS,
                                           arr, str(len(arr))+'s')

        elif args[0] == "remove":
            arr += self.wpanApi.encode_fields('CbC',
                                              prefix.network.prefixlen,
                                              stable,
                                              flags)

            self.prop_set_value(SPINEL_PROP_THREAD_ALLOW_LOCAL_NET_DATA_CHANGE,1)
            value = self.prop_remove_value(SPINEL_PROP_THREAD_ON_MESH_NETS,
                                           arr, str(len(arr))+'s')

        print("Done")

    def do_releaserouterid(self, line):
        """
        releaserouterid <routerid>

            Release a Router ID that has been allocated by the device in the Leader role.

            > releaserouterid 16
            Done
        """
        if line:
            value = int(line)
            self.prop_remove_value(SPINEL_PROP_THREAD_ACTIVE_ROUTER_IDS, value)
        print("Done")


    def do_rloc16(self, line):
        """
        rloc16

            Get the Thread RLOC16 value.

            > rloc16
            0xdead
            Done
        """
        self.handle_property(line, SPINEL_PROP_THREAD_RLOC16, 'H')

    def complete_route(self, text, line, begidx, endidx):
        _SUB_COMMANDS = ('add', 'remove')
        return [i for i in _SUB_COMMANDS if i.startswith(text)]

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
        args = line.split(" ")
        stable = 0
        prf = 0

        num = len(args)
        if (num > 1):
            prefix = ipaddress.IPv6Interface(unicode(args[1]))
            arr = prefix.ip.packed

        if args[0] == "":
            value = self.prop_get_value(SPINEL_PROP_THREAD_LOCAL_ROUTES)

        elif args[0] == "add":
            arr += self.wpanApi.encode_fields('CbC',
                                              prefix.network.prefixlen,
                                              stable,
                                              prf)

            self.prop_set_value(SPINEL_PROP_THREAD_ALLOW_LOCAL_NET_DATA_CHANGE,1)
            value = self.prop_insert_value(SPINEL_PROP_THREAD_LOCAL_ROUTES,
                                           arr, str(len(arr))+'s')

        elif args[0] == "remove":
            self.prop_set_value(SPINEL_PROP_THREAD_ALLOW_LOCAL_NET_DATA_CHANGE,1)
            value = self.prop_remove_value(SPINEL_PROP_THREAD_LOCAL_ROUTES,
                                           arr, str(len(arr))+'s')

        print("Done")

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


    def do_routerselectionjitter(self, line):
        """
        routerselectionjitter

            Get the ROUTER_SELECTION_JITTER value.

            > routerselectionjitter
            120
            Done

        routerselectionjitter <threshold>

            Set the ROUTER_SELECTION_JITTER value.

            > routerselectionjitter 120
            Done
        """
        self.handle_property(line, SPINEL_PROP_THREAD_ROUTER_SELECTION_JITTER)

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

    def do_routerdowngradethreshold(self, line):
        """
        routerdowngradethreshold

            Get the ROUTER_DOWNGRADE_THRESHOLD value.

            > routerdowngradethreshold
            16
            Done

        routerdowngradethreshold <threshold>

            Set the ROUTER_DOWNGRADE_THRESHOLD value.

            > routerdowngradethreshold 16
            Done
        """
        self.handle_property(line, SPINEL_PROP_THREAD_ROUTER_DOWNGRADE_THRESHOLD)

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


    def complete_thread(self, text, line, begidx, endidx):
        _SUB_COMMANDS = ('start', 'stop')
        return [i for i in _SUB_COMMANDS if i.startswith(text)]

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

        result = self.prop_get_or_set_value(SPINEL_PROP_NET_STACK_UP, line)
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

    def complete_whitelist(self, text, line, begidx, endidx):
        _SUB_COMMANDS = ('add', 'remove', 'clear', 'enable', 'disable')
        return [i for i in _SUB_COMMANDS if i.startswith(text)]

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

        whitelist add <extaddr> [rssi]

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
            value = self.prop_set_value(SPINEL_PROP_MAC_WHITELIST, None, None)

        elif args[0] == "add":
            arr = util.hex_to_bytes(args[1])
            try:
                rssi = int(args[2])
            except:
                rssi = SPINEL_RSSI_OVERRIDE
            arr += pack('b', rssi)
            value = self.prop_insert_value(SPINEL_PROP_MAC_WHITELIST, arr,
                                           str(len(arr))+'s')

        elif args[0] == "remove":
            arr = util.hex_to_bytes(args[1])
            arr += pack('b', SPINEL_RSSI_OVERRIDE)
            value = self.prop_remove_value(SPINEL_PROP_MAC_WHITELIST, arr,
                                           str(len(arr))+'s')

        print("Done")

    def do_ncpll64(self, line):
        """ Display the link local IPv6 address. """
        self.handle_property(line, SPINEL_PROP_IPV6_LL_ADDR, '6')

    def do_ncpml64(self, line):
        """ Display the mesh local IPv6 address. """
        self.handle_property(line, SPINEL_PROP_IPV6_ML_ADDR, '6')

    def complete_ncptun(self, text, line, begidx, endidx):
        _SUB_COMMANDS = ('up', 'down', 'add', 'remove', 'ping')
        return [i for i in _SUB_COMMANDS if i.startswith(text)]

    def do_ncptun(self, line):
        """
        ncp-tun

            Control sideband tunnel interface.

        ncp-tun up

            Bring up Thread TUN interface.

            > ncp-tun up
            Done

        ncp-tun down

            Bring down Thread TUN interface.

            > ncp-tun down
            Done

        ncp-tun add <ipaddr>

            Add an IPv6 address to the Thread TUN interface.

            > ncp-tun add 2001::dead:beef:cafe
            Done

        ncp-tun del <ipaddr>

            Delete an IPv6 address from the Thread TUN interface.

            > ncp-tun del 2001::dead:beef:cafe
            Done

        ncp-tun ping <ipaddr> [size] [count] [interval]

            Send an ICMPv6 Echo Request.

            > ncp-tun ping fdde:ad00:beef:0:558:f56b:d688:799
            16 bytes from fdde:ad00:beef:0:558:f56b:d688:799: icmp_seq=1 hlim=64 time=28ms
        """
        args = line.split(" ")

        num = len(args)
        if (num > 1):
            ipaddr = args[1]
            prefix = ipaddress.IPv6Interface(unicode(ipaddr))
            arr = prefix.ip.packed

        if args[0] == "":
            pass

        elif args[0] == "add":
            if self.wpanApi.tunIf:
                self.wpanApi.tunIf.addr_add(ipaddr)

        elif args[0] == "remove":
            if self.wpanApi.tunIf:
                self.wpanApi.tunIf.addr_del(ipaddr)

        elif args[0] == "up":
            self.wpanApi.if_up(self.nodeid)

        elif args[0] == "down":
            self.wpanApi.if_down()

        elif args[0] == "ping":
            # Use tunnel to send ping
            size = "56"
            count = "1"
            interval = "1"
            if (len(args) > 1): size = args[1]
            if (len(args) > 2): count = args[2]
            if (len(args) > 3): interval = args[3]

            if self.wpanApi.tunIf:
                self.wpanApi.tunIf.ping6(" -c "+count+" -s "+size+" "+addr)

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


if __name__ == "__main__":

    args = sys.argv[1:]

    optParser = optparse.OptionParser()

    optParser = optparse.OptionParser(usage=optparse.SUPPRESS_USAGE)
    optParser.add_option("-u", "--uart", action="store",
                         dest="uart", type="string")
    optParser.add_option("-p", "--pipe", action="store",
                         dest="pipe", type="string")
    optParser.add_option("-s", "--socket", action="store",
                         dest="socket", type="string")
    optParser.add_option("-n", "--nodeid", action="store",
                         dest="nodeid", type="string", default="1")
    optParser.add_option("-q", "--quiet", action="store_true", dest="quiet")
    optParser.add_option("-v", "--verbose", action="store_false",dest="verbose")
    optParser.add_option("-d", "--debug", action="store",
                         dest="debug", type="int", default=CONFIG.DEBUG_ENABLE)

    (options, remainingArgs) = optParser.parse_args(args)


    if options.debug:
        CONFIG.DebugSetLevel(options.debug)

    # Set default stream to pipe
    streamType = 'p'
    streamDescriptor = "../../examples/apps/ncp/ot-ncp "+options.nodeid

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
        if len(remainingArgs) > 0:
            streamDescriptor = " ".join(remainingArgs)

    stream = StreamOpen(streamType, streamDescriptor)
    shell = SpinelCliCmd(stream, nodeid=options.nodeid)

    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        logger.info('\nCTRL+C Pressed')
        
    if shell.wpanApi:
        shell.wpanApi.stream.close()
