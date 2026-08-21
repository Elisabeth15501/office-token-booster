# "省 Token" Skill 竞品市场调研报告

> 调研时间：2026-08-21  
> 目标：识别"省 Token"类 Skill 的核心策略差异，寻找 office-token-booster 的差异化定位机会

---

## 一、调研范围与方法

| 平台 | 关键词 | 结果 |
|------|--------|------|
| SkillHub | 省token / token 节约 / 省流 | 3 个直接相关 skill |
| ClawHub / GitHub | token saver / context optimizer / cost optimization | 4 个直接相关项目 |
| 搜索引擎 | openclaw token 省钱 / 省token skill | 行业文章 + 配置指南 |

**直接竞品（3 个 SkillHub + 3 个 ClawHub/GitHub 项目）：**

| # | 名称 | 平台 | 定位 | 核心策略 |
|---|------|------|------|----------|
| 1 | **token省流助手** (qclaw) | SkillHub | 用户输入压缩 | 文本/代码三级压缩 |
| 2 | **词元token节约省钱大师** | SkillHub | 技能结构瘦身 | 扫描+清理技能文件本身 |
| 3 | **省Token技能** (ilang-less-token) | SkillHub | 摘要提示词优化 | 提示词一行化，省40-65% |
| 4 | **OpenClaw Token Saver** | GitHub/ClawHub | 上下文监控+策略建议 | 自动触发+20+策略清单 |
| 5 | **OpenClaw Context Optimizer** | ClawHub | 上下文压缩 | 去重/修剪/摘要+学习系统 |
| 6 | **OpenClaw Token Optimizer** | GitHub | 全链路成本优化 | 模型路由+心跳+缓存+预算追踪 |

---

## 二、竞品核心策略拆解

### 2.1 四大省 Token 策略家族

```
                    ┌──────────────────────────────────────────────┐
                    │              省 Token Skill 家族              │
                    └──────────────────────────────────────────────┘
                                      │
           ┌──────────────────┬───────┴───────┬──────────────────┐
           ▼                  ▼               ▼                   ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ 输入侧压缩    │  │ 上下文侧裁剪  │  │ 模型侧路由    │  │ 结构侧瘦身    │
    │ (Input)      │  │ (Context)    │  │ (Model)      │  │ (Structure)  │
    └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
           │                 │                 │                 │
    省流助手          Context Optimizer   Token Optimizer   token-saver-master
    ilang-less-token  (atlaspa)           (Asif2BD)         (user_ad872d55)
```

#### 策略 A：输入侧压缩（压缩用户说出的内容）
- **token省流助手**（SkillHub）：三级压缩强度（轻度/默认/严格），纯文本+代码+混合三种模式，实时展示节省量。最大承诺：**节省 20%-70%**。
- **ilang-less-token**（SkillHub）：专治"冗长摘要指令"，把一段话的摘要提示词压成一行，**节省 40-65%**。
- **共同特征**：拦截用户输入 → 压缩后再发给模型。本质是**用户端的"节流阀"**。

#### 策略 B：上下文侧裁剪（压缩对话历史/文件）
- **Context Optimizer**（ClawHub）：去重(20-30%)+修剪(30-40%)+摘要(40-60%)+混合(40-60%)，带学习系统自适应。免费 100次/天，Pro 0.5 USDT/月。
- **OpenClaw Token Saver**（GitHub）：50-90% 总省幅，自动在 70%/80%/90% 上下文阈值时触发警告/强制压缩。
- **OpenClaw Token Optimizer**（GitHub）：懒加载上下文（**80% savings**），bootstrap 大小限制（20-40%），Session Pruning。
- **共同特征**：在 API 调用前清洗 context，**不改变用户意图，只减少上下文负载**。

#### 策略 C：模型侧路由（智能选模型）
- **OpenClaw Token Optimizer**：`model_router.py` 根据任务复杂度选模型——简单任务走 Haiku（$1/M token），复杂任务走 Opus（$5/M token）。**节省 60-98%**。
- **配置模板**已给出：`simple→Haiku`，`standard→Sonnet`，`complex→Opus`。
- **共同特征**：不改变 token 数量，只降低 **单价**。需要用户有多模型访问权限。

#### 策略 D：结构侧瘦身（压缩 Skill 文件本身）
- **token-saver-master**（SkillHub）：**最独特的角度**——扫描 `D:\Qclaw Document\skills\` 下所有技能，识别冗余 SKILL.md、重复技能、过长 description，执行清理。
- 目标不是省用户的对话 Token，而是**省所有调用该 Skill 时的系统提示 Token**。
- **共同特征**：针对 Skill 开发者/管理员的"基础设施优化"，而非终端用户的"对话优化"。

---

## 三、各竞品详细对比表

| 维度 | token省流助手 | ilang-less-token | token-saver-master | Context Optimizer | Token Saver (JX-76) | Token Optimizer (Asif2BD) |
|------|------------|-----------------|-------------------|-------------------|--------------------|--------------------------|
| **平台** | SkillHub | SkillHub | SkillHub | ClawHub | GitHub/ClawHub | GitHub |
| **定位** | 输入压缩器 | 提示词压缩 | 技能结构审计 | 上下文压缩 | 上下文监控+策略 | 全链路成本优化 |
| **省 Token 方式** | 压缩用户输入 | 一行化摘要提示词 | 清理技能文件 | 去重/修剪/摘要 | 自动触发压缩 | 懒加载+路由+心跳+缓存 |
| **目标用户** | 日常对话用户 | 摘要需求用户 | Skill 开发者 | 重度对话用户 | 通用用户 | 重度/OpenClaw 用户 |
| **节省幅度** | 20-70% | 40-65% | 取决于技能规模 | 40-60% | 50-90% | 50-80% |
| **是否需要 API Key** | ❌ 纯本地 | ❌ 纯本地 | ❌ 纯本地 | ❌ 纯本地 | ❌ 纯本地 | ❌ 纯本地 |
| **联网需求** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **学习/自适应** | ❌ | ❌ | ❌ | ✅ 学习系统 | ❌ | ❌ |
| **ROI 追踪** | ✅ 实时节省数 | ❌ | ❌ | ✅ 内置 ROI 计算 | ✅ 状态面板 | ✅ token_tracker |
| **付费模式** | 免费 | 免费 | 免费 | 免费+Pro(0.5USDT) | 免费 | 免费 |
| **安装方式** | SkillHub 一键 | SkillHub 一键 | SkillHub 一键 | ClawHub/npx | git clone | git clone |

---

## 四、市场空白与机会分析

### 4.1 当前市场的三个盲区

| 盲区 | 描述 | 现有竞品是否覆盖 |
|------|------|----------------|
| **① 用量可见性（"看见"而非"压缩"）** | 用户不知道自己在哪花 token，只是被动省。没有工具帮用户**看清**token 花在哪、哪个任务最费、哪个最省。 | ❌ 无竞品覆盖 |
| **② 量化节省价值（"省了多少"而非"怎么省"）** | 现有 skill 只告诉用户"压缩了 X token"，但不回答"这次任务我到底省了多少钱/多少时间"。 | ❌ 无竞品覆盖 |
| **③ 任务级 vs 系统级** | 现有 skill 要么是系统级（压缩所有对话），要么是结构级（清理技能文件）。缺少**任务级**视角——哪个办公任务类型最费 token、哪些该自动化、哪些该跳过 AI。 | ❌ 无竞品覆盖 |

### 4.2 office-token-booster 的差异化定位

```
现有竞品格局:

  [输入压缩] ← token省流助手, ilang-less-token
  [上下文裁剪] ← Context Optimizer, Token Saver
  [模型路由] ← Token Optimizer
  [结构瘦身] ← token-saver-master
  ──────────────────────────────────────────
  [用量洞察 + 任务级优化] ← 市场空白 ← office-token-booster 的位置
```

**office-token-booster 的独特价值主张（UVP）：**

> "其他 skill 帮你**少花** token，office-token-booster 帮你**看清** token 花在哪、**算清楚**省了多少、**指出**哪里最该优化。"

| 对比维度 | 竞品（省 Token） | office-token-booster |
|----------|----------------|---------------------|
| **核心动作** | 压缩/路由/裁剪（主动干预） | 度量/记账/诊断（被动观察） |
| **用户感知** | "我的输入被压缩了" | "原来我周报最费 token" |
| **输出物** | 更短的 token 流 | 报告 + 可视化 + ROI 建议 |
| **定位** | 工具型（执行） | 洞察型（分析） |
| **与竞品的关系** | 互补：先用竞品压缩，再用本 skill 看效果 | 可组合：「省了 token → 省了多少 → 下一步优化什么」 |

### 4.3 与竞品的协同场景（非竞争关系）

| 场景 | 竞品 A | 竞品 B | office-token-booster 的角色 |
|------|--------|--------|---------------------------|
| 长对话省 token | Context Optimizer 压缩上下文 | — | 压缩后跑一遍本 skill，看压缩前后的 cost 对比 |
| 任务级分析 | 省流助手压缩输入 | — | 记账 + 生成"哪个任务类型最费"的报告 |
| 月度复盘 | Token Saver 的 ROI 追踪 | — | 接入真实宿主 traces，跨周/月趋势可视化 |
| 多 skill 协同 | — | — | 作为**度量层**串起所有省 token 动作的效果评估 |

---

## 五、对 office-token-booster 的策略建议

### 5.1 确认定位：坚持"洞察"，不碰"执行"

市场已验证"压缩/裁剪/路由"类 skill 有需求（下载量 260+，多平台均有发布）。但这类 skill 的本质是**执行工具**——它们替用户做了决策（压缩/路由/裁剪），改变了用户与模型的交互过程。

office-token-booster 的核心价值在于**不做这些干预，只提供信息**——这正是 v0.9 Option C「洞察定位」的正确性所在：
- 竞争对手越多的领域（省 token 执行），你的差异化空间越小
- 没人做的领域（token 洞察+任务级分析），你的护城河越大

### 5.2 可考虑的增强方向（v0.10+）

1. **与省 token skill 联动**：在报告中增加"已安装的省 token skill 列表 + 预估节省贡献"，帮助用户理解自己的优化栈
2. **任务级 baseline**：不仅看总消耗，还按任务类型（周报/纪要/Excel）分桶，告诉用户"你的周报任务占 35% 的 token"
3. **月度趋势 + 异常检测**：与 agent-analytics-report 的思路一致，检测 token 峰值（如"本周比上周多花了 3 倍"）

### 5.3 市场定位一句话

> **office-token-booster 是「省 Token 技能生态」的度量层**——别人帮你省，你帮他们看省了多少。

---

## 六、附录：SkillHub 上找到的三个 skill 详情

### 6.1 token省流助手 (`user_29dc410e/token-saver-qclaw`)
- **版本**：v6.0.0 稳健增强版
- **平台**：QClaw / OpenClaw
- **安装**：SkillHub 一键安装
- **核心功能**：三级压缩（轻度/默认/严格）+ 代码安全压缩 + 系统指令保护 + 实时节省统计
- **特点**：零依赖纯 Python，自然语言切换压缩模式（"严格模式"/"轻度模式"）

### 6.2 词元token节约省钱大师 (`user_ad872d55/token-saver-master`)
- **平台**：SkillHub
- **定位**：技能结构审计器
- **核心功能**：扫描 skills/ 目录 → 识别 SKILL.md >100行、description >120字、重复技能 → 输出优化建议 → 等待授权后执行清理
- **特点**：最独特的角度——从 Skill 本身的大小入手省 token，而非对话内容

### 6.3 省Token技能 (`ilang-less-token`)
- **版本**：v1.0.4
- **评分**：4.3/5.0（AI 评分）
- **下载量**：260+
- **核心功能**：将摘要类提示词压缩为一行 I-Lang 指令
- **特点**：垂直领域专注——只解决"摘要指令太冗长"这一个痛点

---

*报告生成时间：2026-08-21*  
*数据来源：SkillHub (skillhub.cloud.tencent.com)、ClawHub (clawhub.ai)、GitHub*
