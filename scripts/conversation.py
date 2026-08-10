#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""conversation.py — office-token-booster 对话编排层（B 线 v0.4）

把三个既有外壳（qa 追问 / report_engine 报告 / ledger_agent 写回）串成
单一对话流：用户说一句，本层理解意图、调用对应的内核能力，必要时建议记账。

设计原则（与三层解耦一致）：
- 只消费既有模块，**绝不改 qa / report_engine / ledger_agent 一行**。v0.4 完全是新增的
  "粘合层"，复用它们暴露的纯函数（answer_followup / generate_* / propose_* / run_long_chain）。
- 纯标准库、无第三方依赖、无网络、无硬编码密钥。
- 状态用普通 dict 传递（state["pending"] 保存待确认条目），便于上层 Skill / 对话 UI 集成。
- 安全默认：记账必须显式「确认」才写回账本（ledger_agent 内部仍是默认 dry-run + 备份）。

用法：
  python conversation.py <ledger.json>          # 进入交互式对话
  或在 Python 中：
  from conversation import handle
  state = {}
  print(handle("ledger.json", "记一笔 周报生成 花了1800 token 5分钟", state))
  print(handle("ledger.json", "确认", state))
"""

import argparse
import json
import re
import sys
from pathlib import Path

# 允许从任意目录运行（与 qa / report_engine / ledger_agent 保持一致的 sibling import）。
sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagnose import load_ledger, diagnose, format_number          # noqa: E402
from qa import answer_followup                                      # noqa: E402
from ledger_agent import (                                         # noqa: E402
    propose_entry, propose_automation_targets, run_long_chain)
from report_engine import (                                        # noqa: E402
    generate_markdown_summary, generate_markdown_report)


# ─────────────────────────────────────────────────────────────
# 自然语言解析
# ─────────────────────────────────────────────────────────────

def _parse_numbers(text):
    """从自然语句里抽 token / 分钟数，抽不到返回 None。"""
    tokens = None
    minutes = None
    m = re.search(r"(\d[\d,]*)\s*(?:个\s*)?(?:token|tokens|Token|TOKEN)", text)
    if m:
        tokens = int(m.group(1).replace(",", ""))
    m = re.search(r"(\d[\d,]*)\s*(?:分钟|分|min|mins)", text, re.I)
    if m:
        minutes = int(m.group(1).replace(",", ""))
    return tokens, minutes


def _detect_type(text, diag):
    """判断任务类型：先看账本里已记录的类型名是否出现在话里；
    否则抓『生成了/做了/完成了…<词>』后面的短语作为候选，再做一次模糊匹配
    （候选是某已知类型的子串，或反之），尽量落到账本已有的标准类型名。"""
    known = [d["task_type"] for d in diag.by_type if d["task_type"]]
    for k in known:
        if k in text:
            return k
    m = re.search(
        r"(?:生成了|做了|完成了|写好?了|做好?了|产出|整理|搞完?了|记[一笔]?)\s*"
        r"([一-龥A-Za-z0-9]{1,10}?)(?:[，,。.\s]|$)",
        text,
    )
    cand = m.group(1).strip() if m else None
    if not cand:
        return None
    for k in known:
        if cand in k or k in cand:
            return k
    return cand


def classify(text):
    """把一句话归到意图：exit / cancel / confirm / record / report_summary /
    report_full / targets / followup。"""
    t = (text or "").strip()
    if not t:
        return "unknown"
    if re.search(r"(退出|exit|quit|再见|bye)", t, re.I):
        return "exit"
    if re.search(r"(取消|不算了|不要记|别记|false|撤销)", t, re.I):
        return "cancel"
    if re.search(r"(确认|好的|记吧|写吧|我同意|同意|可以|确定|没问题|行|就这样)", t):
        return "confirm"
    if re.search(r"(完整报告|详细报告|九段|生成报告|全部明细|看报告)", t):
        return "report_full"
    if re.search(r"(摘要|一页|总结一下|概览|看下概况|概括)", t):
        return "report_summary"
    if re.search(r"(待自动化|哪些值得|自动化建议|该自动化|targets)", t, re.I):
        return "targets"
    # 显式记账词
    if re.search(r"(记一笔|记录|记账|记一下|记上|登记|添加任务|新增任务|记下来|写进账本)", t):
        return "record"
    # 被动完成信号：既说「完成了某任务」又给出成本数字 → 自动建议记账
    if (re.search(r"(花了|用了|耗时|花费|消耗|占)\s*.{0,12}?\s*(token|分钟|分)", t, re.I)
            and re.search(r"(生成|完成|做完|写好|做好|产出|整理|搞完|记)", t)):
        return "record"
    return "followup"


# ─────────────────────────────────────────────────────────────
# 路由
# ─────────────────────────────────────────────────────────────

def handle(ledger_path, text, state):
    """对话主路由。state 是调用方维护的 dict（至少含可选 "pending"）。

    返回中文回复字符串。本函数不读 stdin、不写 stdout，方便上层直接调用。
    """
    intent = classify(text)

    if intent == "exit":
        return "再见，账本已保留。"

    if intent == "cancel":
        if state.get("pending"):
            state["pending"] = None
            return "已取消，未写入账本。"
        return "当前没有待确认的记录。"

    tasks = load_ledger(ledger_path)
    diag = diagnose(tasks)

    if intent == "confirm":
        pending = state.get("pending")
        if not pending:
            return ('没有待确认的记录。你可以说：记一笔 周报生成 花了1800 token 5分钟')
        res = run_long_chain(
            ledger_path, pending["type"], apply=True, date=pending.get("date"),
            skill_tokens=pending.get("skill_tokens"),
            skill_minutes=pending.get("skill_minutes"),
            baseline_tokens=pending.get("baseline_tokens"),
            baseline_minutes=pending.get("baseline_minutes"),
            note=pending.get("note"),
        )
        state["pending"] = None
        new_d = res["new_diag"]
        msg = (f"[已记录] {pending['type']}。当前共 {new_d.n} 条任务，"
               f"累计节省 {format_number(new_d.saved_tok)} Token"
               f"（省 {new_d.token_save_pct:.1f}%）、"
               f"{format_number(new_d.saved_min)} 分钟"
               f"（省 {new_d.time_save_pct:.1f}%）。")
        tgs = propose_automation_targets(new_d)
        if tgs:
            msg += "\n待自动化建议：" + tgs[0]
        return msg

    if intent == "record":
        tokens, minutes = _parse_numbers(text)
        ttype = _detect_type(text, diag)
        if not ttype:
            return ('没认出任务类型。请这样告诉我：「记一笔 周报生成 花了1800 token 5分钟」，'
                    '或直接说类型名。')
        entry, meta = propose_entry(
            diag, ttype, skill_tokens=tokens, skill_minutes=minutes)
        # 存用户原始输入（未提供的字段留 None，让确认时按历史均值重估）
        state["pending"] = {
            "type": ttype,
            "date": entry["date"],
            "skill_tokens": tokens,
            "skill_minutes": minutes,
            "baseline_tokens": None,
            "baseline_minutes": None,
            "note": entry["note"],
        }
        lines = [
            f"建议记账：{ttype}",
            f"  本技能消耗：{format_number(entry['skill_tokens'])} Token / {entry['skill_minutes']} 分钟",
            f"  基准估计：{format_number(entry['baseline_tokens'])} Token / {entry['baseline_minutes']} 分钟（按历史均值预填）",
        ]
        if meta["estimated_fields"]:
            lines.append(f"  [提示] 以下为估算值，建议复核：{', '.join(meta['estimated_fields'])}")
        for w in meta["warnings"]:
            lines.append(f"  [注意] {w}")
        lines.append("确认写进账本吗？（回复「确认」即写回，或说「取消」）")
        return "\n".join(lines)

    if intent == "report_summary":
        return generate_markdown_summary(diag)

    if intent == "report_full":
        return generate_markdown_report(diag)

    if intent == "targets":
        out = propose_automation_targets(diag)
        if isinstance(out, list) and out and out[0].startswith("账本暂无"):
            return out[0]
        return "待自动化类型建议（按历史基线从高到低）：\n" + "\n".join(
            " - " + l for l in out)

    # 兜底：交给 qa 做数据接地的追问应答
    return answer_followup(diag, text)


# ─────────────────────────────────────────────────────────────
# CLI（交互式 REPL，薄包装）
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="办公室提效 · 对话式自动记账编排（office-token-booster v0.4）")
    parser.add_argument("ledger", nargs="?", help="账本 JSON 路径")
    parser.add_argument("--ledger", dest="ledger", help="账本 JSON 路径（同位置参数）")
    args = parser.parse_args()

    ledger = args.ledger
    if not ledger:
        print("[错误] 请提供账本路径：python conversation.py <ledger.json>",
              file=sys.stderr)
        return 2
    try:
        load_ledger(ledger)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2

    state = {}
    print("=== 办公室提效对话（v0.4）===")
    print('试试：记一笔 周报生成 花了1800 token 5分钟 ｜ 哪个类型省最多？ '
          '｜ 生成摘要 ｜ 待自动化建议 ｜ 退出')
    while True:
        try:
            line = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见，账本已保留。")
            break
        if not line:
            continue
        resp = handle(ledger, line, state)
        if classify(line) == "exit":
            print("助手> " + resp)
            break
        print("助手> " + resp + "\n")


if __name__ == "__main__":
    sys.exit(main())
