# OpenThread PHY Diagnostics Example

This example application demonstrates a minimal example application
to test an OpenThread platform radio driver implementation
via a basic command-line interface.  The steps below take you through
the minimal steps required to send (tx) and receive (rx) packets between
two devices.

## 1. Build

```bash
$ cd openthread
$ ./bootstrap-configure
$ make
```

## 2. Start Node 1

Spawn the process:

```bash
$ cd openthread/examples/phy
$ ./soc --nodeid=1 -S
```

List all commands:

```bash
help
Done
```

Enter receive mode:

```bash
rx
Done
```

## 3. Start Node 2

Spawn the process:

```bash
$ cd openthread/examples/phy
$ ./soc --nodeid=2 -S
```

Transmit a burst of packets:

```bash
tx
Done
```

## 4. Want More?

You may note that the example above did not include any network parameter configuration, such as the IEEE 802.15.4 PAN ID or the Thread Master Key.  OpenThread currently implements default values for network parameters.  However, you may use the CLI to change network parameters, other configurations, and perform other operations.

See the [OpenThread CLI Reference README.md](../../src/cli/README.md) to explore more.
