/*
 *  Copyright (c) 2018, The OpenThread Authors.
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions are met:
 *  1. Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *  2. Redistributions in binary form must reproduce the above copyright
 *     notice, this list of conditions and the following disclaimer in the
 *     documentation and/or other materials provided with the distribution.
 *  3. Neither the name of the copyright holder nor the
 *     names of its contributors may be used to endorse or promote products
 *     derived from this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 *  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 *  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 *  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 *  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 *  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 *  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 *  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 *  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 *  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 *  POSSIBILITY OF SUCH DAMAGE.
 */

/**
 * @file
 *   This file implements a simple BLE scan tool using
 *   OpenThread BLE driver platform abstraction API.
 */

#include <assert.h>

#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <openthread/error.h>
#include <openthread/instance.h>
#include <openthread/platform/ble.h>
#include <openthread/platform/ble_hci.h>

int main(int argc, char *argv[])
{
    otInstance *sInstance;
    sInstance = otInstanceInitSingle();
    assert(sInstance);

    uid_t euid = geteuid();

    if (euid != 0)
    {
        printf("Please run as sudo.\n");
        exit(0);
    }

    int dev = -1;

    if (argc > 1)
    {
        dev = atoi(argv[1]);
    }

    // Use hci api to override default deviceId
    otPlatBleHciSetDeviceId(sInstance, dev);
    otError err = otPlatBleEnable(sInstance);
    dev         = otPlatBleHciGetDeviceId(sInstance);

    if (err != OT_ERROR_NONE)
    {
        printf("BLE interface %d not found.\n", dev);
        exit(1);
    }

    printf("Opened hci%d\n", dev);

    otPlatBleGapScanStart(sInstance, OT_BLE_SCAN_INTERVAL_MAX, OT_BLE_SCAN_WINDOW_MAX);

    while (1)
    {
        otPlatBleHciTick(sInstance);
    }
}

void print_bytes(uint8_t *aBytes, int aLength)
{
    for (int i = 0; i < aLength; i++)
    {
        printf("%02x", aBytes[i]);
    }
}

extern "C" void otPlatBleGapOnAdvReceived(otInstance          *aInstance,
                                          otPlatBleDeviceAddr *aAddress,
                                          otBleRadioPacket    *aPacket)
{
    (void)aInstance;
    (void)aPacket;

    printf("%02x:%02x:%02x:%02x:%02x:%02x : ", aAddress->mAddr[5], aAddress->mAddr[4], aAddress->mAddr[3],
           aAddress->mAddr[2], aAddress->mAddr[1], aAddress->mAddr[0]);

    print_bytes(aPacket->mValue, aPacket->mLength);

    printf("\n");

    fflush(stdout);
}
