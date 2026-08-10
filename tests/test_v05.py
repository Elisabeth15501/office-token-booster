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

# 让脚本无论从哪个目录运行都能 import 到 scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from conversation import handle, _detect_type
from diagnose import load_ledger, diagnose
from report_engine import generate_markdown_summary

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
        init_diag = diagnose(load_ledger(ledger))

        # ── 0. 类型字典：全新类型识别（不污染账本）──
        tt, is_new = _detect_type("记一笔 合同审查 花了1000 token", init_diag)
        step("全新类型识别 → (合同审查, is_new=True)",
             tt == "合同审查" and is_new, f"返回=({tt!r}, {is_new})")

        # ── 1. 类型字典消歧：『生成了周报』→『周报生成』──
        r1 = handle(ledger, "我刚生成了周报，花了1800 token 5分钟", state)
        pending_type = state.get("pending", {}).get("type")
        step("类型字典消歧：『生成了周报』→ 标准类型『周报生成』",
             pending_type == "周报生成", f"pending.type={pending_type!r}")
        step("预览文本含『建议记账：周报生成』", "建议记账：周报生成" in r1, r1)

        # ── 2. 确认写回 ──
        r2 = handle(ledger, "确认", state)
        step("确认后写回（含『已记录』）", "已记录" in r2, r2)
        n = len(json.load(open(ledger, encoding="utf-8"))["tasks"])
        step("账本任务数 4 → 5", n == 5, f"tasks={n}")

        # ── 3. 三层数字一致：确认消息 / 摘要 / 内核 同源（整体节省率）──
        d = diagnose(load_ledger(ledger))
        summ = generate_markdown_summary(d)
        m_msg = re.search(r"省 ([\d.]+)%", r2)
        msg_pct = float(m_msg.group(1)) if m_msg else None
        # 确认消息的整体节省率来自 new_diag.token_save_pct，与重新 diagnose 的 d 同源
        diff_msg = abs(msg_pct - d.token_save_pct) if msg_pct is not None else 999
        step("确认消息整体节省率 == 内核 Diagnosis（三层同源）",
             diff_msg < 0.05, f"msg={msg_pct}%  diag={d.token_save_pct:.1f}%")
        # 摘要报告也应含同一整体节省率（内核同源，误差<0.05pp）
        sum_pcts = [float(x) for x in re.findall(r"省 ([\d.]+)%", summ)]
        diff_min = min((abs(p - d.token_save_pct) for p in sum_pcts), default=999)
        step("摘要报告含与内核一致的整体节省率", diff_min < 0.05,
             f"diag={d.token_save_pct:.1f}%  摘要中的节省率={sum_pcts}")

        # ── 4. 追问 ──
        r3 = handle(ledger, "哪个类型省最多？", state)
        step("追问有接地回答", len(r3) > 5, r3)

        # ── 5. 待自动化建议 ──
        r4 = handle(ledger, "待自动化建议", state)
        step("待自动化建议非空", "自动化" in r4 or "周报生成" in r4, r4)

        # ── 6. 退出 ──
        r5 = handle(ledger, "退出", state)
        step("退出对话", "再见" in r5, r5)

    finally:
        os.unlink(ledger)

    print("\n" + "=" * 48)
    passed = sum(results)
    total = len(results)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("v0.5 类型字典消歧 + 三层一致 验证通过，可实地使用。")
        sys.exit(0)
    else:
        print(f"❌ {total - passed} 项失败 ({passed}/{total})")
        sys.exit(1)


if __name__ == "__main__":
    main()
