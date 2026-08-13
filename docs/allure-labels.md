# office-token-booster Allure Label 维度体系

> 本文档汇总本项目测试使用的全部 `@allure.label` 维度，便于新测试统一风格、也方便在 Allure 报告里按维度筛选/分组。

---

## 1. 层级维度（layer）— 架构分层

标识被测代码所在的架构层级，与代码目录结构对齐：

| 取值 | 含义 | 对应模块 |
|------|------|----------|
| `内核层` | 纯函数诊断内核，零副作用 | `diagnose.py` |
| `编排层` | 对话路由与意图识别 | `conversation.py` |
| `触发层` | Skill 触发与事件桥接 | `skill_bridge.py` |
| `宿主适配层` | 宿主平台钩子与事件归一化 | `host_hook.py` |
| `适配层` | 报告渲染与数据转换 | `report_engine.py` |
| `写回层` | 账本追加与长链路 Agent | `ledger_agent.py` |
| `渲染层` | Allure 结果 → HTML 渲染器 | `render_allure_html.py` |
| `测试基础设施` | 测试共享辅助、图表生成 | `tests/helpers.py` |

**用法示例：**
```python
@allure.label("layer", "内核层")
def test_diagnose_empty_tasks(): ...
```

---

## 2. 测试类型（test_type）— 正向 / 负向 / 边界

标识测试的「方向性」，便于统计覆盖深度：

| 取值 | 含义 | 典型场景 |
|------|------|----------|
| `positive` | 正向路径：正常输入得到预期输出 | 标准对话流程、正常触发 |
| `negative` | 负向路径：异常/恶意输入被优雅处理 | 畸形 JSON、缺失字段、越界值 |
| `boundary` | 边界值：空、零、极大值、临界值 | 空账本、0 token、超长文本 |
| `regression` | 回归测试：历史 Bug 修复后防复现 | H1/H2/M1~M5 等对抗式修复 |
| `integration` | 集成测试：多模块协作链路 | 三层一致性、端到端触发 |
| `smoke` | 冒烟测试：核心功能快速验证 | 类型消歧、成本路由、确认写回 |

**用法示例：**
```python
@allure.label("test_type", "boundary")
def test_parse_number_empty_string(): ...
```

> **约定**：`@pytest.mark.smoke|integration|regression` 与 `@allure.label("test_type", ...)` 同时存在时，两者语义应对齐。

---

## 3. 组件维度（component）— 被测模块

标识具体被测的源文件/模块，便于按模块查看覆盖率：

| 取值 | 说明 |
|------|------|
| `diagnose` | `scripts/diagnose.py`（含 `Diagnosis`、`compute_summary`、`detect_baseline_anomalies`） |
| `conversation` | `scripts/conversation.py`（含 `handle`、`classify`、`_detect_type`、`_parse_numbers`） |
| `skill_bridge` | `scripts/skill_bridge.py`（含 `on_conversation_event`、`is_completion_event`） |
| `host_hook` | `scripts/host_hook.py`（含 `build_completion_event`、`on_task_completed`） |
| `report_engine` | `scripts/report_engine.py`（含 `generate_html_report`、`generate_markdown_summary`） |
| `ledger_agent` | `scripts/ledger_agent.py`（含 `propose_entry`、`append_entry`、`run_long_chain`） |
| `renderer` | `tools/render_allure_html.py`（含 `load_results`、`render`、`main`） |

**用法示例：**
```python
@allure.label("component", "conversation")
def test_classify_empty_input(): ...
```

---

## 4. 风险域（risk_area）— 业务风险

从「业务/产品」视角标注测试覆盖的风险点，便于作品集展示时说明测试设计思路：

| 取值 | 含义 | 相关测试 |
|------|------|----------|
| `data_integrity` | 数据完整性：账本读写不丢数、备份可回滚 | `append_entry` 原子写、三层一致 |
| `cost_accuracy` | 成本准确性：Token/分钟数解析与计算正确 | `_parse_numbers`、cost_source 路由 |
| `type_disambiguation` | 类型消歧：自然语言正确映射标准类型 | `_detect_type`、字典兜底 |
| `debranding` | 去品牌化：不绑定具体平台 | `test_v07_debranding` |
| `real_closed_loop` | 真实闭环：宿主实测成本写回 | `test_v07_confirm_real_closed_loop` |
| `ui_rendering` | UI 渲染：报告/HTML 产出正确 | `generate_html_report`、renderer、`test_v08`（趋势/对比/ROI 卡片） |
| `credibility` | 数据可信度：主动暴露前提、不虚高 | `detect_baseline_anomalies` |

**用法示例：**
```python
@allure.label("risk_area", "cost_accuracy")
def test_cost_source_mixed(): ...
```

---

## 5. 优先级（priority）— 测试重要性

与 `@allure.severity` 互补，`severity` 面向「缺陷影响面」，`priority` 面向「测试执行优先级」：

| 取值 | 含义 | 对应场景 |
|------|------|----------|
| `P0` | 阻塞级：失败即阻塞发布 | 确认写回、三层数字一致 |
| `P1` | 高优先级：核心功能必保 | 触发路由、成本来源、类型消歧 |
| `P2` | 中优先级：体验/完整性 | 报告渲染、去品牌化、可信度护栏 |
| `P3` | 低优先级：锦上添花 | 图表可视化、环境探测、边界兜底 |

**用法示例：**
```python
@allure.label("priority", "P0")
def test_confirm_writeback(): ...
```

---

## 6. 版本套件（suite）— 版本归属

标识测试所属的功能版本，便于按迭代查看覆盖：

| 取值 | 说明 |
|------|------|
| `v0.5` | 对话编排 + 类型字典消歧 |
| `v0.6` | Skill 触发流 + 被动完成信号 |
| `v0.7` | 真实闭环 + 去品牌化 |
| `renderer` | 报告渲染器 |
| `boundary` | 跨版本边界/负向测试 |

**用法示例：**
```python
@allure.label("suite", "v0.7")
def test_v07_cost_source_routing(): ...
```

---

## 7. 完整装饰器组合示例

```python
@allure.epic("office-token-booster")
@allure.feature("v0.7 真实闭环 + 去品牌化")
@allure.story("成本来源路由")
@allure.title("v0.7 成本来源：事件只给 token → mixed（M4）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("回归 M4：宿主事件只回报 skill_tokens 时，成本来源标为 'mixed' ...")
@allure.label("layer", "触发层")
@allure.label("test_type", "regression")
@allure.label("component", "skill_bridge")
@allure.label("risk_area", "cost_accuracy")
@allure.label("priority", "P1")
@allure.label("suite", "v0.7")
@src_link("scripts/skill_bridge.py", line=151, name="on_conversation_event() 源码")
@pytest.mark.regression
def test_v07_cost_source_mixed(ledger): ...
```

---

## 8. 已有测试 Label 速查表

| 测试文件 | 用例数 | 已覆盖 Label |
|----------|--------|-------------|
| `test_v05.py` | 3 | epic, layer, src_link, feature, story, severity, title, description |
| `test_v06.py` | 7 | epic, layer, src_link, feature, story, severity, title, description |
| `test_v07.py` | 7 | epic, layer, src_link, feature, story, severity, title, description |
| `test_renderer.py` | 2 | feature, title（renderer 不依赖 allure-pytest 时退化）；fixture 含自定义维度徽章断言 |
| `test_boundary.py` | 17 | 全维度覆盖（layer / test_type / component / risk_area / priority / suite / epic / src_link / feature / story / severity / title / description） |
| `test_v08.py` | 8 | epic, layer, src_link, feature, story, severity, title, description；全维度（test_type / component / risk_area / priority / suite），覆盖内核层（diagnose）与渲染层（report_engine） |

---

## 9. 渲染器展示效果

上述 label 在 `render_allure_html.py` 生成的自包含 HTML 报告中以 **badge（徽章）** 形式展示：

- `epic` → 紫色徽章
- `layer` → 绿色边框徽章
- `feature` → 默认蓝色徽章
- `story` → 青色徽章
- `severity` → 彩色背景徽章（按严重程度配色）
- `test_type` / `component` / `risk_area` / `priority` / `suite` → 标准徽章（白色底+彩色字）

在 Allure 原生报告（`allure serve`）中，可在 **Labels** 标签页按任意维度筛选/分组。
