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
 *   This file implements a simple BLE beacon advertising tool using
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

#include "openthread-system.h"

#define DEFAULT_ADV_INTERVAL 500

static otInstance *sInstance;

static const uint8_t sAdv[] = {0x02, 0x01, 0x06, 0x16, 0x16, 0xf5, 0xfe, ///< UUID
			       0x00,                                     ///< Type
			       0x01,                                     ///< Count
			       0xc5,                                     ///< TX Power
			       0xDE, 0xAD, 0xBE, 0xEF, 0xFA, 0xCE, 0xBA, 0xBE,
			       0xDA, 0xDA, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05};

static const uint8_t sScanResp[] = {11,   //  length
				    0x09, //  type: COMPLETE_LOCAL_NAME
				    'o',  'p', 'e', 'n', 't', 'h', 'r', 'e', 'a', 'd'};

void print_bytes(const uint8_t *aBytes, int aLength, const char *aName)
{
    printf("%s = 0x", aName);

    for (int i = 0; i < aLength; i++)
    {
        printf("%02x", aBytes[i]);
    }

    printf("\n");
}

void enable_advertising()
{
    otError err;

    print_bytes(sAdv, sizeof(sAdv), "sAdv");

    err = otPlatBleGapScanResponseSet(sInstance, sScanResp, sizeof(sScanResp));
    if (err)
    {
        printf("Error: (%2d) in otPlatBleGapScanResponseSet\n", err);
    }
    err = otPlatBleGapServiceSet(sInstance, "openthread", 0);
    if (err)
    {
        printf("Error: (%2d) in otPlatBleGapServiceSet\n", err);
    }
    err = otPlatBleGapAdvDataSet(sInstance, sAdv, sizeof(sAdv));
    if (err)
    {
        printf("Error: (%2d) in otPlatBleGapAdvDataSet\n", err);
    }
    err = otPlatBleGapAdvStart(sInstance, DEFAULT_ADV_INTERVAL, OT_BLE_ADV_MODE_CONNECTABLE);
    if (err)
    {
        printf("Error: (%2d) in otPlatBleGapAdvStart\n", err);
    }
    printf("Advertising...\n");
}

void otPlatBleGapOnDisconnected(otInstance *aInstance, uint16_t aConnectionId)
{
    (void)aInstance;

    printf("Disconnected: #%d\n", aConnectionId);

    enable_advertising();
}

void otPlatBleGapOnConnected(otInstance *aInstance, uint16_t aConnectionId)
{
    (void)aInstance;

    printf("Connected: #%d\n", aConnectionId);
}

int main(int argc, char *argv[])
{
    otSysInit(argc, argv);

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

    printf("Opened hci%d\n", otPlatBleHciGetDeviceId(sInstance));

    enable_advertising();

    while (1)
    {
        otPlatBleHciTick(sInstance);
    }
}
