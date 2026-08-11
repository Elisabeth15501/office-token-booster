# -*- coding: utf-8 -*-
"""tests/helpers.py — 测试共享辅助（Allure 可视化 / 账本读取）

把三份测试里重复出现的「Token 节省率 HTML 柱状图」与账本读取/附件辅助集中到一处，
避免 copy-paste（DRY，且便于在 Allure 报告里统一增强可视化）。
"""

import json
import subprocess
from pathlib import Path

import allure


def read_ledger(ledger_path):
    """读取临时账本 JSON，返回 dict。"""
    with open(ledger_path, encoding="utf-8") as f:
        return json.load(f)


def attach_ledger(ledger_path, name="账本内容(JSON)"):
    """把账本内容作为 JSON 附件挂到 Allure，便于报告里直接查看写回结果。"""
    allure.attach(json.dumps(read_ledger(ledger_path), ensure_ascii=False, indent=2),
                  name=name, attachment_type=allure.attachment_type.JSON)


def attach_text(text, name):
    """把一段文本作为 TEXT 附件挂到 Allure。"""
    allure.attach(str(text), name=name, attachment_type=allure.attachment_type.TEXT)


def build_token_savings_chart(tasks, overall_pct):
    """生成 HTML 柱状图，展示各类型任务的 token 节省情况。"""
    rows = []
    max_tokens = max((t["baseline_tokens"] for t in tasks), default=1) or 1
    colors = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#F44336", "#00BCD4"]

    for i, t in enumerate(tasks):
        saved = t["baseline_tokens"] - t["skill_tokens"]
        pct = (saved / t["baseline_tokens"] * 100) if t["baseline_tokens"] else 0
        bar_width = (t["baseline_tokens"] / max_tokens) * 200
        skill_width = (t["skill_tokens"] / max_tokens) * 200
        color = colors[i % len(colors)]
        rows.append(f"""
        <tr>
            <td style="padding:6px 12px;border-bottom:1px solid #eee;font-weight:500;">{t['type']}</td>
            <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#666;">{t['baseline_tokens']:,}</td>
            <td style="padding:6px 12px;border-bottom:1px solid #eee;color:#666;">{t['skill_tokens']:,}</td>
            <td style="padding:6px 12px;border-bottom:1px solid #eee;">
                <div style="display:flex;align-items:center;gap:4px;">
                    <div style="width:{bar_width}px;height:18px;background:{color}33;border-radius:3px;position:relative;">
                        <div style="width:{skill_width}px;height:18px;background:{color};border-radius:3px;"></div>
                    </div>
                    <span style="font-size:12px;color:{color};font-weight:600;">{pct:.1f}%</span>
                </div>
            </td>
            <td style="padding:6px 12px;border-bottom:1px solid #eee;font-weight:600;color:{color};">{saved:,}</td>
        </tr>
        """)

    html = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;padding:16px;">
        <h3 style="margin:0 0 4px 0;color:#333;">Token 节省分析</h3>
        <p style="margin:0 0 16px 0;color:#666;font-size:13px;">整体节省率: <strong style="color:#4CAF50;font-size:16px;">{overall_pct:.1f}%</strong>　|　共 {len(tasks)} 条任务</p>
        <table style="border-collapse:collapse;width:100%;font-size:13px;">
            <thead>
                <tr style="background:#f5f5f5;">
                    <th style="padding:8px 12px;text-align:left;">任务类型</th>
                    <th style="padding:8px 12px;text-align:left;">Baseline</th>
                    <th style="padding:8px 12px;text-align:left;">Skill</th>
                    <th style="padding:8px 12px;text-align:left;width:240px;">节省率</th>
                    <th style="padding:8px 12px;text-align:left;">节省 Token</th>
                </tr>
            </thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
    </div>
    """
    return html


def _repo_blob_base():
    """返回 GitHub blob URL 基址（含当前 commit），用于 @allure.link 源码跳转。

    形如 https://github.com/<owner>/<repo>/blob/<sha>。
    无 git 信息（脱机 / 无 origin remote）时返回 None，调用方应退化为无操作装饰器。
    """
    try:
        repo_root = Path(__file__).resolve().parent.parent
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=repo_root, timeout=5,
        )
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=repo_root, timeout=5,
        )
        if remote.returncode == 0 and commit.returncode == 0:
            url = remote.stdout.strip()
            if url.endswith(".git"):
                url = url[:-4]
            sha = commit.stdout.strip()
            if url and sha:
                return f"{url}/blob/{sha}"
    except Exception:
        pass
    return None


def src_link(rel_path, line=None, name="源码"):
    """返回一个 allure.link 装饰器，指向 GitHub 上对应文件/行，便于报告里一键看源码。

    用法示例：
        @src_link("scripts/diagnose.py", line=275, name="diagnose() 源码")
        def test_xxx(): ...

    - 无 allure-pytest 或无法取得 git 信息时，退化为无操作装饰器，
      保证测试在非标准环境（如仅跑纯 pytest）下也能正常工作。
    - 基于当前 HEAD 的 commit SHA 生成固定链接，作品集报告里的源码链接始终可溯源。
    """
    try:
        import allure as _allure
    except ImportError:
        return lambda f: f
    base = _repo_blob_base()
    if not base:
        return lambda f: f
    url = f"{base}/{rel_path}"
    if line is not None:
        url += f"#L{line}"
    return _allure.link(url, name=name, link_type="source")
