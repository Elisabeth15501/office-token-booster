# office-token-booster v1.0.2 发布说明

> **修复补丁版** —— 办公室 AI 提效助手，执行与度量一体，可安全上架天禧 AI 技能广场。
>
> 发布日期：2026-09-24 ｜ 版本号：`1.0.2` ｜ License：MIT ｜ 作者：Elisabeth15501

---

## 一句话定位

`office-token-booster` 既帮你**做**办公交付物（周报 / 会议纪要 / 数据分析 / 文档整理 / PPT 大纲），又自动记下每次**省了多少 Token 和时间** —— 执行与度量一体，让「AI 提效」看得见、算得清、可验证。

本版本为 **v1.0.2 修复补丁**：基于 v1.0.0 参赛版与 v1.0.1 类型字典修复，进一步修掉千问办公实跑与 GitHub Issue 反馈的 3 个渲染/问答缺陷，并移除报告中一处冗余的安装确认 UI。**未改任何对外能力边界**，上架包安全合规口径与 v1.0.1 一致。

---

## v1.0.2 变更摘要

### 🐛 修复 3 个 GitHub Issue（实跑验证）

| Issue | 现象 | 修复 |
|-------|------|------|
| **#1** | 周报里「发现问题 / 解决问题」被错误塞进「风险与阻塞」节 | `executor.classify` 增加完成动词语义门槛（发现 / 定位 / 修复 / 完成 / 已 / 上线 / 提交 / 解决 / 搞定 / 处理）；中性陈述句不再被「问题 / issue」关键词抢走。显式锚点「风险：」仍优先。 |
| **#2** | 追问「最省 / 最费 Token」落到通用帮助，答非所问 | `qa.answer_followup` 消耗分支补齐「最费 / 费token / 费钱 / 耗费最多」并排除「省」，节省分支补齐「最省 / 省最多 / 省得最多 / 最划算」。 |
| **#3** | 周报出现双层子弹「- - 」 | `executor._lines` 用统一正则剥离行首列表标记（`- / * / + / • / · / 数字列表`），一处覆盖全部渲染器。 |

### 🧹 移除冗余 UI

- 提效报告「推荐 Skill」卡片里的**安装确认橙框**（安装命令 + `.workbuddy` 安全提示）已移除。推荐卡仍保留 Skill 名称、推荐原因、预期节省、SkillHub/ClawHub 信息与来源链接——用户要装可顺着来源自行安装。

### ✅ 测试

- 新增 `tests/test_issue_parity.py`（7 条，含抽取 `SKILL.md` 示例问法的结构性防漂移断言）。
- 受影响旧测试全过；全量套件维持 **165 passed, 3 skipped**（开发依赖，不进上架包）。

---

## 安全与合规

- ✅ `network.outbound = false`：全程本地运行，不联网、不上传用户内容、不读密钥。
- ✅ 上架包内 `.py` 扫描 `urllib / requests / http.client / socket.create / os.system / subprocess / os.popen / eval` 等联网 / 危险特征 **0 命中**。
- ✅ 无硬编码本地绝对路径（如 `C:/Users/...`）。
- ✅ 联网能力（技能推荐市场查询）默认关闭，相关客户端已从上架包剔除。
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
- 版本号已统一为 `1.0.2`，与 git tag `v1.0.2` 对应。
- 若此前手动改过 `network.outbound`，升级后请确认它为 `false` 以匹配上架合规要求。
