#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_v05.py — office-token-booster v0.5 实地测试脚本

自带一个临时样本账本，脚本化跑完整对话流程，验证 v0.5 的两件事：
  1. 类型字典消歧：自然语言里的『周报』『生成了周报』能正确落到标准类型『周报生成』
  2. 三层数字一致：确认写回的消息、摘要报告、追问回答，数字全部来自同一份 Diagnosis

运行（无需准备任何数据，脚本自动建/删临时账本）：
  cd office-token-booster
  python tests/test_v05.py
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest
import allure

# 让脚本无论从哪个目录运行都能 import 到 scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
# 让测试辅助模块（tests/helpers.py）可被 import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversation import handle, _detect_type
from diagnose import load_ledger, diagnose
from report_engine import generate_markdown_summary
from helpers import build_token_savings_chart, src_link

# 4 条样本任务，覆盖常见类型，让节省率有差异
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

@allure.feature("v0.5 核心功能")
@allure.story("类型字典消歧")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description(
    "验证类型字典消歧：自然语言输入（如『生成了周报』）能正确映射到标准类型『周报生成』。"
    " 覆盖全新类型识别、消歧映射、确认写回三个环节。"
)

@allure.epic("office-token-booster")
@allure.label("layer", "编排层")
@src_link("scripts/conversation.py", line=215, name="handle() 源码")
@pytest.mark.smoke
def test_v05_type_disambiguation(ledger):
    """验证类型字典消歧：自然语言 → 标准类型映射正确。"""
    state = {}
    init_diag = diagnose(load_ledger(ledger))

    # ── 0. 全新类型识别（不污染账本）──
    tt, is_new = _detect_type("记一笔 合同审查 花了1000 token", init_diag)
    allure.attach(
        f"detected=({tt!r}, is_new={is_new})",
        name="全新类型识别结果",
        attachment_type=allure.attachment_type.TEXT,
    )
    assert tt == "合同审查" and is_new, f"全新类型识别失败: ({tt!r}, {is_new})"

    # ── 1. 类型字典消歧：『生成了周报』→『周报生成』──
    r1 = handle(ledger, "我刚生成了周报，花了1800 token 5分钟", state)
    pending_type = state.get("pending", {}).get("type")
    allure.attach(
        f"pending_type={pending_type!r}\nr1_response={r1}",
        name="消歧结果",
        attachment_type=allure.attachment_type.TEXT,
    )
    assert pending_type == "周报生成", f"消歧失败: pending.type={pending_type!r}"
    assert "建议记账：周报生成" in r1, f"预览文本缺失: {r1}"

    # ── 2. 确认写回 ──
    r2 = handle(ledger, "确认", state)
    n = len(json.load(open(ledger, encoding="utf-8"))["tasks"])
    allure.attach(
        f"r2_response={r2}\ntasks_count={n}",
        name="确认写回结果",
        attachment_type=allure.attachment_type.TEXT,
    )
    assert "已记录" in r2, f"确认写回失败: {r2}"
    assert n == 5, f"账本任务数错误: {n} (期望 5)"

@allure.feature("v0.5 核心功能")
@allure.story("三层数字一致性")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description(
    "验证确认消息、摘要报告、内核 Diagnosis 三者的节省率数值来自同一计算源，"
    "误差 < 0.05pp，防止多处数据不一致。"
)
@allure.epic("office-token-booster")
@allure.label("layer", "内核层")
@src_link("scripts/diagnose.py", line=275, name="diagnose() 源码")
@pytest.mark.smoke
def test_v05_three_layer_consistency(ledger):
    """验证三层数字一致：确认消息 / 摘要 / 内核 来源同源。"""
    state = {}

    # 先执行一轮录入以获得可验证的节省率
    handle(ledger, "我刚生成了周报，花了1800 token 5分钟", state)
    r2 = handle(ledger, "确认", state)

    d = diagnose(load_ledger(ledger))
    summ = generate_markdown_summary(d)

    # 确认消息中的节省率
    m_msg = re.search(r"省 ([\d.]+)%", r2)
    msg_pct = float(m_msg.group(1)) if m_msg else None

    diff_msg = abs(msg_pct - d.token_save_pct) if msg_pct is not None else 999
    sum_pcts = [float(x) for x in re.findall(r"省 ([\d.]+)%", summ)]
    diff_min = min((abs(p - d.token_save_pct) for p in sum_pcts), default=999)

    allure.attach(
        f"msg_pct={msg_pct}%\n"
        f"diag.token_save_pct={d.token_save_pct:.1f}%\n"
        f"diff_msg={diff_msg}\n"
        f"summary_pcts={sum_pcts}\n"
        f"diff_min={diff_min}",
        name="三层节省率对比",
        attachment_type=allure.attachment_type.TEXT,
    )

    # HTML visualization: token savings bar chart
    tasks = json.load(open(ledger, encoding="utf-8"))["tasks"]
    chart_html = build_token_savings_chart(tasks, d.token_save_pct)
    allure.attach(
        chart_html,
        name="Token 节省率可视化",
        attachment_type=allure.attachment_type.HTML,
    )

    # 与内核 Diagnosis 一致
    assert diff_msg < 0.05, f"确认消息节省率不一致: msg={msg_pct}% diag={d.token_save_pct:.1f}%"

    # 摘要报告也一致
    assert diff_min < 0.05, f"摘要报告节省率不一致: diag={d.token_save_pct:.1f}% 摘要={sum_pcts}"

@allure.feature("v0.5 核心功能")
@allure.story("对话流程完整性")
@allure.severity(allure.severity_level.NORMAL)
@allure.description(
    "验证完整对话流程：追问『哪个类型省最多？』、『待自动化建议』、『退出』均能正常响应。"
)
@allure.epic("office-token-booster")
@allure.label("layer", "编排层")
@src_link("scripts/conversation.py", line=215, name="handle() 源码")
@pytest.mark.smoke
def test_v05_conversation_flow(ledger):
    """验证完整对话流程：追问 → 建议 → 退出。"""
    state = {}

    # 跑一次完整录入
    handle(ledger, "我刚生成了周报，花了1800 token 5分钟", state)
    handle(ledger, "确认", state)

    # ── 4. 追问 ──
    r3 = handle(ledger, "哪个类型省最多？", state)
    allure.attach(r3, name="追问回答", attachment_type=allure.attachment_type.TEXT)
    assert len(r3) > 5, f"追问回答过短: {r3}"

    # ── 5. 待自动化建议 ──
    r4 = handle(ledger, "待自动化建议", state)
    allure.attach(r4, name="自动化建议", attachment_type=allure.attachment_type.TEXT)
    assert "自动化" in r4 or "周报生成" in r4, f"建议缺失: {r4}"

    # ── 6. 退出 ──
    r5 = handle(ledger, "退出", state)
    allure.attach(r5, name="退出响应", attachment_type=allure.attachment_type.TEXT)
    assert "再见" in r5, f"退出对话失败: {r5}"


if __name__ == "__main__":
    import sys
    _root = Path(__file__).resolve().parent.parent
    _report_dir = str(_root / "allure-results")
    print(f"Allure 数据 → {_report_dir}")
    print(f"查看报告: allure serve {_report_dir}")
    sys.exit(pytest.main([__file__, "-v", f"--alluredir={_report_dir}"]))