# office-token-booster v1.0.0 发布说明

> **「参赛版」里程碑发布** —— 办公室 AI 提效助手，执行与度量一体，可安全上架天禧 AI 技能广场。
>
> 发布日期：2026-09-05 ｜ 版本号：`1.0.0` ｜ License：MIT ｜ 作者：Elisabeth15501

---

## 一句话定位

`office-token-booster` 既帮你**做**办公交付物（周报 / 会议纪要 / 数据分析 / 文档整理 / PPT 大纲），又自动记下每次**省了多少 Token 和时间** —— 执行与度量一体，让「AI 提效」看得见、算得清、可验证。

本版本为对齐「参赛版」里程碑的正式发布，汇总了自 v0.9.10 以来的质量护栏、天禧 AI 上架打包与一轮安全合规修复，已通过天禧 AI 安全检测并可在技能广场稳定运行。

---

## 自 v0.9.x 以来的关键变更

### 🛡️ 「不降质量」护栏度量（v0.9.11 引入，本版固化）
- 新增 `scripts/quality.py`：**离线、确定性、零成本**的结构完整性评分（不调用 LLM，不联网，不重新烧 Token）。
- 对 4 类交付物（周报 / 会议纪要 / 数据分析 / 文档整理）逐项检查**关键章节是否齐全**；任一必要章节缺失即判「节省不可信」（`credible=False`），即便总分过门槛。
- 质量分从执行 → 账本 → 提效报告全链路贯通，最终在报告中以**三态横幅**（达标 / 节省不可信 / 未测）呈现，直接服务于北极星「不降低交付质量」一极。

### 📦 天禧 AI 上架打包收敛（v0.9.12）
- `network.outbound` 声明收敛为 `false`（原联网推荐指向非天禧市场，属安全审核红旗）；上架包**移除** `clawhub_client.py` / `skillhub_client.py`，仅保留本地推荐逻辑。
- 打包卫生：zip 仅含运行必需文件，剔除 `__pycache__`、`.pytest_cache`、`allure-results`、`tests/`、`.github/` 等开发与测试产物。
- 版本号三处（SKILL.md / config.yaml / CHANGELOG）对齐为一致版本。

### 🔒 安全合规修复（本版 HEAD 提交）
针对天禧 AI 安全检测报告的 4 类问题逐项修复：
1. **远程管道安装命令（低危）**：`skill_recommender.py` 中 `curl | bash/sh`、`npx skills add`、`clawhub install` 等远程安装命令全部改为静态「请按官方说明手动安装」指引，消除供应链投毒风险。
2. **无限循环告警**：`conversation.py` 的 `while True:` 改为带显式 `running` 标志的循环，退出条件清晰可识别。
3. **过度异常捕获（掩盖错误）**：`executor.py` 四处 `except Exception/except:` 改为具体异常类型（`ImportError` / `ModuleNotFoundError` / `KeyError` / `ValueError` / `json.JSONDecodeError` 等）并引入 `logging` 记录，不再静默吞错。
4. **引用不存在的文件**：`SKILL.md` 中 `ledger.json` 示例路径统一改为 `examples/ledger.json`，并新增示例账本文件，消除告警。

---

## 安全与合规

- ✅ `security_preflight scripts` → **EXIT=0**：无 R1 危险执行 / R2 网络外发 / R3 硬编码密钥 红线。
- ✅ 上架包内 20+ 个 `.py` 扫描 `urllib / requests / http.client / socket / os.system / subprocess` 等联网/危险特征 **0 命中**。
- ✅ 无硬编码本地绝对路径（如 `C:/Users/...`）。
- ✅ 全程本地运行：报告本地生成，不联网、不上传用户内容、不读密钥。
- ✅ 联网能力（技能推荐市场查询）默认**关闭**，且相关客户端已从上传包剔除。

---

## 质量护栏设计说明（为什么不用 LLM 判分）

质量分是**结构完整性的代理指标**（该有的章节在不在、有没有静默丢数据），**不等同于**对内容好坏的人工评分。采用确定性清单而非 LLM 判分，是为了不重新消耗 Token、也不需要联网 —— 否则会与「降本降步骤」一极自相矛盾。建议对外表述为「**结构完整性护栏 + 用户最终确认**」双重保障。

---

## 测试

- 全量测试套件：**166 passed, 0 failed**（含 15 项质量护栏回归、17 项负向/边界、13 项跨 Agent 可移植性测试）。
- 三层一致不变量（内核重算值与报告/摘要/对话外壳误差 < 0.05pp）守卫通过。
- 所有测试为 Python 标准库 + pytest + allure（开发依赖，不进上架包）。

---

## 上架包内容

`office-token-booster.zip`（约 113 KB）包含：

| 类别 | 文件 |
|------|------|
| 元信息 | `SKILL.md`、`config.yaml`、`LICENSE`、`RELEASE_NOTES.md` |
| 文档 | `README.md`、`QUICKSTART.md`、`CHANGELOG.md`、`usage-examples.md` |
| 业务代码 | `scripts/` 11 个模块（执行引擎、账本、报告、质量护栏、诊断、对话、宿主成本、推荐等）+ `type_registry.json` |
| 示例 | `examples/ledger.json`（示例账本） |

> 上架包已剔除一切联网客户端与开发/测试噪音，可直接上传天禧 AI 技能广场。

---

## 快速开始

```bash
# 1) 初始化空账本（仅首次）
python scripts/executor.py --init-ledger ledger.json

# 2) 做一次办公任务，并顺手记一笔账
python scripts/executor.py --type 周报生成 --input 本周事件.txt --output 周报.md \
    --apply-ledger ledger.json --skill-tokens 1800 --skill-minutes 6 \
    --baseline-tokens 12000 --baseline-minutes 25 --confirm-ledger

# 3) 生成提效报告（可对比最近一周 vs 上一周）
python scripts/report_engine.py ledger.json --format markdown --output 提效报告.md
```

更完整的用法见 `QUICKSTART.md` 与 `usage-examples.md`（含 4 条天禧/SkillHub 上架示例及配套答案）。

---

## 升级提示

- 从 v0.9.x 升级无需数据迁移；账本 `ledger.json` 格式保持不变。
- 若此前手动改过 `network.outbound`，升级后请确认它为 `false` 以匹配上架合规要求。
- 版本号已统一为 `1.0.0`，与 git tag `v1.0.0` 对应。
