#!/usr/bin/env python3
"""Phase 2 功能测试：SkillHub 联网搜索 + 安装确认"""
import sys
sys.path.insert(0, 'scripts')

from skill_recommender import recommend_skills, format_recommendations_md, format_recommendations_html
from skillhub_client import search_skills, get_skill_detail, format_install_warning

print("=" * 70)
print("Phase 2 功能测试")
print("=" * 70)

# 测试 1：SkillHub 搜索
print("\n[测试 1] SkillHub 搜索省 Token Skill")
print("-" * 70)
resp = search_skills("省token", limit=5)
print(f"找到 {resp.total} 个结果")
for s in resp.skills[:3]:
    print(f"  - {s.name} ({s.slug}) | ⭐{s.stars} | {s.description_zh[:50] if s.description_zh else 'N/A'}...")

# 测试 2：获取 Skill 详情
print("\n[测试 2] 获取 Skill 详情")
print("-" * 70)
if resp.skills:
    detail = get_skill_detail(resp.skills[0].slug)
    if detail:
        print(f"  {detail.name}")
        print(f"  Stars: {detail.stars}, Installs: {detail.installs}")
        print(f"  描述: {detail.description_zh}")

# 测试 3：推荐引擎联网模式
print("\n[测试 3] 推荐引擎（联网模式）")
print("-" * 70)
by_type = [
    {"task_type": "代码开发", "baseline_tokens": 50000, "skill_tokens": 30000, "count": 5},
    {"task_type": "对话问答", "baseline_tokens": 30000, "skill_tokens": 20000, "count": 3},
]
recs = recommend_skills(by_type, total_tasks=10, use_online_search=True)
print(f"推荐 {len(recs)} 个 Skill")
for r in recs:
    print(f"\n  🎯 {r.skill}")
    print(f"     原因: {r.reason[:60]}...")
    print(f"     SkillHub: {'有' if r.skillhub_info else '无'}")
    if r.skillhub_info:
        info = r.skillhub_info
        print(f"     ⭐{info.get('stars', 0)} | {info.get('installs', 0)} 安装")
        if info.get('tags'):
            print(f"     标签: {', '.join(info['tags'][:3])}")
    print(f"     安装命令: {r.install_cmd}")
    print(f"     需确认: {r.requires_confirmation}")

# 测试 4：Markdown 格式（含安装确认提示）
print("\n[测试 4] Markdown 格式输出")
print("-" * 70)
if recs:
    print(format_recommendations_md(recs[:1]))

# 测试 5：HTML 格式
print("\n[测试 5] HTML 格式输出（前 200 字符）")
print("-" * 70)
if recs:
    html = format_recommendations_html(recs[:1])
    print(html[:500] + "...")

# 测试 6：安装确认提示
print("\n[测试 6] 安装确认提示格式")
print("-" * 70)
if recs:
    print(format_install_warning(type('obj', (object,), {
        'slug': recs[0].skillhub_slug or recs[0].skill,
        'name': recs[0].skill,
        'description_zh': '测试描述',
        'stars': 100,
        'installs': 50,
        'homepage': 'https://github.com/test/test',
        'tags': ['token', 'saving'],
        'author': 'test'
    })(), recs[0].install_cmd))

print("\n" + "=" * 70)
print("所有测试完成")
print("=" * 70)
