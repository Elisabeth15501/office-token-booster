#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_v09_qa_consumption.py — qa.py 追问语义坑回归测试（v0.9）

修复点：追问「哪个任务 Token 消耗最多」曾错误路由到「节省最多」分支
（saved_tokens 最高），因为「最多」关键词命中了 savings 分支。
本文件用一份刻意让两种最大值错位的账本，证明：
  - 「消耗最多 / 用量最多 / 消耗最高」→ 锚定 skill_tokens（实际消耗），返回 consumption 类型
  - 「节省最多 / 省最多」→ 仍锚定 saved_tokens（节省），返回 savings 类型
两种意图严格区分，互不串味。

运行：
  cd office-token-booster
  python -m pytest tests/test_v09_qa_consumption.py -v --alluredir=allure-results
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

from diagnose import diagnose
from qa import answer_followup
from helpers import attach_text, src_link


# 刻意设计：让「实耗最高」与「节省最高」是不同类型，验证二者不会串味。
#   会议纪要：baseline 21000 / skill 5500  → 实耗 5500，节省 15500（节省最高）
#   周报生成：baseline 5000  / skill 8000  → 实耗 8000（实耗最高），节省 -3000
#   数据分析：baseline 3000  / skill 2000  → 实耗 2000，节省 1000
SAMPLE = {
    "tasks": [
        {"date": "2026-08-08", "type": "会议纪要", "baseline_tokens": 21000, "skill_tokens": 5500,
         "baseline_minutes": 60, "skill_minutes": 15, "note": "会议"},
        {"date": "2026-08-09", "type": "周报生成", "baseline_tokens": 5000, "skill_tokens": 8000,
         "baseline_minutes": 25, "skill_minutes": 30, "note": "周报"},
        {"date": "2026-08-10", "type": "数据分析", "baseline_tokens": 3000, "skill_tokens": 2000,
         "baseline_minutes": 20, "skill_minutes": 8, "note": "报表"},
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


def _diag(ledger):
    return diagnose(json.load(open(ledger, encoding="utf-8"))["tasks"])


@allure.feature("v0.9 追问语义修正")
@allure.story("「消耗最多」≠「节省最多」")
@allure.epic("office-token-booster")
@allure.label("layer", "追问层")
@allure.label("test_type", "正向")
@allure.label("component", "qa")
@allure.label("risk_area", "intent_routing")
@allure.label("priority", "P0")
@src_link("scripts/qa.py", line=39, name="answer_followup() 源码")
@allure.title("追问『哪个任务Token消耗最多』→ 返回实耗最高的『周报生成』而非节省最高的『会议纪要』")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.regression
def test_qa_consume_most_routes_to_skill_tokens(ledger):
    """核心回归：消耗意图必须锚定 skill_tokens，不能落到 saved_tokens 分支。"""
    d = _diag(ledger)
    ans = answer_followup(d, "请问我哪个任务Token消耗最多？")
    with allure.step("断言命中实耗最高的类型『周报生成』（skill_tokens=8000）"):
        attach_text(ans, "qa 答：Token 消耗最多")
        assert "周报生成" in ans, f"消耗最多应返回『周报生成』，实际: {ans}"
        assert "消耗" in ans, f"答文应体现『消耗』语义，实际: {ans}"
    with allure.step("断言未错误返回节省最高的『会议纪要』"):
        # 会议纪要 是 saved_tokens 最高（15500），若串味会返回它
        assert "会议纪要" not in ans, f"消耗最多不应返回节省最高的『会议纪要』: {ans}"


@allure.feature("v0.9 追问语义修正")
@allure.story("「消耗最多」≠「节省最多」")
@allure.epic("office-token-booster")
@allure.label("layer", "追问层")
@allure.label("test_type", "正向")
@allure.label("component", "qa")
@allure.label("risk_area", "intent_routing")
@allure.label("priority", "P1")
@src_link("scripts/qa.py", line=39, name="answer_followup() 源码")
@allure.title("追问『哪个任务消耗最高 / 用量最多』 → 同样返回实耗最高『周报生成』")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.regression
@pytest.mark.parametrize("q", [
    "哪个任务类型消耗最高？",
    "哪种任务Token用量最多？",
    "哪个任务占用的Token最多？",
])
def test_qa_consume_synonyms_route_to_skill_tokens(ledger, q):
    """消耗的同义表述（最高/用量最多/占用最多）都应锚定 skill_tokens。"""
    d = _diag(ledger)
    ans = answer_followup(d, q)
    with allure.step(f"断言『{q}』返回实耗最高『周报生成』"):
        attach_text(ans, f"qa 答：{q}")
        assert "周报生成" in ans, f"消耗同义问法应返回『周报生成』，实际: {ans}"
        assert "会议纪要" not in ans, f"不应串味到节省最高『会议纪要』: {ans}"


@allure.feature("v0.9 追问语义修正")
@allure.story("「消耗最多」≠「节省最多」")
@allure.epic("office-token-booster")
@allure.label("layer", "追问层")
@allure.label("test_type", "正向")
@allure.label("component", "qa")
@allure.label("risk_area", "intent_routing")
@allure.label("priority", "P1")
@src_link("scripts/qa.py", line=39, name="answer_followup() 源码")
@allure.title("追问『哪个任务节省最多』 → 仍返回节省最高『会议纪要』（不串味到消耗）")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.regression
def test_qa_save_most_still_routes_to_saved_tokens(ledger):
    """反向守卫：显式问『节省最多』必须仍走 saved_tokens 分支。"""
    d = _diag(ledger)
    ans = answer_followup(d, "哪个任务类型节省最多？")
    with allure.step("断言命中节省最高的类型『会议纪要』（saved_tokens=15500）"):
        attach_text(ans, "qa 答：节省最多")
        assert "会议纪要" in ans, f"节省最多应返回『会议纪要』，实际: {ans}"
        assert "节省" in ans, f"答文应体现『节省』语义，实际: {ans}"


@allure.feature("v0.9 追问语义修正")
@allure.story("「消耗最多」≠「节省最多」")
@allure.epic("office-token-booster")
@allure.label("layer", "追问层")
@allure.label("test_type", "边界")
@allure.label("component", "qa")
@allure.label("risk_area", "intent_routing")
@allure.label("priority", "P2")
@src_link("scripts/qa.py", line=39, name="answer_followup() 源码")
@allure.title("『消耗又节省』混合表述 → 优先按『节省』解析，不串味")
@allure.severity(allure.severity_level.MINOR)
@pytest.mark.regression
def test_qa_mixed_consume_save_resolves_to_save(ledger):
    """若问法同时含『消耗』与『节省』（如『消耗和节省最多的是哪个』），
    应优先按显式『节省』意图走 saved_tokens 分支，避免误判为纯消耗。"""
    d = _diag(ledger)
    ans = answer_followup(d, "消耗最多和节省最多的任务分别是哪个？")
    with allure.step("断言混合问法中『节省』部分命中『会议纪要』"):
        attach_text(ans, "qa 答：混合问法")
        # 该问法含『节省』关键词，应至少出现节省最高的类型，而非纯消耗串味
        assert "会议纪要" in ans, f"混合问法应识别『节省』意图返回『会议纪要』: {ans}"
