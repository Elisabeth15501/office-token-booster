#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_v06.py — office-token-booster v0.6 实地测试脚本

验证 v0.6 Skill 触发流（skill_bridge.on_conversation_event）：
  1. 高信心完成事件（动词+成本）→ 触发记账建议，类型正确落到标准名
  2. 中信心完成事件（仅动词、无成本，如『写完了那份PPT』）→ 经类型字典兜底仍触发并识别类型
  3. 非完成事件（纯闲聊）→ 不触发，交给普通对话（passthrough=True）
  4. 触发默认不写账本（dry-run）：触发后账本任务数不变
  5. 触发后用户『确认』→ 写回账本且三层数字同源一致
  6. 完成信号识别器 is_completion_event 基本判定正确

运行（pytest + Allure）：
  cd office-token-booster
  python -m pytest tests/test_v06.py -v --alluredir=allure-results
  # 或单文件直接运行： python tests/test_v06.py
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

from skill_bridge import on_conversation_event, is_completion_event, TriggerResult
from diagnose import load_ledger, diagnose, format_number, detect_baseline_anomalies
from report_engine import generate_markdown_summary, generate_html_report
from conversation import handle, classify, _parse_numbers
from helpers import build_token_savings_chart, attach_ledger, attach_text, src_link

# 4 条样本任务，覆盖常见类型；注意不含 PPT制作（用它测「字典兜底识别新类型」）
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


@allure.feature("v0.6 Skill 触发流")
@allure.story("完成信号识别器")
@allure.epic("office-token-booster")
@allure.label("layer", "触发层")
@src_link("scripts/skill_bridge.py", line=65, name="is_completion_event() 源码")
@allure.title("v0.6 完成信号识别器：高/低信心判定")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证 is_completion_event 对高信心（动词+成本）与低信心（非完成事件）的基本判定。")
@pytest.mark.integration
def test_v06_completion_detector():
    """完成信号识别器基本判定正确。"""
    with allure.step("高信心事件（动词+成本）应判为完成且 high"):
        sig_high = is_completion_event("我刚生成了周报，花了1800 token 5分钟")
        attach_text(sig_high, "高信心识别结果")
        assert sig_high["is_completion"] and sig_high["has_cost"] and sig_high["confidence"] == "high", \
            f"高信心判定失败: {sig_high}"

    with allure.step("低信心事件（非完成）应判为未完成且 low"):
        sig_low = is_completion_event("今天天气不错")
        attach_text(sig_low, "低信心识别结果")
        assert (not sig_low["is_completion"]) and sig_low["confidence"] == "low", \
            f"低信心判定失败: {sig_low}"


@allure.feature("v0.6 Skill 触发流")
@allure.story("触发与路由")
@allure.epic("office-token-booster")
@allure.label("layer", "触发层")
@src_link("scripts/skill_bridge.py", line=151, name="on_conversation_event() 源码")
@allure.title("v0.6 触发路由：高/中信心触发 + 字典兜底 + 非完成 passthrough + dry-run")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description(
    "验证高信心完成事件→触发且类型正确落到标准名；中信心（仅动词、PPT）→经类型字典兜底仍触发；"
    "非完成事件→不触发并 passthrough 给普通对话。同时验证触发默认 dry-run 不改账本。"
)
@pytest.mark.smoke
def test_v06_trigger_and_routing(ledger):
    """高/中信心触发 + 类型字典兜底 + 非完成 passthrough + dry-run。"""
    state = {}
    with allure.step("读取初始账本任务数"):
        n0 = len(json.load(open(ledger, encoding="utf-8"))["tasks"])
        attach_text(n0, "初始任务数")

    with allure.step("高信心完成事件（动词+成本）→ 触发 + 类型正确 + 建议文本 + passthrough=False"):
        r1 = on_conversation_event(ledger, {"role": "user",
            "text": "我刚生成了周报，花了1800 token 5分钟"}, state)
        attach_text(
            f"triggered={r1.triggered}\nintent={r1.intent}\npending_type={r1.pending_type!r}\n"
            f"passthrough={r1.passthrough}\nsuggestion={r1.suggestion}",
            "高信心触发详情")
        assert r1.triggered, f"高信心事件未触发: intent={r1.intent}"
        assert r1.pending_type == "周报生成", f"触发类型错误: {r1.pending_type!r}"
        assert "建议记账" in r1.suggestion, f"建议文本缺失: {r1.suggestion[:40]}"
        assert r1.passthrough is False, f"passthrough 应为 False: {r1.passthrough}"

    with allure.step("触发默认 dry-run：账本任务数不变（仍为 4）"):
        n_after_trigger = len(json.load(open(ledger, encoding="utf-8"))["tasks"])
        assert n_after_trigger == n0, f"触发后账本被改动: tasks={n_after_trigger} (期望 {n0})"
        attach_ledger(ledger)
        state["pending"] = None

    with allure.step("中信心完成事件（仅动词、PPT）→ 字典兜底仍触发并识别为『PPT制作』"):
        r2 = on_conversation_event(ledger, {"role": "user", "text": "写完了那份PPT"}, state)
        attach_text(
            f"triggered={r2.triggered}\nintent={r2.intent}\npending_type={r2.pending_type!r}\n"
            f"suggestion={r2.suggestion}",
            "中信心触发详情")
        assert r2.triggered, f"中信心事件未触发: intent={r2.intent}"
        assert r2.pending_type == "PPT制作", f"PPT 兜底识别失败: {r2.pending_type!r}"
        assert "建议记账" in r2.suggestion, f"中信心建议文本缺失: {r2.suggestion[:40]}"

    with allure.step("非完成事件（纯闲聊）→ 不触发，passthrough=True 交普通对话"):
        r3 = on_conversation_event(ledger, {"role": "user", "text": "今天天气不错"}, state)
        attach_text(
            f"triggered={r3.triggered}\nconfidence={r3.confidence}\npassthrough={r3.passthrough}",
            "非完成事件详情")
        assert not r3.triggered, f"非完成事件误触发: confidence={r3.confidence}"
        assert r3.passthrough is True, f"非完成事件未 passthrough: {r3.passthrough}"


@allure.feature("v0.6 Skill 触发流")
@allure.story("确认写回与三层一致")
@allure.epic("office-token-booster")
@allure.label("layer", "内核层")
@src_link("scripts/diagnose.py", line=275, name="diagnose() 源码")
@allure.title("v0.6 确认写回账本 + 三层数字同源一致")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description(
    "验证触发后用户『确认』→写回账本；且确认消息 / 摘要报告 / 内核 Diagnosis 三者的节省率同源（误差 < 0.05pp）。"
)
@pytest.mark.smoke
def test_v06_confirm_and_three_layer(ledger):
    """确认写回账本，三层数字同源一致。"""
    state = {}
    n0 = len(SAMPLE["tasks"])

    with allure.step("触发并确认 → 写回账本（含『已记录』，任务数 4→5）"):
        on_conversation_event(ledger, {"role": "user",
            "text": "我刚生成了周报，花了1800 token 5分钟"}, state)
        r_confirm = handle(ledger, "确认", state)
        n_after = len(json.load(open(ledger, encoding="utf-8"))["tasks"])
        attach_text(f"r_confirm={r_confirm}\ntasks_count={n_after}", "确认写回详情")
        assert "已记录" in r_confirm, f"确认写回失败: {r_confirm[:40]}"
        assert n_after == n0 + 1, f"账本任务数错误: {n_after} (期望 {n0 + 1})"

    with allure.step("三层同源一致性校验（确认消息 / 摘要 / 内核 Diagnosis）"):
        ledger_tasks = load_ledger(ledger)
        d = diagnose(ledger_tasks)
        summ = generate_markdown_summary(d)
        # 1) 内核自洽：Diagnosis 节省率与账本原始数字独立重算一致
        #    （修复 L4：不再用正则抓文案，文案改动不会让测试误伤）
        base_tok = sum(t["baseline_tokens"] for t in ledger_tasks)
        skill_tok = sum(t["skill_tokens"] for t in ledger_tasks)
        recomputed = (base_tok - skill_tok) / base_tok * 100 if base_tok else 0.0
        # 2) 确认消息 / 摘要 均来自同一内核值（以格式化串包含方式校验同源）
        pct_str = f"{d.token_save_pct:.1f}%"
        attach_text(
            f"diag.token_save_pct={d.token_save_pct:.1f}%\n"
            f"recomputed={recomputed:.1f}%\npct_str={pct_str}",
            "三层节省率对比")

        allure.attach(build_token_savings_chart(ledger_tasks, d.token_save_pct),
                      name="Token 节省率可视化", attachment_type=allure.attachment_type.HTML)
        attach_ledger(ledger)

        assert abs(d.token_save_pct - recomputed) < 1e-6, \
            f"内核省率与账本重算不一致: diag={d.token_save_pct:.1f}% recomputed={recomputed:.1f}%"
        assert pct_str in r_confirm, \
            f"确认消息未包含内核节省率 {pct_str}: {r_confirm[:60]}"
        assert pct_str in summ, f"摘要报告未包含内核节省率 {pct_str}"


@allure.feature("v0.6 Skill 触发流")
@allure.story("产品产出物展示（作品集）")
@allure.epic("office-token-booster")
@allure.label("layer", "适配层")
@src_link("scripts/report_engine.py", line=292, name="generate_html_report() 源码")
@allure.title("v0.6 在测试报告内嵌技能实际产出（HTML 报告附件）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description(
    "把技能自身的 report_engine 完整 HTML 报告作为附件挂到 Allure，"
    "让审阅者在测试报告里直接看到本技能的真实产出（作品集展示用）。"
)
@pytest.mark.integration
def test_v06_product_html_report_attachment(ledger):
    """把技能实际产出的 HTML 报告作为附件，作品集可一键查看真实效果。"""
    tasks = json.load(open(ledger, encoding="utf-8"))["tasks"]
    d = diagnose(tasks)
    html_report = generate_html_report(d)
    with allure.step("生成产品 HTML 报告并校验关键数字存在"):
        assert "办公室提效报告" in html_report, "产品报告未包含标题"
        assert format_number(d["saved_tok"]) in html_report, "产品报告未包含节省 Token"
        allure.attach(html_report, name="技能产出 · 提效报告(HTML)",
                      attachment_type=allure.attachment_type.HTML)
        attach_text(
            f"report_len={len(html_report)}\nsaved_tok={format_number(d['saved_tok'])}",
            "产品报告元信息")


@allure.feature("v0.6 Skill 触发流")
@allure.story("数据可信度护栏（作品集·诚实性）")
@allure.epic("office-token-booster")
@allure.label("layer", "内核层")
@src_link("scripts/diagnose.py", line=178, name="detect_baseline_anomalies() 源码")
@allure.title("v0.6 数据可信度护栏：异常账本被识别并提示")
@allure.severity(allure.severity_level.NORMAL)
@allure.description(
    "构造一笔『技能 Token ≈ 基准』的异常账本，验证 detect_baseline_anomalies 主动暴露"
    "可信度风险。作品集体现「不夸大提效、主动暴露前提」的诚实与护栏设计。"
)
@pytest.mark.regression
def test_v06_credibility_guard():
    """异常账本（技能消耗≈基准）应被护栏识别并提示。"""
    tasks = [{
        "date": "2026-08-01", "type": "周报生成",
        "baseline_tokens": 5000, "skill_tokens": 5000,
        "baseline_minutes": 20, "skill_minutes": 20, "note": "技能消耗与基准持平，未体现提效",
    }]
    with allure.step("检测异常账本并断言返回护栏提示"):
        caveats = detect_baseline_anomalies(tasks)
        attach_text(caveats, "可信度护栏提示")
        assert caveats, "异常账本未被识别"
        assert any("持平" in c or "未体现提效" in c for c in caveats), \
            f"护栏未捕获持平/未提效: {caveats}"


@allure.feature("v0.6 Skill 触发流")
@allure.story("自然语言解析健壮性（对抗式修复回归）")
@allure.epic("office-token-booster")
@allure.label("layer", "编排层")
@src_link("scripts/conversation.py", line=92, name="_parse_numbers() 源码")
@allure.title("v0.6 成本解析：小数/单位不崩溃、正确换算（H1）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description(
    "回归 H1：_parse_numbers 对小数（『200.5 token』→200 不崩溃）、中文单位"
    "（『1.5万 token』→15000 不丢单位）、畸形输入（『abc token』→None 不抛异常）均正确。"
)
@pytest.mark.regression
def test_v06_parse_numbers_robust():
    """成本解析：小数/单位/畸形输入均健壮。"""
    with allure.step("小数不崩溃：『200.5 token』→ 200"):
        tok, _ = _parse_numbers("花了200.5 token")
        attach_text(tok, "小数解析")
        assert tok == 200, f"小数解析失败: {tok}"

    with allure.step("中文单位换算：『1.5万 token』→ 15000"):
        tok, _ = _parse_numbers("花了1.5万 token")
        attach_text(tok, "万单位解析")
        assert tok == 15000, f"万单位解析失败: {tok}"

    with allure.step("畸形输入不抛异常：『abc token』→ None"):
        try:
            tok, _ = _parse_numbers("花了abc token")
        except Exception as e:  # noqa: BLE001
            raise AssertionError(f"畸形输入应返回 None 而非抛异常: {e}")
        attach_text(tok, "畸形输入解析")
        assert tok is None, f"畸形输入未降级为 None: {tok}"


@allure.feature("v0.6 Skill 触发流")
@allure.story("意图识别准确性（对抗式修复回归）")
@allure.epic("office-token-booster")
@allure.label("layer", "编排层")
@src_link("scripts/conversation.py", line=180, name="classify() 源码")
@allure.title("v0.6 确认意图不误判疑问句/否定/含『行』词（H2）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description(
    "回归 H2：classify 不再把『这个行业报告可以吗？』『我不确定』『流行方案』误判为 confirm；"
    "正常确认词『确认』『可以』『行』仍判定为 confirm。"
)
@pytest.mark.regression
def test_v06_classify_confirm_no_false_positive():
    """确认意图识别：排除疑问句/否定/含『行』词，保留正常确认。"""
    with allure.step("易误判句不应判为 confirm"):
        for bad in ["这个行业报告可以吗？", "我不确定", "流行方案", "这个方案行吗"]:
            assert classify(bad) != "confirm", f"误判为 confirm: {bad!r}"
        attach_text(
            {b: classify(b) for b in ["这个行业报告可以吗？", "我不确定", "流行方案", "这个方案行吗"]},
            "易误判句意图分布")

    with allure.step("正常确认词仍判为 confirm"):
        for good in ["确认", "可以", "行", "没问题", "就这样"]:
            assert classify(good) == "confirm", f"未识别为 confirm: {good!r}"
        attach_text(
            {g: classify(g) for g in ["确认", "可以", "行", "没问题", "就这样"]},
            "正常确认词意图分布")


if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    _report_dir = str(_root / "allure-results")
    print(f"Allure 数据 → {_report_dir}")
    print(f"查看报告: allure serve {_report_dir}")
    sys.exit(pytest.main([__file__, "-v", f"--alluredir={_report_dir}"]))
