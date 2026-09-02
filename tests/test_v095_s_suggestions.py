# -*- coding: utf-8 -*-
"""tests/test_v095_s_suggestions.py — 对抗式审查 S 级建议（S1-S7）回归测试。

守卫点：
- S1: handle() 接受预计算 intent，REPL 不再双重 classify
- S2: execute 意图不再无谓调用 propose_entry
- S3: analyze_csv 披露被静默丢弃的单元格
- S4: 用户字段进 HTML 经 html.escape（防 XSS）
- S5: export_docx 在模板缺「Intense Quote」样式时回退默认段落
- S6: 数字/类型正则已在模块级预编译（行为不变 + 单位/邻接语义保持）
- S7: 周报行内锚点前缀正确路由（风险段不被「下周」吞掉）
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import allure
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import conversation  # noqa: E402
from conversation import classify, handle  # noqa: E402
from executor import (  # noqa: E402
    analyze_csv,
    _md_to_html,
    export_docx,
    render_weekly_report,
)
from diagnose import load_ledger, diagnose  # noqa: E402
from report_engine import generate_html_report  # noqa: E402

pytestmark = [
    pytest.mark.layer("execution"),
    pytest.mark.test_type("regression"),
    pytest.mark.component("conversation+executor"),
    pytest.mark.suite("v0.9.10-s-suggestions"),
    pytest.mark.risk_area("robustness"),
    pytest.mark.priority("p1"),
]


@pytest.fixture
def empty_ledger():
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"tasks": []}, tmp, ensure_ascii=False)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@allure.title("S1: handle 接受预计算 intent，exit 不应触发读账本")
@allure.severity(allure.severity_level.NORMAL)
def test_s1_handle_honors_intent_without_ledger():
    # 传入 intent="exit"，即便账本路径不存在也应安全返回（不调用 load_ledger）。
    resp = handle("此文件并不存在.json", "退出", {}, intent="exit")
    assert resp == "再见，账本已保留。"
    # 不传 intent 时仍自行 classify（向后兼容）
    assert handle("此文件并不存在.json", "退出", {}) == "再见，账本已保留。"


@allure.title("S2: execute 意图不调用 propose_entry（消除无谓估算）")
@allure.severity(allure.severity_level.NORMAL)
def test_s2_execute_skips_propose_entry(monkeypatch, empty_ledger):
    calls = []
    orig = conversation.propose_entry

    def spy(*a, **k):
        calls.append((a, k))
        return orig(*a, **k)

    monkeypatch.setattr(conversation, "propose_entry", spy)
    st = {}
    handle(empty_ledger, "帮我写周报：需求评审完成", st, intent="execute")
    assert calls == [], "execute 路径不应调用 propose_entry（S2 修复后）"
    # pending 结构仍正确：今日日期 + 空备注
    assert st["pending"]["date"]
    assert st["pending"]["note"] == ""


@allure.title("S3: analyze_csv 披露被静默丢弃的单元格")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("脏数据（ragged 行 / 空单元格 / 数值列非数字）应在报告末尾显式披露。")
def test_s3_analyze_csv_discloses_dropped():
    csv_text = "name,score,note\nA,10,ok\nB,20,ok\nC,,ok\nD,abc,notnum\nE,30"  # C 缺 score；D score 非数字；E 缺 note
    md = analyze_csv(csv_text)
    with allure.step("断言披露数据完整性"):
        assert "数据完整性" in md, "应披露被忽略的单元格"
        assert "忽略" in md
        # score 列：数值 10/20/30 → 求和 60；C 空、D 非数字被计入丢弃
        assert "60.00" in md, "有效数值仍应正确求和"
        assert "非数字单元格" in md


@allure.title("S4: 报告 HTML 转义用户字段（防 XSS）")
@allure.severity(allure.severity_level.CRITICAL)
def test_s4_report_html_escapes_user_fields():
    malicious = '<script>alert("x")</script>'
    diag = diagnose([
        {"date": "2026-09-02", "type": malicious,
         "baseline_tokens": 100, "skill_tokens": 10,
         "baseline_minutes": 5, "skill_minutes": 1, "note": malicious},
    ])
    html = generate_html_report(diag)
    with allure.step("断言恶意字段被转义"):
        assert "<script>" not in html, "原始 script 不得出现"
        assert "&lt;script&gt;" in html, "应转义为实体"
    # 引擎内部 _md_to_html 同样转义
    html2 = _md_to_html(f"# 会议纪要\n- {malicious}", "测试")
    assert "<script>" not in html2 and "&lt;script&gt;" in html2


@allure.title("S5: export_docx 缺失 Intense Quote 样式时回退")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("模板无『Intense Quote』样式时，quote 段落应回退默认段落样式而非崩溃。")
def test_s5_export_docx_intense_quote_fallback(monkeypatch, tmp_path):
    docx_mod = pytest.importorskip("docx")
    RealDocument = docx_mod.Document  # 先保留真实 Document，避免 save 时递归到 patch

    class _CoreProps:
        title = None

    class _FakeDoc:
        """模拟 Document：add_paragraph 在指定样式时抛错，模拟缺样式模板。"""

        def __init__(self):
            self.paragraphs = []
            self.core_properties = _CoreProps()

        def add_heading(self, text, level=1):
            self.paragraphs.append(text)
            return text

        def add_paragraph(self, text, style=None):
            if style == "Intense Quote":
                raise KeyError(f"no style {style!r}")
            self.paragraphs.append(text)
            return text

        def add_table(self, rows=1, cols=1):
            return None

        def save(self, path):
            # 落一个最小合法 docx（用真实 Document 写出，确保文件可被再打开）
            real = RealDocument()
            for p in self.paragraphs:
                real.add_paragraph(p)
            real.save(path)

    fake = _FakeDoc()
    md = "> 这是一句引述\n普通段落"
    # export_docx 内部 `from docx import Document` 惰性绑定，monkeypatch docx 模块级 Document 即可生效
    monkeypatch.setattr(docx_mod, "Document", lambda: fake)
    path, status = export_docx(md, str(tmp_path / "r.docx"), "周报")
    with allure.step("断言缺样式时回退且不抛错"):
        assert status == "ok", "缺 Intense Quote 样式应回退而非失败"
        assert path.endswith(".docx")
        reopen = RealDocument(path)
        texts = [p.text for p in reopen.paragraphs]
        assert any("这是一句引述" in t for t in texts), "quote 内容应保留"


@allure.title("S6: 数字解析支持单位且关键词须邻接")
@allure.severity(allure.severity_level.NORMAL)
def test_s6_parse_number_unit_and_adjacency():
    from conversation import _parse_numbers, _parse_number, _TOKEN_KW_RE, _MIN_KW_RE
    # 单位：1.5万 token → 15000
    tok, _ = _parse_numbers("花了1.5万 token")
    assert tok == 15000
    # 常规：1800 token 5分钟
    tok, mn = _parse_numbers("花了1800 token 5分钟")
    assert tok == 1800 and mn == 5
    # 邻接：关键词在数字之前不命中（『token 1800』）
    assert _parse_number("token 1800", _TOKEN_KW_RE) is None
    # 小数不崩溃
    assert _parse_numbers("花了200.5 token")[0] == 200


@allure.title("S7: 周报行内锚点前缀正确路由（风险不被下周吞掉）")
@allure.severity(allure.severity_level.NORMAL)
def test_s7_weekly_anchor_routing():
    md = render_weekly_report(
        "本周概览：推进执行引擎\n完成executor骨架\n"
        "风险：测试覆盖不足；下周计划：补回归测试\n正常重点工作"
    )
    with allure.step("断言分段结构正确"):
        assert "## 风险与阻塞" in md
        assert "## 下周计划" in md
        # 风险段应含「测试覆盖不足」，且未被错误归到「下周计划」
        assert "测试覆盖不足" in md
        assert "补回归测试" in md
