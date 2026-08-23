#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clawhub_client.py — ClawHub API 客户端

用于搜索 ClawHub 平台上的省 Token Skill。

API 端点：
- Search: https://clawhub.ai/api/v1/search?q={query}&limit={n}
- Detail: https://clawhub.ai/api/v1/skills/{slug}

设计原则：
- 纯函数，无副作用
- 错误处理完善，网络异常不崩溃
- 与 SkillHub 客户端分离，各自独立维护
"""

from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ClawHubSkill:
    """ClawHub Skill 信息。"""

    slug: str                           # 技能 slug（用于安装命令）
    name: str                           # 技能名称
    summary: Optional[str] = None       # 技能描述
    owner: Optional[str] = None         # 作者
    stars: int = 0                      # Stars 数
    installs: int = 0                   # 安装数
    tags: list[str] = field(default_factory=list)  # 标签
    homepage: Optional[str] = None      # 仓库链接
    install_ref: Optional[str] = None   # 安装引用（如 @owner/skill）


@dataclass
class ClawHubSearchResponse:
    """ClawHub 搜索结果。"""

    skills: list[ClawHubSkill] = field(default_factory=list)
    total: int = 0
    query: str = ""


class ClawHubClient:
    """ClawHub HTTP 客户端。"""

    BASE_URL = "https://clawhub.ai/api/v1"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def search(self, query: str, limit: int = 10) -> ClawHubSearchResponse:
        """搜索 ClawHub 技能。

        Args:
            query: 搜索关键词
            limit: 最大返回结果数

        Returns:
            ClawHubSearchResponse
        """
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"{self.BASE_URL}/search?q={encoded_query}&limit={limit}"

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "office-token-booster/0.9.2",
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            return self._parse_search_response(data, query)

        except urllib.error.HTTPError as e:
            print(f"[ClawHub] HTTP {e.code}: {e.reason}", file=sys.stderr)
            return ClawHubSearchResponse(query=query)
        except urllib.error.URLError as e:
            print(f"[ClawHub] Network error: {e.reason}", file=sys.stderr)
            return ClawHubSearchResponse(query=query)
        except Exception as e:
            print(f"[ClawHub] Unexpected error: {e}", file=sys.stderr)
            return ClawHubSearchResponse(query=query)

    def get_skill(self, slug: str) -> Optional[ClawHubSkill]:
        """获取单个 Skill 详情。

        Args:
            slug: Skill slug

        Returns:
            ClawHubSkill or None
        """
        try:
            url = f"{self.BASE_URL}/skills/{slug}"

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "office-token-booster/0.9.2",
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            # 检查是否是错误响应
            if "code" in data:
                print(f"[ClawHub] Error: {data.get('message', 'Unknown error')}", file=sys.stderr)
                return None

            return self._parse_skill_detail(data, slug)

        except urllib.error.HTTPError as e:
            print(f"[ClawHub] HTTP {e.code} for {slug}: {e.reason}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"[ClawHub] Error fetching {slug}: {e}", file=sys.stderr)
            return None

    def _parse_search_response(self, data: dict, query: str) -> ClawHubSearchResponse:
        """解析搜索结果。"""
        results = data.get("results", [])
        skills = []

        for r in results:
            slug = r.get("slug", "")
            if not slug:
                continue

            # 解析作者和安装引用
            owner = None
            install_ref = None

            # sourceIdentity 可能为 null
            source_identity = r.get("sourceIdentity") or {}
            if source_identity:
                owner = source_identity.get("owner")
                repo = source_identity.get("repo")
                if owner and repo:
                    install_ref = f"{owner}/{repo}"
                elif owner:
                    install_ref = owner

            # 如果没有 sourceIdentity，从其他字段尝试获取
            if not owner:
                owner = r.get("ownerHandle")

            if not install_ref and owner:
                install_ref = f"{owner}/{slug}"

            # 解析 stats
            native = r.get("native") or {}
            skill_data = native.get("skill") or {}
            stats = skill_data.get("stats") or {}

            # 安全获取 summary
            summary = r.get("summary") or skill_data.get("summary")

            skill = ClawHubSkill(
                slug=slug,
                name=r.get("displayName", slug),
                summary=summary,
                owner=owner,
                stars=stats.get("stars", 0),
                installs=stats.get("installs", stats.get("downloads", 0)),
                tags=list((skill_data.get("tags") or {}).keys()),
                homepage=r.get("links", {}).get("source") or r.get("canonicalUrl"),
                install_ref=install_ref,
            )
            skills.append(skill)

        return ClawHubSearchResponse(
            skills=skills,
            total=len(skills),
            query=query,
        )

    def _parse_skill_detail(self, data: dict, slug: str) -> Optional[ClawHubSkill]:
        """解析 Skill 详情。"""
        # 从 different structures 中提取信息
        skill_data = data.get("skill", data)
        stats = skill_data.get("stats", {})

        return ClawHubSkill(
            slug=slug,
            name=skill_data.get("displayName", slug),
            summary=skill_data.get("summary"),
            owner=data.get("ownerHandle") or skill_data.get("ownerPublisherId"),
            stars=stats.get("stars", 0),
            installs=stats.get("installs", stats.get("downloads", 0)),
            tags=list(skill_data.get("tags", {}).keys()),
            homepage=data.get("links", {}).get("source"),
            install_ref=data.get("install", {}).get("reference"),
        )


# 全局客户端实例
_client = None


def get_client() -> ClawHubClient:
    """获取全局客户端实例。"""
    global _client
    if _client is None:
        _client = ClawHubClient()
    return _client


def search_clawhub(query: str, limit: int = 10) -> ClawHubSearchResponse:
    """便捷函数：搜索 ClawHub 技能。

    Args:
        query: 搜索关键词
        limit: 最大返回结果数

    Returns:
        ClawHubSearchResponse
    """
    client = get_client()
    return client.search(query, limit)


def get_clawhub_skill(slug: str) -> Optional[ClawHubSkill]:
    """便捷函数：获取单个 Skill 详情。

    Args:
        slug: Skill slug

    Returns:
        ClawHubSkill or None
    """
    client = get_client()
    return client.get_skill(slug)


def format_clawhub_install_warning(skill: ClawHubSkill) -> str:
    """格式化安装确认提示（Markdown）。"""
    lines = [
        f"⚠️ **ClawHub 安装确认**",
        "",
        f"即将安装的 Skill：**{skill.name}** (`{skill.slug}`)",
        "",
    ]

    if skill.summary:
        lines.append(f"- **描述**：{skill.summary[:100]}...")

    if skill.owner:
        lines.append(f"- **作者**：{skill.owner}")

    lines += [
        f"- **Stars**：{skill.stars} ⭐ | **安装数**：{skill.installs}",
    ]

    if skill.tags:
        lines.append(f"- **标签**：{', '.join(skill.tags[:5])}")

    if skill.homepage:
        lines.append(f"- **仓库**：{skill.homepage}")

    # 安装命令
    install_cmd = f"clawhub add {skill.install_ref or skill.slug}" if skill.install_ref else f"clawhub add {skill.slug}"
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
        f"> 💡 你也可以手动访问 ClawHub 查看详情：",
        f"> https://clawhub.ai/{skill.slug}",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    # 测试
    print("=" * 70)
    print("ClawHub 客户端测试")
    print("=" * 70)

    # 搜索
    print("\n1. 搜索省 Token Skill...")
    resp = search_clawhub("省token", limit=5)
    print(f"   找到 {resp.total} 个结果")
    for s in resp.skills[:3]:
        print(f"   - {s.name} ({s.slug}) | ⭐{s.stars} | {s.installs} 安装")
        if s.summary:
            print(f"     {s.summary[:60]}...")

    # 详情
    if resp.skills:
        print("\n2. 获取详情：", resp.skills[0].slug)
        detail = get_clawhub_skill(resp.skills[0].slug)
        if detail:
            print(f"   {detail.name} | ⭐{detail.stars} | {detail.installs} 安装")
            print(f"   描述：{detail.summary}")

    # 安装提示
    print("\n3. 安装确认提示示例：")
    if resp.skills:
        print(format_clawhub_install_warning(resp.skills[0]))

    print("\n" + "=" * 70)
    print("测试完成")
