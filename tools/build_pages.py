#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/build_pages.py — 构建 office-token-booster 的 GitHub Pages 作品集站点

把仓库里的「文档 + 示例 + 测试结果」统一渲染成一个静态站点，写入 public/：

    public/
      index.html                 站点门户（导航到以下各块）
      readme.html                README.md
      skill.html                 SKILL.md（去 frontmatter）
      examples.html              usage-examples.md（示例对话）
      example-report.html        由 examples/ledger.json 用 report_engine 生成（示例报告）
      example-report.md          同上报告的 Markdown 版（兜底/可下载）
      allure-report.html         pytest+Allure 测试结果（CI 已由 render_allure_html 生成）
      assets/site.css            统一视觉样式

设计原则：纯标准库 + 项目自带脚本，零第三方运行时依赖，CI 内可完全复现
（生成的 HTML 被 .gitignore 忽略，不入库）。

用法：
    python tools/build_pages.py
"""

import html
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC = REPO_ROOT / "public"
ASSETS = PUBLIC / "assets"

GITHUB_REPO = "Elisabeth15501/office-token-booster"
GITHUB_BLOB = f"https://github.com/{GITHUB_REPO}/blob/main"
VERSION = "1.0.0"

# 站点内各页面的相对链接（全部位于 public/ 根，便于本地 file:// 与 Pages 同构）
NAV = [
    ("首页", "index.html"),
    ("README", "readme.html"),
    ("SKILL.md", "skill.html"),
    ("示例对话", "examples.html"),
    ("示例报告", "example-report.html"),
    ("测试结果", "allure-report.html"),
]


def _rewrite_md_links(body):
    """把指向仓库内 .md 的相对链接改写为 GitHub blob 绝对链接，避免 Pages 上 404。"""
    def _rep(m):
        url = m.group(1)
        if url.startswith(("http://", "https://", "#", "/")):
            return m.group(0)
        return f'href="{GITHUB_BLOB}/{url}"'
    return re.sub(r'href="([^"]+\.md)"', _rep, body)


# ---------------------------------------------------------------------------
# 共享样式（Linear 风格：浅色卡片 + 主色 #2563eb）
# ---------------------------------------------------------------------------

SITE_CSS = """\
:root{
  --bg:#f7f8fa; --card:#ffffff; --fg:#1f2937; --muted:#6b7280;
  --border:#e5e7eb; --accent:#2563eb; --accent-soft:#eff6ff;
  --code-bg:#0f172a; --code-fg:#e2e8f0;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Microsoft YaHei",sans-serif;
  background:var(--bg); color:var(--fg); line-height:1.6;
}
a{color:var(--accent);text-decoration:none;}
a:hover{text-decoration:underline;}

/* 顶部导航 */
.site-nav{
  position:sticky; top:0; z-index:10; background:rgba(255,255,255,.9);
  backdrop-filter:saturate(180%) blur(8px);
  border-bottom:1px solid var(--border); padding:0 20px;
  display:flex; align-items:center; gap:18px; height:54px;
}
.site-nav .brand{font-weight:700; color:var(--fg); margin-right:auto; font-size:15px;}
.site-nav .brand span{color:var(--accent);}
.site-nav a{color:var(--muted); font-size:14px; font-weight:500; padding:6px 2px; border-bottom:2px solid transparent;}
.site-nav a:hover{color:var(--fg); text-decoration:none;}
.site-nav a.active{color:var(--accent); border-bottom-color:var(--accent);}

/* 容器 */
.wrap{max-width:960px; margin:0 auto; padding:28px 20px 64px;}

/* 门户 hero */
.hero{background:var(--card); border:1px solid var(--border); border-radius:16px; padding:28px; margin-bottom:22px;}
.hero h1{margin:0 0 6px; font-size:26px;}
.hero .badge{display:inline-block; background:var(--accent-soft); color:var(--accent); border:1px solid #bfdbfe;
  font-size:12px; font-weight:700; padding:3px 10px; border-radius:999px; margin-bottom:10px;}
.hero p{color:var(--muted); margin:8px 0 0;}

/* 卡片网格 */
.grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:16px;}
.card{background:var(--card); border:1px solid var(--border); border-radius:14px; padding:18px; transition:.15s;}
.card:hover{border-color:var(--accent); box-shadow:0 4px 16px rgba(37,99,235,.08);}
.card h3{margin:0 0 6px; font-size:16px;}
.card p{margin:0 0 12px; color:var(--muted); font-size:13px;}
.card .go{font-weight:600; font-size:14px;}

/* 文档内容（md2html 输出） */
.md-h1{font-size:24px; margin:8px 0 14px; padding-bottom:8px; border-bottom:2px solid var(--border);}
.md-h2{font-size:19px; margin:26px 0 10px; padding-bottom:6px; border-bottom:1px solid var(--border);}
.md-h3{font-size:16px; margin:20px 0 8px;}
.md-h4,.md-h5,.md-h6{font-size:14px; margin:16px 0 6px; color:var(--fg);}
.md-p{margin:10px 0;}
.md-list{padding-left:22px; margin:10px 0;}
.md-list li{margin:4px 0;}
.md-nested{margin:4px 0;}
.md-quote{border-left:3px solid var(--accent); background:var(--accent-soft);
  margin:12px 0; padding:8px 14px; color:var(--fg); border-radius:0 8px 8px 0;}
.md-hr{border:none; border-top:1px solid var(--border); margin:22px 0;}
.md-code{background:var(--accent-soft); color:#1e40af; padding:2px 6px; border-radius:6px;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:.9em;}
.md-pre{background:var(--code-bg); color:var(--code-fg); padding:14px; border-radius:10px;
  overflow:auto; font-size:13px; line-height:1.5;}
.md-pre code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; white-space:pre;}
.md-table-wrap{overflow:auto; margin:12px 0;}
.md-table{border-collapse:collapse; width:100%; font-size:14px;}
.md-table th,.md-table td{border:1px solid var(--border); padding:8px 12px; text-align:left;}
.md-table th{background:#f1f5f9; font-weight:600;}
.md-img{max-width:100%; border:1px solid var(--border); border-radius:8px;}

footer{color:var(--muted); font-size:13px; text-align:center; margin-top:40px;}
"""


# ---------------------------------------------------------------------------
# 页面外壳
# ---------------------------------------------------------------------------

def _nav_html(active):
    items = []
    for label, href in NAV:
        cls = "active" if href == active else ""
        items.append(f'<a class="{cls}" href="{href}">{label}</a>')
    brand = f'<a class="brand" href="index.html">office<span>-token-booster</span></a>'
    return f'<nav class="site-nav">{brand}{"".join(items)}</nav>'


def make_page(title, body_html, *, active, nav=True):
    nav_block = _nav_html(active) if nav else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · office-token-booster</title>
<link rel="stylesheet" href="assets/site.css">
</head><body>
{nav_block}
<main class="wrap">
{body_html}
</main>
<footer>office-token-booster v{VERSION} · MIT License · <a href="https://github.com/{GITHUB_REPO}" target="_blank" rel="noopener">GitHub 仓库</a></footer>
</body></html>"""


# ---------------------------------------------------------------------------
# 构建步骤
# ---------------------------------------------------------------------------

def build_doc_page(src_name, out_name, title, *, strip_frontmatter=False, active=None):
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import md2html  # noqa: WPS433 (本地工具模块)
    src = REPO_ROOT / src_name
    body = md2html.convert(src.read_text(encoding="utf-8"),
                           strip_frontmatter=strip_frontmatter)
    body = _rewrite_md_links(body)
    out = PUBLIC / out_name
    out.write_text(make_page(title, body, active=out_name), encoding="utf-8")
    print(f"[OK] {src_name} -> {out_name}")


def build_example_report():
    """用项目自带 report_engine 由 examples/ledger.json 生成示例报告。"""
    ledger = REPO_ROOT / "examples" / "ledger.json"
    if not ledger.is_file():
        print(f"[跳过] 示例账本不存在：{ledger}", file=sys.stderr)
        return
    for fmt, ext in (("html", "html"), ("markdown", "md")):
        out = PUBLIC / f"example-report.{ext}"
        cmd = [sys.executable, str(REPO_ROOT / "scripts" / "report_engine.py"),
               str(ledger), "--format", fmt, "-o", str(out)]
        try:
            subprocess.run(cmd, check=True, cwd=str(REPO_ROOT),
                           capture_output=True, text=True)
            print(f"[OK] 示例报告({fmt}) -> {out.name}")
        except subprocess.CalledProcessError as e:
            print(f"[错误] 生成示例报告失败：{e.stderr}", file=sys.stderr)
            raise


def ensure_allure_report():
    """确认 public/allure-report.html 存在；缺失且有 allure-results 时本地补渲染。"""
    target = PUBLIC / "allure-report.html"
    if target.is_file():
        print(f"[OK] 已存在 {target.name}")
        return
    results = REPO_ROOT / "allure-results"
    if results.is_dir():
        cmd = [sys.executable, str(REPO_ROOT / "tools" / "render_allure_html.py"),
               "--results", str(results), "--output", str(target)]
        try:
            subprocess.run(cmd, check=True, cwd=str(REPO_ROOT),
                           capture_output=True, text=True)
            print(f"[OK] 本地补渲染 {target.name}")
            return
        except subprocess.CalledProcessError as e:
            print(f"[警告] 补渲染 allure 报告失败：{e.stderr}", file=sys.stderr)
    print("[警告] 未找到 public/allure-report.html（CI 中应由 test job 生成）",
          file=sys.stderr)


def build_index():
    cards = [
        ("📘 README", "项目说明、特性、快速开始、测试与分享方式。",
         "readme.html", "阅读 README"),
        ("🧩 SKILL.md", "技能定义、核心卖点、触发流与合规范围。",
         "skill.html", "查看技能定义"),
        ("💬 示例对话", "4 条真实示例：周报 / 会议纪要 / 记账闭环 / 提效报告。",
         "examples.html", "看示例对话"),
        ("📊 示例报告", "由 examples/ledger.json 实跑生成的提效报告。",
         "example-report.html", "看示例报告"),
        ("🧪 测试结果", "pytest + Allure 全量测试报告（166 用例）。",
         "allure-report.html", "看测试报告"),
    ]
    grid = ['<div class="grid">']
    for title, desc, href, go in cards:
        grid.append(
            f'<a class="card" href="{href}"><h3>{title}</h3>'
            f'<p>{desc}</p><span class="go">{go} →</span></a>'
        )
    grid.append("</div>")
    hero = f"""<div class="hero">
  <span class="badge">v{VERSION} · 参赛版正式发布</span>
  <h1>office-token-booster</h1>
  <p>办公室 AI 提效助手 —— 既帮你做办公交付物，又自动记下每次省了多少 Token 和时间。
  执行与度量一体，让「AI 提效」看得见、算得清、可验证。</p>
</div>"""
    body = hero + "\n".join(grid)
    out = PUBLIC / "index.html"
    out.write_text(make_page("作品集", body, active="index.html"), encoding="utf-8")
    print(f"[OK] index.html")


def main():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "site.css").write_text(SITE_CSS, encoding="utf-8")
    print(f"[OK] assets/site.css")

    build_doc_page("README.md", "readme.html", "README", active="readme.html")
    build_doc_page("SKILL.md", "skill.html", "SKILL.md",
                   strip_frontmatter=True, active="skill.html")
    build_doc_page("usage-examples.md", "examples.html", "示例对话",
                   active="examples.html")
    build_example_report()
    ensure_allure_report()
    build_index()

    print(f"\n[完成] 站点已生成于 {PUBLIC}/")
    print("  预览：python -m http.server -d public 8000  → http://localhost:8000/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
