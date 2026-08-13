#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_v08.py — office-token-booster v0.8 实地测试脚本

验证 v0.8 提效洞察可视化：
  1. 内核周期对比（本期 vs 上期）：多周 → direction/delta/pct 正确；单周 → None（优雅降级）
  2. 自动化 ROI 评分：roi_targets 按 roi_score 降序；月度外推 = 累计×(30/跨度天)
  3. 趋势折线图（零依赖 SVG）：多周渲染 <svg>/polyline/周标签；空数据返回 ""
  4. 报告渲染：完整报告 + 一页摘要均含 chart-line / cmp-card / roi-card
  5. 追问意图：新增「本期 vs 上期」可答；数据不足时给出友好提示
  6. 长链路 Agent：propose_automation_targets 改为按 ROI 降序（与内核同源，不重复造轮子）

运行（pytest + Allure）：
  cd office-token-booster
  python -m pytest tests/test_v08.py -v --alluredir=allure-results
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
import allure

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagnose import diagnose, compute_period_compare, compute_roi_targets
from report_engine import (
    generate_html_report, generate_html_summary,
    build_trend_line_chart, build_compare_card, build_roi_card,
)
from qa import answer_followup
from ledger_agent import propose_automation_targets
from helpers import attach_text, attach_ledger, src_link


# 跨 4 个自然周的样本（每周 1 条，便于验证周期对比与趋势）
SAMPLE = {
    "tasks": [
        {"date": "2026-07-20", "type": "周报生成", "baseline_tokens": 5000, "skill_tokens": 1800,
         "baseline_minutes": 20, "skill_minutes": 5, "note": "周报"},
        {"date": "2026-07-27", "type": "文档撰写", "baseline_tokens": 8000, "skill_tokens": 3000,
         "baseline_minutes": 30, "skill_minutes": 12, "note": "方案"},
        {"date": "2026-08-03", "type": "数据分析", "baseline_tokens": 6000, "skill_tokens": 2500,
         "baseline_minutes": 25, "skill_minutes": 10, "note": "报表"},
        {"date": "2026-08-10", "type": "代码编写", "baseline_tokens": 7000, "skill_tokens": 3200,
         "baseline_minutes": 40, "skill_minutes": 15, "note": "脚本"},
    ]
}

# 单周样本（用于验证周期对比降级为 None）
SAMPLE_ONE_WEEK = {
    "tasks": [
        {"date": "2026-08-10", "type": "周报生成", "baseline_tokens": 5000, "skill_tokens": 1800,
         "baseline_minutes": 20, "skill_minutes": 5},
    ]
}


@pytest.fixture
def ledger():
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(SAMPLE, tmp, ensure_ascii=False)
    tmp.close()
    path = tmp.name
    yield path
    os.unlink(path)


@pytest.fixture
def ledger_one_week():
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(SAMPLE_ONE_WEEK, tmp, ensure_ascii=False)
    tmp.close()
    path = tmp.name
    yield path
    os.unlink(path)


@allure.feature("v0.8 提效洞察可视化")
@allure.story("周期对比（本期 vs 上期）")
@allure.epic("office-token-booster")
@allure.label("layer", "内核层")
@allure.label("test_type", "正向")
@allure.label("component", "diagnose")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "v0.8")
@src_link("scripts/diagnose.py", line=78, name="compute_period_compare() 源码")
@allure.title("v0.8 周期对比：多周 → direction/delta/pct 正确")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("验证 diagnose 对跨周账本能算出本期 vs 上期的方向/增量/百分比。")
@pytest.mark.smoke
def test_v08_period_compare_multiweek(ledger):
    """多周账本 → period_compare 含正确的方向/增量/百分比。"""
    d = diagnose(json.load(open(ledger, encoding="utf-8"))["tasks"])
    pc = d.period_compare
    with allure.step("断言 period_compare 非空且字段完整"):
        attach_text(pc, "period_compare")
        assert pc is not None, "多周账本应产生 period_compare"
        assert pc["current_week"] == "2026-W33", f"当前周错误: {pc['current_week']}"
        assert pc["previous_week"] == "2026-W32", f"上一周错误: {pc['previous_week']}"
        assert pc["direction"] == "up", f"方向错误: {pc['direction']}"
        # 本期(代码编写 3800) - 上期(数据分析 3500) = 300
        assert pc["saved_tokens_delta"] == 300, f"delta 错误: {pc['saved_tokens_delta']}"
        assert abs(pc["saved_tokens_pct"] - 8.5714) < 0.01, f"pct 错误: {pc['saved_tokens_pct']}"


@allure.feature("v0.8 提效洞察可视化")
@allure.story("周期对比（本期 vs 上期）")
@allure.epic("office-token-booster")
@allure.label("layer", "内核层")
@allure.label("test_type", "边界")
@allure.label("component", "diagnose")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P2")
@allure.label("suite", "v0.8")
@src_link("scripts/diagnose.py", line=78, name="compute_period_compare() 源码")
@allure.title("v0.8 周期对比：单周 → 优雅降级为 None")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证数据不足两周时 period_compare 为 None（不崩溃、不误报）。")
@pytest.mark.regression
def test_v08_period_compare_single_week(ledger_one_week):
    """单周账本 → period_compare 应为 None（优雅降级）。"""
    d = diagnose(json.load(open(ledger_one_week, encoding="utf-8"))["tasks"])
    with allure.step("断言 period_compare 为 None"):
        attach_text(d.period_compare, "period_compare")
        assert d.period_compare is None, f"单周不应有 period_compare: {d.period_compare}"


@allure.feature("v0.8 提效洞察可视化")
@allure.story("自动化 ROI 评分")
@allure.epic("office-token-booster")
@allure.label("layer", "内核层")
@allure.label("test_type", "正向")
@allure.label("component", "diagnose")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "v0.8")
@src_link("scripts/diagnose.py", line=113, name="compute_roi_targets() 源码")
@allure.title("v0.8 ROI 评分：降序 + 月度外推正确")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("验证 roi_targets 按 roi_score 降序，且月度节省 = 累计×(30/跨度天)。")
@pytest.mark.smoke
def test_v08_roi_targets_ranking(ledger):
    """roi_targets 按 roi_score 降序，月度外推符合公式。"""
    d = diagnose(json.load(open(ledger, encoding="utf-8"))["tasks"])
    with allure.step("断言按 roi_score 降序"):
        attach_text(d.roi_targets, "roi_targets")
        scores = [t["roi_score"] for t in d.roi_targets]
        assert scores == sorted(scores, reverse=True), f"未按 ROI 降序: {scores}"
    with allure.step("断言月度外推 = 累计 × (30 / 跨度天)"):
        # 跨度 22 天；文档撰写 累计省 5000 → 月度 ≈ 5000×(30/22)=6818.18
        doc = next(t for t in d.roi_targets if t["task_type"] == "文档撰写")
        assert doc["monthly_saved_tokens"] == 6818, f"月度外推错误: {doc['monthly_saved_tokens']}"
        assert doc["effort_hours"] == 4, "接入成本启发式应为 4 人时"
    with allure.step("断言 ROI 头名与月度头名一致（文档撰写）"):
        assert d.roi_targets[0]["task_type"] == "文档撰写", f"ROI 头名错误: {d.roi_targets[0]}"


@allure.feature("v0.8 提效洞察可视化")
@allure.story("趋势折线图（SVG）")
@allure.epic("office-token-booster")
@allure.label("layer", "渲染层")
@allure.label("test_type", "正向")
@allure.label("component", "report_engine")
@allure.label("risk_area", "ui_rendering")
@allure.label("priority", "P1")
@allure.label("suite", "v0.8")
@src_link("scripts/report_engine.py", line=147, name="build_trend_line_chart() 源码")
@allure.title("v0.8 趋势折线图：多周渲染 SVG + 周标签")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 build_trend_line_chart 生成含 polyline 与周标签的内联 SVG。")
@pytest.mark.smoke
def test_v08_trend_line_chart():
    """多周 → SVG 含 polyline 与周标签；空数据 → 空串。"""
    weeks = [
        {"week": "2026-W32", "saved_tokens": 100},
        {"week": "2026-W33", "saved_tokens": 250},
        {"week": "2026-W34", "saved_tokens": 180},
    ]
    svg = build_trend_line_chart(weeks)
    with allure.step("断言 SVG 结构与周标签"):
        attach_text(svg[:400], "trend svg (head)")
        assert "<svg" in svg and "<polyline" in svg, "趋势图缺少 svg/polyline"
        assert "W32" in svg and "W33" in svg and "W34" in svg, "趋势图缺少周标签"
    with allure.step("边界：空数据返回空串"):
        assert build_trend_line_chart([]) == "", "空数据应返回空串"


@allure.feature("v0.8 提效洞察可视化")
@allure.story("报告渲染（chart/cmp/roi）")
@allure.epic("office-token-booster")
@allure.label("layer", "渲染层")
@allure.label("test_type", "正向")
@allure.label("component", "report_engine")
@allure.label("risk_area", "ui_rendering")
@allure.label("priority", "P1")
@allure.label("suite", "v0.8")
@src_link("scripts/report_engine.py", line=293, name="generate_html_report() 源码")
@allure.title("v0.8 报告渲染：完整报告 + 摘要含趋势/对比/ROI 卡片")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("验证完整与摘要 HTML 均渲染出 chart-line / cmp-card / roi-card。")
@pytest.mark.smoke
def test_v08_report_renders_insight_cards(ledger):
    """完整报告与一页摘要都应含三大洞察卡片。"""
    d = diagnose(json.load(open(ledger, encoding="utf-8"))["tasks"])
    full = generate_html_report(d)
    summary = generate_html_summary(d)
    with allure.step("完整报告含三大卡片"):
        attach_text(
            f"chart-line={'chart-line' in full} cmp-card={'cmp-card' in full} roi-card={'roi-card' in full}",
            "完整报告卡片检查")
        assert "chart-line" in full and "cmp-card" in full and "roi-card" in full
    with allure.step("一页摘要含三大卡片"):
        assert "chart-line" in summary and "cmp-card" in summary and "roi-card" in summary


@allure.feature("v0.8 提效洞察可视化")
@allure.story("追问意图（本期 vs 上期）")
@allure.epic("office-token-booster")
@allure.label("layer", "追问层")
@allure.label("test_type", "正向")
@allure.label("component", "qa")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P2")
@allure.label("suite", "v0.8")
@src_link("scripts/qa.py", line=147, name="answer_followup() 源码")
@allure.title("v0.8 追问：『这周比上周』可答本期 vs 上期")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证新增的『本期 vs 上期』追问意图返回方向箭头与对比数字；数据不足时友好提示。")
@pytest.mark.regression
def test_v08_qa_period_compare(ledger):
    """『这周比上周』→ 返回本期 vs 上期对比文案。"""
    d = diagnose(json.load(open(ledger, encoding="utf-8"))["tasks"])
    ans = answer_followup(d, "这周比上周怎么样")
    with allure.step("断言返回本期 vs 上期对比"):
        attach_text(ans, "qa 答：本期 vs 上期")
        assert "本期" in ans and "上期" in ans, f"未返回周期对比: {ans}"
        assert "▲" in ans or "▼" in ans or "▬" in ans, f"缺少方向箭头: {ans}"


@allure.feature("v0.8 提效洞察可视化")
@allure.story("追问意图（本期 vs 上期）")
@allure.epic("office-token-booster")
@allure.label("layer", "追问层")
@allure.label("test_type", "边界")
@allure.label("component", "qa")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P3")
@allure.label("suite", "v0.8")
@src_link("scripts/qa.py", line=147, name="answer_followup() 源码")
@allure.title("v0.8 追问：单周数据 → 友好提示而非崩溃")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证账本周数据不足时，『本期 vs 上期』给出友好提示而非异常。")
@pytest.mark.regression
def test_v08_qa_period_compare_insufficient(ledger_one_week):
    """单周 → 『本期 vs 上期』返回数据不足提示。"""
    d = diagnose(json.load(open(ledger_one_week, encoding="utf-8"))["tasks"])
    ans = answer_followup(d, "这周比上周怎么样")
    with allure.step("断言返回数据不足提示"):
        attach_text(ans, "qa 答（单周）")
        assert "周数据不足" in ans, f"应提示数据不足: {ans}"


@allure.feature("v0.8 提效洞察可视化")
@allure.story("Agent 自动化建议（ROI 同源）")
@allure.epic("office-token-booster")
@allure.label("layer", "写回层")
@allure.label("test_type", "正向")
@allure.label("component", "ledger_agent")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P2")
@allure.label("suite", "v0.8")
@src_link("scripts/ledger_agent.py", line=112, name="propose_automation_targets() 源码")
@allure.title("v0.8 Agent：自动化建议按 ROI 降序（与内核同源）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 propose_automation_targets 改为复用内核 roi_targets，按 ROI 降序，头名为文档撰写。")
@pytest.mark.regression
def test_v08_agent_roi_targets(ledger):
    """Agent 的自动化建议头名 = ROI 头名（文档撰写），且文本含 ROI。"""
    d = diagnose(json.load(open(ledger, encoding="utf-8"))["tasks"])
    lines = propose_automation_targets(d)
    with allure.step("断言建议头部与 ROI 头名一致且含 ROI"):
        attach_text(lines, "自动化建议")
        assert lines and "文档撰写" in lines[0], f"建议头名错误: {lines}"
        assert any("ROI" in ln for ln in lines), "建议文本应含 ROI 评分"


if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    _report_dir = str(_root / "allure-results")
    print(f"Allure 数据 → {_report_dir}")
    sys.exit(pytest.main([__file__, "-v", f"--alluredir={_report_dir}"]))
