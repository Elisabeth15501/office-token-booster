#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/render_allure_html.py — 零依赖的 Allure 结果 → 自包含 HTML 报告渲染器

无需 Java / 无需 allure CLI：直接读取 pytest+allure-pytest 产出的 allure-results/ 目录，
生成单个自包含 allure-report.html，可本地双击打开，也可直接部署到 GitHub Pages / Netlify
作为作品集展示。

用法：
    python tools/render_allure_html.py --results allure-results --output allure-report.html
若不传参数，默认读取 ./allure-results 并输出 ./allure-report.html。

说明：
- 纯标准库（json / pathlib / base64 / html），不引入任何第三方依赖。
- 内联 CSS + 少量原生 JS（折叠 / 状态筛选），无外部 CDN，离线可用。
- 支持渲染：测试状态、feature/story/severity 标签、描述、嵌套 steps、
  TEXT/HTML/JSON/图片 四种附件（图片以 base64 内联）。
"""

import argparse
import base64
import html
import json
import mimetypes
import os
import sys
from pathlib import Path


STATUS_LABELS = {
    "passed": "通过", "failed": "失败", "broken": "错误",
    "skipped": "跳过", "unknown": "未知",
}

# 失败分类默认值：当 allure-results 下没有 categories.json 时注入，
# 让作品集报告即使本地运行也呈现专业的结构化失败桶。
DEFAULT_CATEGORIES = [
    {"name": "产品缺陷 (Product Bug)", "matchedStatuses": ["failed"],
     "description": "断言失败 / 逻辑错误 / 需求未满足"},
    {"name": "测试/环境问题 (Test/Env)", "matchedStatuses": ["broken"],
     "description": "未捕获异常 / 环境或依赖导致的中断"},
    {"name": "跳过 (Skipped)", "matchedStatuses": ["skipped"],
     "description": "条件跳过或尚未实现"},
]


def detect_environment():
    """尽力探测运行环境元数据，供报告「运行环境」表展示（作品集加分项）。

    仅在 allure-results 下没有 environment.properties 时作为兜底使用；
    全部探测都包在 try 里，单一探测失败不影响整体。
    """
    env = {"project": "office-token-booster",
           "report.renderer": "render_allure_html.py (zero-dependency)"}
    try:
        env["python.version"] = sys.version.split()[0]
    except Exception:
        pass
    try:
        import importlib.metadata as md
        for pkg, key in (("pytest", "pytest.version"),
                         ("allure-pytest", "allure-pytest.version")):
            try:
                env[key] = md.version(pkg)
            except Exception:
                pass
    except Exception:
        pass
    # git commit（若处于仓库内）
    try:
        import subprocess
        repo_root = Path(__file__).resolve().parent.parent
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, cwd=repo_root, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            env["git.commit"] = out.stdout.strip()
    except Exception:
        pass
    return env

STATUS_COLOR = {
    "passed": "#16a34a", "failed": "#dc2626", "broken": "#d97706",
    "skipped": "#6b7280", "unknown": "#6b7280",
}
SEVERITY_COLOR = {
    "blocker": "#7f1d1d", "critical": "#dc2626", "normal": "#2563eb",
    "minor": "#0891b2", "trivial": "#65a30d",
}


def load_results(results_dir):
    """读取所有 *-result.json，返回测试结果列表。"""
    results = []
    for p in sorted(Path(results_dir).glob("*-result.json")):
        try:
            results.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return results


def load_attachment(results_dir, source, declared_type=None):
    """读取附件内容。返回 (kind, payload)。
    kind ∈ {text, html, json, image}; payload 分别为字符串 / 字符串 / 字符串 / data URI。
    declared_type：allure 结果里记录的 MIME（如 application/json / text/html），优先于扩展名猜测。
    """
    path = Path(results_dir) / source
    if not path.is_file():
        return "text", f"[附件缺失: {source}]"
    # 优先使用 allure 记录的 MIME，否则按扩展名猜（修复：原先完全忽略 result 里的 type 字段）
    ctype = declared_type if (declared_type and "/" in declared_type) else ""
    if not ctype:
        ext = path.suffix.lower().lstrip(".")
        if ext in ("html",):
            ctype = "text/html"
        elif ext in ("json",):
            ctype = "application/json"
        elif ext in ("png", "jpg", "jpeg", "gif", "svg", "webp"):
            ctype = f"image/{ext}" if ext != "jpg" else "image/jpeg"
        else:
            ctype = "text/plain"

    data = path.read_bytes()
    if ctype.startswith("image/"):
        b64 = base64.b64encode(data).decode("ascii")
        return "image", f"data:{ctype};base64,{b64}"
    text = data.decode("utf-8", errors="replace")
    if ctype == "text/html":
        return "html", text
    if ctype == "application/json":
        try:
            text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except Exception:
            pass
        return "json", text
    return "text", text


def render_attachments(results_dir, attachments):
    if not attachments:
        return ""
    out = ['<div class="attachments">']
    for att in attachments:
        name = att.get("name", "附件")
        source = att.get("source")
        if not source:
            continue
        kind, payload = load_attachment(results_dir, source, att.get("type"))
        out.append(f'<div class="att-block"><div class="att-title">📎 {html.escape(name)} '
                   f'<span class="att-kind">{html.escape(kind)}</span></div>')
        if kind == "image":
            out.append(f'<img class="att-img" src="{payload}" alt="{html.escape(name)}">')
        elif kind == "html":
            out.append(f'<div class="att-html">{payload}</div>')
        else:  # text / json
            out.append(f'<pre class="att-pre">{html.escape(payload)}</pre>')
        out.append('</div>')
    out.append('</div>')
    return "\n".join(out)


def render_links(links):
    """渲染 allure 记录的 links（如 @allure.link 源码链接）。"""
    if not links:
        return ""
    items = []
    for lk in links:
        url = lk.get("url") or "#"
        name = lk.get("name") or url
        ltype = lk.get("type") or ""
        tag = f'<span class="link-type">{html.escape(ltype)}</span>' if ltype else ""
        items.append(
            f'<a class="tc-link" href="{html.escape(url, quote=True)}" target="_blank" '
            f'rel="noopener">{html.escape(name)}</a>{tag}'
        )
    return '<div class="tc-links">🔗 ' + " · ".join(items) + '</div>'


def render_steps(results_dir, steps):
    if not steps:
        return ""
    out = ['<ul class="steps">']
    for s in steps:
        st = s.get("status", "unknown")
        color = STATUS_COLOR.get(st, "#6b7280")
        icon = "✔" if st == "passed" else ("✘" if st in ("failed", "broken") else "•")
        name = html.escape(s.get("name", ""))
        out.append(
            f'<li class="step"><span class="step-icon" style="color:{color}">{icon}</span>'
            f'<span class="step-name">{name}</span>'
            f'<span class="step-status" style="color:{color}">{STATUS_LABELS.get(st, st)}</span>'
        )
        # 子步骤
        child = render_steps(results_dir, s.get("steps", []))
        att = render_attachments(results_dir, s.get("attachments", []))
        if child or att:
            out.append('<div class="step-body">' + child + att + '</div>')
        out.append('</li>')
    out.append('</ul>')
    return "\n".join(out)


def fmt_duration(ms):
    if not ms:
        return "—"
    s = ms / 1000.0
    if s < 1:
        return f"{int(ms)} ms"
    if s < 60:
        return f"{s:.1f} s"
    return f"{int(s // 60)}m {s % 60:.0f}s"


def labels_of(result):
    out = {}
    for lb in result.get("labels", []):
        out.setdefault(lb.get("name"), lb.get("value"))
    return out


def render_test_card(idx, result, results_dir):
    status = result.get("status", "unknown")
    color = STATUS_COLOR.get(status, "#6b7280")
    labels = labels_of(result)
    feature = labels.get("feature", "")
    story = labels.get("story", "")
    severity = labels.get("severity", "normal")
    epic = labels.get("epic", "")
    layer = labels.get("layer", "")
    sev_color = SEVERITY_COLOR.get(severity, "#2563eb")

    badges = []
    if epic:
        badges.append(f'<span class="badge epic">{html.escape(epic)}</span>')
    if layer:
        badges.append(f'<span class="badge layer">{html.escape(layer)}</span>')
    if feature:
        badges.append(f'<span class="badge feat">{html.escape(feature)}</span>')
    if story:
        badges.append(f'<span class="badge story">{html.escape(story)}</span>')
    badges.append(f'<span class="badge sev" style="background:{sev_color}">{html.escape(severity)}</span>')

    links_html = render_links(result.get("links", []))

    # 自定义维度标签：test_type / component / risk_area / priority / suite
    # （这些维度在 docs/allure-labels.md 中定义，便于在作品集报告里按维度筛选/分组）
    custom_names = ("test_type", "component", "risk_area", "priority", "suite")
    custom_badges = []
    for cn in custom_names:
        cv = labels.get(cn)
        if cv:
            custom_badges.append(
                f'<span class="badge dim" data-dim="{html.escape(cn)}">'
                f'{html.escape(cn)}: {html.escape(cv)}</span>'
            )
    custom_html = f'<div class="tc-dims">{("".join(custom_badges))}</div>' if custom_badges else ""

    duration = fmt_duration(result.get("stop", 0) - result.get("start", 0))
    desc = result.get("description")
    desc_html = f'<div class="tc-desc">{html.escape(desc)}</div>' if desc else ""

    steps_html = render_steps(results_dir, result.get("steps", []))
    att_html = render_attachments(results_dir, result.get("attachments", []))

    # 失败信息
    err_html = ""
    sd = result.get("statusDetails") or {}
    if sd.get("message"):
        err_html = f'<pre class="tc-error">{html.escape(sd["message"])}</pre>'

    return f"""
    <div class="tc" data-status="{status}">
      <div class="tc-head">
        <span class="tc-status" style="background:{color}">{STATUS_LABELS.get(status, status)}</span>
        <span class="tc-name">{html.escape(result.get("name", "未命名"))}</span>
        <span class="tc-dur">{duration}</span>
      </div>
      <div class="tc-badges">{''.join(badges)}</div>
      {custom_html}
      {desc_html}
      {links_html}
      <div class="tc-body">
        {steps_html}
        {att_html}
        {err_html}
      </div>
    </div>"""


def load_environment(results_dir):
    env_path = Path(results_dir) / "environment.properties"
    env = {}
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    else:
        env = detect_environment()
    return env


def render(env, categories, tests, results_dir):
    total = len(tests)
    counts = {}
    durations = 0
    for t in tests:
        counts[t.get("status", "unknown")] = counts.get(t.get("status", "unknown"), 0) + 1
        durations += (t.get("stop", 0) - t.get("start", 0)) or 0

    pass_rate = (counts.get("passed", 0) / total * 100) if total else 0

    cards = "\n".join(
        render_test_card(i, t, results_dir) for i, t in enumerate(tests)
    )

    env_rows = "".join(
        f'<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>'
        for k, v in env.items()
    )

    cat_html = ""
    if categories:
        items = "".join(
            f'<li><b>{html.escape(c.get("name",""))}</b>：{html.escape(c.get("description",""))} '
            f'<span class="muted">[{", ".join(c.get("matchedStatuses", []))}]</span></li>'
            for c in categories
        )
        cat_html = f'<div class="cat"><h3>失败分类（categories.json）</h3><ul>{items}</ul></div>'

    # 状态计数胶囊
    pills = []
    for st in ("passed", "failed", "broken", "skipped"):
        if counts.get(st):
            pills.append(
                f'<button class="pill" data-filter="{st}" style="--c:{STATUS_COLOR[st]}">'
                f'{STATUS_LABELS[st]} {counts[st]}</button>'
            )
    pills_html = "".join(pills) + (
        '<button class="pill" data-filter="all" style="--c:#111">全部 ' + str(total) + '</button>'
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>office-token-booster · 测试报告</title>
<style>
:root{{--bg:#f7f8fa;--card:#fff;--fg:#1f2937;--muted:#6b7280;--border:#e5e7eb;--accent:#2563eb;}}
*{{box-sizing:border-box;}}
body{{font-family:-apple-system,Segoe UI,Roboto,'Microsoft YaHei',sans-serif;background:var(--bg);
  color:var(--fg);margin:0;padding:24px;line-height:1.55;}}
.wrap{{max-width:1040px;margin:0 auto;}}
h1{{font-size:22px;margin:0 0 4px;}}
.sub{{color:var(--muted);font-size:13px;margin-bottom:18px;}}
.cards{{display:flex;gap:14px;flex-wrap:wrap;margin:16px 0;}}
.stat{{flex:1;min-width:140px;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px;}}
.stat .big{{font-size:26px;font-weight:700;}}
.stat .lbl{{color:var(--muted);font-size:12px;}}
.pills{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 18px;}}
.pill{{border:2px solid var(--c);color:var(--c);background:#fff;border-radius:999px;padding:5px 14px;
  font-size:13px;font-weight:600;cursor:pointer;}}
.pill.active{{background:var(--c);color:#fff;}}
.section{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;margin:14px 0;}}
.section h3{{margin:0 0 10px;font-size:15px;}}
table{{border-collapse:collapse;width:100%;font-size:13px;}}
th,td{{border:1px solid var(--border);padding:6px 10px;text-align:left;}}
.tc{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px;margin:12px 0;}}
.tc-head{{display:flex;align-items:center;gap:10px;}}
.tc-status{{color:#fff;font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px;}}
.tc-name{{font-weight:600;flex:1;}}
.tc-dur{{color:var(--muted);font-size:12px;}}
.tc-badges{{margin:8px 0;display:flex;gap:6px;flex-wrap:wrap;}}
.badge{{font-size:11px;padding:2px 8px;border-radius:6px;background:#eef2ff;color:#3730a3;}}
.badge.story{{background:#ecfeff;color:#0e7490;}}
.badge.sev{{color:#fff;}}
.badge.epic{{background:#f3e8ff;color:#6b21a8;font-weight:700;}}
.badge.layer{{background:#ecfdf5;color:#047857;border:1px solid #a7f3d0;}}
.tc-dims{{margin:6px 0;display:flex;gap:6px;flex-wrap:wrap;}}
.badge.dim{{background:#fff;color:#374151;border:1px solid #d1d5db;border-radius:6px;font-size:11px;}}
.badge.dim[data-dim="test_type"]{{color:#7c3aed;border-color:#ddd6fe;}}
.badge.dim[data-dim="component"]{{color:#0369a1;border-color:#bae6fd;}}
.badge.dim[data-dim="risk_area"]{{color:#b45309;border-color:#fde68a;}}
.badge.dim[data-dim="priority"]{{color:#be123c;border-color:#fecdd3;}}
.badge.dim[data-dim="suite"]{{color:#047857;border-color:#a7f3d0;}}
.tc-links{{margin:6px 0;font-size:12px;}}
.tc-link{{color:var(--accent);text-decoration:none;font-weight:600;}}
.tc-link:hover{{text-decoration:underline;}}
.link-type{{color:var(--muted);font-weight:400;font-size:11px;margin-left:4px;
  background:#f1f5f9;border-radius:4px;padding:1px 6px;}}
.tc-desc{{color:var(--muted);font-size:13px;margin:4px 0;white-space:pre-wrap;}}
.steps{{list-style:none;padding-left:0;margin:8px 0;}}
.step{{padding:4px 0;border-left:3px solid var(--border);padding-left:10px;margin:4px 0;}}
.step-icon{{font-weight:700;margin-right:6px;}}
.step-name{{font-weight:500;}}
.step-status{{font-size:11px;margin-left:6px;}}
.step-body{{padding-left:14px;}}
.attachments{{margin:8px 0;}}
.att-block{{border:1px dashed var(--border);border-radius:8px;padding:8px;margin:6px 0;}}
.att-title{{font-size:12px;font-weight:600;margin-bottom:4px;}}
.att-kind{{color:var(--muted);font-weight:400;font-size:11px;margin-left:6px;}}
.att-pre{{background:#0f172a;color:#e2e8f0;padding:10px;border-radius:8px;overflow:auto;font-size:12px;max-height:320px;}}
.att-html{{overflow:auto;max-height:420px;border:1px solid var(--border);border-radius:8px;}}
.att-img{{max-width:100%;border:1px solid var(--border);border-radius:8px;}}
.tc-error{{background:#fef2f2;color:#991b1b;padding:10px;border-radius:8px;overflow:auto;font-size:12px;}}
.muted{{color:var(--muted);}}
.cat ul{{margin:6px 0;padding-left:18px;font-size:13px;}}
.hidden{{display:none;}}
</style></head>
<body><div class="wrap">
<h1>🧪 office-token-booster · 测试报告</h1>
<div class="sub">pytest + Allure（自包含静态报告，无需 Java）｜ 共 {total} 个用例</div>

<div class="cards">
  <div class="stat"><div class="big">{total}</div><div class="lbl">用例总数</div></div>
  <div class="stat"><div class="big" style="color:{STATUS_COLOR['passed']}">{counts.get('passed',0)}</div><div class="lbl">通过</div></div>
  <div class="stat"><div class="big" style="color:{STATUS_COLOR['failed']}">{counts.get('failed',0)}</div><div class="lbl">失败</div></div>
  <div class="stat"><div class="big" style="color:{STATUS_COLOR['broken']}">{counts.get('broken',0)}</div><div class="lbl">错误</div></div>
  <div class="stat"><div class="big" style="color:{STATUS_COLOR['skipped']}">{counts.get('skipped',0)}</div><div class="lbl">跳过</div></div>
  <div class="stat"><div class="big">{pass_rate:.1f}%</div><div class="lbl">通过率</div></div>
  <div class="stat"><div class="big">{fmt_duration(durations)}</div><div class="lbl">总耗时</div></div>
</div>

<div class="pills">{pills_html}</div>

<div class="section">
  <h3>运行环境（environment.properties）</h3>
  <table><tbody>{env_rows}</tbody></table>
</div>

{cat_html}

<h2 style="font-size:16px;margin-top:8px;">测试用例（{total}）</h2>
{cards}

</div>
<script>
document.querySelectorAll('.pill').forEach(function(b){{
  b.addEventListener('click', function(){{
    var f = b.getAttribute('data-filter');
    document.querySelectorAll('.pill').forEach(function(x){{x.classList.remove('active');}});
    b.classList.add('active');
    document.querySelectorAll('.tc').forEach(function(c){{
      c.classList.toggle('hidden', !(f==='all' || c.getAttribute('data-status')===f));
    }});
  }});
}});
document.querySelector('.pill[data-filter="all"]').classList.add('active');
</script>
</body></html>"""
    return html_doc


def main():
    ap = argparse.ArgumentParser(description="Allure 结果 -> 自包含 HTML 报告（零依赖）")
    ap.add_argument("--results", default="allure-results", help="allure-results 目录")
    ap.add_argument("--output", default="allure-report.html", help="输出 HTML 路径")
    args = ap.parse_args()

    results_dir = Path(args.results)
    if not results_dir.is_dir():
        print(f"[错误] 目录不存在：{results_dir}", file=sys.stderr)
        return 2

    tests = load_results(results_dir)
    if not tests:
        print(f"[警告] {results_dir} 下没有 *-result.json，未生成报告。", file=sys.stderr)
        return 1

    env = load_environment(results_dir)
    categories = []
    cat_path = results_dir / "categories.json"
    if cat_path.is_file():
        try:
            categories = json.loads(cat_path.read_text(encoding="utf-8"))
        except Exception:
            categories = []
    # 没有 categories.json 时注入默认分类，让报告更完整
    if not categories:
        categories = DEFAULT_CATEGORIES

    doc = render(env, categories, tests, results_dir)
    # 先写临时文件再原子替换，避免「覆盖已存在文件」在某些沙箱/只读场景下被拒绝
    out_path = Path(args.output)
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    tmp_path.write_text(doc, encoding="utf-8")
    os.replace(tmp_path, out_path)
    print(f"[OK] 已生成 {args.output}（{len(tests)} 个用例，"
          f"通过 {sum(1 for t in tests if t.get('status')=='passed')}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
