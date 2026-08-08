#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""report_engine.py — 办公室提效账本报告生成器（office-token-booster / B 线）

读取用户主动提供的「提效账本」JSON（ledger.json），量化「笨办法 vs 本技能」节省的
Token 与耗时，生成 Markdown / HTML / JSON 报告。

设计原则（与 agent-analytics-report 报告引擎一脉相承，但完全解耦）：
- 纯标准库，无第三方依赖、无网络、无硬编码密钥
- 数据源是用户主动提供的文件（ledger.json），不读取任何平台私有目录
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

# ---------------------------------------------------------------------------
# FORK NOTE (office-token-booster / B 线):
# 本文件从 agent-analytics-report/scripts/generate_report.py fork 而来（ADR-7 双产品线独立）。
# 已剥离 WorkBuddy 数据源耦合：移除 collect_usage_data 运行时导入与 main() 实时采集分支，
# 中性化 pricing.json 引用（ADR-9：B 线默认走「用户上传/导出数据」模式，不依赖天禧/WorkBuddy 用量 API）。
# 下方报告函数已适配 office ledger 数据（消费 token/耗时/任务类型），作为 B 线唯一报告生成器。
# 通用渲染原语（format_number / _pad_label / build_donut_chart 等）沿用 A 引擎。
# ---------------------------------------------------------------------------

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────────
# 通用工具（沿用 A 引擎渲染原语）
# ─────────────────────────────────────────────────────────────

def format_number(n):
    """数字格式化：K/M/G 后缀"""
    if n is None:
        return "0"
    n = float(n)
    if n >= 1_000_000_000:
        return f"{n / 1e9:.2f}G"
    elif n >= 1_000_000:
        return f"{n / 1e6:.2f}M"
    elif n >= 1_000:
        return f"{n / 1e3:.1f}K"
    return str(int(n)) if n == int(n) else f"{n:.1f}"


def _disp_width(s):
    """等宽字体下的显示宽度：CJK / 全角字符计 2，其余计 1。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in str(s))


def _pad_label(s, width):
    """按显示宽度右侧补空格，使等宽字体下中文 / 英文混排的标签列对齐。"""
    return str(s) + " " * max(0, width - _disp_width(s))


# 环形图调色板（与表格配色协调）
_DONUT_PALETTE = [
    "#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6",
    "#1abc9c", "#e67e22", "#34495e", "#16a085", "#c0392b",
    "#8e44ad", "#27ae60",
]


def build_donut_chart(stats, title="节省 Token 占比（按任务类型）",
                      center_label="节省 Token", value_key="saved_tokens", unit=""):
    """生成自包含内联 SVG 环形图（currentColor + CSS 变量，浅/深主题兼容）。

    stats: 含 task_type 与各数值字段的列表。value_key 指定扇形取值字段。
    无数据时返回空串；不依赖外部 CDN。
    """
    items = [s for s in stats if s.get(value_key, 0) > 0]
    total = sum(s.get(value_key, 0) for s in items)
    if total <= 0:
        return ""
    items = sorted(items, key=lambda x: x.get(value_key, 0), reverse=True)

    cx, cy, r, sw = 110, 110, 80, 34
    circ = 2 * math.pi * r
    cum = 0.0
    arcs = []
    legend = []
    for i, s in enumerate(items):
        frac = s.get(value_key, 0) / total
        seg_len = frac * circ
        color = _DONUT_PALETTE[i % len(_DONUT_PALETTE)]
        pct = frac * 100
        arcs.append(
            f'        <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" '
            f'stroke-dasharray="{seg_len:.2f} {circ - seg_len:.2f}" '
            f'stroke-dashoffset="{-cum:.2f}" />'
        )
        legend.append(
            f'            <div class="legend-item">'
            f'<span class="swatch" style="background:{color}"></span>'
            f'{s["task_type"]}：{pct:.1f}%'
            f'<span class="pct">（{format_number(s.get(value_key, 0))}{unit}）</span></div>'
        )
        cum += seg_len

    svg = f"""    <div class="chart-pie">
        <svg width="220" height="220" viewBox="0 0 220 220" role="img" aria-label="{title}">
            <g transform="rotate(-90 {cx} {cy})">
                <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" style="stroke:var(--table-border)" stroke-width="{sw}" />
{chr(10).join(arcs)}
            </g>
            <text x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="15" font-weight="bold" style="fill:var(--accent-fg)">{format_number(total)}</text>
            <text x="{cx}" y="{cy + 14}" text-anchor="middle" font-size="11" style="fill:var(--muted)">{center_label}</text>
        </svg>
        <div class="legend">
{chr(10).join(legend)}
        </div>
    </div>"""
    return svg


def build_saving_chart_md(by_type, value_key="saved_tokens", title="各任务类型 节省 Token 分布"):
    """Markdown 横向条形图（fenced ``` 代码块）：各任务类型节省量分布。"""
    items = [d for d in by_type if d.get(value_key, 0) > 0]
    if not items:
        return ""
    items = sorted(items, key=lambda x: x.get(value_key, 0), reverse=True)[:10]
    total = sum(d.get(value_key, 0) for d in items) or 1
    maxv = max(d.get(value_key, 0) for d in items) or 1
    bar_w = 32
    label_w = 16
    out = [f"**{title}**", ""]
    for d in items:
        v = d.get(value_key, 0)
        pct = v / total * 100
        n = max(int(bar_w * v / maxv), 1)
        bar = "█" * n
        out.append(f"{_pad_label(d['task_type'], label_w)} | {bar} {pct:.1f}% ({format_number(v)})")
    return "```\n" + "\n".join(out) + "\n```"


# ─────────────────────────────────────────────────────────────
# 办公数据层（消费 ledger.json）
# ─────────────────────────────────────────────────────────────

def load_ledger(path):
    """读取用户提供的账本 JSON，返回 tasks 列表。"""
    if not Path(path).is_file():
        raise FileNotFoundError(f"账本文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        raise ValueError("ledger.json 顶层必须有 tasks 数组")
    return tasks


def _safe_div(a, b):
    return (a / b) if b else 0.0


def compute_summary(tasks):
    """把 tasks 汇总为报告所需的摘要结构。"""
    total_base_tok = sum(t.get("baseline_tokens", 0) or 0 for t in tasks)
    total_skill_tok = sum(t.get("skill_tokens", 0) or 0 for t in tasks)
    total_base_min = sum(t.get("baseline_minutes", 0) or 0 for t in tasks)
    total_skill_min = sum(t.get("skill_minutes", 0) or 0 for t in tasks)
    n = len(tasks)

    saved_tok = total_base_tok - total_skill_tok
    saved_min = total_base_min - total_skill_min

    # 按任务类型聚合
    by_type_map = {}
    for t in tasks:
        ty = t.get("type", "其他")
        d = by_type_map.setdefault(ty, {"task_type": ty, "baseline_tokens": 0, "skill_tokens": 0,
                                       "baseline_minutes": 0, "skill_minutes": 0, "count": 0})
        d["baseline_tokens"] += t.get("baseline_tokens", 0) or 0
        d["skill_tokens"] += t.get("skill_tokens", 0) or 0
        d["baseline_minutes"] += t.get("baseline_minutes", 0) or 0
        d["skill_minutes"] += t.get("skill_minutes", 0) or 0
        d["count"] += 1

    by_type = []
    for ty, d in by_type_map.items():
        d["saved_tokens"] = d["baseline_tokens"] - d["skill_tokens"]
        d["saved_minutes"] = d["baseline_minutes"] - d["skill_minutes"]
        d["token_save_pct"] = _safe_div(d["saved_tokens"], d["baseline_tokens"]) * 100
        d["time_save_pct"] = _safe_div(d["saved_minutes"], d["baseline_minutes"]) * 100
        by_type.append(d)
    by_type.sort(key=lambda x: x["saved_tokens"], reverse=True)

    # 按周聚合（取 date 的 ISO 周）
    by_week_map = {}
    for t in tasks:
        date = t.get("date", "")
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            wk = dt.strftime("%Y-W%V")
        except (ValueError, TypeError):
            wk = "未知周"
        w = by_week_map.setdefault(wk, {"week": wk, "baseline_tokens": 0, "skill_tokens": 0,
                                        "baseline_minutes": 0, "skill_minutes": 0, "count": 0})
        w["baseline_tokens"] += t.get("baseline_tokens", 0) or 0
        w["skill_tokens"] += t.get("skill_tokens", 0) or 0
        w["baseline_minutes"] += t.get("baseline_minutes", 0) or 0
        w["skill_minutes"] += t.get("skill_minutes", 0) or 0
        w["count"] += 1

    by_week = []
    for wk, w in by_week_map.items():
        w["saved_tokens"] = w["baseline_tokens"] - w["skill_tokens"]
        w["saved_minutes"] = w["baseline_minutes"] - w["skill_minutes"]
        w["token_save_pct"] = _safe_div(w["saved_tokens"], w["baseline_tokens"]) * 100
        by_week.append(w)
    by_week.sort(key=lambda x: x["week"])

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
        "by_week": by_week,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ─────────────────────────────────────────────────────────────
# 核心洞察（办公域）
# ─────────────────────────────────────────────────────────────

def build_insights(s):
    """根据汇总产出办公域洞察与建议。返回 (insights, recommendations) 两个列表。"""
    insights = []
    recs = []

    if s["n"] == 0:
        return ["账本为空，暂无提效数据。"], ["先记录 1~2 周的任务账本，再生成报告。"]

    insights.append(
        f"本期共 {s['n']} 条任务，合计节省 **{format_number(s['saved_tok'])} Token**"
        f"（省 {s['token_save_pct']:.1f}%），节省 **{format_number(s['saved_min'])} 分钟**"
        f"（省 {s['time_save_pct']:.1f}%）。"
    )

    if s["by_type"]:
        top = s["by_type"][0]
        insights.append(
            f"「{top['task_type']}」是提效主力：{top['count']} 次任务节省 "
            f"{format_number(top['saved_tokens'])} Token（省 {top['token_save_pct']:.1f}%）。"
        )
        # 找基线最高的类型（最值得自动化的场景）
        hottest = max(s["by_type"], key=lambda x: x["baseline_tokens"])
        recs.append(
            f"优先把「{hottest['task_type']}」类重复任务交给技能：其单次基线约 "
            f"{format_number(hottest['baseline_tokens'] / max(hottest['count'], 1))} Token，"
            f"自动化空间最大。"
        )

    if s["token_save_pct"] >= 50:
        insights.append("整体提效显著（Token 节省 ≥ 50%），技能化已明显见效。")
    elif s["token_save_pct"] < 20 and s["n"] >= 3:
        insights.append("Token 节省偏低，可能部分任务本身已较精简，或基线估计偏高。")
        recs.append("回顾基线估计是否合理：基线应是「自己手搓 / 反复试错」的真实成本。")

    recs.append("保持「本地处理、不上传内容」的合规优势，作为对外可演示的差异化卖点。")
    return insights, recs


# ─────────────────────────────────────────────────────────────
# Markdown 报告（九段结构，办公域适配）
# ─────────────────────────────────────────────────────────────

def generate_markdown_report(s):
    L = []
    L.append("# 办公室提效报告")
    L.append("")
    L.append(f"> 生成时间：{s['generated_at']} ｜ 共 {s['n']} 条任务记录")
    L.append("")

    # 一、概览
    L.append("## 一、概览")
    L.append("")
    L.append(f"- **节省 Token**：{format_number(s['saved_tok'])}（基准 {format_number(s['total_base_tok'])} → 本技能 {format_number(s['total_skill_tok'])}），节省 **{s['token_save_pct']:.1f}%**")
    L.append(f"- **节省时间**：{format_number(s['saved_min'])} 分钟（基准 {format_number(s['total_base_min'])} → 本技能 {format_number(s['total_skill_min'])}），节省 **{s['time_save_pct']:.1f}%**")
    L.append("")

    # 二、Token 提效可视化
    L.append("## 二、Token 提效可视化")
    L.append("")
    L.append(build_saving_chart_md(s["by_type"]))
    L.append("")

    # 三、任务类型统计
    L.append("## 三、任务类型统计")
    L.append("")
    L.append("| 类型 | 任务数 | 基准 Token | 本技能 Token | 省 Token | 省时间(分) | Token节省% |")
    L.append("|------|------|------|------|------|------|------|")
    for d in s["by_type"]:
        L.append(f"| {d['task_type']} | {d['count']} | {format_number(d['baseline_tokens'])} | {format_number(d['skill_tokens'])} | "
                 f"{format_number(d['saved_tokens'])} | {format_number(d['saved_minutes'])} | {d['token_save_pct']:.1f}% |")
    L.append("")

    # 四、任务 Token 消耗统计
    L.append("## 四、任务 Token 消耗统计")
    L.append("")
    L.append("| 类型 | 基准 Token | 本技能 Token | 节省 Token | 节省占比 |")
    L.append("|------|------|------|------|------|")
    for d in s["by_type"]:
        L.append(f"| {d['task_type']} | {format_number(d['baseline_tokens'])} | {format_number(d['skill_tokens'])} | "
                 f"{format_number(d['saved_tokens'])} | {d['token_save_pct']:.1f}% |")
    L.append("")

    # 五、能力 / 场景使用统计
    L.append("## 五、能力 / 场景使用统计")
    L.append("")
    L.append("> 按调用次数看各办公能力的使用频度，识别高频场景。")
    L.append("")
    L.append("| 能力 / 场景 | 调用次数 | 占总任务比 |")
    L.append("|------|------|------|")
    for d in s["by_type"]:
        ratio = _safe_div(d["count"], s["n"]) * 100
        L.append(f"| {d['task_type']} | {d['count']} | {ratio:.1f}% |")
    L.append("")

    # 六、任务执行情况
    L.append("## 六、任务执行情况")
    L.append("")
    L.append("| 日期 | 类型 | 基准(min) | 技能(min) | 省(min) | 基准(tok) | 技能(tok) | 省(tok) |")
    L.append("|------|------|------|------|------|------|------|------|")
    # 这里需要原始 tasks；compute_summary 不保留，改为在 main 注入
    for t in s.get("_tasks", []):
        bt = t.get("baseline_tokens", 0) or 0
        st = t.get("skill_tokens", 0) or 0
        bm = t.get("baseline_minutes", 0) or 0
        sm = t.get("skill_minutes", 0) or 0
        L.append(f"| {t.get('date','')} | {t.get('type','')} | {bm} | {sm} | {bm-sm} | {format_number(bt)} | {format_number(st)} | {format_number(bt-st)} |")
    L.append("")

    # 七、产出物清单
    L.append("## 七、产出物清单")
    L.append("")
    for i, t in enumerate(s.get("_tasks", []), 1):
        note = t.get("note") or "（无备注）"
        L.append(f"{i}. `{t.get('date','')}` ｜ {t.get('type','')} ｜ {note}")
    L.append("")

    # 八、核心洞察与建议
    insights, recs = build_insights(s)
    L.append("## 八、核心洞察与建议")
    L.append("")
    L.append("**洞察**")
    L.append("")
    for x in insights:
        L.append(f"- {x}")
    L.append("")
    L.append("**建议**")
    L.append("")
    for x in recs:
        L.append(f"- {x}")
    L.append("")

    # 九、下周展望
    L.append("## 九、下周展望")
    L.append("")
    L.append("- 持续记录任务账本，观察节省趋势是否稳定。")
    L.append("- 对高频 / 高基线场景沉淀为可复用提示词模板，进一步压缩技能 Token。")
    L.append("- 若参加「天禧 AI Skills 苍穹共创计划」，本报告的「本地处理、零上传」可作为合规卖点。")
    L.append("")
    L.append("---")
    L.append("*节省值为基于你填写的基准估计计算的参考值，用于建立提效体感，非平台计费数据。*")
    return "\n".join(L)


# ─────────────────────────────────────────────────────────────
# HTML 报告
# ─────────────────────────────────────────────────────────────

def _bar_html(value, max_value, color="#2ecc71"):
    w = int(_safe_div(value, max_value) * 100)
    w = max(2, min(100, w))
    return (f'<div style="background:#f3f4f6;border-radius:4px;height:14px;width:100%;">'
            f'<div style="background:{color};height:14px;border-radius:4px;width:{w}%;"></div></div>')


def generate_html_report(s):
    donut = build_donut_chart(s["by_type"], title="各任务类型 节省 Token 占比",
                              center_label="节省 Token", value_key="saved_tokens")
    insights, recs = build_insights(s)

    type_rows = ""
    max_tok = max((d["baseline_tokens"] for d in s["by_type"]), default=1) or 1
    for d in s["by_type"]:
        type_rows += (
            f'<tr><td>{d["task_type"]}</td><td>{d["count"]}</td>'
            f'<td>{format_number(d["baseline_tokens"])}</td><td>{format_number(d["skill_tokens"])}</td>'
            f'<td>{format_number(d["saved_tokens"])}</td><td>{format_number(d["saved_minutes"])}</td>'
            f'<td>{d["token_save_pct"]:.1f}%</td></tr>'
        )

    week_rows = ""
    for w in s["by_week"]:
        week_rows += (f'<tr><td>{w["week"]}</td><td>{w["count"]}</td>'
                      f'<td>{format_number(w["baseline_tokens"])}</td><td>{format_number(w["skill_tokens"])}</td>'
                      f'<td>{format_number(w["saved_tokens"])}</td></tr>')

    insight_html = "".join(f"<li>{x}</li>" for x in insights)
    rec_html = "".join(f"<li>{x}</li>" for x in recs)

    task_rows = ""
    for t in s.get("_tasks", []):
        bt = t.get("baseline_tokens", 0) or 0
        st = t.get("skill_tokens", 0) or 0
        bm = t.get("baseline_minutes", 0) or 0
        sm = t.get("skill_minutes", 0) or 0
        task_rows += (f'<tr><td>{t.get("date","")}</td><td>{t.get("type","")}</td>'
                      f'<td>{bm}</td><td>{sm}</td><td>{bm-sm}</td>'
                      f'<td>{format_number(bt)}</td><td>{format_number(st)}</td>'
                      f'<td>{format_number(bt-st)}</td></tr>')

    css = """
    :root{--bg:#fff;--fg:#111827;--muted:#6b7280;--table-border:#e5e7eb;
          --accent:#22c55e;--accent-fg:#111827;}
    body{font-family:-apple-system,Segoe UI,Roboto,'Microsoft YaHei',sans-serif;
         max-width:920px;margin:24px auto;padding:0 16px;color:var(--fg);}
    h1{font-size:22px;} h2{font-size:17px;margin-top:28px;border-left:4px solid var(--accent);padding-left:8px;}
    .cards{display:flex;gap:16px;flex-wrap:wrap;margin:16px 0;}
    .card{flex:1;min-width:180px;background:#f9fafb;border:1px solid var(--table-border);
          border-radius:10px;padding:14px;}
    .card .big{font-size:24px;font-weight:700;} .card .sub{color:var(--muted);font-size:13px;}
    .chart-pie{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin:12px 0;}
    .legend{font-size:13px;} .legend-item{margin:2px 0;}
    .swatch{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;}
    table{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px;}
    th,td{border:1px solid var(--table-border);padding:6px 8px;text-align:right;}
    th:first-child,td:first-child{text-align:left;}
    th{background:#f3f4f6;} .note{color:var(--muted);font-size:12px;margin-top:18px;}
    ul{margin:6px 0;}
    """

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>办公室提效报告</title>
<style>{css}</style></head><body>
<h1>办公室提效报告</h1>
<p style="color:var(--muted)">生成时间：{s['generated_at']} ｜ 共 {s['n']} 条任务记录</p>
<div class="cards">
  <div class="card"><div class="big">{format_number(s['saved_tok'])}</div><div class="sub">节省 Token（基准 {format_number(s['total_base_tok'])} → 本技能 {format_number(s['total_skill_tok'])}，省 {s['token_save_pct']:.1f}%）</div></div>
  <div class="card"><div class="big">{format_number(s['saved_min'])} 分</div><div class="sub">节省时间（基准 {format_number(s['total_base_min'])} → 本技能 {format_number(s['total_skill_min'])}，省 {s['time_save_pct']:.1f}%）</div></div>
  <div class="card" style="display:flex;align-items:center;justify-content:center;">{donut}</div>
</div>

<h2>一、任务类型统计</h2>
<table><thead><tr><th>类型</th><th>任务数</th><th>基准 Token</th><th>本技能 Token</th><th>省 Token</th><th>省时间(分)</th><th>Token节省%</th></tr></thead>
<tbody>{type_rows}</tbody></table>

<h2>二、按周趋势</h2>
<table><thead><tr><th>周</th><th>任务数</th><th>基准 Token</th><th>本技能 Token</th><th>省 Token</th></tr></thead>
<tbody>{week_rows}</tbody></table>

<h2>三、任务执行情况</h2>
<table><thead><tr><th>日期</th><th>类型</th><th>基准(min)</th><th>技能(min)</th><th>省(min)</th><th>基准(tok)</th><th>技能(tok)</th><th>省(tok)</th></tr></thead>
<tbody>{task_rows}</tbody></table>

<h2>四、核心洞察与建议</h2>
<p><strong>洞察</strong></p><ul>{insight_html}</ul>
<p><strong>建议</strong></p><ul>{rec_html}</ul>

<p class="note">节省值为基于你填写的基准估计计算的参考值，用于建立提效体感，非平台计费数据。本报告全部本地生成，不含任何外部传输。</p>
</body></html>"""
    return html


# ─────────────────────────────────────────────────────────────
# JSON 报告
# ─────────────────────────────────────────────────────────────

def generate_json_report(s):
    out = dict(s)
    out.pop("_tasks", None)
    return json.dumps(out, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="办公室提效账本报告生成器（office-token-booster）")
    parser.add_argument("data_file", nargs="?", help="账本 JSON 路径（未提供则尝试读取当前目录 ledger.json；B 线仅支持用户上传/导出的数据文件，ADR-9）")
    parser.add_argument("--ledger", dest="data_file", help="账本 JSON 路径（同 data_file）")
    parser.add_argument("--output", "-o", type=str, help="输出文件路径")
    parser.add_argument("--format", type=str, default="markdown",
                        choices=["markdown", "html", "json"], help="输出格式")
    args = parser.parse_args()

    if not args.data_file:
        _default_ledger = Path("ledger.json")
        if _default_ledger.is_file():
            args.data_file = str(_default_ledger)
    if not args.data_file:
        print("[错误] B 线（office-token-booster）仅支持读取用户上传/导出的数据文件（ADR-9），"
              "不实时采集 WorkBuddy 用量。用法: python report_engine.py <ledger.json> [--format markdown|html|json]",
              file=sys.stderr)
        return 2

    try:
        tasks = load_ledger(args.data_file)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2

    if not tasks:
        print("[提示] 账本为空，无可统计任务。", file=sys.stderr)
        return 1

    s = compute_summary(tasks)
    s["_tasks"] = tasks  # 供明细段落使用（JSON 输出会剔除）

    if args.format == "markdown":
        report = generate_markdown_report(s)
    elif args.format == "html":
        report = generate_html_report(s)
    else:
        report = generate_json_report(s)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"[OK] 报告已保存到 {args.output}", file=sys.stderr)
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
