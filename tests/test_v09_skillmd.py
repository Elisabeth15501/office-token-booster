#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_v09_skillmd.py — office-token-booster v0.9 SKILL.md 定位一致性

v0.9 改了定位为 Option C「办公室 Token 洞察与提效助手」：本测试锁定 SKILL.md
不再「描述=能力」不符——即不允许再出现「能整理会议纪要 / 分析 Excel」这类
未实现的执行器承诺，且必须诚实声明「只度量、不执行」。

运行（pytest + Allure）：
  cd office-token-booster
  python -m pytest tests/test_v09_skillmd.py -v --alluredir=allure-results
"""

import re
import sys
from pathlib import Path

import pytest
import allure

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import attach_text, src_link

SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"


def _load():
    text = SKILL_MD.read_text(encoding="utf-8")
    # 取 frontmatter（首个 --- 与第二个 --- 之间）
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    fm = m.group(1) if m else ""
    return text, fm


def _section(text: str, header: str) -> str:
    """抽取某个含 `header` 的 `## ...` 小节正文（到下一个同级 `## ` 为止）。取不到返回空串。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("## ") and header in line:
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start + 1:end])


# 原 MVP 表里那些「未实现执行器」的触发/能力词（v0.9 必须不再作为承诺出现）
_FORBIDDEN_EXECUTOR_TRIGGERS = [
    "会议纪要整理", "会议纪要总结", "Excel 数据分析", "周报生成", "文档提炼",
]


@allure.feature("v0.9 定位一致性（Option C）")
@allure.story("SKILL.md 描述诚实化")
@allure.epic("office-token-booster")
@allure.label("layer", "测试基础设施")
@allure.label("test_type", "正向")
@allure.label("component", "documentation")
@allure.label("risk_area", "credibility")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9")
@src_link("SKILL.md", line=1, name="SKILL.md 源码")
@allure.title("v0.9 SKILL.md：name 不变 + version 0.9.0 + 描述含『洞察』")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("验证 name 仍为 office-token-booster、版本升到 0.9.0、描述体现 Option C 洞察定位。")
@pytest.mark.smoke
def test_v09_skillmd_metadata():
    text, fm = _load()
    with allure.step("断言 name / version / description"):
        attach_text(fm, "frontmatter")
        assert 'name: office-token-booster' in fm, "name 必须保持不变"
        assert 'version: 0.9.0' in fm, "版本应升到 0.9.0"
        assert "洞察" in fm, "description 应体现『洞察』定位（Option C）"
        assert "办公室 Token 洞察与提效助手" in fm


@allure.feature("v0.9 定位一致性（Option C）")
@allure.story("触发词去执行化")
@allure.epic("office-token-booster")
@allure.label("layer", "测试基础设施")
@allure.label("test_type", "回归")
@allure.label("component", "documentation")
@allure.label("risk_area", "credibility")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9")
@src_link("SKILL.md", line=16, name="triggers 源码")
@allure.title("v0.9 SKILL.md：触发词不再承诺未实现的执行器")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("验证 triggers 不含会议纪要整理/Excel 分析/周报生成/文档提炼等执行类词。")
@pytest.mark.regression
def test_v09_skillmd_no_executor_triggers():
    text, fm = _load()
    with allure.step("断言触发词均为度量语言"):
        attach_text(fm, "frontmatter triggers")
        for bad in _FORBIDDEN_EXECUTOR_TRIGGERS:
            assert bad not in fm, f"触发词不应再承诺未实现执行器：{bad}"
        # 正向：应含度量类触发词
        assert "办公提效复盘" in fm, "应含度量类触发词『办公提效复盘』"


@allure.feature("v0.9 定位一致性（Option C）")
@allure.story("MVP 表诚实化")
@allure.epic("office-token-booster")
@allure.label("layer", "测试基础设施")
@allure.label("test_type", "正向")
@allure.label("component", "documentation")
@allure.label("risk_area", "credibility")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9")
@src_link("SKILL.md", line=59, name="MVP 范围 源码")
@allure.title("v0.9 SKILL.md：明确『只度量、不执行』，MVP 表不列未实现执行器")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("验证正文诚实声明只度量不执行，且『能做什么(MVP 范围)』表不再把执行器列为能力。"
                    "注：账本示例 / CLI 用法里的任务类型名（如『周报生成』）是用户记账数据，不算能力承诺，"
                    "故禁词扫描仅限定在 MVP 表这一节，不扫全篇。")
@pytest.mark.smoke
def test_v09_skillmd_honest_scope():
    text, fm = _load()
    with allure.step("断言诚实边界声明（全篇）"):
        attach_text(text, "SKILL.md 正文")
        assert "只度量、不执行" in text, "必须明确声明只度量不执行"
    with allure.step("断言 MVP 范围表不把未实现执行器列为能力"):
        mvt = _section(text, "能做什么（真实范围 · MVP）")
        attach_text(mvt or "（未找到 MVP 小节）", "能做什么（MVP 范围）表")
        assert mvt, "应存在『能做什么（真实范围 · MVP）』小节"
        for bad in _FORBIDDEN_EXECUTOR_TRIGGERS:
            assert bad not in mvt, f"MVP 表不应把未实现执行器列为能力：{bad}"


@allure.feature("v0.9 定位一致性（Option C）")
@allure.story("QUICKSTART + 可选宿主接入声明")
@allure.epic("office-token-booster")
@allure.label("layer", "测试基础设施")
@allure.label("test_type", "正向")
@allure.label("component", "documentation")
@allure.label("risk_area", "credibility")
@allure.label("priority", "P2")
@allure.label("suite", "v0.9")
@src_link("SKILL.md", line=79, name="QUICKSTART 源码")
@allure.title("v0.9 SKILL.md：含 QUICKSTART 且 Non-goals 声明可选宿主接入（无网/无密钥）")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("验证新增 QUICKSTART 章节，且 Non-goals 诚实说明可选只读本机用量、不联网无密钥。")
@pytest.mark.smoke
def test_v09_skillmd_quickstart_and_hostcost_clause():
    text, fm = _load()
    with allure.step("断言 QUICKSTART 与宿主接入条款"):
        attach_text(text, "SKILL.md 正文")
        assert "## 快速开始（QUICKSTART）" in text, "应新增 QUICKSTART 章节"
        assert "可选" in text and "只读本机" in text, "Non-goals 应说明可选只读本机用量"
        assert ("不联网" in text or "无网络" in text) and ("无密钥" in text or "不硬编码密钥" in text), \
            "应声明不联网、无密钥（满足安全红线）"


if __name__ == "__main__":
    _root = Path(__file__).resolve().parent.parent
    _report_dir = str(_root / "allure-results")
    print(f"Allure 数据 → {_report_dir}")
    sys.exit(pytest.main([__file__, "-v", f"--alluredir={_report_dir}"]))
