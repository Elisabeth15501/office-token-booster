#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_portability_cross_agent.py — 证明 office-token-booster 可在「任意 Agent 主机」上使用

背景：本 skill 将提交联想天禧 AI Skill 比赛。天禧平台尚未发布、格式未知，因此
「可移植性」是必须证明的硬指标。本测试套件证明：

  1. 唯一耦合点是 HostCostProvider 契约（fetch_recent -> list[CostRecord]）。
     任何主机只需实现这一个方法，core（diagnose/report）一行都不用改。
  2. 一个「非 WorkBuddy」的假 provider（模拟天禧）能完整跑通
     import → diagnose → report 闭环，证明核心与具体宿主解耦。
  3. 字段名容忍：_extract_tokens 识别 OpenAI/Claude 的 usage.{prompt,completion,total}
     等常见形态，故未知主机只要导出 JSON 即可被 GenericJsonProvider 读。
  4. 宿主无关的 GenericJsonProvider 真能读「第三方主机导出的用法文件」。
  5. 未知/不支持的主机（provider 返回 []）→ 优雅降级，不崩、不影响已有账本报告。
  6. 最强证明：即便 host_cost 模块根本无法导入（模拟一个没有任何适配层的主机），
     skill 的 core 仍能独立跑通——它从不依赖 host_cost。

运行：
  cd office-token-booster
  python -m pytest tests/test_portability_cross_agent.py -v --alluredir=allure-results
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import allure

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from host_cost import (
    CostRecord, HostCostProvider, LocalProvider, EventCostProvider,
    GenericJsonProvider, _extract_tokens, draft_entries_from_host,
)
from ledger_agent import import_host_usage
from helpers import attach_text, src_link

REPO_ROOT = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────
# 1. Provider 契约 = 唯一耦合点
# ─────────────────────────────────────────────────────────────

@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("Provider 契约是唯一耦合点")
@allure.epic("office-token-booster")
@allure.label("layer", "宿主适配层")
@allure.label("test_type", "契约")
@allure.label("component", "host_cost")
@allure.label("risk_area", "portability")
@allure.label("priority", "P0")
@allure.label("suite", "portability")
@src_link("scripts/host_cost.py", line=69, name="HostCostProvider 契约源码")
@allure.title("可移植性：最小 duck-typed provider 即满足 HostCostProvider")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("一个只实现 fetch_recent 的极简类即可 isinstance HostCostProvider，并流经 draft_entries_from_host。")
@pytest.mark.smoke
def test_port_contract_minimal_provider_satisfies_protocol():
    """第三主机只需实现 fetch_recent(days)->list[CostRecord]，无需继承任何基类。"""
    class MinimalProvider:  # 故意不继承、不 import 任何东西
        def fetch_recent(self, days=7):
            return [CostRecord(date="2026-08-15", skill_tokens=100, source="foreign")]

    p = MinimalProvider()
    with allure.step("断言满足运行时 Protocol 契约"):
        assert isinstance(p, HostCostProvider), "最小 provider 应满足 HostCostProvider"
    with allure.step("断言流经草稿生成（core 不感知具体主机）"):
        entries = draft_entries_from_host(p, days=7)
        attach_text(entries, "draft entries from minimal provider")
        assert entries[0]["skill_tokens"] == 100
        assert entries[0]["type"] == "AI办公任务", "未知主机未归类时应有默认类型"


@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("Provider 契约是唯一耦合点")
@allure.epic("office-token-booster")
@allure.label("layer", "宿主适配层")
@allure.label("test_type", "契约")
@allure.label("component", "host_cost")
@allure.label("risk_area", "portability")
@allure.label("priority", "P1")
@allure.label("suite", "portability")
@src_link("scripts/host_cost.py", line=69, name="HostCostProvider 契约源码")
@allure.title("可移植性：所有真实 provider 实现均满足契约")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("LocalProvider / EventCostProvider / GenericJsonProvider 都实现同一契约。")
@pytest.mark.smoke
def test_port_contract_all_real_providers_satisfy():
    assert isinstance(LocalProvider(), HostCostProvider)
    assert isinstance(EventCostProvider({}), HostCostProvider)
    assert isinstance(GenericJsonProvider(REPO_ROOT / "nonexistent.json"), HostCostProvider)


# ─────────────────────────────────────────────────────────────
# 2. 端到端跨 Agent 闭环（用「非 WorkBuddy」的假 provider 模拟天禧）
# ─────────────────────────────────────────────────────────────

class _TianxiLikeProvider:
    """模拟天禧 AI 的用量提供方：返回与 WorkBuddy 完全无关的字段/模型名，且不归类任务。"""
    def __init__(self, records):
        self._records = records

    def fetch_recent(self, days=7):
        return self._records


@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("端到端跨主机闭环")
@allure.epic("office-token-booster")
@allure.label("layer", "core")
@allure.label("test_type", "正向")
@allure.label("component", "diagnose+report")
@allure.label("risk_area", "portability")
@allure.label("priority", "P0")
@allure.label("suite", "portability")
@src_link("scripts/ledger_agent.py", line=200, name="import_host_usage 源码")
@allure.title("可移植性：非 WorkBuddy provider 完整跑通 import→diagnose→report")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("用模拟天禧的 provider（未知模型名、task_type=None）导入、诊断、出报告，证明核心与具体宿主解耦。")
@pytest.mark.smoke
def test_port_cross_agent_closed_loop():
    ledger = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"tasks": []}, ledger)
    ledger.close()
    try:
        provider = _TianxiLikeProvider([
            CostRecord(date="2026-08-15", skill_tokens=2830000, skill_minutes=120,
                       model="tianxi-gpt-x", task_type=None, source="tianxi"),
            CostRecord(date="2026-08-16", skill_tokens=1500000, skill_minutes=80,
                       model="tianxi-gpt-x", task_type=None, source="tianxi"),
        ])
        res = import_host_usage(ledger.name, days=7, provider=provider,
                                apply=True, baseline_ratio=3.0)
        with allure.step("断言导入写盘且来源为未知主机"):
            attach_text(res, "cross-agent import result")
            assert res["applied"] is True
            assert res["count"] == 2
            on_disk = json.load(open(ledger.name, encoding="utf-8"))
            assert len(on_disk["tasks"]) == 2
            assert on_disk["tasks"][0]["note"] == "宿主实测(tianxi)"
            assert on_disk["tasks"][0]["model"] == "tianxi-gpt-x"

        # 端到端：跑真实 report_engine CLI（最贴近用户用法）
        out = subprocess.run(
            [sys.executable, "scripts/report_engine.py", ledger.name, "--summary"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60,
        )
        with allure.step("断言报告生成成功（core 不感知天禧）"):
            attach_text(out.stdout + "\n" + out.stderr, "report summary (cross-agent)")
            assert out.returncode == 0, f"report 失败: {out.stderr}"
            # 报告应出现节省相关结论（baseline_ratio=3 → 约 66.7%）
            assert "66.7" in out.stdout or "节省" in out.stdout, "报告应展示提效结论"
    finally:
        os.unlink(ledger.name)


# ─────────────────────────────────────────────────────────────
# 3. 字段名容忍（不同主机的 token 字段差异）
# ─────────────────────────────────────────────────────────────

@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("字段名容忍（OpenAI/Claude 风格）")
@allure.epic("office-token-booster")
@allure.label("layer", "宿主适配层")
@allure.label("test_type", "正向")
@allure.label("component", "host_cost")
@allure.label("risk_area", "portability")
@allure.label("priority", "P1")
@allure.label("suite", "portability")
@src_link("scripts/host_cost.py", line=137, name="_extract_tokens 源码")
@allure.title("可移植性：识别 OpenAI/Claude 的 usage.{prompt,completion,total}_tokens")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("未知主机若按主流 LLM API 形态导出 usage，抽取器应能识别 token 与耗时。")
@pytest.mark.smoke
def test_port_schema_tolerance_openai_usage():
    # OpenAI / Claude 典型：usage 嵌套 + prompt/completion/total
    rec = {"usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
           "model": "gpt-5"}
    tok, mins = _extract_tokens(rec)
    with allure.step("断言 prompt+completion=total 被正确抽取"):
        attach_text({"tok": tok, "mins": mins}, "extracted (openai usage)")
        assert tok == 1500, "应识别 usage.total_tokens"
    # 仅给 prompt+completion、无 total 也应求和
    rec2 = {"usage": {"prompt_tokens": 1000, "completion_tokens": 500}}
    assert _extract_tokens(rec2)[0] == 1500, "无 total 时应 prompt+completion"


@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("字段名容忍（多键兜底）")
@allure.epic("office-token-booster")
@allure.label("layer", "宿主适配层")
@allure.label("test_type", "正向")
@allure.label("component", "host_cost")
@allure.label("risk_area", "portability")
@allure.label("priority", "P2")
@allure.label("suite", "portability")
@src_link("scripts/host_cost.py", line=137, name="_extract_tokens 源码")
@allure.title("可移植性：多键兜底识别 totalTokens / token_usage / 耗时")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("即使主机用不同字段名（totalTokens、token_usage 字典、duration 毫秒）也能解析。")
@pytest.mark.regression
def test_port_schema_tolerance_alternate_keys():
    assert _extract_tokens({"totalTokens": 800})[0] == 800
    assert _extract_tokens({"token_usage": {"total_tokens": 900}})[0] == 900
    assert _extract_tokens({"token_usage": {"prompt_tokens": 300, "completion_tokens": 200}})[0] == 500
    # 耗时：duration 毫秒 → 分钟
    tok, mins = _extract_tokens({"total_tokens": 100, "duration": 180000})
    assert mins == 3, "180000ms 应折算为 3 分钟"


# ─────────────────────────────────────────────────────────────
# 4. 宿主无关的 GenericJsonProvider（第三方主机导出文件）
# ─────────────────────────────────────────────────────────────

@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("GenericJsonProvider 即插即用")
@allure.epic("office-token-booster")
@allure.label("layer", "宿主适配层")
@allure.label("test_type", "正向")
@allure.label("component", "host_cost")
@allure.label("risk_area", "portability")
@allure.label("priority", "P1")
@allure.label("suite", "portability")
@src_link("scripts/host_cost.py", line=258, name="GenericJsonProvider 源码")
@allure.title("可移植性：GenericJsonProvider 读取第三方主机导出的用法 JSON")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("第三主机只要导出 JSON/JSONL，GenericJsonProvider 即可解析为 CostRecord，无需专属代码。")
@pytest.mark.smoke
def test_port_generic_json_provider(tmp_path):
    export = tmp_path / "foreign_usage.json"
    # 模拟天禧导出的用法文件（混合字段形态：usage 嵌套 + 扁平 totalTokens）
    export.write_text(json.dumps([
        {"usage": {"prompt_tokens": 1000, "completion_tokens": 500},
         "model": "tianxi-gpt-x", "startedAt": "2026-08-15T10:00:00Z"},
        {"totalTokens": 2000, "model": "tianxi-gpt-x", "startedAt": "2026-08-16T10:00:00Z"},
    ], ensure_ascii=False), encoding="utf-8")
    recs = GenericJsonProvider(export).fetch_recent(7)
    with allure.step("断言第三方导出被正确解析"):
        attach_text(recs, "generic json records")
        assert len(recs) == 2
        assert recs[0].skill_tokens == 1500
        assert recs[1].skill_tokens == 2000
        assert all(r.source == "generic_json" for r in recs)


@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("GenericJsonProvider 即插即用")
@allure.epic("office-token-booster")
@allure.label("layer", "宿主适配层")
@allure.label("test_type", "边界")
@allure.label("component", "host_cost")
@allure.label("risk_area", "portability")
@allure.label("priority", "P3")
@allure.label("suite", "portability")
@src_link("scripts/host_cost.py", line=258, name="GenericJsonProvider 源码")
@allure.title("可移植性：文件不存在 / 无 token → 返回空（不崩）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("未知主机尚未导出用法文件时，GenericJsonProvider 优雅返回空。")
@pytest.mark.regression
def test_port_generic_json_provider_empty(tmp_path):
    missing = tmp_path / "nope.json"
    assert GenericJsonProvider(missing).fetch_recent(7) == []
    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    assert GenericJsonProvider(empty).fetch_recent(7) == []


# ─────────────────────────────────────────────────────────────
# 5. 未知/不支持的主机 → 优雅降级
# ─────────────────────────────────────────────────────────────

@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("未知主机优雅降级")
@allure.epic("office-token-booster")
@allure.label("layer", "写回层")
@allure.label("test_type", "边界")
@allure.label("component", "ledger_agent")
@allure.label("risk_area", "portability")
@allure.label("priority", "P1")
@allure.label("suite", "portability")
@src_link("scripts/ledger_agent.py", line=200, name="import_host_usage 源码")
@allure.title("可移植性：provider 返回 []（未知主机）不崩且友好提示")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("当主机格式未知、无记录时，导入返回 count=0 + 提示，不影响已有账本报告。")
@pytest.mark.regression
def test_port_graceful_degradation_unknown_host():
    ledger = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"tasks": [{"date": "2026-08-10", "type": "周报生成",
                          "baseline_tokens": 3000, "skill_tokens": 1000}]}, ledger)
    ledger.close()
    try:
        res = import_host_usage(ledger.name, days=7, provider=_TianxiLikeProvider([]),
                                apply=True, baseline_ratio=3.0)
        with allure.step("断言未知主机下安全降级"):
            attach_text(res, "import result (unknown host)")
            assert res["count"] == 0
            assert res["applied"] is False
            assert res["note"], "应给出友好提示而非异常"
            # 已有账本未被破坏
            on_disk = json.load(open(ledger.name, encoding="utf-8"))
            assert len(on_disk["tasks"]) == 1
    finally:
        os.unlink(ledger.name)


# ─────────────────────────────────────────────────────────────
# 6. 最强证明：host_cost 完全不可导入时，core 仍能独立跑通
# ─────────────────────────────────────────────────────────────

@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("core 与 host_cost 零耦合")
@allure.epic("office-token-booster")
@allure.label("layer", "core")
@allure.label("test_type", "契约")
@allure.label("component", "diagnose+report")
@allure.label("risk_area", "portability")
@allure.label("priority", "P0")
@allure.label("suite", "portability")
@allure.title("可移植性：host_cost 不可导入时 core 仍独立可用")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("通过 meta_path 拦截 host_cost 的导入（模拟一个没有任何适配层的主机），"
                    "验证 diagnose/report 核心从不依赖 host_cost，因此可在任意主机上运行。")
@pytest.mark.smoke
def test_port_core_independent_of_host_cost():
    ledger_json = json.dumps({"tasks": [
        {"date": "2026-08-15", "type": "周报生成",
         "baseline_tokens": 3000, "skill_tokens": 1000,
         "baseline_minutes": 30, "skill_minutes": 10},
    ]})
    # 在子进程里刻意让 host_cost 无法导入，模拟「未知主机平台无适配层」。
    scripts_dir = str(REPO_ROOT / "scripts")
    code = (
        "import sys, json, os, tempfile\n"
        f"sys.path.insert(0, {scripts_dir!r})\n"
        "class _Blocker:\n"
        "    def find_module(self, name, path=None):\n"
        "        return self if (name == 'host_cost' or name.startswith('host_cost.')) else None\n"
        "    def load_module(self, name):\n"
        "        raise ImportError('host_cost blocked (simulated unknown host): ' + name)\n"
        "sys.meta_path.insert(0, _Blocker())\n"
        "import diagnose, report_engine\n"          # 仅依赖 diagnose，绝不依赖 host_cost
        "from ledger_agent import load_ledger\n"     # ledger_agent 顶层只 import diagnose
        "p = None\n"
        "import tempfile, os\n"
        "f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')\n"
        "f.write('''" + ledger_json.replace("'", "\\'") + "''')\n"
        "f.close()\n"
        "d = diagnose.diagnose(load_ledger(f.name))\n"
        "print('SAVED_TOK', d.saved_tok)\n"
        "os.unlink(f.name)\n"
        "print('CORE_OK host_cost_never_imported')\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=str(REPO_ROOT),
                         capture_output=True, text=True, timeout=60)
    with allure.step("断言 core 在不依赖 host_cost 时跑通"):
        attach_text(out.stdout + "\n" + out.stderr, "core run (host_cost blocked)")
        assert out.returncode == 0, f"core 应可独立运行: {out.stderr}"
        assert "CORE_OK host_cost_never_imported" in out.stdout
        assert "SAVED_TOK" in out.stdout


# ─────────────────────────────────────────────────────────────
# 7. 宿主重复导入去重（真实缺口修复）
# ─────────────────────────────────────────────────────────────

@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("宿主重复导入去重")
@allure.epic("office-token-booster")
@allure.label("layer", "写回层")
@allure.label("test_type", "边界")
@allure.label("component", "ledger_agent")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "portability")
@src_link("scripts/ledger_agent.py", line=216, name="import_host_usage 源码")
@allure.title("可移植性：宿主重复导入按 session_id 去重，账本不膨胀")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("同一 provider 重复 apply 时，已存在的 session_id 被跳过，账本不追加重复会话；"
                    "无 session_id 的用户自记条目不受影响。")
@pytest.mark.regression
def test_port_dedup_by_session_id():
    ledger = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"tasks": []}, ledger)
    ledger.close()
    try:
        provider = _TianxiLikeProvider([
            CostRecord(date="2026-08-15", skill_tokens=100, session_id="sess-A", source="tianxi"),
            CostRecord(date="2026-08-16", skill_tokens=200, session_id="sess-B", source="tianxi"),
        ])
        # 第一次导入：应写回 2 条
        r1 = import_host_usage(ledger.name, days=7, provider=provider,
                               apply=True, baseline_ratio=3.0)
        with allure.step("断言首次导入写回 2 条"):
            attach_text(r1, "first import result")
            assert r1["count"] == 2
            assert r1["skipped_duplicates"] == 0
            on_disk = json.load(open(ledger.name, encoding="utf-8"))
            assert len(on_disk["tasks"]) == 2

        # 第二次重复导入：应全部去重，账本不膨胀
        r2 = import_host_usage(ledger.name, days=7, provider=provider,
                               apply=True, baseline_ratio=3.0)
        with allure.step("断言重复导入被去重，账本不膨胀"):
            attach_text(r2, "second import result (dedup)")
            assert r2["skipped_duplicates"] == 2
            assert r2["count"] == 0
            on_disk = json.load(open(ledger.name, encoding="utf-8"))
            assert len(on_disk["tasks"]) == 2, "不应重复追加"
            assert all(t.get("session_id") in ("sess-A", "sess-B") for t in on_disk["tasks"])

        # 第三次：新增一个不同 session_id → 应追加而非去重
        provider2 = _TianxiLikeProvider([
            CostRecord(date="2026-08-17", skill_tokens=300, session_id="sess-C", source="tianxi"),
        ])
        r3 = import_host_usage(ledger.name, days=7, provider=provider2,
                               apply=True, baseline_ratio=3.0)
        with allure.step("断言新 session_id 正常追加（不去重）"):
            attach_text(r3, "third import (new id)")
            assert r3["skipped_duplicates"] == 0
            assert r3["count"] == 1
            on_disk = json.load(open(ledger.name, encoding="utf-8"))
            assert len(on_disk["tasks"]) == 3
    finally:
        os.unlink(ledger.name)


@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("CLI --provider generic 开关")
@allure.epic("office-token-booster")
@allure.label("layer", "cli")
@allure.label("test_type", "集成")
@allure.label("component", "ledger_agent CLI")
@allure.label("risk_area", "portability")
@allure.label("priority", "P1")
@allure.label("suite", "portability")
@allure.title("CLI：--provider generic 读第三方用法文件并写回")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.smoke
def test_cli_provider_generic_imports(tmp_path):
    """正对天禧/OpenClaw：第三方主机只要导出 JSON，CLI --provider generic 即可零代码导入。"""
    export = tmp_path / "foreign_usage.json"
    export.write_text(json.dumps([
        {"totalTokens": 1200, "model": "tianxi-gpt-x", "startedAt": "2026-08-16T10:00:00Z", "type": "周报生成"},
        {"totalTokens": 3300, "model": "tianxi-gpt-x", "startedAt": "2026-08-17T11:00:00Z"},
    ], ensure_ascii=False), encoding="utf-8")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "ledger_agent.py"),
                        str(ledger), "--import-host", "--provider", "generic",
                        "--provider-arg", str(export), "--apply", "--baseline-ratio", "3"],
                       cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60,
                       encoding="utf-8")
    with allure.step("断言导入成功且写回 2 条"):
        attach_text(r.stdout + r.stderr, "cli generic import")
        assert r.returncode == 0, r.stderr
        tasks = json.load(open(ledger, encoding="utf-8"))["tasks"]
        assert len(tasks) == 2
        assert tasks[0].get("source") == "generic_json"


@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("CLI --provider generic 开关")
@allure.epic("office-token-booster")
@allure.label("layer", "cli")
@allure.label("test_type", "契约")
@allure.label("component", "ledger_agent CLI")
@allure.label("risk_area", "portability")
@allure.label("priority", "P1")
@allure.label("suite", "portability")
@allure.title("CLI：--provider generic 缺 --provider-arg 应报错 exit 2")
@allure.severity(allure.severity_level.NORMAL)
def test_cli_provider_generic_requires_arg(tmp_path):
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "ledger_agent.py"),
                        str(ledger), "--import-host", "--provider", "generic", "--apply"],
                       cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60,
                       encoding="utf-8")
    with allure.step("断言 exit 2 且提示缺 provider-arg"):
        attach_text(r.stderr, "cli error")
        assert r.returncode == 2
        assert "provider-arg" in r.stderr


@allure.feature("跨 Agent / 多平台可移植性")
@allure.story("无 session_id 的宿主条目内容签名去重")
@allure.epic("office-token-booster")
@allure.label("layer", "core")
@allure.label("test_type", "契约")
@allure.label("component", "import_host_usage")
@allure.label("risk_area", "dedup")
@allure.label("priority", "P0")
@allure.label("suite", "portability")
@allure.title("去重：缺 session_id 的宿主条目按内容签名去重（天禧/OpenClaw 场景）")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.smoke
def test_port_dedup_content_signature_no_session_id():
    """第三方 generic 导出往往没有 session_id；重复导入应靠内容签名去重而非膨胀。"""
    ledger = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"tasks": []}, ledger)
    ledger.close()
    try:
        provider = _TianxiLikeProvider([
            CostRecord(date="2026-08-15", skill_tokens=100, session_id="", source="generic_json"),
            CostRecord(date="2026-08-16", skill_tokens=200, session_id="", source="generic_json"),
        ])
        r1 = import_host_usage(ledger.name, days=7, provider=provider, apply=True, baseline_ratio=3.0)
        with allure.step("首次导入 2 条"):
            assert r1["count"] == 2
            assert r1["skipped_duplicates"] == 0
        r2 = import_host_usage(ledger.name, days=7, provider=provider, apply=True, baseline_ratio=3.0)
        with allure.step("重复导入应内容签名去重，账本不膨胀"):
            assert r2["skipped_duplicates"] == 2
            on_disk = json.load(open(ledger.name, encoding="utf-8"))
            assert len(on_disk["tasks"]) == 2

        # 用户手记条目（无 source）不被误删
        manual = {"date": "2026-08-15", "type": "周报生成", "skill_tokens": 100,
                  "baseline_tokens": 300, "skill_minutes": 0, "baseline_minutes": 0,
                  "note": "手记"}
        on_disk = json.load(open(ledger.name, encoding="utf-8"))
        on_disk["tasks"].append(manual)
        json.dump(on_disk, open(ledger.name, "w", encoding="utf-8"))
        r3 = import_host_usage(ledger.name, days=7, provider=provider, apply=True, baseline_ratio=3.0)
        with allure.step("手记条目保留，总数 = 3"):
            assert r3["skipped_duplicates"] == 2
            on_disk = json.load(open(ledger.name, encoding="utf-8"))
            assert len(on_disk["tasks"]) == 3, "手记应保留不被去重"
    finally:
        os.unlink(ledger.name)


if __name__ == "__main__":
    _report_dir = str(REPO_ROOT / "allure-results")
    print(f"Allure 数据 → {_report_dir}")
    sys.exit(pytest.main([__file__, "-v", f"--alluredir={_report_dir}"]))
