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
 *   This defines the eventing mechanism between NimBLE host task
 *   and the main openthread task.
 */

#include "platform-posix.h"

#include <openthread/platform/ble.h>

#include <nimble/nimble_npl.h>

#include "ble_nimble_event.h"

#define PIPE_READ 0
#define PIPE_WRITE 1

static int sPipeFd[2]; ///< file descriptors for waking ot

void platformBleInit()
{
    int err = pipe2(sPipeFd, O_NONBLOCK);
    if (err)
    {
        fprintf(stderr, "ERROR: platformBleInit unable to open pipe.\n");
        exit(EXIT_FAILURE);
    }
}

void platformBleSignal()
{
    uint8_t val = 1;
    write(sPipeFd[PIPE_WRITE], &val, sizeof(val));
    otPlatBleHciTick(NULL);
}

void platformBleUpdateFdSet(fd_set *aReadFdSet, int *aMaxFd)
{
    if (aReadFdSet != NULL && sPipeFd[PIPE_READ])
    {
        FD_SET(sPipeFd[PIPE_READ], aReadFdSet);

        if (aMaxFd != NULL && *aMaxFd < sPipeFd[PIPE_READ])
        {
            *aMaxFd = sPipeFd[PIPE_READ];
        }
    }
}

void platformBleProcess(otInstance *aInstance)
{
    otPlatBleHciTick(aInstance);
}

void dispatch_otPlatBleGapOnConnected(otInstance *aInstance, uint16_t aConnectionId)
{
    otPlatBleGapOnConnected(aInstance, aConnectionId);
    platformBleSignal();
}

void dispatch_otPlatBleGapOnDisconnected(otInstance *aInstance, uint16_t aConnectionId)
{
    otPlatBleGapOnDisconnected(aInstance, aConnectionId);
    platformBleSignal();
}

void dispatch_otPlatBleGapOnAdvReceived(otInstance *aInstance, otPlatBleDeviceAddr *aAddress, otBleRadioPacket *aPacket)
{
    otPlatBleGapOnAdvReceived(aInstance, aAddress, aPacket);
    platformBleSignal();
}

void dispatch_otPlatBleGapOnScanRespReceived(otInstance *         aInstance,
                                             otPlatBleDeviceAddr *aAddress,
                                             otBleRadioPacket *   aPacket)
{
    otPlatBleGapOnScanRespReceived(aInstance, aAddress, aPacket);
    platformBleSignal();
}

void dispatch_otPlatBleGattServerOnReadRequest(otInstance *aInstance, uint16_t aHandle, otBleRadioPacket *aPacket)
{
    otPlatBleGattServerOnReadRequest(aInstance, aHandle, aPacket);
    platformBleSignal();
}

void dispatch_otPlatBleGattServerOnWriteRequest(otInstance *aInstance, uint16_t aHandle, otBleRadioPacket *aPacket)
{
    otPlatBleGattServerOnWriteRequest(aInstance, aHandle, aPacket);
    platformBleSignal();
}

void dispatch_otPlatBleGattServerOnSubscribeRequest(otInstance *aInstance, uint16_t aHandle, bool aSubscribing)
{
    otPlatBleGattServerOnSubscribeRequest(aInstance, aHandle, aSubscribing);
    platformBleSignal();
}

void dispatch_otPlatBleGattServerOnIndicationConfirmation(otInstance *aInstance, uint16_t aHandle)
{
    otPlatBleGattServerOnIndicationConfirmation(aInstance, aHandle);
    platformBleSignal();
}

void dispatch_otPlatBleGattClientOnReadResponse(otInstance *aInstance, otBleRadioPacket *aPacket)
{
    otPlatBleGattClientOnReadResponse(aInstance, aPacket);
    platformBleSignal();
}

void dispatch_otPlatBleGattClientOnWriteResponse(otInstance *aInstance, uint16_t aHandle)
{
    otPlatBleGattClientOnWriteResponse(aInstance, aHandle);
    platformBleSignal();
}

void dispatch_otPlatBleGattClientOnIndication(otInstance *aInstance, uint16_t aHandle, otBleRadioPacket *aPacket)
{
    otPlatBleGattClientOnIndication(aInstance, aHandle, aPacket);
    platformBleSignal();
}

void dispatch_otPlatBleGattClientOnSubscribeResponse(otInstance *aInstance, uint16_t aHandle)
{
    otPlatBleGattClientOnSubscribeResponse(aInstance, aHandle);
    platformBleSignal();
}

void dispatch_otPlatBleGattClientOnServiceDiscovered(otInstance *aInstance,
                                                     uint16_t    aStartHandle,
                                                     uint16_t    aEndHandle,
                                                     uint16_t    aServiceUuid,
                                                     otError     aError)
{
    otPlatBleGattClientOnServiceDiscovered(aInstance, aStartHandle, aEndHandle, aServiceUuid, aError);
    platformBleSignal();
}

void dispatch_otPlatBleGattClientOnCharacteristicsDiscoverDone(otInstance *                 aInstance,
                                                               otPlatBleGattCharacteristic *aChars,
                                                               uint16_t                     aCount,
                                                               otError                      aError)
{
    otPlatBleGattClientOnCharacteristicsDiscoverDone(aInstance, aChars, aCount, aError);
    platformBleSignal();
}

void dispatch_otPlatBleGattClientOnDescriptorsDiscoverDone(otInstance *             aInstance,
                                                           otPlatBleGattDescriptor *aDescs,
                                                           uint16_t                 aCount,
                                                           otError                  aError)
{
    otPlatBleGattClientOnDescriptorsDiscoverDone(aInstance, aDescs, aCount, aError);
    platformBleSignal();
}

void dispatch_otPlatBleGattClientOnMtuExchangeResponse(otInstance *aInstance, uint16_t aMtu, otError aError)
{
    otPlatBleGattClientOnMtuExchangeResponse(aInstance, aMtu, aError);
    platformBleSignal();
}

void dispatch_otPlatBleL2capOnDisconnect(otInstance *aInstance, uint16_t aLocalCid, uint16_t aPeerCid)
{
    otPlatBleL2capOnDisconnect(aInstance, aLocalCid, aPeerCid);
    platformBleSignal();
}

void dispatch_otPlatBleL2capOnConnectionRequest(otInstance *aInstance, uint16_t aPsm, uint16_t aMtu, uint16_t aPeerCid)
{
    otPlatBleL2capOnConnectionRequest(aInstance, aPsm, aMtu, aPeerCid);
    platformBleSignal();
}

void dispatch_otPlatBleL2capOnConnectionResponse(otInstance *                  aInstance,
                                                 otPlatBleL2capConnetionResult aResult,
                                                 uint16_t                      aMtu,
                                                 uint16_t                      aPeerCid)
{
    otPlatBleL2capOnConnectionResponse(aInstance, aResult, aMtu, aPeerCid);
    platformBleSignal();
}

void dispatch_otPlatBleL2capOnSduReceived(otInstance *      aInstance,
                                          uint16_t          aLocalCid,
                                          uint16_t          aPeerCid,
                                          otBleRadioPacket *aPacket)
{
    otPlatBleL2capOnSduReceived(aInstance, aLocalCid, aPeerCid, aPacket);
    platformBleSignal();
}

void dispatch_otPlatBleL2capOnSduSent(otInstance *aInstance)
{
    otPlatBleL2capOnSduSent(aInstance);
    platformBleSignal();
}
