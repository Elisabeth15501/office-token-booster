#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_v07.py — office-token-booster v0.7 实地测试脚本

验证 v0.7 真实闭环 + 去品牌化（skill_bridge + host_hook）：
  1. 宿主完成事件携带真实用量（cost）→ 触发记账建议，且采用实测成本（cost_source="event"）
  2. 文本解析成本仍可用（cost_source="text"），兼容 v0.6 行为
  3. 非完成事件（纯闲聊）→ 不触发，passthrough=True
  4. 触发默认不写账本（dry-run）
  5. 触发后用户『确认』→ 写回账本，且写回的 skill_tokens == 宿主回报的真实用量（证明非用户自报）
  6. 确认后三层数字同源一致
  7. 去品牌化：skill_bridge.py 不再把 WorkBuddy 当作「绑定平台」
     （旧绑定措辞 "接进 WorkBuddy"/"WorkBuddy 对话事件" 已消失，仅作为多平台之一被列举）
  8. host_hook.build_completion_event 能归一化出通用事件 dict

运行（pytest + Allure）：
  cd office-token-booster
  python -m pytest tests/test_v07.py -v --alluredir=allure-results
  # 或单文件直接运行： python tests/test_v07.py
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest
import allure

# 让脚本无论从哪个目录运行都能 import 到 scripts/ 与 tests/helpers.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skill_bridge import on_conversation_event, is_completion_event, TriggerResult
from host_hook import build_completion_event, on_task_completed
from diagnose import load_ledger, diagnose
from report_engine import generate_markdown_summary
from conversation import handle
from helpers import build_token_savings_chart, attach_ledger, attach_text, src_link

# 4 条样本任务；不含 PPT制作（用于字典兜底识别新类型）
SAMPLE = {
    "tasks": [
        {"date": "2026-08-01", "type": "周报生成", "baseline_tokens": 5000, "skill_tokens": 1800,
         "baseline_minutes": 20, "skill_minutes": 5, "note": "周报"},
        {"date": "2026-08-02", "type": "文档撰写", "baseline_tokens": 8000, "skill_tokens": 3000,
         "baseline_minutes": 30, "skill_minutes": 12, "note": "方案"},
        {"date": "2026-08-03", "type": "数据分析", "baseline_tokens": 6000, "skill_tokens": 2500,
         "baseline_minutes": 25, "skill_minutes": 10, "note": "报表"},
        {"date": "2026-08-04", "type": "代码编写", "baseline_tokens": 7000, "skill_tokens": 3200,
         "baseline_minutes": 40, "skill_minutes": 15, "note": "脚本"},
    ]
}


@pytest.fixture
def ledger():
    """创建临时账本，测试结束后自动删除。"""
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(SAMPLE, tmp, ensure_ascii=False)
    tmp.close()
    path = tmp.name
    yield path
    allure.attach(path, name="ledger_path", attachment_type=allure.attachment_type.TEXT)
    os.unlink(path)


@allure.feature("v0.7 真实闭环 + 去品牌化")
@allure.story("去品牌化（防回归）")
@allure.epic("office-token-booster")
@allure.label("layer", "触发层")
@src_link("scripts/skill_bridge.py", line=151, name="on_conversation_event() 源码")
@allure.title("v0.7 去品牌化：skill_bridge.py 平台无关")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 skill_bridge.py 不再把 WorkBuddy 作为绑定平台，而是平台无关（仅作为多平台之一列举）。")
@pytest.mark.regression
def test_v07_debranding():
    """去品牌化：skill_bridge.py 平台无关，不绑定 WorkBuddy。"""
    src_path = Path(__file__).resolve().parent.parent / "scripts" / "skill_bridge.py"
    src = src_path.read_text(encoding="utf-8").lower()
    bound_phrases = ["接进 workbuddy", "workbuddy 对话事件", "接 workbuddy"]
    re_bound = any(p in src for p in bound_phrases)
    with allure.step("检查是否仍含 WorkBuddy 绑定措辞"):
        attach_text(f"bound_phrases={bound_phrases}\nre_bound={re_bound}", "绑定措辞检查")
        assert not re_bound, "skill_bridge.py 仍含 WorkBuddy 绑定措辞"

    with allure.step("检查是否声明平台无关"):
        declared = "平台无关" in src or "不绑定任何具体平台" in src
        attach_text(f"declared_platform_agnostic={declared}", "平台无关声明")
        assert declared, "skill_bridge.py 未声明平台无关"


@allure.feature("v0.7 真实闭环 + 去品牌化")
@allure.story("宿主事件归一化")
@allure.epic("office-token-booster")
@allure.label("layer", "宿主适配层")
@src_link("scripts/host_hook.py", line=33, name="build_completion_event() 源码")
@allure.title("v0.7 宿主事件归一化（build_completion_event）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 host_hook.build_completion_event 能归一化出通用事件 dict（cost/completed/role）。")
@pytest.mark.integration
def test_v07_host_hook_normalization():
    """host_hook.build_completion_event 归一化出通用事件 dict。"""
    with allure.step("归一化『周报生成 + 真实用量』事件"):
        ev = build_completion_event("我刚生成了周报", skill_tokens=1800,
                                    skill_minutes=5, completed=True)
        attach_text(ev, "归一化事件 dict")
        assert ev.get("cost", {}).get("skill_tokens") == 1800, f"cost.skill_tokens 错误: {ev}"
        assert ev.get("completed") is True, f"completed 错误: {ev}"
        assert ev.get("role") == "user", f"role 错误: {ev}"


@allure.feature("v0.7 真实闭环 + 去品牌化")
@allure.story("成本来源路由")
@allure.epic("office-token-booster")
@allure.label("layer", "触发层")
@src_link("scripts/skill_bridge.py", line=151, name="on_conversation_event() 源码")
@allure.title("v0.7 成本来源路由：event vs text + dry-run")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description(
    "验证宿主真实用量事件采用实测成本（cost_source=event）；"
    "文本解析成本仍可用（cost_source=text，兼容 v0.6）；触发默认 dry-run 不改账本。"
)
@pytest.mark.smoke
def test_v07_cost_source_routing(ledger):
    """真实用量成本来源=event，文本成本来源=text，触发 dry-run。"""
    state = {}
    with allure.step("读取初始账本任务数"):
        n0 = len(json.load(open(ledger, encoding="utf-8"))["tasks"])
        attach_text(n0, "初始任务数")

    with allure.step("宿主真实用量事件 → 触发 + 采用实测成本（cost_source=event）"):
        ev_real = {"role": "user", "text": "我刚生成了周报",
                   "cost": {"skill_tokens": 1800, "skill_minutes": 5}, "completed": True}
        r1 = on_conversation_event(ledger, ev_real, state)
        attach_text(
            f"triggered={r1.triggered}\npending_type={r1.pending_type!r}\n"
            f"cost_source={r1.cost_source}\nsuggestion={r1.suggestion}",
            "真实用量事件触发详情")
        assert r1.triggered, f"真实用量事件未触发: intent={r1.intent}"
        assert r1.pending_type == "周报生成", f"触发类型错误: {r1.pending_type!r}"
        assert r1.cost_source == "event", f"成本来源错误: {r1.cost_source}"
        assert "建议记账" in r1.suggestion, f"建议文本缺失: {r1.suggestion[:40]}"

    with allure.step("触发默认 dry-run：账本任务数不变"):
        n_after_trigger = len(json.load(open(ledger, encoding="utf-8"))["tasks"])
        assert n_after_trigger == n0, f"触发后账本被改动: tasks={n_after_trigger} (期望 {n0})"
        attach_ledger(ledger)
        state["pending"] = None

    with allure.step("文本成本事件 → 仍可用（cost_source=text，兼容 v0.6）"):
        r2 = on_conversation_event(ledger, {"role": "user",
            "text": "我刚生成了周报，花了1800 token 5分钟"}, state)
        attach_text(f"triggered={r2.triggered}\ncost_source={r2.cost_source}", "文本成本事件触发详情")
        assert r2.triggered, f"文本成本事件未触发: intent={r2.intent}"
        assert r2.cost_source == "text", f"文本成本来源错误: {r2.cost_source}"


@allure.feature("v0.7 真实闭环 + 去品牌化")
@allure.story("非完成事件路由")
@allure.epic("office-token-booster")
@allure.label("layer", "触发层")
@src_link("scripts/skill_bridge.py", line=151, name="on_conversation_event() 源码")
@allure.title("v0.7 非完成事件不触发（passthrough）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证非完成事件（纯闲聊）不触发，passthrough=True 交普通对话。")
@pytest.mark.smoke
def test_v07_non_completion_passthrough(ledger):
    """非完成事件不触发，passthrough=True。"""
    with allure.step("纯闲聊事件 → 不触发且 passthrough=True"):
        state = {}
        r3 = on_conversation_event(ledger, {"role": "user", "text": "今天天气不错"}, state)
        attach_text(
            f"triggered={r3.triggered}\nconfidence={r3.confidence}\npassthrough={r3.passthrough}",
            "非完成事件详情")
        assert not r3.triggered, f"非完成事件误触发: confidence={r3.confidence}"
        assert r3.passthrough is True, f"非完成事件未 passthrough: {r3.passthrough}"


@allure.feature("v0.7 真实闭环 + 去品牌化")
@allure.story("确认写回与真实闭环")
@allure.epic("office-token-booster")
@allure.label("layer", "触发层")
@src_link("scripts/skill_bridge.py", line=151, name="on_conversation_event() 源码")
@allure.title("v0.7 确认写回 + 真实闭环（写回条目采用宿主实测）+ 三层一致")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description(
    "验证触发后用户『确认』→写回账本，且写回条目的 skill_tokens/minutes == 宿主真实用量"
    "（证明非用户自报）；三层数字同源一致。"
)
@pytest.mark.smoke
def test_v07_confirm_real_closed_loop(ledger):
    """确认写回账本，写回条目采用宿主真实用量（真实闭环）+ 三层一致。"""
    state = {}
    n0 = len(SAMPLE["tasks"])
    ev_real = {"role": "user", "text": "我刚生成了周报",
               "cost": {"skill_tokens": 1800, "skill_minutes": 5}, "completed": True}

    with allure.step("触发并确认 → 写回账本（含『已记录』，任务数 4→5）"):
        on_conversation_event(ledger, ev_real, state)
        r_confirm = handle(ledger, "确认", state)
        n_after = len(json.load(open(ledger, encoding="utf-8"))["tasks"])
        attach_text(f"r_confirm={r_confirm}\ntasks_count={n_after}", "确认写回详情")
        assert "已记录" in r_confirm, f"确认写回失败: {r_confirm[:40]}"
        assert n_after == n0 + 1, f"账本任务数错误: {n_after} (期望 {n0 + 1})"

    with allure.step("真实闭环：写回条目的 skill_tokens/minutes == 宿主回报的真实用量"):
        last = json.load(open(ledger, encoding="utf-8"))["tasks"][-1]
        attach_text(
            f"last.skill_tokens={last.get('skill_tokens')}\nlast.skill_minutes={last.get('skill_minutes')}",
            "写回条目真实用量")
        assert last.get("skill_tokens") == 1800, f"写回 skill_tokens 非真实用量: {last.get('skill_tokens')}"
        assert last.get("skill_minutes") == 5, f"写回 skill_minutes 非真实用量: {last.get('skill_minutes')}"

    with allure.step("三层同源一致性校验（确认消息 / 摘要 / 内核 Diagnosis）"):
        d = diagnose(load_ledger(ledger))
        summ = generate_markdown_summary(d)
        m_msg = re.search(r"省 ([\d.]+)%", r_confirm)
        msg_pct = float(m_msg.group(1)) if m_msg else None
        diff_msg = abs(msg_pct - d.token_save_pct) if msg_pct is not None else 999
        sum_pcts = [float(x) for x in re.findall(r"省 ([\d.]+)%", summ)]
        diff_min = min((abs(p - d.token_save_pct) for p in sum_pcts), default=999)
        attach_text(
            f"msg_pct={msg_pct}%\ndiag.token_save_pct={d.token_save_pct:.1f}%\n"
            f"diff_msg={diff_msg}\nsummary_pcts={sum_pcts}\ndiff_min={diff_min}",
            "三层节省率对比")

        tasks = json.load(open(ledger, encoding="utf-8"))["tasks"]
        allure.attach(build_token_savings_chart(tasks, d.token_save_pct),
                      name="Token 节省率可视化", attachment_type=allure.attachment_type.HTML)
        attach_ledger(ledger)

        assert diff_msg < 0.05, f"确认消息节省率不一致: msg={msg_pct}% diag={d.token_save_pct:.1f}%"
        assert diff_min < 0.05, f"摘要报告节省率不一致: diag={d.token_save_pct:.1f}% 摘要={sum_pcts}"


@allure.feature("v0.7 真实闭环 + 去品牌化")
@allure.story("成本来源路由（对抗式修复回归）")
@allure.epic("office-token-booster")
@allure.label("layer", "触发层")
@src_link("scripts/skill_bridge.py", line=151, name="on_conversation_event() 源码")
@allure.title("v0.7 成本来源：事件只给 token → mixed（M4）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description(
    "回归 M4：宿主事件只回报 skill_tokens（缺 skill_minutes）时，成本来源标为 'mixed'（部分实测、部分文本估算），"
    "不再误标为 'event'。"
)
@pytest.mark.regression
def test_v07_cost_source_mixed(ledger):
    """事件只给 skill_tokens → cost_source='mixed'。"""
    state = {}
    ev_mixed = {"role": "user", "text": "我刚生成了周报",
                "cost": {"skill_tokens": 1800}, "completed": True}
    with allure.step("事件只给 skill_tokens → 触发 + cost_source=mixed"):
        r = on_conversation_event(ledger, ev_mixed, state)
        attach_text(
            f"triggered={r.triggered}\npending_type={r.pending_type!r}\n"
            f"cost_source={r.cost_source}",
            "mixed 成本来源详情")
        assert r.triggered, f"事件未触发: intent={r.intent}"
        assert r.pending_type == "周报生成", f"触发类型错误: {r.pending_type!r}"
        assert r.cost_source == "mixed", f"成本来源应为 mixed: {r.cost_source}"


@allure.feature("v0.7 真实闭环 + 去品牌化")
@allure.story("中信心路由（对抗式修复回归）")
@allure.epic("office-token-booster")
@allure.label("layer", "触发层")
@src_link("scripts/skill_bridge.py", line=151, name="on_conversation_event() 源码")
@allure.title("v0.7 中信心+无法识别类型 → 不接管、passthrough（M5）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description(
    "回归 M5：仅含完成动词、无成本、且类型字典认不出的句子（如『写完了那份foobar稀奇任务』），"
    "不应强行接管普通对话，passthrough=True 交回普通问答。"
)
@pytest.mark.regression
def test_v07_medium_unknown_passthrough(ledger):
    """中信心 + 类型无法识别 → 不触发、passthrough=True。"""
    state = {}
    with allure.step("仅动词、无成本、类型未知 → 不触发且 passthrough"):
        r = on_conversation_event(ledger,
            {"role": "user", "text": "写完了那份foobar稀奇任务"}, state)
        attach_text(
            f"triggered={r.triggered}\nconfidence={r.confidence}\n"
            f"passthrough={r.passthrough}",
            "中信心未知类型详情")
        assert not r.triggered, f"中信心未知类型不应接管: confidence={r.confidence}"
        assert r.passthrough is True, f"应 passthrough 交普通对话: {r.passthrough}"


if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    _report_dir = str(_root / "allure-results")
    print(f"Allure 数据 → {_report_dir}")
    print(f"查看报告: allure serve {_report_dir}")
    sys.exit(pytest.main([__file__, "-v", f"--alluredir={_report_dir}"]))
