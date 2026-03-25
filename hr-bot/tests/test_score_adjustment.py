#!/usr/bin/env python3
"""
测试候选人分数调整功能
"""

import requests
import json
import time

def test_score_adjustment(candidate_name):
    """测试候选人分数调整"""
    print(f"\n=== 测试 {candidate_name} 分数调整 ===")
    
    # 测试数据
    jd_content = "综合办（董办）副主任岗位，负责公司治理、董事会运作等工作"
    resume_text = f"{candidate_name}的简历内容"
    transcript = f"{candidate_name}的面试回答"
    
    # API端点
    url = "http://121.229.172.161:3111/api/v1/interview-evaluation/evaluate-stream"
    
    try:
        # 发送请求
        response = requests.post(url, data={
            "jd_content": jd_content,
            "resume_content": resume_text,
            "candidate_name": candidate_name
        }, stream=True)
        
        if response.status_code == 200:
            # 处理流式响应
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data:'):
                        data_str = line[5:]
                        try:
                            data = json.loads(data_str)
                            if data.get('type') == 'result':
                                # 提取结果
                                result_data = data.get('data', {})
                                candidate_dimensions = result_data.get('candidate_dimensions', [])
                                overall_score = result_data.get('overall_score', 0)
                                
                                print(f"综合分数: {overall_score}")
                                print("各维度分数:")
                                for dim in candidate_dimensions:
                                    print(f"  {dim.get('name')}: {dim.get('score')}")
                                return True
                        except json.JSONDecodeError:
                            pass
        else:
            print(f"请求失败: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"测试失败: {str(e)}")
    
    return False

if __name__ == "__main__":
    # 测试两位候选人
    test_score_adjustment("王霄凯")
    test_score_adjustment("黄俊华")
