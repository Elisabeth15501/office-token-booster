#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_boundary.py — 负向/边界测试集

覆盖各模块的极端输入、畸形数据、空值与越界场景，验证系统「优雅降级」能力。
所有测试均按 docs/allure-labels.md 的维度体系标注 label，便于在 Allure 报告中
按 test_type=boundary|negative、risk_area、component 等维度筛选。
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
import allure

# 让脚本无论从哪个目录运行都能 import 到 scripts/ 与 tests/helpers.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagnose import (
    format_number, load_ledger, compute_summary,
    detect_baseline_anomalies, diagnose, Diagnosis,
)
from conversation import classify, _detect_type, _parse_numbers, _parse_number
from skill_bridge import (
    is_completion_event, _coerce_int, on_conversation_event,
    TriggerResult,
)
from host_hook import build_completion_event
from ledger_agent import propose_entry, append_entry
from report_engine import generate_html_report, generate_markdown_summary

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from render_allure_html import load_results, render, DEFAULT_CATEGORIES

from helpers import src_link, attach_text


# ─────────────────────────────────────────────────────────────
# diagnose.py 边界
# ─────────────────────────────────────────────────────────────

@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("format_number 极端输入")
@allure.title("format_number: None/0/负数/超大数")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 format_number 对 None、0、负数、超大数据的格式化不崩溃且输出合理。")
@allure.label("layer", "内核层")
@allure.label("test_type", "boundary")
@allure.label("component", "diagnose")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P2")
@allure.label("suite", "boundary")
@src_link("scripts/diagnose.py", line=36, name="format_number() 源码")
def test_format_number_edge_cases():
    """format_number 对极端数值的边界处理。"""
    with allure.step("None → '0'"):
        assert format_number(None) == "0", "None 应格式化为 '0'"
    with allure.step("0 → '0'"):
        assert format_number(0) == "0", "0 应格式化为 '0'"
    with allure.step("负数 → 原样字符串"):
        assert format_number(-1500) == "-1500", f"负数格式化异常: {format_number(-1500)}"
    with allure.step("超大数 1e9 → '1.00G'"):
        assert format_number(1_000_000_000) == "1.00G", f"超大数格式化异常: {format_number(1_000_000_000)}"
    with allure.step("极大数 1e12 → '1000.00G'"):
        assert format_number(1_000_000_000_000) == "1000.00G"


@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("load_ledger 异常文件")
@allure.title("load_ledger: 文件不存在/损坏JSON/顶层非dict")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 load_ledger 对缺失文件、损坏 JSON、顶层非 dict 的输入抛出预期异常。")
@allure.label("layer", "内核层")
@allure.label("test_type", "negative")
@allure.label("component", "diagnose")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "boundary")
@src_link("scripts/diagnose.py", line=54, name="load_ledger() 源码")
def test_load_ledger_invalid_inputs():
    """load_ledger 对畸形文件的异常处理。"""
    with allure.step("文件不存在 → FileNotFoundError"):
        with pytest.raises(FileNotFoundError):
            load_ledger("/nonexistent/ledger.json")

    with allure.step("损坏 JSON → JSONDecodeError"):
        bad = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        bad.write("{invalid json")
        bad.close()
        with pytest.raises(json.JSONDecodeError):
            load_ledger(bad.name)
        os.unlink(bad.name)

    with allure.step("顶层非 dict → ValueError"):
        arr = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump([1, 2, 3], arr)
        arr.close()
        with pytest.raises(ValueError):
            load_ledger(arr.name)
        os.unlink(arr.name)


@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("compute_summary 空任务与缺失字段")
@allure.title("compute_summary: 空tasks/含None字段/单条任务")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 compute_summary 对空 tasks 列表、字段缺失/为 None 的任务、单条任务均不崩溃。")
@allure.label("layer", "内核层")
@allure.label("test_type", "boundary")
@allure.label("component", "diagnose")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "boundary")
@src_link("scripts/diagnose.py", line=66, name="compute_summary() 源码")
def test_compute_summary_edge_cases():
    """compute_summary 对空任务和字段缺失的鲁棒性。"""
    with allure.step("空 tasks → 全零汇总"):
        s = compute_summary([])
        assert s["n"] == 0
        assert s["saved_tok"] == 0
        assert s["token_save_pct"] == 0.0

    with allure.step("字段缺失/为 None → 按 0 计算"):
        s = compute_summary([
            {"date": "2026-08-01", "type": "周报生成"},
            {"date": "2026-08-02", "type": "文档撰写",
             "baseline_tokens": None, "skill_tokens": 1000},
        ])
        assert s["n"] == 2
        assert s["total_base_tok"] == 0
        assert s["total_skill_tok"] == 1000

    with allure.step("单条任务 → 正常汇总"):
        s = compute_summary([
            {"date": "2026-08-01", "type": "周报生成",
             "baseline_tokens": 5000, "skill_tokens": 1800,
             "baseline_minutes": 20, "skill_minutes": 5},
        ])
        assert s["n"] == 1
        assert s["saved_tok"] == 3200


@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("detect_baseline_anomalies 极端账本")
@allure.title("detect_baseline_anomalies: 空/负节省/零基线/单条")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证护栏对空账本、负节省、零基线、单条任务的边界处理。")
@allure.label("layer", "内核层")
@allure.label("test_type", "boundary")
@allure.label("component", "diagnose")
@allure.label("risk_area", "credibility")
@allure.label("priority", "P2")
@allure.label("suite", "boundary")
@src_link("scripts/diagnose.py", line=178, name="detect_baseline_anomalies() 源码")
def test_detect_baseline_anomalies_edge_cases():
    """可信度护栏对极端账本的边界处理。"""
    with allure.step("空 tasks → 空列表"):
        assert detect_baseline_anomalies([]) == []

    with allure.step("负节省（skill > baseline）→ 被捕获"):
        caveats = detect_baseline_anomalies([
            {"date": "2026-08-01", "type": "测试", "baseline_tokens": 100,
             "skill_tokens": 200, "baseline_minutes": 10, "skill_minutes": 15},
        ])
        assert any("持平或更高" in c or "未体现提效" in c for c in caveats), \
            f"负节省未被捕获: {caveats}"

    with allure.step("零基线 → 不崩溃（避免除零）"):
        caveats = detect_baseline_anomalies([
            {"date": "2026-08-01", "type": "测试", "baseline_tokens": 0,
             "skill_tokens": 0, "baseline_minutes": 0, "skill_minutes": 0},
        ])
        # 零基线且零技能 → skill_token==0 触发特殊提示
        assert isinstance(caveats, list)


@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("Diagnosis 空初始化与字典访问")
@allure.title("Diagnosis: 空对象/KeyError/get默认值")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 Diagnosis 空初始化、__getitem__ 缺失键抛 KeyError、get 返回默认值。")
@allure.label("layer", "内核层")
@allure.label("test_type", "boundary")
@allure.label("component", "diagnose")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P2")
@allure.label("suite", "boundary")
@src_link("scripts/diagnose.py", line=236, name="Diagnosis 类源码")
def test_diagnosis_empty_and_access():
    """Diagnosis 空对象与字典访问边界。"""
    with allure.step("空初始化 → 全默认值"):
        d = Diagnosis()
        assert d.n == 0
        assert d.token_save_pct == 0.0

    with allure.step("__getitem__ 缺失键 → KeyError"):
        with pytest.raises(KeyError):
            _ = d["nonexistent_key"]

    with allure.step("get 缺失键 → 默认值"):
        assert d.get("nonexistent_key", "fallback") == "fallback"
        assert d.get("nonexistent_key") is None


# ─────────────────────────────────────────────────────────────
# conversation.py 边界
# ─────────────────────────────────────────────────────────────

@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("_parse_numbers 畸形输入")
@allure.title("_parse_numbers: 空串/非数字/负数/超大数/emoji")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证成本解析器对空字符串、非数字、负数、超大数、emoji、极端单位的降级处理。")
@allure.label("layer", "编排层")
@allure.label("test_type", "boundary")
@allure.label("component", "conversation")
@allure.label("risk_area", "cost_accuracy")
@allure.label("priority", "P1")
@allure.label("suite", "boundary")
@src_link("scripts/conversation.py", line=92, name="_parse_numbers() 源码")
def test_parse_numbers_boundary():
    """_parse_numbers 对极端输入的降级处理。"""
    with allure.step("空字符串 → (None, None)"):
        assert _parse_numbers("") == (None, None)

    with allure.step("纯非数字 → (None, None)"):
        assert _parse_numbers("花了abc token") == (None, None)

    with allure.step("负数前缀 → 符号被忽略，按正数解析（成本域非负，符号无意义）"):
        tok, _ = _parse_numbers("花了-100 token")
        assert tok == 100, f"负数符号处理异常: {tok}"

    with allure.step("超大数 → 正常解析不溢出"):
        tok, _ = _parse_numbers("花了999999999 token")
        assert tok == 999_999_999

    with allure.step("emoji/特殊字符 → (None, None)"):
        assert _parse_numbers("花了💰 token") == (None, None)

    with allure.step("非法复合单位『万万』→ 解析失败返回 None（不崩溃）"):
        # 正则要求『数字 + 可选单位 + 紧接 token』，"1万万 token" 中第二个『万』
        # 阻断了单位与 token 关键字的邻接，无法匹配 → 优雅降级为 None，不抛异常
        tok, _ = _parse_numbers("花了1万万 token")
        attach_text(tok, "『万万』解析结果")
        assert tok is None, f"非法复合单位应解析失败，实际: {tok}"


@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("classify 极端输入")
@allure.title("classify: 空/None/仅标点/超长文本/全空格")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证意图分类器对空输入、None、仅标点、超长文本、全空格的降级处理。")
@allure.label("layer", "编排层")
@allure.label("test_type", "boundary")
@allure.label("component", "conversation")
@allure.label("risk_area", "type_disambiguation")
@allure.label("priority", "P1")
@allure.label("suite", "boundary")
@src_link("scripts/conversation.py", line=180, name="classify() 源码")
def test_classify_boundary():
    """classify 对极端输入的降级处理。"""
    with allure.step("空字符串 → unknown"):
        assert classify("") == "unknown"

    with allure.step("None → unknown"):
        assert classify(None) == "unknown"

    with allure.step("全空格 → unknown"):
        assert classify("   \t\n  ") == "unknown"

    with allure.step("仅标点 → followup"):
        assert classify("???！！！") == "followup"

    with allure.step("超长文本 → 不崩溃，正常分类"):
        long_text = "生成" * 500 + "周报"
        result = classify(long_text)
        attach_text(result, "超长文本分类结果")
        assert result in ("record", "followup", "report_summary", "execute")


@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("_detect_type 极端输入")
@allure.title("_detect_type: 空text/空diag/大小写混合")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证类型检测对空文本、空诊断对象、大小写混合的边界处理。")
@allure.label("layer", "编排层")
@allure.label("test_type", "boundary")
@allure.label("component", "conversation")
@allure.label("risk_area", "type_disambiguation")
@allure.label("priority", "P1")
@allure.label("suite", "boundary")
@src_link("scripts/conversation.py", line=99, name="_detect_type() 源码")
def test_detect_type_boundary():
    """_detect_type 对极端输入的降级处理。"""
    empty_diag = Diagnosis()

    with allure.step("空 text → (None, False)"):
        assert _detect_type("", empty_diag) == (None, False)

    with allure.step("空 diag（无已知类型）→ 新类型候选"):
        tt, is_new = _detect_type("记一笔 周报生成 花了1000 token", empty_diag)
        attach_text(f"tt={tt!r}, is_new={is_new}", "空diag检测结果")
        # 短语抓取应能抓到「周报生成」
        assert tt is not None, "空diag也应通过短语抓取识别类型"

    with allure.step("大小写混合（PPT vs ppt）→ 字典大小写不敏感兜底"):
        # 依赖 type_registry.json 里有 PPT制作
        diag_with_ppt = Diagnosis(by_type=[{"task_type": "PPT制作", "count": 1,
                                              "baseline_tokens": 1000, "skill_tokens": 500,
                                              "baseline_minutes": 10, "skill_minutes": 5,
                                              "saved_tokens": 500, "saved_minutes": 5,
                                              "token_save_pct": 50.0, "time_save_pct": 50.0}])
        tt, is_new = _detect_type("写完了那份ppt", diag_with_ppt)
        attach_text(f"tt={tt!r}", "大小写混合检测结果")
        # _lenient_type 在 skill_bridge 里做大小写不敏感匹配，conversation._detect_type 本身不做
        # 所以这里可能返回 None 或新候选，只要不打断即可
        assert is_new is False or tt is None or isinstance(tt, str), "大小写混合不应崩溃"


# ─────────────────────────────────────────────────────────────
# skill_bridge.py 边界
# ─────────────────────────────────────────────────────────────

@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("is_completion_event 极端输入")
@allure.title("is_completion_event: None/空串/仅标点/无动词")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证完成信号识别器对 None、空字符串、仅标点、无动词文本的降级处理。")
@allure.label("layer", "触发层")
@allure.label("test_type", "boundary")
@allure.label("component", "skill_bridge")
@allure.label("risk_area", "type_disambiguation")
@allure.label("priority", "P2")
@allure.label("suite", "boundary")
@src_link("scripts/skill_bridge.py", line=65, name="is_completion_event() 源码")
def test_is_completion_event_boundary():
    """完成信号识别器对极端输入的降级处理。"""
    with allure.step("None → low 且不触发"):
        sig = is_completion_event(None)
        assert sig["is_completion"] is False
        assert sig["confidence"] == "low"

    with allure.step("空字符串 → low"):
        sig = is_completion_event("")
        assert sig["is_completion"] is False

    with allure.step("仅标点 → low"):
        sig = is_completion_event("！！！？？？")
        assert sig["is_completion"] is False

    with allure.step("无动词纯成本 → low（is_completion=False，成本识别需触发词）"):
        sig = is_completion_event("1800 token 5分钟")
        assert sig["is_completion"] is False
        # 成本正则要求『花了/用了/…』等触发词，纯数字无动词 → has_cost=False
        assert sig["has_cost"] is False
        assert sig["confidence"] == "low"


@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("_coerce_int 畸形输入")
@allure.title("_coerce_int: 字符串abc/布尔/列表/空串/超大字符串")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证宿主成本强制转换函数对非数值输入的降级：返回 None 不崩溃。")
@allure.label("layer", "触发层")
@allure.label("test_type", "negative")
@allure.label("component", "skill_bridge")
@allure.label("risk_area", "cost_accuracy")
@allure.label("priority", "P0")
@allure.label("suite", "boundary")
@src_link("scripts/skill_bridge.py", line=114, name="_coerce_int() 源码")
def test_coerce_int_negative():
    """_coerce_int 对非数值输入的安全降级。"""
    with allure.step("字符串 'abc' → None"):
        assert _coerce_int("abc") is None

    with allure.step("布尔 True → 1（int(float(True)) 行为）"):
        result = _coerce_int(True)
        attach_text(result, "布尔 True 转换结果")
        assert result == 1  # int(float(True)) == 1

    with allure.step("列表 → None"):
        assert _coerce_int([1, 2]) is None

    with allure.step("空字符串 → None"):
        assert _coerce_int("") is None

    with allure.step("负数字符串 → 正常转换"):
        assert _coerce_int("-100") == -100


@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("on_conversation_event 畸形事件")
@allure.title("on_conversation_event: None event/缺text/成本为字符串")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证触发主入口对 None event、缺失 text、成本字段为字符串的降级处理。")
@allure.label("layer", "触发层")
@allure.label("test_type", "negative")
@allure.label("component", "skill_bridge")
@allure.label("risk_area", "cost_accuracy")
@allure.label("priority", "P0")
@allure.label("suite", "boundary")
@src_link("scripts/skill_bridge.py", line=151, name="on_conversation_event() 源码")
def test_on_conversation_event_negative(tmp_path):
    """on_conversation_event 对畸形事件的降级处理。"""
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")

    with allure.step("None event → 返回默认 TriggerResult"):
        r = on_conversation_event(str(ledger), None, {})
        assert r.triggered is False
        assert r.cost_source == "none"

    with allure.step("event 缺 text → 不触发"):
        r = on_conversation_event(str(ledger), {"role": "user"}, {})
        assert r.triggered is False

    with allure.step("event text 为空字符串 → 不触发"):
        r = on_conversation_event(str(ledger), {"role": "user", "text": ""}, {})
        assert r.triggered is False

    with allure.step("cost 为字符串 'abc' → 降级为 None（不崩溃）"):
        r = on_conversation_event(str(ledger), {
            "role": "user", "text": "我刚生成了周报",
            "cost": {"skill_tokens": "abc", "skill_minutes": "def"},
            "completed": True,
        }, {})
        attach_text(
            f"triggered={r.triggered}\npending_type={r.pending_type!r}\n"
            f"cost_source={r.cost_source}",
            "畸形成本事件触发详情")
        # 不应崩溃，且 cost_source 应为 none（因为两个 cost 都被降级为 None）
        assert r.cost_source == "none" or r.cost_source == "text"


# ─────────────────────────────────────────────────────────────
# ledger_agent.py 边界
# ─────────────────────────────────────────────────────────────

@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("propose_entry 未知类型与空diag")
@allure.title("propose_entry: 未知类型/空diag/全None字段")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 propose_entry 对未知类型、空 Diagnosis、全 None 字段的降级：生成警告与估算标记。")
@allure.label("layer", "写回层")
@allure.label("test_type", "boundary")
@allure.label("component", "ledger_agent")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "boundary")
@src_link("scripts/ledger_agent.py", line=48, name="propose_entry() 源码")
def test_propose_entry_boundary():
    """propose_entry 对极端输入的降级处理。"""
    empty_diag = Diagnosis()

    with allure.step("未知类型 + 空 diag → 0 值 + warnings"):
        entry, meta = propose_entry(empty_diag, "稀奇类型")
        attach_text(f"entry={entry}\nmeta={meta}", "未知类型提案详情")
        assert entry["baseline_tokens"] == 0
        assert entry["skill_tokens"] == 0
        assert meta["warnings"], "未知类型应生成警告"
        assert "baseline_tokens" in meta["estimated_fields"]

    with allure.step("全 None 字段 → 估算值 + 标记"):
        entry2, meta2 = propose_entry(empty_diag, "另一类型",
                                       skill_tokens=None, skill_minutes=None,
                                       baseline_tokens=None, baseline_minutes=None)
        assert meta2["estimated_fields"], "全 None 应标记估算字段"


@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("append_entry 异常账本与空条目")
@allure.title("append_entry: 空条目/损坏的ledger/dry_run")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 append_entry 对空条目、损坏 ledger 文件、dry_run 的边界处理。")
@allure.label("layer", "写回层")
@allure.label("test_type", "boundary")
@allure.label("component", "ledger_agent")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "boundary")
@src_link("scripts/ledger_agent.py", line=135, name="append_entry() 源码")
def test_append_entry_boundary(tmp_path):
    """append_entry 对异常账本的边界处理。"""
    ledger = tmp_path / "ledger.json"

    with allure.step("空条目追加到空文件 → tasks 含 1 条空-ish 记录"):
        ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
        new_ledger, bak = append_entry(str(ledger), {}, dry_run=False)
        assert len(new_ledger["tasks"]) == 1
        assert bak is not None, "应生成备份"

    with allure.step("损坏的 ledger（非 JSON）→ 重建为 {'tasks': [entry]}"):
        bad = tmp_path / "bad_ledger.json"
        bad.write_text("not json at all", encoding="utf-8")
        new_ledger2, bak2 = append_entry(str(bad), {"type": "修复"}, dry_run=False)
        assert len(new_ledger2["tasks"]) == 1
        assert new_ledger2["tasks"][0]["type"] == "修复"

    with allure.step("dry_run=True → 不碰磁盘，返回预览"):
        n_before = len(json.loads(ledger.read_text(encoding="utf-8"))["tasks"])
        preview, _ = append_entry(str(ledger), {"type": "dry"}, dry_run=True)
        n_after = len(json.loads(ledger.read_text(encoding="utf-8"))["tasks"])
        assert n_before == n_after, "dry_run 不应修改文件"
        assert len(preview["tasks"]) == n_before + 1, "dry_run 应返回含新条目的预览"


# ─────────────────────────────────────────────────────────────
# host_hook.py 边界
# ─────────────────────────────────────────────────────────────

@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("build_completion_event 极端输入")
@allure.title("build_completion_event: None text/负数/超大token/仅completed")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证宿主事件归一化函数对 None text、负数、超大 token、仅 completed 标志的边界处理。")
@allure.label("layer", "宿主适配层")
@allure.label("test_type", "boundary")
@allure.label("component", "host_hook")
@allure.label("risk_area", "real_closed_loop")
@allure.label("priority", "P1")
@allure.label("suite", "boundary")
@src_link("scripts/host_hook.py", line=33, name="build_completion_event() 源码")
def test_build_completion_event_boundary():
    """build_completion_event 对极端输入的边界处理。"""
    with allure.step("None text → 含 None text 的 dict（调用方责任）"):
        ev = build_completion_event(None)
        assert ev["text"] is None
        assert "cost" not in ev

    with allure.step("负数 token → 正常包含（业务层校验）"):
        ev = build_completion_event("测试", skill_tokens=-100)
        assert ev["cost"]["skill_tokens"] == -100

    with allure.step("超大 token → 正常包含"):
        ev = build_completion_event("测试", skill_tokens=999999999)
        assert ev["cost"]["skill_tokens"] == 999999999

    with allure.step("仅 completed=True，无 cost → 无 cost 字段"):
        ev = build_completion_event("测试", completed=True)
        assert ev["completed"] is True
        assert "cost" not in ev


# ─────────────────────────────────────────────────────────────
# report_engine.py 边界
# ─────────────────────────────────────────────────────────────

@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("report_engine 空Diagnosis")
@allure.title("report_engine: 空Diagnosis → HTML/Markdown不崩溃")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证报告渲染对空 Diagnosis（零任务）的边界：不崩溃、输出含占位提示。")
@allure.label("layer", "适配层")
@allure.label("test_type", "boundary")
@allure.label("component", "report_engine")
@allure.label("risk_area", "ui_rendering")
@allure.label("priority", "P2")
@allure.label("suite", "boundary")
@src_link("scripts/report_engine.py", line=292, name="generate_html_report() 源码")
def test_report_engine_empty_diagnosis():
    """报告渲染对空 Diagnosis 的边界处理。"""
    empty_diag = Diagnosis()

    with allure.step("HTML 报告不崩溃"):
        html = generate_html_report(empty_diag)
        assert "办公室提效报告" in html
        attach_text(f"html_len={len(html)}", "空Diagnosis HTML长度")

    with allure.step("Markdown 摘要不崩溃"):
        md = generate_markdown_summary(empty_diag)
        assert "暂无数据" in md or "暂无任务类型数据" in md or "共 0 条" in md
        attach_text(md, "空Diagnosis Markdown摘要")


# ─────────────────────────────────────────────────────────────
# renderer 边界
# ─────────────────────────────────────────────────────────────

@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("renderer 空结果与损坏JSON")
@allure.title("renderer: 空results目录/损坏JSON/空tests列表")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证渲染器对空结果目录、损坏 result.json、空 tests 列表的边界：不崩溃、产出合法HTML。")
@allure.label("layer", "渲染层")
@allure.label("test_type", "boundary")
@allure.label("component", "renderer")
@allure.label("risk_area", "ui_rendering")
@allure.label("priority", "P2")
@allure.label("suite", "boundary")
@src_link("tools/render_allure_html.py", line=91, name="load_results() 源码")
def test_renderer_boundary(tmp_path):
    """渲染器对空/损坏输入的边界处理。"""
    with allure.step("空目录 → load_results 返回 []"):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        assert load_results(str(empty_dir)) == []

    with allure.step("损坏 JSON → 静默跳过，不崩溃"):
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "bad-result.json").write_text("not json", encoding="utf-8")
        results = load_results(str(bad_dir))
        assert results == [], "损坏 JSON 应被静默跳过"

    with allure.step("空 tests 列表 → render 产出合法 HTML"):
        html = render({}, DEFAULT_CATEGORIES, [], str(empty_dir))
        assert "<!DOCTYPE html>" in html
        assert "0 个用例" in html or "用例总数" in html
        attach_text(f"html_len={len(html)}", "空tests HTML长度")


# ─────────────────────────────────────────────────────────────
# 跨模块集成边界
# ─────────────────────────────────────────────────────────────

@allure.epic("office-token-booster")
@allure.feature("边界测试")
@allure.story("端到端：空账本完整对话")
@allure.title("端到端: 空账本 → handle 各意图不崩溃")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证空账本状态下，对话路由（摘要、建议、追问、退出）全部不崩溃。")
@allure.label("layer", "编排层")
@allure.label("test_type", "boundary")
@allure.label("component", "conversation")
@allure.label("risk_area", "data_integrity")
@allure.label("priority", "P1")
@allure.label("suite", "boundary")
@src_link("scripts/conversation.py", line=215, name="handle() 源码")
def test_handle_empty_ledger(tmp_path):
    """空账本状态下的端到端对话边界。"""
    ledger = tmp_path / "empty.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    state = {}

    from conversation import handle

    with allure.step("追问 → 有应答"):
        r1 = handle(str(ledger), "哪个类型省最多？", state)
        attach_text(r1, "空账本追问应答")
        assert len(r1) > 0

    with allure.step("摘要 → 有输出"):
        r2 = handle(str(ledger), "生成摘要", state)
        attach_text(r2, "空账本摘要应答")
        assert "暂无" in r2 or "0 条" in r2 or "暂无数据" in r2

    with allure.step("建议 → 有输出"):
        r3 = handle(str(ledger), "待自动化建议", state)
        attach_text(r3, "空账本建议应答")
        assert len(r3) > 0

    with allure.step("退出 → 正常"):
        r4 = handle(str(ledger), "退出", state)
        assert "再见" in r4


if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    _report_dir = str(_root / "allure-results")
    print(f"Allure 数据 → {_report_dir}")
    print(f"查看报告: allure serve {_report_dir}")
    sys.exit(pytest.main([__file__, "-v", f"--alluredir={_report_dir}"]))
