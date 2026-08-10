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

运行（无需准备任何数据，脚本自动建/删临时账本）：
  cd office-token-booster
  python tests/test_v06.py
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

# 让脚本无论从哪个目录运行都能 import 到 scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from skill_bridge import on_conversation_event, is_completion_event, TriggerResult
from diagnose import load_ledger, diagnose
from report_engine import generate_markdown_summary

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

results = []


def step(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}")
    if detail:
        print("        " + detail.replace("\n", "\n        "))
    results.append(ok)


def main():
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(SAMPLE, tmp, ensure_ascii=False)
    tmp.close()
    ledger = tmp.name

    try:
        state = {}
        n0 = len(json.load(open(ledger, encoding="utf-8"))["tasks"])

        # ── 0. 完成信号识别器基本判定 ──
        sig_high = is_completion_event("我刚生成了周报，花了1800 token 5分钟")
        step("is_completion_event 高信心（动词+成本）",
             sig_high["is_completion"] and sig_high["has_cost"] and sig_high["confidence"] == "high",
             str(sig_high))
        sig_low = is_completion_event("今天天气不错")
        step("is_completion_event 低信心（非完成事件）不触发",
             (not sig_low["is_completion"]) and sig_low["confidence"] == "low", str(sig_low))

        # ── 1. 高信心完成事件（动词+成本）→ 触发 + 类型正确 ──
        r1 = on_conversation_event(ledger, {"role": "user",
            "text": "我刚生成了周报，花了1800 token 5分钟"}, state)
        step("高信心完成事件触发（triggered=True）", r1.triggered, f"intent={r1.intent}")
        step("触发类型落到标准名『周报生成』", r1.pending_type == "周报生成",
             f"pending_type={r1.pending_type!r}")
        step("建议文本含『建议记账』", "建议记账" in r1.suggestion, r1.suggestion[:40])
        step("触发后 passthrough=False（已被接管）", r1.passthrough is False, str(r1.passthrough))

        # ── 4. 触发默认不写账本（dry-run）──
        n_after_trigger = len(json.load(open(ledger, encoding="utf-8"))["tasks"])
        step("触发后账本未改动（仍为 4 条，dry-run）",
             n_after_trigger == n0, f"tasks={n_after_trigger} (期望 {n0})")

        # 重置 pending，避免影响后续用例
        state["pending"] = None

        # ── 2. 中信心完成事件（仅动词、无成本，PPT）→ 字典兜底仍触发 ──
        r2 = on_conversation_event(ledger, {"role": "user", "text": "写完了那份PPT"}, state)
        step("中信心完成事件触发（无成本也能触发）", r2.triggered, f"intent={r2.intent}")
        step("PPT 经类型字典兜底识别为标准名『PPT制作』",
             r2.pending_type == "PPT制作", f"pending_type={r2.pending_type!r}")
        step("中信心建议文本含『建议记账』", "建议记账" in r2.suggestion, r2.suggestion[:40])

        # ── 3. 非完成事件（纯闲聊）→ 不触发，passthrough ──
        r3 = on_conversation_event(ledger, {"role": "user", "text": "今天天气不错"}, state)
        step("非完成事件不触发（triggered=False）", not r3.triggered, f"confidence={r3.confidence}")
        step("非完成事件 passthrough=True（交普通对话）", r3.passthrough is True, str(r3.passthrough))

        # 重置 pending
        state["pending"] = None

        # ── 5. 触发后用户『确认』→ 写回 + 三层一致 ──
        on_conversation_event(ledger, {"role": "user",
            "text": "我刚生成了周报，花了1800 token 5分钟"}, state)
        # 模拟 Skill 把用户的「确认」交给普通对话流处理
        from conversation import handle
        r_confirm = handle(ledger, "确认", state)
        step("确认后写回（含『已记录』）", "已记录" in r_confirm, r_confirm[:40])
        n_after = len(json.load(open(ledger, encoding="utf-8"))["tasks"])
        step("账本任务数 4 → 5", n_after == n0 + 1, f"tasks={n_after}")

        # 三层同源：确认消息 / 重新 diagnose / 摘要报告 节省率一致
        d = diagnose(load_ledger(ledger))
        summ = generate_markdown_summary(d)
        m_msg = re.search(r"省 ([\d.]+)%", r_confirm)
        msg_pct = float(m_msg.group(1)) if m_msg else None
        diff_msg = abs(msg_pct - d.token_save_pct) if msg_pct is not None else 999
        step("确认消息节省率 == 内核 Diagnosis（三层同源）",
             diff_msg < 0.05, f"msg={msg_pct}%  diag={d.token_save_pct:.1f}%")
        sum_pcts = [float(x) for x in re.findall(r"省 ([\d.]+)%", summ)]
        diff_min = min((abs(p - d.token_save_pct) for p in sum_pcts), default=999)
        step("摘要报告含与内核一致的整体节省率", diff_min < 0.05,
             f"diag={d.token_save_pct:.1f}%  摘要中的节省率={sum_pcts}")

    finally:
        os.unlink(ledger)

    print("\n" + "=" * 48)
    passed = sum(results)
    total = len(results)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("v0.6 Skill 触发流 验证通过，可实地接入 WorkBuddy 对话事件。")
        sys.exit(0)
    else:
        print(f"❌ {total - passed} 项失败 ({passed}/{total})")
        sys.exit(1)


if __name__ == "__main__":
    main()
