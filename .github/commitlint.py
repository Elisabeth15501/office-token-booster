#!/usr/bin/env python3
"""轻量 Conventional Commits 校验器（零第三方依赖，CI 内运行）。

用法:
    python .github/commitlint.py                 # 校验 HEAD 提交
    python .github/commitlint.py <sha>            # 校验单个提交
    python .github/commitlint.py A..B            # 校验区间内所有提交（CI push 用 before..after）

本项目约定:
    类型(type) ∈ {feat, fix, test, docs, refactor, style, perf, build, ci, chore}
    格式:       <type>(<scope>): <subject>
    - scope 可选（如 test, ci, skill_bridge）
    - subject 小写开头、不以句号结尾、建议 ≤ 100 字
    - Merge / Revert 提交自动跳过
"""
import re
import subprocess
import sys

TYPES = {"feat", "fix", "test", "docs", "refactor", "style", "perf", "build", "ci", "chore"}
RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[a-z0-9_\-/.]+)\))?!?:\s+(?P<subject>.+)$", re.I)
MERGE_RE = re.compile(r"^merge\s", re.I)
REVERT_RE = re.compile(r"^revert\s", re.I)


def commits_in_range(spec):
    if not spec or spec == "HEAD":
        return ["HEAD"]
    if ".." in spec:
        out = subprocess.run(["git", "rev-list", spec], capture_output=True, text=True)
        return [c for c in out.stdout.split() if c]
    return [spec]


def subject_of(rev):
    out = subprocess.run(["git", "log", "-1", "--format=%s", rev], capture_output=True, text=True)
    return out.stdout.strip()


def main():
    spec = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    revs = commits_in_range(spec)
    errors, warns = [], []
    for rev in revs:
        subj = subject_of(rev)
        if MERGE_RE.match(subj) or REVERT_RE.match(subj):
            continue
        m = RE.match(subj)
        if not m:
            errors.append(
                f"[{rev[:8]}] 提交信息不符合 Conventional Commits：\n        {subj!r}\n"
                f"        期望格式: feat(scope): 描述"
            )
            continue
        if m.group("type").lower() not in TYPES:
            errors.append(f"[{rev[:8]}] 未知类型 '{m.group('type')}'；允许: {sorted(TYPES)}")
        if m.group("subject").endswith("."):
            warns.append(f"[{rev[:8]}] subject 以句号结尾（建议去掉）")
        if len(m.group("subject")) > 100:
            warns.append(f"[{rev[:8]}] subject 过长（>100 字）")
    for w in warns:
        print("⚠️", w)
    if errors:
        print("❌ 提交信息校验失败：")
        for e in errors:
            print("  ", e)
        sys.exit(1)
    print(f"✅ 提交信息校验通过（检查 {len(revs)} 个提交）")
    sys.exit(0)


if __name__ == "__main__":
    main()
