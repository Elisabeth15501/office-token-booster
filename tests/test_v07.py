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

运行（无需准备任何数据，脚本自动建/删临时账本）：
  cd office-token-booster
  python tests/test_v07.py
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
from host_hook import build_completion_event, on_task_completed
from diagnose import load_ledger, diagnose
from report_engine import generate_markdown_summary
from conversation import handle

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

        # ── 7. 去品牌化源码检查（防回归：不得把 WorkBuddy 当作绑定平台）──
        src = (Path(__file__).resolve().parent.parent / "scripts" / "skill_bridge.py") \
            .read_text(encoding="utf-8").lower()
        bound_phrases = ["接进 workbuddy", "workbuddy 对话事件", "接 workbuddy"]
        re_bound = any(p in src for p in bound_phrases)
        step("去品牌化：skill_bridge.py 不绑定 WorkBuddy 为必需平台",
             not re_bound,
             "仍含绑定措辞" if re_bound else "已改为平台无关（仅作为多平台之一列举）")
        step("去品牌化：skill_bridge.py 声明平台无关",
             "平台无关" in src or "不绑定任何具体平台" in src,
             "含『平台无关/不绑定具体平台』声明")

        # ── 8. host_hook 归一化 ──
        ev = build_completion_event("我刚生成了周报", skill_tokens=1800,
                                    skill_minutes=5, completed=True)
        step("host_hook 归一化事件含 cost.skill_tokens=1800",
             ev.get("cost", {}).get("skill_tokens") == 1800, str(ev))
        step("host_hook 归一化事件含 completed=True",
             ev.get("completed") is True, str(ev))
        step("host_hook 归一化事件默认 role=user",
             ev.get("role") == "user", str(ev))

        # ── 1. 宿主真实用量事件 → 触发 + cost_source=event ──
        ev_real = {"role": "user", "text": "我刚生成了周报",
                   "cost": {"skill_tokens": 1800, "skill_minutes": 5}, "completed": True}
        r1 = on_conversation_event(ledger, ev_real, state)
        step("宿主真实用量事件触发（triggered=True）", r1.triggered, f"intent={r1.intent}")
        step("触发类型落到标准名『周报生成』", r1.pending_type == "周报生成",
             f"pending_type={r1.pending_type!r}")
        step("成本来源 = event（采用实测而非文本解析）",
             r1.cost_source == "event", f"cost_source={r1.cost_source}")
        step("建议文本含『建议记账』", "建议记账" in r1.suggestion, r1.suggestion[:40])

        # ── 4. 触发默认不写账本（dry-run）──
        n_after_trigger = len(json.load(open(ledger, encoding="utf-8"))["tasks"])
        step("触发后账本未改动（仍为 4 条，dry-run）",
             n_after_trigger == n0, f"tasks={n_after_trigger} (期望 {n0})")
        state["pending"] = None

        # ── 2. 文本成本仍可用（cost_source=text，兼容 v0.6）──
        r2 = on_conversation_event(ledger, {"role": "user",
            "text": "我刚生成了周报，花了1800 token 5分钟"}, state)
        step("文本成本事件触发（triggered=True）", r2.triggered, f"intent={r2.intent}")
        step("成本来源 = text（兼容 v0.6）", r2.cost_source == "text",
             f"cost_source={r2.cost_source}")
        state["pending"] = None

        # ── 3. 非完成事件（纯闲聊）→ 不触发，passthrough ──
        r3 = on_conversation_event(ledger, {"role": "user", "text": "今天天气不错"}, state)
        step("非完成事件不触发（triggered=False）", not r3.triggered,
             f"confidence={r3.confidence}")
        step("非完成事件 passthrough=True（交普通对话）", r3.passthrough is True,
             str(r3.passthrough))
        state["pending"] = None

        # ── 5. 触发后用户『确认』→ 写回 + 真实成本落地 ──
        on_conversation_event(ledger, ev_real, state)
        r_confirm = handle(ledger, "确认", state)
        step("确认后写回（含『已记录』）", "已记录" in r_confirm, r_confirm[:40])
        n_after = len(json.load(open(ledger, encoding="utf-8"))["tasks"])
        step("账本任务数 4 → 5", n_after == n0 + 1, f"tasks={n_after}")
        # 关键：写回条目的 skill_tokens == 宿主真实用量 1800（非用户自报）→ 真实闭环
        last = json.load(open(ledger, encoding="utf-8"))["tasks"][-1]
        step("写回条目 skill_tokens == 宿主真实用量 1800（真实闭环）",
             last.get("skill_tokens") == 1800, f"actual={last.get('skill_tokens')}")
        step("写回条目 skill_minutes == 宿主真实用量 5",
             last.get("skill_minutes") == 5, f"actual={last.get('skill_minutes')}")

        # ── 6. 三层同源：确认消息 / 重新 diagnose / 摘要报告 节省率一致 ──
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
        print("v0.7 真实闭环 + 去品牌化 验证通过，可接入任意宿主对话平台。")
        sys.exit(0)
    else:
        print(f"❌ {total - passed} 项失败 ({passed}/{total})")
        sys.exit(1)


if __name__ == "__main__":
    main()
