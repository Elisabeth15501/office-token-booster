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


def _lowest_type(diag):
    """节省 Token 最少的类型（提效最不明显的场景）。"""
    return min(diag.by_type, key=lambda x: x["saved_tokens"]) if diag.by_type else None


def _match_type(diag, q):
    """若追问里出现某个已记录的任务类型名，返回该类型 dict，否则 None。"""
    for d in diag.by_type:
        if d["task_type"] and d["task_type"] in q:
            return d
    return None


def answer_followup(diag, question):
    """基于 Diagnosis 结构化数据应答常见追问。返回中文文本（已接地，不编造）。

    分支覆盖了「对话式诊断」常见问法：总览 / 比例 / 类型排名 / 自动化优先级 /
    周趋势 / 明细 / 最差场景 / 耗时 / 方法论 / 可信度 / 完整报告路由等。
    """
    q = (question or "").strip()
    if not q:
        return "请提出一个关于账本的具体问题，例如：节省最多的任务类型是什么？"

    if diag.n == 0:
        return "账本为空，暂无可分析的数据。请先记录任务账本。"

    # 完整报告路由
    if any(k in q for k in ("完整报告", "完整", "九段", "明细", "看报告", "生成报告", "全部")):
        return ("请对我说「生成完整报告」，技能将调用 report_engine 输出完整明细报告"
                "（任务类型 / 周趋势 / 执行情况 / 产出物 / 洞察建议 / 可信度提示等）。")

    # 指定类型名匹配（如「会议纪要怎么样」）
    hit = _match_type(diag, q)
    if hit:
        return (f"「{hit['task_type']}」：{hit['count']} 次，基准 {format_number(hit['baseline_tokens'])} "
                f"→ 本技能 {format_number(hit['skill_tokens'])} Token，"
                f"省 {format_number(hit['saved_tokens'])}（{hit['token_save_pct']:.1f}%）；"
                f"耗时省 {format_number(hit['saved_minutes'])} 分（{hit['time_save_pct']:.1f}%）。")

    # 方法论 / 怎么算出来的
    if any(k in q for k in ("怎么算", "怎么得出", "公式", "方法", "如何计算", "基准是什么", "基线是什么", "baseline")):
        return (diag.methodology + "\n"
                "简言之：节省 = 你填的「基准估计」−「本技能实际消耗」。基准是你对"
                "「自己手搓 / 反复试错」成本的主观估计，不是平台实测扣费。")

    # 可信度 / 异常 / 虚高
    if any(k in q for k in ("可信", "准确", "可靠", "异常", "偏差", "虚高", "真实", "水分", "护栏")):
        if diag.caveats:
            return "数据可信度提示（已识别以下可能拉高提效声称的项）：\n" + "\n".join(
                f"- ⚠️ {c}" for c in diag.caveats)
        return ("当前未发现明显异常。但请记住：节省值是你填的基准估计的参照值，不是平台实测扣费；"
                "其可信度完全取决于「基准」是否如实反映你手搓的真实成本。")

    # 任务明细 / 清单
    if any(k in q for k in ("明细", "清单", "哪些任务", "做了什么", "任务列表", "记录", "列表")):
        if not diag.tasks:
            return "暂无任务明细。"
        lines = [f"共 {len(diag.tasks)} 条任务："]
        for i, t in enumerate(diag.tasks, 1):
            bt = t.get("baseline_tokens", 0) or 0
            st = t.get("skill_tokens", 0) or 0
            note = t.get("note") or ""
            lines.append(f"{i}. {t.get('date','')} ｜ {t.get('type','')} ｜ 省 "
                         f"{format_number(bt - st)} Token {('｜ ' + note) if note else ''}")
        return "\n".join(lines)

    # 最不省 / 最差场景
    if any(k in q for k in ("最差", "最低", "不省", "最少", "拉胯", "最不划算")):
        low = _lowest_type(diag)
        if low:
            return (f"提效最不明显的是「{low['task_type']}」：{low['count']} 次仅省 "
                    f"{format_number(low['saved_tokens'])} Token（省 {low['token_save_pct']:.1f}%）。"
                    f"可检查该类是否基线估计偏低，或本技能在该场景收益本就有限。")
        return "暂无可统计的任务类型。"

    # 耗时 / 时间
    if any(k in q for k in ("耗时", "时间", "分钟", "花了多久", "效率")):
        return (f"合计节省 {format_number(diag.saved_min)} 分钟（省 {diag.time_save_pct:.1f}%）；"
                f"基准 {format_number(diag.total_base_min)} 分 → 本技能 {format_number(diag.total_skill_min)} 分。")

    # 任务数 / 记录数
    if any(k in q for k in ("多少任务", "几条", "记录数", "个数", "多少条", "一共几条")):
        return f"账本共 {diag.n} 条任务记录。"

    # 总节省 / 概览
    if any(k in q for k in ("总共", "合计", "总节省", "一共", "总体", "概览", "总结一下")):
        return (
            f"共 {diag.n} 条任务，合计节省 {format_number(diag.saved_tok)} Token"
            f"（省 {diag.token_save_pct:.1f}%）、{format_number(diag.saved_min)} 分钟"
            f"（省 {diag.time_save_pct:.1f}%）。"
        )

    # 节省比例
    if any(k in q for k in ("比例", "百分比", "省了", "省多少", "%", "多高")):
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
    if any(k in q for k in ("值得", "自动化", "优先", "场景", "推荐做", "哪些任务值得", "哪类")):
        hot = _hottest_type(diag)
        if hot:
            return (f"基线成本最高、最值得自动化的是「{hot['task_type']}」：单次基线约 "
                    f"{format_number(hot['baseline_tokens'] / max(hot['count'], 1))} Token，"
                    f"自动化空间最大。")
        return "暂无可分析的任务类型。"

    # 按周趋势
    if any(k in q for k in ("周", "趋势", "变化", "每周", "时间线", "走势")):
        if not diag.by_week:
            return "账本中没有可用的日期信息，无法按周分析。"
        lines = ["按周节省 Token："]
        for w in diag.by_week:
            lines.append(f"- {w['week']}：{w['count']} 次任务，省 "
                         f"{format_number(w['saved_tokens'])} Token（省 {w['token_save_pct']:.1f}%）")
        return "\n".join(lines)

    # 建议
    if any(k in q for k in ("建议", "怎么", "如何", "下一步", "优化", "改进", "该怎么做")):
        if not diag.recommendations:
            return "暂无建议。"
        return "建议：\n" + "\n".join(f"- {r}" for r in diag.recommendations)

    # 洞察
    if any(k in q for k in ("洞察", "发现", "结论", "看出来", "总结", "亮点")):
        if not diag.insights:
            return "暂无洞察。"
        return "洞察：\n" + "\n".join(f"- {x}" for x in diag.insights)

    # 兜底
    return (
        "我已为你生成「一页摘要」作为首屏。可继续追问，或说「生成完整报告」查看完整明细。常见问法：\n"
        "- 总共节省了多少？\n"
        "- 哪个任务类型节省最多 / 最不省？\n"
        "- 哪个场景最值得自动化？\n"
        "- 按周趋势如何？\n"
        "- 有哪些任务明细？\n"
        "- 这些数字怎么算出来的 / 可信吗？\n"
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
