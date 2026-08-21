#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_skill_recommender.py — v0.9.1 Skill 推荐功能测试"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from skill_recommender import (
    recommend_skills,
    format_recommendations_md,
    format_recommendations_html,
    SkillRecommendation,
)


class TestRecommendSkills:
    """推荐引擎核心逻辑测试"""

    def test_code_task_recommends_ponytail(self):
        """代码类任务 → 推荐 Ponytail"""
        by_type = [
            {"task_type": "代码开发", "baseline_tokens": 50000, "skill_tokens": 30000, "count": 5},
        ]
        recs = recommend_skills(by_type, total_tasks=5)
        skills = [r.skill for r in recs]
        assert "ponytail" in skills

    def test_dialogue_task_recommends_caveman(self):
        """对话类任务 → 推荐 Caveman"""
        by_type = [
            {"task_type": "对话问答", "baseline_tokens": 20000, "skill_tokens": 15000, "count": 10},
        ]
        recs = recommend_skills(by_type, total_tasks=10)
        skills = [r.skill for r in recs]
        assert "caveman" in skills

    def test_terminal_task_recommends_rtk(self):
        """终端类任务 → 推荐 RTK"""
        by_type = [
            {"task_type": "终端日志", "baseline_tokens": 80000, "skill_tokens": 60000, "count": 8},
        ]
        recs = recommend_skills(by_type, total_tasks=8)
        skills = [r.skill for r in recs]
        assert "rtk" in skills

    def test_weekly_report_recommends_token_diet(self):
        """周报任务 → 推荐 token-diet"""
        by_type = [
            {"task_type": "周报撰写", "baseline_tokens": 10000, "skill_tokens": 5000, "count": 2},
        ]
        recs = recommend_skills(by_type, total_tasks=2)
        skills = [r.skill for r in recs]
        assert "token-diet" in skills

    def test_no_data_returns_empty(self):
        """无数据时返回空列表"""
        recs = recommend_skills([], total_tasks=0)
        assert recs == []

    def test_max_recommendations_limit(self):
        """最多返回指定数量的推荐"""
        by_type = [
            {"task_type": "代码开发", "baseline_tokens": 50000, "skill_tokens": 30000, "count": 5},
            {"task_type": "对话问答", "baseline_tokens": 20000, "skill_tokens": 15000, "count": 10},
            {"task_type": "终端日志", "baseline_tokens": 80000, "skill_tokens": 60000, "count": 8},
            {"task_type": "周报撰写", "baseline_tokens": 10000, "skill_tokens": 5000, "count": 2},
        ]
        recs = recommend_skills(by_type, total_tasks=25, max_recommendations=2)
        assert len(recs) <= 2

    def test_priority_ordering(self):
        """高优先级排在前面"""
        by_type = [
            {"task_type": "代码开发", "baseline_tokens": 50000, "skill_tokens": 30000, "count": 5},
            {"task_type": "对话问答", "baseline_tokens": 20000, "skill_tokens": 15000, "count": 10},
        ]
        recs = recommend_skills(by_type, total_tasks=15)
        # HIGH 优先级的 ponytail 应在 MEDIUM 之前
        if len(recs) >= 2:
            priorities = [r.priority for r in recs]
            high_idx = priorities.index("HIGH") if "HIGH" in priorities else len(priorities)
            medium_idx = priorities.index("MEDIUM") if "MEDIUM" in priorities else len(priorities)
            assert high_idx < medium_idx

    def test_recommendation_fields(self):
        """推荐字段完整性检查"""
        by_type = [{"task_type": "代码开发", "baseline_tokens": 1000, "skill_tokens": 500, "count": 1}]
        recs = recommend_skills(by_type, total_tasks=1)
        assert len(recs) >= 1
        rec = recs[0]
        assert rec.skill
        assert rec.reason
        assert rec.install_cmd
        assert rec.expected_saving
        assert rec.priority in ["CRITICAL", "HIGH", "MEDIUM"]


class TestFormatRecommendations:
    """格式化输出测试"""

    def test_md_format_contains_keys(self):
        """Markdown 格式包含关键信息"""
        recs = [
            SkillRecommendation(
                skill="ponytail",
                reason="测试原因",
                install_cmd="clawhub install ponytail",
                expected_saving="-22% Token",
                priority="HIGH",
                evidence_url="https://github.com/DietrichGebert/ponytail",
            )
        ]
        md = format_recommendations_md(recs)
        assert "ponytail" in md
        assert "clawhub install ponytail" in md
        assert "-22% Token" in md

    def test_html_format_contains_keys(self):
        """HTML 格式包含关键信息"""
        recs = [
            SkillRecommendation(
                skill="caveman",
                reason="测试原因",
                install_cmd="npx skills add JuliusBrussee/caveman",
                expected_saving="-65%",
                priority="HIGH",
            )
        ]
        html = format_recommendations_html(recs)
        assert "caveman" in html
        assert "npx skills add" in html

    def test_empty_recommendations_md(self):
        """空推荐返回提示文本"""
        md = format_recommendations_md([])
        assert "暂无匹配推荐" in md

    def test_empty_recommendations_html(self):
        """空推荐返回提示 HTML"""
        html = format_recommendations_html([])
        assert "暂无匹配推荐" in html


class TestIntegration:
    """集成测试：与 report_engine 联动"""

    def test_report_engine_imports(self):
        """report_engine 能正确导入 recommender"""
        from report_engine import generate_markdown_report, generate_html_report
        # 只是测试导入，不实际生成报告
        assert callable(generate_markdown_report)
        assert callable(generate_html_report)
