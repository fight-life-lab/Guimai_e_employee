#!/usr/bin/env python3
"""测试 AI面试评价流程 V4 - 双雷达图对比"""

import requests

url = "http://121.229.172.161:3111/api/v1/interview-evaluation/evaluate-v2"

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
4. 具备较强的统筹规划能力
"""

resume_content = """
姓名：董享前
学历：本科
专业：工商管理
工作经验：6年
曾任职位：行政主管
技能：公文写作、会议组织、项目管理
主要成就：
- 成功组织公司年度董事会会议
- 优化行政流程，提升工作效率30%
- 负责公司重要文件起草工作
"""

# 测试使用预存 ASR 数据（不需要上传音频文件）
data = {
    "jd_content": jd_content,
    "resume_content": resume_content,
    "candidate_name": "董享前",
    "jd_title": "综合办副主任"
}

print("=" * 70)
print("测试 AI面试评价 API - V4 (双雷达图对比)")
print("=" * 70)
print(f"\n候选人: 董享前")
print(f"岗位: 综合办副主任")
print(f"\n新功能:")
print("1. 左侧：JD岗位要求雷达图 + AI评分与理由")
print("2. 右侧：员工面试表现雷达图 + AI评分与理由")
print("3. 真伪验证：检查面试回答与简历一致性")
print("4. 问题提取：基于结构化面试问题评估回答")
print("5. 使用 Qwen3-235B 全尺寸大模型")
print("\n" + "=" * 70)
print("正在发送请求，请稍候（可能需要3-5分钟）...")
print("=" * 70 + "\n")

try:
    response = requests.post(url, data=data, timeout=600)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ 成功!")
        
        # JD岗位要求
        print(f"\n📋 JD岗位要求维度评分:")
        print("-" * 70)
        for dim in result.get('jd_dimensions', []):
            print(f"  • {dim['name']}: {dim['score']}分 - {dim.get('reason', '无')[:50]}...")
        
        # 候选人表现
        print(f"\n🎯 候选人表现维度评分:")
        print("-" * 70)
        for dim in result.get('candidate_dimensions', []):
            gap = dim.get('gap', 0)
            gap_str = f"+{gap}" if gap >= 0 else f"{gap}"
            print(f"  • {dim['name']}: {dim['score']}分 (差距: {gap_str}) - {dim.get('reason', '无')[:50]}...")
        
        # 综合评分
        print(f"\n📊 综合评分: {result.get('overall_score')}分")
        print(f"📋 评价等级: {result.get('evaluation_level')}")
        
        # 真伪验证
        auth = result.get('authenticity_check', {})
        print(f"\n🔍 真伪验证: {auth.get('status', '未知')} (可信度: {auth.get('confidence', 0)}%)")
        if auth.get('inconsistencies'):
            print(f"  发现 {len(auth['inconsistencies'])} 处不一致")
        
        # 问题回答
        qa_list = result.get('question_answers', [])
        if qa_list:
            print(f"\n❓ 结构化问题评估 ({len(qa_list)}个):")
            for i, qa in enumerate(qa_list[:3], 1):
                print(f"  问题{i}: {qa.get('score', 0)}分 - {qa.get('evaluation', '无')[:40]}...")
        
        print(f"\n📝 面试总结:")
        print("-" * 70)
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
