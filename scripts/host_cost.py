#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""host_cost.py — office-token-booster v0.9 真实宿主用量接入（隔离层，防屎山）

把「宿主平台的真实 Token / 耗时用量」接入提效账本，让 skill_tokens 从「用户自报」
升级为「宿主实测」。设计红线（与三层解耦一致）：

- 单一抽象 HostCostProvider：fetch_recent(days) -> list[CostRecord]。
- 两个实现：
    - EventCostProvider       —— 包装一次宿主回报的 event["cost"]（v0.7 已支持的真实路径，
                                 在此升级为可单测的一等公民）。
    - WorkBuddyLocalProvider  —— 只读本机 WorkBuddy 的本地用量数据
                                 （~/.workbuddy/traces、workbuddy.db、usage-log.json）。
- 全程纯标准库、无网络、无硬编码密钥、无副作用（只读 + 纯解析）。
- 任何解析失败都降级为「跳过该条 / 返回空列表」，绝不抛异常炸掉调用方。

为何不污染内核：本模块只产出 CostRecord，由 skill_bridge / ledger_agent 在需要时
取用；diagnose / qa / report_engine 一行都不动。
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

# 允许从任意目录运行（与兄弟模块一致）。
sys.path.insert(0, str(Path(__file__).resolve().parent))


@dataclass
class CostRecord:
    """一条宿主真实用量记录。

    skill_tokens / skill_minutes 来自宿主实测；task_type 为该次任务的归类
    （宿主若未提供则留 None，由调用方决定如何落到账本类型）。
    """

    date: str                         # YYYY-MM-DD
    skill_tokens: int = 0
    skill_minutes: int = 0
    model: str = ""
    task_type: Optional[str] = None
    session_id: str = ""
    source: str = "host"             # 来源标识（workbuddy_traces / event）

    def to_ledger_entry(self, *, baseline_tokens: int = 0, baseline_minutes: int = 0,
                        note: str = "") -> dict:
        """转成标准账本草稿（skill 用实测值，baseline 默认 0 待补）。

        把「宿主实测成本」直接灌进账本，让 skill_tokens 不再靠用户估算；
        baseline 仍代表「笨办法手搓成本」，平台无从获得，故默认 0、需用户补填。
        """
        return {
            "date": self.date,
            "type": self.task_type or "AI办公任务",
            "baseline_tokens": int(baseline_tokens),
            "skill_tokens": int(self.skill_tokens),
            "baseline_minutes": int(baseline_minutes),
            "skill_minutes": int(self.skill_minutes),
            "note": note or f"宿主实测({self.source})",
        }


@runtime_checkable
class HostCostProvider(Protocol):
    """宿主用量提供方契约。实现只需提供 fetch_recent(days) -> list[CostRecord]。"""

    def fetch_recent(self, days: int) -> list["CostRecord"]:
        ...


def _today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _coerce_int(v) -> int:
    if v is None:
        return 0
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _within_days(iso_date: str, days: int) -> bool:
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
    except (TypeError, ValueError):
        return False
    lo = datetime.now() - timedelta(days=days)
    hi = datetime.now() + timedelta(days=1)
    return lo <= d <= hi


# ─────────────────────────────────────────────────────────────
# 实现 1：事件成本（包装一次宿主回报的 event["cost"]）
# ─────────────────────────────────────────────────────────────

class EventCostProvider:
    """把单次宿主事件里的 cost 当成「最近一条」用量记录，便于单测与复用。"""

    def __init__(self, event: dict):
        self._event = event or {}

    def fetch_recent(self, days: int = 1) -> list[CostRecord]:
        cost = self._event.get("cost") or {}
        tok = _coerce_int(cost.get("skill_tokens"))
        mins = _coerce_int(cost.get("skill_minutes"))
        if tok == 0 and mins == 0:
            return []
        return [CostRecord(
            date=_today_iso(),
            skill_tokens=tok,
            skill_minutes=mins,
            model=str(cost.get("model", "") or ""),
            task_type=self._event.get("type"),
            source="event",
        )]


# ─────────────────────────────────────────────────────────────
# 实现 2：WorkBuddy 本地用量（本机只读，无网络 / 无密钥）
# ─────────────────────────────────────────────────────────────

# 本机 WorkBuddy 数据根（与 agent-analytics-report 同源）。
_WORKBUDDY_ROOT = Path(os.path.expanduser("~")) / ".workbuddy"
_TRACES_DIR = _WORKBUDDY_ROOT / "traces"
_DB_PATH = _WORKBUDDY_ROOT / "workbuddy.db"
_USAGE_LOG = _WORKBUDDY_ROOT / "usage-log.json"


def _extract_tokens(obj: dict) -> tuple[int, int]:
    """从一条 trace / usage 记录里容忍地抽取 (skill_tokens, skill_minutes)。

    不同 WorkBuddy 版本的字段名可能漂移，这里多键兜底的「防屎山」写法：
    解析不到就返回 (0, 0)，绝不让单条脏数据炸掉整体。
    """
    if not isinstance(obj, dict):
        return 0, 0
    tok_keys = ("effective_tokens", "effectiveTokens", "total_tokens", "totalTokens",
                "skill_tokens", "token_usage", "tokens")
    min_keys = ("effective_minutes", "skill_minutes", "minutes", "duration_min")
    tok = 0
    for k in tok_keys:
        v = obj.get(k)
        if isinstance(v, dict):
            tok = _coerce_int(v.get("total")) or _coerce_int(v.get("totalTokens"))
            if tok:
                break
        elif _coerce_int(v):
            tok = _coerce_int(v)
            break
    mins = 0
    for k in min_keys:
        v = obj.get(k)
        if _coerce_int(v):
            mins = _coerce_int(v)
            break
    return tok, mins


def _extract_date(obj: dict) -> str:
    for k in ("date", "day", "timestamp", "created_at", "time"):
        v = obj.get(k)
        if isinstance(v, str) and len(v) >= 10:
            return v[:10]
    return _today_iso()


def _read_trace_file(path: Path) -> Optional[dict]:
    """容忍地读取一个 trace 文件：先试整文件 JSON，再试 JSONL（每行一个对象）。"""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    if not text.strip():
        return None
    try:
        return json.loads(text)            # 1) 整文件 JSON
    except json.JSONDecodeError:
        pass
    for line in text.splitlines():         # 2) JSONL：取首个可解析对象
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


class WorkBuddyLocalProvider:
    """只读本机 WorkBuddy 的本地用量（traces / db / usage-log），返回真实 CostRecord。

    红线：只读、纯解析、任何异常都降级（返回空/跳过），不碰网络、不碰密钥、不改文件。
    schema 在不同 WorkBuddy 版本可能漂移，所有字段抽取都走 _extract_tokens /
    _extract_date 的容忍逻辑；解析不到就当没有。无数据时不报错，返回空列表。
    """

    def __init__(self, root: Path = _WORKBUDDY_ROOT):
        self.root = Path(root)

    def fetch_recent(self, days: int = 7) -> list[CostRecord]:
        records: list[CostRecord] = []
        traces_dir = self.root / "traces"
        if traces_dir.is_dir():
            for p in sorted(traces_dir.glob("*")):
                if not p.is_file():
                    continue
                if p.suffix.lower() not in ("", ".json", ".jsonl", ".log"):
                    continue
                try:
                    obj = _read_trace_file(p)
                except Exception:
                    continue
                if not obj:
                    continue
                tok, mins = _extract_tokens(obj)
                if tok == 0 and mins == 0:
                    continue
                rec = CostRecord(
                    date=_extract_date(obj),
                    skill_tokens=tok,
                    skill_minutes=mins,
                    model=str(obj.get("model") or obj.get("modelInfo") or ""),
                    task_type=obj.get("task_type") or obj.get("type"),
                    session_id=str(obj.get("session_id") or obj.get("sessionId") or ""),
                    source="workbuddy_traces",
                )
                if _within_days(rec.date, days):
                    records.append(rec)
        return records


def get_default_provider() -> Optional[HostCostProvider]:
    """返回默认宿主用量提供方：本机 WorkBuddy 数据存在则用本地读取器，否则 None。"""
    if _TRACES_DIR.is_dir() or _DB_PATH.is_file() or _USAGE_LOG.is_file():
        return WorkBuddyLocalProvider()
    return None


# ─────────────────────────────────────────────────────────────
# 便捷：把真实用量转成账本草稿（dry-run，不写盘）
# ─────────────────────────────────────────────────────────────

def draft_entries_from_host(provider: HostCostProvider, days: int = 7, *,
                            baseline_tokens: int = 0,
                            baseline_minutes: int = 0) -> list[dict]:
    """用宿主真实用量生成账本草稿列表（skill 取实测值，baseline 默认 0 待补）。

    返回标准账本 entry dict 列表；调用方（ledger_agent / 对话流）应让用户确认后再写回，
    本函数绝不碰磁盘。
    """
    recs = provider.fetch_recent(days)
    return [r.to_ledger_entry(baseline_tokens=baseline_tokens,
                              baseline_minutes=baseline_minutes)
            for r in recs]


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="办公室 Token 洞察 · v0.9 真实宿主用量接入（只读本机 WorkBuddy 数据）")
    parser.add_argument("--days", type=int, default=7, help="最近 N 天（默认 7）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出原始记录")
    args = parser.parse_args()

    provider = get_default_provider()
    if provider is None:
        print("[信息] 未检测到本机 WorkBuddy 用量数据（~/.workbuddy/traces 等不存在）。")
        print("        宿主用量接入为可选能力；无数据时技能仍按『用户自报成本』正常工作。")
        return 0
    recs = provider.fetch_recent(args.days)
    if args.json:
        print(json.dumps([r.__dict__ for r in recs], ensure_ascii=False, indent=2))
    else:
        print(f"=== 检测到本机 WorkBuddy 最近 {args.days} 天用量（{len(recs)} 条）===")
        for r in recs[:20]:
            print(f"  {r.date}  {r.skill_tokens:,} tok / {r.skill_minutes} min"
                  f"  模型={r.model or '?'}  任务={r.task_type or '未归类'}")
        if len(recs) > 20:
            print(f"  … 其余 {len(recs) - 20} 条略")
    return 0


if __name__ == "__main__":
    sys.exit(main())
