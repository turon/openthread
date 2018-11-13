# OpenThread BLE Platform

OpenThread provides an api for providing Bluetooth operation in conjunction
with regular IEEE 802.15.4 required for Thread.  This API allows for the
following compelling use cases:

- Thread Router or End Device also acting as a BLE Beacon
- Thread Router or End Device also acting as a GATT Server via BLE connection
- Thread Router or End Device also acting as a GATT Client via BLE connection

It is the responsibility of the platform layer to implement the low level
details to time slice between IEEE 802.15.4 and Bluetooth.

## Building

Instructions for how to build OpenThread with BLE support follows:

### Nordic NRF52840

To build as a distribution:

```./bootstrap
V=1 BLE=1 BLE_HOST=nimble make -f examples/Makefile-nrf52840

# Firmware can be found in following locations:
./output/nrf52840/bin/ot-cli-ftd.hex
./output/nrf52840/bin/ot-cli-ftd
./build/nrf52840/examples/apps/cli/ot-cli-ftd
```

Alternatively, to build directly in the local tree:

```
./configure --with-examples=posix --enable-cli-app --enable-ble --with-ble-host=nimble
make

# Firmware can be found in following locations:
./examples/apps/cli/ot-cli-ftd
```

To flash the board with the built firmware:

```
V=1 BLE=1 BLE_HOST=nimble make -f examples/Makefile-nrf52840 nrfjprog
```

To connect to cli app:

```
sudo minicom -D /dev/ttyACM0 -b 11520
```

### Linux

To build as a distribution:

```./bootstrap
V=1 BLE=1 BLE_HOST=nimble make -f examples/Makefile-posix

# Firmware can be found in following locations:
./output/nrf52840/bin/ot-cli-ftd
./build/x86_64-unknown-linux-gnu/examples/apps/cli/ot-cli-ftd
```

Alternatively, to build directly in the local tree:

```
./configure --with-examples=posix --enable-cli-app --enable-ble --with-ble-host=nimble
make

# Firmware can be found in following locations:
./examples/apps/cli/ot-cli-ftd
```

## Applications

### ot-ftd-cli ###

This shell app provides OpenThread Full Thread Device Command Line Interface.

See the [Command Reference](https://github.com/turon/openthread-bh/blob/nimble/raal/src/cli/README.md#ble) for more details on the `ble` and other commands.

```
./examples/apps/cli/ot-ftd-cli <deviceId>
```

#### BLE-only

This command sequence will start BLE-only operation.

```
./examples/apps/cli/ot-ftd-cli <deviceId>
> ble start
> ble adv start
> ble bdaddr
```

Note:

* `ble bdaddr` will output random address of device so it can be discovered.

#### Thread-only

This command sequence will start BLE-only operation.

```
./examples/apps/cli/ot-ftd-cli <deviceId> 
> ble start
> panid 1
> ifconfig up
> thread start
> ping ff02::1 200 10
```

Note:

* `ble start` required to start nimble scheduler for RAAL.
* `panid 1` required to set panid to something other than default broadcast (0xFFFF)
* `ifconfig up` turns on 15.4 radio.  This alone is enough to cause issues with the current raal implementation.
* `thread start` starts the Thread stack and will result in some TX events.
* `ping ff02::1 200 10` will trigger 10 TX events of 200 bytes each.

#### Dual: Thread / BLE

```
./examples/apps/cli/ot-ftd-cli <deviceId> 
> ble start
> ble adv start
> panid 1
> ifconfig up
> thread start
> ping ff02::1 200 10
```

## Debug GPIO

```
#define LED_2 14     // Radio mode: BLE=1, 802.15.4=0
#define LED_3 15     // Sched slot: BLE=1, RAAL=0

#define DEBUG_PIN_802154_EVT      28

#define MYNEWT_VAL_BLE_PHY_DBG_TIME_ADDRESS_END_PIN (29)
#define MYNEWT_VAL_BLE_PHY_DBG_TIME_TXRXEN_READY_PIN (30)
#define MYNEWT_VAL_BLE_PHY_DBG_TIME_WFR_PIN (31)
```
