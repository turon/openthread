#!/usr/bin/python
#
#  Copyright (c) 2016, Nest Labs, Inc.
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

import pexpect
import time
import unittest

import node

LEADER = 1
ROUTER1 = 2
SED1 = 3
ED2 = 4
ED3 = 5
ED4 = 6
ED5 = 7

class Cert_5_3_4_AddressMapCache(unittest.TestCase):
    def setUp(self):
        self.nodes = {}
        for i in range(1,8):
            self.nodes[i] = node.Node(i)

        self.nodes[LEADER].set_panid(0xface)
        self.nodes[LEADER].set_mode('rsdn')
        self.nodes[LEADER].add_whitelist(self.nodes[ROUTER1].get_addr64())
        self.nodes[LEADER].add_whitelist(self.nodes[ED2].get_addr64())
        self.nodes[LEADER].add_whitelist(self.nodes[ED3].get_addr64())
        self.nodes[LEADER].add_whitelist(self.nodes[ED4].get_addr64())
        self.nodes[LEADER].add_whitelist(self.nodes[ED5].get_addr64())
        self.nodes[LEADER].enable_whitelist()

        self.nodes[ROUTER1].set_panid(0xface)
        self.nodes[ROUTER1].set_mode('rsdn')
        self.nodes[ROUTER1].add_whitelist(self.nodes[LEADER].get_addr64())
        self.nodes[ROUTER1].add_whitelist(self.nodes[SED1].get_addr64())
        self.nodes[ROUTER1].enable_whitelist()

        self.nodes[SED1].set_panid(0xface)
        self.nodes[SED1].set_mode('rsn')
        self.nodes[SED1].add_whitelist(self.nodes[ROUTER1].get_addr64())
        self.nodes[SED1].enable_whitelist()

        self.nodes[ED2].set_panid(0xface)
        self.nodes[ED2].set_mode('rsn')
        self.nodes[ED2].add_whitelist(self.nodes[LEADER].get_addr64())
        self.nodes[ED2].enable_whitelist()

        self.nodes[ED3].set_panid(0xface)
        self.nodes[ED3].set_mode('rsn')
        self.nodes[ED3].add_whitelist(self.nodes[LEADER].get_addr64())
        self.nodes[ED3].enable_whitelist()

        self.nodes[ED4].set_panid(0xface)
        self.nodes[ED4].set_mode('rsn')
        self.nodes[ED4].add_whitelist(self.nodes[LEADER].get_addr64())
        self.nodes[ED4].enable_whitelist()

        self.nodes[ED5].set_panid(0xface)
        self.nodes[ED5].set_mode('rsn')
        self.nodes[ED5].add_whitelist(self.nodes[LEADER].get_addr64())
        self.nodes[ED5].enable_whitelist()

    def tearDown(self):
        for node in self.nodes.itervalues():
            node.stop()
        del self.nodes

    def test(self):
        self.nodes[LEADER].start()
        self.nodes[LEADER].set_state('leader')
        self.assertEqual(self.nodes[LEADER].get_state(), 'leader')

        self.nodes[ROUTER1].start()
        time.sleep(3)
        self.assertEqual(self.nodes[ROUTER1].get_state(), 'router')

        self.nodes[SED1].start()
        time.sleep(3)
        self.assertEqual(self.nodes[SED1].get_state(), 'child')

        self.nodes[ED2].start()
        time.sleep(3)
        self.assertEqual(self.nodes[ED2].get_state(), 'child')

        self.nodes[ED3].start()
        time.sleep(3)
        self.assertEqual(self.nodes[ED3].get_state(), 'child')

        self.nodes[ED4].start()
        time.sleep(3)
        self.assertEqual(self.nodes[ED4].get_state(), 'child')

        self.nodes[ED5].start()
        time.sleep(3)
        self.assertEqual(self.nodes[ED5].get_state(), 'child')

        for i in range(4, 8):
            addrs = self.nodes[i].get_addrs()
            for addr in addrs:
                if addr[0:4] != 'fe80':
                    self.nodes[SED1].ping(addr)

        for i in range(4, 8):
            addrs = self.nodes[i].get_addrs()
            for addr in addrs:
                if addr[0:4] != 'fe80':
                    self.nodes[SED1].ping(addr)

if __name__ == '__main__':
    unittest.main()
