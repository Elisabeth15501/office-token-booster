#!/usr/bin/env python3
"""ClawHub 集成测试"""
import sys
sys.path.insert(0, 'scripts')

from clawhub_client import search_clawhub, get_clawhub_skill, format_clawhub_install_warning
from skill_recommender import recommend_skills, format_recommendations_md

print("=" * 70)
print("ClawHub 集成测试")
print("=" * 70)

# 测试 1：搜索 ClawHub
print("\n[测试 1] 搜索 ClawHub 省 Token Skill")
print("-" * 70)
resp = search_clawhub("省token", limit=5)
print(f"找到 {resp.total} 个结果")
for s in resp.skills[:3]:
    print(f"  - {s.name} ({s.slug}) | ⭐{s.stars} | {s.installs} 安装")

# 测试 2：获取详情
print("\n[测试 2] 获取 Skill 详情")
print("-" * 70)
if resp.skills:
    detail = get_clawhub_skill(resp.skills[0].slug)
    if detail:
        print(f"  {detail.name}")
        print(f"  Stars: {detail.stars}, Installs: {detail.installs}")
        print(f"  描述: {detail.summary}")

# 测试 3：推荐引擎联网模式（SkillHub + ClawHub）
print("\n[测试 3] 推荐引擎（双平台联网）")
print("-" * 70)
by_type = [
    {"task_type": "代码开发", "baseline_tokens": 50000, "skill_tokens": 30000, "count": 5},
    {"task_type": "对话问答", "baseline_tokens": 30000, "skill_tokens": 20000, "count": 3},
]
recs = recommend_skills(by_type, total_tasks=10, use_online_search=True)
print(f"推荐 {len(recs)} 个 Skill")
for r in recs:
    print(f"\n  🎯 {r.skill}")
    print(f"     SkillHub: {'有' if r.skillhub_info else '无'}")
    print(f"     ClawHub: {'有' if r.clawhub_info else '无'}")
    if r.clawhub_info:
        info = r.clawhub_info
        print(f"     ⭐{info.get('stars', 0)} | {info.get('installs', 0)} 安装")
        if info.get('summary'):
            print(f"     描述: {info['summary'][:60]}...")

# 测试 4：Markdown 格式
print("\n[测试 4] Markdown 格式输出")
print("-" * 70)
if recs:
    print(format_recommendations_md(recs[:1]))

print("\n" + "=" * 70)
print("所有测试完成")
print("=" * 70)
