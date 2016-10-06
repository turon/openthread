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

import logging

from struct import pack
from struct import unpack

import spinel.config as CONFIG
from spinel.stream import IStream
from spinel.util import hexify_int
from spinel.util import hexify_bytes

HDLC_FLAG     = 0x7e
HDLC_ESCAPE   = 0x7d

# RFC 1662 Appendix C

HDLC_FCS_INIT = 0xFFFF
HDLC_FCS_POLY = 0x8408
HDLC_FCS_GOOD = 0xF0B8

class Hdlc(IStream):
    def __init__(self, stream):
        self.stream = stream
        self.fcstab = self.mkfcstab()

    def mkfcstab(self):
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

    def fcs16(self, byte, fcs):
        fcs = (fcs >> 8) ^ self.fcstab[(fcs ^ byte) & 0xff]
        return fcs

    def collect(self):
        fcs = HDLC_FCS_INIT
        packet = []
        raw = []

        # Synchronize
        while 1:
            b = self.stream.read()
            if CONFIG.DEBUG_HDLC: raw.append(b)
            if (b == HDLC_FLAG): break

        # Read packet, updating fcs, and escaping bytes as needed
        while 1:
            b = self.stream.read()
            if CONFIG.DEBUG_HDLC: raw.append(b)
            if (b == HDLC_FLAG): break
            if (b == HDLC_ESCAPE):
                b = self.stream.read()
                if CONFIG.DEBUG_HDLC: raw.append(b)
                b ^= 0x20
            packet.append(b)
            fcs = self.fcs16(b, fcs)

        if CONFIG.DEBUG_HDLC:
            logging.debug("RX Hdlc: "+str(map(hexify_int,raw)))

        if (fcs != HDLC_FCS_GOOD):
            packet = None

        return packet[:-2]        # remove FCS16 from end

    def encode_byte(self, b, packet = []):
        if (b == HDLC_ESCAPE) or (b == HDLC_FLAG):
            packet.append(HDLC_ESCAPE)
            packet.append(b ^ 0x20)
        else:
            packet.append(b)
        return packet

    def encode(self, payload = ""):
        fcs = HDLC_FCS_INIT
        packet = []
        packet.append(HDLC_FLAG)
        for b in payload:
            b = ord(b)
            fcs = self.fcs16(b, fcs)
            packet = self.encode_byte(b, packet)

        fcs ^= 0xffff;
        b = fcs & 0xFF
        packet = self.encode_byte(b, packet)
        b = fcs >> 8
        packet = self.encode_byte(b, packet)
        packet.append(HDLC_FLAG)
        packet = pack("%dB" % len(packet), *packet)

        if CONFIG.DEBUG_HDLC:
            logging.debug("TX Hdlc: "+hexify_bytes(packet))
        return packet

