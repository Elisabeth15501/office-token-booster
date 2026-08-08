#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
office-token-booster :: 提效账本报告引擎
=====================================
读取用户提供的任务账本 JSON，量化"笨办法 vs 本技能"节省的 Token 与耗时，
生成 Markdown + HTML 报告。

设计原则（与 agent-analytics-report 报告引擎一脉相承，但完全解耦）：
- 纯标准库，无第三方依赖、无网络、无硬编码密钥
- 数据源是用户主动提供的文件，不读取任何平台私有目录
- 节省值为参考估计，不是平台计费数据

账本格式（ledger.json）：
{
  "tasks": [
    {
      "date": "2026-08-08",
      "type": "会议纪要",
      "baseline_tokens": 12000,
      "skill_tokens": 3000,
      "baseline_minutes": 25,
      "skill_minutes": 3,
      "note": "可选备注"
    }
  ]
}
"""

import argparse
import json
import os
import sys
from datetime import datetime


# ---------- 工具函数 ----------

def fmt_int(n):
    """千分位整数。"""
    try:
        return f"{int(round(n)):,}"
    except (TypeError, ValueError):
        return "0"


def fmt_pct(n, digits=1):
    try:
        return f"{n:.{digits}f}%"
    except (TypeError, ValueError):
        return "0%"


def _safe_div(a, b):
    return (a / b) if b else 0.0


# ---------- 计算 ----------

def load_ledger(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"账本文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        raise ValueError("ledger.json 顶层必须有 tasks 数组")
    return tasks


def compute_summary(tasks):
    total_base_tok = sum(t.get("baseline_tokens", 0) or 0 for t in tasks)
    total_skill_tok = sum(t.get("skill_tokens", 0) or 0 for t in tasks)
    total_base_min = sum(t.get("baseline_minutes", 0) or 0 for t in tasks)
    total_skill_min = sum(t.get("skill_minutes", 0) or 0 for t in tasks)
    n = len(tasks)

    saved_tok = total_base_tok - total_skill_tok
    saved_min = total_base_min - total_skill_min

    # 按任务类型聚合
    by_type = {}
    for t in tasks:
        ty = t.get("type", "其他")
        d = by_type.setdefault(ty, {"baseline_tokens": 0, "skill_tokens": 0,
                                    "baseline_minutes": 0, "skill_minutes": 0, "count": 0})
        d["baseline_tokens"] += t.get("baseline_tokens", 0) or 0
        d["skill_tokens"] += t.get("skill_tokens", 0) or 0
        d["baseline_minutes"] += t.get("baseline_minutes", 0) or 0
        d["skill_minutes"] += t.get("skill_minutes", 0) or 0
        d["count"] += 1

    for ty, d in by_type.items():
        d["saved_tokens"] = d["baseline_tokens"] - d["skill_tokens"]
        d["saved_minutes"] = d["baseline_minutes"] - d["skill_minutes"]
        d["token_save_pct"] = _safe_div(d["saved_tokens"], d["baseline_tokens"]) * 100
        d["time_save_pct"] = _safe_div(d["saved_minutes"], d["baseline_minutes"]) * 100

    # 按周聚合（取 date 的 ISO 周）
    by_week = {}
    for t in tasks:
        date = t.get("date", "")
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            wk = dt.strftime("%Y-W%V")
        except (ValueError, TypeError):
            wk = "未知周"
        w = by_week.setdefault(wk, {"baseline_tokens": 0, "skill_tokens": 0,
                                    "baseline_minutes": 0, "skill_minutes": 0, "count": 0})
        w["baseline_tokens"] += t.get("baseline_tokens", 0) or 0
        w["skill_tokens"] += t.get("skill_tokens", 0) or 0
        w["baseline_minutes"] += t.get("baseline_minutes", 0) or 0
        w["skill_minutes"] += t.get("skill_minutes", 0) or 0
        w["count"] += 1

    return {
        "n": n,
        "total_base_tok": total_base_tok,
        "total_skill_tok": total_skill_tok,
        "total_base_min": total_base_min,
        "total_skill_min": total_skill_min,
        "saved_tok": saved_tok,
        "saved_min": saved_min,
        "token_save_pct": _safe_div(saved_tok, total_base_tok) * 100,
        "time_save_pct": _safe_div(saved_min, total_base_min) * 100,
        "by_type": by_type,
        "by_week": dict(sorted(by_week.items())),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ---------- SVG 甜甜圈 ----------

def build_donut(saved_pct, title="Token 节省占比"):
    """saved_pct: 0~100。返回一段内联 SVG。"""
    pct = max(0.0, min(100.0, saved_pct))
    r = 60
    cx = cy = 80
    circ = 2 * 3.141592653589793 * r
    arc = circ * (pct / 100.0)
    # 背景环
    svg = (
        f'<svg viewBox="0 0 160 160" width="160" height="160" role="img" aria-label="{title}">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#e5e7eb" stroke-width="18"/>'
    )
    if arc > 0:
        svg += (
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#22c55e" stroke-width="18" '
            f'stroke-dasharray="{arc:.1f} {circ:.1f}" stroke-dashoffset="0" '
            f'transform="rotate(-90 {cx} {cy})" stroke-linecap="round"/>'
        )
    svg += (
        f'<text x="{cx}" y="{cy-4}" text-anchor="middle" font-size="22" font-weight="700" fill="#111827">'
        f'{fmt_pct(pct, 0)}</text>'
        f'<text x="{cx}" y="{cy+18}" text-anchor="middle" font-size="11" fill="#6b7280">{title}</text>'
        f'</svg>'
    )
    return svg


# ---------- Markdown 报告 ----------

def generate_markdown_report(s):
    L = []
    L.append("# 办公室提效报告")
    L.append("")
    L.append(f"> 生成时间：{s['generated_at']} ｜ 共 {s['n']} 条任务记录")
    L.append("")
    L.append("## 总览")
    L.append("")
    L.append(f"- **节省 Token**：{fmt_int(s['saved_tok'])}（基准 {fmt_int(s['total_base_tok'])} → 本技能 {fmt_int(s['total_skill_tok'])}），节省 **{fmt_pct(s['token_save_pct'])}**")
    L.append(f"- **节省时间**：{fmt_int(s['saved_min'])} 分钟（基准 {fmt_int(s['total_base_min'])} → 本技能 {fmt_int(s['total_skill_min'])}），节省 **{fmt_pct(s['time_save_pct'])}**")
    L.append("")
    L.append("## 按任务类型")
    L.append("")
    L.append("| 类型 | 任务数 | 基准 Token | 本技能 Token | 省 Token | 省时间(分) | Token节省% |")
    L.append("|------|------|------|------|------|------|------|")
    for ty, d in sorted(s["by_type"].items(), key=lambda kv: kv[1]["saved_tokens"], reverse=True):
        L.append(f"| {ty} | {d['count']} | {fmt_int(d['baseline_tokens'])} | {fmt_int(d['skill_tokens'])} | "
                 f"{fmt_int(d['saved_tokens'])} | {fmt_int(d['saved_minutes'])} | {fmt_pct(d['token_save_pct'])} |")
    L.append("")
    L.append("## 按周趋势")
    L.append("")
    L.append("| 周 | 任务数 | 基准 Token | 本技能 Token | 省 Token |")
    L.append("|------|------|------|------|------|")
    for wk, w in s["by_week"].items():
        L.append(f"| {wk} | {w['count']} | {fmt_int(w['baseline_tokens'])} | {fmt_int(w['skill_tokens'])} | "
                 f"{fmt_int(w['baseline_tokens'] - w['skill_tokens'])} |")
    L.append("")
    L.append("---")
    L.append("*节省值为基于你填写的基准估计计算的参考值，用于建立提效体感，非平台计费数据。*")
    return "\n".join(L)


# ---------- HTML 报告 ----------

def _bar(value, max_value, color="#22c55e"):
    w = int(_safe_div(value, max_value) * 100)
    w = max(2, min(100, w))
    return (f'<div style="background:#f3f4f6;border-radius:4px;height:14px;width:100%;">'
            f'<div style="background:{color};height:14px;border-radius:4px;width:{w}%;"></div></div>')


def generate_html_report(s):
    donut = build_donut(s["token_save_pct"])
    type_rows = ""
    max_tok = max((d["baseline_tokens"] for d in s["by_type"].values()), default=1) or 1
    for ty, d in sorted(s["by_type"].items(), key=lambda kv: kv[1]["saved_tokens"], reverse=True):
        type_rows += (
            f'<tr><td>{ty}</td><td>{d["count"]}</td>'
            f'<td>{fmt_int(d["baseline_tokens"])}</td><td>{fmt_int(d["skill_tokens"])}</td>'
            f'<td>{fmt_int(d["saved_tokens"])}</td><td>{fmt_int(d["saved_minutes"])}</td>'
            f'<td>{fmt_pct(d["token_save_pct"])}</td></tr>'
        )
    week_rows = ""
    for wk, w in s["by_week"].items():
        week_rows += (f'<tr><td>{wk}</td><td>{w["count"]}</td>'
                      f'<td>{fmt_int(w["baseline_tokens"])}</td><td>{fmt_int(w["skill_tokens"])}</td>'
                      f'<td>{fmt_int(w["baseline_tokens"] - w["skill_tokens"])}</td></tr>')

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>办公室提效报告</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,'Microsoft YaHei',sans-serif;max-width:860px;margin:24px auto;padding:0 16px;color:#111827;}}
 h1{{font-size:22px;}} h2{{font-size:17px;margin-top:28px;border-left:4px solid #22c55e;padding-left:8px;}}
 .cards{{display:flex;gap:16px;flex-wrap:wrap;margin:16px 0;}}
 .card{{flex:1;min-width:200px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:14px;}}
 .card .big{{font-size:24px;font-weight:700;}} .card .sub{{color:#6b7280;font-size:13px;}}
 table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px;}}
 th,td{{border:1px solid #e5e7eb;padding:6px 8px;text-align:right;}} th:first-child,td:first-child{{text-align:left;}}
 th{{background:#f3f4f6;}} .note{{color:#6b7280;font-size:12px;margin-top:18px;}}
</style></head><body>
<h1>办公室提效报告</h1>
<p style="color:#6b7280">生成时间：{s['generated_at']} ｜ 共 {s['n']} 条任务记录</p>
<div class="cards">
  <div class="card"><div class="big">{fmt_int(s['saved_tok'])}</div><div class="sub">节省 Token（基准 {fmt_int(s['total_base_tok'])} → 本技能 {fmt_int(s['total_skill_tok'])}）</div></div>
  <div class="card"><div class="big">{fmt_int(s['saved_min'])} 分</div><div class="sub">节省时间（基准 {fmt_int(s['total_base_min'])} → 本技能 {fmt_int(s['total_skill_min'])}）</div></div>
  <div class="card" style="display:flex;align-items:center;justify-content:center;">{donut}</div>
</div>
<h2>按任务类型</h2>
<table><thead><tr><th>类型</th><th>任务数</th><th>基准 Token</th><th>本技能 Token</th><th>省 Token</th><th>省时间(分)</th><th>Token节省%</th></tr></thead>
<tbody>{type_rows}</tbody></table>
<h2>按周趋势</h2>
<table><thead><tr><th>周</th><th>任务数</th><th>基准 Token</th><th>本技能 Token</th><th>省 Token</th></tr></thead>
<tbody>{week_rows}</tbody></table>
<p class="note">节省值为基于你填写的基准估计计算的参考值，用于建立提效体感，非平台计费数据。本报告全部本地生成，不含任何外部传输。</p>
</body></html>"""
    return html


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description="办公室提效账本报告生成器")
    ap.add_argument("--ledger", default="ledger.json", help="账本 JSON 路径（默认 ledger.json）")
    ap.add_argument("--out-dir", default="reports", help="报告输出目录（默认 reports/）")
    args = ap.parse_args()

    try:
        tasks = load_ledger(args.ledger)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2

    if not tasks:
        print("[提示] 账本为空，无可统计任务。", file=sys.stderr)
        return 1

    s = compute_summary(tasks)
    md = generate_markdown_report(s)
    html = generate_html_report(s)

    os.makedirs(args.out_dir, exist_ok=True)
    md_path = os.path.join(args.out_dir, "saving-report.md")
    html_path = os.path.join(args.out_dir, "saving-report.html")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[完成] 共 {s['n']} 条任务")
    print(f"  节省 Token : {fmt_int(s['saved_tok'])} ({fmt_pct(s['token_save_pct'])})")
    print(f"  节省时间   : {fmt_int(s['saved_min'])} 分钟 ({fmt_pct(s['time_save_pct'])})")
    print(f"  MD  -> {md_path}")
    print(f"  HTML-> {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
