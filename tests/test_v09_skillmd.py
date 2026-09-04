#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_v09_skillmd.py — office-token-booster SKILL.md 定位一致性

方向 B（v0.9.5）：定位翻转为「办公室 AI 提效助手 —— 执行与度量一体」。
本测试锁定 SKILL.md 诚实声明：既执行（周报/纪要/数据分析/文档/PPT 大纲）又度量，
且不替代专业排版/多模态生成、不出现超出实现范围的过度承诺（自动发邮件等）。

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


# 方向 B：执行层已落地，但不得「过度承诺」超出已实现范围（这些词不得出现）
_OVERPROMISE_FORBIDDEN = [
    "自动发送邮件", "多模态生成", "专业排版", "自动删除文件", "连接数据库改数据",
]


@allure.feature("v1.0 定位一致性（方向 B）")
@allure.story("SKILL.md 描述诚实化")
@allure.epic("office-token-booster")
@allure.label("layer", "测试基础设施")
@allure.label("test_type", "正向")
@allure.label("component", "documentation")
@allure.label("risk_area", "credibility")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9.5-direction-b")
@src_link("SKILL.md", line=1, name="SKILL.md 源码")
@allure.title("v1.0 SKILL.md：name 不变 + version >= 0.9.0 + 描述诚实声明『执行与度量一体』")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("验证 name 仍为 office-token-booster、版本 >= 0.9.0（对 1.0.0 及更高版本均成立）、描述体现方向 B 执行+度量一体定位。")
@pytest.mark.smoke
def test_v09_skillmd_metadata():
    text, fm = _load()
    with allure.step("断言 name / version / description"):
        attach_text(fm, "frontmatter")
        assert 'name: office-token-booster' in fm, "name 必须保持不变"
        import re as _re
        _m = _re.search(r'version:\s*([0-9]+)\.([0-9]+)\.([0-9]+)', fm)
        assert _m, "frontmatter 必须含 version 字段"
        _ver = tuple(int(_m.group(i)) for i in range(1, 4))
        assert _ver >= (0, 9, 0), f"版本应 >= 0.9.0，实际 {_ver}"
        assert "办公室 AI 提效助手" in fm, "方向 B：名称翻转为「办公室 AI 提效助手」"
        assert "执行与度量一体" in fm, "应诚实声明执行与度量一体（既做又记）"
        assert "自动记下" in fm, "应声明执行后自动记账"


@allure.feature("v1.0 定位一致性（方向 B）")
@allure.story("执行触发词诚实化")
@allure.epic("office-token-booster")
@allure.label("layer", "测试基础设施")
@allure.label("test_type", "正向")
@allure.label("component", "documentation")
@allure.label("risk_area", "credibility")
@allure.label("priority", "P1")
@allure.label("suite", "v0.9.5-direction-b")
@src_link("SKILL.md", line=16, name="triggers 源码")
@allure.title("v1.0 SKILL.md：触发词诚实承诺已落地的执行器")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("验证 triggers 含 task_execution 意图与执行类示例（周报/纪要/数据分析/文档/PPT），"
                    "且不出现超出实现范围的过度承诺（自动发邮件/多模态/专业排版等）。")
@pytest.mark.smoke
def test_v09_skillmd_executor_triggers_present():
    text, fm = _load()
    with allure.step("断言执行类触发词已诚实声明"):
        attach_text(fm, "frontmatter triggers")
        assert "task_execution" in fm, "应新增 task_execution 意图"
        for good in ["帮我写一份周报", "整理一下会议纪要", "分析这个 CSV", "提炼成要点", "PPT 大纲"]:
            assert good in fm, f"触发词应含已落地的执行示例：{good}"
    with allure.step("断言描述不出现超出实现范围的过度承诺"):
        # 仅扫 description 能力声明区（避开 non_triggers / Non-goals 里的免责措辞）
        m = re.search(r"description:\s*(.*?)(?:\n\w+:|$)", fm, re.S)
        desc = m.group(1) if m else fm
        for bad in _OVERPROMISE_FORBIDDEN:
            assert bad not in desc, f"description 不得过度承诺未实现能力：{bad}"


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
@allure.title("v1.0 SKILL.md：明确『既执行又度量』且不替代专业排版/多模态")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("验证正文诚实声明既执行又度量，且边界明确不替代专业排版/多模态生成；"
                    "『能做什么』表应列出已落地的任务执行能力。")
@pytest.mark.smoke
def test_v09_skillmd_honest_scope():
    text, fm = _load()
    with allure.step("断言诚实边界声明（执行+度量，不替代专业工具）"):
        attach_text(text, "SKILL.md 正文")
        assert "既执行、又度量" in text, "应诚实声明既执行又度量"
        assert "不替代" in text, "应声明不替代专业排版/多模态类工具"
        assert "纯本地" in text or "不联网" in text, "应声明执行层纯本地/不联网"
    with allure.step("断言『能做什么』表列出已落地的任务执行能力"):
        sec = _section(text, "能做什么（真实范围）")
        attach_text(sec or "（未找到小节）", "能做什么表")
        assert sec, "应存在『能做什么（真实范围）』小节"
        assert "任务执行（方向 B）" in sec, "能做什么表应列出已落地的任务执行能力"
        assert "自动记账" in sec, "执行能力应说明自动记账闭环"


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
