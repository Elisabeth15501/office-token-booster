---
name: office-token-booster
description: 办公室 Token 洞察与提效助手 —— 看清你用 AI 办公到底省了多少 Token 和时间。它不替你做会议纪要/Excel/周报，而是帮你记账、对比「笨办法 vs 本技能」的 Token 与耗时，并给出最该自动化的 ROI 建议。适用于办公生产力复盘、AI 用量洞察、提效度量与自动化决策场景。
version: 0.9.3
author: Elisabeth15501
license: MIT
tags:
  - 办公生产力
  - 效率工具
  - 数据分析
  - token提效
  - 用量洞察
categories:
  - 办公生产力
  - 数据分析
  - 效率工具
triggers:
  - intent: usage_overview
    description: 查看本机 AI 办公的真实 Token / 耗时用量（只读本地 traces，零上传）
    examples:
      - "我最近 7 天用了多少 Token？"
      - "帮我看看这周 AI 办公消耗了多少"
      - "我的本机宿主用了多少 Token？"
      - "统计一下我这个月的 AI 用量"
  - intent: efficiency_review
    description: 基于账本 baseline 度量「用 AI 办公省了多少 Token / 时间」
    examples:
      - "生成我的提效报告"
      - "用 AI 办公帮我省了多少？"
      - "我这个月提效怎么样？"
      - "做个周度提效汇总"
      - "做个办公提效复盘"
  - intent: task_diagnosis
    description: 追问哪个任务最费 / 最省 Token、最该自动化
    examples:
      - "哪个任务类型最费 Token？"
      - "哪个任务最省时间？"
      - "哪种办公任务最该自动化？"
      - "什么任务 AI 帮我最多？"
  - intent: report_visualization
    description: 生成 Token 用量 / 提效的可视化报告（HTML / 图表）
    examples:
      - "生成一份 Token 用量报告"
      - "把我的 AI 用量做成图表"
      - "给我出个提效 HTML 报告"
  - intent: import_bookkeeping
    description: 导入宿主真实用量或自然语言记账
    examples:
      - "把本机最近 7 天宿主用量导入账本"
      - "记一笔：写周报花了 1800 token"
      - "我刚写完周报，用 AI 花了 1800 token"
non_triggers:
  - "帮我写一份周报"
  - "整理一下会议纪要"
  - "分析这张 Excel 算个指标"
tools:
  - filesystem
  - shell
metadata:
  openclaw:
    requires:
      python: ">=3.10"
    env: []
    platform: ["tianxi", "openclaw", "linux", "macos", "windows"]
---

# 办公室 Token 洞察与提效助手（office-token-booster）

> 看清你用 AI 办公到底省了多少 Token 和时间——它**不替你做**会议纪要 / Excel / 周报，而是帮你记账、对比「笨办法 vs 本技能」、给最该自动化的 ROI 建议。

## 这个技能解决什么

办公室里大量时间花在**重复、低创意**的事情上：整理会议纪要、从杂乱 Excel 算关键指标、每周写周报、把长文档压成要点。这些事你可以用任意 AI 工具做完——但**做完之后，你往往说不清到底省了多少**。

`office-token-booster` 是一个**提效度量与洞察账本**：你（或用本技能的宿主用量接入）把每次任务的「笨办法估计成本 vs 实际 AI 成本」记一笔，它帮你**量化节省的 Token / 时间、按类型与周趋势可视化、并给出最该做成可复用模板的 ROI 建议**。它让"AI 到底帮我省了什么"从一句模糊的"提效了"，变成可复盘、可决策的数字。

> **定位边界（重要）**：本技能是「度量与洞察」工具，**不执行**任何办公任务（不整理纪要、不分析 Excel、不写周报）。它衡量你用别的 AI 做完任务后的节省，而不是替你做任务。

## 核心卖点：Token 提效洞察可视化

很多办公助手只说"我帮你做了"，但**不说帮了多少**。本技能内置一份「提效账本」：

- 你每次交给我们一个任务，记一笔：传统做法（自己手搓 / 反复试错）大概要花多少 Token、多少分钟；用本技能做花了多少。
- 累积后生成**提效报告**：总节省 Token、节省比例、按任务类型的节省分布、每周趋势。
- 报告纯本地生成，**不联网、不上传你的任何内容**。

> 注意：节省值是基于你填写的"基准估计"计算的参考值，不是平台用量扣费数据。它用于建立"提效体感"，不是计费凭证。

## 能做什么（真实范围 · MVP）

本技能**只度量、不执行**。下列能力均已落地（44+ 测试全绿）：

| 能力 | 输入 | 产出 |
|------|------|------|
| 提效账本 | 任务记录 JSON（`baseline` 笨办法估计 vs `skill` 实际 AI 成本） | MD / HTML 提效报告（节省 Token、耗时、率、趋势） |
| Token 洞察可视化 | 账本 | 环形图 + 趋势折线图 + 本期 vs 上期对比卡 + 自动化 ROI Top N 卡 |
| 对话式诊断 | 账本 + 自然语言追问 | 锚定内核的结构化回答（类型排名 / 最差场景 / 周趋势 / 周期对比 / 可信度） |
| 长链路自动记账 | 一句话 / 宿主完成事件 | 建议记账 → 你确认 → 原子写回（默认 dry-run，带备份） |
| 真实宿主用量接入（v0.9） | 本机宿主本地用量（可选开启） | 把宿主实测 Token/耗时导成账本草稿，skill 不再靠估算 |

## 怎么用

直接用自然语言触发，例如：

- "生成我的提效报告"（或指向账本 JSON 的路径）
- "哪个任务类型最省 Token？" / "这周比上周怎么样？"
- "哪些任务最该做成自动化模板？"
- "把本机最近 7 天的真实宿主用量导入账本"
- "我刚用 AI 写完了周报，花了 1800 token"（被动记账建议）

> 想要"帮我整理会议纪要 / 分析 Excel"等**执行类**能力？本技能目前不做——它负责**衡量**你用任意 AI 做完这些事后的节省。执行类已在路线图中作为后续扩展方向。

## 快速开始（QUICKSTART）

零依赖（纯标准库 Python ≥3.10），从项目目录即可跑通核心闭环。

**1) 准备一份账本（或用内置示例）**

把下面内容存为 `ledger.json`：

```json
{
  "tasks": [
    {"date": "2026-08-08", "type": "周报生成",
     "baseline_tokens": 12000, "skill_tokens": 3000,
     "baseline_minutes": 25, "skill_minutes": 3, "note": "手写周报"},
    {"date": "2026-08-11", "type": "会议纪要",
     "baseline_tokens": 9000, "skill_tokens": 2500,
     "baseline_minutes": 20, "skill_minutes": 4, "note": "2 小时会"}
  ]
}
```

> `baseline_*` = 你不用本技能、自己手搓 / 反复试错的估计成本；`skill_*` = 这次用 AI 实际花的。节省 = baseline − skill。

**2) 生成提效报告**

```bash
python scripts/report_engine.py ledger.json --format html --output 提效报告.html
# 一句话摘要：加 --summary；Markdown：--format markdown
```

**3) 对话式追问（内核 API）**

```python
from scripts.diagnose import load_ledger, diagnose
from scripts.qa import answer_followup
d = diagnose(load_ledger("ledger.json"))
print(answer_followup(d, "哪个任务类型最省 Token？"))
print(answer_followup(d, "这周比上周怎么样？"))
```

**4) 真实宿主用量接入（v0.9，可选）**

```bash
# 只读本机宿主最近 7 天用量；无数据则提示跳过，不影响其它功能
python scripts/host_cost.py --days 7
# 把真实用量导成账本草稿（dry-run 预览，不写盘；加 --apply 才写回）
python scripts/ledger_agent.py ledger.json --import-host --days 7
```

**全量测试：**

```bash
pytest tests/ -q --alluredir=allure-results
```

## 提效账本数据格式

把任务记录保存为 JSON（如 `ledger.json`），每一条：

```json
{
  "tasks": [
    {
      "date": "2026-08-08",
      "type": "会议纪要",
      "baseline_tokens": 12000,
      "skill_tokens": 3000,
      "baseline_minutes": 25,
      "skill_minutes": 3,
      "note": "2 小时录音转写"
    }
  ]
}
```

然后说"生成提效报告"，技能调用 `scripts/report_engine.py` 产出报告。

## 对话式提效诊断（推荐流程）

技能支持**先给一页摘要 + 图表、再追问、最后按需展开完整报告**的对话式诊断，让你按需深挖：

1. **一页摘要（首屏）**：技能先调用 `report_engine.py --summary` 输出一页精简摘要（核心数字 + 提效主力 + 一句话结论 + 数据可信度 + 方法论说明），配合环形图一屏看完，不淹没细节。
2. **追问（基于诊断结果、不编造）**：例如
   - "哪个任务类型节省最多？" → 按 `by_type` 排序回答
   - "哪个场景最不省？" / "按周趋势如何？" → 从结构化结果精确取数
   - "有哪些任务明细？" → 列出每条任务省了多少
   - "这些数字怎么算出来的 / 可信吗？" → 解释方法论与基线护栏（caveats）
   - 追问由 `scripts/qa.py` 处理，所有回答都**锚定在 `diagnose()` 产出的结构化 Diagnosis 上**，不做无数据支撑的猜测。
3. **展开完整报告**：当你说"生成完整报告"，技能调用 `report_engine.py` 输出完整明细（任务类型 / 周趋势 / 执行情况 / 产出物 / 洞察建议 / 数据可信度提示），供需要落地细节时使用。

> 一页摘要与完整报告共用同一份 `Diagnosis` 内核，追问题也不重新计算，保证首屏、追问、完整报告三处数字完全一致。

## 长链路自动记账（v0.3 长链路 Agent）

对话式诊断是「只读、响应式」外壳；v0.3 在此基础上叠加**主动管道**：任务完成后，让 Agent 自动把这笔账记回 `ledger.json`，减少你手填负担。它直接消费共享内核 `diagnose()`，对话层（`qa.py`）与报告层（`report_engine.py`）**一行都不用改**。

由 `scripts/ledger_agent.py` 提供，三个动作可组合：

1. **建议生成（propose_entry）**：`python ledger_agent.py <ledger.json> --type 周报生成 --skill-tokens 1800`
   - 用该类型的历史均值预填 `baseline`（你手搓成本）估计；你也可显式传 `--baseline-tokens` / `--baseline-minutes` / `--skill-minutes` / `--note` 覆盖。
   - 未提供或新类型时，会标记「估算字段」并提醒你补填真实手搓成本。
2. **待自动化建议（--targets）**：`python ledger_agent.py <ledger.json> --targets`
   - 按历史基线从高到低，列出最该做成可复用模板的任务类型。
3. **写回账本（append_entry）**：默认 **dry-run 仅预览**，加上 `--apply` 才真正写回（写前自动备份为 `<ledger>.bak`，原子替换）。
   - 预览会显示写回前后「任务数 / 节省 Token / 节省分钟」的变化，方便你确认。

完整流程编排见 `run_long_chain(ledger_path, task_type, ...)`：load_ledger → diagnose → propose → append → 重新 diagnose。

> 安全默认：不加 `--apply` 绝不改动你的账本文件。Agent 写回的仍是「用户账本」，不是平台 Trace——这与 ADR-9 上传/导出模式一致。

## 对话式自动记账编排（v0.4 粘合层）

v0.3 给了「主动记账」的原子能力；v0.4 把它们与对话式诊断、报告**串成一条连续对话**——用户说一句，技能理解意图并调用对应内核能力，任务完成时还能自动建议记账。

由 `scripts/conversation.py` 提供，纯新增、**不改 qa / report_engine / ledger_agent 一行**：

- **意图路由（classify + handle）**：把一句话归到 记账 / 确认 / 取消 / 生成摘要 / 生成完整报告 / 待自动化建议 / 追问 等意图，再分派给对应内核能力。
- **自然语言记账**：说「记一笔 周报生成 花了1800 token 5分钟」，自动解析类型与成本，用该类型历史均值预填 baseline 估计并预览；你回「确认」才写回（ledger_agent 内部仍是 dry-run + 备份）。
- **被动记账建议**：说「我刚生成了周报，花了1800 token」也能识别为记账意图（完成动词 + 成本数字），并模糊匹配到账本已有类型名，降低手填负担。
- **连续对话**：记账前后都能直接追问（qa 接地）、看摘要（report_engine）、看自动化建议（ledger_agent），所有数字来自同一份 `Diagnosis`，三处始终一致；确认写回后还会主动弹一条「最该自动化」的建议。

交互示例：`python conversation.py <ledger.json>` 进入 REPL；也可在 Python 里 `handle(ledger, text, state)` 单轮调用，便于 Skill / 对话 UI 集成（state 保存待确认条目）。

> 这就是 v0.1 三层解耦的复利：v0.4 没有碰任何既有三层，只是新增一个消费它们的编排层，却让「说一句就记一笔、记完接着问」成为单一体验。

## 类型字典消歧（v0.5）

v0.4 的 `_detect_type` 靠「子串模糊匹配」把自然语言里的类型落到账本标准名——隐患是：说「生成了周报」只抓到短词「周报」，若账本里同时有「周报生成」和「周报审核」就会歧义；全新类型也容易被误判。

v0.5 引入 **`scripts/type_registry.json` 类型字典**（标准名 ↔ 别名/关键词映射），让类型识别从「猜」变成「查表」：

- `_detect_type` 匹配优先级：① 账本已知标准类型精确出现 → ② 类型字典标准名/别名命中 → ③ 短语抓取（记账词或完成动词后跟类型名）+ 字典模糊匹配 → ④ 都无命中则作为**全新类型候选**返回（预览时提示你确认，并建议在字典补别名）。
- 词典缺失/损坏时自动降级为空字典（退化为 v0.4 行为），不影响其他功能。
- 新增类型时，只需在 `type_registry.json` 的 `types` 里加一个标准名 + 别名列表，即可让以后的自然语言记账准确识别——**仍不改 qa / report_engine / ledger_agent / diagnose 一行**。

实地验证脚本见 `tests/test_v05.py`：`python tests/test_v05.py` 自带临时账本跑完整流程，断言类型字典消歧正确、三层数字同源一致。

## Skill 触发流（v0.6 接宿主对话事件）

v0.5 以前，记账要等**用户主动说**「记一笔」或「我刚生成了周报」。v0.6 再往前一步：**让「用户完成一次任务」这件事本身自动建议记账**——不必再记着去敲那句命令。

由 `scripts/skill_bridge.py` 提供，纯新增、**不改 diagnose / qa / report_engine / ledger_agent / conversation 一行**：

- **完成信号识别（is_completion_event）**：一句话里含「生成了 / 做好了 / 写完了 / 交付了 …」等完成动词即视为「任务完成事件」。再细分信心：动词+成本数字 = high（直接给完整建议）；仅动词、无成本 = medium（仍触发，并提示补成本）；纯闲聊/问答 = low（不触发，交普通对话）。
- **事件桥接（on_conversation_event）**：把一条**宿主对话事件**（如用户说「我刚生成了周报，花了1800 token 5分钟」）翻译成 `conversation.handle()` 的调用，**内部暂存待记账条目到 state["pending"]**，返回结构化 `TriggerResult`（是否触发 / 建议文案 / 待记账类型 / 信心），供 Skill / UI 渲染成「要不要记一笔？」卡片。
- **类型字典兜底（_lenient_type）**：对于「写完了那份PPT」这类**没给成本、且别名大小写不符**的完成句，对话层 `_detect_type` 认不出类型时，桥接层用类型字典做大小写不敏感兜底匹配，仍能落到标准名「PPT制作」。
- **确认才写回（安全默认不变）**：触发流只「建议」，绝不在用户确认前落盘。用户回「确认」交给普通对话流 `handle("确认", state)` 写回——与 v0.4/v0.5 完全一致。

> 本模块**不绑定任何具体平台**（天禧 / OpenClaw 皆可），只认通用的「对话事件」契约，可直接复用到比赛仓库。

宿主技能侧集成示例：

```python
from skill_bridge import on_conversation_event
state = {}
# 宿主在完成一次办公任务后，把真实用量随事件一并传来（v0.7 起支持 event["cost"]）
res = on_conversation_event("ledger.json", {
    "role": "user", "text": "我刚生成了周报",
    "cost": {"skill_tokens": 1800, "skill_minutes": 5},
}, state)
if res.triggered:
    show_suggestion(res.suggestion)   # 渲染「建议记账：周报生成 … 确认？」
```

> 这就是 v0.1 三层解耦 + v0.4 编排层 + v0.5 类型字典的又一次复利：v0.6 **只新增一个消费 `conversation.handle()` 的「触发适配器」**，把「人敲 CLI」换成「对话事件驱动」，内核与三层外壳零改动。

实地验证脚本见 `tests/test_v06.py`：`python tests/test_v06.py` 自带临时账本，断言高/中信心完成事件触发、非完成事件不触发、触发默认 dry-run 不写账本、确认后写回且三层数字同源一致。

## 真实闭环 + 去品牌化（v0.7）

v0.6 的触发流已能自动建议记账，但成本仍需**用户自报**（"花了1800 token"）。v0.7 再往前一步：**让宿主平台把任务的真实用量直接随事件传进来**，把"提效"从"自报"变成"实测"——这才是比赛方案 Option B 真正想要的"对比笨办法 vs 本技能"的硬数据。

由 `scripts/skill_bridge.py`（升级）与 `scripts/host_hook.py`（新增）共同提供，**内核与三层外壳 + 编排层仍零改动**：

- **真实成本捕获（event["cost"]）**：宿主在完成一次办公任务后，可在事件里带上 `{"skill_tokens": N, "skill_minutes": M}`。桥接层优先采用这个**实测值**，而非从自然语言里解析数字；`TriggerResult.cost_source` 标记为 `"event"`（自报则为 `"text"`），供 Skill / UI 标注"本技能实测消耗"。
- **结构化完成标志（event["completed"]）**：宿主也能显式声明"任务已完成"（`completed=True`），优先级高于文本里的完成动词，便于平台把"产出物落地"这个动作直接映射成记账建议。
- **宿主钩子示例（host_hook.py）**：一个**平台无关**的适配器，演示宿主如何把完成事件归一化成通用 `event` dict（`build_completion_event`）并接进 `on_conversation_event`（`on_task_completed`）。它**不 import 任何平台 SDK、不发网络请求、不硬编码密钥**，满足 OpenClaw / 天禧 安全红线；平台-specific 的 glue 由平台侧实现。
- **去品牌化**：`skill_bridge` 不再绑定具体宿主平台，可同时服务 天禧 / OpenClaw；比赛仓库可直接复用内核，无需改造。

> 真实闭环落地证据：宿主回报 `skill_tokens=1800` 的事件经触发→确认后，写回账本的条目 `skill_tokens` 即为 1800（非用户手敲），且确认消息 / 内核 Diagnosis / 摘要报告三处节省率完全一致（v0.7 测试已断言）。

实地验证脚本见 `tests/test_v07.py`：`python tests/test_v07.py` 自带临时账本，断言真实用量事件触发且 `cost_source=event`、确认后写回采用宿主真实用量、三层数字同源、源码已去品牌化（无具体平台绑定措辞）；`python scripts/host_hook.py --demo` 可看宿主完成事件如何触发记账建议。

## 设计与合规

- **全部本地处理**：报告在本地生成，不向任何外部域名发送你的内容。
- **无硬编码密钥**：脚本不读取任何 API Key / Token。
- **数据最小化**：只处理你主动提供的文件，不扫描技能目录以外的系统文件。
- **开源协议**：MIT，可自由学习、修改、再分发。

## 范围说明（Non-goals）

- **不执行办公任务**：不整理会议纪要、不分析 Excel、不写周报——只度量你用别的 AI 做完后的节省（执行类为后续路线图方向）。
- **不读平台计费 / 不联网 / 无密钥**：默认节省值来自你填的基准估计。v0.9 起**可选**开启「真实宿主用量接入」，仅**只读本机宿主的本地用量目录**（具体路径随宿主而定，例如宿主的 traces 目录）来补全 skill 实测成本；不调用任何平台计费 API、不发网络请求、不读任何密钥，满足 OpenClaw / 天禧 安全红线。无本机数据时该功能自动跳过，不影响其它功能。
- 不自动执行会改动你系统的危险操作（如删除文件、发送邮件）；写回账本默认 dry-run，需你确认（`--apply`）才落地。
- 当前版本聚焦"办公文本类任务"的提效度量，复杂 PPT 排版 / 多模态生成在后续版本扩展。
