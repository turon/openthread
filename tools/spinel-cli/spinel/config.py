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

DEBUG_ENABLE = 0

DEBUG_TUN = 0
DEBUG_HDLC = 0

DEBUG_STREAM_TX = 0
DEBUG_STREAM_RX = 0

DEBUG_LOG_PKT = DEBUG_ENABLE
DEBUG_LOG_SERIAL = DEBUG_ENABLE
DEBUG_LOG_PROP = DEBUG_ENABLE
DEBUG_CMD_RESPONSE = 0
DEBUG_EXPERIMENTAL = 1


def DebugSetLevel(level):
    global DEBUG_ENABLE, DEBUG_LOG_PROP
    global DEBUG_LOG_PKT, DEBUG_LOG_SERIAL

    # Defaut to all logging disabled

    DEBUG_ENABLE = 0
    DEBUG_LOG_PROP = 0
    DEBUG_LOG_PKT = 0
    DEBUG_LOG_SERIAL = 0
    DEBUG_HDLC = 0
    DEBUG_STREAM_RX = 0
    DEBUG_STREAM_TX = 0

    if level:
        DEBUG_ENABLE = level
        if level >= 1: DEBUG_LOG_PROP = 1
        if level >= 2: DEBUG_LOG_PKT = 1
        if level >= 3: DEBUG_LOG_SERIAL = 1
        if level >= 4: DEBUG_HDLC = 1
        if level >= 5: 
            DEBUG_STREAM_RX = 1
            DEBUG_STREAM_TX = 1

    print "DEBUG_ENABLE = "+str(DEBUG_ENABLE)

