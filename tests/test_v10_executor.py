# -*- coding: utf-8 -*-
"""v0.9.5 方向 B：执行引擎回归测试。

守卫点：
- 5 个执行模块都能产出结构化 Markdown 交付物
- 数据分析模块真·本地计算指标（不联网）
- 执行后自动记账闭环复用 run_long_chain 护栏（缺省 baseline 写回被拦截，不污染账本）
- 用户内容进 HTML 经 html.escape（防 XSS 注入，守住安全红线）

全维度打标（layer/test_type/component/risk_area/priority/suite）。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import allure
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import executor  # noqa: E402  # 需要模块对象以 monkeypatch _try_import
from executor import (  # noqa: E402
    execute,
    resolve_exec_type,
    propose_ledger,
    _md_to_html,
    analyze_csv,
    export_docx,
    export_xlsx,
)
import host_hook  # noqa: E402  # 方向 B 宿主钩子闭环

pytestmark = [
    pytest.mark.layer("execution"),
    pytest.mark.test_type("integration"),
    pytest.mark.component("executor"),
    pytest.mark.suite("v0.9.5-direction-b"),
    pytest.mark.risk_area("execution-safety"),
    pytest.mark.priority("p0"),
]


# --------------------------------------------------------------------------
# 任务类型归一
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：类型归一覆盖 5 个模块 + 未知类型返回 None")
@allure.severity(allure.severity_level.CRITICAL)
def test_resolve_exec_type_coverage():
    for alias in ["周报", "周报生成", "weekly", "纪要", "会议纪要", "数据分析", "文档整理", "要点提炼", "PPT大纲", "slides"]:
        assert resolve_exec_type(alias) is not None, f"未识别别名：{alias}"
    assert resolve_exec_type("完全不相关的任务xyz") is None


# --------------------------------------------------------------------------
# 周报生成
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：周报生成渲染出概览/重点/风险/下周结构")
@allure.severity(allure.severity_level.CRITICAL)
def test_weekly_report_structure():
    md, meta = execute("周报生成",
                       "本周概览：推进执行引擎\n完成executor骨架\n风险：测试覆盖不足\n下周计划：补回归测试")
    with allure.step("断言结构化分节"):
        assert "# 周报" in md
        assert "## 本周概览" in md
        assert "## 重点工作" in md
        assert "## 风险与阻塞" in md
        assert "## 下周计划" in md
        assert meta["task_type"] == "周报生成"


# --------------------------------------------------------------------------
# 会议纪要
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：会议纪要抽取结论/待办（含负责人+截止）/遗留")
@allure.severity(allure.severity_level.CRITICAL)
def test_meeting_minutes_extract_action_items():
    md, _ = execute("会议纪要",
                    "参会：张三李四\n结论：方向B通过\n待办：@张三 截止2026-09-10 写测试\n遗留：PPT模块待定")
    with allure.step("断言关键分节与待办解析"):
        assert "# 会议纪要" in md
        assert "## 核心结论" in md
        assert "## 待办事项" in md
        assert "@张三" in md and "2026-09-10" in md, "应解析出负责人与截止日期"
        assert "## 遗留问题" in md


# --------------------------------------------------------------------------
# 数据分析（CSV 本地计算）
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：数据分析本地计算数值指标（不联网）")
@allure.severity(allure.severity_level.CRITICAL)
def test_csv_analysis_computes_metrics():
    md, _ = execute("数据分析", "name,score\nA,10\nB,20\nC,30")
    with allure.step("断言指标表含求和/均值/中位数"):
        assert "# 数据分析报告" in md
        assert "score" in md
        assert "60.00" in md, "求和 10+20+30=60"
        assert "20.00" in md, "均值 20"
        assert "20.00" in md, "中位数 20"


# --------------------------------------------------------------------------
# 文档整理 / 要点提炼
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：文档整理产出大纲+核心要点+一句话总结")
@allure.severity(allure.severity_level.NORMAL)
def test_doc_summary_outline():
    md, _ = execute("文档整理",
                    "# 标题一\n这是第一段关于执行引擎设计的内容。\n# 标题二\n第二段讲安全红线与零依赖。")
    with allure.step("断言三段结构"):
        assert "# 要点提炼" in md
        assert "## 文档大纲" in md
        assert "## 核心要点" in md
        assert "## 一句话总结" in md


# --------------------------------------------------------------------------
# PPT 大纲
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：PPT 大纲生成 5 页结构")
@allure.severity(allure.severity_level.NORMAL)
def test_ppt_outline():
    md, _ = execute("PPT大纲", "办公室AI提效助手\n要点一：又做又记\n要点二：零依赖")
    with allure.step("断言幻灯片分页"):
        assert "# 幻灯片大纲" in md
        assert "Slide 1" in md and "Slide 5" in md


# --------------------------------------------------------------------------
# 自动记账闭环（复用 run_long_chain 护栏）
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：自动记账——缺省 baseline 写回被护栏拦截")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("执行完一笔任务后自动记账：未提供 baseline 时应用写回应被 blocked，不污染账本。")
def test_auto_ledger_blocks_missing_baseline():
    ledger = Path(tempfile.mkdtemp()) / "ledger.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    # 应用写回（apply=True）但缺 baseline → 应被拦截
    res = propose_ledger(str(ledger), "周报生成", skill_tokens=1800, apply=True)
    with allure.step("断言 blocked 且不写盘"):
        assert res is not None
        assert res.get("blocked") is True, "缺省 baseline 写回应被拦截"
        assert "block_reason" in res
        # 账本未被污染
        assert json.load(open(ledger, encoding="utf-8"))["tasks"] == []


@allure.title("v1.0 执行引擎：自动记账——dry-run 预览不写盘且保留 skill 成本")
@allure.severity(allure.severity_level.NORMAL)
def test_auto_ledger_dryrun_preview():
    ledger = Path(tempfile.mkdtemp()) / "ledger.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    res = propose_ledger(str(ledger), "会议纪要", skill_tokens=2500, apply=False)
    with allure.step("断言预览模式不写盘但记录成本"):
        assert res is not None
        assert res.get("applied") is False
        assert res["entry"]["skill_tokens"] == 2500
        assert json.load(open(ledger, encoding="utf-8"))["tasks"] == []


# --------------------------------------------------------------------------
# HTML 转义（安全红线）
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：用户内容进 HTML 经 html.escape 防 XSS")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("会议纪要/周报等用户字段若含 <script>，必须转义，不得原样进 HTML。")
def test_html_escape_user_content():
    malicious = '<script>alert("xss")</script>'
    md = f"# 会议纪要\n- {malicious}\n- 正常内容"
    html_out = _md_to_html(md, "测试")
    with allure.step("断言脚本被转义"):
        assert "<script>" not in html_out, "原始 script 标签不得出现在 HTML 输出"
        assert "&lt;script&gt;" in html_out, "应转义为实体"
        assert "正常内容" in html_out


# --------------------------------------------------------------------------
# 可选富格式导出（docx / xlsx）—— 缺失优雅降级，不破零依赖默认
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：docx 库缺失时优雅降级为 Markdown（零依赖）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("python-docx 不可用时，export_docx 应降级写出 .md 且不抛错。")
def test_export_docx_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(executor, "_try_import", lambda n: None)
    md = "# 周报\n- 项目A完成\n- 项目B进行中"
    path, status = export_docx(md, str(tmp_path / "report"), "周报")
    with allure.step("断言降级为 .md 且内容等同"):
        assert status.startswith("degraded")
        assert path.endswith(".md")
        assert Path(path).read_text(encoding="utf-8") == md


@allure.title("v1.0 执行引擎：xlsx 库缺失时优雅降级为 CSV（零依赖）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("openpyxl 不可用时，export_xlsx 应降级写出 .csv（含表格数据）。")
def test_export_xlsx_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(executor, "_try_import", lambda n: None)
    md = "# 数据分析\n| 字段 | 求和 |\n|---|---|\n| score | 60.00 |"
    path, status = export_xlsx(md, str(tmp_path / "data"), "数据分析")
    with allure.step("断言降级为 .csv 且保留表格数据"):
        assert status.startswith("degraded")
        assert path.endswith(".csv")
        txt = Path(path).read_text(encoding="utf-8-sig")
        assert "score" in txt and "60.00" in txt


docx_mod = pytest.importorskip("docx")


@allure.title("v1.0 执行引擎：docx 存在时生成真实 .docx（含标题与要点）")
@allure.severity(allure.severity_level.CRITICAL)
def test_export_docx_real(tmp_path):
    md = "# 周报\n- 完成A\n- 完成B"
    path, status = export_docx(md, str(tmp_path / "r.docx"), "周报")
    with allure.step("断言真实 docx 含结构化内容"):
        assert status == "ok" and path.endswith(".docx")
        doc = docx_mod.Document(path)
        texts = [p.text for p in doc.paragraphs]
        assert any("周报" in t for t in texts)
        assert any("完成A" in t for t in texts)


openpyxl_mod = pytest.importorskip("openpyxl")


@allure.title("v1.0 执行引擎：xlsx 存在时生成真实 .xlsx（内容+表 sheet）")
@allure.severity(allure.severity_level.CRITICAL)
def test_export_xlsx_real(tmp_path):
    md = "# 数据分析\n| 字段 | 求和 |\n|---|---|\n| score | 60.00 |"
    path, status = export_xlsx(md, str(tmp_path / "d.xlsx"), "数据分析")
    with allure.step("断言真实 xlsx 含数据与表 sheet"):
        assert status == "ok" and path.endswith(".xlsx")
        wb = openpyxl_mod.load_workbook(path)
        assert "内容" in wb.sheetnames
        assert "表1" in wb.sheetnames
        vals = [c.value for row in wb["表1"].iter_rows() for c in row]
        assert "score" in vals and "60.00" in vals


# --------------------------------------------------------------------------
# 自动记账：接受 event cost 字典 + 宿主钩子闭环
# --------------------------------------------------------------------------
@allure.title("v1.0 执行引擎：propose_ledger 接受 event cost 字典合并记账")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("宿主完成事件的 cost 字典（skill_tokens/skill_minutes）应并入记账条目。")
def test_propose_ledger_accepts_cost_dict():
    ledger = Path(tempfile.mkdtemp()) / "ledger.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    cost = {"skill_tokens": 1800, "skill_minutes": 5}
    res = propose_ledger(str(ledger), "周报生成", cost=cost, apply=False)
    with allure.step("断言 cost 进入 entry 且不写盘"):
        assert res is not None
        assert res["entry"]["skill_tokens"] == 1800
        assert res["entry"]["skill_minutes"] == 5
        assert json.load(open(ledger, encoding="utf-8"))["tasks"] == []


@allure.title("v1.0 宿主钩子：executor 完成后用 event cost 自动记回（闭环）")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("host_hook.on_executor_completed 复用 v0.7 事件 cost 形态直接记回 ledger。")
def test_host_hook_executor_completed_uses_event_cost():
    ledger = Path(tempfile.mkdtemp()) / "ledger.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    event = {"role": "user", "text": "我刚生成了周报",
             "cost": {"skill_tokens": 1800, "skill_minutes": 5}}
    res = host_hook.on_executor_completed(str(ledger), "周报生成", event, apply=False)
    with allure.step("断言 event cost 进入记账条目"):
        assert res is not None
        assert res["entry"]["skill_tokens"] == 1800
        assert res["entry"]["skill_minutes"] == 5
        assert json.load(open(ledger, encoding="utf-8"))["tasks"] == []


# --------------------------------------------------------------------------
# v0.9.6 增强回归（E1–E4）
# --------------------------------------------------------------------------
@allure.title("v0.9.6 E1：propose_ledger 透传 baseline 后可真正写回空账本")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("executor 自动记账闭环：显式传入 baseline 应绕过 P0 护栏写回，而非永远被拦截。")
def test_propose_ledger_writes_with_explicit_baseline():
    ledger = Path(tempfile.mkdtemp()) / "ledger.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    res = propose_ledger(str(ledger), "周报生成", skill_tokens=1800, skill_minutes=5,
                         baseline_tokens=6000, baseline_minutes=30, apply=True)
    with allure.step("断言写回成功且账本含 1 条"):
        assert res is not None
        assert res.get("applied") is True, "显式 baseline 应通过护栏写回"
        assert res.get("blocked") is not True
        tasks = json.load(open(ledger, encoding="utf-8"))["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["skill_tokens"] == 1800
        assert tasks[0]["baseline_tokens"] == 6000


@allure.title("v0.9.6 E1：executor CLI 经 --baseline-tokens 写回账本")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("端到端：--confirm-ledger 配合 --baseline-tokens 应能真正写回账本。")
def test_executor_cli_apply_with_baseline_writes(capsys):
    ledger = Path(tempfile.mkdtemp()) / "ledger.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    rc = executor.main([
        "--type", "周报生成", "--input", "要点X",
        "--apply-ledger", str(ledger),
        "--skill-tokens", "1800", "--baseline-tokens", "6000",
        "--baseline-minutes", "30", "--confirm-ledger",
    ])
    err = capsys.readouterr().err
    assert rc == 0
    assert "已写回账本" in err
    tasks = json.load(open(ledger, encoding="utf-8"))["tasks"]
    assert len(tasks) == 1


@allure.title("v0.9.6 E2：--confirm-ledger 被拦截时显示真实 block_reason（不再 None）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("executor 读 res.get('reason') 键名错，应读 block_reason，避免「已拦截：None」。")
def test_confirm_ledger_shows_block_reason(capsys):
    ledger = Path(tempfile.mkdtemp()) / "ledger.json"
    ledger.write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    rc = executor.main([
        "--type", "周报生成", "--input", "要点X",
        "--apply-ledger", str(ledger), "--skill-tokens", "1800", "--confirm-ledger",
    ])
    err = capsys.readouterr().err
    assert rc == 0
    assert "已拦截" in err
    assert "None" not in err, "不应再出现「已拦截：None」"
    assert "手搓" in err, "应显示真实拦截原因（缺 baseline）"


@allure.title("v0.9.6 E3：周报行内锚点——一行混合要点不丢「风险」段")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("render_weekly_report 按 ；/ ; 拆子项并识别行内前缀，避免风险段被「下周」整行吞掉。")
def test_weekly_report_inline_anchors_split():
    md, _ = execute("周报生成",
                    "本周概览：方向B落地；完成executor骨架\n风险：回归覆盖不足；下周计划：补测试")
    with allure.step("断言四类结构均出现且风险未被吞"):
        assert "## 本周概览" in md
        assert "## 重点工作" in md
        assert "## 风险与阻塞" in md
        assert "## 下周计划" in md
        assert "回归覆盖不足" in md
        assert "补测试" in md
        # 风险要点不应错进「下周计划」段（原 bug 会把整行吞掉）
        assert "风险" in md


@allure.title("v0.9.6 E4：账本文件不存在时友好提示而非原始栈")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("executor --apply-ledger 指向不存在文件应捕获 FileNotFoundError 给友好提示。")
def test_missing_ledger_friendly_error(capsys):
    rc = executor.main([
        "--type", "周报生成", "--input", "要点X",
        "--apply-ledger", "/nonexistent/path/账本.json",
        "--skill-tokens", "1800",
    ])
    out = capsys.readouterr()
    assert rc == 0
    assert "不存在" in out.err
    assert "--init-ledger" in out.err, "应推荐安全的 --init-ledger 而非脆弱的 echo/python -c"
    assert "# 周报" in out.out, "交付物应正常生成（仅记账被跳过）"


@allure.title("v0.9.6 D1：--init-ledger 创建空账本（Test2/3 根因修复）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("--init-ledger 应写入 {\"tasks\":[]} 并安全退出，替代脆弱的 echo / python -c。")
def test_init_ledger_creates_empty(capsys, tmp_path):
    p = tmp_path / "账本.json"
    rc = executor.main(["--init-ledger", str(p)])
    out = capsys.readouterr()
    assert rc == 0
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data == {"tasks": []}
    assert "已创建空账本" in out.err


@allure.title("v0.9.6 D1：--init-ledger 对已存在账本幂等跳过")
@allure.severity(allure.severity_level.MINOR)
@allure.description("账本已存在时不应覆盖，给出提示并正常退出。")
def test_init_ledger_idempotent(capsys, tmp_path):
    p = tmp_path / "账本.json"
    p.write_text(json.dumps({"tasks": [{"x": 1}]}, ensure_ascii=False), encoding="utf-8")
    rc = executor.main(["--init-ledger", str(p)])
    out = capsys.readouterr()
    assert rc == 0
    # 原数据未被覆盖
    assert json.loads(p.read_text(encoding="utf-8")) == {"tasks": [{"x": 1}]}
    assert "已存在" in out.err


@allure.title("v0.9.6 D1+E1：init 后带 baseline 闭环可写回并出报告")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("先用 --init-ledger 建空账本，再 --confirm-ledger 带 baseline 写回，report_engine 能生成 HTML。")
def test_init_then_apply_generates_report(capsys, tmp_path):
    ledger = tmp_path / "账本.json"
    # 1) init
    assert executor.main(["--init-ledger", str(ledger)]) == 0
    # 2) 带 baseline 写回（走 executor 闭环，非空账本也能过护栏）
    rc = executor.main([
        "--type", "周报生成", "--input", "要点X",
        "--apply-ledger", str(ledger),
        "--skill-tokens", "1800", "--baseline-tokens", "6000", "--baseline-minutes", "30",
        "--confirm-ledger",
    ])
    out = capsys.readouterr()
    assert rc == 0
    assert "已写回账本" in out.err
    tasks = json.loads(ledger.read_text(encoding="utf-8"))["tasks"]
    assert len(tasks) == 1
    # 3) 报告可生成（不再因账本空而跳过）——走 report_engine CLI 真实路径
    import report_engine, sys as _sys
    report = tmp_path / "报告.html"
    _old_argv = _sys.argv
    _sys.argv = ["report_engine.py", str(ledger), "--format", "html", "--output", str(report)]
    try:
        rc2 = report_engine.main()
    finally:
        _sys.argv = _old_argv
    assert rc2 == 0
    assert report.exists() and report.stat().st_size > 0
