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

import sys
import logging
import traceback

import serial
import socket
import subprocess

import spinel.util
import spinel.config as CONFIG

class IStream():
    def read(self, size): pass
    def write(self, data): pass
    def close(self): pass

class StreamSerial(IStream):
    def __init__(self, dev, baudrate=115200):
        comm = serial.Serial(dev, baudrate, timeout=1)
        logging.debug("TX Raw: (%d) %s" % (len(data), spinel.util.hexify_bytes(data)))

    def read(self, size=1):
        b = self.sock.recv(size)
        if CONFIG.DEBUG_STREAM_RX:
            logging.debug("RX Raw: "+spinel.util.hexify_bytes(b))
            pass
        return b

class StreamSocket(IStream):
    def __init__(self, sock):
        self.sock = sock

    def write(self, data):
        self.sock.send(data)
        if CONFIG.DEBUG_STREAM_TX:
            logging.debug("TX Raw: "+str(map(spinel.util.hexify_chr,data)))
            pass

    def read(self, size=1):
        b = self.sock.recv(size)
        if CONFIG.DEBUG_STREAM_RX:
            logging.debug("RX Raw: "+str(map(spinel.util.hexify_chr,b)))
            pass
        return b

class StreamPipe(IStream):
    def __init__(self, filename):
        """ Create a stream object from a piped system call """
        try:
            self.pipe = subprocess.Popen(filename, shell = True,
                                         stdin = subprocess.PIPE,
                                         stdout = subprocess.PIPE,
                                         stderr = sys.stdout.fileno())
        except:
            logging.Error("Couldn't open "+filename)
            print("Couldn't open "+filename)
            print traceback.format_exc()
            pass

    def write(self, data):
        if CONFIG.DEBUG_STREAM_TX:
            logging.debug("TX Raw: (%d) %s" % (len(data), spinel.util.hexify_bytes(data)))
            pass
        self.pipe.stdin.write(data)

    def read(self, size=1):
        """ Blocking read on stream object """
        for b in iter(lambda: self.pipe.stdout.read(size), ''):
            if CONFIG.DEBUG_STREAM_RX:
                logging.debug("RX Raw: "+spinel.util.hexify_bytes(b))
                pass
            return ord(b)

    def close(self):
        if self.pipe:
            self.pipe.kill()
            self.pipe = None

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
