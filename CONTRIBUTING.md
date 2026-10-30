# 🤝 贡献指南 / Contributing / 貢獻指南

感谢你愿意让 MQTTForge 变得更好！本项目秉持「零依赖、离线优先、可测试」三条底线，
提交前请先对照这三条自查。

Thanks for making MQTTForge better. The project holds three bottom lines —
**zero dependency, offline-first, testable**. Please self-check against them before submitting.

---

## 🧭 提交规范（Angular Commit Convention）

提交信息必须遵循 Angular 规范，这是 CI 与更新日志自动生成的依据。

| 类型 | 含义 | 示例 |
| --- | --- | --- |
| `feat` | 新增功能 | `feat: 支持 MQTT 5.0 属性字段` |
| `fix` | 修复缺陷 | `fix: 修正 QoS 2 重复转发` |
| `docs` | 文档更新 | `docs: 补充繁體中文 README` |
| `refactor` | 代码重构（不改变外部行为） | `refactor: 抽出报文解析索引表` |
| `test` | 测试相关 | `test: 增加剩余长度边界用例` |
| `perf` | 性能优化 | `perf: 复用编码缓冲区` |
| `build` | 构建 / 依赖变更 | `build: 升级 setuptools 要求` |
| `ci` | 持续集成配置 | `ci: 增加 Python 3.12 矩阵` |
| `chore` | 其他杂项 | `chore: 更新 .gitignore` |

格式：

```
<type>(<scope>): <subject>
<空行>
<body>
<空行>
<footer>
```

- `subject` 使用祈使句、首字母小写、结尾不加句号，长度控制在 50 字符内
- `body` 说明「为什么改」而不是「改了什么」
- 破坏性变更在 `footer` 写 `BREAKING CHANGE: ...`

---

## 🛠 本地开发流程

```bash
git clone https://github.com/gitstq/MQTTForge.git
cd MQTTForge

# 安装开发期依赖（仅用于打包，运行时零依赖）
pip install -r requirements-dev.txt

# 运行全部测试
python -m unittest discover -s tests -v

# 运行离线自检
python -m mqttforge selftest

# 一键构建
./build.sh          # Linux / macOS
build.bat           # Windows
```

## ✅ 提交前检查清单

- [ ] 新增代码**没有**引入任何第三方运行时依赖（只允许标准库）
- [ ] 新增功能配套了单元测试，且 `python -m unittest discover -s tests` 全绿
- [ ] `python -m mqttforge selftest` 保持 11/11
- [ ] 公开 API 变更同步更新了 `README.md` / `README.zh-TW.md` / `README.en.md` 三份文档
- [ ] 提交信息符合 Angular 规范

## 🧪 测试约定

- 测试文件放在 `tests/` 下，命名 `test_*.py`
- 网络相关测试必须使用内嵌 `MiniBroker`，**不得**依赖外部 Broker 或公网
- 涉及时序的断言请留出余量，避免 CI 上偶发抖动

## 📄 许可

贡献即表示你同意你的代码以本项目相同的 [MIT 许可](./LICENSE) 发布。
