#!/usr/bin/env python3
"""
测试张春远的专业能力评估
"""

import requests
import json

API_URL = 'http://121.229.172.161:3111/api/v1/interview-evaluation/evaluate-stream'

JD_CONTENT = '''
综合办（董办）副主任岗位JD
岗位职责：
1. 协助主任处理综合办日常事务
2. 负责董事会相关文件起草和会议组织
3. 协调各部门工作，推进重点项目
4. 负责公司重要文稿撰写和审核
5. 参与公司战略规划和决策支持

任职要求：
1. 本科及以上学历，管理类、中文、法律等相关专业优先
2. 5年以上相关工作经验，有国企或大型企业工作经验者优先
3. 优秀的沟通协调能力和文字功底
4. 具备较强的统筹规划能力和执行力
5. 熟悉公司治理、董事会运作流程
6. 具备较强的政治敏感性和保密意识
'''

# 张春远的简历内容
RESUME_CONTENT = '''
姓名：张春远
工作经历：
- 中昊智达集团 总裁办主任（8年）
- 负责行政、人事、法务等工作
- 参与过公司战略规划

教育背景：
- 中国劳动关系学院 公共管理硕士（在读）
- 大专，管理专业
'''

data = {
    'jd_content': JD_CONTENT,
    'resume_content': RESUME_CONTENT,
    'candidate_name': '张春远',  # 使用正确的名字触发预存ASR
    'jd_title': '综合办副主任'
}

print('正在测试张春远的专业能力评估...')
response = requests.post(API_URL, data=data, stream=True, timeout=600)

if response.status_code == 200:
    print('✅ API调用成功')
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                try:
                    event_data = json.loads(line[6:])
                    if event_data.get('type') == 'progress':
                        print(f"进度: {event_data.get('progress')}% - {event_data.get('message')}")
                    elif event_data.get('type') == 'result':
                        result = event_data.get('data')
                        print('\n📊 评估结果：')
                        print(f'综合评分: {result.get("overall_score", 0)}分')
                        print(f'评价等级: {result.get("evaluation_level", "未知")}')
                        
                        print('\n🎯 专业能力评估：')
                        for dim in result.get('candidate_dimensions', []):
                            if dim.get('name') == '专业能力':
                                print(f'专业能力: {dim.get("score", 0)}分')
                                print(f'与JD要求差距: {dim.get("gap", 0)}')
                                print(f'理由: {dim.get("reason", "无")}')
                        break
                except json.JSONDecodeError:
                    continue
else:
    print(f'❌ API调用失败: {response.status_code}')
    print(f'响应内容: {response.text[:500]}')
