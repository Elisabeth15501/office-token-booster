#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill_recommender.py — office-token-booster v0.9.1 Skill 推荐引擎

根据用户用量数据推荐最适合的「省 Token」Skill。

设计原则：
- 纯函数，无副作用，无网络请求
- 硬编码推荐规则表（task_type → skill 映射），避免依赖外部 API
- 每个推荐附带量化依据（benchmark 数据），不夸大的承诺
- 最多返回 3 个推荐，避免推荐过载
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SkillRecommendation:
    """一条 Skill 推荐记录。"""

    skill: str                          # Skill 名称（用于展示和安装命令）
    reason: str                         # 推荐理由（自然语言）
    install_cmd: str                    # 安装命令（可直接复制执行）
    expected_saving: str                # 预期节省（来自 benchmark，标注来源）
    priority: str = "MEDIUM"           # CRITICAL / HIGH / MEDIUM
    evidence_url: Optional[str] = None  # 数据来源链接（可选）


# ─────────────────────────────────────────────────────────────
# 推荐规则表：task_type → 匹配规则
# ─────────────────────────────────────────────────────────────

# 关键词映射：任务类型关键词 → 推荐 Skill
_TASK_TYPE_RULES = [
    {
        "keywords": ["代码", "编程", "开发", "写代码", "重构", "debug", "调试"],
        "skill": SkillRecommendation(
            skill="ponytail",
            reason="你的'{task_type}'任务消耗较高，Ponytail 通过 YAGNI 决策阶梯强制最少代码，实测减 22% Token / 20% 成本",
            install_cmd="clawhub install ponytail",
            expected_saving="-22% Token (Ponytail agentic benchmark, 12 tasks, Haiku 4.5)",
            priority="HIGH",
            evidence_url="https://github.com/DietrichGebert/ponytail",
        ),
    },
    {
        "keywords": ["对话", "问答", "咨询", "聊天", "讨论", "解释"],
        "skill": SkillRecommendation(
            skill="caveman",
            reason="你的'{task_type}'任务消耗较高，Caveman 让 AI 用精简语言回复，输出侧平均减 65% Token",
            install_cmd="npx skills add JuliusBrussee/caveman",
            expected_saving="-65% output tokens (Caveman README, 10-task benchmark)",
            priority="HIGH",
            evidence_url="https://github.com/JuliusBrussee/caveman",
        ),
    },
    {
        "keywords": ["终端", "日志", "编译", "测试", "git", "命令行", "CLI", "构建"],
        "skill": "rtk",
        "reason_template": "你的'{task_type}'任务涉及终端输出，RTK 过滤 CLI 噪声，实测平均减 89% 无效 Token",
        "install_cmd": "curl -fsSL https://rtk-ai.app/install.sh | sh",
        "expected_saving": "-89% CLI noise (RTK benchmark, 2,900+ commands)",
        "priority": "MEDIUM",
        "evidence_url": "https://github.com/rtk-ai/rtk",
    },
    {
        "keywords": ["周报", "纪要", "会议纪要", "总结", "报告"],
        "skill": SkillRecommendation(
            skill="token-diet",
            reason="你的'{task_type}'任务消耗较高，token-diet 六维治理综合优化，平均减 31% 账单",
            install_cmd="curl -fsSL https://raw.githubusercontent.com/Kulaxyz/token-diet/main/install.sh | bash",
            expected_saving="-31% bill on average (token-diet Sonnet 5 benchmark)",
            priority="MEDIUM",
            evidence_url="https://github.com/Kulaxyz/token-diet",
        ),
    },
]

# 全局阈值规则：总消耗超过阈值时触发
_GLOBAL_RULES = [
    {
        "threshold_cost": 50.0,  # 元/周
        "condition": "total_cost >= threshold",
        "skill": SkillRecommendation(
            skill="token-diet",
            reason="本周总消耗较高，token-diet 六维治理综合优化，平均减 31% 账单",
            install_cmd="curl -fsSL https://raw.githubusercontent.com/Kulaxyz/token-diet/main/install.sh | bash",
            expected_saving="-31% bill on average (token-diet Sonnet 5 benchmark)",
            priority="CRITICAL",
            evidence_url="https://github.com/Kulaxyz/token-diet",
        ),
    },
    {
        "threshold_tasks": 10,  # 任务数
        "condition": "total_tasks >= threshold",
        "skill": SkillRecommendation(
            skill="caveman",
            reason="本周任务频繁，Caveman 让 AI 精简回复，累计节省可观",
            install_cmd="npx skills add JuliusBrussee/caveman",
            expected_saving="-65% output tokens (Caveman README)",
            priority="MEDIUM",
            evidence_url="https://github.com/JuliusBrussee/caveman",
        ),
    },
]


def recommend_skills(
    by_type: list[dict],
    total_tasks: int,
    max_recommendations: int = 3,
) -> list[SkillRecommendation]:
    """根据用量数据推荐最适合的省 Token Skill。

    Args:
        by_type: 按任务类型聚合的统计数据，每项含 task_type / baseline_tokens / skill_tokens 等
        total_tasks: 总任务数（对应 Diagnosis.n）
        max_recommendations: 最多返回几条推荐

    Returns:
        SkillRecommendation 列表，按 priority 降序排列
    """
    """根据用量数据推荐最适合的省 Token Skill。

    Args:
        by_type: 按任务类型聚合的统计数据，每项含 task_type / baseline_tokens / skill_tokens 等
        total_tasks: 总任务数
        total_cost: 总消耗（元），用于全局阈值规则
        max_recommendations: 最多返回几条推荐

    Returns:
        SkillRecommendation 列表，按 priority 降序排列
    """
    recommendations: dict[str, SkillRecommendation] = {}

    # 1. 任务类型匹配
    for type_stat in by_type:
        task_type = type_stat.get("task_type", "")
        for rule in _TASK_TYPE_RULES:
            keywords = rule.get("keywords", [])
            if not keywords:
                continue
            if any(kw in task_type for kw in keywords):
                rec = rule["skill"]
                if isinstance(rec, SkillRecommendation):
                    # 替换模板变量
                    final_reason = rec.reason.format(task_type=task_type)
                    rec = SkillRecommendation(
                        skill=rec.skill,
                        reason=final_reason,
                        install_cmd=rec.install_cmd,
                        expected_saving=rec.expected_saving,
                        priority=rec.priority,
                        evidence_url=rec.evidence_url,
                    )
                elif isinstance(rec, str):
                    # 兼容旧格式（字符串 skill 名 + 单独字段）
                    rule_data = {k: v for k, v in rule.items() if k != "skill"}
                    rec = SkillRecommendation(
                        skill=rule_data.get("skill", rec),
                        reason=rule_data.get("reason_template", f"你的'{task_type}'任务适合 {rec}").format(
                            task_type=task_type
                        ),
                        install_cmd=rule_data["install_cmd"],
                        expected_saving=rule_data["expected_saving"],
                        priority=rule_data.get("priority", "MEDIUM"),
                        evidence_url=rule_data.get("evidence_url"),
                    )
                # 去重：只保留第一个匹配（最高优先级）
                if rec.skill not in recommendations:
                    recommendations[rec.skill] = rec
                break

    # 2. 全局阈值规则（按任务数量触发）
    for rule in _GLOBAL_RULES:
        if "threshold_tasks" in rule and total_tasks >= rule["threshold_tasks"]:
            rec = rule["skill"]
            if rec.skill not in recommendations:
                recommendations[rec.skill] = rec

    # 3. 排序：CRITICAL > HIGH > MEDIUM
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    sorted_recs = sorted(
        recommendations.values(),
        key=lambda x: priority_order.get(x.priority, 99),
    )

    return sorted_recs[:max_recommendations]


def format_recommendation_md(rec: SkillRecommendation) -> str:
    """将单条推荐格式化为 Markdown。"""
    lines = [
        f"### 🎯 推荐：{rec.skill}",
        "",
        f"- **原因**：{rec.reason}",
        f"- **预期节省**：{rec.expected_saving}",
        f"- **安装命令**：`{rec.install_cmd}`",
    ]
    if rec.evidence_url:
        lines.append(f"- **数据来源**：[{rec.evidence_url}]({rec.evidence_url})")
    lines.append("")
    return "\n".join(lines)


def format_recommendations_md(recommendations: list[SkillRecommendation]) -> str:
    """将推荐列表格式化为 Markdown 板块。"""
    if not recommendations:
        return "## 推荐 Skill\n\n暂无匹配推荐。当你有更多任务数据后，系统会智能推荐合适的省 Token Skill。\n"

    lines = ["## 推荐 Skill\n", "> 基于你的任务类型和消耗量，推荐以下 Skill 来降低 Token 成本：\n"]
    for rec in recommendations:
        lines.append(format_recommendation_md(rec))
    return "\n".join(lines)


def format_recommendations_html(recommendations: list[SkillRecommendation]) -> str:
    """将推荐列表格式化为 HTML 板块。"""
    if not recommendations:
        return """
    <h2>推荐 Skill</h2>
    <p style="color:var(--muted)">暂无匹配推荐。当你有更多任务数据后，系统会智能推荐合适的省 Token Skill。</p>
    """

    cards = []
    for rec in recommendations:
        priority_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟢"}.get(rec.priority, "⚪")
        card = f"""
    <div class="rec-card" style="border-left: 4px solid {'#dc2626' if rec.priority == 'CRITICAL' else '#ea580c' if rec.priority == 'HIGH' else '#16a34a'}; margin: 12px 0; padding: 14px; background: #f9fafb; border-radius: 8px;">
      <div style="font-weight: 700; font-size: 16px; margin-bottom: 8px;">{priority_emoji} {rec.skill}</div>
      <div style="font-size: 13px; color: var(--fg); margin-bottom: 6px;">{rec.reason}</div>
      <div style="font-size: 13px; color: var(--accent); font-weight: 600; margin-bottom: 6px;">预期节省：{rec.expected_saving}</div>
      <div style="font-size: 12px;">
        <span style="color: var(--muted);">安装：</span>
        <code style="background: #e5e7eb; padding: 2px 6px; border-radius: 4px;">{rec.install_cmd}</code>
      </div>
      {'<div style="font-size: 11px; color: var(--muted); margin-top: 6px;">来源：%s</div>' % rec.evidence_url if rec.evidence_url else ''}
    </div>"""
        cards.append(card)

    html = """
    <h2>推荐 Skill</h2>
    <p style="color:var(--muted); font-size: 13px;">基于你的任务类型和消耗量，推荐以下 Skill 来降低 Token 成本：</p>
    """ + "\n".join(cards)
    return html
