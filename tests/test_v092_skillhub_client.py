#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_v092_skillhub_client.py — SkillHub 联网搜索测试（v0.9.2）"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestSkillHubClient:
    """SkillHub 客户端测试套件。"""

    def test_search_returns_list(self):
        from skillhub_client import search_skills
        resp = search_skills("省token", limit=5)
        assert hasattr(resp, "skills")
        assert hasattr(resp, "total")
        assert resp.total >= 0

    def test_search_result_structure(self):
        from skillhub_client import SearchResponse
        assert hasattr(SearchResponse, "skills")
        assert hasattr(SearchResponse, "total")
        assert hasattr(SearchResponse, "query")

    def test_format_install_warning_contains_skill_name(self):
        from skillhub_client import SkillInfo, format_install_warning
        skill = SkillInfo(
            slug="test-skill",
            name="Test Skill",
            description_zh="测试技能",
            stars=10,
            installs=5,
            homepage="https://example.com",
            tags=["test"]
        )
        result = format_install_warning(skill, "npx skills add test-skill")
        assert "Test Skill" in result
        assert "npx skills add test-skill" in result
        assert "⚠️" in result
