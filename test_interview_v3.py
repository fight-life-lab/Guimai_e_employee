#!/usr/bin/env python3
"""测试 AI面试评价流程 - V3 (使用预存 ASR 数据)"""

import requests

url = "http://121.229.172.161:3111/api/v1/interview-evaluation/evaluate"

# 测试数据
jd_content = """
综合办（董办）副主任岗位JD
岗位职责：
1. 协助主任处理综合办日常事务
2. 负责董事会相关文件起草和会议组织
3. 协调各部门工作，推进重点项目
任职要求：
1. 本科及以上学历，管理类相关专业
2. 5年以上相关工作经验
3. 优秀的沟通协调能力和文字功底
"""

resume_content = """
姓名：董享前
学历：本科
专业：工商管理
工作经验：6年
曾任职位：行政主管
技能：公文写作、会议组织、项目管理
"""

# 测试使用预存 ASR 数据（不需要上传音频文件）
data = {
    "jd_content": jd_content,
    "resume_content": resume_content,
    "candidate_name": "董享前",
    "jd_title": "综合办副主任"
}

print("=" * 60)
print("测试 AI面试评价 API - V3")
print("=" * 60)
print(f"\n候选人: 董享前")
print(f"岗位: 综合办副主任")
print(f"\n新功能:")
print("1. 优先使用预存 ASR 转录数据 (/root/shijingjing/e-employee/hr-bot/data/transcriptions/董享前.json)")
print("2. 面试录音提取 - 问题提取")
print("3. 岗位要求 vs 员工面试雷达图对比")
print("4. AI评分 + 评分理由")
print("5. 使用 Qwen3-235B 全尺寸大模型")
print("\n" + "=" * 60)
print("正在发送请求，请稍候（可能需要2-5分钟）...")
print("=" * 60 + "\n")

try:
    response = requests.post(url, data=data, timeout=600)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ 成功!")
        print(f"\n📊 综合评分: {result.get('overall_score')}")
        print(f"📋 评价等级: {result.get('evaluation_level')}")
        print(f"\n📝 转录文本长度: {len(result.get('transcript', ''))} 字符")
        
        # 显示6维度评分
        dimensions = result.get('dimensions', [])
        if dimensions:
            print(f"\n📈 6维度评分详情:")
            print("-" * 60)
            for dim in dimensions:
                print(f"  • {dim['name']}: {dim['score']}分 (权重{dim['weight']}%)")
                print(f"    评分理由: {dim['analysis'][:60]}...")
        
        # 显示问题回答
        question_answers = result.get('question_answers', [])
        if question_answers:
            print(f"\n❓ 提取的面试问题 ({len(question_answers)}个):")
            print("-" * 60)
            for i, qa in enumerate(question_answers[:3], 1):
                print(f"  问题{i}: {qa['question'][:40]}...")
                print(f"    评分: {qa['score']}分 - {qa['evaluation'][:40]}...")
        
        print(f"\n📝 面试总结:")
        print("-" * 60)
        print(result.get('summary', '无')[:200])
        
        print(f"\n✅ 优势:")
        for s in result.get('strengths', [])[:3]:
            print(f"  • {s}")
        
        print(f"\n💡 建议:")
        for r in result.get('recommendations', [])[:2]:
            print(f"  • {r}")
            
    else:
        print(f"\n❌ 错误: {response.text[:500]}")
except Exception as e:
    print(f"\n❌ 请求异常: {e}")
