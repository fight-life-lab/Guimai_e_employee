#!/usr/bin/env python3
"""测试API调用"""

import requests
import json
import pandas as pd
import os

# API配置
API_URL = "http://121.229.172.161:3111/api/v1/interview-evaluation/evaluate-stream"

# JD内容
JD_CONTENT = """
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
"""

# 读取江焕垣的简历
def read_jiang_resume():
    file_path = "/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/data/招聘数据/综合办（董办）副主任报名表汇总/附件：新国脉数字文化股份有限公司招聘报名表-江焕垣.xlsx"
    
    try:
        df = pd.read_excel(file_path)
        resume_text = []
        
        for col in df.columns:
            for val in df[col].dropna():
                if isinstance(val, str) and val.strip():
                    resume_text.append(val.strip())
        
        resume_content = "\n".join(resume_text)
        return resume_content
    except Exception as e:
        print(f"读取失败: {e}")
        return None

# 测试API调用
def test_api_call():
    resume_content = read_jiang_resume()
    
    if not resume_content:
        print("无法读取简历内容")
        return
    
    print(f"简历内容长度: {len(resume_content)}")
    print(f"前1000字符: {resume_content[:1000]}...")
    
    # 准备数据
    data = {
        "jd_content": JD_CONTENT,
        "resume_content": resume_content[:3000],  # 进一步缩短
        "candidate_name": "江焕垣",
        "jd_title": "综合办副主任"
    }
    
    print("\n正在调用API...")
    
    try:
        response = requests.post(API_URL, data=data, timeout=600, stream=True)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            # 解析SSE格式
            final_data = None
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    print(f"接收到: {line}")
                    if line.startswith('data: '):
                        json_str = line[6:]
                        try:
                            event_data = json.loads(json_str)
                            if event_data.get('type') == 'result':
                                final_data = event_data.get('data')
                                break
                        except json.JSONDecodeError as e:
                            print(f"JSON解析错误: {e}")
                            continue
            
            if final_data:
                print("\n成功获取结果")
                print(f"综合评分: {final_data.get('overall_score')}")
            else:
                print("未收到结果数据")
        else:
            print(f"API错误: {response.text}")
    except Exception as e:
        print(f"请求异常: {e}")

if __name__ == "__main__":
    test_api_call()
