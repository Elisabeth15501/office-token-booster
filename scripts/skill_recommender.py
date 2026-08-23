#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill_recommender.py — office-token-booster v0.9.2 Skill 推荐引擎

根据用户用量数据推荐最适合的「省 Token」Skill。

设计原则：
- Phase 1：纯函数，无副作用，硬编码推荐规则表（task_type → skill 映射）
- Phase 2：支持 SkillHub 联网搜索，动态获取最新 Skill 信息
- ⚠️ 安装是危险动作，必须用户亲自确认才能执行
- 每个推荐附带量化依据（benchmark 数据），不夸大的承诺
- 最多返回 3 个推荐，避免推荐过载
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    # Phase 2 新增字段
    skillhub_slug: Optional[str] = None  # SkillHub slug（用于联网查询）
    skillhub_info: Optional[dict] = None  # SkillHub 详情（搜索后填充）
    clawhub_info: Optional[dict] = None   # ClawHub 详情（搜索后填充）
    requires_confirmation: bool = True  # 是否需用户确认才安装


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
            skillhub_slug="ponytail",
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
            skillhub_slug="caveman",
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
        "skillhub_slug": "rtk",
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
            skillhub_slug="token-diet",
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
    use_online_search: bool = False,
) -> list[SkillRecommendation]:
    """根据用量数据推荐最适合的省 Token Skill。

    Args:
        by_type: 按任务类型聚合的统计数据，每项含 task_type / baseline_tokens / skill_tokens 等
        total_tasks: 总任务数（对应 Diagnosis.n）
        max_recommendations: 最多返回几条推荐
        use_online_search: 是否启用 SkillHub 联网搜索（Phase 2）

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
                        skillhub_slug=rec.skillhub_slug,
                        requires_confirmation=True,
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
                        skillhub_slug=rule_data.get("skillhub_slug"),
                        requires_confirmation=True,
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
                rec.requires_confirmation = True
                recommendations[rec.skill] = rec

    # 3. 排序：CRITICAL > HIGH > MEDIUM
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    sorted_recs = sorted(
        recommendations.values(),
        key=lambda x: priority_order.get(x.priority, 99),
    )

    result = sorted_recs[:max_recommendations]

    # 4. Phase 2：联网搜索补充信息（可选）
    if use_online_search and result:
        from skillhub_client import search_token_saving_skills
        from clawhub_client import search_clawhub

        # 搜索 SkillHub
        try:
            online_skills = search_token_saving_skills(limit=10)
            for rec in result:
                if rec.skillhub_slug and not rec.skillhub_info:
                    # 尝试从搜索结果中找到匹配的 Skill
                    for skill in online_skills.skills:
                        if skill.slug == rec.skillhub_slug or skill.name.lower() == rec.skill.lower():
                            rec.skillhub_info = {
                                "source": "skillhub",
                                "slug": skill.slug,
                                "name": skill.name,
                                "description": skill.description_zh,
                                "stars": skill.stars,
                                "installs": skill.installs,
                                "homepage": skill.homepage,
                                "tags": skill.tags,
                            }
                            break
        except Exception as e:
            print(f"[SkillRecommender] SkillHub search failed: {e}", file=__import__("sys").stderr)

        # 搜索 ClawHub
        try:
            clawhub_skills = search_clawhub(result[0].skill, limit=5)
            for rec in result:
                if not rec.clawhub_info:
                    # 尝试匹配
                    for skill in clawhub_skills.skills:
                        if skill.slug == rec.skill or skill.name.lower() == rec.skill.lower():
                            rec.clawhub_info = {
                                "slug": skill.slug,
                                "name": skill.name,
                                "summary": skill.summary,
                                "owner": skill.owner,
                                "stars": skill.stars,
                                "installs": skill.installs,
                                "tags": skill.tags,
                                "homepage": skill.homepage,
                                "install_ref": skill.install_ref,
                            }
                            break
        except Exception as e:
            print(f"[SkillRecommender] ClawHub search failed: {e}", file=__import__("sys").stderr)

    return result


def format_recommendation_md(rec: SkillRecommendation) -> str:
    """将单条推荐格式化为 Markdown（含安装确认提示）。"""
    lines = [
        f"### 🎯 推荐：{rec.skill}",
        "",
        f"- **原因**：{rec.reason}",
        f"- **预期节省**：{rec.expected_saving}",
    ]

    # 如果有 SkillHub 信息，显示详细数据
    if rec.skillhub_info:
        info = rec.skillhub_info
        lines.append(f"- **SkillHub**：⭐{info.get('stars', 0)} | {info.get('installs', 0)} 安装")
        if info.get('description'):
            lines.append(f"- **描述**：{info['description'][:100]}...")
        if info.get('homepage'):
            lines.append(f"- **仓库**：{info['homepage']}")
        if info.get('tags'):
            lines.append(f"- **标签**：{', '.join(info['tags'][:5])}")

    # 如果有 ClawHub 信息，显示详细数据
    if rec.clawhub_info:
        info = rec.clawhub_info
        lines.append(f"- **ClawHub**：⭐{info.get('stars', 0)} | {info.get('installs', 0)} 安装")
        if info.get('summary'):
            lines.append(f"- **描述**：{info['summary'][:100]}...")
        if info.get('owner'):
            lines.append(f"- **作者**：{info['owner']}")
        if info.get('homepage'):
            lines.append(f"- **仓库**：{info['homepage']}")
        if info.get('tags'):
            lines.append(f"- **标签**：{', '.join(info['tags'][:5])}")

    if rec.evidence_url:
        lines.append(f"- **数据来源**：[{rec.evidence_url}]({rec.evidence_url})")

    # 安装确认提示（必须用户亲自确认）
    lines += [
        "",
        "⚠️ **安装确认**：",
        "",
        f"> 请确认无误后，手动运行以下命令安装：",
        "",
        f"```bash",
        f"{rec.install_cmd}",
        f"```",
        "",
        "> 🛡️ **安全提示**：安装 Skill 会修改你的 `.workbuddy/` 目录。",
        "> 如需回滚，可手动删除对应目录。",
    ]
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
    """将推荐列表格式化为 HTML 板块（含安装确认提示）。"""
    if not recommendations:
        return """
    <h2>推荐 Skill</h2>
    <p style="color:var(--muted)">暂无匹配推荐。当你有更多任务数据后，系统会智能推荐合适的省 Token Skill。</p>
    """

    cards = []
    for rec in recommendations:
        priority_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟢"}.get(rec.priority, "⚪")
        priority_color = '#dc2626' if rec.priority == 'CRITICAL' else '#ea580c' if rec.priority == 'HIGH' else '#16a34a'

        # SkillHub 信息
        hub_info_html = ""
        if rec.skillhub_info:
            info = rec.skillhub_info
            stars = info.get('stars', 0)
            installs = info.get('installs', 0)
            desc = info.get('description', '')[:80] + '...' if info.get('description') else '暂无描述'
            tags_html = ''.join(f"<span style='background:#e5e7eb;padding:2px 6px;border-radius:4px;font-size:11px;margin-right:4px'>{t}</span>" for t in info.get('tags', [])[:5])

            hub_info_html = f"""
            <div style="margin-top:8px;padding:8px;background:#f0f9ff;border-radius:6px;font-size:12px;">
              <div style="font-weight:600;color:#0369a1;margin-bottom:4px;">📦 SkillHub 信息</div>
              <div style="color:#475569;">⭐{stars} | {installs} 安装</div>
              <div style="color:#64748b;margin-top:4px;">{desc}</div>
              {f'<div style="margin-top:6px;">{tags_html}</div>' if info.get('tags') else ''}
              {f'<div style="margin-top:4px;"><a href="{info["homepage"]}" target="_blank" style="color:#2563eb;font-size:11px;">查看仓库</a></div>' if info.get('homepage') else ''}
            </div>"""

        card = f"""
    <div class="rec-card" style="border-left: 4px solid {priority_color}; margin: 12px 0; padding: 14px; background: #f9fafb; border-radius: 8px;">
      <div style="font-weight: 700; font-size: 16px; margin-bottom: 8px;">{priority_emoji} {rec.skill}</div>
      <div style="font-size: 13px; color: var(--fg); margin-bottom: 6px;">{rec.reason}</div>
      <div style="font-size: 13px; color: var(--accent); font-weight: 600; margin-bottom: 6px;">预期节省：{rec.expected_saving}</div>
      {hub_info_html}
      <div style="margin-top:12px;padding:10px;background:#fff7ed;border-radius:6px;border:1px solid #fed7aa;">
        <div style="font-size:12px;font-weight:600;color:#9a3412;margin-bottom:6px;">⚠️ 安装确认</div>
        <div style="font-size:12px;color:#7c2d12;margin-bottom:6px;">请确认无误后，手动运行以下命令安装：</div>
        <pre style="background:#f3f4f6;padding:8px;border-radius:4px;overflow-x:auto;font-size:11px;"><code style="color:#111827;">{rec.install_cmd}</code></pre>
        <div style="font-size:11px;color:#9a3412;margin-top:6px;">🛡️ 安全提示：安装 Skill 会修改你的 <code>.workbuddy/</code> 目录。如需回滚，可手动删除对应目录。</div>
      </div>
      {'<div style="font-size: 11px; color: var(--muted); margin-top: 6px;">来源：<a href="' + rec.evidence_url + '" target="_blank">' + rec.evidence_url + '</a></div>' if rec.evidence_url else ''}
    </div>"""
        cards.append(card)

    html = """
    <h2>推荐 Skill</h2>
    <p style="color:var(--muted); font-size: 13px;">基于你的任务类型和消耗量，推荐以下 Skill 来降低 Token 成本：</p>
    """ + "\n".join(cards)
    return html
