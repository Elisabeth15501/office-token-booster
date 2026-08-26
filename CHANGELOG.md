# 更新日志 · office-token-booster

一键可复用的办公提效技能（执行 + 度量一体）。版本号遵循语义化，稳定点打 tag。

---

## v0.9.6 — 执行引擎增强 + 缺陷修补（2026-08-27）

方向 B（执行 + 度量）执行引擎打磨，**修复实测暴露的功能级缺陷（D1/D2）+ 三处增强（E1–E4）**。
全套测试 123 → **126 passed**（新增 3 例 D1 回归），零回归。测试 2 / 测试 3 已用修正后正道命令复验通过。

### 安全修复（CodeQL CWE-20）
- **S1 · 修复 `skillhub_client.py` URL 子串消毒不完整**
  - 原代码 `if homepage and "github.com" in homepage:` 仅做子串包含判断，可能导致任意位置含 `github.com` 的恶意 URL 被误判为合法 GitHub 仓库。
  - 改为 `urllib.parse.urlparse(homepage).hostname`，并对 hostname 小写归一化后仅接受 `github.com` 或 `*.github.com`；解析异常兜底为 `None`。
  - 修复 GitHub CodeQL 告警 *Incomplete URL substring sanitization #1*。

### 缺陷修补（D1–D2，实测 Test 2/3 根因）
- **D1 · 新增「一等创建空账本」命令 `--init-ledger`（Test 2/3 根因修复）**
  - 此前用户只能用 `echo {"tasks":[]} > 账本.json`（PowerShell 下报语法错）或 `python -c "open(...).write('{\"tasks\":[]}')"`（PowerShell 下 `\"` 未转义致 SyntaxError）来建账本，两个写法在用户真实环境均失败。
  - 新增 `executor.py --init-ledger <path>`：写入 `{"tasks":[]}`（UTF-8、ensure_ascii=False），父目录自动创建；账本已存在时幂等跳过不覆盖。执行引擎首次记账不再依赖脆弱 shell 命令。
- **D2 · E4 友好提示改为推荐 `--init-ledger`**
  - 原 E4 提示里教用户 `echo {"tasks":[]}` ——正是 Test 2 在 PowerShell 失败的命令。改为推荐安全的 `.venv\Scripts\python scripts\executor.py --init-ledger <path>`。

### 增强（E1–E4）
- **E1 · 打通自动记账闭环（功能级修复）**
  - `executor.propose_ledger` 新增 `baseline_tokens` / `baseline_minutes` 参数并透传给 `ledger_agent.run_long_chain`。
  - CLI 新增 `--baseline-tokens` / `--baseline-minutes`；配合 `--confirm-ledger` 即可在**空账本**上真正写回（此前因 P0 护栏永远拦截 baseline 缺省条目，执行引擎的自动记账对首条记录是条死路）。
  - 不传 baseline 时仍走 P0 护栏拦截（不污染账本），行为向后兼容。
- **E2 · 修复「已拦截：None」**
  - `executor.py` 误读 `res.get('reason')`，实际键名为 `block_reason`；改为 `res.get('block_reason') or res.get('reason')`，拦截时显示真实原因。
  - 连带修复 `host_hook.py` 同款键名 bug。
- **E3 · 周报引擎行内锚点增强**
  - `render_weekly_report` 按 `；`/`;` 拆分一行内的多个要点，分别归类；识别行内前缀 `风险：`/`下周：`/`阻塞：`/`概览：` 等路由。
  - 修复测试1 中「一行混合要点被整行抢走、丢失『风险与阻塞』段」的问题。
- **E4 · 缺失账本文件友好提示**
  - `--apply-ledger` 指向不存在文件时，捕获 `FileNotFoundError` 输出友好提示（推荐 `--init-ledger`），不再抛出原始栈；交付物照常生成，仅跳过记账。

### 测试
- 新增 3 例 D1 回归：`--init-ledger` 建空账本 / 对已存在账本幂等跳过 / init→带 baseline 写回→report_engine 生成 HTML 全闭环。
- 既有 E1–E4 共 5 例回归不变。

---

## v0.9.5 — 执行引擎落地（方向 B，稳定点）

- 任务执行引擎 `executor.py`：周报 / 会议纪要 / 数据分析（CSV 本地计算）/ 文档整理 / PPT 大纲 五大模块，纯标准库、零依赖、不联网、不读密钥。
- 执行 + 度量闭环：执行完任务可选自动记回 ledger（复用 `run_long_chain` P0 护栏，默认 dry-run）。
- 可选富格式导出 docx / xlsx（缺失优雅降级为 md / csv）。
- 宿主钩子 `host_hook.on_executor_completed` 复用 v0.7 事件 cost 形态直接记回。
- 测试套件达 118 例（含 17 边界 + 13 跨 Agent 可移植）。

> 更早版本（v0.5–v0.9.4）演进见 README「演进路线」。
