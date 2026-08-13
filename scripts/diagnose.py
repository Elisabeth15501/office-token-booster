#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diagnose.py — office-token-booster 诊断内核（B 线）

纯函数内核：读取用户账本 -> 计算提效指标 -> 产出结构化 Diagnosis 对象。
不依赖任何渲染逻辑、无网络、无第三方依赖。

这是「对话式诊断」与「长链路 Agent」两个外壳共享的内核：
- 对话式诊断 = 内核 + 交互 Q&A 外壳（只读、响应式）
- 长链路 Agent = 内核 + 建议生成 + 写回动作（主动管道）
两者都只消费 Diagnosis 对象，互不耦合（见产品发展计划时间线 ADR-7 / 双产品线解耦）。

设计原则（与 agent-analytics-report 报告引擎一脉相承，但完全解耦）：
- 纯标准库，无第三方依赖、无网络、无硬编码密钥
- 数据源是用户主动提供的文件（ledger.json），不读取任何平台私有目录
- 节省值为参考估计，不是平台计费数据
"""

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


# 方法论说明（报告页脚反复出现，统一出口）。
# 核心：节省值是用户自报基准估计的参照值，非平台用量实测扣费；不调用任何外部 API。
METHODOLOGY_NOTE = (
    "方法论说明：本报告的「节省值」= 你填写的基准估计（不使用本技能、自己手搓 / 反复试错的成本）"
    "− 本技能实际消耗，均为你的主观参照估计，非平台用量实测扣费。本技能不调用任何外部 API "
    "测量 Token，仅读取你主动提供的账本文件（本地处理、零上传，符合 ADR-9）。"
)


def format_number(n):
    """数字格式化：K/M/G 后缀。内核与渲染共用。"""
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


def _safe_div(a, b):
    return (a / b) if b else 0.0


def load_ledger(path):
    """读取用户提供的账本 JSON，返回 tasks 列表。"""
    if not Path(path).is_file():
        raise FileNotFoundError(f"账本文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("ledger.json 顶层必须是 JSON 对象（含 tasks 数组）")
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        raise ValueError("ledger.json 顶层必须有 tasks 数组")
    return tasks


# ─────────────────────────────────────────────────────────────
# v0.8 提效洞察：周期对比 + 自动化 ROI 评分（纯函数，内核单一事实源）
# ─────────────────────────────────────────────────────────────

def compute_period_compare(by_week):
    """对比「最近一周 vs 上一周」的提效变化（消费已聚合的 by_week）。

    返回 dict：current/previous 的 saved_tokens/count/saved_minutes，以及
    各维度 delta / pct / direction（up/down/flat/new）。数据不足两周时返回 None。
    pct 在上一期为 0 时记为 None（避免除零，由 direction="new" 表达）。
    """
    if not by_week or len(by_week) < 2:
        return None
    cur, prev = by_week[-1], by_week[-2]

    def _pct(cur_v, prev_v):
        return None if prev_v == 0 else (cur_v - prev_v) / prev_v * 100

    saved_delta = cur["saved_tokens"] - prev["saved_tokens"]
    if prev["saved_tokens"] == 0 and cur["saved_tokens"] > 0:
        direction = "new"
    elif saved_delta > 0:
        direction = "up"
    elif saved_delta < 0:
        direction = "down"
    else:
        direction = "flat"

    return {
        "current_week": cur["week"],
        "previous_week": prev["week"],
        "current": {"saved_tokens": cur["saved_tokens"], "count": cur["count"],
                    "saved_minutes": cur["saved_minutes"]},
        "previous": {"saved_tokens": prev["saved_tokens"], "count": prev["count"],
                     "saved_minutes": prev["saved_minutes"]},
        "saved_tokens_delta": saved_delta,
        "saved_tokens_pct": _pct(cur["saved_tokens"], prev["saved_tokens"]),
        "count_delta": cur["count"] - prev["count"],
        "count_pct": _pct(cur["count"], prev["count"]),
        "saved_minutes_delta": cur["saved_minutes"] - prev["saved_minutes"],
        "saved_minutes_pct": _pct(cur["saved_minutes"], prev["saved_minutes"]),
        "direction": direction,
    }


# 自动化接入成本启发式（人时/类型）：演示用默认值，后续可由 config.yaml 覆盖。
ROI_EFFORT_HOURS = 4


def compute_roi_targets(by_type, span_days=None):
    """给每个任务类型算「自动化 ROI 评分」，输出按 ROI 降序的待自动化清单。

    roi_score = 月度节省 Token / 接入成本(人时)
      - 月度节省 = 累计节省 × (30 / 记录跨度天)，把已有数据外推到一月
      - 接入成本 = ROI_EFFORT_HOURS（默认 4 人时/类型，演示启发式）
    纯函数，仅依赖 by_type 聚合值，不读取任何外部配置。
    """
    if not by_type:
        return []
    sd = span_days if (span_days and span_days > 0) else 30
    targets = []
    for d in by_type:
        cnt = d.get("count", 0) or 0
        saved = d.get("saved_tokens", 0) or 0
        avg_base = (d.get("baseline_tokens", 0) or 0) / cnt if cnt else 0
        monthly_saved = saved * (30.0 / sd)
        roi = monthly_saved / ROI_EFFORT_HOURS if ROI_EFFORT_HOURS else 0
        targets.append({
            "task_type": d["task_type"],
            "count": cnt,
            "saved_tokens": saved,
            "avg_base_tokens": round(avg_base),
            "monthly_saved_tokens": round(monthly_saved),
            "effort_hours": ROI_EFFORT_HOURS,
            "roi_score": round(roi, 1),
        })
    targets.sort(key=lambda x: x["roi_score"], reverse=True)
    return targets


def compute_summary(tasks):
    """把 tasks 汇总为结构化摘要（dict）。diagnose() 会包装为 Diagnosis。"""
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

    # 记录周期跨度（天）：用于把累计节省外推到「月度」计算 ROI
    _dates = []
    for t in tasks:
        try:
            _dates.append(datetime.strptime(t["date"], "%Y-%m-%d"))
        except (ValueError, TypeError, KeyError):
            pass
    span_days = (max(_dates) - min(_dates)).days + 1 if len(_dates) >= 2 else 0

    period_compare = compute_period_compare(by_week)
    roi_targets = compute_roi_targets(by_type, span_days)

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
        "span_days": span_days,
        "period_compare": period_compare,
        "roi_targets": roi_targets,
        "tasks": tasks,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def build_insights(s):
    """根据汇总产出办公域洞察与建议。返回 (insights, recommendations)。"""
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

    # v0.8：自动化 ROI 优先序（消费内核已算好的 roi_targets）
    if s.get("roi_targets"):
        top_roi = s["roi_targets"][0]
        recs.append(
            f"按自动化 ROI 排序，优先做成可复用模板的是「{top_roi['task_type']}」"
            f"（预估月省 {format_number(top_roi['monthly_saved_tokens'])} Token，"
            f"接入成本约 {top_roi['effort_hours']} 人时，ROI≈{top_roi['roi_score']}）。"
        )

    return insights, recs


def detect_baseline_anomalies(tasks):
    """轻量护栏：识别可能拉高「提效」可信度风险的账本填写问题。

    返回中文提示列表（caveats）。目的不是纠错，而是让报告在评委 / 用户面前
    主动暴露「节省值是自报参照」这一前提，避免虚高数字被当成实测扣费。
    """
    caveats = []

    # 1) 零 / 负节省：技能 Token 与基准持平或更高 -> 该任务未体现提效
    for t in tasks:
        bt = t.get("baseline_tokens", 0) or 0
        st = t.get("skill_tokens", 0) or 0
        ty = t.get("type", "其他")
        date = t.get("date", "")
        if bt > 0 and st >= bt:
            if st == 0:
                caveats.append(
                    f"任务「{ty} @ {date}」技能 Token 为 0，节省率记为 100%，"
                    f"可能存在漏填或基线估计偏高，建议复核。"
                )
            else:
                caveats.append(
                    f"任务「{ty} @ {date}」技能 Token（{format_number(st)}）与基准"
                    f"（{format_number(bt)}）持平或更高，该任务未体现提效，请确认填写。"
                )

    # 2) 基线离群：单条基准显著高于「整体中位数」3 倍 -> 估计可能偏高
    #    （全局口径，可捕获「仅出现一次的高基线任务」，比同类口径更稳）
    baselines = [t.get("baseline_tokens", 0) or 0 for t in tasks if (t.get("baseline_tokens", 0) or 0) > 0]
    if len(baselines) >= 2:
        med = statistics.median(baselines)
        if med > 0:
            for t in tasks:
                bt = t.get("baseline_tokens", 0) or 0
                ty = t.get("type", "其他")
                date = t.get("date", "")
                if bt > 3 * med:
                    caveats.append(
                        f"任务「{ty} @ {date}」基准 Token（{format_number(bt)}）显著高于整体中位数"
                        f"（{format_number(med)}），估计可能偏高，拉高了整体节省率。"
                    )
                    break  # 只报一次，避免噪声

    # 3) 整体极高节省率 -> 提示基准是否保守（不论样本量，只给温和提醒）
    total_base = sum(t.get("baseline_tokens", 0) or 0 for t in tasks)
    total_skill = sum(t.get("skill_tokens", 0) or 0 for t in tasks)
    if total_base > 0:
        overall_pct = (total_base - total_skill) / total_base * 100
        if overall_pct > 85:
            sample_note = "（样本较少时尤其需复核）" if len(tasks) <= 3 else ""
            caveats.append(
                f"整体 Token 节省率高达 {overall_pct:.1f}%{sample_note}，"
                f"请确认「基准」是否为真实手搓成本，避免高估提效。"
            )

    return caveats


@dataclass
class Diagnosis:
    """诊断内核的结构化输出契约。渲染层（report_engine）与对话层（qa）共享此对象。

    同时支持属性访问（diag.saved_tok）与字典式访问（diag["saved_tok"]），
    便于渲染代码最小改动地复用。"""
    n: int = 0
    total_base_tok: int = 0
    total_skill_tok: int = 0
    total_base_min: int = 0
    total_skill_min: int = 0
    saved_tok: int = 0
    saved_min: int = 0
    token_save_pct: float = 0.0
    time_save_pct: float = 0.0
    by_type: list = field(default_factory=list)
    by_week: list = field(default_factory=list)
    span_days: int = 0
    period_compare: dict = None
    roi_targets: list = field(default_factory=list)
    insights: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    caveats: list = field(default_factory=list)
    methodology: str = METHODOLOGY_NOTE
    tasks: list = field(default_factory=list)
    generated_at: str = ""

    def __getitem__(self, key):
        # 缺失键抛 KeyError（而非 getattr 默认的 AttributeError），
        # 与 .get(key, default) 的语义一致，外部 diag["foo"] 报错信息不再误导（修复 L1）。
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key) from None

    def get(self, key, default=None):
        return getattr(self, key, default)

    def to_dict(self):
        return asdict(self)


def diagnose(tasks):
    """纯函数内核：tasks（list[dict]）-> Diagnosis。

    不读取文件、不渲染、无副作用，可被对话式诊断与长链路 Agent 复用。
    """
    s = compute_summary(tasks)
    insights, recs = build_insights(s)
    caveats = detect_baseline_anomalies(tasks)
    return Diagnosis(
        n=s["n"],
        total_base_tok=s["total_base_tok"],
        total_skill_tok=s["total_skill_tok"],
        total_base_min=s["total_base_min"],
        total_skill_min=s["total_skill_min"],
        saved_tok=s["saved_tok"],
        saved_min=s["saved_min"],
        token_save_pct=s["token_save_pct"],
        time_save_pct=s["time_save_pct"],
        by_type=s["by_type"],
        by_week=s["by_week"],
        span_days=s["span_days"],
        period_compare=s["period_compare"],
        roi_targets=s["roi_targets"],
        insights=insights,
        recommendations=recs,
        caveats=caveats,
        tasks=s["tasks"],
        generated_at=s["generated_at"],
    )
