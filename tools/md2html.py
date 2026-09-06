#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/md2html.py — 零依赖的 Markdown(GFM 子集) → HTML 片段转换器

用途：构建 GitHub Pages 作品集站点时，把仓库里的 README.md / SKILL.md /
usage-examples.md 渲染成干净的自包含 HTML 片段（不含 <html>/<head> 外壳，
由 build_pages.py 负责包成完整页面）。

纯标准库（re / html），不引入任何第三方依赖，与项目「零依赖」身份一致。

支持的语法（GFM 常用子集）：
- 标题 # ## ### ####
- 无序列表（- * +，支持一级缩进嵌套）
- 有序列表（1. 2. ...）
- 代码围栏 ```lang ... ```
- 行内代码 `code`
- 粗体 **x** / 斜体 *x* 或 _x_
- 链接 [text](url) 与图片 ![alt](url)
- 表格（| a | b | ＋ 分隔行 |---|---|）
- 引用块 >
- 分隔线 ---
- 段落（空行分隔）

用法：
    python tools/md2html.py --input README.md --output readme.body.html
    或作为模块：from md2html import convert; html = convert(md_text)
"""

import argparse
import html
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 行内格式化
# ---------------------------------------------------------------------------

_CODE_PLACEHOLDER = "\x00CODE{}\x00"  # 占位符，避免行内代码内容被二次处理


def _inline(text):
    """对一段已经过 html.escape 的文本做行内格式化。"""
    # 1) 先抽取行内代码，用占位符保护
    code_spans = []

    def _stash_code(m):
        code_spans.append(m.group(1))
        return _CODE_PLACEHOLDER.format(len(code_spans) - 1)

    text = re.sub(r"`([^`]+)`", _stash_code, text)

    # 2) 图片 ![alt](url)
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda m: f'<img class="md-img" alt="{m.group(1)}" src="{m.group(2)}">',
        text,
    )
    # 3) 链接 [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a class="md-link" href="{m.group(2)}" target="_blank" '
        f'rel="noopener">{m.group(1)}</a>',
        text,
    )
    # 4) 粗体 **x**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # 5) 斜体 *x* 或 _x_（_ 仅作用于非单词边界，避免误伤 snake_case 与 _blank 等）
    text = re.sub(r"(?<![\*\w])\*([^*\n]+?)\*(?![\*\w])", r"<em>\1</em>", text)
    text = re.sub(r"(?<![\w])_([^_\s][^_]*?)_(?![\w])", r"<em>\1</em>", text)

    # 6) 还原行内代码
    def _restore_code(m):
        idx = int(m.group(1))
        return f"<code class='md-code'>{html.escape(code_spans[idx])}</code>"

    text = re.sub(_CODE_PLACEHOLDER.replace("{}", r"(\d+)"), _restore_code, text)
    return text


# ---------------------------------------------------------------------------
# 块级解析
# ---------------------------------------------------------------------------


def _is_table_sep(line):
    s = line.strip()
    if not s.startswith("|") and not s.endswith("|") and "|" not in s:
        return False
    # 允许 | --- | --- | 或 ---|--- 形式
    inner = s.strip("|")
    return bool(re.fullmatch(r"[\s:|-]+", inner)) and "-" in inner


def _split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _render_table(rows):
    header = rows[0]
    body = rows[1:]
    out = ['<div class="md-table-wrap"><table class="md-table">']
    out.append("<thead><tr>")
    for c in header:
        out.append(f"<th>{_inline(html.escape(c))}</th>")
    out.append("</tr></thead><tbody>")
    for r in body:
        out.append("<tr>")
        for c in r:
            out.append(f"<td>{_inline(html.escape(c))}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def convert(md, *, strip_frontmatter=False):
    """把 Markdown 文本转换为 HTML 片段字符串。"""
    if strip_frontmatter:
        # 去掉开头的 --- ... --- YAML frontmatter（SKILL.md 用）
        if md.startswith("---"):
            end = md.find("\n---", 3)
            if end != -1:
                md = md[end + 4:]

    lines = md.split("\n")
    out = []
    i = 0
    n = len(lines)

    # 列表状态
    list_stack = []  # 每项: (indent, kind)  kind ∈ {'ul','ol'}

    def _close_lists(upto_indent=None):
        nonlocal list_stack
        while list_stack:
            ind, kind = list_stack[-1]
            if upto_indent is not None and ind < upto_indent:
                break
            out.append("</li>")  # 闭合最后一个未闭合的列表项
            out.append("</ul>" if kind == "ul" else "</ol>")
            list_stack.pop()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 代码围栏
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # 跳过结束的 ```
            cls = "md-pre"
            if lang:
                cls += f" lang-{html.escape(lang)}"
            code = "\n".join(buf)
            out.append(
                f'<pre class="{cls}"><code>{html.escape(code)}</code></pre>'
            )
            _close_lists()
            continue

        # 空行
        if stripped == "":
            _close_lists()
            i += 1
            continue

        # 分隔线
        if re.fullmatch(r"[-*_]{3,}", stripped):
            _close_lists()
            out.append('<hr class="md-hr">')
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            _close_lists()
            level = len(m.group(1))
            content = _inline(html.escape(m.group(2).strip()))
            out.append(f'<h{level} class="md-h md-h{level}">{content}</h{level}>')
            i += 1
            continue

        # 引用块
        if stripped.startswith(">"):
            _close_lists()
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(f'<blockquote class="md-quote">'
                       f'{_inline(html.escape(" ".join(buf)))}</blockquote>')
            continue

        # 表格（当前行含 | 且下一行是分隔行）
        if "|" in stripped and i + 1 < n and _is_table_sep(lines[i + 1]):
            _close_lists()
            rows = [_split_row(lines[i])]
            i += 2  # 跳过表头与分隔行
            while i < n and "|" in lines[i].strip() and lines[i].strip():
                rows.append(_split_row(lines[i]))
                i += 1
            out.append(_render_table(rows))
            continue

        # 列表项（- * + 或 1.）
        list_match = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", line)
        if list_match:
            indent = len(list_match.group(1).replace("\t", "  "))
            marker = list_match.group(2)
            kind = "ol" if re.match(r"\d+\.", marker) else "ul"
            content = _inline(html.escape(list_match.group(3)))

            # 与上一项比较缩进
            if list_stack and indent > list_stack[-1][0]:
                # 嵌套：开子列表
                out.append(f'<{"ul" if kind=="ul" else "ol"} class="md-list md-nested">')
                list_stack.append((indent, kind))
                out.append(f"<li>{content}")
            elif list_stack and indent < list_stack[-1][0]:
                # 退层
                while list_stack and list_stack[-1][0] > indent:
                    out.append("</li>")
                    out.append("</ul>" if list_stack[-1][1] == "ul" else "</ol>")
                    list_stack.pop()
                if list_stack:
                    out.append("</li>")
                    out.append(f"<li>{content}")
                else:
                    out.append(f'<{"ul" if kind=="ul" else "ol"} class="md-list">'
                               f"<li>{content}")
                    list_stack.append((indent, kind))
            else:
                # 同级：先闭合上一个 <li>（如果有）
                if list_stack:
                    out.append("</li>")
                else:
                    out.append(f'<{"ul" if kind=="ul" else "ol"} class="md-list">')
                    list_stack.append((indent, kind))
                out.append(f"<li>{content}")
            i += 1
            continue

        # 段落（聚合连续非空、非块级行）
        _close_lists()
        buf = [stripped]
        i += 1
        while i < n and lines[i].strip() != "" \
                and not lines[i].strip().startswith("```") \
                and not re.match(r"^#{1,6}\s", lines[i]) \
                and not lines[i].strip().startswith(">") \
                and not re.match(r"^(\s*)([-*+]|\d+\.)\s+", lines[i]) \
                and not (("|" in lines[i].strip())
                         and i + 1 < n and _is_table_sep(lines[i + 1])):
            buf.append(lines[i].strip())
            i += 1
        para = " ".join(buf)
        out.append(f'<p class="md-p">{_inline(html.escape(para))}</p>')

    _close_lists()
    return "\n".join(x for x in out if x != "")


def main():
    ap = argparse.ArgumentParser(description="Markdown(GFM 子集) → HTML 片段")
    ap.add_argument("--input", "-i", required=True, help="输入 Markdown 文件")
    ap.add_argument("--output", "-o", help="输出 HTML 片段文件（不写则打印到 stdout）")
    ap.add_argument("--strip-frontmatter", action="store_true",
                    help="去掉开头的 --- YAML frontmatter（用于 SKILL.md）")
    args = ap.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    body = convert(text, strip_frontmatter=args.strip_frontmatter)
    if args.output:
        Path(args.output).write_text(body, encoding="utf-8")
        print(f"[OK] {args.input} -> {args.output} ({len(body)} chars)")
    else:
        sys.stdout.write(body)
    return 0


# 延迟导入，仅 CLI 用到
from pathlib import Path  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
