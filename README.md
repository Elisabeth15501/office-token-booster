# 办公室提效助手（office-token-booster）

> 把重复办公任务交给技能，把省下的 Token 和時間看得見。

`office-token-booster` 是一个面向**办公生产力**场景的 AI 技能（OpenClaw格式），
帮你把会议纪要、Excel 数据分析、周报、文档提炼等重复任务自动化，并**量化每次任务节省的 Token 与耗时**。

本技能是 `agent-analytics-report`（WorkBuddy 用量分析报告）的**姐妹产品线**——
两者复用同一套「报告渲染 + 异常检测」思路，但定位完全不同：

| 产品线 | 平台 | 定位 |
|--------|------|------|
| `agent-analytics-report` | WorkBuddy | 分析 AI 助手自身用量与成本 |
| `office-token-booster` | 天禧 AI / OpenClaw | 办公任务自动化 + 提效可视化 |

## 特性

- 🗂️ **办公任务自动化**：会议纪要、数据分析、周报、文档提炼
- 📊 **提效可视化**：内置「提效账本」，把节省的 Token / 耗时算清楚、画出来
- 🔒 **本地优先**：报告本地生成，不联网、不上传你的内容
- 🧩 **OpenClaw 格式**：可直接提交天禧 AI 技能广场 / ClawHub

## 快速开始

1. 把任务记录写成 `ledger.json`（格式见 `SKILL.md`）。
2. 触发技能："生成提效报告"。
3. 技能先做**一页摘要 + 图表**，再支持基于诊断结果的**追问**（如"哪个类型节省最多""按周趋势""有什么建议"）。

## 目录结构

```
office-token-booster/
├── SKILL.md              # OpenClaw 格式技能定义 + 对话式诊断流程
├── config.yaml           # 替代原 config.json
├── scripts/
│   ├── diagnose.py       # 诊断内核（纯函数）：ledger -> Diagnosis，含 baseline 护栏 + 方法论说明
│   ├── report_engine.py  # 渲染层：消费 Diagnosis 产出完整报告 / 一页摘要（MD/HTML）+ JSON
│   ├── qa.py             # 对话式追问外壳：answer_followup(diagnosis, question)，锚定 Diagnosis 不编造
│   ├── ledger_agent.py   # 长链路 Agent（v0.3）：建议生成 + 写回账本（默认 dry-run，--apply 才写）
│   ├── conversation.py   # 对话编排层（v0.4）：意图路由，把 qa/报告/Agent 串成单一对话流，不改三层一行
│   └── type_registry.json# 类型字典（v0.5）：标准类型名 ↔ 别名/关键词，消除自然语言记账的类型歧义
├── tests/
│   └── test_v05.py       # v0.5 实地测试：自带临时账本跑完整流程，断言类型字典消歧 + 三层一致
├── references/           # 扩展文档
├── README.md
└── LICENSE
```

> 三层解耦：`diagnose.py`(内核) 是「对话式诊断」「长链路 Agent」「对话编排」三个外壳的共享内核，
> 后加能力时只需消费内核，既有三层代码不受影响（见 `产品发展计划时间线_双产品线.md`）。

## 合规

- 全部本地处理，无外联、无硬编码密钥。
- MIT 协议，自研代码，可自由学习 / 修改 / 再分发。
- 节省值为用户自行估计的基准对比参考，**非平台计费数据**。

## 演进路线

- v0.1.0：技能骨架 + 提效账本报告引擎 + 办公任务定位
- v0.2（已完成）：对话式诊断 —— 三层解耦（diagnose 内核 / report_engine 渲染 / qa 追问）；一页摘要首屏（`--summary`）+ 完整报告双模板；追问语料丰富（总览/比例/类型排名/自动化优先级/周趋势/明细/最差场景/耗时/方法论/可信度/完整报告路由）；报告内置 baseline 护栏与「方法论说明」，主动暴露"节省值是自报参照"前提
- v0.3（已完成）：长链路 Agent —— `ledger_agent.py` 消费同一内核，提供「建议生成（propose_entry，按类型历史均值预填 baseline）」「待自动化建议（--targets）」「写回账本（append_entry，默认 dry-run 预览、--apply 才原子写回并自动备份）」三件套，对话层与报告层零改动
- v0.4（已完成）：对话编排层 —— 新增 `conversation.py`，用意图路由（classify + handle）把 qa 追问 / 报告 / ledger_agent 写回串成单一对话流；支持自然语言记账（解析类型与成本、历史均值预填基线、确认才写回）、被动记账建议（"我刚生成了周报，花了1800 token"也能识别）、连续对话（记账前后随意追问/看摘要/看建议），纯粘合层、不改既有三层一行
- v0.5（已完成）：类型字典消歧 —— 新增 `scripts/type_registry.json`（标准名 ↔ 别名映射）与 `tests/test_v05.py`（实地测试脚本）；`conversation._detect_type` 改为「账本已知类型 → 字典别名 → 短语抓取+字典模糊 → 全新类型候选」四级匹配，消除"周报"误判短词/多义歧义，词典缺失自动降级；qa/report_engine/ledger_agent/diagnose 仍零改动
- 目标：提交「天禧 AI Skills 苍穹共创计划」（截止 2026-12-31）
