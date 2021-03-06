/*
 *  Copyright (c) 2019, The OpenThread Authors.
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
 *   This file implements the OpenThread platform abstraction for radio communication.
 *
 */

#include <assert.h>

#include "openthread-system.h"
#include <openthread/config.h>
#include <openthread/platform/alarm-milli.h>
#include <openthread/platform/diag.h>
#include <openthread/platform/radio.h>

#include "common/logging.hpp"
#include "utils/code_utils.h"

#include "utils/soft_source_match_table.h"

#include "board_config.h"
#include "em_cmu.h"
#include "em_core.h"
#include "em_system.h"
#include "hal-config.h"
#include "openthread-core-efr32-config.h"
#include "pa_conversions_efr32.h"
#include "platform-band.h"
#include "rail.h"
#include "rail_config.h"
#include "rail_ieee802154.h"

enum
{
    IEEE802154_MIN_LENGTH      = 5,
    IEEE802154_MAX_LENGTH      = 127,
    IEEE802154_ACK_LENGTH      = 5,
    IEEE802154_FRAME_TYPE_MASK = 0x7,
    IEEE802154_FRAME_TYPE_ACK  = 0x2,
    IEEE802154_FRAME_PENDING   = 1 << 4,
    IEEE802154_ACK_REQUEST     = 1 << 5,
    IEEE802154_DSN_OFFSET      = 2,
};

enum
{
    EFR32_RECEIVE_SENSITIVITY    = -100, // dBm
    EFR32_RSSI_AVERAGING_TIMEOUT = 300,  // us
};

enum
{
    EFR32_SCHEDULER_SAMPLE_RSSI_PRIORITY = 10, // High priority
    EFR32_SCHEDULER_TX_PRIORITY          = 10, // High priority
    EFR32_SCHEDULER_RX_PRIORITY          = 20, // Low priority
};

enum
{
#if RADIO_CONFIG_2P4GHZ_OQPSK_SUPPORT && RADIO_CONFIG_915MHZ_OQPSK_SUPPORT
    EFR32_NUM_BAND_CONFIGS = 2,
#else
    EFR32_NUM_BAND_CONFIGS = 1,
#endif
};

typedef enum
{
    ENERGY_SCAN_STATUS_IDLE,
    ENERGY_SCAN_STATUS_IN_PROGRESS,
    ENERGY_SCAN_STATUS_COMPLETED
} energyScanStatus;

typedef enum
{
    ENERGY_SCAN_MODE_SYNC,
    ENERGY_SCAN_MODE_ASYNC
} energyScanMode;

RAIL_Handle_t gRailHandle;

static volatile bool sTransmitBusy      = false;
static bool          sPromiscuous       = false;
static bool          sIsSrcMatchEnabled = false;
static otRadioState  sState             = OT_RADIO_STATE_DISABLED;

static uint8_t      sReceivePsdu[IEEE802154_MAX_LENGTH];
static otRadioFrame sReceiveFrame;
static otError      sReceiveError;

static otRadioFrame     sTransmitFrame;
static uint8_t          sTransmitPsdu[IEEE802154_MAX_LENGTH];
static volatile otError sTransmitError;

static efr32CommonConfig sCommonConfig;
static efr32BandConfig   sBandConfigs[EFR32_NUM_BAND_CONFIGS];

static volatile energyScanStatus sEnergyScanStatus;
static volatile int8_t           sEnergyScanResultDbm;
static energyScanMode            sEnergyScanMode;

#define QUARTER_DBM_IN_DBM 4
#define US_IN_MS 1000

static void RAILCb_Generic(RAIL_Handle_t aRailHandle, RAIL_Events_t aEvents);

static const RAIL_IEEE802154_Config_t sRailIeee802154Config = {
    .addresses = NULL,
    .ackConfig =
        {
            .enable     = true,
            .ackTimeout = 894,
            .rxTransitions =
                {
                    .success = RAIL_RF_STATE_RX,
                    .error   = RAIL_RF_STATE_RX,
                },
            .txTransitions =
                {
                    .success = RAIL_RF_STATE_RX,
                    .error   = RAIL_RF_STATE_RX,
                },
        },
    .timings =
        {
            .idleToRx            = 100,
            .txToRx              = 192 - 10,
            .idleToTx            = 100,
            .rxToTx              = 192,
            .rxSearchTimeout     = 0,
            .txToRxSearchTimeout = 0,
        },
    .framesMask       = RAIL_IEEE802154_ACCEPT_STANDARD_FRAMES,
    .promiscuousMode  = false,
    .isPanCoordinator = false,
};

RAIL_DECLARE_TX_POWER_VBAT_CURVES(piecewiseSegments, curvesSg, curves24Hp, curves24Lp);

static int8_t sTxPowerDbm = OPENTHREAD_CONFIG_DEFAULT_TRANSMIT_POWER;

static efr32BandConfig *sCurrentBandConfig = NULL;

static RAIL_Handle_t efr32RailInit(efr32CommonConfig *aCommonConfig)
{
    RAIL_Status_t status;
    RAIL_Handle_t handle;

    handle = RAIL_Init(&aCommonConfig->mRailConfig, NULL);
    assert(handle != NULL);

    status = RAIL_ConfigCal(handle, RAIL_CAL_ALL);
    assert(status == RAIL_STATUS_NO_ERROR);

    status = RAIL_IEEE802154_Init(handle, &sRailIeee802154Config);
    assert(status == RAIL_STATUS_NO_ERROR);

    status = RAIL_ConfigEvents(handle, RAIL_EVENTS_ALL,
                               RAIL_EVENT_RX_ACK_TIMEOUT |                      //
                                   RAIL_EVENTS_TX_COMPLETION |                  //
                                   RAIL_EVENT_RX_PACKET_RECEIVED |              //
                                   RAIL_EVENT_RSSI_AVERAGE_DONE |               //
                                   RAIL_EVENT_IEEE802154_DATA_REQUEST_COMMAND | //
                                   RAIL_EVENT_CAL_NEEDED                        //
    );
    assert(status == RAIL_STATUS_NO_ERROR);

    uint16_t actualLenth = RAIL_SetTxFifo(handle, aCommonConfig->mRailTxFifo, 0, sizeof(aCommonConfig->mRailTxFifo));
    assert(actualLenth == sizeof(aCommonConfig->mRailTxFifo));

    return handle;
}

static void efr32RailConfigLoad(efr32BandConfig *aBandConfig)
{
    RAIL_Status_t status;
#if HAL_PA_2P4_LOWPOWER == 1
    RAIL_TxPowerConfig_t txPowerConfig = {RAIL_TX_POWER_MODE_2P4_LP, HAL_PA_VOLTAGE, 10};
#else
    RAIL_TxPowerConfig_t txPowerConfig = {RAIL_TX_POWER_MODE_2P4_HP, HAL_PA_VOLTAGE, 10};
#endif
    if (aBandConfig->mChannelConfig != NULL)
    {
        uint16_t firstChannel = RAIL_ConfigChannels(gRailHandle, aBandConfig->mChannelConfig, NULL);
        assert(firstChannel == aBandConfig->mChannelMin);

        txPowerConfig.mode = RAIL_TX_POWER_MODE_SUBGIG;
    }
    else
    {
        status = RAIL_IEEE802154_Config2p4GHzRadio(gRailHandle);
        assert(status == RAIL_STATUS_NO_ERROR);
    }
    status = RAIL_ConfigTxPower(gRailHandle, &txPowerConfig);
    assert(status == RAIL_STATUS_NO_ERROR);
}

static void efr32RadioSetTxPower(int8_t aPowerDbm)
{
    RAIL_Status_t              status;
    RAIL_TxPowerCurvesConfig_t txPowerCurvesConfig = {curves24Hp, curvesSg, curves24Lp, piecewiseSegments};

    status = RAIL_InitTxPowerCurves(&txPowerCurvesConfig);
    assert(status == RAIL_STATUS_NO_ERROR);

    status = RAIL_SetTxPowerDbm(gRailHandle, ((RAIL_TxPower_t)aPowerDbm) * 10);
    assert(status == RAIL_STATUS_NO_ERROR);
}

static efr32BandConfig *efr32RadioGetBandConfig(uint8_t aChannel)
{
    efr32BandConfig *config = NULL;

    for (uint8_t i = 0; i < EFR32_NUM_BAND_CONFIGS; i++)
    {
        if ((sBandConfigs[i].mChannelMin <= aChannel) && (aChannel <= sBandConfigs[i].mChannelMax))
        {
            config = &sBandConfigs[i];
            break;
        }
    }

    return config;
}

static void efr32ConfigInit(void (*aEventCallback)(RAIL_Handle_t railHandle, RAIL_Events_t events))
{
    sCommonConfig.mRailConfig.eventsCallback = aEventCallback;
    sCommonConfig.mRailConfig.protocol       = NULL; // only used by Bluetooth stack
    sCommonConfig.mRailConfig.scheduler      = NULL; // only needed for DMP

    uint8_t index = 0;

#if RADIO_CONFIG_2P4GHZ_OQPSK_SUPPORT
    sBandConfigs[index].mChannelConfig = NULL;
    sBandConfigs[index].mChannelMin    = OT_RADIO_2P4GHZ_OQPSK_CHANNEL_MIN;
    sBandConfigs[index].mChannelMax    = OT_RADIO_2P4GHZ_OQPSK_CHANNEL_MAX;

    index++;
#endif

#if RADIO_CONFIG_915MHZ_OQPSK_SUPPORT
    sBandConfigs[index].mChannelConfig = channelConfigs[0];
    sBandConfigs[index].mChannelMin    = OT_RADIO_915MHZ_OQPSK_CHANNEL_MIN;
    sBandConfigs[index].mChannelMax    = OT_RADIO_915MHZ_OQPSK_CHANNEL_MAX;
#endif
    gRailHandle = efr32RailInit(&sCommonConfig);
    assert(gRailHandle != NULL);
    efr32RailConfigLoad(&(sBandConfigs[0]));
}

void efr32RadioInit(void)
{
    RAIL_Status_t status;

    // check if RAIL_TX_FIFO_SIZE is power of two..
    assert((RAIL_TX_FIFO_SIZE & (RAIL_TX_FIFO_SIZE - 1)) == 0);

    // check the limits of the RAIL_TX_FIFO_SIZE.
    assert((RAIL_TX_FIFO_SIZE >= 64) || (RAIL_TX_FIFO_SIZE <= 4096));

    efr32ConfigInit(RAILCb_Generic);

    CMU_ClockEnable(cmuClock_PRS, true);

    status = RAIL_ConfigSleep(gRailHandle, RAIL_SLEEP_CONFIG_TIMERSYNC_ENABLED);
    assert(status == RAIL_STATUS_NO_ERROR);

    sReceiveFrame.mLength  = 0;
    sReceiveFrame.mPsdu    = sReceivePsdu;
    sTransmitFrame.mLength = 0;
    sTransmitFrame.mPsdu   = sTransmitPsdu;

    sCurrentBandConfig = efr32RadioGetBandConfig(OPENTHREAD_CONFIG_DEFAULT_CHANNEL);
    assert(sCurrentBandConfig != NULL);

    efr32RadioSetTxPower(sTxPowerDbm);

    sEnergyScanStatus = ENERGY_SCAN_STATUS_IDLE;
    sTransmitError    = OT_ERROR_NONE;
    sTransmitBusy     = false;

    otLogInfoPlat("Initialized", NULL);
}

void efr32RadioDeinit(void)
{
    RAIL_Status_t status;

    RAIL_Idle(gRailHandle, RAIL_IDLE_ABORT, true);
    status = RAIL_ConfigEvents(gRailHandle, RAIL_EVENTS_ALL, 0);
    assert(status == RAIL_STATUS_NO_ERROR);

    sCurrentBandConfig = NULL;
}

static otError efr32StartEnergyScan(energyScanMode aMode, uint16_t aChannel, RAIL_Time_t aAveragingTimeUs)
{
    RAIL_Status_t    status;
    otError          error  = OT_ERROR_NONE;
    efr32BandConfig *config = NULL;

    otEXPECT_ACTION(sEnergyScanStatus == ENERGY_SCAN_STATUS_IDLE, error = OT_ERROR_BUSY);

    sEnergyScanStatus = ENERGY_SCAN_STATUS_IN_PROGRESS;
    sEnergyScanMode   = aMode;

    RAIL_Idle(gRailHandle, RAIL_IDLE, true);

    config = efr32RadioGetBandConfig(aChannel);
    otEXPECT_ACTION(config != NULL, error = OT_ERROR_INVALID_ARGS);

    if (sCurrentBandConfig != config)
    {
        efr32RailConfigLoad(config);
        sCurrentBandConfig = config;
    }

    status = RAIL_StartAverageRssi(gRailHandle, aChannel, aAveragingTimeUs, NULL);
    otEXPECT_ACTION(status == RAIL_STATUS_NO_ERROR, error = OT_ERROR_FAILED);

exit:
    return error;
}

void otPlatRadioGetIeeeEui64(otInstance *aInstance, uint8_t *aIeeeEui64)
{
    OT_UNUSED_VARIABLE(aInstance);

    uint64_t eui64;
    uint8_t *eui64Ptr = NULL;

    eui64    = SYSTEM_GetUnique();
    eui64Ptr = (uint8_t *)&eui64;

    for (uint8_t i = 0; i < OT_EXT_ADDRESS_SIZE; i++)
    {
        aIeeeEui64[i] = eui64Ptr[(OT_EXT_ADDRESS_SIZE - 1) - i];
    }
}

void otPlatRadioSetPanId(otInstance *aInstance, uint16_t aPanId)
{
    OT_UNUSED_VARIABLE(aInstance);

    RAIL_Status_t status;

    otLogInfoPlat("PANID=%X", aPanId);

    utilsSoftSrcMatchSetPanId(aPanId);

    for (uint8_t i = 0; i < EFR32_NUM_BAND_CONFIGS; i++)
    {
        status = RAIL_IEEE802154_SetPanId(gRailHandle, aPanId, 0);
        assert(status == RAIL_STATUS_NO_ERROR);
    }
}

void otPlatRadioSetExtendedAddress(otInstance *aInstance, const otExtAddress *aAddress)
{
    OT_UNUSED_VARIABLE(aInstance);

    RAIL_Status_t status;

    otLogInfoPlat("ExtAddr=%X%X%X%X%X%X%X%X", aAddress->m8[7], aAddress->m8[6], aAddress->m8[5], aAddress->m8[4],
                  aAddress->m8[3], aAddress->m8[2], aAddress->m8[1], aAddress->m8[0]);

    for (uint8_t i = 0; i < EFR32_NUM_BAND_CONFIGS; i++)
    {
        status = RAIL_IEEE802154_SetLongAddress(gRailHandle, (uint8_t *)aAddress->m8, 0);
        assert(status == RAIL_STATUS_NO_ERROR);
    }
}

void otPlatRadioSetShortAddress(otInstance *aInstance, uint16_t aAddress)
{
    OT_UNUSED_VARIABLE(aInstance);

    RAIL_Status_t status;

    otLogInfoPlat("ShortAddr=%X", aAddress);

    for (uint8_t i = 0; i < EFR32_NUM_BAND_CONFIGS; i++)
    {
        status = RAIL_IEEE802154_SetShortAddress(gRailHandle, aAddress, 0);
        assert(status == RAIL_STATUS_NO_ERROR);
    }
}

bool otPlatRadioIsEnabled(otInstance *aInstance)
{
    OT_UNUSED_VARIABLE(aInstance);

    return (sState != OT_RADIO_STATE_DISABLED);
}

otError otPlatRadioEnable(otInstance *aInstance)
{
    otEXPECT(!otPlatRadioIsEnabled(aInstance));

    otLogInfoPlat("State=OT_RADIO_STATE_SLEEP", NULL);
    sState = OT_RADIO_STATE_SLEEP;

exit:
    return OT_ERROR_NONE;
}

otError otPlatRadioDisable(otInstance *aInstance)
{
    otEXPECT(otPlatRadioIsEnabled(aInstance));

    otLogInfoPlat("State=OT_RADIO_STATE_DISABLED", NULL);
    sState = OT_RADIO_STATE_DISABLED;

exit:
    return OT_ERROR_NONE;
}

otError otPlatRadioSleep(otInstance *aInstance)
{
    OT_UNUSED_VARIABLE(aInstance);

    otError error = OT_ERROR_NONE;

    otEXPECT_ACTION((sState != OT_RADIO_STATE_TRANSMIT) && (sState != OT_RADIO_STATE_DISABLED),
                    error = OT_ERROR_INVALID_STATE);

    otLogInfoPlat("State=OT_RADIO_STATE_SLEEP", NULL);

    RAIL_Idle(gRailHandle, RAIL_IDLE_ABORT, true); // abort packages under reception
    sState = OT_RADIO_STATE_SLEEP;

exit:
    return error;
}

otError otPlatRadioReceive(otInstance *aInstance, uint8_t aChannel)
{
    otError          error = OT_ERROR_NONE;
    RAIL_Status_t    status;
    efr32BandConfig *config;

    OT_UNUSED_VARIABLE(aInstance);
    otEXPECT_ACTION(sState != OT_RADIO_STATE_DISABLED, error = OT_ERROR_INVALID_STATE);

    config = efr32RadioGetBandConfig(aChannel);
    otEXPECT_ACTION(config != NULL, error = OT_ERROR_INVALID_ARGS);

    if (sCurrentBandConfig != config)
    {
        RAIL_Idle(gRailHandle, RAIL_IDLE_ABORT, true);
        efr32RailConfigLoad(config);
        sCurrentBandConfig = config;
    }

    status = RAIL_StartRx(gRailHandle, aChannel, NULL);
    otEXPECT_ACTION(status == RAIL_STATUS_NO_ERROR, error = OT_ERROR_FAILED);

    otLogInfoPlat("State=OT_RADIO_STATE_RECEIVE", NULL);
    sState                 = OT_RADIO_STATE_RECEIVE;
    sReceiveFrame.mChannel = aChannel;

exit:
    return error;
}

otError otPlatRadioTransmit(otInstance *aInstance, otRadioFrame *aFrame)
{
    otError           error      = OT_ERROR_NONE;
    RAIL_CsmaConfig_t csmaConfig = RAIL_CSMA_CONFIG_802_15_4_2003_2p4_GHz_OQPSK_CSMA;
    RAIL_TxOptions_t  txOptions  = RAIL_TX_OPTIONS_DEFAULT;
    efr32BandConfig * config;
    RAIL_Status_t     status;
    uint8_t           frameLength;

    assert(sTransmitBusy == false);

    otEXPECT_ACTION((sState != OT_RADIO_STATE_DISABLED) && (sState != OT_RADIO_STATE_TRANSMIT),
                    error = OT_ERROR_INVALID_STATE);

    config = efr32RadioGetBandConfig(aFrame->mChannel);
    otEXPECT_ACTION(config != NULL, error = OT_ERROR_INVALID_ARGS);

    sState         = OT_RADIO_STATE_TRANSMIT;
    sTransmitError = OT_ERROR_NONE;
    sTransmitBusy  = true;

    if (sCurrentBandConfig != config)
    {
        RAIL_Idle(gRailHandle, RAIL_IDLE_ABORT, true);
        efr32RailConfigLoad(config);
        sCurrentBandConfig = config;
    }

    otEXPECT(aFrame->mLength >= IEEE802154_MIN_LENGTH && aFrame->mLength <= IEEE802154_MAX_LENGTH);
    frameLength = (uint8_t)aFrame->mLength;
    RAIL_WriteTxFifo(gRailHandle, &frameLength, sizeof frameLength, true);
    RAIL_WriteTxFifo(gRailHandle, aFrame->mPsdu, frameLength - 2, false);

    if (aFrame->mPsdu[0] & IEEE802154_ACK_REQUEST)
    {
        txOptions |= RAIL_TX_OPTION_WAIT_FOR_ACK;
    }

    if (aFrame->mInfo.mTxInfo.mCsmaCaEnabled)
    {
        status = RAIL_StartCcaCsmaTx(gRailHandle, aFrame->mChannel, txOptions, &csmaConfig, NULL);
    }
    else
    {
        status = RAIL_StartTx(gRailHandle, aFrame->mChannel, txOptions, NULL);
    }

    if (status == RAIL_STATUS_NO_ERROR)
    {
        otPlatRadioTxStarted(aInstance, aFrame);
    }
    else
    {
        sTransmitError = OT_ERROR_CHANNEL_ACCESS_FAILURE;
        sTransmitBusy  = false;
    }

exit:
    return error;
}

otRadioFrame *otPlatRadioGetTransmitBuffer(otInstance *aInstance)
{
    OT_UNUSED_VARIABLE(aInstance);

    return &sTransmitFrame;
}

int8_t otPlatRadioGetRssi(otInstance *aInstance)
{
    int8_t rssi = OT_RADIO_RSSI_INVALID;
    OT_UNUSED_VARIABLE(aInstance);

    if ((RAIL_GetRadioState(gRailHandle) & RAIL_RF_STATE_RX))
    {
        int16_t railRssi = RAIL_RSSI_INVALID;
        railRssi         = RAIL_GetRssi(gRailHandle, true);
        if (railRssi != RAIL_RSSI_INVALID)
        {
            rssi = railRssi / QUARTER_DBM_IN_DBM;
        }
    }

    return rssi;
}

otRadioCaps otPlatRadioGetCaps(otInstance *aInstance)
{
    OT_UNUSED_VARIABLE(aInstance);

    return OT_RADIO_CAPS_ACK_TIMEOUT | OT_RADIO_CAPS_CSMA_BACKOFF | OT_RADIO_CAPS_ENERGY_SCAN;
}

bool otPlatRadioGetPromiscuous(otInstance *aInstance)
{
    OT_UNUSED_VARIABLE(aInstance);

    return sPromiscuous;
}

void otPlatRadioSetPromiscuous(otInstance *aInstance, bool aEnable)
{
    OT_UNUSED_VARIABLE(aInstance);

    RAIL_Status_t status;

    sPromiscuous = aEnable;

    for (uint8_t i = 0; i < EFR32_NUM_BAND_CONFIGS; i++)
    {
        status = RAIL_IEEE802154_SetPromiscuousMode(gRailHandle, aEnable);
        assert(status == RAIL_STATUS_NO_ERROR);
    }
}

void otPlatRadioEnableSrcMatch(otInstance *aInstance, bool aEnable)
{
    OT_UNUSED_VARIABLE(aInstance);

    // set Frame Pending bit for all outgoing ACKs if aEnable is false
    sIsSrcMatchEnabled = aEnable;
}

static void processNextRxPacket(otInstance *aInstance)
{
    RAIL_RxPacketHandle_t  packetHandle = RAIL_RX_PACKET_HANDLE_INVALID;
    RAIL_RxPacketInfo_t    packetInfo;
    RAIL_RxPacketDetails_t packetDetails;
    RAIL_Status_t          status;
    uint16_t               length;

    packetHandle = RAIL_GetRxPacketInfo(gRailHandle, RAIL_RX_PACKET_HANDLE_OLDEST, &packetInfo);
    otEXPECT_ACTION(packetInfo.packetStatus == RAIL_RX_PACKET_READY_SUCCESS,
                    packetHandle = RAIL_RX_PACKET_HANDLE_INVALID);

    status = RAIL_GetRxPacketDetailsAlt(gRailHandle, packetHandle, &packetDetails);
    otEXPECT(status == RAIL_STATUS_NO_ERROR);

    length = packetInfo.packetBytes + 1;

    // check the length in recv packet info structure
    otEXPECT(length == packetInfo.firstPortionData[0]);

    // check the length validity of recv packet
    otEXPECT(length >= IEEE802154_MIN_LENGTH && length <= IEEE802154_MAX_LENGTH);

    otLogInfoPlat("Received data:%d", length);

    // skip length byte
    assert(packetInfo.firstPortionBytes > 0);
    packetInfo.firstPortionData++;
    packetInfo.firstPortionBytes--;
    packetInfo.packetBytes--;

    // read packet
    memcpy(sReceiveFrame.mPsdu, packetInfo.firstPortionData, packetInfo.firstPortionBytes);
    memcpy(sReceiveFrame.mPsdu + packetInfo.firstPortionBytes, packetInfo.lastPortionData,
           packetInfo.packetBytes - packetInfo.firstPortionBytes);

    status = RAIL_ReleaseRxPacket(gRailHandle, packetHandle);
    if (status == RAIL_STATUS_NO_ERROR)
    {
        packetHandle = RAIL_RX_PACKET_HANDLE_INVALID;
    }

    sReceiveFrame.mLength = length;

    if (packetDetails.isAck)
    {
        assert((length == IEEE802154_ACK_LENGTH) &&
               (sReceiveFrame.mPsdu[0] & IEEE802154_FRAME_TYPE_MASK) == IEEE802154_FRAME_TYPE_ACK);

        sTransmitBusy = false;

        if (sReceiveFrame.mPsdu[IEEE802154_DSN_OFFSET] == sTransmitFrame.mPsdu[IEEE802154_DSN_OFFSET])
        {
            sTransmitError = OT_ERROR_NONE;
        }
        else
        {
            sTransmitError = OT_ERROR_NO_ACK;
        }
    }
    else
    {
        otEXPECT(length != IEEE802154_ACK_LENGTH);

        sReceiveError = OT_ERROR_NONE;

        sReceiveFrame.mInfo.mRxInfo.mRssi = packetDetails.rssi;
        sReceiveFrame.mInfo.mRxInfo.mLqi  = packetDetails.lqi;

        // TODO: grab timestamp and handle conversion to msec/usec and RAIL_GetRxTimeSyncWordEndAlt
        // sReceiveFrame.mInfo.mRxInfo.mMsec = packetDetails.packetTime;
        // sReceiveFrame.mInfo.mRxInfo.mUsec = packetDetails.packetTime;

        // TODO Set this flag only when the packet is really acknowledged with frame pending set.
        // See https://github.com/openthread/openthread/pull/3785
        sReceiveFrame.mInfo.mRxInfo.mAckedWithFramePending = true;

#if OPENTHREAD_CONFIG_DIAG_ENABLE

        if (otPlatDiagModeGet())
        {
            otPlatDiagRadioReceiveDone(aInstance, &sReceiveFrame, sReceiveError);
        }
        else
#endif
        {
            // signal MAC layer for each received frame if promiscous is enabled
            // otherwise only signal MAC layer for non-ACK frame
            if (sPromiscuous || sReceiveFrame.mLength > IEEE802154_ACK_LENGTH)
            {
                otLogInfoPlat("Received %d bytes", sReceiveFrame.mLength);
                otPlatRadioReceiveDone(aInstance, &sReceiveFrame, sReceiveError);
            }
        }
    }

    otSysEventSignalPending();

exit:

    if (packetHandle != RAIL_RX_PACKET_HANDLE_INVALID)
    {
        RAIL_ReleaseRxPacket(gRailHandle, packetHandle);
    }
}

static void ieee802154DataRequestCommand(RAIL_Handle_t aRailHandle)
{
    RAIL_Status_t status;

    if (sIsSrcMatchEnabled)
    {
        RAIL_IEEE802154_Address_t sourceAddress;

        status = RAIL_IEEE802154_GetAddress(aRailHandle, &sourceAddress);
        assert(status == RAIL_STATUS_NO_ERROR);

        if ((sourceAddress.length == RAIL_IEEE802154_LongAddress &&
             utilsSoftSrcMatchExtFindEntry((otExtAddress *)sourceAddress.longAddress) >= 0) ||
            (sourceAddress.length == RAIL_IEEE802154_ShortAddress &&
             utilsSoftSrcMatchShortFindEntry(sourceAddress.shortAddress) >= 0))
        {
            status = RAIL_IEEE802154_SetFramePending(aRailHandle);
            assert(status == RAIL_STATUS_NO_ERROR);
        }
    }
    else
    {
        status = RAIL_IEEE802154_SetFramePending(aRailHandle);
        assert(status == RAIL_STATUS_NO_ERROR);
    }
}

static void RAILCb_Generic(RAIL_Handle_t aRailHandle, RAIL_Events_t aEvents)
{
    if (aEvents & RAIL_EVENT_IEEE802154_DATA_REQUEST_COMMAND)
    {
        ieee802154DataRequestCommand(aRailHandle);
    }
    if (aEvents & RAIL_EVENTS_TX_COMPLETION)
    {
        if (aEvents & RAIL_EVENT_TX_PACKET_SENT)
        {
            if ((sTransmitFrame.mPsdu[0] & IEEE802154_ACK_REQUEST) == 0)
            {
                sTransmitError = OT_ERROR_NONE;
                sTransmitBusy  = false;
            }
        }
        else if (aEvents & RAIL_EVENT_TX_CHANNEL_BUSY)
        {
            sTransmitError = OT_ERROR_CHANNEL_ACCESS_FAILURE;
            sTransmitBusy  = false;
        }
        else
        {
            sTransmitError = OT_ERROR_ABORT;
            sTransmitBusy  = false;
        }
    }

    if (aEvents & RAIL_EVENT_RX_ACK_TIMEOUT)
    {
        sTransmitError = OT_ERROR_NO_ACK;
        sTransmitBusy  = false;
    }

    if (aEvents & RAIL_EVENT_RX_PACKET_RECEIVED)
    {
        RAIL_HoldRxPacket(aRailHandle);
    }

    if (aEvents & RAIL_EVENT_CAL_NEEDED)
    {
        RAIL_Status_t status;

        status = RAIL_Calibrate(aRailHandle, NULL, RAIL_CAL_ALL_PENDING);
        assert(status == RAIL_STATUS_NO_ERROR);
    }

    if (aEvents & RAIL_EVENT_RSSI_AVERAGE_DONE)
    {
        const int16_t energyScanResultQuarterDbm = RAIL_GetAverageRssi(aRailHandle);

        sEnergyScanStatus = ENERGY_SCAN_STATUS_COMPLETED;

        if (energyScanResultQuarterDbm == RAIL_RSSI_INVALID)
        {
            sEnergyScanResultDbm = OT_RADIO_RSSI_INVALID;
        }
        else
        {
            sEnergyScanResultDbm = energyScanResultQuarterDbm / QUARTER_DBM_IN_DBM;
        }
    }

    otSysEventSignalPending();
}

otError otPlatRadioEnergyScan(otInstance *aInstance, uint8_t aScanChannel, uint16_t aScanDuration)
{
    OT_UNUSED_VARIABLE(aInstance);

    return efr32StartEnergyScan(ENERGY_SCAN_MODE_ASYNC, aScanChannel, (RAIL_Time_t)aScanDuration * US_IN_MS);
}

void efr32RadioProcess(otInstance *aInstance)
{
    if (sState == OT_RADIO_STATE_TRANSMIT && sTransmitBusy == false)
    {
        if (sTransmitError != OT_ERROR_NONE)
        {
            otLogDebgPlat("Transmit failed ErrorCode=%d", sTransmitError);
        }

        sState = OT_RADIO_STATE_RECEIVE;
#if OPENTHREAD_CONFIG_DIAG_ENABLE
        if (otPlatDiagModeGet())
        {
            otPlatDiagRadioTransmitDone(aInstance, &sTransmitFrame, sTransmitError);
        }
        else
#endif
            if (((sTransmitFrame.mPsdu[0] & IEEE802154_ACK_REQUEST) == 0) || (sTransmitError != OT_ERROR_NONE))
        {
            otPlatRadioTxDone(aInstance, &sTransmitFrame, NULL, sTransmitError);
        }
        else
        {
            otPlatRadioTxDone(aInstance, &sTransmitFrame, &sReceiveFrame, sTransmitError);
        }

        otSysEventSignalPending();
    }
    else if (sEnergyScanMode == ENERGY_SCAN_MODE_ASYNC && sEnergyScanStatus == ENERGY_SCAN_STATUS_COMPLETED)
    {
        sEnergyScanStatus = ENERGY_SCAN_STATUS_IDLE;
        otPlatRadioEnergyScanDone(aInstance, sEnergyScanResultDbm);
        otSysEventSignalPending();
    }

    processNextRxPacket(aInstance);
}

otError otPlatRadioGetTransmitPower(otInstance *aInstance, int8_t *aPower)
{
    OT_UNUSED_VARIABLE(aInstance);

    otError error = OT_ERROR_NONE;

    otEXPECT_ACTION(aPower != NULL, error = OT_ERROR_INVALID_ARGS);
    *aPower = sTxPowerDbm;

exit:
    return error;
}

otError otPlatRadioSetTransmitPower(otInstance *aInstance, int8_t aPower)
{
    OT_UNUSED_VARIABLE(aInstance);

    RAIL_Status_t status;

    status = RAIL_SetTxPowerDbm(gRailHandle, ((RAIL_TxPower_t)aPower) * 10);
    assert(status == RAIL_STATUS_NO_ERROR);

    sTxPowerDbm = aPower;

    return OT_ERROR_NONE;
}

int8_t otPlatRadioGetReceiveSensitivity(otInstance *aInstance)
{
    OT_UNUSED_VARIABLE(aInstance);

    return EFR32_RECEIVE_SENSITIVITY;
}
