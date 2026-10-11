#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.0.7 类型字典别名收敛回归测试（对应安全优化方案 P1-D2）。

守卫点：
- 正例：保留的**动词短语 / 英文短语**别名仍能正确归一到标准类型；
- 负例：被移除的**单词级名词**（文档 / 数据 / 代码 / 邮件 / ppt / 报表 等）
  在普通提及语境下**不得**被误判为记账类型（消除歧义、避免与其它技能抢触发）。

匹配语义：conversation._detect_type 对字典别名做子串匹配；本测试用「非记账句式」
（不含『记一笔 / 生成了 / 做了』等记账词）模拟普通对话提及，验证不会误命中。
"""
from __future__ import annotations

import allure
import sys
from pathlib import Path

# 允许从任意目录运行（与 conversation 保持一致的 sibling import）。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import conversation  # noqa: E402
from conversation import _detect_type  # noqa: E402
from diagnose import load_ledger, diagnose  # noqa: E402


def _fresh_diag():
    """用内置样例账本构建一个 Diagnosis（含已知标准类型），供 _detect_type 使用。

    每次刷新 conversation._REGISTRY，确保读到最新的 type_registry.json。
    """
    ledger_path = Path(__file__).resolve().parent.parent / "examples" / "ledger.json"
    if ledger_path.is_file():
        diag = diagnose(load_ledger(str(ledger_path)))
    else:
        diag = diagnose([])
    conversation._REGISTRY = conversation._load_registry()
    return diag


_POSITIVE = [
    ("帮我写文档", "文档撰写"),
    ("帮我做ppt", "PPT制作"),
    ("分析数据算一下", "数据分析"),
    ("帮我写代码", "代码编写"),
    ("帮我回邮件", "邮件草拟"),
]

_NEGATIVE = [
    "我看了这篇文档，写得不错",          # 普通提及「文档」
    "今天邮件特别多，回不过来",          # 普通提及「邮件」
    "这段代码有个 bug 要修",             # 普通提及「代码」
    "给我看看这个 PPT 模板好不好看",     # 普通提及「PPT」（大写，且非短语别名）
    "这些数据太乱了",                    # 普通提及「数据」，不含「数据分析 / 数据报表」（且无触发动词）
    ("记一笔 周报 花了 1800 token", "周报生成"),  # 记账句式仍可经标准名包含命中
]


@allure.title("v1.0.7 类型字典：保留的动词短语别名仍能正确归一")
@allure.severity(allure.severity_level.NORMAL)
def test_kept_phrase_aliases_still_resolve():
    diag = _fresh_diag()
    for phrase, expected in _POSITIVE:
        ttype, _ = _detect_type(phrase, diag)
        assert ttype == expected, f"短语别名归失败: 输入={phrase!r} 期望={expected!r} 实际={ttype!r}"


@allure.title("v1.0.7 类型字典：单词级名词在普通提及下不得误判为记账类型")
@allure.severity(allure.severity_level.CRITICAL)
def test_removed_noun_aliases_do_not_overmatch():
    diag = _fresh_diag()
    for phrase in _NEGATIVE:
        if isinstance(phrase, tuple):
            continue  # 记账句式正例，单独测
        ttype, _ = _detect_type(phrase, diag)
        assert ttype is None, f"普通提及被误判为记账类型: 输入={phrase!r} 命中={ttype!r}"


@allure.title("v1.0.7 类型字典：记账句式中的单词仍经标准名包含正确命中")
@allure.severity(allure.severity_level.NORMAL)
def test_bare_word_via_booking_phrase_still_resolves():
    diag = _fresh_diag()
    for phrase in _NEGATIVE:
        if not isinstance(phrase, tuple):
            continue
        text, expected = phrase
        ttype, _ = _detect_type(text, diag)
        assert ttype == expected, f"记账句式归失败: 输入={text!r} 期望={expected!r} 实际={ttype!r}"
