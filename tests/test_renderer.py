#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_renderer.py — tools/render_allure_html.py 冒烟测试（作品集核心交付物）

渲染器是「把 allure-results 变成单文件 HTML 报告」的零依赖工具，本身是作品集
对外交付的关键一环，必须被测试覆盖（修复 L6）。

本测试不依赖 Java / allure CLI：内置最小 allure-results fixture（一通过一失败 +
一个文本附件），断言：
  1. load_results 正确读取 result.json；
  2. render 产出 HTML 含用例名、状态、运行环境、失败分类（DEFAULT_CATEGORIES）；
  3. main() 能写出独立 HTML 文件且内容自洽。
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# 让测试无论从哪个目录运行都能 import 到 tools/render_allure_html.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from render_allure_html import (                                # noqa: E402
    load_results, load_environment, render, DEFAULT_CATEGORIES, main)


# allure 装饰器（未安装 allure-pytest 时退化为无操作，普通 pytest 仍可运行）
try:
    import allure

    def allure_feature(name):
        return allure.feature(name)

    def allure_title(name):
        return allure.title(name)
except ImportError:  # pragma: no cover
    def allure_feature(name):
        return lambda f: f

    def allure_title(name):
        return lambda f: f


@pytest.fixture
def results_dir():
    """构造一个最小但真实的 allure-results 目录（一通过一失败 + 一个文本附件）。"""
    d = tempfile.mkdtemp(prefix="ar_fixture_")
    # 通过的用例：含 steps 与 attachment
    passed = {
        "name": "测试A_生成提效报告通过",
        "status": "passed",
        "start": 1000, "stop": 1500,
        "labels": [
            {"name": "epic", "value": "office-token-booster"},
            {"name": "layer", "value": "内核层"},
            {"name": "feature", "value": "v0.6 Skill 触发流"},
            {"name": "story", "value": "确认写回与三层一致"},
            {"name": "severity", "value": "critical"},
            {"name": "test_type", "value": "positive"},
            {"name": "component", "value": "diagnose"},
            {"name": "risk_area", "value": "data_integrity"},
            {"name": "priority", "value": "P0"},
            {"name": "suite", "value": "v0.6"},
        ],
        "description": "renderer smoke fixture: passed case",
        "links": [{"url": "https://github.com/Elisabeth15501/office-token-booster/blob/main/scripts/diagnose.py#L275",
                   "name": "diagnose() 源码", "type": "source"}],
        "steps": [{"name": "步骤1_读取账本", "status": "passed"},
                  {"name": "步骤2_写回", "status": "passed"}],
        "attachments": [{"name": "账本快照", "source": "att1.txt", "type": "text/plain"}],
    }
    # 失败的用例：含 statusDetails.message
    failed = {
        "name": "测试B_异常账本被护栏捕获",
        "status": "failed",
        "start": 2000, "stop": 2200,
        "statusDetails": {"message": "boom: 异常账本未被识别"},
    }
    (Path(d) / "a1b2c3-result.json").write_text(
        json.dumps(passed, ensure_ascii=False), encoding="utf-8")
    (Path(d) / "d4e5f6-result.json").write_text(
        json.dumps(failed, ensure_ascii=False), encoding="utf-8")
    (Path(d) / "att1.txt").write_text("ledger snapshot content", encoding="utf-8")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@allure_feature("测试报告渲染器")
@allure_title("渲染器冒烟：读取 + 渲染产出含用例名与状态")
def test_renderer_smoke(results_dir):
    """render() 产出 HTML 必须包含用例名、状态、运行环境与默认失败分类。"""
    tests = load_results(results_dir)
    assert len(tests) == 2, f"应读取到 2 个 result.json，实际 {len(tests)}"

    env = load_environment(results_dir)
    html = render(env, DEFAULT_CATEGORIES, tests, results_dir)

    # 用例名 & 状态都出现
    assert "测试A_生成提效报告通过" in html, "渲染结果缺失通过的用例名"
    assert "测试B_异常账本被护栏捕获" in html, "渲染结果缺失失败的用例名"
    assert "通过" in html and "失败" in html, "渲染结果缺失状态标签"

    # 运行环境表 & 默认失败分类（作品集报告观感）
    assert "运行环境" in html, "渲染结果缺失运行环境表"
    assert "失败分类" in html, "渲染结果缺失失败分类区块"
    assert "Product Bug" in html, "渲染结果缺失默认 Product Bug 分类"

    # 架构分层标签（epic / layer）与源码链接（@allure.link）都要呈现
    assert "office-token-booster" in html, "渲染结果缺失 epic 标签"
    assert "内核层" in html, "渲染结果缺失 layer 分层标签"
    assert "tc-link" in html, "渲染结果缺失源码链接块"
    assert "diagnose() 源码" in html, "渲染结果缺失源码链接名称"
    assert "href=" in html, "渲染结果缺失链接 href"

    # 自定义维度标签（docs/allure-labels.md 定义）也要呈现为徽章
    assert "test_type: positive" in html, "渲染结果缺失 test_type 维度徽章"
    assert "component: diagnose" in html, "渲染结果缺失 component 维度徽章"
    assert "risk_area: data_integrity" in html, "渲染结果缺失 risk_area 维度徽章"
    assert "priority: P0" in html, "渲染结果缺失 priority 维度徽章"
    assert "suite: v0.6" in html, "渲染结果缺失 suite 维度徽章"

    # 失败信息也要呈现
    assert "boom" in html, "渲染结果未呈现失败信息"


@allure_feature("测试报告渲染器")
@allure_title("渲染器冒烟：main() 写出独立自包含 HTML 文件")
def test_renderer_main_writes_file(results_dir):
    """main() 能写出独立的 HTML 文件，且内容与渲染一致。"""
    out = Path(results_dir) / "report.html"
    sys.argv = ["render_allure_html.py", "--results", results_dir, "--output", str(out)]
    rc = main()
    assert rc == 0, f"main() 返回非 0: {rc}"
    assert out.is_file(), "main() 未写出 HTML 文件"
    content = out.read_text(encoding="utf-8")
    assert "测试A_生成提效报告通过" in content, "产出文件缺失用例名"
    assert content.lstrip().startswith("<!DOCTYPE html>"), "产出不是合法 HTML 文档"


if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    _report_dir = str(_root / "allure-results")
    print(f"Allure 数据 → {_report_dir}")
    sys.exit(pytest.main([__file__, "-v", f"--alluredir={_report_dir}"]))
