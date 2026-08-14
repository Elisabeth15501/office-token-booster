#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ledger_agent.py — office-token-booster 长链路 Agent（B 线 v0.3）

长链路 Agent = 诊断内核（diagnose） + 建议生成（propose） + 写回动作（append）。
本模块**只消费** `diagnose.py` 产出的 `Diagnosis` 对象，不 import `report_engine`、
也不 import `qa`，因此对话式诊断（qa）+ 报告渲染（report_engine）一行代码都不用动 ——
这正是 v0.1 三层解耦要换来的好处（见 README「演进路线」与产品发展计划时间线 ADR-7）。

能力（对应 README 的 v0.3 定义：采集任务 → 分析 → 给出省钱/提效建议 → 可选写回模板）：
1. propose_entry(diag, task_type, ...)      —— 建议生成：把刚完成的任务变成一条账本草稿，
                                               用该类型历史均值预填 baseline 估计。
2. propose_automation_targets(diag)         —— 建议生成：输出下一批「最该自动化」的任务类型。
3. append_entry(ledger_path, entry, ...)    —— 写回模板：原子写回账本（默认 dry-run，
                                               --apply 才真写；写前自动备份）。
4. run_long_chain(ledger_path, task_type)   —— 编排：load_ledger → diagnose → propose → append → 重新 diagnose。

设计原则（与内核一致）：
- 纯标准库、无第三方依赖、无网络、无硬编码密钥。
- 安全默认：CLI 不传 --apply 只预览，绝不改动用户文件。
- 所有数字来自内核 Diagnosis，保证与报告 / 追问三处一致。
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 允许从任意目录运行（与 report_engine / qa 保持一致的 sibling import）。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diagnose import load_ledger, diagnose, format_number  # noqa: E402


# ─────────────────────────────────────────────────────────────
# 建议生成
# ─────────────────────────────────────────────────────────────

def _lookup_type(diag, task_type):
    """在 Diagnosis.by_type 里找该类型的聚合记录（dict），没有返回 None。"""
    for d in diag.by_type:
        if d["task_type"] == task_type:
            return d
    return None


def propose_entry(diag, task_type, *, date=None, skill_tokens=None, skill_minutes=None,
                  baseline_tokens=None, baseline_minutes=None, note=None):
    """把刚完成的任务转成一条账本草稿。

    基线（baseline）= 你不用本技能、自己手搓 / 反复试错的成本，平台无从获得，故优先用
    该类型的历史均值预填；若用户显式传入则用传入值。技能实际消耗（skill_*）同理。

    返回 (entry_dict, meta_dict)：
      entry_dict  —— 标准账本字段（date/type/baseline_tokens/skill_tokens/baseline_minutes/
                     skill_minutes/note），可直接 append 进 ledger。
      meta_dict   —— {history_found, estimated_fields, warnings}，供 CLI 提示哪些是估算值。
    """
    hist = _lookup_type(diag, task_type)
    meta = {"history_found": hist is not None, "estimated_fields": [], "warnings": []}
    cnt = hist["count"] if hist else 0

    # 基线估计（无历史时设为 0 并告警，提醒用户补填真实手搓成本）
    if baseline_tokens is None:
        if hist:
            baseline_tokens = round(hist["baseline_tokens"] / cnt)
        else:
            baseline_tokens = 0
            meta["warnings"].append(
                f"类型「{task_type}」无历史记录，baseline_tokens 暂置 0，请补填真实手搓成本")
            meta["estimated_fields"].append("baseline_tokens")
    if baseline_minutes is None:
        if hist:
            baseline_minutes = round(hist["baseline_minutes"] / cnt)
        else:
            baseline_minutes = 0
            meta["estimated_fields"].append("baseline_minutes")

    # 技能实际消耗（未提供则用该类型历史均值估算，并标记为估算）
    if skill_tokens is None:
        if hist:
            skill_tokens = round(hist["skill_tokens"] / cnt)
            meta["estimated_fields"].append("skill_tokens")
            meta["warnings"].append("skill_tokens 未提供，用该类型历史均值估算，建议填实际值")
        else:
            skill_tokens = 0
            meta["estimated_fields"].append("skill_tokens")
    if skill_minutes is None:
        if hist:
            skill_minutes = round(hist["skill_minutes"] / cnt)
            meta["estimated_fields"].append("skill_minutes")
        else:
            skill_minutes = 0
            meta["estimated_fields"].append("skill_minutes")

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    entry = {
        "date": date,
        "type": task_type,
        "baseline_tokens": int(baseline_tokens),
        "skill_tokens": int(skill_tokens),
        "baseline_minutes": int(baseline_minutes),
        "skill_minutes": int(skill_minutes),
        "note": note or "",
    }
    return entry, meta


def propose_automation_targets(diag, top_n=3):
    """建议生成：输出下一批「最该自动化」的任务类型（按自动化 ROI 降序）。

    直接复用 Diagnosis.roi_targets（内核算好的 ROI 评分），不与 build_insights 的
    recommendations 重复造轮子，也保证报告与 Agent 建议同源。
    """
    if not diag.roi_targets:
        return ["账本暂无数据，先记录几笔任务再生成自动化建议。"]
    out = []
    for t in diag.roi_targets[:top_n]:
        out.append(
            f"「{t['task_type']}」：历史 {t['count']} 次，累计节省 {format_number(t['saved_tokens'])} Token"
            f"（ROI≈{t['roi_score']}），预估月省 {format_number(t['monthly_saved_tokens'])} Token，"
            f"优先做成可复用模板。"
        )
    return out


# ─────────────────────────────────────────────────────────────
# 写回模板（原子 + 备份 + 默认 dry-run）
# ─────────────────────────────────────────────────────────────

def append_entry(ledger_path, entry, *, backup=True, dry_run=False):
    """把 entry 追加进 ledger 的 tasks 数组。

    - dry_run=True：只返回「将会写成的 ledger」dict，不碰磁盘（CLI 默认）。
    - dry_run=False：先备份原文件为 <path>.bak，再原子写入（写临时文件后 os.replace）。
    返回 (new_ledger_dict, backup_path_or_None)。
    """
    p = Path(ledger_path)
    if p.is_file():
        try:
            with open(p, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except (json.JSONDecodeError, ValueError):
            # 损坏的账本：从空账本重建，原文件会在下方备份步骤留存（不丢数据）
            ledger = {"tasks": []}
        if not isinstance(ledger, dict):
            ledger = {"tasks": []}
    else:
        ledger = {"tasks": []}

    tasks = ledger.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []
    tasks.append(entry)
    ledger["tasks"] = tasks

    if dry_run:
        return ledger, None

    backup_path = None
    if backup and p.is_file():
        # 时间戳备份（修复 M2）：每次 apply 生成独立 .bak，连续写回不再覆盖首备，
        # 可回滚到任意历史版本。文件名形如 ledger.json.20260812T142501123456.bak
        ts = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        backup_path = Path(str(p) + f".{ts}.bak")
        backup_path.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

    tmp = Path(str(p) + ".tmp")
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)  # 原子替换（Windows 也安全）
    return ledger, backup_path


def append_entries(ledger_path, entries, *, backup=True, dry_run=False):
    """把多条 entry 一次性追加进 ledger 的 tasks 数组（append_entry 的批量版）。

    与 append_entry 同语义：dry_run 只返回新 ledger dict；否则先备份再原子写入。
    返回 (new_ledger_dict, backup_path_or_None)。
    """
    p = Path(ledger_path)
    if p.is_file():
        try:
            with open(p, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except (json.JSONDecodeError, ValueError):
            ledger = {"tasks": []}
        if not isinstance(ledger, dict):
            ledger = {"tasks": []}
    else:
        ledger = {"tasks": []}

    tasks = ledger.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []
    tasks.extend(entries)
    ledger["tasks"] = tasks

    if dry_run:
        return ledger, None

    backup_path = None
    if backup and p.is_file():
        ts = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        backup_path = Path(str(p) + f".{ts}.bak")
        backup_path.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

    tmp = Path(str(p) + ".tmp")
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)
    return ledger, backup_path


def import_host_usage(ledger_path, days=7, provider=None, *,
                      baseline_tokens=0, baseline_minutes=0, apply=False):
    """v0.9：把宿主真实用量导入为提效账本草稿（skill 取实测值，baseline 默认 0 待补）。

    默认 dry-run（只返回草稿与预览诊断，不碰磁盘）；apply=True 才批量写回。
    返回 dict：{entries, count, applied, backup_path, new_diag, note}。
    """
    from host_cost import get_default_provider, draft_entries_from_host

    provider = provider or get_default_provider()
    if provider is None:
        return {"entries": [], "count": 0, "applied": False, "backup_path": None,
                "new_diag": None, "note": "未检测到本机宿主用量数据，跳过导入。"}

    entries = draft_entries_from_host(
        provider, days, baseline_tokens=baseline_tokens, baseline_minutes=baseline_minutes)
    if not entries:
        return {"entries": [], "count": 0, "applied": False, "backup_path": None,
                "new_diag": None, "note": f"最近 {days} 天无可用宿主用量记录。"}

    if not apply:
        new_diag = diagnose(entries)
        return {"entries": entries, "count": len(entries), "applied": False,
                "backup_path": None, "new_diag": new_diag, "note": "dry-run 预览，未写盘。"}

    new_ledger, bak = append_entries(
        ledger_path, entries, backup=True, dry_run=False)
    new_diag = diagnose(new_ledger["tasks"])
    return {"entries": entries, "count": len(entries), "applied": True,
            "backup_path": bak, "new_diag": new_diag,
            "note": f"已写回 {len(entries)} 条（备份：{bak}）。"}


# ─────────────────────────────────────────────────────────────
# 长链路编排
# ─────────────────────────────────────────────────────────────

def run_long_chain(ledger_path, task_type, *, apply=False, date=None,
                   skill_tokens=None, skill_minutes=None,
                   baseline_tokens=None, baseline_minutes=None, note=None):
    """长链路 Agent 主流程：读取 → 诊断 → 建议 → 写回 → 重新诊断。

    返回 dict：{old_diag, entry, meta, new_diag, ledger_path, applied, backup_path}。
    对话层（qa）/ 渲染层（report_engine）完全不参与，保证内核单一事实源。
    """
    tasks = load_ledger(ledger_path)
    old_diag = diagnose(tasks)
    entry, meta = propose_entry(old_diag, task_type, date=date,
                                skill_tokens=skill_tokens, skill_minutes=skill_minutes,
                                baseline_tokens=baseline_tokens, baseline_minutes=baseline_minutes,
                                note=note)
    new_ledger, bak = append_entry(ledger_path, entry, backup=True, dry_run=not apply)
    new_diag = diagnose(new_ledger["tasks"])
    return {
        "old_diag": old_diag, "entry": entry, "meta": meta,
        "new_diag": new_diag, "ledger_path": ledger_path,
        "applied": apply, "backup_path": bak,
    }


# ─────────────────────────────────────────────────────────────
# CLI（薄包装，与内核解耦）
# ─────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="办公室提效 · 长链路自动记账（office-token-booster v0.3）")
    parser.add_argument("ledger", nargs="?", help="账本 JSON 路径")
    parser.add_argument("--ledger", dest="ledger", help="账本 JSON 路径（同位置参数）")
    parser.add_argument("--type", help="本次完成任务的类型（如 周报生成）")
    parser.add_argument("--date", help="任务日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--skill-tokens", type=int, help="本技能实际消耗 Token（未填则用历史均值估算）")
    parser.add_argument("--skill-minutes", type=int, help="本技能实际耗时分钟（未填则用历史均值估算）")
    parser.add_argument("--baseline-tokens", type=int, help="你手搓的成本 Token（未填则用该类型历史均值）")
    parser.add_argument("--baseline-minutes", type=int, help="你手搓的耗时分钟（未填则用该类型历史均值）")
    parser.add_argument("--note", help="备注")
    parser.add_argument("--apply", action="store_true",
                        help="真正写回账本（默认仅预览，不改动文件）")
    parser.add_argument("--targets", action="store_true",
                        help="改为输出「待自动化类型建议」而不写回")
    parser.add_argument("--import-host", action="store_true",
                        help="v0.9：把本机 WorkBuddy 真实用量导成账本草稿（dry-run 预览；加 --apply 写回）")
    parser.add_argument("--days", type=int, default=7,
                        help="--import-host 的时间窗（最近 N 天，默认 7）")
    args = parser.parse_args()

    if not args.ledger:
        print("[错误] 请提供账本路径：python ledger_agent.py <ledger.json> --type ...",
              file=sys.stderr)
        return 2

    try:
        tasks = load_ledger(args.ledger)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2

    diag = diagnose(tasks)

    if args.import_host:
        res = import_host_usage(args.ledger, days=args.days, apply=args.apply)
        print("=== v0.9 真实宿主用量导入 ===")
        print(res["note"])
        if res["entries"]:
            print(f"草稿条目（{res['count']} 条，skill 取宿主实测，baseline 默认 0 待补）：")
            for e in res["entries"][:20]:
                print("  - " + json.dumps(e, ensure_ascii=False))
            if res["new_diag"]:
                print(f"预览节省 Token：{format_number(res['new_diag'].saved_tok)}"
                      f"（率 {res['new_diag'].token_save_pct:.1f}%，baseline 仍为 0 时仅为占位）")
        if res["applied"]:
            print(f"[OK] 已写回 {res['ledger_path'] if 'ledger_path' in res else args.ledger}"
                  f"（备份：{res['backup_path']}）")
        else:
            print("（未加 --apply，仅预览。加上 --apply 才会真正写入账本。）")
        return 0

    if args.targets:
        print("待自动化类型建议（按历史基线从高到低）：")
        for line in propose_automation_targets(diag):
            print(" - " + line)
        return 0

    if not args.type:
        print("[错误] 写回模式需要 --type；或加 --targets 仅看建议。", file=sys.stderr)
        return 2

    res = run_long_chain(args.ledger, args.type, apply=args.apply, date=args.date,
                         skill_tokens=args.skill_tokens, skill_minutes=args.skill_minutes,
                         baseline_tokens=args.baseline_tokens,
                         baseline_minutes=args.baseline_minutes, note=args.note)
    entry, meta = res["entry"], res["meta"]
    old_d, new_d = res["old_diag"], res["new_diag"]

    print("=== 建议记账条目（propose_entry）===")
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    if meta["estimated_fields"]:
        print(f"[提示] 以下字段为估算/缺省，建议复核：{', '.join(meta['estimated_fields'])}")
    for w in meta["warnings"]:
        print(f"[注意] {w}")

    print("\n=== 写回预览（默认 dry-run，不改动文件）===")
    print(f"任务数   ：{old_d.n} -> {new_d.n}")
    print(f"节省Token：{format_number(old_d.saved_tok)} -> {format_number(new_d.saved_tok)}"
          f"（省 {old_d.token_save_pct:.1f}% -> {new_d.token_save_pct:.1f}%）")
    print(f"节省分钟：{format_number(old_d.saved_min)} -> {format_number(new_d.saved_min)}"
          f"（省 {old_d.time_save_pct:.1f}% -> {new_d.time_save_pct:.1f}%）")

    if res["applied"]:
        print(f"\n[OK] 已写回 {res['ledger_path']}（备份：{res['backup_path']}）")
    else:
        print("\n（未加 --apply，仅预览。加上 --apply 才会真正写入账本。）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
