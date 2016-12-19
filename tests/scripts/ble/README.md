
To run BLE simulation tests, sudo is required:

```
sudo VERBOSE=1 NODE_TYPE=sim OT_CLI_PATH=../../../examples/apps/cli/ot-cli-ftd ./test_beacon.py

sudo VERBOSE=1 NODE_TYPE=sim OT_CLI_PATH=../../../examples/apps/cli/ot-cli-ftd ./test_conn.py
```

Watch out for stray HCI simulators:

```
$ ps aux | grep btvirt

root      64552  0.0  0.0   4464   676 pts/12   S    22:25   0:00 ../../../third_party/bluez/repo/emulator/btvirt -l3 -L

$ sudo killall btvirt
```