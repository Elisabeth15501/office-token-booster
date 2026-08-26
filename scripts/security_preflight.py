#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""security_preflight.py — office-token-booster 执行层安全预检（CI 红线）

扫描指定目录的 .py 源码，检测执行层四红线：
  R1 危险执行：eval( / exec( / os.system / subprocess 调用（非白名单）
  R2 网络外发：urllib.request / requests / http.client / socket / smtp / urlopen
  R3 硬编码密钥：AKIA* / sk-* / ghp_* / xox* / JWT / password=明文 等
  R4 字段转义（警告级）：对外输出用户字段处是否使用 html.escape

退出码：0 = 通过（无红线）；1 = 命中红线（CI 应 fail）。

设计原则：纯标准库、无第三方依赖、无网络、无副作用，可被 CI 直接调用。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# R1：危险执行（排除 execute_render / executor / _do_execute 等合法标识符）
_RE_DANGER_EXEC = re.compile(
    r"(?<![\w.])(eval|exec)\s*\(|(?<![\w.])os\.system\s*\("
    r"|(?<![\w.])subprocess\.(?:call|run|Popen|check_output|check_call)\s*\(")
# R2：网络外发
_RE_NETWORK = re.compile(
    r"\b(urllib\.request|requests|http\.client|aiohttp|httpx|smtplib|"
    r"socket\.socket|urlopen|urlretrieve)\b")
# R3：硬编码密钥 / 明文凭证
_RE_SECRET = re.compile(
    r"(AKIA[0-9A-Z]{16}"
    r"|sk-[A-Za-z0-9]{20,}"
    r"|ghp_[A-Za-z0-9]{36}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}"
    r"|password\s*=\s*[\"'][^\"']{8,}[\"']"
    r"|secret\s*=\s*[\"'][^\"']{8,}[\"'])")
# R4：字段转义（仅做信息/警告统计，不 fail）
_RE_ESCAPE = re.compile(r"html\.escape")
_RE_IMPORT_HTML = re.compile(r"^\s*import\s+html|from\s+html\s+import", re.M)

# R1 白名单（预检脚本自身含 exec/eval 关键词字符串，豁免其 R1 检查）
_WHITELIST_FILES = {"security_preflight.py", "test_security_preflight.py"}
# R2 豁免：以下为显式联网搜索客户端（设计内允许联网，仅豁免 R2）
_NETWORK_ALLOWED = {"skillhub_client.py", "clawhub_client.py", "security_preflight.py", "test_security_preflight.py"}


def scan_file(path: Path):
    """返回 (reds, warns) 列表。"""
    reds, warns = [], []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return reds, warns
    name = path.name
    skip_r1 = name in _WHITELIST_FILES
    skip_r2 = name in _NETWORK_ALLOWED
    for i, line in enumerate(text.splitlines(), 1):
        if not skip_r1 and _RE_DANGER_EXEC.search(line):
            reds.append(f"[{name}:{i}] R1 危险执行: {line.strip()[:80]}")
        if not skip_r2 and _RE_NETWORK.search(line):
            reds.append(f"[{name}:{i}] R2 网络外发: {line.strip()[:80]}")
        if _RE_SECRET.search(line):
            reds.append(f"[{name}:{i}] R3 硬编码密钥/凭证: {line.strip()[:80]}")
    # R4 统计（项目级，非逐行）
    if _RE_IMPORT_HTML.search(text) or _RE_ESCAPE.search(text):
        warns.append(f"[{name}] R4 html.escape 已使用（{len(_RE_ESCAPE.findall(text))} 处）")
    return reds, warns


def main(argv=None):
    ap = argparse.ArgumentParser(description="执行层安全预检（四红线）")
    ap.add_argument("paths", nargs="*", default=["scripts"],
                    help="要扫描的目录或文件（默认 scripts）")
    args = ap.parse_args(argv)

    reds, warns = [], []
    scanned = 0
    for p in args.paths:
        pp = Path(p)
        files = [pp] if pp.is_file() else sorted(pp.rglob("*.py"))
        for f in files:
            if f.name.startswith("."):
                continue
            scanned += 1
            r, w = scan_file(f)
            reds += r
            warns += w

    print(f"[安全预检] 扫描 {scanned} 个 .py 文件")
    for w in warns:
        print("  [warn] " + w)
    if reds:
        print(f"[FAIL] 命中 {len(reds)} 条红线：")
        for r in reds:
            print("  [red] " + r)
        return 1
    print("[PASS] 未命中任何红线（R1 危险执行 / R2 网络外发 / R3 硬编码密钥）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
