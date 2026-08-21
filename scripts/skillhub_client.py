#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skillhub_client.py — office-token-booster v0.9.2 SkillHub 客户端

提供 SkillHub 联网搜索能力，支持：
- 关键词搜索 Skill
- 获取 Skill 详情
- 安全提示：安装是危险动作，需用户确认

API 端点：
- 搜索：https://lightmake.site/api/v1/search?q={query}&limit={n}
- 详情：https://lightmake.site/api/v1/skills/{slug}
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SkillInfo:
    """SkillHub 中的 Skill 信息。"""
    slug: str
    name: str
    description_zh: Optional[str] = None
    stars: int = 0
    installs: int = 0
    downloads: int = 0
    homepage: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    author: Optional[str] = None


@dataclass
class SearchResponse:
    """搜索响应。"""
    skills: list[SkillInfo] = field(default_factory=list)
    query: str = ""
    total: int = 0
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# HTTP 工具函数
# ─────────────────────────────────────────────────────────────

_SKILLHUB_BASE_URL = "https://lightmake.site/api/v1"
_USER_AGENT = "office-token-booster/0.9.2 (Python)"


def _http_get(url: str, timeout: int = 10) -> Optional[dict]:
    """发送 GET 请求，返回 JSON 数据；失败返回 None。"""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        pass
    return None


def _fetch_search_results(query: str, limit: int = 10) -> list[dict]:
    """从 SkillHub 搜索接口获取结果。"""
    url = f"{_SKILLHUB_BASE_URL}/search?q={urllib.parse.quote(query)}&limit={limit}"
    data = _http_get(url)
    if data and "results" in data:
        return data["results"]
    return []


def _fetch_skill_detail(slug: str) -> Optional[dict]:
    """从 SkillHub 获取单个 Skill 详情。"""
    url = f"{_SKILLHUB_BASE_URL}/skills/{slug}"
    data = _http_get(url)
    return data if data else None


# ─────────────────────────────────────────────────────────────
# SkillInfo 解析
# ─────────────────────────────────────────────────────────────

def _parse_skill_info(item: dict) -> SkillInfo:
    """从 API 响应 item 解析 SkillInfo。"""
    slug = item.get("slug", "")
    name = item.get("name", slug)
    desc = item.get("description_zh") or item.get("description") or item.get("summary")
    stars = item.get("stars", 0)
    installs = item.get("installs", 0) or item.get("downloads", 0)
    homepage = item.get("homepage") or item.get("repository")
    category = item.get("category")
    tags = item.get("tags", [])
    author = item.get("author", item.get("owner", item.get("username")))

    return SkillInfo(
        slug=slug,
        name=name,
        description_zh=desc,
        stars=stars,
        installs=installs,
        downloads=installs,
        homepage=homepage,
        category=category,
        tags=tags,
        author=author,
    )


def _parse_search_result(item: dict) -> SkillInfo:
    """从搜索结果 item 解析 SkillInfo（字段可能较少）。"""
    slug = item.get("slug", "")
    name = item.get("name", slug)
    desc = item.get("description_zh") or item.get("description", "")

    # 尝试从 homepage 提取 repository URL
    homepage = item.get("homepage")
    repo_url = None
    if homepage and "github.com" in homepage:
        repo_url = homepage

    return SkillInfo(
        slug=slug,
        name=name,
        description_zh=desc[:200] if desc else None,
        stars=item.get("stars", 0),
        installs=item.get("installs", 0) or item.get("downloads", 0),
        homepage=repo_url,
        tags=item.get("tags", []),
    )


# ─────────────────────────────────────────────────────────────
# 公开 API
# ─────────────────────────────────────────────────────────────

def search_skills(query: str, limit: int = 10) -> SearchResponse:
    """搜索 SkillHub，返回匹配的 Skill 列表。

    Args:
        query: 搜索关键词（中文或英文）
        limit: 最多返回数量

    Returns:
        SearchResponse，包含 skills 列表或 error
    """
    import urllib.parse

    results = _fetch_search_results(query, limit)
    if not results:
        return SearchResponse(query=query, total=0)

    skills = [_parse_search_result(r) for r in results]
    return SearchResponse(skills=skills, query=query, total=len(skills))


def get_skill_detail(slug: str) -> Optional[SkillInfo]:
    """获取单个 Skill 的详细信息。

    Args:
        slug: Skill 标识符

    Returns:
        SkillInfo 或 None（如果未找到或出错）
    """
    detail = _fetch_skill_detail(slug)
    if detail:
        return _parse_skill_info(detail)
    return None


def search_token_saving_skills(limit: int = 8) -> SearchResponse:
    """搜索省 Token 相关的 Skill。

    尝试多个关键词组合，返回去重后的结果。
    """
    keywords = ["省token", "token saver", "省钱", "cost reduction", "效率"]
    all_skills: dict[str, SkillInfo] = {}

    for kw in keywords:
        resp = search_skills(kw, limit=limit)
        for skill in resp.skills:
            if skill.slug not in all_skills:
                all_skills[skill.slug] = skill

    # 按 stars 降序排序
    sorted_skills = sorted(all_skills.values(), key=lambda s: s.stars, reverse=True)[:limit]
    return SearchResponse(skills=sorted_skills, total=len(sorted_skills))


# ─────────────────────────────────────────────────────────────
# 安装确认提示
# ─────────────────────────────────────────────────────────────

def format_install_warning(skill: SkillInfo, install_cmd: str) -> str:
    """生成安装确认提示（Markdown 格式）。

    ⚠️ 安装 Skill 是危险动作，会修改你的工作空间配置。
       请在理解风险后，手动运行安装命令确认安装。
    """
    lines = [
        "⚠️ **安装确认**",
        "",
        f"即将安装的 Skill：**{skill.name}**",
        "",
        f"- **Slug**：`{skill.slug}`",
        f"- **描述**：{skill.description_zh or '暂无描述'}",
        f"- **Stars**：{skill.stars} ⭐ | **安装数**：{skill.installs}",
    ]
    if skill.author:
        lines.append(f"- **作者**：{skill.author}")
    if skill.homepage:
        lines.append(f"- **仓库**：{skill.homepage}")
    if skill.tags:
        lines.append(f"- **标签**：{', '.join(skill.tags[:5])}")

    lines += [
        "",
        "🛡️ **安全提示**：",
        "- 安装 Skill 会修改你的 `.workbuddy/` 目录",
        "- 建议先阅读 [文档](https://docs.workbuddy.cn) 了解影响",
        "- 如需回滚，可手动删除对应目录",
        "",
        f"```bash",
        f"# 请确认无误后执行以下命令安装：",
        f"{install_cmd}",
        f"```",
        "",
        "> 💡 你也可以手动访问 SkillHub 查看详情：",
        f"> https://lightmake.site/skill/{skill.slug}",
    ]
    return "\n".join(lines)


def format_install_warning_html(skill: SkillInfo, install_cmd: str) -> str:
    """生成安装确认提示（HTML 格式）。"""
    tags_html = (f"<span style='background:#e5e7eb;padding:2px 6px;border-radius:4px;font-size:11px;margin-right:4px'>{t}</span>"
                 for t in skill.tags[:5])

    html = f"""
    <div style="border:2px solid #f59e0b;border-radius:10px;padding:16px;background:#fffbeb;margin:12px 0;">
      <div style="font-size:16px;font-weight:700;color:#92400e;margin-bottom:10px;">
        ⚠️ 安装确认：{skill.name}
      </div>
      <div style="font-size:13px;color:#78350f;margin-bottom:8px;">
        {skill.description_zh or '暂无描述'}
      </div>
      <table style="font-size:12px;color:#78350f;border-collapse:collapse;width:100%;">
        <tr><td style="padding:4px 0;width:80px;"><b>Slug</b></td><td style="padding:4px 0;"><code style="background:#fef3c7;padding:2px 6px;border-radius:4px;">{skill.slug}</code></td></tr>
        <tr><td style="padding:4px 0;"><b>Stars</b></td><td style="padding:4px 0;">{skill.stars} ⭐ | 安装 {skill.installs} 次</td></tr>
        {'<tr><td style="padding:4px 0;"><b>作者</b></td><td style="padding:4px 0;">' + skill.author + '</td></tr>' if skill.author else ''}
        {'<tr><td style="padding:4px 0;"><b>仓库</b></td><td style="padding:4px 0;"><a href="' + skill.homepage + '" target="_blank" style="color:#2563eb;">' + skill.homepage + '</a></td></tr>' if skill.homepage else ''}
        <tr><td style="padding:4px 0;"><b>标签</b></td><td style="padding:4px 0;">' + "".join(tags_html) + '</td></tr>
      </table>
      <div style="margin-top:12px;padding:10px;background:#fee2e2;border-radius:6px;font-size:12px;color:#991b1b;">
        <b>⚠️ 安全提示：</b>安装 Skill 会修改你的 <code>.workbuddy/</code> 目录。建议先阅读文档了解影响。如需回滚，可手动删除对应目录。
      </div>
      <div style="margin-top:10px;">
        <div style="font-size:12px;color:#78350f;margin-bottom:4px;">请确认无误后执行以下命令安装：</div>
        <pre style="background:#f3f4f6;padding:10px;border-radius:6px;overflow-x:auto;font-size:12px;"><code style="color:#111827;">{install_cmd}</code></pre>
      </div>
      <div style="margin-top:8px;font-size:11px;color:#92400e;">
        💡 详情：
        <a href="https://lightmake.site/skill/{skill.slug}" target="_blank" style="color:#2563eb;">
          https://lightmake.site/skill/{skill.slug}
        </a>
      </div>
    </div>
    """
    return html


# ─────────────────────────────────────────────────────────────
# 测试入口
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("SkillHub 客户端测试")
    print("=" * 60)

    # 测试搜索
    print("\n1. 搜索省 Token Skill...")
    resp = search_token_saving_skills(limit=5)
    print(f"   找到 {resp.total} 个结果")
    for s in resp.skills:
        print(f"   - {s.name} ({s.slug}) | ⭐{s.stars} | {s.description_zh[:50] if s.description_zh else 'N/A'}...")

    # 测试单个详情
    if resp.skills:
        print(f"\n2. 获取详情：{resp.skills[0].slug}")
        detail = get_skill_detail(resp.skills[0].slug)
        if detail:
            print(f"   {detail.name} | ⭐{detail.stars} | {detail.installs} 安装")
            print(f"   描述：{detail.description_zh}")
        else:
            print("   （无详情）")

    # 测试安装提示
    print("\n3. 安装确认提示示例：")
    if resp.skills:
        print(format_install_warning(resp.skills[0], "npx skills add " + resp.skills[0].slug))
