#!/usr/bin/env python3
"""Build the 天禧 AI upload zip for office-token-booster.

Deterministic whitelist packaging: only runtime files are included; network
clients (clawhub/skillhub) and dev-only tools (security_preflight /
test_recommendation) are excluded. A forbidden-pattern scan fails the build
if any dangerous import/feature slips into the packaged .py files.
"""
import os
import re
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Explicit whitelist (relative to REPO). Anything not listed is excluded.
WHITELIST = [
    "SKILL.md",
    "config.yaml",
    "LICENSE",
    "README.md",
    "QUICKSTART.md",
    "CHANGELOG.md",
    "usage-examples.md",
    "RELEASE_NOTES.md",
    "requirements-optional.txt",
    "requirements-dev.txt",
    "docs/allure-labels.md",
    "docs/portability-contract.md",
    "examples/ledger.json",
    "scripts/conversation.py",
    "scripts/diagnose.py",
    "scripts/host_cost.py",
    "scripts/host_hook.py",
    "scripts/ledger_agent.py",
    "scripts/qa.py",
    "scripts/report_engine.py",
    "scripts/skill_bridge.py",
    "scripts/skill_recommender.py",
    "scripts/executor.py",
    "scripts/type_registry.py",
    "scripts/type_registry.json",
    "scripts/quality.py",
]

# Forbidden patterns inside packaged .py files (security audit red lines).
FORBIDDEN = [
    r"import\s+urllib",
    r"from\s+urllib",
    r"import\s+requests",
    r"import\s+http\.client",
    r"socket\.create",
    r"os\.system",
    r"subprocess",
    r"os\.popen",
    r"\beval\(",
]

FORBIDDEN_RE = [re.compile(p) for p in FORBIDDEN]


def main():
    out = os.path.join(REPO, "office-token-booster.zip")
    missing = [f for f in WHITELIST if not os.path.exists(os.path.join(REPO, f))]
    if missing:
        print("ERROR: whitelist files missing:", missing, file=sys.stderr)
        return 1

    # Security scan over packaged .py files.
    hits = 0
    for rel in WHITELIST:
        if not rel.endswith(".py"):
            continue
        path = os.path.join(REPO, rel)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for rx in FORBIDDEN_RE:
            for m in rx.finditer(text):
                # allow harmless mentions (e.g. comments) — only flag real code lines
                line = text[max(0, m.start() - 200):m.start()].splitlines()[-1] if False else ""
                print(f"  [FORBIDDEN] {rel}: {rx.pattern}", file=sys.stderr)
                hits += 1
    if hits:
        print(f"ERROR: {hits} forbidden-pattern hit(s); aborting.", file=sys.stderr)
        return 1

    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in WHITELIST:
            z.write(os.path.join(REPO, rel), rel)
    size = os.path.getsize(out)
    print(f"OK: {out} ({size} bytes, {len(WHITELIST)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
