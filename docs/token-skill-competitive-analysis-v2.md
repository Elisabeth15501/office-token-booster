# 「省 Token」Skill 市场调研 & office-token-booster 推荐能力可行性分析

> 调研时间：2026-08-21  
> 目标：识别「省 Token」类 Skill 的核心策略差异，评估 office-token-booster 增加「推荐合适 Skill 去省 Token」功能的可行性

---

## 一、核心竞品全景图

### 1.1 八大直接竞品一览

| # | Skill 名称 | 作者/来源 | GitHub Stars | 核心策略 | 实测节省 |
|---|----------|----------|-------------|---------|---------|
| 1 | **Caveman** | JuliusBrussee | 85K+ | 输出侧压缩：AI 用"穴居人语"说话 | 输出 −65%（JetBrains 实测 −8.5%） |
| 2 | **Ponytail** | DietrichGebert | 104K | YAGNI 决策阶梯：强制最少代码 | 代码 −54%、Token −22%、成本 −20% |
| 3 | **token-diet** | Kulaxyz | 446 | 六维治理：回复/文档/测试/代码/上下文/工具 | 平均 −31% 账单 |
| 4 | **RTK** | rtk-ai | 71.5K | 输入侧压缩：CLI 输出代理层过滤 | 噪声 −89%（命令级 −49%~−92%） |
| 5 | **Token Tamer** | theshadowrose | — | 预算追踪 + 浪费检测 + Kill Switch |  observability 层，不直接省 |
| 6 | **Context Optimizer** | atlaspa (ClawHub) | — | 去重/修剪/摘要 + 学习系统 | 40–60% |
| 7 | **Token Optimizer** | Asif2BD (GitHub) | — | 模型路由 + 懒加载 + 心跳管理 | 50–80%（取决于模型差价） |
| 8 | **Low Token Usage** | IKKF | — | 三级自适应压缩（low/medium/extreme） | 未公开 |

### 1.2 SkillHub / ClawHub 本地生态

| Skill | 平台 | 定位 | 特点 |
|-------|------|------|------|
| token省流助手 | SkillHub | 输入压缩器 | 三级强度 + 实时节省数 |
| ilang-less-token | SkillHub | 提示词一行化 | 专治摘要指令冗长 |
| token-saver-master | SkillHub | 技能结构审计 | 清理 SKILL.md 本身的大小 |

---

## 二、四大策略家族对比

```
省 Token Skill 家族
         │
    ┌────┴────────────────────────────────┐
    │                                     │
输入侧压缩                              输出侧压缩
 (Input)                                (Output)
    │                                     │
RTK (71.5K)                         Caveman (85K)
token省流助手                        token-diet (446)
                                     Low Token Usage
    │                                     │
CLI 输出代理层                      Prompt 工程
压缩终端噪音                        让 AI 闭嘴
    │                                     │
↓ 89% 噪声去除                      ↓ 65% 输出 Token
    │                                     │
    └───────────────┬─────────────────────┘
                    │
           行为约束型 (Behavioral)
                    │
              Ponytail (104K) ⭐最大
              决策阶梯：能否用原生/标准库/一行？
                    │
              ↓ −54% LOC / −22% Token / 100% 安全
```

### 关键发现：互补而非竞争

Caveman 和 Ponytail 的作者明确说：
> "Caveman 压'怎么说'，Ponytail 压'建什么'。两者不重叠，可以叠加使用。"

RTK 压输入，Caveman 压输出 —— 双向节流组合使用效果最佳。

这意味着：
- **没有单一"最佳"省 token skill**，不同场景适用不同 skill
- 用户需要的是**诊断 → 推荐 → 安装 → 验证**的完整闭环

---

## 三、market gap 分析

### 3.1 三个市场盲区

| 盲区 | 描述 | 现有竞品覆盖 |
|------|------|------------|
| **① 用量可见性** | 用户不知道自己在哪花 token，只是被动省 | ❌ 无 |
| **② 量化节省价值** | 只告诉用户"压缩了 X token"，但不回答"这次任务省了多少钱" | ❌ 无 |
| **③ 任务级 vs 系统级** | 现有 skill 要么是系统级（压缩所有对话），要么是结构级（清理技能文件）。缺少任务级视角——哪个办公任务类型最费 token、哪些该自动化 | ❌ 无 |

### 3.2 office-token-booster 的独特定位

```
竞品格局:

  [输入压缩] ← RTK, token省流助手
  [输出压缩] ← Caveman, token-diet
  [行为约束] ← Ponytail
  [预算追踪] ← Token Tamer
  [上下文裁剪] ← Context Optimizer
  ──────────────────────────────────────────
  [用量洞察 + 任务级分析 + Skill 推荐] ← 市场空白
                                           ↑
                                  office-token-booster 的位置
```

**核心差异化：**
> "其他 skill 帮你**少花** token，office-token-booster 帮你**看清** token 花在哪、**算清楚**省了多少、**指出**下一步该装什么 Skill。"

---

## 四、office-token-booster + Skill 推荐功能可行性分析

### 4.1 用户场景链路

```
用户完成一周工作
     │
     ▼
调用 office-token-booster 生成周报
     │
     ├── 报告呈现：本周总消耗、任务类型分布、异常检测
     │
     ├── 【新增】洞察板块："你的周报任务占比 35%，是最大 Token 消耗项"
     │
     ├── 【新增】推荐板块："推荐安装 Ponytail 或 Caveman 来优化代码/对话类任务"
     │
     └── 【新增】一键安装：`clawhub install ponytail` / `npx skills add JuliusBrussee/caveman`
```

### 4.2 技术可行性：完全复用现有栈

| 能力 | 已有基础设施 | 新增需求 |
|------|------------|---------|
| Skill 发现 | `find-skills` skill（npm query + search） | ✅ 已可用 |
| Skill 详情 | SkillHub/ClawHub API | ✅ 已可用 |
| Skill 安装建议 | `suggest_plugin_install` | ✅ 已可用 |
| 用户用量数据 | `host_cost.py` 真实 traces 读取 | ✅ 已可用 |
| 任务分类 | 现有 `aggregate_traces_by` 按 task 分组 | ✅ 已可用 |

### 4.3 推荐逻辑设计

```python
# 伪代码：推荐引擎核心逻辑

def recommend_token_saving_skills(usage_data: dict) -> list[Recommendation]:
    """根据用量数据推荐最合适的省 token skill"""
    
    recommendations = []
    
    # 1. 识别高消耗任务类型
    task_costs = usage_data.get("task_cost_breakdown", {})
    top_tasks = sorted(task_costs.items(), key=lambda x: x[1], reverse=True)[:3]
    
    for task_type, cost in top_tasks:
        # 2. 任务类型 → skill 映射
        if "代码" in task_type or "编程" in task_type:
            recommendations.append(Recommendation(
                skill="ponytail",
                reason=f"你的'{task_type}'任务消耗 {cost:.2f} 元，Ponytail 可减 22% Token",
                install_cmd="clawhub install ponytail",
                expected_saving="-22% Token (Ponytail agentic benchmark)",
                priority="HIGH"
            ))
        
        elif "对话" in task_type or "问答" in task_type or "咨询" in task_type:
            recommendations.append(Recommendation(
                skill="caveman",
                reason=f"你的'{task_type}'任务消耗 {cost:.2f} 元，Caveman 可减 65% 输出 Token",
                install_cmd="npx skills add JuliusBrussee/caveman",
                expected_saving="-65% output tokens (Caveman README)",
                priority="HIGH"
            ))
        
        elif "终端" in task_type or "日志" in task_type or "编译" in task_type:
            recommendations.append(Recommendation(
                skill="rtk",
                reason=f"你的'{task_type}'任务消耗 {cost:.2f} 元，RTK 可过滤 89% 噪声",
                install_cmd="curl -fsSL https://rtk-ai.app/install.sh | sh",
                expected_saving="-89% CLI noise (RTK benchmark)",
                priority="MEDIUM"
            ))
    
    # 3. 全局建议（按总消耗量排序）
    total_cost = usage_data.get("total_cost", 0)
    if total_cost > 50:  # 高消耗用户
        recommendations.insert(0, Recommendation(
            skill="token-diet",
            reason=f"本周总消耗 {total_cost:.2f} 元，token-diet 综合六维治理平均省 31%",
            install_cmd="curl -fsSL https://raw.githubusercontent.com/Kulaxyz/token-diet/main/install.sh | bash",
            expected_saving="-31% bill on average",
            priority="CRITICAL"
        ))
    
    return recommendations[:3]  # 最多推荐 3 个
```

### 4.4 推荐规则表（task_type → skill 映射）

| 用户任务类型 | 推荐 Skill | 安装命令 | 预期节省 | 证据来源 |
|------------|-----------|---------|---------|---------|
| 代码/编程/开发 | **Ponytail** | `clawhub install ponytail` | −22% Token, −20% 成本 | Ponytail agentic benchmark |
| 对话/问答/咨询 | **Caveman** | `npx skills add JuliusBrussee/caveman` | −65% 输出 Token | Caveman README |
| 终端/日志/编译 | **RTK** | `curl -fsSL https://rtk-ai.app/install.sh \| sh` | −89% 噪声 | RTK benchmark (2,900+ commands) |
| 综合高消耗 (>50元/周) | **token-diet** | `curl ... \| bash` | −31% 账单 | token-diet Sonnet 5 benchmark |
| 上下文过长 | **Context Optimizer** | `clawhub install context-optimizer` | −40~60% | ClawHub 文档 |
| 模型使用不均 | **Token Optimizer** | `git clone ...` | −60~98%（取决于差价） | GitHub README |

---

## 五、实施路径建议

### Phase 1：MVP（v0.9.1）— 本地 Skill 推荐

- **触发点**：报告生成后，如果检测到高消耗任务类型
- **数据来源**：本机 traces + 硬编码的推荐规则表
- **输出**：报告末尾新增「推荐 Skill」板块（最多 3 个）
- **安装**：展示安装命令，需用户手动执行
- **限制**：仅推荐本地已确认的 Skill（不联网搜索）

### Phase 2：扩展（v1.0）— 联网推荐 + 预估节省

- **触发点**：同上
- **数据来源**：本机 traces + SkillHub 联网搜索
- **新增能力**：
  - 根据用户任务类型自动搜索匹配 Skill
  - 展示 Skill 详情（stars、下载量、评价）
  - 预估节省金额（基于 benchmark 数据 × 用户当前费率）
- **一键安装**：调用 `suggest_plugin_install` 提交安装建议

### Phase 3：进阶（v1.1+）— 闭环验证

- **触发点**：用户安装推荐 Skill 后
- **新增能力**：
  - 自动检测新 Skill 是否生效（通过 traces 分析）
  - 对比安装前后的 token 消耗变化
  - 生成「优化效果报告」（已省 XX 元）
- **形成闭环**：度量 → 推荐 → 安装 → 验证 → 再度量

---

## 六、风险评估与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 推荐过度泛化，伤口碑 | 用户装了不匹配的 Skill，体验差 | 严格限定：仅推荐与报告直接相关 + 有量化 benchmark 的 Skill |
| Skill 数据源不稳定 | SkillHub/ClawHub API 变更导致推荐失效 | 硬编码 fallback 列表 + 定期同步 |
| 推荐与竞品的重叠 | 用户可能已有同类 Skill | 检测本地已装 Skill，跳过重复推荐 |
| 用户不信任自动推荐 | 视为广告或推广 | 透明化：展示 evidence（benchmark 链接）、标注「预估」而非承诺 |

---

## 七、结论

### 7.1 市场机会确认

✅ **用户需求强**：看完报告后自然追问「那我该用什么 Skill？」  
✅ **技术完全可行**：复用 recommend-experts 的 `search_plugins + suggest_plugin_install` 栈  
✅ **市场空白明显**：竞品只做"执行"（压缩/路由），无人做"洞察 + 推荐"  
✅ **差异化定位清晰**：office-token-booster = 「省 Token 技能生态」的度量层

### 7.2 一句话定位

> **office-token-booster 是「省 Token 技能生态」的度量层——别人帮你省，你帮他们看省了多少；别人帮你压缩，你帮他们选对压缩策略。**

### 7.3 下一步行动

- [ ] Phase 1 MVP：在 `generate_report.py` 中新增 `recommend_skills()` 函数
- [ ] 硬编码推荐规则表（task_type → skill 映射）
- [ ] 报告模板新增「推荐 Skill」板块
- [ ] 联调测试：真实 traces 数据 → 推荐结果验证
- [ ] v0.9.1 版本发布

---

*报告生成时间：2026-08-21*  
*数据来源：GitHub、SkillHub、ClawHub、BetterClaw Blog、JetBrains Research*
