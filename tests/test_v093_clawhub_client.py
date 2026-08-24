#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_v093_clawhub_client.py — ClawHub 联网搜索测试（v0.9.3）"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestClawHubClient:
    """ClawHub 客户端测试套件。"""

    def test_search_returns_list(self):
        from clawhub_client import search_clawhub
        resp = search_clawhub("省token", limit=5)
        assert hasattr(resp, "skills")
        assert hasattr(resp, "total")
        assert resp.total >= 0

    def test_search_result_structure(self):
        from clawhub_client import ClawHubSkill, ClawHubSearchResponse
        # 创建实例来检查字段
        skill = ClawHubSkill(
            slug="test", name="Test", summary="", owner="test", stars=0, installs=0, tags=[]
        )
        assert hasattr(skill, "slug")
        assert hasattr(skill, "name")
        resp = ClawHubSearchResponse(skills=[], total=0, query="test")
        assert hasattr(resp, "skills")

    def test_format_install_warning_contains_skill_name(self):
        from clawhub_client import ClawHubSkill, format_clawhub_install_warning
        skill = ClawHubSkill(
            slug="test-skill",
            name="Test Skill",
            summary="测试技能",
            owner="testuser",
            stars=10,
            installs=5,
            tags=["test"]
        )
        result = format_clawhub_install_warning(skill)
        assert "Test Skill" in result
        assert "clawhub add" in result
        assert "⚠️" in result
