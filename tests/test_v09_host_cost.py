#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_v09_host_cost.py — office-token-booster v0.9 真实宿主用量接入

验证 v0.9「接真实宿主 cost」且防屎山：
  1. EventCostProvider：包装 event["cost"] 为可单测记录；无 cost 返回空
  2. WorkBuddyLocalProvider：只读本机 traces → 真实 CostRecord；
     容忍 JSONL / 缺字段跳过 / 超窗过滤；无数据返回空（不崩）
  3. draft_entries_from_host：草稿 skill 取实测值、baseline 默认 0
  4. 触发流 enrichment：event 无 cost + 提供 provider → 自动补全 cost_source
  5. 向后兼容：cost_provider=None 时行为完全不变
  6. import_host_usage：dry-run 返回草稿且不写盘；无记录返回友好提示

运行（pytest + Allure）：
  cd office-token-booster
  python -m pytest tests/test_v09_host_cost.py -v --alluredir=allure-results
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
import allure

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from host_cost import (
    CostRecord, EventCostProvider, WorkBuddyLocalProvider, draft_entries_from_host,
)
from skill_bridge import on_conversation_event
from ledger_agent import import_host_usage
from helpers import attach_text, src_link


class _FakeProvider:
    """测试用假提供方（duck-typed HostCostProvider）。"""

    def __init__(self, records):
        self._records = records

    def fetch_recent(self, days=1):
        return self._records


def _make_wb_root(tmp, traces):
    """在 tmp 下造一个 ~/.workbuddy 形态的根（traces/ 子目录 + 文件）。"""
    traces_dir = Path(tmp) / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    for name, content in traces.items():
        (traces_dir / name).write_text(content, encoding="utf-8")
    return Path(tmp)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ─────────────────────────────────────────────────────────────
# 1. EventCostProvider
# ─────────────────────────────────────────────────────────────

@allure.feature("v0.9 真实宿主用量接入")
@allure.story("事件成本提供方")
@allure.epic("office-token-booster")
@allure.label("layer", "宿主适配层")
@allure.label("test_type", "正向")
@allure.label("component", "host_cost")
@allure.label("risk_area", "real_closed_loop")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9")
@src_link("scripts/host_cost.py", line=95, name="EventCostProvider 源码")
@allure.title("v0.9 EventCostProvider：包装 event['cost'] 为记录")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 EventCostProvider 把事件里的 skill_tokens/minutes 转成 CostRecord。")
@pytest.mark.smoke
def test_v09_event_cost_provider():
    """event 带 cost → 返回记录；无 cost → 空。"""
    p = EventCostProvider({"text": "x", "cost": {"skill_tokens": 1800, "skill_minutes": 5}})
    recs = p.fetch_recent(1)
    with allure.step("断言记录含实测值"):
        attach_text(recs, "event records")
        assert len(recs) == 1
        assert recs[0].skill_tokens == 1800 and recs[0].skill_minutes == 5
        assert recs[0].source == "event"
    empty = EventCostProvider({"text": "x"}).fetch_recent(1)
    assert empty == [], "无 cost 应返回空列表"


# ─────────────────────────────────────────────────────────────
# 2. WorkBuddyLocalProvider — 读取 + 容忍 + 降级
# ─────────────────────────────────────────────────────────────

@allure.feature("v0.9 真实宿主用量接入")
@allure.story("WorkBuddy 本地用量读取")
@allure.epic("office-token-booster")
@allure.label("layer", "宿主适配层")
@allure.label("test_type", "正向")
@allure.label("component", "host_cost")
@allure.label("risk_area", "real_closed_loop")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9")
@src_link("scripts/host_cost.py", line=150, name="WorkBuddyLocalProvider.fetch_recent 源码")
@allure.title("v0.9 WorkBuddyLocalProvider：读取 traces 真实用量")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("验证只读本机 traces 能解析出真实 CostRecord（token/日期/来源）。")
@pytest.mark.smoke
def test_v09_workbuddy_provider_reads_traces():
    """temp 根下造一条合法 trace → 返回含实测 token 的记录。"""
    today = _today()
    root = _make_wb_root(
        tempfile.mkdtemp(),
        {"s1.json": json.dumps({
            "session_id": "s1", "effective_tokens": 5000,
            "date": today, "model": "glm-5.2", "task_type": "周报生成",
        }, ensure_ascii=False)},
    )
    recs = WorkBuddyLocalProvider(root=root).fetch_recent(7)
    with allure.step("断言记录字段正确"):
        attach_text(recs, "wb records")
        assert len(recs) == 1
        r = recs[0]
        assert r.skill_tokens == 5000
        assert r.date == today
        assert r.model == "glm-5.2"
        assert r.task_type == "周报生成"
        assert r.source == "workbuddy_traces"


@allure.feature("v0.9 真实宿主用量接入")
@allure.story("WorkBuddy 本地用量读取（容忍/降级）")
@allure.epic("office-token-booster")
@allure.label("layer", "宿主适配层")
@allure.label("test_type", "边界")
@allure.label("component", "host_cost")
@allure.label("risk_area", "real_closed_loop")
@allure.label("priority", "P2")
@allure.label("suite", "v0.9")
@src_link("scripts/host_cost.py", line=150, name="WorkBuddyLocalProvider.fetch_recent 源码")
@allure.title("v0.9 容忍 JSONL / 缺字段跳过 / 超窗过滤")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证脏数据跳过、超时间窗过滤、JSONL 兼容，且不抛异常。")
@pytest.mark.regression
def test_v09_workbuddy_provider_tolerant_and_window():
    today = _today()
    old = "2000-01-01"
    root = _make_wb_root(
        tempfile.mkdtemp(),
        {
            # 合法 JSONL：第一行有效、第二行垃圾、第三行无 token（应跳过）
            "mix.jsonl": "\n".join([
                json.dumps({"total_tokens": 3000, "date": today, "task_type": "文档撰写"}),
                "this is not json at all",
                json.dumps({"date": today, "model": "x"}),  # 无 token → 跳过
            ]),
            # 超窗（极旧日期）→ 过滤掉
            "old.json": json.dumps({"effective_tokens": 9999, "date": old}),
        },
    )
    recs = WorkBuddyLocalProvider(root=root).fetch_recent(7)
    with allure.step("断言只留窗口内、有 token 的记录"):
        attach_text(recs, "wb records (filtered)")
        assert len(recs) == 1, f"应仅 1 条（窗口内+有token）: {recs}"
        assert recs[0].skill_tokens == 3000
        assert recs[0].task_type == "文档撰写"


@allure.feature("v0.9 真实宿主用量接入")
@allure.story("WorkBuddy 本地用量读取（无数据降级）")
@allure.epic("office-token-booster")
@allure.label("layer", "宿主适配层")
@allure.label("test_type", "边界")
@allure.label("component", "host_cost")
@allure.label("risk_area", "real_closed_loop")
@allure.label("priority", "P2")
@allure.label("suite", "v0.9")
@src_link("scripts/host_cost.py", line=150, name="WorkBuddyLocalProvider.fetch_recent 源码")
@allure.title("v0.9 无 traces 目录 → 返回空（不崩）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证根下无 traces 时返回空列表，不抛异常（防屎山降级）。")
@pytest.mark.regression
def test_v09_workbuddy_provider_no_data():
    root = Path(tempfile.mkdtemp())  # 空根，无 traces
    recs = WorkBuddyLocalProvider(root=root).fetch_recent(7)
    assert recs == [], "无数据应返回空列表"


# ─────────────────────────────────────────────────────────────
# 3. draft_entries_from_host
# ─────────────────────────────────────────────────────────────

@allure.feature("v0.9 真实宿主用量接入")
@allure.story("真实用量 → 账本草稿")
@allure.epic("office-token-booster")
@allure.label("layer", "写回层")
@allure.label("test_type", "正向")
@allure.label("component", "host_cost")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9")
@src_link("scripts/host_cost.py", line=183, name="draft_entries_from_host 源码")
@allure.title("v0.9 草稿：skill 取实测值，baseline 默认 0")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证草稿 entry 的 skill_tokens 来自宿主实测，baseline 默认 0 待补。")
@pytest.mark.smoke
def test_v09_draft_entries_from_host():
    rec = CostRecord(date=_today(), skill_tokens=4200, skill_minutes=9,
                     task_type="周报生成", source="workbuddy_traces")
    entries = draft_entries_from_host(_FakeProvider([rec]), days=7)
    with allure.step("断言草稿字段"):
        attach_text(entries, "draft entries")
        assert len(entries) == 1
        e = entries[0]
        assert e["skill_tokens"] == 4200 and e["skill_minutes"] == 9
        assert e["baseline_tokens"] == 0, "baseline 默认 0 待补"
        assert e["type"] == "周报生成"


# ─────────────────────────────────────────────────────────────
# 4. 触发流 enrichment（skill_bridge）
# ─────────────────────────────────────────────────────────────

@allure.feature("v0.9 真实宿主用量接入")
@allure.story("触发流成本补全")
@allure.epic("office-token-booster")
@allure.label("layer", "触发层")
@allure.label("test_type", "正向")
@allure.label("component", "skill_bridge")
@allure.label("risk_area", "cost_accuracy")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9")
@src_link("scripts/skill_bridge.py", line=151, name="on_conversation_event 源码")
@allure.title("v0.9 触发流：event 无 cost + provider → 自动补全实测成本")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("验证事件未带 cost 但提供 provider 时，触发流用宿主实测值补全并标注来源。")
@pytest.mark.smoke
def test_v09_bridge_enrichment():
    provider = _FakeProvider([CostRecord(date=_today(), skill_tokens=777,
                                         skill_minutes=3, task_type="周报生成")])
    ledger = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"tasks": []}, ledger)
    ledger.close()
    try:
        res = on_conversation_event(ledger.name, {"text": "我刚生成了周报"}, {},
                                    cost_provider=provider)
        with allure.step("断言成本被补全且来源为实测"):
            attach_text(res, "bridge result")
            assert res.triggered is True
            assert res.cost_source in ("event", "mixed"), f"来源应为实测: {res.cost_source}"
            assert "777" in res.suggestion, "建议应含补全的实测 token"
    finally:
        os.unlink(ledger.name)


@allure.feature("v0.9 真实宿主用量接入")
@allure.story("触发流向后兼容")
@allure.epic("office-token-booster")
@allure.label("layer", "触发层")
@allure.label("test_type", "回归")
@allure.label("component", "skill_bridge")
@allure.label("risk_area", "cost_accuracy")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9")
@src_link("scripts/skill_bridge.py", line=151, name="on_conversation_event 源码")
@allure.title("v0.9 向后兼容：cost_provider=None 时行为不变")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("验证不传 provider 时，触发流完全保持 v0.7 行为，无副作用。")
@pytest.mark.regression
def test_v09_bridge_no_provider_unchanged():
    ledger = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"tasks": []}, ledger)
    ledger.close()
    try:
        # 无 cost、无 provider：应走原 medium 信心 passthrough（不触发接管）
        res = on_conversation_event(ledger.name, {"text": "我刚生成了周报"}, {},
                                    cost_provider=None)
        with allure.step("断言未补全成本（保持原行为）"):
            attach_text(res, "bridge result (no provider)")
            assert res.cost_source in ("none", "text"), f"不应补全: {res.cost_source}"
    finally:
        os.unlink(ledger.name)


# ─────────────────────────────────────────────────────────────
# 5. import_host_usage（dry-run / 空）
# ─────────────────────────────────────────────────────────────

@allure.feature("v0.9 真实宿主用量接入")
@allure.story("真实用量导入账本（dry-run）")
@allure.epic("office-token-booster")
@allure.label("layer", "写回层")
@allure.label("test_type", "正向")
@allure.label("component", "ledger_agent")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9")
@src_link("scripts/ledger_agent.py", line=200, name="import_host_usage 源码")
@allure.title("v0.9 import_host_usage：dry-run 返回草稿且不写盘")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 import_host_usage 默认 dry-run：返回草稿、applied=False、不改动账本文件。")
@pytest.mark.smoke
def test_v09_import_host_usage_dryrun():
    ledger = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"tasks": []}, ledger)
    ledger.close()
    try:
        provider = _FakeProvider([CostRecord(date=_today(), skill_tokens=1234,
                                             skill_minutes=4, task_type="周报生成")])
        res = import_host_usage(ledger.name, days=7, provider=provider, apply=False)
        with allure.step("断言 dry-run 行为"):
            attach_text(res, "import result")
            assert res["applied"] is False
            assert res["count"] == 1
            assert res["entries"][0]["skill_tokens"] == 1234
            # 不写盘：账本文件仍是空 tasks
            on_disk = json.load(open(ledger.name, encoding="utf-8"))
            assert on_disk["tasks"] == [], "dry-run 不应写盘"
    finally:
        os.unlink(ledger.name)


@allure.feature("v0.9 真实宿主用量接入")
@allure.story("真实用量导入账本（无记录）")
@allure.epic("office-token-booster")
@allure.label("layer", "写回层")
@allure.label("test_type", "边界")
@allure.label("component", "ledger_agent")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P3")
@allure.label("suite", "v0.9")
@src_link("scripts/ledger_agent.py", line=200, name="import_host_usage 源码")
@allure.title("v0.9 import_host_usage：无记录 → 友好提示")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 provider 无记录时返回 count=0 与友好提示，不报错。")
@pytest.mark.regression
def test_v09_import_host_usage_empty():
    ledger = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"tasks": []}, ledger)
    ledger.close()
    try:
        res = import_host_usage(ledger.name, days=7, provider=_FakeProvider([]), apply=False)
        with allure.step("断言空记录友好处理"):
            attach_text(res, "import result (empty)")
            assert res["count"] == 0
            assert res["note"], "应给出提示文案"
    finally:
        os.unlink(ledger.name)


if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    _report_dir = str(_root / "allure-results")
    print(f"Allure 数据 → {_report_dir}")
    sys.exit(pytest.main([__file__, "-v", f"--alluredir={_report_dir}"]))
