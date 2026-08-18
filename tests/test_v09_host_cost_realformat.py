#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_v09_host_cost_realformat.py — 锁住「真实宿主 trace 格式」解析

实测发现 v0.9 初版 LocalProvider 读不懂本机真实 trace：
  - 真实 trace 藏在 traces/<session_id>/trace_<hash>.json（嵌套子目录），初版只 glob 顶层 → 0 条
  - 真实 token 字段在 trace.totalTokens，初版在顶层找 → 0
  - 真实日期字段是 trace.startedAt（ISO），初版键表无 → 退回今天
本测试用「嵌套子目录 + {trace:{...}} 结构」复刻真实格式，确保修复不回退。

运行：
  cd office-token-booster
  python -m pytest tests/test_v09_host_cost_realformat.py -v --alluredir=allure-results
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

from host_cost import LocalProvider, draft_entries_from_host, CostRecord
from ledger_agent import import_host_usage
from helpers import attach_text, src_link


def _make_real_wb_root(tmp):
    """复刻真实 ~/.workbuddy 形态：traces/<session_id>/trace_<hash>.json，含 trace 嵌套。"""
    traces_dir = Path(tmp) / "traces"
    sid = "2bb3ef57-38d3-423b-8272-f559f4fe679f"
    sess = traces_dir / sid
    sess.mkdir(parents=True, exist_ok=True)
    trace = {
        "trace": {
            "traceId": "trace_x",
            "name": "Agent workflow",
            "startedAt": "2026-08-15T04:33:23.448Z",
            "endedAt": "2026-08-15T04:36:21.121Z",
            "duration": 177673,                 # ms → 约 3 分钟
            "totalTokens": 3830904,
            "sessionId": sid,
            "modelInfo": {"models": ["hy3"]},
            "agentName": "cli",
        },
        "spans": [],
    }
    (sess / "trace_x.json").write_text(json.dumps(trace, ensure_ascii=False), encoding="utf-8")
    return Path(tmp)


@allure.feature("v0.9 真实宿主用量接入")
@allure.story("真实 trace 嵌套格式解析")
@allure.epic("office-token-booster")
@allure.label("layer", "宿主适配层")
@allure.label("test_type", "正向")
@allure.label("component", "host_cost")
@allure.label("risk_area", "real_closed_loop")
@allure.label("priority", "P0")
@allure.label("suite", "v0.9")
@src_link("scripts/host_cost.py", line=200, name="LocalProvider.fetch_recent 源码")
@allure.title("v0.9 真实格式：嵌套子目录 + trace.totalTokens + startedAt 解析")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("复刻本机真实 trace 结构，确保 provider 递归子目录、读 trace.totalTokens/startedAt/duration。")
@pytest.mark.smoke
def test_v09_real_nested_trace_format():
    root = _make_real_wb_root(tempfile.mkdtemp())
    recs = LocalProvider(root=root).fetch_recent(7)
    with allure.step("断言真实嵌套结构被正确解析"):
        attach_text(recs, "real-format records")
        assert len(recs) == 1
        r = recs[0]
        assert r.skill_tokens == 3830904, "应读 trace.totalTokens"
        assert r.date == "2026-08-15", "应读 trace.startedAt 的日期部分"
        assert r.model == "hy3", "应读 trace.modelInfo.models[0]"
        assert r.skill_minutes == 3, "duration(ms) 应折算为约 3 分钟"
        assert r.session_id == "2bb3ef57-38d3-423b-8272-f559f4fe679f"
        assert r.source == "local_traces"


@allure.feature("v0.9 真实宿主用量接入")
@allure.story("baseline_ratio 假设估算")
@allure.epic("office-token-booster")
@allure.label("layer", "写回层")
@allure.label("test_type", "正向")
@allure.label("component", "host_cost")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9")
@src_link("scripts/host_cost.py", line=250, name="draft_entries_from_host 源码")
@allure.title("v0.9 baseline_ratio：按 skill_tokens*ratio 估算 baseline")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 --baseline-ratio 把 baseline 设为实测的倍数（假设性），便于先看提效报告。")
@pytest.mark.smoke
def test_v09_draft_entries_baseline_ratio():
    rec = CostRecord(date="2026-08-15", skill_tokens=1000, skill_minutes=5,
                     task_type="AI办公任务", source="local_traces")
    entries = draft_entries_from_host(_FakeProvider(rec), days=7, baseline_ratio=3.0)
    with allure.step("断言 baseline = skill*ratio"):
        attach_text(entries, "draft entries (ratio=3)")
        assert entries[0]["baseline_tokens"] == 3000
        assert entries[0]["skill_tokens"] == 1000
        assert entries[0]["baseline_minutes"] == 15


@allure.feature("v0.9 真实宿主用量接入")
@allure.story("真实格式 + dry-run 导入")
@allure.epic("office-token-booster")
@allure.label("layer", "写回层")
@allure.label("test_type", "正向")
@allure.label("component", "ledger_agent")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9")
@src_link("scripts/ledger_agent.py", line=216, name="import_host_usage 源码")
@allure.title("v0.9 import_host_usage：真实格式 provider dry-run 不写盘")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("用真实格式 provider 跑 import_host_usage，确认读得到数据且 dry-run 不写盘。")
@pytest.mark.smoke
def test_v09_import_realformat_dryrun():
    ledger = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"tasks": []}, ledger)
    ledger.close()
    try:
        provider = LocalProvider(root=_make_real_wb_root(tempfile.mkdtemp()))
        res = import_host_usage(ledger.name, days=7, provider=provider, apply=False,
                                baseline_ratio=3.0)
        with allure.step("断言真实格式可读且 dry-run 安全"):
            attach_text(res, "import result (real format)")
            assert res["count"] == 1
            assert res["applied"] is False
            assert res["entries"][0]["skill_tokens"] == 3830904
            assert res["entries"][0]["baseline_tokens"] == 3830904 * 3
            on_disk = json.load(open(ledger.name, encoding="utf-8"))
            assert on_disk["tasks"] == [], "dry-run 不应写盘"
    finally:
        os.unlink(ledger.name)


class _FakeProvider:
    """测试用假提供方（duck-typed HostCostProvider）。"""

    def __init__(self, record):
        self._record = record

    def fetch_recent(self, days=1):
        return [self._record]


if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    _report_dir = str(_root / "allure-results")
    print(f"Allure 数据 → {_report_dir}")
    sys.exit(pytest.main([__file__, "-v", f"--alluredir={_report_dir}"]))
