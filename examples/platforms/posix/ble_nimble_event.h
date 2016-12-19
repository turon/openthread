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

#ifndef BLE_NIMBLE_EVENT_H_
#define BLE_NIMBLE_EVENT_H_

#include <openthread/error.h>
#include <openthread/instance.h>
#include <openthread/platform/ble.h>

// GAP
void dispatch_otPlatBleGapOnConnected(otInstance *aInstance, uint16_t aConnectionId);
void dispatch_otPlatBleGapOnDisconnected(otInstance *aInstance, uint16_t aConnectionId);
void dispatch_otPlatBleGapOnAdvReceived(otInstance *aInstance, otPlatBleDeviceAddr *aAddress, otBleRadioPacket *aPacket);
void dispatch_otPlatBleGapOnScanRespReceived(otInstance *         aInstance,
                                             otPlatBleDeviceAddr *aAddress,
                                             otBleRadioPacket *   aPacket);

// GATT SERVER
void dispatch_otPlatBleGattServerOnReadRequest(otInstance *aInstance, uint16_t aHandle, otBleRadioPacket *aPacket);
void dispatch_otPlatBleGattServerOnWriteRequest(otInstance *aInstance, uint16_t aHandle, otBleRadioPacket *aPacket);
void dispatch_otPlatBleGattServerOnSubscribeRequest(otInstance *aInstance, uint16_t aHandle, bool aSubscribing);
void dispatch_otPlatBleGattServerOnIndicationConfirmation(otInstance *aInstance, uint16_t aHandle);


void dispatch_otPlatBleGattClientOnIndication(otInstance *aInstance, uint16_t aHandle, otBleRadioPacket *aPacket);
void dispatch_otPlatBleGattClientOnReadResponse(otInstance *aInstance, otBleRadioPacket *aPacket);
void dispatch_otPlatBleGattClientOnWriteResponse(otInstance *aInstance, uint16_t aHandle);
void dispatch_otPlatBleGattClientOnSubscribeResponse(otInstance *aInstance, uint16_t aHandle);
void dispatch_otPlatBleGattClientOnServiceDiscovered(otInstance *aInstance,
                                                     uint16_t    aStartHandle,
                                                     uint16_t    aEndHandle,
                                                     uint16_t    aServiceUuid,
                                                     otError     aError);
void dispatch_otPlatBleGattClientOnCharacteristicsDiscoverDone(otInstance *                 aInstance,
                                                               otPlatBleGattCharacteristic *aChars,
                                                               uint16_t                     aCount,
                                                               otError                      aError);
void dispatch_otPlatBleGattClientOnDescriptorsDiscoverDone(otInstance *             aInstance,
                                                           otPlatBleGattDescriptor *aDescs,
                                                           uint16_t                 aCount,
                                                           otError                  aError);
void dispatch_otPlatBleGattClientOnMtuExchangeResponse(otInstance *aInstance, uint16_t aMtu, otError aError);

// L2CAP
void dispatch_otPlatBleL2capOnDisconnect(otInstance *aInstance, uint16_t aLocalCid, uint16_t aPeerCid);
void dispatch_otPlatBleL2capOnConnectionRequest(otInstance *aInstance, uint16_t aPsm, uint16_t aMtu, uint16_t aPeerCid);
void dispatch_otPlatBleL2capOnConnectionResponse(otInstance *                  aInstance,
                                               otPlatBleL2capConnetionResult aResult,
                                               uint16_t                      aMtu,
                                               uint16_t                      aPeerCid);
void dispatch_otPlatBleL2capOnSduReceived(otInstance *      aInstance,
                                        uint16_t          aLocalCid,
                                        uint16_t          aPeerCid,
                                        otBleRadioPacket *aPacket);
void dispatch_otPlatBleL2capOnSduSent(otInstance *aInstance);

#endif // BLE_NIMBLE_EVENT_H_
