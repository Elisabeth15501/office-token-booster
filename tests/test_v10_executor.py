# -*- coding: utf-8 -*-
"""v1.0.0 方向 B：执行引擎回归测试。

守卫点：
- 5 个执行模块都能产出结构化 Markdown 交付物
- 数据分析模块真·本地计算指标（不联网）
- 执行后自动记账闭环复用 run_long_chain 护栏（缺省 baseline 写回被拦截，不污染账本）
- 用户内容进 HTML 经 html.escape（防 XSS 注入，守住安全红线）

全维度打标（layer/test_type/component/risk_area/priority/suite）。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import allure
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from executor import (  # noqa: E402
    execute,
    resolve_exec_type,
    propose_ledger,
    _md_to_html,
    analyze_csv,
)

pytestmark = [
    pytest.mark.layer("execution"),
    pytest.mark.test_type("integration"),
    pytest.mark.component("executor"),
    pytest.mark.suite("v1.0.0-direction-b"),
    pytest.mark.risk_area("execution-safety"),
    pytest.mark.priority("p0"),
]


# --------------------------------------------------------------------------
# 任务类型归一
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：类型归一覆盖 5 个模块 + 未知类型返回 None")
@allure.severity(allure.severity_level.CRITICAL)
def test_resolve_exec_type_coverage():
    for alias in ["周报", "周报生成", "weekly", "纪要", "会议纪要", "数据分析", "文档整理", "要点提炼", "PPT大纲", "slides"]:
        assert resolve_exec_type(alias) is not None, f"未识别别名：{alias}"
    assert resolve_exec_type("完全不相关的任务xyz") is None


# --------------------------------------------------------------------------
# 周报生成
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：周报生成渲染出概览/重点/风险/下周结构")
@allure.severity(allure.severity_level.CRITICAL)
def test_weekly_report_structure():
    md, meta = execute("周报生成",
                       "本周概览：推进执行引擎\n完成executor骨架\n风险：测试覆盖不足\n下周计划：补回归测试")
    with allure.step("断言结构化分节"):
        assert "# 周报" in md
        assert "## 本周概览" in md
        assert "## 重点工作" in md
        assert "## 风险与阻塞" in md
        assert "## 下周计划" in md
        assert meta["task_type"] == "周报生成"


# --------------------------------------------------------------------------
# 会议纪要
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：会议纪要抽取结论/待办（含负责人+截止）/遗留")
@allure.severity(allure.severity_level.CRITICAL)
def test_meeting_minutes_extract_action_items():
    md, _ = execute("会议纪要",
                    "参会：张三李四\n结论：方向B通过\n待办：@张三 截止2026-09-10 写测试\n遗留：PPT模块待定")
    with allure.step("断言关键分节与待办解析"):
        assert "# 会议纪要" in md
        assert "## 核心结论" in md
        assert "## 待办事项" in md
        assert "@张三" in md and "2026-09-10" in md, "应解析出负责人与截止日期"
        assert "## 遗留问题" in md


# --------------------------------------------------------------------------
# 数据分析（CSV 本地计算）
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：数据分析本地计算数值指标（不联网）")
@allure.severity(allure.severity_level.CRITICAL)
def test_csv_analysis_computes_metrics():
    md, _ = execute("数据分析", "name,score\nA,10\nB,20\nC,30")
    with allure.step("断言指标表含求和/均值/中位数"):
        assert "# 数据分析报告" in md
        assert "score" in md
        assert "60.00" in md, "求和 10+20+30=60"
        assert "20.00" in md, "均值 20"
        assert "20.00" in md, "中位数 20"


# --------------------------------------------------------------------------
# 文档整理 / 要点提炼
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：文档整理产出大纲+核心要点+一句话总结")
@allure.severity(allure.severity_level.NORMAL)
def test_doc_summary_outline():
    md, _ = execute("文档整理",
                    "# 标题一\n这是第一段关于执行引擎设计的内容。\n# 标题二\n第二段讲安全红线与零依赖。")
    with allure.step("断言三段结构"):
        assert "# 要点提炼" in md
        assert "## 文档大纲" in md
        assert "## 核心要点" in md
        assert "## 一句话总结" in md


# --------------------------------------------------------------------------
# PPT 大纲
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：PPT 大纲生成 5 页结构")
@allure.severity(allure.severity_level.NORMAL)
def test_ppt_outline():
    md, _ = execute("PPT大纲", "办公室AI提效助手\n要点一：又做又记\n要点二：零依赖")
    with allure.step("断言幻灯片分页"):
        assert "# 幻灯片大纲" in md
        assert "Slide 1" in md and "Slide 5" in md


# --------------------------------------------------------------------------
# 自动记账闭环（复用 run_long_chain 护栏）
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：自动记账——缺省 baseline 写回被护栏拦截")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("执行完一笔任务后自动记账：未提供 baseline 时应用写回应被 blocked，不污染账本。")
def test_auto_ledger_blocks_missing_baseline():
    ledger = Path(tempfile.mkdtemp()) / "ledger.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    # 应用写回（apply=True）但缺 baseline → 应被拦截
    res = propose_ledger(str(ledger), "周报生成", skill_tokens=1800, apply=True)
    with allure.step("断言 blocked 且不写盘"):
        assert res is not None
        assert res.get("blocked") is True, "缺省 baseline 写回应被拦截"
        assert "block_reason" in res
        # 账本未被污染
        assert json.load(open(ledger, encoding="utf-8"))["tasks"] == []


@allure.title("v1.0 执行引擎：自动记账——dry-run 预览不写盘且保留 skill 成本")
@allure.severity(allure.severity_level.NORMAL)
def test_auto_ledger_dryrun_preview():
    ledger = Path(tempfile.mkdtemp()) / "ledger.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    res = propose_ledger(str(ledger), "会议纪要", skill_tokens=2500, apply=False)
    with allure.step("断言预览模式不写盘但记录成本"):
        assert res is not None
        assert res.get("applied") is False
        assert res["entry"]["skill_tokens"] == 2500
        assert json.load(open(ledger, encoding="utf-8"))["tasks"] == []


# --------------------------------------------------------------------------
# HTML 转义（安全红线）
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：用户内容进 HTML 经 html.escape 防 XSS")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("会议纪要/周报等用户字段若含 <script>，必须转义，不得原样进 HTML。")
def test_html_escape_user_content():
    malicious = '<script>alert("xss")</script>'
    md = f"# 会议纪要\n- {malicious}\n- 正常内容"
    html_out = _md_to_html(md, "测试")
    with allure.step("断言脚本被转义"):
        assert "<script>" not in html_out, "原始 script 标签不得出现在 HTML 输出"
        assert "&lt;script&gt;" in html_out, "应转义为实体"
        assert "正常内容" in html_out
