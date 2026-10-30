<div align="center">

# 🔧 MQTTForge

**零依賴 · 離線優先的 MQTT 3.1.1 全棧工具箱**

編解碼器 · 用戶端 · 內嵌 Broker · 命令列工具，四種能力一條龍

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen?logo=pypi)](https://github.com/gitstq/MQTTForge)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Protocol](https://img.shields.io/badge/MQTT-3.1.1-orange)](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/mqtt-v3.1.1.html)
[![Tests](https://img.shields.io/badge/tests-92%20passing-brightgreen)](./tests)
[![Version](https://img.shields.io/badge/version-v1.0.0-blueviolet)](./CHANGELOG.md)

**🌐 語言切換 / Language / 语言切换**

[简体中文](./README.md) · [繁體中文](./README.zh-TW.md) · [English](./README.en.md)

</div>

---

## 🎉 專案介紹

**MQTTForge** 是一套**零外部依賴**、**離線優先**的 MQTT 3.1.1 全棧工具箱。它把物聯網開發最常用的四件事——**封包編解碼、用戶端通訊、本機 Broker、命令列除錯**——壓進一個只用標準程式庫的 Python 套件裡。

### 🎯 它解決什麼痛點？

| 😖 傳統做法的麻煩 | ✅ MQTTForge 的做法 |
| --- | --- |
| 想除錯 MQTT 得先裝 Mosquitto、配 Docker、開連接埠 | `mqttforge broker` 一條指令，內嵌 Broker 秒啟動 |
| 單元測試依賴真實 Broker，CI 裡經常逾時、偶發失敗 | 內嵌 Broker 跑在同行程，測試**全離線、零網路、可重現** |
| `paho-mqtt` 回呼套回呼，想讀一則訊息得寫一堆黏合程式碼 | `publish()` / `wait_for_message()` 同步阻斷式 API，幾行搞定 |
| 抓到一段二進位封包，只能靠肉眼數十六進位 | `mqttforge decode --hex ...` 直接給結構化欄位報表 |
| 生產環境依賴樹一大包，裝個小程式庫拖進十幾個套件 | **0 個執行時依賴**，純標準程式庫實作 |

### 💡 靈感來源與自研差異化

MQTTForge 借鏡了 Mosquitto、paho-mqtt、hbmqtt 的**產品思維**，但程式碼 100% 自研，並針對「輕量、可內嵌、可測試」做出差異化設計：

- 🧩 **同行程 Broker**：目的不是取代生產級 MQTT 伺服器，而是讓**任何一台什麼都沒裝的機器**都能跑通完整 MQTT 鏈路（CI、教學、離線除錯）。
- 🔬 **編解碼器獨立可用**：`mqttforge.codec` 不碰 socket、不碰執行緒，餵它一段 `bytes` 就出結果——做協定鑑識、寫模糊測試、偽造畸形封包都順手。
- 🧵 **同步 API + 背景執行緒**：對外是阻斷式的心智模型，對內用接收執行緒處理 QoS 握手，兼顧易用性與協定完整性。
- 🛡️ **嚴格校驗優於寬容解析**：非法旗標位元、非法 QoS、截斷封包一律拋出例外，不靜默吞掉壞資料——在協定實作裡，這往往正是資安漏洞的源頭。

> 🛈 本專案定位為**開發 / 測試 / 教學工具**。內嵌 Broker 不建議直接承載生產流量，詳見 [📦 封裝與部署指南](#-封裝與部署指南)。

---

## ✨ 核心特色

### 🧬 協定層
- **14 種控制封包全數實作** —— CONNECT / CONNACK / PUBLISH / PUBACK / PUBREC / PUBREL / PUBCOMP / SUBSCRIBE / SUBACK / UNSUBSCRIBE / UNSUBACK / PINGREQ / PINGRESP / DISCONNECT
- **🔁 QoS 0 / 1 / 2 完整支援** —— 含 PUBREC → PUBREL → PUBCOMP 的**恰好一次**四段握手
- **📐 變長長度欄位**（Remaining Length）—— 1~4 位元組 base-128 編解碼，邊界值完整測試
- **🔤 UTF-8 嚴格校驗** —— 符合 MQTT-1.5.4，畸形 UTF-8 直接報錯而非靜默替換
- **🚦 保留旗標校驗** —— PUBREL / SUBSCRIBE / UNSUBSCRIBE 的旗標必須合規，否則拒絕解析

### 🌳 主題層
- **➕ 單層萬用字元 `+`** 與 **#️⃣ 多層萬用字元 `#`** 的完整比對語義
- **💲 `$SYS` 保護規則** —— 以萬用字元開頭的過濾器**不會**比對 `$` 開頭的主題（MQTT-4.7.2-1）
- **✅ 發布主題名校驗** —— 發布時誤用萬用字元會被立刻攔下
- **🧭 過濾器合法性校驗** —— `#` 必須獨佔層級且位於末位，`+` 必須獨佔層級

### 📡 用戶端
- **🔌 同步阻斷式 API** —— `connect()` / `publish()` / `subscribe()` / `wait_for_message()` / `ping()`
- **🤝 自動應答** —— 接收執行緒自動回 PUBACK / PUBREC / PUBCOMP，QoS 2 不丟不重複
- **💓 自動保活** —— 背景執行緒依 keepalive 週期送出 PINGREQ
- **🧯 遺囑訊息（Will）** —— 支援 topic / payload / qos / retain 全參數
- **🔐 帳號密碼驗證** —— CONNECT 封包的 username / password 旗標與酬載正確編排
- **🧵 執行緒安全** —— 傳送鎖 + 狀態鎖 + 條件變數，多執行緒收發不打架
- **🎭 情境管理器** —— `with MQTTClient(...) as c:` 自動斷線

### 🖥️ 內嵌 Broker
- **🚀 一行啟動** —— `MiniBroker().start_background()` 自動挑選閒置連接埠
- **📣 主題扇出** —— 支援多訂閱者、萬用字元路由、QoS 降級取小值
- **📌 保留訊息** —— 新訂閱者立即收到歷史值，空酬載可清除
- **⚰️ 遺囑訊息** —— 用戶端異常斷線（未送 DISCONNECT）時自動發布
- **📊 執行統計** —— 連線數、發布數、投遞數、保留數一目了然

### 🛠️ 命令列
- **8 個子命令** —— `selftest` / `broker` / `publish` / `subscribe` / `probe` / `decode` / `topics` / `bench`
- **🩺 一鍵自檢** —— `mqttforge selftest` 跑完 11 項端到端檢查，**不需要任何外部服務**
- **🔍 離線封包鑑識** —— 支援 hex / base64 / 檔案三種輸入，輸出結構化欄位 + hexdump
- **📈 吞吐基準** —— 內建壓測，可測本機或遠端 Broker

### 📦 工程化
- **🪶 零執行時依賴** —— 只用標準程式庫，`pip install` 不會拖進任何第三方套件
- **🐍 Python 3.8+** —— 涵蓋 3.8 / 3.9 / 3.10 / 3.11 / 3.12
- **🧪 92 個單元與整合測試** —— 全部離線、可重複執行
- **📝 型別標註** —— 附帶 `py.typed` 標記
- **🖥️ 跨平台** —— Linux / macOS / Windows 建置指令碼齊備

---

## 🚀 快速開始

### 📋 環境需求

| 項目 | 需求 |
| --- | --- |
| Python | **3.8 以上**（建議 3.11+） |
| 作業系統 | Linux / macOS / Windows 全支援 |
| 第三方依賴 | **無** ✅ |
| 網路 | **非必要** —— 內嵌 Broker 完全離線 |

### 📥 安裝

```bash
# 方式一：從原始碼安裝（推薦，方便改程式碼）
git clone https://github.com/gitstq/MQTTForge.git
cd MQTTForge
pip install -e .

# 方式二：安裝建置好的 wheel
pip install mqttforge

# 方式三：完全不安裝，直接在儲存庫目錄裡跑
git clone https://github.com/gitstq/MQTTForge.git
cd MQTTForge
python -m mqttforge selftest
```

### ⚡ 30 秒跑通

**① 先自檢，確認一切正常：**

```bash
mqttforge selftest
```

<details>
<summary>📸 點擊展開預期輸出</summary>

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

**② 起一個本機 Broker：**

```bash
mqttforge broker --port 1883
# MQTTForge broker listening on 127.0.0.1:1883
# Press Ctrl+C to stop.
```

**③ 另開一個終端機訂閱：**

```bash
mqttforge subscribe --host 127.0.0.1 -t "sensors/#" -q 1
# subscribed to 'sensors/#' (granted qos=1)
```

**④ 再開一個終端機發訊息：**

```bash
mqttforge publish --host 127.0.0.1 -t sensors/temp -m "21.5" -q 1
# published 4 bytes to 'sensors/temp' (qos=1, retain=False)
```

訂閱端會立刻列印：

```
[sensors/temp] qos=1 retain=False 21.5
```

### 🐍 三行 Python 起手式

```python
from mqttforge import MQTTClient, MiniBroker

broker = MiniBroker()                      # 起一個行程內 Broker
host, port = broker.start_background()

with MQTTClient(client_id="demo") as client:
    client.connect(host, port)
    client.subscribe([("sensors/#", 1)])            # 訂閱
    client.publish("sensors/temp", b"21.5", qos=1)  # 發布
    print(client.wait_for_message(timeout=2).payload)   # 收到 b'21.5'

broker.shutdown()
```

---

## 📖 詳細使用指南

### 🖥️ 命令列總覽

| 指令 | 作用 | 需要 Broker |
| --- | :--- | :---: |
| `mqttforge selftest` | 端到端自檢，跑完 11 項檢查 | ❌ 自帶 |
| `mqttforge broker` | 啟動內嵌 Broker | ❌ 它就是 |
| `mqttforge publish` | 發布一則訊息 | ✅ |
| `mqttforge subscribe` | 訂閱並列印訊息 | ✅ |
| `mqttforge probe` | 探測 Broker 連通性與往返延遲 | ✅ |
| `mqttforge decode` | 離線解碼 MQTT 封包（hex/base64/檔案） | ❌ |
| `mqttforge topics` | 主題名／過濾器校驗與比對測試 | ❌ |
| `mqttforge bench` | 吞吐壓測 | ❌ 可選自帶 |

> 💡 任何指令都可以加 `--help` 查看完整參數，例如 `mqttforge publish --help`。

---

#### 🩺 `selftest` —— 一鍵端到端自檢

不需要 Mosquitto、不需要 Docker、不需要網路，直接把整條鏈路跑一遍。

```bash
mqttforge selftest              # 預設跑到 QoS 2
mqttforge selftest --qos 0      # 只驗證 QoS 0，最快
mqttforge selftest --qos 1      # 驗證到 QoS 1
```

涵蓋項目：CONNECT/CONNACK 握手 → SUBSCRIBE/SUBACK → QoS 0 → QoS 1 → QoS 2 → 萬用字元扇出 → PINGREQ/PINGRESP → 保留訊息重播 → UNSUBSCRIBE → 編解碼往返 → DISCONNECT。

---

#### 🖥️ `broker` —— 啟動內嵌 Broker

```bash
mqttforge broker                               # 預設 127.0.0.1:1883
mqttforge broker --host 0.0.0.0 --port 1883    # 允許區域網路存取
```

> ⚠️ `--host 0.0.0.0` 會把 Broker 暴露到區域網路。內嵌 Broker **沒有鑑權**，請只在可信網路裡使用。

---

#### 📤 `publish` —— 發布訊息

```bash
mqttforge publish --host 127.0.0.1 -t sensors/temp -m "21.5"
mqttforge publish --host 127.0.0.1 -t sensors/temp -m "21.5" -q 1
mqttforge publish --host 127.0.0.1 -t cfg/interval -m "30" -q 1 -r   # 保留訊息
mqttforge publish --host broker.example.com --username alice --password s3cret \
                  -t a/b -m "hi" -q 2
mqttforge publish --host 127.0.0.1 -t t -m "hi" \
                  --will-topic devices/1/status --will-message offline --will-qos 1
```

| 參數 | 說明 |
| --- | --- |
| `-t, --topic` | 主題名（**不能**含萬用字元） |
| `-m, --message` | 訊息內容 |
| `-q, --qos` | `0` / `1` / `2`，預設 `0` |
| `-r, --retain` | 設為保留訊息 |
| `--username` / `--password` | 驗證資訊 |
| `--will-*` | 遺囑訊息相關參數 |
| `--timeout` | 確認逾時秒數，預設 `10` |

---

#### 📥 `subscribe` —— 訂閱並列印

```bash
mqttforge subscribe --host 127.0.0.1 -t "sensors/#"
mqttforge subscribe --host 127.0.0.1 -t "sensors/#" -t "devices/+" -q 1
mqttforge subscribe --host 127.0.0.1 -t "sensors/#" -n 5          # 收滿 5 則結束
mqttforge subscribe --host 127.0.0.1 -t "sensors/#" --duration 10 # 收 10 秒結束
```

輸出格式：`[主題] qos=等級 retain=是否保留 訊息內容`

---

#### 📡 `probe` —— 探測連通性

```bash
mqttforge probe --host 127.0.0.1 --port 1883
mqttforge probe --host test.mosquitto.org --port 1883
```

<details>
<summary>📸 點擊展開輸出範例</summary>

```
host            : 127.0.0.1:1883
status          : ONLINE
connect time    : 1.24 ms
ping round trip : 0.31 ms
protocol        : MQTT 3.1.1
client id       : mqttforge-3f9c1a2b8e7d
```

Broker 無法連上時回傳結束碼 `1` 並列印 `OFFLINE - <原因>`，方便寫進健康檢查指令碼。

</details>

---

#### 🔍 `decode` —— 離線封包鑑識

把 tcpdump、Wireshark 或設備日誌裡的十六進位字串直接翻譯成人話。

```bash
mqttforge decode --hex "101600044D5154540402003C000A6465766963652D303037"
mqttforge decode --hex "3214000C73656E736F72732F74656D70002A32312E35" --dump
mqttforge decode --base64 "EBYABE1RVFQEAgA8AApkZXZpY2UtMDA3"
mqttforge decode --file capture.bin --dump
```

<details>
<summary>📸 點擊展開輸出範例</summary>

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

| 參數 | 說明 |
| --- | --- |
| `--hex` | 十六進位字串，空格、`0x` 前綴都容忍 |
| `--base64` | Base64 編碼的封包 |
| `--file` | 直接讀二進位檔案 |
| `--dump` | 額外列印 hexdump |
| `--allow-partial` | 容忍末尾被截斷的半包（抓包常見） |

---

#### 🌳 `topics` —— 主題工具

```bash
mqttforge topics match "sensors/#" "sensors/temp"        # → True，結束碼 0
mqttforge topics match "sensors/+" "sensors/temp/deep"   # → False，結束碼 1
mqttforge topics validate "sensors/temp"                 # 作為主題名校驗
mqttforge topics validate "sensors/+" --filter           # 作為過濾器校驗
```

```
$ mqttforge topics match "sensors/#" "sensors/temp"
filter : sensors/#
topic  : sensors/temp
match  : True
```

---

#### 📈 `bench` —— 吞吐基準

```bash
mqttforge bench                                  # 預設：內嵌 Broker，500 則，QoS 0
mqttforge bench -n 5000 -q 1 -s 256              # 5000 則，QoS 1，256 位元組酬載
mqttforge bench --host 127.0.0.1 --port 1883 -n 1000 -q 2
```

<details>
<summary>📸 點擊展開輸出範例</summary>

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

> 📊 數字僅供參考：這是**單機回環 + 開發級 Broker** 的結果，不代表生產 MQTT 伺服器的真實吞吐。

---

### 🐍 Python API

#### 1️⃣ 用戶端 `MQTTClient`

```python
from mqttforge import MQTTClient
from mqttforge.packets import Will

client = MQTTClient(
    client_id="device-001",      # 留空則自動生成 mqttforge-xxxx
    clean_session=True,
    keepalive=60,                # 保活週期（秒），0 表示關閉
    username="alice",            # 選用
    password="s3cret",           # 選用，str 或 bytes
    will=Will(topic="device/001/status", payload=b"offline", qos=1, retain=True),
    timeout=10.0,                # 確認逾時
)

client.connect("127.0.0.1", 1883)

# 訂閱：字串 / 字典 / (過濾器, qos) 清單，三種寫法都行
client.subscribe("sensors/#", qos=1)                        # → [1]
client.subscribe({"sensors/#": 1, "devices/+": 2})          # → [1, 2]
client.subscribe([("sensors/#", 1), ("devices/+", 2)])      # → [1, 2]
# 回傳 granted_qos：-1 表示該訂閱被 Broker 拒絕

# 發布
client.publish("sensors/temp", b"21.5")                     # QoS 0
client.publish("sensors/temp", "21.5", qos=1)               # str 自動 UTF-8 編碼
client.publish("cfg/interval", b"30", qos=1, retain=True)   # 保留訊息

# 收訊息：佇列 + 回呼兩種方式
msg = client.wait_for_message(timeout=5.0)   # None 表示逾時
print(msg.topic, msg.payload, msg.qos, msg.retain)

# 回呼寫法
received = []
client2 = MQTTClient(client_id="cb", on_message=lambda c, m: received.append(m))

# 保活探測
rtt_ms = client.ping()          # 回傳往返延遲（毫秒）

# 取消訂閱 & 斷線
client.unsubscribe(["sensors/#"])
client.disconnect()
```

**情境管理器寫法（推薦）：**

```python
with MQTTClient(client_id="demo") as client:
    client.connect("127.0.0.1", 1883)
    client.publish("a/b", b"hi", qos=1)
```

**例外一覽：**

| 例外 | 觸發時機 |
| --- | --- |
| `ConnectRefused` | Broker 回傳非零 CONNACK 回傳碼（`.return_code` 可取） |
| `TimeoutError_` | 等待 PUBACK / PUBREC / SUBACK 等逾時 |
| `TopicError` | 主題名或過濾器不合法 |
| `CodecError` | 封包編解碼失敗（截斷、非法類型等） |
| `ProtocolError` | 協定違規（保留旗標錯誤、QoS=3 等） |

```python
from mqttforge import ConnectRefused, MQTTError

try:
    client.connect("broker.example.com", 1883)
except ConnectRefused as exc:
    print("拒絕連線，回傳碼", exc.return_code)
except MQTTError as exc:
    print("其他 MQTT 錯誤", exc)
```

---

#### 2️⃣ 內嵌 Broker `MiniBroker`

```python
from mqttforge import MiniBroker

broker = MiniBroker(host="127.0.0.1", port=0, max_qos=2)   # port=0 → 自動挑閒置埠
broker.start()
print(broker.host, broker.port)          # 實際監聽位址

# 或者一步到位
broker = MiniBroker()
host, port = broker.start_background()   # → ("127.0.0.1", 49321)

# 伺服器端主動注入訊息（模擬設備回報，測試訂閱端很有用）
broker.publish("server/announce", b"maintenance in 5 min", qos=1)

# 查看執行狀態
print(broker.stats)
# {'connections': 3, 'published': 12, 'delivered': 12, 'retained': 1}
print(broker.subscriber_count())         # 目前線上工作階段數

broker.shutdown()
```

**在單元測試裡用（`unittest` 範例）：**

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

#### 3️⃣ 編解碼器 `codec`（不碰網路，純位元組）

```python
from mqttforge.codec import encode_packet, decode_packets, decode_hex, encode_hex
from mqttforge.packets import Connect, Publish, Subscribe, Will

# 編碼：物件 → bytes
raw = encode_packet(
    Connect(client_id="device-007", keepalive=60,
            username="fleet", password="hunter2",
            will=Will(topic="d/007/status", payload=b"offline", qos=1, retain=True))
)

# 解碼：bytes → 物件（支援一段流裡含多個封包）
packets, leftover = decode_packets(raw)
print(packets[0].client_id)     # device-007
print(leftover)                 # b'' —— 未解析完的殘包

# 抓包常見半包，用 allow_partial 容忍
packets, rest = decode_packets(raw + b"\x30\x05", allow_partial=True)

# hex 互轉
hex_text = encode_hex(raw)                  # '101600044D515454...'
raw_again = decode_hex("10 16 00 04 ...")   # 容忍空格與 0x 前綴
```

#### 4️⃣ 主題工具 `topics`

```python
from mqttforge.topics import topic_matches, validate_topic_name, validate_topic_filter

topic_matches("sport/#", "sport")                 # True（# 也比對父層級）
topic_matches("sport/tennis/+", "sport/tennis/1") # True
topic_matches("#", "$SYS/broker/uptime")          # False（$ 主題受保護）
topic_matches("$SYS/#", "$SYS/broker/uptime")     # True

validate_topic_name("sensors/temp")   # 合法，原樣回傳
validate_topic_filter("sensors/+")    # 合法（訂閱時可用）
# validate_topic_name("sensors/+")    # 拋 TopicError：發布時不能有萬用字元
```

#### 5️⃣ 封包美化 `inspect`

```python
from mqttforge.inspect import describe, hexdump, format_packets

print(describe(packets[0]))      # 單一封包的結構化報表
print(hexdump(raw))              # 經典 offset/hex/ASCII 三欄檢視
print(format_packets(packets))   # 批次渲染
```

---

### 🎬 典型使用情境

| 情境 | 建議做法 |
| --- | --- |
| 🧪 **CI 裡測 MQTT 相關業務程式碼** | `MiniBroker` 起在 `setUp`，測試全離線、無 flaky |
| 🐛 **線上設備封包對不上，現場排查** | `mqttforge decode --file capture.bin --dump` |
| 🏗️ **本機開發還沒裝 Mosquitto** | `mqttforge broker --port 1883` 直接頂上 |
| 📊 **評估 Broker 效能** | `mqttforge bench --host <broker> -q 1 -n 5000` |
| 🤖 **給 LLM / 指令碼產生 MQTT 封包** | `codec.encode_packet()` 產生精確位元組，不靠手拼 hex |
| 🎓 **教學演示 MQTT 握手** | `mqttforge selftest` 逐步列印 14 種封包互動 |
| 🔌 **把 MQTT 能力嵌進自己的工具** | `from mqttforge import MQTTClient` —— 0 依賴，不污染依賴樹 |

### 📁 範例指令碼

儲存庫 `examples/` 目錄下有三個可以直接跑的完整範例：

```bash
python examples/quickstart.py          # 端到端：QoS 0/1/2 + 保留訊息 + ping
python examples/packet_forensics.py    # 純離線：編碼 → hexdump → 解碼回讀
python examples/iot_simulator.py       # 模擬設備叢集回報 + 收集端彙整
```

---

## 💡 設計思路與迭代規劃

### 🏛️ 分層架構

```
┌─────────────────────────────────────────────────────────┐
│  命令列層     cli.py      8 個子命令，argparse 驅動       │
├─────────────────────────────────────────────────────────┤
│  應用層   client.py  broker.py   用戶端 / 內嵌 Broker     │
├─────────────────────────────────────────────────────────┤
│  協定層        codec.py           14 種封包編解碼         │
├─────────────────────────────────────────────────────────┤
│  模型層   packets.py  topics.py   資料模型 / 主題語義     │
├─────────────────────────────────────────────────────────┤
│  基礎層   errors.py  version.py   例外體系 / 版本常數     │
└─────────────────────────────────────────────────────────┘
```

**關鍵設計決策：**

| 決策 | 原因 |
| --- | --- |
| 🎯 編解碼器與傳輸層徹底解耦 | 單元測試與網路測試可以分開跑；做協定模糊測試不需要起 socket |
| 🧵 用戶端對外同步、對內多執行緒 | 阻斷式 API 易讀；QoS 握手又必須非同步應答，所以內部用接收執行緒 + 條件變數 |
| 🚦 QoS 2 在收到 PUBREL 後才轉發 | 若在收到 PUBLISH 就轉發，發送方重傳（DUP）時會造成**重複投遞** |
| 🆔 封包 ID 池化管理 | `1..65535` 循環配置，用完即還，避免並行情況下撞號 |
| 🛡️ 嚴格校驗、快速失敗 | 協定實作裡「寬容解析」往往是漏洞溫床；非法旗標一律拋例外 |
| 💲 內建 `$SYS` 保護 | 遵循 MQTT-4.7.2-1，避免 `subscribe("#")` 意外吃掉系統主題 |

### ⚠️ 已知邊界

- 📌 只支援 **MQTT 3.1.1**，暫不支援 MQTT 5.0 的屬性（Property）機制
- 🔒 暫不支援 **TLS/SSL**（`mqtts://`）—— 如需加密，建議在通道層解決
- 🗃️ 內嵌 Broker **不持久化**工作階段與訊息，重啟即清空；`clean_session=False` 的狀態不保留
- 🔑 內嵌 Broker **無鑑權**，請勿直接暴露到公網
- 🌐 只支援 TCP 傳輸，不支援 WebSocket
- 🧵 內嵌 Broker 採一連線一執行緒模型，適合開發／測試規模（數十到數百連線）

### 🗺️ 迭代路線圖

- **v1.1** —— 🧵 asyncio 非同步用戶端；Broker 工作階段持久化開關
- **v1.2** —— 🔐 TLS 支援（`ssl` 包裝 socket）；WebSocket 傳輸
- **v1.3** —— 🔑 Broker 鑑權掛鉤（帳號密碼驗證、ACL）
- **v2.0** —— 🚀 MQTT 5.0 支援（屬性、原因碼、共用訂閱）

### 🙌 社群貢獻方向

- 🧪 更多畸形封包的模糊測試案例
- 🌍 命令列輸出的多語系本地化
- 📊 Broker 的 Prometheus 指標匯出
- 🔌 與 Home Assistant / ThingsBoard 的整合範例

---

## 📦 封裝與部署指南

MQTTForge 屬於**工具程式庫 + 命令列**類型，因此以 **PyPI 套件**為主要發行形式，無需為各平台單獨封裝二進位產物。

### 📥 作為依賴安裝

```bash
pip install mqttforge                 # 從 PyPI 安裝
pip install mqttforge==1.0.0          # 鎖定版本
pip install -e .                      # 從原始碼可編輯安裝（開發用）
```

安裝後即可取得 `mqttforge` 命令列進入點：

```bash
mqttforge --version      # → mqttforge 1.0.0
```

### 🏗️ 從原始碼建置發行包

```bash
# Linux / macOS / WSL / Git Bash
./build.sh                 # 跑測試 → 建置 sdist + wheel → 冒煙驗證
./build.sh --no-tests      # 跳過測試，直接建置

# Windows
build.bat
build.bat --no-tests

# 或者用 make
make test                  # 只跑測試
make build                 # 建置
make clean                 # 清理產物
```

產物輸出在 `dist/`：

```
dist/mqttforge-1.0.0.tar.gz                  # 原始碼發行包
dist/mqttforge-1.0.0-py3-none-any.whl        # 通用 wheel（純 Python，全平台通用）
```

> 💡 因為 MQTTForge 是**純 Python 且零依賴**，建置出的 wheel 是 `py3-none-any` —— 一個包通吃所有平台與 Python 版本，不需要按平台分別封裝。

### 📦 封裝成單檔可執行檔（選用）

如果你希望發行一個不需要 Python 環境的獨立程式：

```bash
pip install pyinstaller
pyinstaller --onefile --name mqttforge --console mqttforge/__main__.py
# 產物：dist/mqttforge（Linux/macOS）或 dist/mqttforge.exe（Windows）
```

> ⚠️ PyInstaller 體積約 8~12 MB（含 Python 直譯器）。僅在確實需要「免環境發行」時使用，常規情境直接用 `pip install` 更輕量。

### 🐳 容器化部署（選用）

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

### 🧩 整合進你自己的專案

MQTTForge 零依賴，直接把 `mqttforge/` 目錄放進專案也能用：

```python
# 方式 A：作為正常依賴
from mqttforge import MQTTClient

# 方式 B：只借用編解碼能力（完全不連網）
from mqttforge.codec import encode_packet
from mqttforge.packets import Publish
frame = encode_packet(Publish(topic="a/b", payload=b"hi", qos=1, packet_id=1))
```

### ✅ 相容性矩陣

| 平台 | 狀態 | 備註 |
| --- | :---: | --- |
| Linux (x86_64 / ARM) | ✅ | 主要開發環境 |
| macOS (Intel / Apple Silicon) | ✅ | 純 Python，無編譯步驟 |
| Windows 10/11 | ✅ | 提供 `build.bat` |
| Python 3.8 / 3.9 / 3.10 / 3.11 / 3.12 | ✅ | 僅用標準程式庫 |
| PyPy | ✅ | 無 C 擴充依賴 |

---

## 🤝 貢獻指南

歡迎任何形式的貢獻：🐛 回報 bug、💡 提想法、📝 改文件、🔧 提程式碼。

### 🔀 提交規範（Angular 約定）

本專案嚴格遵循 [Angular 提交規範](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit)，這是 CI 產生 changelog 的依據：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**type 取值：**

| type | 含義 | 範例 |
| --- | --- | --- |
| `feat` | 新增功能 | `feat(broker): 支援共用訂閱` |
| `fix` | 修復問題 | `fix(codec): 修正 4 位元組長度欄位解析` |
| `docs` | 文件更新 | `docs(readme): 補充 Windows 建置說明` |
| `refactor` | 程式碼重構 | `refactor(client): 抽出封包 ID 配置邏輯` |
| `test` | 測試相關 | `test(topics): 補充 $SYS 比對案例` |
| `perf` | 效能最佳化 | `perf(codec): 減少 publish 編碼時的記憶體複製` |
| `chore` | 建置／雜項 | `chore(deps): 更新 dev 依賴` |
| `ci` | CI 設定 | `ci: 增加 Python 3.12 矩陣` |

### 🔧 提交 PR 的步驟

1. **Fork** 本儲存庫並新建分支：`git checkout -b feat/your-feature`
2. **寫程式碼** —— 維持既有風格：型別標註、docstring、註解清晰
3. **加測試** —— 新功能必須有對應案例，放在 `tests/`
4. **跑全量校驗**：
   ```bash
   python -m unittest discover -s tests -v   # 單元測試
   python -m mqttforge selftest              # 端到端自檢
   ./build.sh                                # 建置 + 冒煙
   ```
5. **提交**：`git commit -m "feat(scope): 一句話說明"`
6. **推送** 並開 PR，描述裡請說明：動機、改動點、是否影響既有 API、如何驗證

### 🐛 回報 Issue 的規則

回報 bug 時請儘量提供：

- 🌍 環境：Python 版本、作業系統、MQTTForge 版本
- 🔁 最小重現步驟（可複製的程式碼或指令）
- 😯 預期行為 vs 😱 實際行為
- 📋 完整錯誤堆疊（如有）

### 💬 行為準則

- 對事不對人，技術討論保持理性
- 新功能先開 Issue 討論，避免重複勞動
- 破壞性變更必須在 PR 裡明確標註 `BREAKING CHANGE`

---

## 📄 開源授權說明

本專案以 **MIT License** 開源，詳見 [LICENSE](./LICENSE) 檔案。

**簡單來說，你可以：**

- ✅ 免費用於**商業專案**
- ✅ 修改原始碼、二次發行
- ✅ 作為閉源產品的一部分使用
- ✅ 申請專利使用

**你只需要做一件事：**

- 📌 在軟體與文件中**保留原始的版權宣告與 MIT 授權宣告**

**免責聲明：** 軟體依「原樣」提供，作者不對使用過程中產生的任何直接或間接損失承擔責任。

> 🔖 授權相容提示：MIT 與 GPL v2/v3、Apache 2.0 等主流授權皆相容，可安全引入你的專案依賴樹。

---

<div align="center">

**🔧 MQTTForge** —— 讓 MQTT 除錯回到「裝完就能跑」的狀態

如果這個專案幫到了你，歡迎 ⭐ Star 支持一下！

[⬆ 回到頂端](#-mqttforge)

</div>
