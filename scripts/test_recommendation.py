#!/usr/bin/env python3
"""快速测试 Skill 推荐引擎（v1.0.2 起：纯本地静态规则，联网分支已移除）"""
import sys
sys.path.insert(0, 'scripts')

from skill_recommender import recommend_skills, format_recommendations_md, format_recommendations_html

# 测试数据：模拟用户用量
by_type = [
    {"task_type": "代码开发", "baseline_tokens": 50000, "skill_tokens": 30000, "count": 5},
    {"task_type": "对话问答", "baseline_tokens": 30000, "skill_tokens": 20000, "count": 3},
]

print("=" * 60)
print("测试 1：本地推荐（唯一模式，无联网）")
print("=" * 60)
recs = recommend_skills(by_type, total_tasks=8)
print(f"找到 {len(recs)} 条推荐：")
for r in recs:
    print(f"  🎯 {r.skill} ({r.priority})")
    print(f"     原因：{r.reason[:60]}...")
    print(f"     来源：{r.evidence_url}（未经验证）")
    print()

print("=" * 60)
print("测试 2：Markdown 格式输出")
print("=" * 60)
print(format_recommendations_md(recs[:1]))

print("=" * 60)
print("测试完成")
