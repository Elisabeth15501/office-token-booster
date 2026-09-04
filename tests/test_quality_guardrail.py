#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""不降质量护栏度量（v0.9.11）回归测试。

覆盖：quality.py 各类型结构清单打分、executor 渲染后带质量分、diagnose 聚合
avg_quality / by_type.quality_score_avg、report_engine 护栏横幅（达标 / 跌破基线 /
未测 三态）、conversation 生成→确认跨轮把质量分带进账本。
"""
import json
import os
import sys
import tempfile
from pathlib import Path

# 让 pytest 能 import scripts/ 下的模块（与既有测试 test_v05/test_boundary 等一致）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

pytest.importorskip("allure")  # 无 allure 时本文件整体跳过
import allure  # importorskip 已保证可用；用于 @allure.title 装饰器

from quality import (  # noqa: E402
    score_weekly_report, score_meeting_minutes, score_analysis,
    score_distill, score_deliverable, ScoreResult, QUALITY_FLOOR)
from executor import execute, execute_render  # noqa: E402
from diagnose import diagnose  # noqa: E402
from report_engine import (  # noqa: E402
    generate_html_report, generate_html_summary,
    generate_markdown_report, generate_markdown_summary)
from conversation import handle  # noqa: E402


# ─────────────────────────────────────────────────────────────
# 1) quality.py 各类型清单打分
# ─────────────────────────────────────────────────────────────
@allure.title("质量清单：周报四要素齐全=100，缺风险=75")
def test_score_weekly_report():
    full = ("# 周报\n## 本周概览\n试点启动\n## 重点工作\n- 写完\n"
            "## 风险与阻塞\n- 服务器抖动\n## 下周计划\n- 上线C")
    r_full = score_weekly_report(full)
    assert r_full.score == 100
    assert all(ok for _, ok in r_full.checks)

    no_risk = ("# 周报\n## 本周概览\n试点启动\n## 重点工作\n- 写完\n"
               "## 下周计划\n- 上线C")
    r_low = score_weekly_report(no_risk)
    assert r_low.score == 75  # 概览✓ 工作✓ 计划✓ 风险✗
    assert r_low.credible is False


@allure.title("质量清单：纪要含结论+行动项+负责人=达标")
def test_score_meeting_minutes():
    md = ("# 会议纪要\n## 核心结论\n- 通过试点\n## 待办事项\n"
          "- [ ] 上线C ｜ 负责人：张三 ｜ 截止：2026-09-10\n## 参会与背景\n- 甲乙")
    r = score_meeting_minutes(md)
    assert r.score == 100
    # 缺负责人
    md2 = md.replace("｜ 负责人：张三 ｜ 截止：2026-09-10", "")
    assert score_meeting_minutes(md2).score < 100


@allure.title("质量清单：数据分析无隐藏丢行=100，有丢行扣分")
def test_score_analysis():
    clean = "name,score\nA,10\nB,20\nC,30"
    md_clean = execute("数据分析", clean)[0]
    assert score_analysis(md_clean).score == 100

    dirty = "name,score\nA,10\nB,abc\nC,30"  # B 列非数字 → 被当丢行
    md_dirty = execute("数据分析", dirty)[0]
    assert "忽略" in md_dirty
    assert 0 < score_analysis(md_dirty).score < 100


@allure.title("质量清单：文档整理要点≥3且有实质内容=达标")
def test_score_distill():
    # score_distill 对渲染后的 bullet（- 开头）做结构断言，喂的是执行引擎产出的核心要点形态
    good = ("## 核心要点\n"
            "- 明确本季度的核心交付目标与里程碑\n"
            "- 将大任务拆分为可独立验证的子任务\n"
            "- 周五前完成复盘并输出结论")
    assert score_distill(good).score == 100
    thin = "## 核心要点\n- x\n- y"
    assert score_distill(thin).score < 100


@allure.title("质量清单：未配置清单的类型返回 score=None（未测）")
def test_score_deliverable_unconfigured():
    r = score_deliverable("PPT大纲", "# 大纲\n- a\n- b")
    assert r.score is None
    assert r.credible is False


# ─────────────────────────────────────────────────────────────
# 2) executor 渲染后带质量分（meta）
# ─────────────────────────────────────────────────────────────
@allure.title("executor.execute 在 meta 携带 quality_score / quality_checks")
def test_execute_meta_quality():
    md, meta = execute("周报生成", "本周概览：试点\n重点工作：写完\n风险：抖动\n下周计划：上线")
    assert meta.get("quality_score") is not None
    assert isinstance(meta.get("quality_checks"), list) and meta["quality_checks"]


@allure.title("executor.execute_render 改为三元组 (ok, md, meta)")
def test_execute_render_returns_triple():
    ok, md, meta = execute_render("周报生成", "本周概览：试点\n重点工作：写完\n风险：抖动\n下周计划：上线")
    assert ok is True
    assert isinstance(md, str)
    assert meta.get("quality_score") is not None
    ok2, msg, meta2 = execute_render("不存在的类型", "x")
    assert ok2 is False and meta2 == {}


# ─────────────────────────────────────────────────────────────
# 3) diagnose 聚合
# ─────────────────────────────────────────────────────────────
def _tasks():
    return [
        {"date": "2026-08-10", "type": "周报生成", "baseline_tokens": 12000,
         "skill_tokens": 1800, "baseline_minutes": 25, "skill_minutes": 5, "quality_score": 100},
        {"date": "2026-08-11", "type": "周报生成", "baseline_tokens": 12000,
         "skill_tokens": 2000, "baseline_minutes": 25, "skill_minutes": 6, "quality_score": 75},
        {"date": "2026-08-12", "type": "会议纪要", "baseline_tokens": 8000,
         "skill_tokens": 1500, "baseline_minutes": 20, "skill_minutes": 4, "quality_score": None},
    ]


@allure.title("diagnose：avg_quality 均值聚合 + by_type.quality_score_avg")
def test_diagnose_quality_aggregation():
    d = diagnose(_tasks())
    assert d.has_quality is True
    # 周报生成 (100+75)/2 = 88；整体 (100+75)/2 = 87.5 → 88
    assert d.avg_quality == 88
    wr = next(t for t in d.by_type if t["task_type"] == "周报生成")
    assert wr["quality_score_avg"] == 88
    mt = next(t for t in d.by_type if t["task_type"] == "会议纪要")
    assert mt["quality_score_avg"] is None  # 未测不污染均值


@allure.title("diagnose：质量跌破基线 → quality_ok=False（护栏触发依据）")
def test_diagnose_quality_floor():
    low = [{"date": "2026-08-10", "type": "周报生成", "baseline_tokens": 12000,
            "skill_tokens": 1800, "baseline_minutes": 25, "skill_minutes": 5, "quality_score": 50}]
    d = diagnose(low)
    assert d.avg_quality == 50
    assert d.quality_ok is False


@allure.title("diagnose：无质量分 → has_quality=False 且 quality_ok=True（不误伤）")
def test_diagnose_no_quality():
    noq = [{"date": "2026-08-10", "type": "周报生成", "baseline_tokens": 12000,
            "skill_tokens": 1800, "baseline_minutes": 25, "skill_minutes": 5}]
    d = diagnose(noq)
    assert d.has_quality is False
    assert d.quality_ok is True


# ─────────────────────────────────────────────────────────────
# 4) report_engine 护栏横幅（三态）
# ─────────────────────────────────────────────────────────────
@allure.title("报告：达标 → 质量护栏显示「质量达标」")
def test_report_guard_ok():
    d = diagnose(_tasks())
    html = generate_html_report(d)
    assert "质量护栏" in html
    assert "质量达标" in html


@allure.title("报告：跌破基线 → 横幅显示「节省不可信」")
def test_report_guard_untrusted():
    low = [{"date": "2026-08-10", "type": "周报生成", "baseline_tokens": 12000,
            "skill_tokens": 1800, "baseline_minutes": 25, "skill_minutes": 5, "quality_score": 50}]
    d = diagnose(low)
    html = generate_html_report(d)
    assert "节省不可信" in html


@allure.title("报告：无质量分 → 横幅显示「质量未测」")
def test_report_guard_untested():
    noq = [{"date": "2026-08-10", "type": "周报生成", "baseline_tokens": 12000,
            "skill_tokens": 1800, "baseline_minutes": 25, "skill_minutes": 5}]
    d = diagnose(noq)
    md = generate_markdown_summary(d)
    assert "质量未测" in md


@allure.title("报告：类型表含质量分列")
def test_report_type_table_quality_column():
    d = diagnose(_tasks())
    html = generate_html_report(d)
    assert "质量分" in html  # 表头列


# ─────────────────────────────────────────────────────────────
# 5) conversation 生成→确认跨轮带质量分进账本
# ─────────────────────────────────────────────────────────────
@allure.title("conversation：execute 生成把质量分存入 pending，确认写回账本")
def test_conversation_quality_roundtrip():
    fd, lp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        open(lp, "w").write(json.dumps({"tasks": []}))
        state = {"ledger": lp, "pending": None}
        # 用不含「概览/摘要」的执行触发文本，避免被 classify 误判为 report_summary
        handle(lp, "帮我写周报：这周搞定了A和B，风险是服务器抖动，下周要上线C", state)
        pq = state["pending"].get("quality_score")
        assert pq is not None
        handle(lp, "确认 baseline 12000 token 25分钟", state)
        data = json.load(open(lp))
        assert data["tasks"][0].get("quality_score") == pq
    finally:
        os.remove(lp)
