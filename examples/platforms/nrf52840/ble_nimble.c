/*
 *
 *    Copyright (c) 2018 Nest Labs, Inc.
 *    All rights reserved.
 *
 *    This document is the property of Nest. It is considered
 *    confidential and proprietary information.
 *
 *    This document may not be reproduced or transmitted in any form,
 *    in whole or in part, without the express written permission of
 *    Nest.
 *
 */

/**
 *    @file
 *      This file implements OpenThread BLE platform interface
 *      that maps into nlplatform port of NimBLE API.
 *
 */

#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include <common/logging.hpp>
#include <openthread/platform/ble.h>

#include "ble_nimble_event.h"

#include <nimble/nimble_npl.h>
#include <nimble/nimble_port.h>

#include "ble_l2cap_priv.h"
#include <host/ble_hs.h>
#include <host/ble_l2cap.h>
#include <nimble/ble.h>
#include <services/ans/ble_svc_ans.h>
#include <services/gap/ble_svc_gap.h>
#include <services/gatt/ble_svc_gatt.h>

#define TASK_DEFAULT_PRIORITY 1
#define TASK_DEFAULT_STACK NULL
#define TASK_DEFAULT_STACK_SIZE 400

/// Max amount of time in [ms] to scan on connection request.
#define DEFAULT_CONN_DISC_INTERVAL 1000
#define DEFAULT_ADDR_TYPE BLE_OWN_ADDR_RANDOM

#define BLE_MAX_NUM_SERVICES 2
#define BLE_MAX_NUM_CHARACTERISTICS 5
#define BLE_MAX_NUM_UUIDS (BLE_MAX_NUM_SERVICES + BLE_MAX_NUM_CHARACTERISTICS)

bool     sNimbleInitialized = false;
bool     sNimbleRunning     = false;
uint16_t sNimbleConnHandle;

//static struct ble_npl_task sTaskBleHost;
//static struct ble_npl_task sTaskBleController;
static struct ble_npl_sem  sTaskBleSyncSem;

// Note: static allocation of GATT database. Tune accordingly.
ble_uuid_any_t          sNimbleUuids[BLE_MAX_NUM_UUIDS];
struct ble_gatt_svc_def sNimbleServices[BLE_MAX_NUM_SERVICES];
struct ble_gatt_chr_def sNimbleCharacteristics[BLE_MAX_NUM_CHARACTERISTICS];

int sNimbleUuidsCount           = 0;
int sNimbleServicesCount        = 0;
int sNimbleCharacteristicsCount = 0;

#define L2CAP_COC_MTU (256)
#define L2CAP_COC_BUF_COUNT (3 * MYNEWT_VAL_BLE_L2CAP_COC_MAX_NUM)

struct ble_l2cap_chan *  sNimbleL2capChannel;
struct os_mbuf_pool      sNimbleL2capSduMbufPool;
static struct os_mempool sNimbleL2capSduMemPool;
static os_membuf_t       sNimbleL2capSduMem[OS_MEMPOOL_SIZE(L2CAP_COC_BUF_COUNT, L2CAP_COC_MTU)];

// NimBLE HCI APIs
void ble_hci_ram_init(void);
//void ble_hci_sock_set_device(int dev);
//void ble_hci_sock_ack_handler(void *param);

extern uint32_t NODE_ID;

static otError mapNimbleToOtError(int rc)
{
    otError err;

    switch (rc)
    {
    case BLE_ERR_SUCCESS:
        err = OT_ERROR_NONE;
        break;
    case BLE_ERR_UNSUPPORTED:
        err = OT_ERROR_NOT_IMPLEMENTED;
        break;
    case BLE_ERR_AUTH_FAIL:
        err = OT_ERROR_SECURITY;
        break;

    case BLE_ERR_MEM_CAPACITY:
    case BLE_HS_ENOMEM:
        err = OT_ERROR_NO_BUFS;
        break;

    case BLE_HS_EINVAL:
        err = OT_ERROR_INVALID_ARGS;
        break;
    case BLE_HS_EALREADY:
        err = OT_ERROR_ALREADY;
        break;
    case BLE_HS_ENOADDR:
        err = OT_ERROR_NO_ADDRESS;
        break;

    case BLE_HS_ENOTSYNCED:
    case BLE_HS_EPREEMPTED:
    case BLE_HS_EBUSY:
        err = OT_ERROR_BUSY;
        break;
    default:
        err = OT_ERROR_FAILED;
        break;
    }

    return err;
}

static void mapNimbleToOtAddress(ble_addr_t *nimAddr, otPlatBleDeviceAddr *otAddr)
{
    otAddr->mAddrType = nimAddr->type;
    memcpy(otAddr->mAddr, nimAddr->val, sizeof(otAddr->mAddr));
}

static void mapOtToNimbleAddress(const otPlatBleDeviceAddr *otAddr, ble_addr_t *nimAddr)
{
    nimAddr->type = otAddr->mAddrType;
    memcpy(nimAddr->val, otAddr->mAddr, sizeof(nimAddr->val));
}

static void mapNimbleToOtUuid(const ble_uuid_any_t *nimUuid, otPlatBleUuid *otUuid)
{
    switch (nimUuid->u.type)
    {
    case BLE_UUID_TYPE_16:
        otUuid->mType          = OT_BLE_UUID_TYPE_16;
        otUuid->mValue.mUuid16 = nimUuid->u16.value;
        break;

    case BLE_UUID_TYPE_32:
        otUuid->mType          = OT_BLE_UUID_TYPE_32;
        otUuid->mValue.mUuid32 = nimUuid->u32.value;
        break;

    case BLE_UUID_TYPE_128:
        otUuid->mType           = OT_BLE_UUID_TYPE_128;
        otUuid->mValue.mUuid128 = (uint8_t *)nimUuid->u128.value;
        break;

    default:
        break;
    }
}

static void mapOtToNimbleUuid(const otPlatBleUuid *otUuid, ble_uuid_any_t *nimUuid)
{
    switch (otUuid->mType)
    {
    case OT_BLE_UUID_TYPE_16:
        nimUuid->u.type    = BLE_UUID_TYPE_16;
        nimUuid->u16.value = otUuid->mValue.mUuid16;
        break;

    case OT_BLE_UUID_TYPE_32:
        nimUuid->u.type    = BLE_UUID_TYPE_32;
        nimUuid->u32.value = otUuid->mValue.mUuid32;
        break;

    case OT_BLE_UUID_TYPE_128:
        nimUuid->u.type = BLE_UUID_TYPE_128;
        memcpy(nimUuid->u128.value, otUuid->mValue.mUuid128, sizeof(nimUuid->u128.value));
        break;

    default:
        break;
    }
}

static void *task_ble_host(void *param)
{
    (void)param;

    nimble_port_run();

    return NULL;
}

static void *task_ble_controller(void *param)
{
    (void)param;

    //ble_hci_sock_ack_handler(param);

    return NULL;
}

static void ble_stack_on_sync(void)
{
    int        err;
    ble_addr_t addr;

    // Use Non-resolvable Random Private Address
    err = ble_hs_id_gen_rnd(1, &addr);
    assert(err == 0);
    err = ble_hs_id_set_rnd(addr.val);
    assert(err == 0);

    err = ble_npl_sem_release(&sTaskBleSyncSem);
}

void ble_svc_user_init(void)
{
    int rc = 0;

    ble_svc_gap_init();
    ble_svc_gatt_init();

    if (sNimbleServicesCount == 0)
    {
        // Add bogus service when no user service is passed,
        // as Nimble asserts if only GAP and GATT services defined.
        ble_svc_ans_init();
    }

    for (int i = 0; i < sNimbleServicesCount; i++)
    {
        if (sNimbleServices[i].type != BLE_GATT_SVC_TYPE_END)
        {
            rc = ble_gatts_count_cfg(&sNimbleServices[i]);
            assert(rc == 0);

            rc = ble_gatts_add_svcs(&sNimbleServices[i]);
            assert(rc == 0);
        }
    }
}

static void ble_l2cap_api_init()
{
    int rc;

    rc = os_mempool_init(&sNimbleL2capSduMemPool, L2CAP_COC_BUF_COUNT, L2CAP_COC_MTU, sNimbleL2capSduMem,
                         "ble l2cap sdu mempool");
    assert(rc == 0);

    rc = os_mbuf_pool_init(&sNimbleL2capSduMbufPool, &sNimbleL2capSduMemPool, L2CAP_COC_MTU, L2CAP_COC_BUF_COUNT);

    assert(rc == 0);
}

static void nimble_start(void)
{
    if (!sNimbleInitialized)
    {
        //ble_hci_sock_set_device(otPlatBleHciGetDeviceId(NULL));
        //ble_hci_ram_init();
        nimble_port_init();
        ble_svc_user_init();
        ble_l2cap_api_init();

        ble_hs_cfg.sync_cb = ble_stack_on_sync;
        ble_npl_sem_init(&sTaskBleSyncSem, 0);

        nimble_port_freertos_init(task_ble_host);
        
#if 0
        ble_npl_task_init(&sTaskBleController, "blc", task_ble_controller, NULL, TASK_DEFAULT_PRIORITY,
                          BLE_NPL_TIME_FOREVER, TASK_DEFAULT_STACK, TASK_DEFAULT_STACK_SIZE);

        /* Create task which handles default event queue for host stack. */
        ble_npl_task_init(&sTaskBleHost, "blh", task_ble_host, NULL, TASK_DEFAULT_PRIORITY, BLE_NPL_TIME_FOREVER,
                          TASK_DEFAULT_STACK, TASK_DEFAULT_STACK_SIZE);
#endif

        ble_npl_sem_pend(&sTaskBleSyncSem, BLE_NPL_TIME_FOREVER);
    }

    sNimbleInitialized = true;
}

otError otPlatBleEnable(otInstance *aInstance)
{
    (void)aInstance;

    sNimbleRunning = true;
    nimble_start();
    return OT_ERROR_NONE;
}

otError otPlatBleDisable(otInstance *aInstance)
{
    (void)aInstance;

    ble_hs_sched_reset(0);

    sNimbleRunning = false;

    return OT_ERROR_NONE;
}

otError otPlatBleReset(otInstance *aInstance)
{
    (void)aInstance;

    ble_hci_trans_reset();
    ble_hs_startup_go();

    return OT_ERROR_NONE;
}

bool otPlatBleIsEnabled(otInstance *aInstance)
{
    (void)aInstance;

    return sNimbleRunning;
}

//=============================================================================
//                              GAP
//=============================================================================

static int gap_event_cb(struct ble_gap_event *event, void *arg)
{
    otInstance *instance = (otInstance *)arg;

    switch (event->type)
    {
    case BLE_GAP_EVENT_CONNECT:
        sNimbleConnHandle = event->connect.conn_handle;
        dispatch_otPlatBleGapOnConnected(instance, event->connect.conn_handle);
        break;

    case BLE_GAP_EVENT_DISCONNECT:
        sNimbleConnHandle = 0;
        dispatch_otPlatBleGapOnDisconnected(instance, event->disconnect.conn.conn_handle);
        break;

    case BLE_GAP_EVENT_DISC:
    {
        otBleRadioPacket    packet;
        otPlatBleDeviceAddr address;

        packet.mValue  = event->disc.data;
        packet.mLength = event->disc.length_data;
        mapNimbleToOtAddress(&(event->disc.addr), &address);

        if (event->disc.event_type == BLE_HCI_ADV_RPT_EVTYPE_SCAN_RSP)
        {
            dispatch_otPlatBleGapOnScanRespReceived(instance, &address, &packet);
        }
        else
        {
            dispatch_otPlatBleGapOnAdvReceived(instance, &address, &packet);
        }
        break;
    }

    case BLE_GAP_EVENT_NOTIFY_RX:
    {
        otBleRadioPacket packet;
        packet.mValue  = OS_MBUF_DATA(event->notify_rx.om, uint8_t *);
        packet.mLength = OS_MBUF_PKTLEN(event->notify_rx.om);
        dispatch_otPlatBleGattClientOnIndication(instance, event->notify_rx.attr_handle, &packet);
        break;
    }

    case BLE_GAP_EVENT_NOTIFY_TX:
        if (event->notify_tx.indication && (event->notify_tx.status == BLE_HS_EDONE))
        {
            dispatch_otPlatBleGattServerOnIndicationConfirmation(instance, event->notify_tx.attr_handle);
        }
        break;

    case BLE_GAP_EVENT_SUBSCRIBE:
    {
        bool subscribing = event->subscribe.cur_indicate;
        dispatch_otPlatBleGattServerOnSubscribeRequest(instance, event->subscribe.attr_handle, subscribing);
        break;
    }

    case BLE_GAP_EVENT_DISC_COMPLETE:
        break;

    case BLE_GAP_EVENT_ADV_COMPLETE:
        break;

    case BLE_GAP_EVENT_MTU:
        dispatch_otPlatBleGattClientOnMtuExchangeResponse(instance, event->mtu.value, OT_ERROR_NONE);
        break;
    }

    return 0;
}

otError otPlatBleGapAddressGet(otInstance *aInstance, otPlatBleDeviceAddr *aAddress)
{
    int rc;

    (void)aInstance;

    aAddress->mAddrType = OT_BLE_ADDRESS_TYPE_RANDOM_STATIC;
    rc                  = ble_hs_id_copy_addr(BLE_ADDR_RANDOM, (uint8_t *)&aAddress->mAddr, NULL);

    return mapNimbleToOtError(rc);
}

otError otPlatBleGapAddressSet(otInstance *aInstance, const otPlatBleDeviceAddr *aAddress)
{
    int rc = 0;

    (void)aInstance;

    switch (aAddress->mAddrType)
    {
    case OT_BLE_ADDRESS_TYPE_PUBLIC:
        /*
         * We shouldn't be writing to the controller's address (g_dev_addr).
         * There is no standard way to set the local public address, so this is
         * our only option at the moment.
         */
        // memcpy(g_dev_addr, aAddress->mAddr, sizeof(aAddress->mAddr));
        // ble_hs_id_set_pub(g_dev_addr);
        // break;

    case OT_BLE_ADDRESS_TYPE_RANDOM_STATIC:
        rc = ble_hs_id_set_rnd(aAddress->mAddr);
        break;
    }

    return mapNimbleToOtError(rc);
}

otError otPlatBleGapServiceSet(otInstance *aInstance, const char *aDeviceName, uint16_t aAppearance)
{
    (void)aInstance;
    (void)aAppearance;

    int rc = ble_svc_gap_device_name_set(aDeviceName);
    return mapNimbleToOtError(rc);
}

otError otPlatBleGapConnParamsSet(otInstance *aInstance, const otPlatBleGapConnParams *aConnParams)
{
    (void)aInstance;
    (void)aConnParams;

    return OT_ERROR_NOT_IMPLEMENTED;
}

otError otPlatBleGapAdvDataSet(otInstance *aInstance, const uint8_t *aAdvData, uint8_t aAdvDataLength)
{
    int rc = ble_gap_adv_set_data(aAdvData, aAdvDataLength);

    (void)aInstance;

    return mapNimbleToOtError(rc);
}

otError otPlatBleGapScanResponseSet(otInstance *aInstance, const uint8_t *aScanResponse, uint8_t aScanResponseLength)
{
    int rc = ble_gap_adv_rsp_set_data(aScanResponse, aScanResponseLength);

    (void)aInstance;

    return mapNimbleToOtError(rc);
}

otError otPlatBleGapAdvStart(otInstance *aInstance, uint16_t aInterval, uint8_t aType)
{
    struct ble_gap_adv_params advp;
    int                       rc;

    (void)aInstance;
    (void)aInterval;

    memset(&advp, 0, sizeof advp);
    if (aType | OT_BLE_ADV_MODE_CONNECTABLE)
    {
        advp.conn_mode = BLE_GAP_CONN_MODE_UND;
    }
    else
    {
        advp.conn_mode = BLE_GAP_CONN_MODE_NON;
    }
    if (aType | OT_BLE_ADV_MODE_SCANNABLE)
    {
        advp.disc_mode = BLE_GAP_DISC_MODE_GEN;
    }
    else
    {
        advp.disc_mode = BLE_GAP_DISC_MODE_NON;
    }
    /* The defaults are 30 / 60 ms. */
    advp.itvl_min = BLE_GAP_ADV_FAST_INTERVAL1_MIN * 3;  /* 90 ms */
    advp.itvl_max = BLE_GAP_ADV_FAST_INTERVAL1_MIN * 4;  /* 120 ms */

    rc = ble_gap_adv_start(DEFAULT_ADDR_TYPE, NULL, BLE_HS_FOREVER, &advp, gap_event_cb, aInstance);

    return mapNimbleToOtError(rc);
}

otError otPlatBleGapAdvStop(otInstance *aInstance)
{
    int rc = ble_gap_adv_stop();

    (void)aInstance;

    return mapNimbleToOtError(rc);
}

otError otPlatBleGapScanStart(otInstance *aInstance, uint16_t aInterval, uint16_t aWindow)
{
    (void)aInstance;

    struct ble_gap_disc_params discParams;
    discParams.itvl              = aInterval;
    discParams.window            = aWindow;
    discParams.passive           = 1;
    discParams.limited           = 0;
    discParams.filter_policy     = 0;
    discParams.filter_duplicates = 0;

    int rc = ble_gap_disc(BLE_ADDR_PUBLIC, BLE_HS_FOREVER, &discParams, gap_event_cb, aInstance);

    return mapNimbleToOtError(rc);
}

otError otPlatBleGapScanStop(otInstance *aInstance)
{
    (void)aInstance;

    int rc = ble_gap_disc_cancel();

    return mapNimbleToOtError(rc);
}

otError otPlatBleGapConnect(otInstance *         aInstance,
                            otPlatBleDeviceAddr *aAddress,
                            uint16_t             aScanInterval,
                            uint16_t             aScanWindow)
{
    (void)aInstance;

    int                        rc;
    ble_addr_t                 peerAddr;
    struct ble_gap_conn_params connParams;
    connParams.scan_itvl           = aScanInterval;
    connParams.scan_window         = aScanWindow;
    connParams.itvl_min            = 40;
    connParams.itvl_max            = 56;
    connParams.latency             = 0;
    connParams.supervision_timeout = OT_BLE_CONN_SUPERVISOR_TIMEOUT_MAX;
    connParams.min_ce_len          = 0;
    connParams.max_ce_len          = 0;

    mapOtToNimbleAddress(aAddress, &peerAddr);

    rc = ble_gap_connect(aAddress->mAddrType, &peerAddr, DEFAULT_CONN_DISC_INTERVAL,
                         &connParams, gap_event_cb, aInstance);

    return mapNimbleToOtError(rc);
}

otError otPlatBleGapDisconnect(otInstance *aInstance)
{
    (void)aInstance;

    int rc;
    rc = ble_gap_terminate(sNimbleConnHandle, BLE_ERR_REM_USER_CONN_TERM);
    return mapNimbleToOtError(rc);
}

//=============================================================================
//                        GATT COMMON
//=============================================================================

/**
 * Registers vendor specific UUID Base.
 *
 * @param[in]  aInstance  The OpenThread instance structure.
 * @param[in]  aUUID      A pointer to vendor specific 128-bit UUID Base.
 *
 */
// otError otPlatBleGattVendorUuidRegister(otInstance *aInstance, const otPlatBleUuid *aUuid);

otError otPlatBleGattMtuGet(otInstance *aInstance, uint16_t *aMtu)
{
    (void)aInstance;
    (void)aMtu;

    return OT_ERROR_NOT_IMPLEMENTED;
}

static int gatt_event_cb(uint16_t conn_handle, uint16_t attr_handle, struct ble_gatt_access_ctxt *ctxt, void *arg)
{
    int         rc       = 0;
    otInstance *instance = (otInstance *)arg;

    (void)conn_handle;

    switch (ctxt->op)
    {
    case BLE_GATT_ACCESS_OP_WRITE_CHR:
    {
        otBleRadioPacket packet;
        packet.mValue  = OS_MBUF_DATA(ctxt->om, uint8_t *);
        packet.mLength = OS_MBUF_PKTLEN(ctxt->om);

        dispatch_otPlatBleGattServerOnWriteRequest(instance, attr_handle, &packet);
        break;
    }

    case BLE_GATT_ACCESS_OP_READ_CHR:
    {
        // NOTE: Not needed by WoBLE, as indicate is sent directly.
        otBleRadioPacket packet;
        dispatch_otPlatBleGattServerOnReadRequest(instance, attr_handle, &packet);

        rc = os_mbuf_append(ctxt->om, packet.mValue, packet.mLength);
        break;
    }

    case BLE_GATT_ACCESS_OP_WRITE_DSC:
    {
        // dispatch_otPlatBleGattServerOnSubscribeRequest(otInstance *aInstance, uint16_t aHandle, bool aSubscribing);
        break;
    }
    }

    return rc;
}

//=============================================================================
//                        GATT SERVER
//=============================================================================

static otError bleGattServerCharacteristicRegister(otInstance *                 aInstance,
                                                   uint16_t                     aServiceHandle,
                                                   otPlatBleGattCharacteristic *aChar,
                                                   bool                         aCccd)
{
    (void)aInstance;
    (void)aCccd;

    ble_uuid_any_t *         uuid;
    struct ble_gatt_svc_def *svc;
    struct ble_gatt_chr_def *chr;

    if (aServiceHandle >= sNimbleServicesCount)
        return OT_ERROR_INVALID_STATE;

    svc  = &sNimbleServices[aServiceHandle];
    chr  = &sNimbleCharacteristics[sNimbleCharacteristicsCount];
    uuid = &sNimbleUuids[sNimbleUuidsCount];

    mapOtToNimbleUuid(&aChar->mUuid, uuid);

    chr->access_cb  = gatt_event_cb;
    chr->uuid       = &uuid->u;
    chr->flags      = aChar->mProperties;
    chr->val_handle = &aChar->mHandleValue; // Nimble auto-fill handles in otPlatBleGattCharacteristic

    if (svc->characteristics == NULL)
    {
        svc->characteristics = chr;
    }

    sNimbleUuidsCount++;
    sNimbleCharacteristicsCount++;

    chr           = &sNimbleCharacteristics[sNimbleCharacteristicsCount];
    *(void **)chr = NULL;
    // chr->uuid = 0;

    // Nimble only supports one-time registration of entire GATT database.
    return OT_ERROR_NOT_IMPLEMENTED;
}

static otError bleGattServerServiceRegister(otInstance *aInstance, const otPlatBleUuid *aUuid, uint16_t *aHandle)
{
    (void)aInstance;

    otError error = OT_ERROR_NONE;

    ble_uuid_any_t *         uuid = &sNimbleUuids[sNimbleUuidsCount];
    struct ble_gatt_svc_def *svc  = &sNimbleServices[sNimbleServicesCount];

    // if (sNimbleServicesCount > BLE_MAX_NUM_SERVICES) return

    svc->type = BLE_GATT_SVC_TYPE_PRIMARY;
    svc->uuid = &uuid->u;
    mapOtToNimbleUuid(aUuid, uuid);
    *aHandle = sNimbleUuidsCount;

    // Increment to next slot and set it to NULL.
    sNimbleUuidsCount++;
    sNimbleServicesCount++;
    svc       = &sNimbleServices[sNimbleServicesCount];
    svc->type = BLE_GATT_SVC_TYPE_END;

    return error;
}

otError otPlatBleGattServerServicesRegister(otInstance *aInstance, otPlatBleGattService *aServices)
{
    otError                      error = OT_ERROR_NONE;
    otPlatBleGattCharacteristic *chr;

    bleGattServerServiceRegister(aInstance, &aServices->mUuid, &aServices->mHandle);

    chr = aServices->mCharacteristics;

    while (chr->mUuid.mType != OT_BLE_UUID_TYPE_NONE)
    {
        bleGattServerCharacteristicRegister(aInstance, aServices->mHandle, chr, true);
        chr++;
    }

    return error;
}

otError otPlatBleGattServerIndicate(otInstance *aInstance, uint16_t aHandle, otBleRadioPacket *aPacket)
{
    (void)aInstance;

    int             rc;
    struct os_mbuf *mbuf;

    mbuf = ble_hs_mbuf_from_flat(aPacket->mValue, aPacket->mLength);
    rc   = ble_gattc_indicate_custom(sNimbleConnHandle, aHandle, mbuf);

    otLogInfoBle(aInstance, "[BLE] %s err=%d\r\n", __func__, rc);

    return mapNimbleToOtError(rc);
}

//=============================================================================
//                        GATT CLIENT
//=============================================================================

static int on_gattc_read(uint16_t                     conn_handle,
                         const struct ble_gatt_error *error,
                         struct ble_gatt_attr *       attr,
                         void *                       arg)
{
    otInstance *     instance = (otInstance *)arg;
    otBleRadioPacket packet;

    (void)conn_handle;
    (void)error;

    packet.mValue  = OS_MBUF_DATA(attr->om, uint8_t *);
    packet.mLength = OS_MBUF_PKTLEN(attr->om);
    // packet.mPower = ;

    dispatch_otPlatBleGattClientOnReadResponse(instance, &packet);

    return 0;
}

otError otPlatBleGattClientRead(otInstance *aInstance, uint16_t aHandle)
{
    (void)aInstance;

    int rc = ble_gattc_read(sNimbleConnHandle, aHandle, on_gattc_read, aInstance);

    return mapNimbleToOtError(rc);
}

static int on_gattc_write(uint16_t                     conn_handle,
                          const struct ble_gatt_error *error,
                          struct ble_gatt_attr *       attr,
                          void *                       arg)
{
    otInstance *instance = (otInstance *)arg;

    (void)conn_handle;
    (void)error;

    dispatch_otPlatBleGattClientOnWriteResponse(instance, attr->handle);

    return 0;
}

otError otPlatBleGattClientWrite(otInstance *aInstance, uint16_t aHandle, otBleRadioPacket *aPacket)
{
    (void)aInstance;

    int rc =
        ble_gattc_write_flat(sNimbleConnHandle, aHandle, aPacket->mValue, aPacket->mLength, on_gattc_write, aInstance);

    return mapNimbleToOtError(rc);
}

otError otPlatBleGattClientSubscribeRequest(otInstance *aInstance, uint16_t aHandle, bool aSubscribing)
{
    const uint8_t kGattSubscribeReqValue[]   = {2, 0};
    const uint8_t kGattUnsubscribeReqValue[] = {0, 0};

    otBleRadioPacket packet;
    packet.mValue  = (aSubscribing) ? (uint8_t *)kGattSubscribeReqValue : (uint8_t *)kGattUnsubscribeReqValue;
    packet.mLength = sizeof(kGattSubscribeReqValue);
    return otPlatBleGattClientWrite(aInstance, aHandle, &packet);
}

/**
 * The BLE driver calls this method to notify OpenThread that subscribe response
 * has been received.
 *
 * This method is called only if @p otPlatBleGattClienSubscribe was previously requested.
 *
 * @note This function shall be used only for GATT Client.
 *
 * @param[in] aInstance  The OpenThread instance structure.
 * @param[in] aHandle    The handle on which ATT Write Response has been sent.
 *
 */
// extern void dispatch_otPlatBleGattClientOnSubscribeResponse(otInstance *aInstance, uint16_t aHandle);

static int on_gatt_disc_s(uint16_t                     conn_handle,
                          const struct ble_gatt_error *error,
                          const struct ble_gatt_svc *  service,
                          void *                       arg)
{
    otInstance *instance = (otInstance *)arg;

    (void)conn_handle;

    if (error->status == BLE_HS_EDONE)
    {
        return 0;
    }

    if (service)
    {
        dispatch_otPlatBleGattClientOnServiceDiscovered(instance, service->start_handle, service->end_handle,
                                                        service->uuid.u16.value, mapNimbleToOtError(error->status));
    }
    else
    {
        dispatch_otPlatBleGattClientOnServiceDiscovered(instance, 0xFFFF, 0xFFFF, 0xFFFF,
                                                        mapNimbleToOtError(error->status));
    }
    return 0;
}

otError otPlatBleGattClientServicesDiscover(otInstance *aInstance)
{
    int rc = ble_gattc_disc_all_svcs(sNimbleConnHandle, on_gatt_disc_s, aInstance);

    return mapNimbleToOtError(rc);
}

otError otPlatBleGattClientServiceDiscover(otInstance *aInstance, const otPlatBleUuid *aUuid)
{
    ble_uuid_any_t uuid;
    mapOtToNimbleUuid(aUuid, &uuid);

    int rc = ble_gattc_disc_svc_by_uuid(sNimbleConnHandle, &uuid.u, on_gatt_disc_s, aInstance);

    return mapNimbleToOtError(rc);
}

static int on_gatt_disc_c(uint16_t                     conn_handle,
                          const struct ble_gatt_error *error,
                          const struct ble_gatt_chr *  chr,
                          void *                       arg)
{
    otInstance *                instance = (otInstance *)arg;
    otPlatBleGattCharacteristic characterstic;

    (void)conn_handle;

    if (error->status == BLE_HS_EDONE)
    {
        return 0;
    }

    if (chr)
    {
        characterstic.mHandleValue = chr->val_handle;
        characterstic.mHandleCccd  = chr->def_handle;
        characterstic.mProperties  = chr->properties;
        mapNimbleToOtUuid(&chr->uuid, &characterstic.mUuid);
    }

    dispatch_otPlatBleGattClientOnCharacteristicsDiscoverDone(instance, &characterstic, 1,
                                                              mapNimbleToOtError(error->status));

    return 0;
}

otError otPlatBleGattClientCharacteristicsDiscover(otInstance *aInstance, uint16_t aStartHandle, uint16_t aEndHandle)
{
    int rc = ble_gattc_disc_all_chrs(sNimbleConnHandle, aStartHandle, aEndHandle, on_gatt_disc_c, aInstance);

    return mapNimbleToOtError(rc);
}

static int on_gatt_disc_d(uint16_t                     conn_handle,
                          const struct ble_gatt_error *error,
                          uint16_t                     chr_val_handle,
                          const struct ble_gatt_dsc *  dsc,
                          void *                       arg)
{
    otInstance *            instance = (otInstance *)arg;
    otPlatBleGattDescriptor desc;

    (void)conn_handle;
    (void)chr_val_handle;

    if (error->status == BLE_HS_EDONE)
    {
        return 0;
    }

    if (dsc)
    {
        desc.mHandle = dsc->handle;
        mapNimbleToOtUuid(&dsc->uuid, &desc.mUuid);
    }

    dispatch_otPlatBleGattClientOnDescriptorsDiscoverDone(instance, &desc, 1, mapNimbleToOtError(error->status));

    return 0;
}

otError otPlatBleGattClientDescriptorsDiscover(otInstance *aInstance, uint16_t aStartHandle, uint16_t aEndHandle)
{
    int rc = ble_gattc_disc_all_dscs(sNimbleConnHandle, aStartHandle, aEndHandle, on_gatt_disc_d, aInstance);

    return mapNimbleToOtError(rc);
}

static int on_gatt_mtu(uint16_t conn_handle, const struct ble_gatt_error *error, uint16_t mtu, void *arg)
{
    otInstance *instance = (otInstance *)arg;

    (void)conn_handle;

    dispatch_otPlatBleGattClientOnMtuExchangeResponse(instance, mtu, mapNimbleToOtError(error->status));

    return 0;
}

otError otPlatBleGattClientMtuExchangeRequest(otInstance *aInstance, uint16_t aMtu)
{
    (void)aMtu;

    int rc = ble_gattc_exchange_mtu(sNimbleConnHandle, on_gatt_mtu, aInstance);

    return mapNimbleToOtError(rc);
}

//=============================================================================
//                        L2CAP
//=============================================================================

static int on_l2cap_event(struct ble_l2cap_event *event, void *arg)
{
    otInstance *instance = (otInstance *)arg;

    switch (event->type)
    {
    case BLE_L2CAP_EVENT_COC_CONNECTED:
        sNimbleL2capChannel = event->connect.chan;
        dispatch_otPlatBleL2capOnConnectionRequest(instance, event->connect.chan->psm, event->connect.chan->my_mtu,
                                                   event->connect.chan->scid);
        break;

    case BLE_L2CAP_EVENT_COC_DISCONNECTED:
        sNimbleL2capChannel = NULL;
        dispatch_otPlatBleL2capOnDisconnect(instance, event->disconnect.chan->scid, event->disconnect.chan->dcid);
        break;

    case BLE_L2CAP_EVENT_COC_ACCEPT:
    {
        otPlatBleL2capConnetionResult result;
        dispatch_otPlatBleL2capOnConnectionResponse(instance, result,
                                                    event->accept.chan->peer_mtu, // event->accept.peer_sdu_size
                                                    event->accept.chan->dcid);
        break;
    }

    case BLE_L2CAP_EVENT_COC_DATA_RECEIVED:
    {
        otBleRadioPacket packet;
        packet.mValue  = OS_MBUF_DATA(event->receive.sdu_rx, uint8_t *);
        packet.mLength = OS_MBUF_PKTLEN(event->receive.sdu_rx);
        dispatch_otPlatBleL2capOnSduReceived(instance, event->receive.chan->scid, event->receive.chan->dcid, &packet);
        break;
    }

    default:
        break;
    }

    return 0;
}

otError otPlatBleL2capConnectionRequest(otInstance *aInstance, uint16_t aPsm, uint16_t aMtu, uint16_t *aCid)
{
    int rc;

    (void)aInstance;
    (void)aCid;

    struct os_mbuf *sdu_rx;

    sdu_rx = os_mbuf_get_pkthdr(&sNimbleL2capSduMbufPool, 0);
    assert(sdu_rx != NULL);

    rc = ble_l2cap_connect(sNimbleConnHandle, aPsm, aMtu, sdu_rx, on_l2cap_event, (void *)aInstance);

    return mapNimbleToOtError(rc);
}

otError otPlatBleL2capDisconnect(otInstance *aInstance, uint16_t aLocalCid, uint16_t aPeerCid)
{
    (void)aInstance;
    (void)aLocalCid;
    (void)aPeerCid;

    int rc = ble_l2cap_disconnect(sNimbleL2capChannel);

    return mapNimbleToOtError(rc);
}

otError otPlatBleL2capConnectionResponse(otInstance *                  aInstance,
                                         otPlatBleL2capConnetionResult aResult,
                                         uint16_t                      aMtu,
                                         uint16_t *                    aCid)
{
    (void)aInstance;
    (void)aResult;
    (void)aMtu;
    (void)aCid;

    return OT_ERROR_NOT_IMPLEMENTED;
}

otError otPlatBleL2capSduSend(otInstance *aInstance, uint16_t aLocalCid, uint16_t aPeerCid, otBleRadioPacket *aPacket)
{
    int             rc;
    struct os_mbuf *sdu_tx;

    (void)aInstance;
    (void)aLocalCid;
    (void)aPeerCid;
    (void)aPacket;

    sdu_tx = os_mbuf_get_pkthdr(&sNimbleL2capSduMbufPool, 0);
    if (sdu_tx == NULL)
    {
        return OT_ERROR_NO_BUFS;
    }

    rc = os_mbuf_append(sdu_tx, aPacket->mValue, aPacket->mLength);
    if (rc)
    {
        os_mbuf_free_chain(sdu_tx);
        return mapNimbleToOtError(rc);
    }

    rc = ble_l2cap_send(sNimbleL2capChannel, sdu_tx);

    return mapNimbleToOtError(rc);
}

//=============================================================================
//                        HCI
//=============================================================================

int otPlatBleHciGetDeviceId(otInstance *aInstance)
{
    (void)aInstance;

    return NODE_ID;
}

void otPlatBleHciSetDeviceId(otInstance *aInstance, int aDeviceId)
{
    (void)aInstance;

    if (aDeviceId >= 0)
    {
        otLogDebgBle(*aInstance, "otPlatBleHciSetDeviceId: %d", aDeviceId);

        NODE_ID = aDeviceId;

        ble_hci_sock_set_device(aDeviceId);
    }
}

void otPlatBleHciTick(otInstance *aInstance)
{
    (void)aInstance;

    // Relinquish time on app thread to let the BLE host thread run a bit.
    ble_npl_task_yield();
}
