#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_v097_execute.py — Phase 3 execute 意图路由测试"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from conversation import classify, handle  # noqa: E402


@pytest.fixture
def empty_ledger():
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"tasks": []}, tmp, ensure_ascii=False)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.mark.smoke
def test_classify_execute():
    assert classify("帮我写周报：这周做了A") == "execute"
    assert classify("做个PPT大纲：主题") == "execute"
    assert classify("帮我分析csv") == "execute"


def test_execute_generates_deliverable(empty_ledger):
    st = {}
    r = handle(empty_ledger, "帮我写周报：完成需求评审；风险：联调延期；下周计划：上线", st)
    assert "# 周报" in r
    assert st.get("pending", {}).get("type") == "周报生成"


def test_execute_no_cost_blocks_writeback(empty_ledger):
    """execute 后无成本确认，不应写回账本（防全0污染）。"""
    st = {}
    handle(empty_ledger, "帮我写周报：完成需求评审", st)
    handle(empty_ledger, "确认", st)
    n = len(json.load(open(empty_ledger, encoding="utf-8"))["tasks"])
    assert n == 0, "无成本确认不应写回账本"


def test_execute_with_baseline_writes(empty_ledger):
    """execute 后补 baseline 确认，应写回账本。"""
    st = {}
    handle(empty_ledger, "帮我写周报：完成需求评审", st)
    handle(empty_ledger, "确认 baseline 12000 token 25分钟", st)
    n = len(json.load(open(empty_ledger, encoding="utf-8"))["tasks"])
    assert n == 1, "补 baseline 后应写回"


def test_execute_baseline_minutes_not_misrouted(empty_ledger):
    """回归：Bug #1 修复——紧凑写法『baseline 12000 token 25分钟』的分钟须归 baseline，
    而非被误判为 skill 分钟写入。"""
    st = {}
    handle(empty_ledger, "帮我写周报：完成需求评审", st)
    handle(empty_ledger, "确认 baseline 12000 token 25分钟", st)
    tasks = json.load(open(empty_ledger, encoding="utf-8"))["tasks"]
    assert len(tasks) == 1
    t = tasks[0]
    assert t["baseline_tokens"] == 12000, "baseline token 应归 baseline"
    assert t["baseline_minutes"] == 25, "bug#1: 分钟须归 baseline_minutes"
    assert t["skill_tokens"] == 0, "baseline 优先级下 skill 不应写入"
    assert t["skill_minutes"] == 0, "bug#1: 分钟不应错归 skill_minutes"


def test_execute_csv_routes_data(empty_ledger):
    r = handle(empty_ledger, "帮我分析csv\nname,score\nA,10\nB,20", {})
    assert "数据分析" in r


def test_execute_ppt_not_misrouted_by_bookkeeping_word(empty_ledger):
    """含「记账」词的内容不应把 execute 误判为 record。"""
    st = {}
    r = handle(empty_ledger, "做个PPT大纲：AI提效助手\n方案：执行+记账一体", st)
    assert "# 幻灯片大纲" in r
    assert st.get("pending", {}).get("type") == "PPT大纲"
