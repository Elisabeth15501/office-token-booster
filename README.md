# 办公室提效助手（office-token-booster）

> 把重复办公任务交给技能，把省下的 Token 和時間看得見。

`office-token-booster` 是一个面向**办公生产力**场景的 AI 技能（OpenClaw / 天禧 AI 格式），
帮你把会议纪要、Excel 数据分析、周报、文档提炼等重复任务自动化，并**量化每次任务节省的 Token 与耗时**。

本技能是 `agent-analytics-report`（WorkBuddy 用量分析报告）的**兄弟产品线**——
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
3. 技能调用 `scripts/saving_report.py` 产出 `reports/saving-report.md` 与 `.html`。

## 目录结构

```
office-token-booster/
├── SKILL.md              # OpenClaw 格式技能定义
├── config.yaml           # 替代原 config.json
├── scripts/
│   └── saving_report.py  # 提效账本报告引擎（本地、离线）
├── references/           # 扩展文档
├── README.md
└── LICENSE
```

## 合规

- 全部本地处理，无外联、无硬编码密钥。
- MIT 协议，自研代码，可自由学习 / 修改 / 再分发。
- 节省值为用户自行估计的基准对比参考，**非平台计费数据**。

## 演进路线

- v0.1.0（本版）：技能骨架 + 提效账本报告引擎 + 办公任务定位
- v0.2：对话式诊断（先出摘要 + 图表，再支持追问）
- v0.3：长链路 Agent（采集任务 → 分析 → 给出省钱/提效建议 → 可选写回模板）
- 目标：提交「天禧 AI Skills 苍穹共创计划」（截止 2026-12-31）
