#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_p1_dirty_data.py — 质量门禁 P1 脏数据崩溃回归

锁定：账本数值字段为字符串（如 "5000"）、缺失或非数字时，
内核 diagnose() 与渲染层 report_engine 必须优雅归一（coerce 为 int），
不得触发 `TypeError: int + str`（原 P1 交付阻塞缺陷）。

运行：
  cd office-token-booster
  python -m pytest tests/test_p1_dirty_data.py -v
"""

import sys
from pathlib import Path

import pytest
import allure

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagnose import diagnose
from report_engine import generate_html_report, generate_html_summary
from helpers import src_link


# 脏数据账本：baseline_tokens 为字符串、skill_minutes 缺失、另一条 baseline_minutes 为非数字
DIRTY = [
    {"date": "2026-08-10", "type": "周报生成", "baseline_tokens": "5000",
     "skill_tokens": 1800, "baseline_minutes": 20, "skill_minutes": 5},
    {"date": "2026-08-11", "type": "会议纪要", "baseline_tokens": 8000,
     "skill_tokens": 3000, "baseline_minutes": "30", "skill_minutes": None},
    {"date": "2026-08-12", "type": "数据分析", "baseline_tokens": "abc",
     "skill_tokens": 2500, "baseline_minutes": 25, "skill_minutes": "garbage"},
]


@allure.feature("质量门禁 P1 脏数据")
@allure.story("内核归一化")
@allure.epic("office-token-booster")
@allure.label("layer", "内核层")
@allure.label("test_type", "对抗/边界")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "gate")
@src_link("scripts/diagnose.py", line=54, name="_normalize_tasks() 源码")
@allure.title("P1 脏数据：字符串/缺失/非数字字段不崩溃且数值正确")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("账本数值字段混入字符串/None/非数字时，diagnose 必须 coerce 为 int，不得 TypeError。")
def test_p1_dirty_data_diagnose_no_crash():
    """脏数据账本 → diagnose 不崩溃，且聚合数值正确。"""
    d = diagnose(DIRTY)
    with allure.step("断言不崩溃且总节省正确"):
        # 周报生成: (5000-1800)=3200；会议纪要: (8000-3000)=5000；数据分析: (0-2500)=-2500（"abc"→0）
        assert d.saved_tok == 3200 + 5000 - 2500, f"saved_tok 错误: {d.saved_tok}"
        assert d.saved_min == (20 - 5) + (30 - 0) + (25 - 0), f"saved_min 错误: {d.saved_min}"
    with allure.step("断言原始 task 数值已归一为 int（供渲染层安全消费）"):
        for t in d.tasks:
            assert isinstance(t["baseline_tokens"], int)
            assert isinstance(t["skill_tokens"], int)
            assert isinstance(t["baseline_minutes"], int)
            assert isinstance(t["skill_minutes"], int)


@allure.feature("质量门禁 P1 脏数据")
@allure.story("渲染层安全消费")
@allure.epic("office-token-booster")
@allure.label("layer", "渲染层")
@allure.label("test_type", "对抗/边界")
@allure.label("risk_area", "ui_rendering")
@allure.label("priority", "P1")
@allure.label("suite", "gate")
@src_link("scripts/report_engine.py", line=337, name="任务执行情况渲染 源码")
@allure.title("P1 脏数据：HTML 完整报告 + 摘要渲染不崩溃")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("report_engine 消费 s.tasks 时不得因残留字符串字段崩溃（bm-sm / bt-st）。")
def test_p1_dirty_data_report_render_no_crash():
    """脏数据 Diagnosis → HTML 全文报告与一页摘要均正常渲染。"""
    d = diagnose(DIRTY)
    full = generate_html_report(d)
    summary = generate_html_summary(d)
    with allure.step("断言两份报告均成功产出且含关键区块"):
        assert "<html" in full or "<!DOCTYPE" in full, "完整报告未渲染"
        assert "节省" in full, "完整报告缺少节省区块"
        assert "节省" in summary, "摘要缺少节省区块"
