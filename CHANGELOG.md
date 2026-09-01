# 更新日志 · office-token-booster

一键可复用的办公提效技能（执行 + 度量一体）。版本号遵循语义化，稳定点打 tag。

---

## v0.9.8 — Bug #1 修复：baseline 分钟误归 skill（2026-09-02）

- **修复 `conversation._parse_baseline`**：紧凑写法 `确认 baseline 12000 token 25分钟` 中的「25分钟」此前被 `_parse_numbers` 误判为 skill 分钟写入账本（baseline_minutes=0, skill_minutes=25）。改为**段式解析**——锁定首个 baseline 触发词（基准/手搓/baseline/笨办法）之后的子串，在该子串内统一解析 token/分钟，使「触发词 … token … 分钟」任意间隔都正确归 baseline。
- **回归测试**：`tests/test_v097_execute.py::test_execute_baseline_minutes_not_misrouted` 锁定 `baseline_tokens=12000 / baseline_minutes=25 / skill_*=0`。
- **测试健壮性**：`test_security_preflight._write` 改用独立临时子目录写入，杜绝 TEMP 同名残留导致的 rename 冲突（FileExistsError）。
- 全套测试 138 passed，零回归。
- 版本号 `0.9.7 → 0.9.8`（config.yaml / SKILL.md）。

---

## v0.9.7 — Phase 3 落地：execute 意图路由 + 安全预检 + QUICKSTART（2026-08-26）

完成 **Phase 3** 三项内容（原计划 10–11 月，提前至 v0.9.7），并补上独立快速开始文档。

### 对话编排层 · execute 意图路由（方向 B 闭环关键一环）
- `conversation.classify` 新增 `execute` 意图：自然语言「帮我写周报 / 整理会议纪要 / 分析 CSV / 提炼要点 / 出 PPT 大纲」自动路由到 `executor` 渲染交付物，再走 `run_long_chain` baseline 护栏自动记账。
- 新增 `_EXEC_RE` / `_EXEC_SYNONYMS` 识别执行类中文触发词；`resolve_exec_type` 归一类型、`execute_render` 公共 API（供编排层安全调用，不碰私有 `_DISPATCH`）。
- **防账本污染护栏**：`confirm` 分支新增「成本完整性」校验——当 skill 与 baseline 的 token/分钟均为空或 0 时，**拦截写回**并提示补成本，避免空账本出现全零/负节省记录。
- 收窄 `record` 正则：移除裸词「记账」，避免执行内容里含「记账」二字被误路由到记账意图。
- `conversation._do_execute`：渲染后存入 `state["pending"]`，提示预览 + 要 baseline，确认才落盘。

### 执行层安全预检（四红线）+ CI 闸门
- 新增 `scripts/security_preflight.py`：扫描 `.py` 文件检测 R1 危险执行（`eval/exec/os.system/subprocess`）、R2 网络外发（`urllib.request/requests/http.client/socket` 等）、R3 硬编码密钥（`AKIA*/sk-/ghp_/xox*/JWT/password=/secret=`）、R4 `html.escape` 转义（仅告警）。
- 白名单：`security_preflight.py` / `test_security_preflight.py` 豁免 R1；`skillhub_client.py` / `clawhub_client.py` / `security_preflight.py` / `test_security_preflight.py` 豁免 R2（设计内允许联网的搜索客户端）。
- `.github/workflows/ci.yml` 新增 `security` job，在 `deploy-pages` 前跑 `python scripts/security_preflight.py scripts`，**须 0 红线才放行**。
- 当前 `scripts/` 实测通过预检（0 红线，仅 4 处 R4 转义告警）。

### 文档
- 新增独立 **[QUICKSTART.md](QUICKSTART.md)**：5 分钟跑通「初始化账本 → 执行任务 → 确认写回 → 看提效报告」闭环；含环境要求、常见任务示例表、PowerShell/Windows 注意事项、安全红线说明。
- `README.md`「快速开始」改为方向 B 视角并链接 QUICKSTART；`SKILL.md`「快速开始（QUICKSTART）」补 execute→bookkeep 步骤并链接独立文件。
- `docs/v1.0.0-prelaunch-plan.md`：Phase 3 三项全部勾选（含 PPT 大纲模块补勾，代码其实已在 Phase 2 随 executor 落地）；质量门禁「安全预检脚本」项勾选。

### 测试
- 新增 `tests/test_security_preflight.py`（6 例：R1/R2/R3 检测、R2 联网白名单豁免、干净文件通过、scripts/ 实测通过）。
- 新增 `tests/test_v097_execute.py`（6 例：意图分类、渲染交付物、缺成本拦截写回、带 baseline 写回、CSV 路由、PPT 不被「记账」误路由）。
- `tests/test_boundary.py` 超长文本分类断言补 `execute` 意图（边界测试覆盖新意图）。
- 全套测试 **138 passed**（126 → 138，新增 12 例），零回归。

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
