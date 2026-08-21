#!/usr/bin/env python3
"""快速测试 Skill 推荐引擎"""
import sys
sys.path.insert(0, 'scripts')

from skill_recommender import recommend_skills, format_recommendations_md, format_recommendations_html

# 测试数据：模拟用户用量
by_type = [
    {"task_type": "代码开发", "baseline_tokens": 50000, "skill_tokens": 30000, "count": 5},
    {"task_type": "对话问答", "baseline_tokens": 30000, "skill_tokens": 20000, "count": 3},
]

print("=" * 60)
print("测试 1：基础推荐（离线模式）")
print("=" * 60)
recs = recommend_skills(by_type, total_tasks=8, use_online_search=False)
print(f"找到 {len(recs)} 条推荐：")
for r in recs:
    print(f"  🎯 {r.skill} ({r.priority})")
    print(f"     原因：{r.reason[:60]}...")
    print(f"     安装：{r.install_cmd}")
    print()

print("=" * 60)
print("测试 2：联网搜索推荐（Phase 2）")
print("=" * 60)
recs_online = recommend_skills(by_type, total_tasks=8, use_online_search=True)
print(f"找到 {len(recs_online)} 条推荐：")
for r in recs_online:
    print(f"  🎯 {r.skill}")
    if r.skillhub_info:
        info = r.skillhub_info
        print(f"     SkillHub: ⭐{info.get('stars', 0)} | {info.get('installs', 0)} 安装")
        if info.get('description'):
            print(f"     描述：{info['description'][:60]}...")
    print()

print("=" * 60)
print("测试 3：Markdown 格式输出")
print("=" * 60)
print(format_recommendations_md(recs[:1]))

print("=" * 60)
print("测试完成")
