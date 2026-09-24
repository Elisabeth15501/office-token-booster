"""Issue 防漂移回归测试（#1 / #2 / #3）。

- #1：周报风险节不应把「含完成类动词 + 问题」的 neutral 句抢走。
- #2：SKILL.md 承诺的追问 example 必须被 answer_followup 接住（不落通用帮助）。
- #3：输入自带项目符号不应渲染出双层子弹「- - 」。
"""
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from executor import execute, render_weekly_report, _lines
from diagnose import load_ledger, diagnose


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _generic_help(text: str) -> bool:
    """answer_followup 落到通用帮助文本的标志。"""
    return text.startswith("我已为你生成") or "常见问法" in text


# ---------------------------------------------------------------------------
# Issue #2：SKILL.md 承诺的追问必须接住
# ---------------------------------------------------------------------------
def _extract_task_diagnosis_examples() -> list[str]:
    """从 SKILL.md frontmatter 抽取 intent=task_diagnosis 下的 examples。"""
    skl = open(os.path.join(REPO_ROOT, "SKILL.md"), encoding="utf-8").read()
    fm = skl.split("---")[1]
    # 定位 task_diagnosis 意图区块
    m = re.search(r"intent:\s*task_diagnosis(.*?)(?=\n\s*-\s*intent:|\nnon_triggers:)", fm, re.S)
    block = m.group(1) if m else ""
    return re.findall(r'-\s*"([^"]+)"', block)


def test_skillmd_task_diagnosis_examples_resolved():
    """文档承诺的每一个 example 都应被 qa 接住，不掉通用帮助。"""
    from qa import answer_followup

    examples = _extract_task_diagnosis_examples()
    assert examples, "未从 SKILL.md 抽到 task_diagnosis examples（结构可能已变）"
    diag = diagnose(load_ledger(os.path.join(REPO_ROOT, "examples", "ledger.json")))
    unresolved = []
    for ex in examples:
        out = answer_followup(diag, ex)
        if _generic_help(out):
            unresolved.append(ex)
    assert not unresolved, f"以下 SKILL.md 示例落到通用帮助：{unresolved}"


def test_most_save_and_most_cost_resolved():
    """Issue #2 复现：最省 / 最费 Token 必须命中对应能力。"""
    from qa import answer_followup

    diag = diagnose(load_ledger(os.path.join(REPO_ROOT, "examples", "ledger.json")))
    out_save = answer_followup(diag, "哪个任务类型最省 Token？")
    out_cost = answer_followup(diag, "哪个任务类型最费 Token？")
    assert not _generic_help(out_save), "「最省 Token」落到通用帮助"
    assert not _generic_help(out_cost), "「最费 Token」落到通用帮助"
    assert "节省最多" in out_save
    assert "实耗最多" in out_cost


# ---------------------------------------------------------------------------
# Issue #1：风险节不应抢走「含完成动词 + 问题」的 neutral 句
# ---------------------------------------------------------------------------
def test_weekly_risk_not_grab_done_verb_line():
    md = render_weekly_report(
        "完成执行引擎骨架\n发现更隐蔽的问题：测试文件里的模块级 importorskip 会让整份文件停止收集\n下周计划：补回归测试"
    )
    assert "## 重点工作" in md
    # 该行应归属重点工作（默认桶）
    work_section = md.split("## 重点工作", 1)[1].split("## ", 1)[0]
    assert "发现更隐蔽的问题" in work_section
    # 既无风险节，或风险节中不含该行
    if "## 风险与阻塞" in md:
        risk_section = md.split("## 风险与阻塞", 1)[1].split("## 下周计划", 1)[0]
        assert "发现更隐蔽的问题" not in risk_section


def test_weekly_risk_explicit_anchor_still_routes():
    """显式锚点（风险：…）应始终进风险节，不受完成动词门槛影响。"""
    md = render_weekly_report("风险：部署仍未完成，需跟进")
    risk_section = md.split("## 风险与阻塞", 1)[1].split("## 下周计划", 1)[0]
    assert "部署仍未完成" in risk_section


# ---------------------------------------------------------------------------
# Issue #3：输入自带项目符号不应双层子弹
# ---------------------------------------------------------------------------
def test_lines_strips_leading_bullets():
    src = "- 完成牛来排片追踪站 V3 上线\n* 第二点\n1. 第三点\n  • 第四点"
    got = _lines(src)
    assert got == [
        "完成牛来排片追踪站 V3 上线",
        "第二点",
        "第三点",
        "第四点",
    ]


def test_weekly_report_no_double_bullet():
    md, _ = execute("周报生成", "- 完成牛来排片追踪站 V3 上线\n- 修复了渲染分节 bug")
    # 不应出现双层子弹「- - 」
    assert "- - " not in md
    assert "完成牛来排片追踪站 V3 上线" in md


def test_meeting_minutes_bullet_and_action_items():
    """Issue #3 回归：会议纪要待办行剥离前缀后仍解析出负责人/截止。"""
    md, _ = execute(
        "会议纪要",
        "- 参会：张三李四\n- 待办：@张三 截止2026-09-10 写测试\n- 遗留：PPT 模块待定",
    )
    assert "- - " not in md
    assert "@张三" in md and "2026-09-10" in md
