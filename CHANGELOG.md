# 更新日志 · office-token-booster

一键可复用的办公提效技能（执行 + 度量一体）。版本号遵循语义化，稳定点打 tag。

---

## v0.9.6 — 执行引擎增强（2026-08-27）

方向 B（执行 + 度量）执行引擎打磨，**重点修复此前实测暴露的两处真实缺陷 + 两处打磨**。
全套测试 118 → **123 passed**（新增 5 例 E1–E4 回归），零回归。

### 新增 / 修复（E1–E4）
- **E1 · 打通自动记账闭环（功能级修复）**
  - `executor.propose_ledger` 新增 `baseline_tokens` / `baseline_minutes` 参数并透传给 `ledger_agent.run_long_chain`。
  - CLI 新增 `--baseline-tokens` / `--baseline-minutes`；配合 `--confirm-ledger` 即可在**空账本**上真正写回（此前因 P0 护栏永远拦截 baseline 缺省条目，执行引擎的自动记账对首条记录是条死路）。
  - 不传 baseline 时仍走 P0 护栏拦截（不污染账本），行为向后兼容。
- **E2 · 修复「已拦截：None」**
  - `executor.py` 第 647 行误读 `res.get('reason')`，实际键名为 `block_reason`；改为 `res.get('block_reason') or res.get('reason')`，拦截时显示真实原因。
  - 连带修复 `host_hook.py` 第 185 行同款键名 bug。
- **E3 · 周报引擎行内锚点增强**
  - `render_weekly_report` 按 `；`/`;` 拆分一行内的多个要点，分别归类；识别行内前缀 `风险：`/`下周：`/`阻塞：`/`概览：` 等路由。
  - 修复测试1 中「一行混合要点被整行抢走、丢失『风险与阻塞』段」的问题。
- **E4 · 缺失账本文件友好提示**
  - `--apply-ledger` 指向不存在文件时，捕获 `FileNotFoundError` 输出友好提示（含创建空账本的示例命令），不再抛出原始栈；交付物照常生成，仅跳过记账。

### 测试
- 新增 `tests/test_v10_executor.py`：E1（透传 baseline 写回 / CLI 端到端写回）、E2（拦截显示真实原因）、E3（行内锚点不丢风险段）、E4（缺失账本友好提示）共 5 例。

---

## v0.9.5 — 执行引擎落地（方向 B，稳定点）

- 任务执行引擎 `executor.py`：周报 / 会议纪要 / 数据分析（CSV 本地计算）/ 文档整理 / PPT 大纲 五大模块，纯标准库、零依赖、不联网、不读密钥。
- 执行 + 度量闭环：执行完任务可选自动记回 ledger（复用 `run_long_chain` P0 护栏，默认 dry-run）。
- 可选富格式导出 docx / xlsx（缺失优雅降级为 md / csv）。
- 宿主钩子 `host_hook.on_executor_completed` 复用 v0.7 事件 cost 形态直接记回。
- 测试套件达 118 例（含 17 边界 + 13 跨 Agent 可移植）。

> 更早版本（v0.5–v0.9.4）演进见 README「演进路线」。
