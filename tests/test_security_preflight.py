#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_security_preflight.py — 执行层四红线预检单元测试"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from security_preflight import scan_file, main  # noqa: E402


def _write(content, name="sample.py"):
    # NamedTemporaryFile 会忽略 name 参数并生成随机文件名，
    # 但安全预检的豁免是基于 path.name 判定的，因此必须把文件
    # 真正命名为传入的 basename，否则豁免（如 R2 联网白名单）不生效。
    tmp = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8")
    tmp.write(content)
    tmp.close()
    target = Path(tmp.name).with_name(name)
    if target != Path(tmp.name):
        os.rename(tmp.name, target)
    return target


@pytest.mark.smoke
def test_detect_danger_exec():
    p = _write("x = eval('1+1')\n")
    try:
        reds, _ = scan_file(p)
        assert any("R1" in r for r in reds), reds
    finally:
        p.unlink()


@pytest.mark.smoke
def test_detect_network():
    p = _write("import urllib.request\nurllib.request.urlopen('http://x')\n")
    try:
        reds, _ = scan_file(p)
        assert any("R2" in r for r in reds), reds
    finally:
        p.unlink()


@pytest.mark.smoke
def test_detect_secret():
    p = _write("token = 'sk-" + "a" * 24 + "'\n")
    try:
        reds, _ = scan_file(p)
        assert any("R3" in r for r in reds), reds
    finally:
        p.unlink()


def test_network_allowed_skip():
    """联网搜索客户端（设计内允许联网）应豁免 R2。"""
    p = _write("import urllib.request\nurllib.request.urlopen('http://x')\n", "skillhub_client.py")
    try:
        reds, _ = scan_file(p)
        assert not any("R2" in r for r in reds), reds
    finally:
        p.unlink()


def test_clean_passes():
    p = _write("def f():\n    return 1\n")
    try:
        reds, _ = scan_file(p)
        assert reds == [], reds
    finally:
        p.unlink()


@pytest.mark.smoke
def test_main_on_scripts_passes():
    """当前 scripts/ 应通过预检（无红线）。"""
    rc = main(["scripts"])
    assert rc == 0, "scripts/ 应通过安全预检"
