#!/usr/bin/env python3
"""
测试AI评估分数缓存功能
"""

import requests
import json

BASE_URL = "http://localhost:3111"
PROJECT = "20260401战略招聘"

def test_evaluation_cache_api():
    """测试评估缓存API"""
    print("=" * 60)
    print("测试AI评估分数缓存功能")
    print("=" * 60)
    
    # 1. 测试批量获取评估缓存
    print("\n1. 测试批量获取评估缓存API")
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/interview-evaluation/evaluations-batch",
            params={"project": PROJECT},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API调用成功")
            print(f"   - 成功: {data.get('success')}")
            print(f"   - 总数: {data.get('total')}")
            print(f"   - 消息: {data.get('message')}")
            
            if data.get('evaluations'):
                print(f"\n   评估缓存列表:")
                for eval_item in data['evaluations'][:3]:  # 只显示前3个
                    candidate_name = eval_item.get('candidate_name', '未知')
                    evaluation = eval_item.get('evaluation', {})
                    overall_score = evaluation.get('overall_score', 'N/A')
                    print(f"   - {candidate_name}: 综合评分 {overall_score}")
            
            return True
        else:
            print(f"❌ API调用失败: {response.status_code}")
            print(f"   错误: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_single_evaluation_cache():
    """测试单个候选人评估缓存"""
    print("\n2. 测试单个候选人评估缓存API")
    
    # 先获取候选人列表
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/interview-batch/candidates/{PROJECT}",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            candidates = data.get('candidates', [])
            
            if candidates:
                # 测试第一个候选人
                candidate_name = candidates[0].get('name', '')
                print(f"   测试候选人: {candidate_name}")
                
                response = requests.get(
                    f"{BASE_URL}/api/v1/interview-evaluation/evaluation-cache",
                    params={
                        "candidate_name": candidate_name,
                        "project": PROJECT
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ API调用成功")
                    print(f"   - 有缓存: {data.get('cached')}")
                    if data.get('cached'):
                        eval_data = data.get('evaluation', {})
                        print(f"   - 综合评分: {eval_data.get('overall_score', 'N/A')}")
                        print(f"   - 评价等级: {eval_data.get('evaluation_level', 'N/A')}")
                        
                        # 显示6个维度分数
                        dimensions = eval_data.get('dimensions', [])
                        if dimensions:
                            print(f"   - 6维度评分:")
                            for dim in dimensions:
                                print(f"     • {dim.get('name')}: {dim.get('score')}分")
                    return True
                else:
                    print(f"❌ API调用失败: {response.status_code}")
                    return False
            else:
                print("   暂无候选人数据")
                return True
        else:
            print(f"❌ 获取候选人列表失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


if __name__ == "__main__":
    print("\n请确保服务已启动: uvicorn app.main:app --host 0.0.0.0 --port 3111\n")
    
    results = []
    results.append(("批量获取评估缓存", test_evaluation_cache_api()))
    results.append(("单个候选人评估缓存", test_single_evaluation_cache()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
