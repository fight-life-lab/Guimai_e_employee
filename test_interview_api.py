#!/usr/bin/env python3
"""测试AI面试评价API"""

import requests
import json

url = "http://121.229.172.161:3111/api/v1/interview-evaluation/evaluate"

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

# 打开音频文件
with open("/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/data/综合办（董办）副主任岗位电话面试录音/03月20日_2（董享前）.aac", "rb") as f:
    files = {
        "audio_file": ("03月20日_2（董享前）.aac", f, "audio/aac")
    }
    data = {
        "jd_content": jd_content,
        "resume_content": resume_content
    }
    
    print("正在发送AI面试评价请求，请稍候（可能需要1-3分钟）...")
    try:
        response = requests.post(url, data=data, files=files, timeout=300)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 成功!")
            print(f"综合评分: {result.get('overall_score')}")
            print(f"评价等级: {result.get('evaluation_level')}")
            print(f"转录文本长度: {len(result.get('transcript', ''))} 字符")
            print(f"维度数: {len(result.get('dimensions', []))}")
            print(f"\n面试总结:")
            print(result.get('summary', '无')[:200] + '...')
        else:
            print(f"❌ 错误: {response.text}")
    except Exception as e:
        print(f"❌ 请求异常: {e}")
