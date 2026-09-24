#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_v102_security_fix.py — v1.0.2 天禧扫描安全整改回归测试

对应天禧 AI 上架扫描报告（detailId 287056）四项发现：
- 中危：build_compare_card 周标签未转义即拼入 HTML
- 低危：--online / use_online_search 联网残留，声明（network.outbound=false）与实现不一致
- 低危：第三方推荐节省数字未经实测验证且未披露
- 信息：CHANGELOG 描述历史修复时嵌入了可复制执行的命令形态
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import report_engine
from report_engine import build_compare_card, generate_html_report
from skill_recommender import (
    recommend_skills,
    format_recommendations_md,
    format_recommendations_html,
)

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
ROOT = SCRIPTS.parent


def _make_pc(week):
    """构造一份 period_compare 形状的 dict（week 可注入任意值）。"""
    return {
        "direction": "up",
        "current_week": week,
        "previous_week": week,
        "current": {"saved_tokens": 100, "count": 2, "saved_minutes": 10},
        "previous": {"saved_tokens": 50, "count": 1, "saved_minutes": 5},
        "saved_tokens_pct": 100.0,
        "count_pct": 100.0,
        "saved_minutes_pct": 100.0,
    }


class TestCompareCardEscaping:
    """中危整改：对比卡周标签必须经 esc() 转义。"""

    def test_malicious_script_tag_escaped(self):
        html = build_compare_card(_make_pc("<script>alert(1)</script>"))
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_malicious_img_onerror_escaped(self):
        html = build_compare_card(_make_pc('"><img src=x onerror=alert(1)>'))
        assert "<img" not in html  # 不再构成真实标签

    def test_normal_week_label_intact(self):
        html = build_compare_card(_make_pc("2026-W36"))
        assert "2026-W36" in html

    def test_diagnose_collapses_malformed_date(self):
        """正常链路兜底：非法日期折叠为「未知周」，不透传原始值。"""
        tasks = [
            {"date": "<script>x</script>", "type": "周报生成",
             "baseline_tokens": 1000, "skill_tokens": 500,
             "baseline_minutes": 10, "skill_minutes": 2},
            {"date": "2026-09-01", "type": "周报生成",
             "baseline_tokens": 1000, "skill_tokens": 500,
             "baseline_minutes": 10, "skill_minutes": 2},
        ]
        diag = report_engine.diagnose(tasks)
        html = generate_html_report(diag)
        assert "<script>x</script>" not in html


class TestNoOnlineRemnants:
    """低危整改：联网推荐残留清除，与 network.outbound=false 声明一致。"""

    def test_recommend_skills_rejects_online_flag(self):
        with pytest.raises(TypeError):
            recommend_skills([], total_tasks=0, use_online_search=True)

    def test_report_engine_no_online_arg(self):
        src = (SCRIPTS / "report_engine.py").read_text(encoding="utf-8")
        assert "--online" not in src
        assert "use_online_search" not in src

    def test_skill_recommender_no_online_clients(self):
        src = (SCRIPTS / "skill_recommender.py").read_text(encoding="utf-8")
        assert "skillhub_client" not in src
        assert "clawhub_client" not in src
        assert "use_online_search" not in src


class TestUnverifiedDisclosure:
    """低危整改：第三方推荐明确标注「未经本技能实测验证」。"""

    @staticmethod
    def _by_type():
        return [{"task_type": "代码开发", "baseline_tokens": 50000,
                 "skill_tokens": 30000, "count": 5}]

    def test_md_contains_unverified_note(self):
        recs = recommend_skills(self._by_type(), total_tasks=5)
        assert recs
        assert "未经本技能实测验证" in format_recommendations_md(recs)

    def test_html_contains_unverified_note(self):
        recs = recommend_skills(self._by_type(), total_tasks=5)
        assert "未经本技能实测验证" in format_recommendations_html(recs)

    def test_html_report_end_to_end(self):
        tasks = [
            {"date": "2026-09-01", "type": "周报生成",
             "baseline_tokens": 12000, "skill_tokens": 3000,
             "baseline_minutes": 25, "skill_minutes": 3},
            {"date": "2026-08-25", "type": "周报生成",
             "baseline_tokens": 11000, "skill_tokens": 3200,
             "baseline_minutes": 24, "skill_minutes": 4},
        ]
        html = generate_html_report(report_engine.diagnose(tasks))
        assert "未经本技能实测验证" in html
        assert "skillhub_client" not in html


class TestDocsNoExecutableDownloadCommands:
    """信息整改：发行文档不得包含可复制执行的远程下载/管道命令形态。"""

    @pytest.mark.parametrize("doc", ["CHANGELOG.md", "SKILL.md", "QUICKSTART.md", "README.md"])
    def test_no_pipe_download_patterns(self, doc):
        p = ROOT / doc
        if not p.is_file():
            pytest.skip(f"{doc} 不存在")
        text = p.read_text(encoding="utf-8")
        assert "curl |" not in text
        assert "| bash" not in text
        assert "wget |" not in text
