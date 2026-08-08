#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qa.py — 对话式诊断的「追问」外壳（office-token-booster / B 线）

消费诊断内核产出的 Diagnosis 对象，对用户的追问给出**基于账本数据**的应答，
避免大模型凭空编造数字（grounding）。这是「对话式诊断」骨架的追问层：
先 show 一页摘要 + 图表（report_engine），再在追问时调用本模块做数据接地。

用法：
  python qa.py <ledger.json> "哪个任务类型节省最多？"

  或在 Python 中：
  from diagnose import load_ledger, diagnose
  from qa import answer_followup
  diag = diagnose(load_ledger("ledger.json"))
  print(answer_followup(diag, "每周节省趋势如何？"))
"""

import argparse
import sys

from diagnose import load_ledger, diagnose, format_number


def _top_type(diag):
    return diag.by_type[0] if diag.by_type else None


def _hottest_type(diag):
    return max(diag.by_type, key=lambda x: x["baseline_tokens"]) if diag.by_type else None


def answer_followup(diag, question):
    """基于 Diagnosis 结构化数据应答常见追问。返回中文文本（已接地，不编造）。"""
    q = (question or "").strip()
    if not q:
        return "请提出一个关于账本的具体问题，例如：节省最多的任务类型是什么？"

    if diag.n == 0:
        return "账本为空，暂无可分析的数据。请先记录任务账本。"

    # 总节省 / 概览
    if any(k in q for k in ("总共", "合计", "总节省", "一共", "总体", "概览")):
        return (
            f"共 {diag.n} 条任务，合计节省 {format_number(diag.saved_tok)} Token"
            f"（省 {diag.token_save_pct:.1f}%）、{format_number(diag.saved_min)} 分钟"
            f"（省 {diag.time_save_pct:.1f}%）。"
        )

    # 节省比例
    if any(k in q for k in ("比例", "百分比", "省了", "省多少", "%")):
        return (f"Token 节省比例 {diag.token_save_pct:.1f}%，"
                f"时间节省比例 {diag.time_save_pct:.1f}%。")

    # 哪个类型节省最多
    if any(k in q for k in ("最多", "最高", "主力", "第一", "最大", "top", "Top")):
        top = _top_type(diag)
        if top:
            return (f"节省最多的任务类型是「{top['task_type']}」：{top['count']} 次共省 "
                    f"{format_number(top['saved_tokens'])} Token（省 {top['token_save_pct']:.1f}%）。")
        return "暂无可统计的任务类型。"

    # 最值得自动化 / 基线最高的场景
    if any(k in q for k in ("值得", "自动化", "优先", "场景", "推荐做", "哪些任务")):
        hot = _hottest_type(diag)
        if hot:
            return (f"基线成本最高、最值得自动化的是「{hot['task_type']}」：单次基线约 "
                    f"{format_number(hot['baseline_tokens'] / max(hot['count'], 1))} Token，"
                    f"自动化空间最大。")
        return "暂无可分析的任务类型。"

    # 按周趋势
    if any(k in q for k in ("周", "趋势", "变化", "每周", "时间")):
        if not diag.by_week:
            return "账本中没有可用的日期信息，无法按周分析。"
        lines = ["按周节省 Token："]
        for w in diag.by_week:
            lines.append(f"- {w['week']}：{w['count']} 次任务，省 "
                         f"{format_number(w['saved_tokens'])} Token（省 {w['token_save_pct']:.1f}%）")
        return "\n".join(lines)

    # 建议
    if any(k in q for k in ("建议", "怎么", "如何", "下一步", "优化", "改进")):
        if not diag.recommendations:
            return "暂无建议。"
        return "建议：\n" + "\n".join(f"- {r}" for r in diag.recommendations)

    # 洞察
    if any(k in q for k in ("洞察", "发现", "结论", "看出来", "总结")):
        if not diag.insights:
            return "暂无洞察。"
        return "洞察：\n" + "\n".join(f"- {x}" for x in diag.insights)

    # 兜底
    return (
        "我只能基于你提供的账本数据回答。你可以问我：\n"
        "- 总共节省了多少？\n"
        "- 哪个任务类型节省最多？\n"
        "- 哪个场景最值得自动化？\n"
        "- 按周趋势如何？\n"
        "- 有什么建议 / 洞察？"
    )


def main():
    parser = argparse.ArgumentParser(description="对话式诊断追问应答（office-token-booster）")
    parser.add_argument("ledger", help="账本 JSON 路径")
    parser.add_argument("question", help="追问内容")
    args = parser.parse_args()
    try:
        tasks = load_ledger(args.ledger)
    except (FileNotFoundError, ValueError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2
    diag = diagnose(tasks)
    print(answer_followup(diag, args.question))
    return 0


if __name__ == "__main__":
    sys.exit(main())
