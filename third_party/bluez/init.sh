#!/bin/bash

sudo ./repo/tools/btmgmt -i hci0 power off 
sudo ./repo/tools/btmgmt -i hci0 le on
sudo ./repo/tools/btmgmt -i hci0 connectable on
sudo ./repo/tools/btmgmt -i hci0 bredr off     # Force BLE: Disables BR/EDR !
sudo ./repo/tools/btmgmt -i hci0 advertising on
sudo ./repo/tools/btmgmt -i hci0 power on
