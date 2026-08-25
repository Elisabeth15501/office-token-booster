#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_v094_gate.py — v1.0.0 质量门禁回归测试（P0/P1/P2）

固化 office-token-booster_代码对抗式审查.md 中三条交付硬阻塞的修复：
- P0：缺省 baseline 写回污染账本（run_long_chain 写回护栏）
- P1：确认词吞记账句（classify 记账优先 + 强确认词收窄）
- P2：HTML 注入（report_engine / skill_recommender 用户字段转义 + URL 协议校验）

全维度打标，便于 Allure 按 test_type=gate / risk_area / component 筛选。
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest
import allure

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagnose import load_ledger, diagnose
from conversation import classify
from ledger_agent import run_long_chain
from report_engine import generate_html_report
from skill_recommender import SkillRecommendation, format_recommendations_html

from helpers import attach_text


def _write_ledger(tasks):
    p = Path(tempfile.mkdtemp()) / "ledger.json"
    p.write_text(json.dumps({"tasks": tasks}, ensure_ascii=False), encoding="utf-8")
    return str(p)


# ─────────────────────────────────────────────────────────────
# P0：缺省 baseline 写回护栏
# ─────────────────────────────────────────────────────────────
@allure.title("P0：新类型缺 baseline 写回被拦截，账本不被污染")
@allure.severity(allure.severity_level.CRITICAL)
@allure.label("test_type", "gate")
@allure.label("risk_area", "data_integrity")
@allure.label("component", "ledger_agent")
@pytest.mark.gate
def test_p0_baseline_missing_blocks_writeback():
    ledger = _write_ledger([])  # 空账本 → 新类型无历史
    res = run_long_chain(ledger, "文档撰写", apply=True,
                         skill_tokens=1800, skill_minutes=5)
    with allure.step("断言写回被拦截且账本不变"):
        attach_text(res, "run_long_chain result")
        assert res.get("blocked") is True, "缺 baseline 的新类型写回应被拦截"
        assert res["applied"] is False
        # 账本文件未被污染
        after = load_ledger(ledger)
        assert len(after) == 0, "被拦截后账本应保持为空，不出现 baseline=0 脏记录"


@allure.title("P0：用户显式 baseline=0 允许写回（不误伤）")
@allure.severity(allure.severity_level.NORMAL)
@allure.label("test_type", "gate")
@allure.label("risk_area", "data_integrity")
@allure.label("component", "ledger_agent")
@pytest.mark.gate
def test_p0_explicit_zero_baseline_allowed():
    ledger = _write_ledger([])
    res = run_long_chain(ledger, "文档撰写", apply=True,
                         skill_tokens=1800, skill_minutes=5,
                         baseline_tokens=0, baseline_minutes=0)
    with allure.step("断言显式 0 仍能写回"):
        attach_text(res, "run_long_chain result")
        assert res.get("blocked") is not True, "用户显式 baseline=0 不应被拦截"
        assert res["applied"] is True


# ─────────────────────────────────────────────────────────────
# P1：确认词不再吞记账句
# ─────────────────────────────────────────────────────────────
@allure.title("P1：『好的，记一笔…』归 record 而非 confirm")
@allure.severity(allure.severity_level.CRITICAL)
@allure.label("test_type", "gate")
@allure.label("risk_area", "intent_misjudge")
@allure.label("component", "conversation")
@pytest.mark.gate
def test_p1_confirm_word_not_swallow_record():
    with allure.step("句首语气词 + 记账词 → record"):
        assert classify("好的，记一笔周报生成 花了1800 token 5分钟") == "record"
        assert classify("可以，记一笔会议纪要 花了900 token") == "record"
    with allure.step("纯强确认词仍 → confirm"):
        assert classify("确认") == "confirm"
        assert classify("行") == "confirm"


# ─────────────────────────────────────────────────────────────
# P2：HTML 注入转义
# ─────────────────────────────────────────────────────────────
@allure.title("P2：恶意 task_type 进 HTML 被转义")
@allure.severity(allure.severity_level.CRITICAL)
@allure.label("test_type", "gate")
@allure.label("risk_area", "xss")
@allure.label("component", "report_engine")
@pytest.mark.gate
def test_p2_html_escape_task_type():
    payload = "<script>alert(1)</script>"
    ledger = _write_ledger([{
        "date": "2026-08-20", "type": payload,
        "baseline_tokens": 12000, "skill_tokens": 3000,
        "baseline_minutes": 25, "skill_minutes": 3,
    }])
    html = generate_html_report(diagnose(load_ledger(ledger)))
    with allure.step("断言原始标签不出现、转义后出现"):
        attach_text(html[:2000], "html head")
        assert "<script>alert(1)</script>" not in html, "原始注入标签不应出现在 HTML 中"
        assert "&lt;script&gt;" in html, "用户字段应被 html.escape 转义"


@allure.title("P2：联网推荐 skill 名/URL 被转义且非 http(s) 不渲染链接")
@allure.severity(allure.severity_level.CRITICAL)
@allure.label("test_type", "gate")
@allure.label("risk_area", "xss")
@allure.label("component", "skill_recommender")
@pytest.mark.gate
def test_p2_skill_recommendation_escape_and_url_scheme():
    rec = SkillRecommendation(
        skill="<img src=x onerror=alert(1)>",
        reason="正常理由",
        install_cmd="skillhub install foo",
        expected_saving="省 10%",
        priority="HIGH",
        evidence_url="javascript:alert(1)",  # 危险协议
    )
    html = format_recommendations_html([rec])
    with allure.step("断言注入被转义、危险协议不进 href"):
        attach_text(html, "skill rec html")
        assert "<img src=x" not in html, "skill 名原始标签不应出现"
        assert "&lt;img" in html, "skill 名应被转义"
        assert "javascript:alert(1)" not in html, "非 http(s) URL 不应渲染为链接"
