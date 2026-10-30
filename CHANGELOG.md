# 📜 更新日志 / Changelog / 更新日誌

本项目所有值得注意的变更都会记录在此文件中。
格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/).

---

## [1.0.0] - 2026-01-15

首个正式版本 / First stable release / 首個正式版本。

### ✨ Added / 新增 / 新增

**编解码器 (`mqttforge.codec`, `mqttforge.packets`)**
- MQTT 3.1.1 全部 14 种控制报文的编码与解码实现
- 剩余长度（Remaining Length）变长字节整数编解码，覆盖 1～4 字节全部边界值
- 所有报文首字节标志位合法性校验（MQTT-2.2.2-1）
- UTF-8 字符串 / 二进制数据字段编解码
- 流式解码 `decode_packets()`：一次喂入任意长度字节流，自动切分完整报文并保留残余半包

**主题工具 (`mqttforge.topics`)**
- 主题名与主题过滤器合法性校验（含 `#` 必须独占层级且位于末尾）
- 通配符匹配 `topic_matches()`，支持 `+` 与 `#`
- `$` 开头主题的系统保护规则（MQTT-4.7.2-1）

**客户端 (`mqttforge.client`)**
- 同步阻塞式 `MQTTClient`，支持 `with` 上下文管理
- QoS 0 / 1 / 2 三级服务质量完整握手
- 自动保活（PINGREQ / PINGRESP）、遗嘱消息、保留消息、Clean Session
- 订阅支持字符串 / 字典 / 二元组列表三种写法
- 可用报文 ID 池（1～65535）自动分配与回收

**内嵌 Broker (`mqttforge.broker`)**
- 进程内 `MiniBroker`，无需外部服务即可完成端到端联调
- 通配符订阅分发、保留消息、遗嘱消息
- 连接 / 消息 / 订阅维度的实时统计

**命令行工具 (`mqttforge.cli`)**
- `selftest` 离线自检（11 项）
- `broker` 启动本地 Broker
- `publish` / `subscribe` 发布与订阅
- `probe` 探测远端 Broker 连通性
- `decode` 十六进制报文取证实录
- `topics match` / `topics validate` 主题工具
- `bench` 吞吐压测

**检视工具 (`mqttforge.inspect`)**
- `describe()` 报文结构化描述、`hexdump()` 十六进制转储、`format_packets()` 批量格式化

**工程化**
- `pyproject.toml` 打包配置（wheel + sdist），零运行时依赖
- `py.typed` 类型提示标记
- `build.sh` / `build.bat` 跨平台一键构建脚本
- 92 个单元测试，覆盖编解码、主题、客户端与 Broker、CLI 子进程调用
- 三语文档：简体中文 / 繁體中文 / English

### 🐛 Fixed / 修复 / 修復

- 修复确认报文大小写不匹配导致的 PUBACK / PUBREC / SUBACK 等待超时
- 修复 QoS 2 消息在 PUBLISH 与 PUBREL 两处重复转发导致的消息双投
- 修复遗嘱消息因 QoS 1 报文缺少报文 ID 而被静默丢弃
- 修复非 PUBLISH 报文标志位非法时不抛 `ProtocolError` 的问题

---

## 版本命名规则 / Versioning

| 变更类型 | 版本位 |
| --- | --- |
| 不兼容的 API 变更 | 主版本号（major） |
| 向后兼容的功能新增 | 次版本号（minor） |
| 向后兼容的问题修复 | 修订号（patch） |
