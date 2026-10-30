<div align="center">

# 🔧 MQTTForge

**零依赖 · 离线优先的 MQTT 3.1.1 全栈工具箱**

编解码器 · 客户端 · 内嵌 Broker · 命令行工具，四条能力一条链路

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen?logo=pypi)](https://github.com/gitstq/MQTTForge)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Protocol](https://img.shields.io/badge/MQTT-3.1.1-orange)](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/mqtt-v3.1.1.html)
[![Tests](https://img.shields.io/badge/tests-92%20passing-brightgreen)](./tests)
[![Version](https://img.shields.io/badge/version-v1.0.0-blueviolet)](./CHANGELOG.md)

**🌐 语言切换 / Language / 語言切換**

[简体中文](./README.md) · [繁體中文](./README.zh-TW.md) · [English](./README.en.md)

</div>

---

## 🎉 项目介绍

**MQTTForge** 是一个**零外部依赖**、**离线优先**的 MQTT 3.1.1 全栈工具箱。它把物联网开发里最常用的四件事——**报文编解码、客户端通信、本地 Broker、命令行调试**——压缩进一个只有标准库的 Python 包里。

### 🎯 它解决什么痛点？

| 😖 传统做法的麻烦 | ✅ MQTTForge 的做法 |
| --- | --- |
| 想调试 MQTT 得先装 Mosquitto、配 Docker、开端口 | `mqttforge broker` 一条命令，内嵌 Broker 秒起 |
| 单元测试依赖真实 Broker，CI 里经常超时、偶发失败 | 内嵌 Broker 跑在同进程，测试**全离线、零网络、可重复** |
| `paho-mqtt` 回调套回调，想读一条消息要写一堆胶水代码 | `publish()` / `wait_for_message()` 同步阻塞 API，几行搞定 |
| 抓到一段二进制报文，只能靠肉眼数 hex | `mqttforge decode --hex ...` 直接出结构化字段报告 |
| 生产依赖树一大坨，装个库拖进来十几个包 | **0 个运行时依赖**，纯标准库实现 |

### 💡 灵感来源与自研差异化

MQTTForge 借鉴了 Mosquitto、paho-mqtt、hbmqtt 的**产品思路**，但代码 100% 自研，并针对"轻量、可嵌入、可测试"做了差异化设计：

- 🧩 **同进程 Broker**：不是为了替代生产级 MQTT 服务器，而是为了让**任何一台没装任何东西的机器**都能跑通完整 MQTT 链路（CI、教学、离线调试）。
- 🔬 **编解码器独立可用**：`mqttforge.codec` 不依赖 socket、不依赖线程，给它一段 `bytes` 就能出结果——做协议取证、写模糊测试、造畸形报文都方便。
- 🧵 **同步 API + 后台线程**：对外是阻塞式的心智模型，内部用接收线程处理 QoS 握手，兼顾易用性与协议完整性。
- 🛡️ **严格校验优于宽容解析**：非法标志位、非法 QoS、截断报文一律抛异常，不静默吞掉坏数据——这在协议实现里往往是安全漏洞的源头。

> 🛈 本项目定位为**开发 / 测试 / 教学工具**。内嵌 Broker 不建议直接承载生产流量，详见 [📦 打包与部署指南](#-打包与部署指南)。

---

## ✨ 核心特性

### 🧬 协议层
- **14 种控制报文全量实现** —— CONNECT / CONNACK / PUBLISH / PUBACK / PUBREC / PUBREL / PUBCOMP / SUBSCRIBE / SUBACK / UNSUBSCRIBE / UNSUBACK / PINGREQ / PINGRESP / DISCONNECT
- **🔁 QoS 0 / 1 / 2 完整支持** —— 含 PUBREC → PUBREL → PUBCOMP 的**恰好一次**四段握手
- **📐 变长长度字段**（Remaining Length）—— 1~4 字节 base-128 编解码，边界值全覆盖测试
- **🔤 UTF-8 严格校验** —— 符合 MQTT-1.5.4，畸形 UTF-8 直接报错而非静默替换
- **🚦 保留标志位校验** —— PUBREL / SUBSCRIBE / UNSUBSCRIBE 的标志位必须合规，否则拒绝解析

### 🌳 主题层
- **➕ 单层通配符 `+`** 与 **#️⃣ 多层通配符 `#`** 的完整匹配语义
- **💲 `$SYS` 保护规则** —— 以通配符开头的过滤器**不会**匹配 `$` 开头的主题（MQTT-4.7.2-1）
- **✅ 发布主题名校验** —— 发布时误用通配符会被立刻拦下
- **🧭 过滤器合法性校验** —— `#` 必须独占层级且位于末位，`+` 必须独占层级

### 📡 客户端
- **🔌 同步阻塞 API** —— `connect()` / `publish()` / `subscribe()` / `wait_for_message()` / `ping()`
- **🤝 自动应答** —— 接收线程自动回 PUBACK / PUBREC / PUBCOMP，QoS 2 不丢不重
- **💓 自动保活** —— 后台线程按 keepalive 周期发 PINGREQ
- **🧯 遗嘱消息（Will）** —— 支持 topic / payload / qos / retain 全参数
- **🔐 用户名密码认证** —— CONNECT 报文的 username / password 标志位与载荷正确编排
- **🧵 线程安全** —— 发送锁 + 状态锁 + 条件变量，多线程收发不打架
- **🎭 上下文管理器** —— `with MQTTClient(...) as c:` 自动断开

### 🖥️ 内嵌 Broker
- **🚀 一行启动** —— `MiniBroker().start_background()` 自动挑选空闲端口
- **📣 主题扇出** —— 支持多订阅者、通配符路由、QoS 降级取小值
- **📌 保留消息** —— 新订阅者立即收到历史值，空载荷可清除
- **⚰️ 遗嘱消息** —— 客户端异常断线（未发 DISCONNECT）时自动发布
- **📊 运行统计** —— 连接数、发布数、投递数、保留数一目了然

### 🛠️ 命令行
- **8 个子命令** —— `selftest` / `broker` / `publish` / `subscribe` / `probe` / `decode` / `topics` / `bench`
- **🩺 一键自检** —— `mqttforge selftest` 跑完 11 项端到端检查，**不需要任何外部服务**
- **🔍 离线报文取证** —— 支持 hex / base64 / 文件三种输入，输出结构化字段 + hexdump
- **📈 吞吐基准** —— 内置压测，可测本地或远端 Broker

### 📦 工程化
- **🪶 零运行时依赖** —— 只用标准库，`pip install` 不会拖进任何第三方包
- **🐍 Python 3.8+** —— 覆盖 3.8 / 3.9 / 3.10 / 3.11 / 3.12
- **🧪 92 个单元与集成测试** —— 全部离线、可重复执行
- **📝 类型标注** —— 附带 `py.typed` 标记
- **🖥️ 跨平台** —— Linux / macOS / Windows 构建脚本齐备

---

## 🚀 快速开始

### 📋 环境要求

| 项目 | 要求 |
| --- | --- |
| Python | **3.8 及以上**（推荐 3.11+） |
| 操作系统 | Linux / macOS / Windows 全支持 |
| 第三方依赖 | **无** ✅ |
| 网络 | **非必需** —— 内嵌 Broker 完全离线 |

### 📥 安装

```bash
# 方式一：从源码安装（推荐，便于改代码）
git clone https://github.com/gitstq/MQTTForge.git
cd MQTTForge
pip install -e .

# 方式二：安装构建好的 wheel
pip install mqttforge

# 方式三：完全不安装，直接在仓库目录里跑
git clone https://github.com/gitstq/MQTTForge.git
cd MQTTForge
python -m mqttforge selftest
```

### ⚡ 30 秒跑通

**① 先自检，确认一切正常：**

```bash
mqttforge selftest
```

<details>
<summary>📸 点击展开预期输出</summary>

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

**② 起一个本地 Broker：**

```bash
mqttforge broker --port 1883
# MQTTForge broker listening on 127.0.0.1:1883
# Press Ctrl+C to stop.
```

**③ 另开一个终端订阅：**

```bash
mqttforge subscribe --host 127.0.0.1 -t "sensors/#" -q 1
# subscribed to 'sensors/#' (granted qos=1)
```

**④ 再开一个终端发消息：**

```bash
mqttforge publish --host 127.0.0.1 -t sensors/temp -m "21.5" -q 1
# published 4 bytes to 'sensors/temp' (qos=1, retain=False)
```

订阅端会立刻打印：

```
[sensors/temp] qos=1 retain=False 21.5
```

### 🐍 三行 Python 起手式

```python
from mqttforge import MQTTClient, MiniBroker

broker = MiniBroker()                      # 起一个进程内 Broker
host, port = broker.start_background()

with MQTTClient(client_id="demo") as client:
    client.connect(host, port)
    client.subscribe([("sensors/#", 1)])   # 订阅
    client.publish("sensors/temp", b"21.5", qos=1)   # 发布
    print(client.wait_for_message(timeout=2).payload) # 收到 b'21.5'

broker.shutdown()
```

---

## 📖 详细使用指南

### 🖥️ 命令行总览

| 命令 | 作用 | 需要 Broker |
| --- | :--- | :---: |
| `mqttforge selftest` | 端到端自检，跑完 11 项检查 | ❌ 自带 |
| `mqttforge broker` | 启动内嵌 Broker | ❌ 它就是 |
| `mqttforge publish` | 发布一条消息 | ✅ |
| `mqttforge subscribe` | 订阅并打印消息 | ✅ |
| `mqttforge probe` | 探测 Broker 连通性与往返延迟 | ✅ |
| `mqttforge decode` | 离线解码 MQTT 报文（hex/base64/文件） | ❌ |
| `mqttforge topics` | 主题名/过滤器校验与匹配测试 | ❌ |
| `mqttforge bench` | 吞吐压测 | ❌ 可选自带 |

> 💡 任何命令都可以加 `--help` 查看完整参数，例如 `mqttforge publish --help`。

---

#### 🩺 `selftest` —— 一键端到端自检

不需要 Mosquitto、不需要 Docker、不需要网络，直接把整条链路跑一遍。

```bash
mqttforge selftest              # 默认跑到 QoS 2
mqttforge selftest --qos 0      # 只验证 QoS 0，最快
mqttforge selftest --qos 1      # 验证到 QoS 1
```

覆盖项：CONNECT/CONNACK 握手 → SUBSCRIBE/SUBACK → QoS 0 → QoS 1 → QoS 2 → 通配符扇出 → PINGREQ/PINGRESP → 保留消息重放 → UNSUBSCRIBE → 编解码往返 → DISCONNECT。

---

#### 🖥️ `broker` —— 启动内嵌 Broker

```bash
mqttforge broker                          # 默认 127.0.0.1:1883
mqttforge broker --host 0.0.0.0 --port 1883   # 允许局域网访问
```

> ⚠️ `--host 0.0.0.0` 会把 Broker 暴露到局域网。内嵌 Broker **没有鉴权**，请只在可信网络里使用。

---

#### 📤 `publish` —— 发布消息

```bash
mqttforge publish --host 127.0.0.1 -t sensors/temp -m "21.5"
mqttforge publish --host 127.0.0.1 -t sensors/temp -m "21.5" -q 1
mqttforge publish --host 127.0.0.1 -t cfg/interval -m "30" -q 1 -r   # 保留消息
mqttforge publish --host broker.example.com --username alice --password s3cret \
                  -t a/b -m "hi" -q 2
mqttforge publish --host 127.0.0.1 -t t -m "hi" \
                  --will-topic devices/1/status --will-message offline --will-qos 1
```

| 参数 | 说明 |
| --- | --- |
| `-t, --topic` | 主题名（**不能**含通配符） |
| `-m, --message` | 消息内容 |
| `-q, --qos` | `0` / `1` / `2`，默认 `0` |
| `-r, --retain` | 设为保留消息 |
| `--username` / `--password` | 认证信息 |
| `--will-*` | 遗嘱消息相关参数 |
| `--timeout` | 确认超时秒数，默认 `10` |

---

#### 📥 `subscribe` —— 订阅并打印

```bash
mqttforge subscribe --host 127.0.0.1 -t "sensors/#"
mqttforge subscribe --host 127.0.0.1 -t "sensors/#" -t "devices/+" -q 1
mqttforge subscribe --host 127.0.0.1 -t "sensors/#" -n 5         # 收满 5 条退出
mqttforge subscribe --host 127.0.0.1 -t "sensors/#" --duration 10 # 收 10 秒退出
```

输出格式：`[主题] qos=级别 retain=是否保留 消息内容`

---

#### 📡 `probe` —— 探测连通性

```bash
mqttforge probe --host 127.0.0.1 --port 1883
mqttforge probe --host test.mosquitto.org --port 1883
```

<details>
<summary>📸 点击展开输出示例</summary>

```
host            : 127.0.0.1:1883
status          : ONLINE
connect time    : 1.24 ms
ping round trip : 0.31 ms
protocol        : MQTT 3.1.1
client id       : mqttforge-3f9c1a2b8e7d
```

Broker 不可达时返回退出码 `1` 并打印 `OFFLINE - <原因>`，方便写进健康检查脚本。

</details>

---

#### 🔍 `decode` —— 离线报文取证

把 tcpdump、Wireshark 或设备日志里的十六进制串直接翻译成人话。

```bash
mqttforge decode --hex "101600044D5154540402003C000A6465766963652D303037"
mqttforge decode --hex "3214000C73656E736F72732F74656D70002A32312E35" --dump
mqttforge decode --base64 "EBYABE1RVFQEAgA8AApkZXZpY2UtMDA3"
mqttforge decode --file capture.bin --dump
```

<details>
<summary>📸 点击展开输出示例</summary>

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

| 参数 | 说明 |
| --- | --- |
| `--hex` | 十六进制串，空格、`0x` 前缀都容忍 |
| `--base64` | Base64 编码的报文 |
| `--file` | 直接读二进制文件 |
| `--dump` | 额外打印 hexdump |
| `--allow-partial` | 容忍末尾被截断的半包（抓包常见） |

---

#### 🌳 `topics` —— 主题工具

```bash
mqttforge topics match "sensors/#" "sensors/temp"        # → True，退出码 0
mqttforge topics match "sensors/+" "sensors/temp/deep"   # → False，退出码 1
mqttforge topics validate "sensors/temp"                 # 作为主题名校验
mqttforge topics validate "sensors/+" --filter           # 作为过滤器校验
```

```
$ mqttforge topics match "sensors/#" "sensors/temp"
filter : sensors/#
topic  : sensors/temp
match  : True
```

---

#### 📈 `bench` —— 吞吐基准

```bash
mqttforge bench                                  # 默认：内嵌 Broker，500 条，QoS 0
mqttforge bench -n 5000 -q 1 -s 256              # 5000 条，QoS 1，256 字节载荷
mqttforge bench --host 127.0.0.1 --port 1883 -n 1000 -q 2
```

<details>
<summary>📸 点击展开输出示例</summary>

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

> 📊 数字仅供参考：这是**单机回环 + 开发级 Broker** 的结果，不代表生产 MQTT 服务器的真实吞吐。

---

### 🐍 Python API

#### 1️⃣ 客户端 `MQTTClient`

```python
from mqttforge import MQTTClient
from mqttforge.packets import Will

client = MQTTClient(
    client_id="device-001",      # 留空则自动生成 mqttforge-xxxx
    clean_session=True,
    keepalive=60,                # 保活周期（秒），0 表示关闭
    username="alice",            # 可选
    password="s3cret",           # 可选，str 或 bytes
    will=Will(topic="device/001/status", payload=b"offline", qos=1, retain=True),
    timeout=10.0,                # 确认超时
)

client.connect("127.0.0.1", 1883)

# 订阅：字符串 / 字典 / (过滤器, qos) 列表，三种写法都行
client.subscribe("sensors/#", qos=1)                        # → [1]
client.subscribe({"sensors/#": 1, "devices/+": 2})          # → [1, 2]
client.subscribe([("sensors/#", 1), ("devices/+", 2)])      # → [1, 2]
# 返回 granted_qos：-1 表示该订阅被 Broker 拒绝

# 发布
client.publish("sensors/temp", b"21.5")                     # QoS 0
client.publish("sensors/temp", "21.5", qos=1)               # str 自动 UTF-8 编码
client.publish("cfg/interval", b"30", qos=1, retain=True)   # 保留消息

# 收消息：队列 + 回调两种方式
msg = client.wait_for_message(timeout=5.0)   # None 表示超时
print(msg.topic, msg.payload, msg.qos, msg.retain)

# 回调方式
received = []
client2 = MQTTClient(client_id="cb", on_message=lambda c, m: received.append(m))

# 保活探测
rtt_ms = client.ping()          # 返回往返延迟（毫秒）

# 取消订阅 & 断开
client.unsubscribe(["sensors/#"])
client.disconnect()
```

**上下文管理器写法（推荐）：**

```python
with MQTTClient(client_id="demo") as client:
    client.connect("127.0.0.1", 1883)
    client.publish("a/b", b"hi", qos=1)
```

**异常一览：**

| 异常 | 触发时机 |
| --- | --- |
| `ConnectRefused` | Broker 返回非零 CONNACK 返回码（`.return_code` 可取） |
| `TimeoutError_` | 等待 PUBACK / PUBREC / SUBACK 等超时 |
| `TopicError` | 主题名或过滤器不合法 |
| `CodecError` | 报文编解码失败（截断、非法类型等） |
| `ProtocolError` | 协议违规（保留标志位错误、QoS=3 等） |

```python
from mqttforge import ConnectRefused, MQTTError

try:
    client.connect("broker.example.com", 1883)
except ConnectRefused as exc:
    print("拒绝连接，返回码", exc.return_code)
except MQTTError as exc:
    print("其他 MQTT 错误", exc)
```

---

#### 2️⃣ 内嵌 Broker `MiniBroker`

```python
from mqttforge import MiniBroker

broker = MiniBroker(host="127.0.0.1", port=0, max_qos=2)   # port=0 → 自动挑空闲端口
broker.start()
print(broker.host, broker.port)          # 实际监听地址

# 或者一步到位
broker = MiniBroker()
host, port = broker.start_background()   # → ("127.0.0.1", 49321)

# 服务端主动注入消息（模拟设备上报，测试订阅端很有用）
broker.publish("server/announce", b"maintenance in 5 min", qos=1)

# 查看运行状态
print(broker.stats)
# {'connections': 3, 'published': 12, 'delivered': 12, 'retained': 1}
print(broker.subscriber_count())         # 当前在线会话数

broker.shutdown()
```

**在单元测试里用（`unittest` 示例）：**

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

#### 3️⃣ 编解码器 `codec`（不碰网络，纯字节）

```python
from mqttforge.codec import encode_packet, decode_packets, decode_hex, encode_hex
from mqttforge.packets import Connect, Publish, Subscribe, Will

# 编码：对象 → bytes
raw = encode_packet(
    Connect(client_id="device-007", keepalive=60,
            username="fleet", password="hunter2",
            will=Will(topic="d/007/status", payload=b"offline", qos=1, retain=True))
)

# 解码：bytes → 对象（支持一段流里包含多个报文）
packets, leftover = decode_packets(raw)
print(packets[0].client_id)     # device-007
print(leftover)                 # b'' —— 未解析完的残包

# 抓包常见半包，用 allow_partial 容忍
packets, rest = decode_packets(raw + b"\x30\x05", allow_partial=True)

# hex 互转
hex_text = encode_hex(raw)                  # '101600044D515454...'
raw_again = decode_hex("10 16 00 04 ...")   # 容忍空格与 0x 前缀
```

#### 4️⃣ 主题工具 `topics`

```python
from mqttforge.topics import topic_matches, validate_topic_name, validate_topic_filter

topic_matches("sport/#", "sport")                 # True（# 也匹配父层级）
topic_matches("sport/tennis/+", "sport/tennis/1") # True
topic_matches("#", "$SYS/broker/uptime")          # False（$ 主题受保护）
topic_matches("$SYS/#", "$SYS/broker/uptime")     # True

validate_topic_name("sensors/temp")   # 合法，原样返回
validate_topic_filter("sensors/+")    # 合法（订阅时可用）
# validate_topic_name("sensors/+")    # 抛 TopicError：发布时不能有通配符
```

#### 5️⃣ 报文美化 `inspect`

```python
from mqttforge.inspect import describe, hexdump, format_packets

print(describe(packets[0]))      # 单个报文的结构化报告
print(hexdump(raw))              # 经典 offset/hex/ASCII 三栏视图
print(format_packets(packets))   # 批量渲染
```

---

### 🎬 典型使用场景

| 场景 | 推荐做法 |
| --- | --- |
| 🧪 **CI 里测 MQTT 相关业务代码** | `MiniBroker` 起在 `setUp`，测试全离线、无 flaky |
| 🐛 **线上设备报文对不上，现场排查** | `mqttforge decode --file capture.bin --dump` |
| 🏗️ **本地开发还没装 Mosquitto** | `mqttforge broker --port 1883` 直接顶上 |
| 📊 **评估 Broker 性能** | `mqttforge bench --host <broker> -q 1 -n 5000` |
| 🤖 **给 LLM / 脚本造 MQTT 报文** | `codec.encode_packet()` 生成精确字节，不靠手拼 hex |
| 🎓 **教学演示 MQTT 握手** | `mqttforge selftest` 逐步打印 14 种报文交互 |
| 🔌 **把 MQTT 能力嵌进自己的工具** | `from mqttforge import MQTTClient` —— 0 依赖，不污染依赖树 |

### 📁 示例脚本

仓库 `examples/` 目录下有三个可以直接跑的完整示例：

```bash
python examples/quickstart.py          # 端到端：QoS 0/1/2 + 保留消息 + ping
python examples/packet_forensics.py    # 纯离线：编码 → hexdump → 解码回读
python examples/iot_simulator.py       # 模拟设备集群上报 + 采集端汇聚
```

---

## 💡 设计思路与迭代规划

### 🏛️ 架构分层

```
┌─────────────────────────────────────────────────────────┐
│  CLI 层        cli.py      8 个子命令，argparse 驱动      │
├─────────────────────────────────────────────────────────┤
│  应用层   client.py   broker.py   客户端 / 内嵌 Broker    │
├─────────────────────────────────────────────────────────┤
│  协议层        codec.py            14 种报文编解码        │
├─────────────────────────────────────────────────────────┤
│  模型层   packets.py  topics.py    数据模型 / 主题语义    │
├─────────────────────────────────────────────────────────┤
│  基础层   errors.py  version.py    异常体系 / 版本常量    │
└─────────────────────────────────────────────────────────┘
```

**关键设计决策：**

| 决策 | 原因 |
| --- | --- |
| 🎯 编解码器与传输层彻底解耦 | 单测和网络测试可以分开跑；做协议 fuzzing 不需要起 socket |
| 🧵 客户端对外同步、对内多线程 | 阻塞 API 更易读；QoS 握手又必须异步应答，所以内部用接收线程 + 条件变量 |
| 🚦 QoS 2 在收到 PUBREL 后才转发 | 如果在收到 PUBLISH 就转发，发送方重传（DUP）时会导致**重复投递** |
| 🆔 报文 ID 池化管理 | `1..65535` 循环分配，用完即还，避免并发下撞号 |
| 🛡️ 严格校验、快速失败 | 协议实现里"宽容解析"往往是漏洞温床；非法标志位一律抛异常 |
| 💲 内建 `$SYS` 保护 | 遵循 MQTT-4.7.2-1，避免 `subscribe("#")` 意外吃掉系统主题 |

### ⚠️ 已知边界

- 📌 只支持 **MQTT 3.1.1**，暂不支持 MQTT 5.0 的属性（Property）机制
- 🔒 暂不支持 **TLS/SSL**（`mqtts://`）—— 如需加密，建议在隧道层解决
- 🗃️ 内嵌 Broker **不持久化**会话与消息，重启即清空；`clean_session=False` 的会话状态不保留
- 🔑 内嵌 Broker **无鉴权**，请勿直接暴露到公网
- 🌐 只支持 TCP 传输，不支持 WebSocket
- 🧵 内嵌 Broker 采用一连接一线程模型，适合开发/测试规模（数十到数百连接）

### 🗺️ 迭代路线图

- **v1.1** —— 🧵 asyncio 异步客户端；Broker 会话持久化开关
- **v1.2** —— 🔐 TLS 支持（`ssl` 包装 socket）；WebSocket 传输
- **v1.3** —— 🔑 Broker 鉴权钩子（用户名密码校验、ACL）
- **v2.0** —— 🚀 MQTT 5.0 支持（属性、原因码、共享订阅）

### 🙌 社区贡献方向

- 🧪 更多畸形报文的模糊测试用例
- 🌍 CLI 输出的多语言本地化
- 📊 Broker 的 Prometheus 指标导出
- 🔌 与 Home Assistant / ThingsBoard 的集成示例

---

## 📦 打包与部署指南

MQTTForge 属于**工具库 + CLI** 类型，因此以 **PyPI 包** 为主要分发形式，无需为各平台单独打包二进制产物。

### 📥 作为依赖安装

```bash
pip install mqttforge                 # 从 PyPI 安装
pip install mqttforge==1.0.0          # 锁定版本
pip install -e .                      # 从源码可编辑安装（开发用）
```

安装后即可获得 `mqttforge` 命令行入口：

```bash
mqttforge --version      # → mqttforge 1.0.0
```

### 🏗️ 从源码构建分发包

```bash
# Linux / macOS / WSL / Git Bash
./build.sh                 # 跑测试 → 构建 sdist + wheel → 冒烟验证
./build.sh --no-tests      # 跳过测试，直接构建

# Windows
build.bat
build.bat --no-tests

# 或者用 make
make test                  # 只跑测试
make build                 # 构建
make clean                 # 清理产物
```

产物输出在 `dist/`：

```
dist/mqttforge-1.0.0.tar.gz                  # 源码分发包
dist/mqttforge-1.0.0-py3-none-any.whl        # 通用 wheel（纯 Python，全平台通用）
```

> 💡 因为 MQTTForge 是**纯 Python 且零依赖**，构建出的 wheel 是 `py3-none-any` —— 一个包通吃所有平台和 Python 版本，不需要按平台分别打包。

### 📦 打包成单文件可执行程序（可选）

如果你希望分发一个不需要 Python 环境的独立程序：

```bash
pip install pyinstaller
pyinstaller --onefile --name mqttforge --console mqttforge/__main__.py
# 产物：dist/mqttforge（Linux/macOS）或 dist/mqttforge.exe（Windows）
```

> ⚠️ PyInstaller 体积约 8~12 MB（含 Python 解释器）。仅在确实需要"免环境分发"时使用，常规场景直接用 `pip install` 更轻。

### 🐳 容器化部署（可选）

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

### 🧩 集成进你自己的项目

MQTTForge 零依赖，直接把 `mqttforge/` 目录拷进项目也能用：

```python
# 方式 A：作为正常依赖
from mqttforge import MQTTClient

# 方式 B：只借用编解码能力（完全不联网）
from mqttforge.codec import encode_packet
from mqttforge.packets import Publish
frame = encode_packet(Publish(topic="a/b", payload=b"hi", qos=1, packet_id=1))
```

### ✅ 兼容性矩阵

| 平台 | 状态 | 备注 |
| --- | :---: | --- |
| Linux (x86_64 / ARM) | ✅ | 主开发环境 |
| macOS (Intel / Apple Silicon) | ✅ | 纯 Python，无编译步骤 |
| Windows 10/11 | ✅ | 提供 `build.bat` |
| Python 3.8 / 3.9 / 3.10 / 3.11 / 3.12 | ✅ | 仅用标准库 |
| PyPy | ✅ | 无 C 扩展依赖 |

---

## 🤝 贡献指南

欢迎任何形式的贡献：🐛 报 bug、💡 提想法、📝 改文档、🔧 提代码。

### 🔀 提交规范（Angular 约定）

本项目严格遵循 [Angular 提交规范](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit)，这是 CI 生成 changelog 的依据：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**type 取值：**

| type | 含义 | 示例 |
| --- | --- | --- |
| `feat` | 新增功能 | `feat(broker): 支持共享订阅` |
| `fix` | 修复问题 | `fix(codec): 修正 4 字节长度字段解析` |
| `docs` | 文档更新 | `docs(readme): 补充 Windows 构建说明` |
| `refactor` | 代码重构 | `refactor(client): 提取报文 ID 分配逻辑` |
| `test` | 测试相关 | `test(topics): 补充 $SYS 匹配用例` |
| `perf` | 性能优化 | `perf(codec): 减少 publish 编码时的内存拷贝` |
| `chore` | 构建/杂项 | `chore(deps): 更新 dev 依赖` |
| `ci` | CI 配置 | `ci: 增加 Python 3.12 矩阵` |

### 🔧 提交 PR 的步骤

1. **Fork** 本仓库并新建分支：`git checkout -b feat/your-feature`
2. **写代码** —— 保持现有风格：类型标注、docstring、中英注释清晰
3. **加测试** —— 新功能必须有对应用例，放在 `tests/`
4. **跑全量校验**：
   ```bash
   python -m unittest discover -s tests -v   # 单元测试
   python -m mqttforge selftest              # 端到端自检
   ./build.sh                                # 构建 + 冒烟
   ```
5. **提交**：`git commit -m "feat(scope): 一句话说明"`
6. **推送** 并开 PR，描述里请说明：动机、改动点、是否影响现有 API、如何验证

### 🐛 反馈 Issue 的规则

提交 bug 时请尽量提供：

- 🌍 环境：Python 版本、操作系统、MQTTForge 版本
- 🔁 最小复现步骤（可复制的代码或命令）
- 😯 期望行为 vs 😱 实际行为
- 📋 完整报错堆栈（如有）

### 💬 行为准则

- 对事不对人，技术讨论保持理性
- 新特性先开 Issue 讨论，避免重复劳动
- 破坏性变更必须在 PR 里明确标注 `BREAKING CHANGE`

---

## 📄 开源协议说明

本项目基于 **MIT License** 开源，详见 [LICENSE](./LICENSE) 文件。

**简单来说，你可以：**

- ✅ 免费用于**商业项目**
- ✅ 修改源码、二次分发
- ✅ 作为闭源产品的一部分使用
- ✅ 申请专利使用

**你需要做的只有一件事：**

- 📌 在软件和文档中**保留原始的版权声明与 MIT 协议声明**

**免责声明：** 软件按"原样"提供，作者不对使用过程中产生的任何直接或间接损失承担责任。

> 🔖 协议兼容提示：MIT 与 GPL v2/v3、Apache 2.0 等主流协议均兼容，可安全引入你的项目依赖树。

---

<div align="center">

**🔧 MQTTForge** —— 让 MQTT 调试回到"装完就能跑"的状态

如果这个项目帮到了你，欢迎 ⭐ Star 支持一下！

[⬆ 回到顶部](#-mqttforge)

</div>
