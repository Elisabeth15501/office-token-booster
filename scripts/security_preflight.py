#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""security_preflight.py — office-token-booster 执行层安全预检（CI 轻量闸门）

扫描指定目录的 .py 源码，按执行层四红线做**轻量静态启发式**检查：
  R1 危险执行：eval( / exec( / os.system / subprocess / __import__(
  R2 网络外发：urllib / requests / http.client / socket / smtp / urlopen 等
  R3 硬编码密钥：AKIA* / sk-* / ghp_* / xox* / JWT / password=/api_key=/token= 等
  R4 字段转义（警告级）：对外输出用户字段处是否使用 html.escape

退出码：0 = 通过（无红线）；1 = 命中红线（CI 应 fail）。

⚠️ 这是**浅层正则扫描，不是安全保证**：可被拆分字符串、环境变量、动态拼接、
十六进制/编码绕过。它的价值是拦住「手滑把密钥/危险调用直接写进仓库」的低级错误，
而非对抗蓄意绕过。请勿在文档/承诺中称其为「零风险保证」。

设计原则：纯标准库、无第三方依赖、无网络、无副作用，可被 CI 直接调用。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# R1：危险执行（排除 execute_render / executor / _do_execute 等合法标识符）
# 注意：不收录裸 compile( —— re.compile( 在几乎所有文件出现，会全量误报。
# __import__( 是本次加固重点（可等价 os.system 跑任意代码，旧正则漏检）；
# 但仅匹配危险目标模块，避免误伤 __import__("sys").stderr 这类良性用法。
_RE_DANGER_EXEC = re.compile(
    r"(?<![\w.])(eval|exec)\s*\(|(?<![\w.])os\.system\s*\("
    r"|(?<![\w.])subprocess\.(?:call|run|Popen|check_output|check_call)\s*\("
    r"|(?<![\w.])__import__\s*\(\s*[\"'](?:os|subprocess|builtins|ctypes|"
    r"importlib|shutil|socket|pickle|codecs|marshal)[\"']")
# R2：网络外发（socket. 覆盖 socket.socket / create_connection / connect 等；
# 另补 urllib3 / pycurl / grpc / websocket / httplib2 等常见客户端）
_RE_NETWORK = re.compile(
    r"\b(urllib\.request|urllib\.parse|requests|http\.client|aiohttp|httpx|smtplib|"
    r"socket\.|urlopen|urlretrieve|urllib3|pycurl|grpc|websocket|httplib2)\b")
# R3：硬编码密钥 / 明文凭证（轻量启发式，非安全保证——详见模块 docstring）
_RE_SECRET = re.compile(
    r"(AKIA[0-9A-Z]{16}"
    r"|sk-[A-Za-z0-9]{20,}"
    r"|ghp_[A-Za-z0-9]{36}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}"
    r"|password\s*=\s*[\"'][^\"']{4,}[\"']"
    r"|secret\s*=\s*[\"'][^\"']{4,}[\"']"
    r"|api[_-]?key\s*=\s*[\"'][^\"']{4,}[\"']"
    r"|access[_-]?token\s*=\s*[\"'][^\"']{4,}[\"']"
    r"|client[_-]?secret\s*=\s*[\"'][^\"']{4,}[\"']"
    r"|private[_-]?key\s*=\s*[\"'][^\"']{4,}[\"']"
    r"|token\s*=\s*[\"'][^\"']{4,}[\"']"
    r"|pwd\s*=\s*[\"'][^\"']{4,}[\"'])")
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
