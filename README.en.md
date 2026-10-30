<div align="center">

# 🔧 MQTTForge

**A zero-dependency, offline-first MQTT 3.1.1 toolkit**

Codec · Client · Embedded Broker · CLI — four capabilities, one package

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen?logo=pypi)](https://github.com/gitstq/MQTTForge)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Protocol](https://img.shields.io/badge/MQTT-3.1.1-orange)](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/mqtt-v3.1.1.html)
[![Tests](https://img.shields.io/badge/tests-92%20passing-brightgreen)](./tests)
[![Version](https://img.shields.io/badge/version-v1.0.0-blueviolet)](./CHANGELOG.md)

**🌐 Language**

[简体中文](./README.md) · [繁體中文](./README.zh-TW.md) · [English](./README.en.md)

</div>

---

## 🎉 About

**MQTTForge** is a **zero-dependency**, **offline-first** MQTT 3.1.1 toolkit. It packs the four things IoT developers reach for most — **packet codec, client, local broker and CLI** — into a single Python package built on the standard library alone.

### 🎯 What pain does it remove?

| 😖 The usual way | ✅ The MQTTForge way |
| --- | --- |
| Debugging MQTT means installing Mosquitto, wiring Docker, opening ports | `mqttforge broker` — an embedded broker, up in a second |
| Unit tests need a real broker, so CI is slow and flaky | The embedded broker runs in-process: **fully offline, zero network, reproducible** |
| paho-mqtt buries you in callbacks; reading one message takes glue code | `publish()` / `wait_for_message()` — a synchronous, blocking API |
| You captured raw bytes and now have to count hex digits by eye | `mqttforge decode --hex ...` gives a structured field report |
| One small library drags in a dozen transitive dependencies | **Zero runtime dependencies.** Standard library only |

### 💡 Inspiration and what we built differently

MQTTForge borrows the **product thinking** of Mosquitto, paho-mqtt and hbmqtt, but the code is 100% original and deliberately optimised for being *small, embeddable and testable*:

- 🧩 **In-process broker** — not meant to replace a production MQTT server, but to make the *complete* MQTT round trip work on any machine with nothing installed (CI, classrooms, offline debugging).
- 🔬 **A standalone codec** — `mqttforge.codec` knows nothing about sockets or threads. Hand it `bytes`, get objects back. Ideal for forensics, fuzzing and crafting malformed frames.
- 🧵 **Synchronous API, background receiver** — a blocking mental model on the outside, a receiver thread handling QoS handshakes on the inside.
- 🛡️ **Strict validation over lenient parsing** — illegal flags, illegal QoS and truncated frames raise instead of being silently swallowed. Lenient parsers are where protocol vulnerabilities hide.

> 🛈 MQTTForge is a **development / testing / teaching tool**. The embedded broker is not intended to carry production traffic — see [📦 Packaging & Deployment](#-packaging--deployment).

---

## ✨ Features

### 🧬 Protocol layer
- **All 14 control packets** — CONNECT / CONNACK / PUBLISH / PUBACK / PUBREC / PUBREL / PUBCOMP / SUBSCRIBE / SUBACK / UNSUBSCRIBE / UNSUBACK / PINGREQ / PINGRESP / DISCONNECT
- **🔁 QoS 0 / 1 / 2** — including the full PUBREC → PUBREL → PUBCOMP *exactly once* handshake
- **📐 Variable length integer** — 1–4 byte base-128 encoding, boundary values fully tested
- **🔤 Strict UTF-8** — conforms to MQTT-1.5.4; malformed UTF-8 raises instead of being replaced
- **🚦 Reserved flag validation** — PUBREL / SUBSCRIBE / UNSUBSCRIBE flags must be correct or the frame is rejected

### 🌳 Topic layer
- **➕ Single-level `+`** and **#️⃣ multi-level `#`** wildcards with full spec semantics
- **💲 `$SYS` protection** — a filter starting with a wildcard never matches a `$`-prefixed topic (MQTT-4.7.2-1)
- **✅ Publish topic validation** — accidentally using a wildcard when publishing is caught immediately
- **🧭 Filter validation** — `#` must own its level and be last; `+` must own its level

### 📡 Client
- **🔌 Synchronous blocking API** — `connect()` / `publish()` / `subscribe()` / `wait_for_message()` / `ping()`
- **🤝 Automatic acknowledgements** — the receiver thread answers PUBACK / PUBREC / PUBCOMP so QoS 2 never duplicates or loses a message
- **💓 Automatic keep-alive** — a background thread sends PINGREQ on the keep-alive interval
- **🧯 Will messages** — topic / payload / qos / retain all supported
- **🔐 Username & password auth** — CONNECT flags and payload laid out correctly
- **🧵 Thread-safe** — send lock, state lock and condition variables
- **🎭 Context manager** — `with MQTTClient(...) as c:` disconnects for you

### 🖥️ Embedded broker
- **🚀 One line to start** — `MiniBroker().start_background()` picks a free port automatically
- **📣 Fan-out** — multiple subscribers, wildcard routing, QoS downgraded to the lower value
- **📌 Retained messages** — new subscribers receive the last value immediately; an empty payload clears it
- **⚰️ Will messages** — published automatically when a client drops without sending DISCONNECT
- **📊 Live stats** — connections, publishes, deliveries and retained count

### 🛠️ CLI
- **8 sub-commands** — `selftest` / `broker` / `publish` / `subscribe` / `probe` / `decode` / `topics` / `bench`
- **🩺 One-shot self-test** — `mqttforge selftest` runs 11 end-to-end checks with **no external service**
- **🔍 Offline forensics** — hex / base64 / file input, structured output plus hexdump
- **📈 Throughput benchmark** — against a local or remote broker

### 📦 Engineering
- **🪶 Zero runtime dependencies** — standard library only; `pip install` pulls in nothing
- **🐍 Python 3.8+** — 3.8 / 3.9 / 3.10 / 3.11 / 3.12
- **🧪 92 unit and integration tests** — all offline and repeatable
- **📝 Type hints** — ships a `py.typed` marker
- **🖥️ Cross-platform** — build scripts for Linux, macOS and Windows

---

## 🚀 Quick start

### 📋 Requirements

| Item | Requirement |
| --- | --- |
| Python | **3.8+** (3.11+ recommended) |
| OS | Linux / macOS / Windows |
| Third-party packages | **None** ✅ |
| Network | **Not required** — the embedded broker is fully offline |

### 📥 Install

```bash
# 1. From source (recommended if you want to hack on it)
git clone https://github.com/gitstq/MQTTForge.git
cd MQTTForge
pip install -e .

# 2. Install a prebuilt wheel
pip install mqttforge

# 3. No install at all — run straight from the checkout
git clone https://github.com/gitstq/MQTTForge.git
cd MQTTForge
python -m mqttforge selftest
```

### ⚡ Up and running in 30 seconds

**① Self-test first:**

```bash
mqttforge selftest
```

<details>
<summary>📸 Expand expected output</summary>

```
MQTTForge self-test (embedded broker on 127.0.0.1:41679)
Python 3.11.1
  [PASS] CONNECT / CONNACK handshake - client id=selftest
  [PASS] SUBSCRIBE / SUBACK - granted qos=2
  [PASS] PUBLISH qos0 (at most once) - 10 bytes
  [PASS] PUBLISH qos1 (PUBACK handshake) - 10 bytes
  [PASS] PUBLISH qos2 (PUBREC/PUBREL/PUBCOMP) - 10 bytes
  [PASS] topic wildcard '#' fan-out - selftest/deep/nested/topic
  [PASS] PINGREQ / PINGRESP - rtt=0.13 ms
  [PASS] retained message replay - replayed b'kept'
  [PASS] UNSUBSCRIBE / UNSUBACK - filter removed
  [PASS] codec round-trip (multi-byte length) - 300-byte payload
  [PASS] DISCONNECT - graceful

11/11 checks passed
```

</details>

**② Start a local broker:**

```bash
mqttforge broker --port 1883
# MQTTForge broker listening on 127.0.0.1:1883
# Press Ctrl+C to stop.
```

**③ Subscribe in another terminal:**

```bash
mqttforge subscribe --host 127.0.0.1 -t "sensors/#" -q 1
# subscribed to 'sensors/#' (granted qos=1)
```

**④ Publish from a third terminal:**

```bash
mqttforge publish --host 127.0.0.1 -t sensors/temp -m "21.5" -q 1
# published 4 bytes to 'sensors/temp' (qos=1, retain=False)
```

The subscriber prints immediately:

```
[sensors/temp] qos=1 retain=False 21.5
```

### 🐍 Three-line Python intro

```python
from mqttforge import MQTTClient, MiniBroker

broker = MiniBroker()                      # in-process broker
host, port = broker.start_background()

with MQTTClient(client_id="demo") as client:
    client.connect(host, port)
    client.subscribe([("sensors/#", 1)])                # subscribe
    client.publish("sensors/temp", b"21.5", qos=1)      # publish
    print(client.wait_for_message(timeout=2).payload)   # b'21.5'

broker.shutdown()
```

---

## 📖 Usage guide

### 🖥️ CLI overview

| Command | Purpose | Needs a broker |
| --- | :--- | :---: |
| `mqttforge selftest` | End-to-end self-test, 11 checks | ❌ built in |
| `mqttforge broker` | Start the embedded broker | ❌ it *is* one |
| `mqttforge publish` | Publish a single message | ✅ |
| `mqttforge subscribe` | Subscribe and print messages | ✅ |
| `mqttforge probe` | Check reachability and round trip | ✅ |
| `mqttforge decode` | Decode raw MQTT bytes (hex/base64/file) | ❌ |
| `mqttforge topics` | Validate and match topic names/filters | ❌ |
| `mqttforge bench` | Throughput benchmark | ❌ optional |

> 💡 Every command supports `--help`, e.g. `mqttforge publish --help`.

---

#### 🩺 `selftest` — one-shot end-to-end check

No Mosquitto, no Docker, no network. It exercises the entire chain.

```bash
mqttforge selftest              # up to QoS 2 by default
mqttforge selftest --qos 0      # QoS 0 only, fastest
mqttforge selftest --qos 1      # up to QoS 1
```

Covers: CONNECT/CONNACK → SUBSCRIBE/SUBACK → QoS 0 → QoS 1 → QoS 2 → wildcard fan-out → PINGREQ/PINGRESP → retained replay → UNSUBSCRIBE → codec round trip → DISCONNECT.

---

#### 🖥️ `broker` — run the embedded broker

```bash
mqttforge broker                               # default 127.0.0.1:1883
mqttforge broker --host 0.0.0.0 --port 1883    # reachable from the LAN
```

> ⚠️ `--host 0.0.0.0` exposes the broker to your network, and the embedded broker has **no authentication**. Only use it on a trusted network.

---

#### 📤 `publish` — send a message

```bash
mqttforge publish --host 127.0.0.1 -t sensors/temp -m "21.5"
mqttforge publish --host 127.0.0.1 -t sensors/temp -m "21.5" -q 1
mqttforge publish --host 127.0.0.1 -t cfg/interval -m "30" -q 1 -r   # retained
mqttforge publish --host broker.example.com --username alice --password s3cret \
                  -t a/b -m "hi" -q 2
mqttforge publish --host 127.0.0.1 -t t -m "hi" \
                  --will-topic devices/1/status --will-message offline --will-qos 1
```

| Flag | Meaning |
| --- | --- |
| `-t, --topic` | Topic name (**no** wildcards) |
| `-m, --message` | Payload |
| `-q, --qos` | `0` / `1` / `2`, default `0` |
| `-r, --retain` | Mark as retained |
| `--username` / `--password` | Credentials |
| `--will-*` | Will message options |
| `--timeout` | Acknowledgement timeout in seconds, default `10` |

---

#### 📥 `subscribe` — subscribe and print

```bash
mqttforge subscribe --host 127.0.0.1 -t "sensors/#"
mqttforge subscribe --host 127.0.0.1 -t "sensors/#" -t "devices/+" -q 1
mqttforge subscribe --host 127.0.0.1 -t "sensors/#" -n 5          # stop after 5
mqttforge subscribe --host 127.0.0.1 -t "sensors/#" --duration 10 # stop after 10s
```

Output format: `[topic] qos=<level> retain=<bool> <payload>`

---

#### 📡 `probe` — reachability check

```bash
mqttforge probe --host 127.0.0.1 --port 1883
mqttforge probe --host test.mosquitto.org --port 1883
```

<details>
<summary>📸 Expand sample output</summary>

```
host            : 127.0.0.1:1883
status          : ONLINE
connect time    : 1.24 ms
ping round trip : 0.31 ms
protocol        : MQTT 3.1.1
client id       : mqttforge-3f9c1a2b8e7d
```

When the broker is unreachable it exits with code `1` and prints `OFFLINE - <reason>`, which makes it easy to drop into a health-check script.

</details>

---

#### 🔍 `decode` — offline packet forensics

Turn hex from tcpdump, Wireshark or a device log into something readable.

```bash
mqttforge decode --hex "101600044D5154540402003C000A6465766963652D303037"
mqttforge decode --hex "3214000C73656E736F72732F74656D70002A32312E35" --dump
mqttforge decode --base64 "EBYABE1RVFQEAgA8AApkZXZpY2UtMDA3"
mqttforge decode --file capture.bin --dump
```

<details>
<summary>📸 Expand sample output</summary>

```
input: 24 byte(s), 1 frame(s)
---- frame #1 ----
CONNECT
  protocol      : MQTT v4
  client id     : device-007
  clean session : True
  keep alive    : 60s
  username      : -
  password      : -
```

```
input: 22 byte(s), 1 frame(s)
---- frame #1 ----
PUBLISH
  topic         : sensors/temp
  qos           : 1 (at least once)
  retain        : False
  dup           : False
  packet id     : 42
  payload       : 4 bytes
  preview       : '21.5'
```

</details>

| Flag | Meaning |
| --- | --- |
| `--hex` | Hex string; spaces and `0x` prefixes are tolerated |
| `--base64` | Base64 encoded frame |
| `--file` | Read raw bytes from a file |
| `--dump` | Also print a hexdump |
| `--allow-partial` | Tolerate a truncated trailing frame (common in captures) |

---

#### 🌳 `topics` — topic utilities

```bash
mqttforge topics match "sensors/#" "sensors/temp"        # → True, exit 0
mqttforge topics match "sensors/+" "sensors/temp/deep"   # → False, exit 1
mqttforge topics validate "sensors/temp"                 # validate as a topic name
mqttforge topics validate "sensors/+" --filter           # validate as a topic filter
```

```
$ mqttforge topics match "sensors/#" "sensors/temp"
filter : sensors/#
topic  : sensors/temp
match  : True
```

---

#### 📈 `bench` — throughput benchmark

```bash
mqttforge bench                                  # embedded broker, 500 msgs, QoS 0
mqttforge bench -n 5000 -q 1 -s 256              # 5000 msgs, QoS 1, 256-byte payload
mqttforge bench --host 127.0.0.1 --port 1883 -n 1000 -q 2
```

<details>
<summary>📸 Expand sample output</summary>

```
using embedded broker on 127.0.0.1:38455
messages     : 200
qos          : 1
payload size : 64 bytes
elapsed      : 0.015 s
throughput   : 13077.9 msg/s
received     : 200
```

</details>

> 📊 Treat these numbers as indicative only: this is **loopback + a development-grade broker**, not the real throughput of a production MQTT server.

---

### 🐍 Python API

#### 1️⃣ Client — `MQTTClient`

```python
from mqttforge import MQTTClient
from mqttforge.packets import Will

client = MQTTClient(
    client_id="device-001",      # empty → auto-generated mqttforge-xxxx
    clean_session=True,
    keepalive=60,                # seconds; 0 disables keep-alive
    username="alice",            # optional
    password="s3cret",           # optional, str or bytes
    will=Will(topic="device/001/status", payload=b"offline", qos=1, retain=True),
    timeout=10.0,                # acknowledgement timeout
)

client.connect("127.0.0.1", 1883)

# Subscribe: a string, a dict, or a list of (filter, qos) pairs
client.subscribe("sensors/#", qos=1)                        # → [1]
client.subscribe({"sensors/#": 1, "devices/+": 2})          # → [1, 2]
client.subscribe([("sensors/#", 1), ("devices/+", 2)])      # → [1, 2]
# Returns granted_qos; -1 means the broker rejected that subscription

# Publish
client.publish("sensors/temp", b"21.5")                     # QoS 0
client.publish("sensors/temp", "21.5", qos=1)               # str is UTF-8 encoded
client.publish("cfg/interval", b"30", qos=1, retain=True)   # retained

# Receive: queue or callback
msg = client.wait_for_message(timeout=5.0)   # None on timeout
print(msg.topic, msg.payload, msg.qos, msg.retain)

# Callback style
received = []
client2 = MQTTClient(client_id="cb", on_message=lambda c, m: received.append(m))

# Keep-alive probe
rtt_ms = client.ping()          # returns round trip in milliseconds

# Unsubscribe and disconnect
client.unsubscribe(["sensors/#"])
client.disconnect()
```

**Context manager (recommended):**

```python
with MQTTClient(client_id="demo") as client:
    client.connect("127.0.0.1", 1883)
    client.publish("a/b", b"hi", qos=1)
```

**Exceptions:**

| Exception | Raised when |
| --- | --- |
| `ConnectRefused` | The broker replies with a non-zero CONNACK code (`.return_code` available) |
| `TimeoutError_` | Waiting for PUBACK / PUBREC / SUBACK timed out |
| `TopicError` | Topic name or filter is invalid |
| `CodecError` | Encoding/decoding failed (truncation, illegal type, …) |
| `ProtocolError` | Protocol violation (bad reserved flags, QoS 3, …) |

```python
from mqttforge import ConnectRefused, MQTTError

try:
    client.connect("broker.example.com", 1883)
except ConnectRefused as exc:
    print("refused, return code", exc.return_code)
except MQTTError as exc:
    print("other MQTT error", exc)
```

---

#### 2️⃣ Embedded broker — `MiniBroker`

```python
from mqttforge import MiniBroker

broker = MiniBroker(host="127.0.0.1", port=0, max_qos=2)   # port=0 → pick a free port
broker.start()
print(broker.host, broker.port)          # actual bound address

# Or in one step
broker = MiniBroker()
host, port = broker.start_background()   # → ("127.0.0.1", 49321)

# Server-side injection (simulate a device reporting in)
broker.publish("server/announce", b"maintenance in 5 min", qos=1)

# Runtime status
print(broker.stats)
# {'connections': 3, 'published': 12, 'delivered': 12, 'retained': 1}
print(broker.subscriber_count())         # live sessions

broker.shutdown()
```

**In unit tests:**

```python
import unittest
from mqttforge import MiniBroker, MQTTClient

class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.broker = MiniBroker(host="127.0.0.1", port=0)
        self.broker.start()
        self.addCleanup(self.broker.shutdown)

    def test_roundtrip(self):
        client = MQTTClient(client_id="t", timeout=5.0)
        client.connect(self.broker.host, self.broker.port, timeout=5.0)
        self.addCleanup(client.disconnect)
        client.subscribe([("test/#", 2)])
        client.publish("test/x", b"payload", qos=2)
        self.assertEqual(client.wait_for_message(timeout=5).payload, b"payload")
```

---

#### 3️⃣ Codec — no network, just bytes

```python
from mqttforge.codec import encode_packet, decode_packets, decode_hex, encode_hex
from mqttforge.packets import Connect, Publish, Subscribe, Will

# Encode: object → bytes
raw = encode_packet(
    Connect(client_id="device-007", keepalive=60,
            username="fleet", password="hunter2",
            will=Will(topic="d/007/status", payload=b"offline", qos=1, retain=True))
)

# Decode: bytes → objects (a buffer may hold several frames)
packets, leftover = decode_packets(raw)
print(packets[0].client_id)     # device-007
print(leftover)                 # b'' — bytes that did not form a full frame

# Captures often end mid-frame; allow_partial tolerates that
packets, rest = decode_packets(raw + b"\x30\x05", allow_partial=True)

# Hex helpers
hex_text = encode_hex(raw)                  # '101600044D515454...'
raw_again = decode_hex("10 16 00 04 ...")   # spaces and 0x prefixes tolerated
```

#### 4️⃣ Topic helpers

```python
from mqttforge.topics import topic_matches, validate_topic_name, validate_topic_filter

topic_matches("sport/#", "sport")                 # True ('#' also matches the parent)
topic_matches("sport/tennis/+", "sport/tennis/1") # True
topic_matches("#", "$SYS/broker/uptime")          # False ('$' topics are protected)
topic_matches("$SYS/#", "$SYS/broker/uptime")     # True

validate_topic_name("sensors/temp")   # valid, returns the topic
validate_topic_filter("sensors/+")    # valid for subscribing
# validate_topic_name("sensors/+")    # raises TopicError: no wildcards when publishing
```

#### 5️⃣ Pretty printing

```python
from mqttforge.inspect import describe, hexdump, format_packets

print(describe(packets[0]))      # structured report for one packet
print(hexdump(raw))              # classic offset / hex / ASCII view
print(format_packets(packets))   # render many at once
```

---

### 🎬 Typical use cases

| Scenario | Recommended approach |
| --- | --- |
| 🧪 **Testing MQTT-dependent code in CI** | Start `MiniBroker` in `setUp`: offline and flake-free |
| 🐛 **A device's packets do not match the spec** | `mqttforge decode --file capture.bin --dump` |
| 🏗️ **Mosquitto is not installed yet** | `mqttforge broker --port 1883` fills the gap |
| 📊 **Evaluating broker performance** | `mqttforge bench --host <broker> -q 1 -n 5000` |
| 🤖 **Generating MQTT frames from a script or LLM** | `codec.encode_packet()` produces exact bytes — no hand-written hex |
| 🎓 **Teaching the MQTT handshake** | `mqttforge selftest` walks through the packet exchanges |
| 🔌 **Embedding MQTT into your own tool** | `from mqttforge import MQTTClient` — zero deps, no dependency-tree pollution |

### 📁 Example scripts

Three runnable examples live in `examples/`:

```bash
python examples/quickstart.py          # end-to-end: QoS 0/1/2 + retained + ping
python examples/packet_forensics.py    # offline: encode → hexdump → decode back
python examples/iot_simulator.py       # simulated fleet reporting to a collector
```

---

## 💡 Design & roadmap

### 🏛️ Layering

```
┌─────────────────────────────────────────────────────────┐
│  CLI          cli.py        8 sub-commands, argparse     │
├─────────────────────────────────────────────────────────┤
│  Application  client.py  broker.py   client / broker     │
├─────────────────────────────────────────────────────────┤
│  Protocol     codec.py              14 packet codec      │
├─────────────────────────────────────────────────────────┤
│  Model        packets.py  topics.py  model / topic rules │
├─────────────────────────────────────────────────────────┤
│  Foundation   errors.py  version.py  exceptions / consts │
└─────────────────────────────────────────────────────────┘
```

**Key decisions:**

| Decision | Why |
| --- | --- |
| 🎯 Codec fully decoupled from transport | Unit tests and network tests can run separately; fuzzing needs no sockets |
| 🧵 Synchronous outside, threaded inside | A blocking API reads better, but QoS handshakes must be answered asynchronously |
| 🚦 QoS 2 forwarded only after PUBREL | Forwarding on PUBLISH would **duplicate** the message when the sender retransmits (DUP) |
| 🆔 Pooled packet identifiers | `1..65535` allocated cyclically and released on completion, avoiding collisions |
| 🛡️ Strict validation, fail fast | Lenient parsing in protocol code is a common source of vulnerabilities |
| 💲 Built-in `$SYS` protection | Implements MQTT-4.7.2-1 so `subscribe("#")` cannot swallow system topics |

### ⚠️ Known limits

- 📌 **MQTT 3.1.1 only** — MQTT 5.0 properties are not supported yet
- 🔒 **No TLS/SSL** (`mqtts://`) — tunnel it if you need encryption
- 🗃️ The embedded broker does **not persist** sessions or messages; `clean_session=False` state is discarded on restart
- 🔑 The embedded broker has **no authentication** — never expose it to the public internet
- 🌐 TCP transport only; no WebSocket
- 🧵 One thread per connection — sized for development and testing (tens to a few hundred connections)

### 🗺️ Roadmap

- **v1.1** — 🧵 asyncio client; optional broker session persistence
- **v1.2** — 🔐 TLS support; WebSocket transport
- **v1.3** — 🔑 Broker auth hooks (credential checks, ACL)
- **v2.0** — 🚀 MQTT 5.0 (properties, reason codes, shared subscriptions)

### 🙌 Where you can help

- 🧪 More malformed-frame fuzzing cases
- 🌍 Localising CLI output
- 📊 Prometheus metrics export for the broker
- 🔌 Integration examples for Home Assistant / ThingsBoard

---

## 📦 Packaging & deployment

MQTTForge is a **library + CLI** project, so it ships primarily as a **PyPI package**. There are no per-platform binaries to build.

### 📥 Install as a dependency

```bash
pip install mqttforge                 # from PyPI
pip install mqttforge==1.0.0          # pin a version
pip install -e .                      # editable install for development
```

That gives you the `mqttforge` console entry point:

```bash
mqttforge --version      # → mqttforge 1.0.0
```

### 🏗️ Build from source

```bash
# Linux / macOS / WSL / Git Bash
./build.sh                 # test → build sdist + wheel → smoke check
./build.sh --no-tests      # skip tests, build only

# Windows
build.bat
build.bat --no-tests

# Or via make
make test                  # tests only
make build                 # build
make clean                 # remove artifacts
```

Artifacts land in `dist/`:

```
dist/mqttforge-1.0.0.tar.gz                  # source distribution
dist/mqttforge-1.0.0-py3-none-any.whl        # universal wheel (pure Python)
```

> 💡 Because MQTTForge is **pure Python with zero dependencies**, the wheel is `py3-none-any`: one artifact for every platform and Python version — no per-platform builds needed.

### 📦 Single-file executable (optional)

If you need a standalone binary with no Python environment:

```bash
pip install pyinstaller
pyinstaller --onefile --name mqttforge --console mqttforge/__main__.py
# → dist/mqttforge (Linux/macOS) or dist/mqttforge.exe (Windows)
```

> ⚠️ A PyInstaller bundle is roughly 8–12 MB because it embeds the interpreter. Only worth it when you truly need dependency-free distribution; `pip install` is lighter otherwise.

### 🐳 Container deployment (optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
EXPOSE 1883
CMD ["mqttforge", "broker", "--host", "0.0.0.0", "--port", "1883"]
```

```bash
docker build -t mqttforge .
docker run -p 1883:1883 mqttforge
```

### 🧩 Embedding in your project

Being dependency free, you can also just drop the `mqttforge/` directory in:

```python
# A: as a normal dependency
from mqttforge import MQTTClient

# B: borrow only the codec (no networking at all)
from mqttforge.codec import encode_packet
from mqttforge.packets import Publish
frame = encode_packet(Publish(topic="a/b", payload=b"hi", qos=1, packet_id=1))
```

### ✅ Compatibility matrix

| Platform | Status | Notes |
| --- | :---: | --- |
| Linux (x86_64 / ARM) | ✅ | Primary development environment |
| macOS (Intel / Apple Silicon) | ✅ | Pure Python, nothing to compile |
| Windows 10/11 | ✅ | `build.bat` provided |
| Python 3.8 / 3.9 / 3.10 / 3.11 / 3.12 | ✅ | Standard library only |
| PyPy | ✅ | No C extensions |

---

## 🤝 Contributing

Contributions of every kind are welcome: 🐛 bugs, 💡 ideas, 📝 docs, 🔧 code.

### 🔀 Commit convention (Angular)

This project follows the [Angular commit convention](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit), which drives changelog generation:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Allowed types:**

| type | Meaning | Example |
| --- | --- | --- |
| `feat` | New feature | `feat(broker): support shared subscriptions` |
| `fix` | Bug fix | `fix(codec): correct 4-byte length parsing` |
| `docs` | Documentation | `docs(readme): add Windows build notes` |
| `refactor` | Refactoring | `refactor(client): extract packet-id allocation` |
| `test` | Tests | `test(topics): add $SYS matching cases` |
| `perf` | Performance | `perf(codec): avoid copies when encoding publish` |
| `chore` | Build / misc | `chore(deps): bump dev dependencies` |
| `ci` | CI config | `ci: add Python 3.12 matrix entry` |

### 🔧 Pull request checklist

1. **Fork** and branch: `git checkout -b feat/your-feature`
2. **Write code** following the existing style: type hints, docstrings, clear comments
3. **Add tests** for new behaviour under `tests/`
4. **Run everything**:
   ```bash
   python -m unittest discover -s tests -v   # unit tests
   python -m mqttforge selftest              # end-to-end self-test
   ./build.sh                                # build + smoke check
   ```
5. **Commit**: `git commit -m "feat(scope): short summary"`
6. **Push** and open a PR describing the motivation, the change, any API impact and how you verified it

### 🐛 Reporting issues

Please include:

- 🌍 Environment: Python version, OS, MQTTForge version
- 🔁 Minimal reproduction (copy-pasteable code or commands)
- 😯 Expected behaviour vs 😱 actual behaviour
- 📋 Full traceback if there is one

### 💬 Code of conduct

- Critique code, not people; keep discussions technical
- Open an issue to discuss new features first, to avoid duplicated work
- Breaking changes must be labelled `BREAKING CHANGE` in the PR

---

## 📄 License

Released under the **MIT License** — see [LICENSE](./LICENSE).

**In short, you may:**

- ✅ Use it in **commercial** projects
- ✅ Modify and redistribute the source
- ✅ Ship it inside a closed-source product
- ✅ Use it under patent claims

**The only obligation:**

- 📌 Keep the original copyright notice and MIT license text in your software and docs

**Disclaimer:** The software is provided "as is"; the authors are not liable for any loss arising from its use.

> 🔖 MIT is compatible with GPL v2/v3, Apache 2.0 and other mainstream licenses, so it is safe to add to your dependency tree.

---

<div align="center">

**🔧 MQTTForge** — MQTT debugging that works the moment you install it

If this project helped you, a ⭐ Star is much appreciated!

[⬆ Back to top](#-mqttforge)

</div>
