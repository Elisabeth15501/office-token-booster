# office-token-booster v1.0.3 发布说明

> **代码质量整改版** —— 办公室 AI 提效助手，执行与度量一体，可安全上架天禧 AI 技能广场。
>
> 发布日期：2026-09-28 ｜ 版本号：`1.0.3` ｜ License：MIT ｜ 作者：Elisabeth15501

---

## 一句话定位

`office-token-booster` 既帮你**做**办公交付物（周报 / 会议纪要 / 数据分析 / 文档整理 / PPT 大纲），又自动记下每次**省了多少 Token 和时间** —— 执行与度量一体，让「AI 提效」看得见、算得清、可验证。

本版本为 **v1.0.3 代码质量整改**：基于 clean-code 审计，清除 1 项红项（不可达死规则 + 一处潜在崩溃）与 4 项黄项（长函数 / 魔法数 / 重复代码 / 工单式注释）。**纯重构，对外行为等价** —— CLI 参数、报告结构、问句应答、输出格式全部不变。

> 版本号说明：天禧 AI 平台要求上传版本号严格大于已登记版本，同版本不允许覆盖，故本轮整改以 v1.0.3 发布。

---

## v1.0.3 变更摘要

### 🔴 修复：潜在崩溃 + 不可达死规则

| 项 | 问题 | 处置 |
|----|------|------|
| `report_engine` | 两处内联推荐渲染仍在读取已删除的 `rec.install_cmd`，命中即抛 `AttributeError` | 统一改走 `format_recommendations_md()`，并保留「九、」编号标题与 🔴/🟠/🟢 优先级标识（与 HTML 口径一致） |
| `skill_recommender` | `_GLOBAL_RULES` 中按金额触发的规则声明了 `threshold_cost` / `condition`，但代码只判断 `threshold_tasks` —— 该 CRITICAL 规则永不触发，`condition` 从未被求值 | **删除而非实现**（账本无成本字段，按金额触发需先引入定价换算，属新功能）；一并删除 `install_cmd` / `requires_confirmation` 死字段 |

### 🟡 重构：无行为变化

- **长函数拆分**：`qa.answer_followup` 改表驱动（17 组关键词常量 + 路由表，162 → 19 行）；`diagnose.compute_summary` 抽聚合 helper（95 → 45 行）；`executor.main` 拆子命令（105 → 44 行）；`recommend_skills` 拆两个 matcher（64 → 26 行）。
- **消除重复**：`diagnose` 两段近似聚合循环合并为 `_group_sum` + `_with_saved`；`executor` 4 处引擎页脚抽取为 `_engine_footer()`。
- **魔法数常量化**：`qa` 内联关键词 → `_KW_*` 命名常量；`diagnose` 阈值 → 命名常量，提示文案改为插值常量（防改常量后文案漂移）。
- **注释清理**：12 个模块共 **35+ 处** `S7/E3/S3/D1/E4/Issue #n/ADR-7/ADR-9/Phase N/v0.x` 工单式与版本号注释，改写为「为什么这样做」。
- **杂项**：删除失效脚本 `test_clawhub.py` 与 `test_phase2.py`（调用已移除的联网参数，早已无法运行）。

### ✅ 验证

- 全量 **186 passed, 3 skipped**（与整改前基线一致）。
- `qa` 模块 **54 组问句新旧输出逐句等价性比对，0 diff** —— 动了 15 个顺序敏感分支，单测不足以覆盖，故从 git HEAD 取出旧模块对拍。
- `security_preflight scripts` EXIT=0；`executor` CLI 五条路径冒烟全通。

---

## 安全与合规

- ✅ `network.outbound = false`：全程本地运行，不联网、不上传用户内容、不读密钥。
- ✅ 上架包内 `.py` 扫描 `urllib / requests / http.client / socket.create / os.system / subprocess / os.popen / eval` 等联网 / 危险特征 **0 命中**。
- ✅ 无硬编码本地绝对路径（如 `C:/Users/...`）。
- ✅ 联网能力（技能推荐市场查询）已彻底移除，相关客户端不在上架包内。
- ✅ 无硬编码密钥；报告本地生成。

---

## 上架包内容

`office-token-booster.zip`（约 128 KB）包含：

| 类别 | 文件 |
|------|------|
| 元信息 | `SKILL.md`、`config.yaml`、`LICENSE`、`RELEASE_NOTES.md` |
| 文档 | `README.md`、`QUICKSTART.md`、`CHANGELOG.md`、`usage-examples.md` |
| 业务代码 | `scripts/` 12 个模块（执行引擎、账本、报告、质量护栏、诊断、对话、宿主成本、推荐等）+ `type_registry.json` |
| 示例 | `examples/ledger.json`（示例账本） |

> 上架包已剔除一切联网客户端（`clawhub_client.py` / `skillhub_client.py`）与开发 / 测试噪音（`security_preflight.py` / `test_recommendation.py` / `tests/` / `.github/`），可直接上传天禧 AI 技能广场。

---

## 升级提示

- 从 v1.0.x 升级无需数据迁移；账本 `ledger.json` 格式保持不变。
- 版本号已统一为 `1.0.3`，与 git tag `v1.0.3` 对应。
- 若此前手动改过 `network.outbound`，升级后请确认它为 `false` 以匹配上架合规要求。
