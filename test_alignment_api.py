#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人岗适配性API测试脚本
直接调用远程服务器接口进行测试
"""

import requests
import json
from datetime import datetime

# API基础地址
API_BASE = "http://121.229.172.161:3111"

def test_alignment_api():
    """
    测试人岗适配分析API
    """
    print("人岗适配性API测试")
    print("=" * 60)
    print(f"API地址: {API_BASE}/api/v1/alignment/analyze")
    print("=" * 60)
    
    # 测试用例 - 使用胡冰进行测试
    test_cases = [
        {
            "name": "测试用例: 胡冰",
            "employee_name": "胡冰",
            "position_name": None
        }
    ]
    
    # 测试每个用例
    results = []
    for i, test_case in enumerate(test_cases):
        print(f"\n=== 测试用例 {i+1}: {test_case['name']} ===")
        
        try:
            # 构建请求数据
            payload = {
                "employee_name": test_case['employee_name']
            }
            if test_case['position_name']:
                payload['position_name'] = test_case['position_name']
            
            print(f"请求参数: {json.dumps(payload, ensure_ascii=False)}")
            
            # 发送请求
            response = requests.post(
                f"{API_BASE}/api/v1/alignment/analyze",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            # 检查响应状态
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success'):
                    print(f"✅ 分析成功")
                    print(f"员工: {result.get('employee_name')} ({result.get('employee_code')})")
                    print(f"部门: {result.get('department')}")
                    print(f"岗位: {result.get('position')}")
                    print(f"综合得分: {result.get('overall_score', 0):.1f}分")
                    print(f"岗位要求: {result.get('job_requirement_score', 0):.1f}分")
                    print(f"评价: {result.get('evaluation')}")
                    
                    # 打印各维度得分
                    dimensions = result.get('dimensions', [])
                    if dimensions:
                        print("\n各维度得分:")
                        for dim in dimensions:
                            print(f"  - {dim['name']}: {dim['score']:.1f}分 (要求: {dim['job_requirement']:.1f}分, 权重: {dim['weight']*100:.0f}%)")
                    
                    # 打印四象限分析
                    quadrant = result.get('quadrant')
                    if quadrant:
                        print(f"\n四象限分析: {quadrant.get('quadrant_name', '未知')}")
                    
                    # 保存结果
                    results.append({
                        "test_case": test_case['name'],
                        "success": True,
                        "data": result
                    })
                else:
                    error_msg = result.get('message', '未知错误')
                    print(f"❌ 分析失败: {error_msg}")
                    results.append({
                        "test_case": test_case['name'],
                        "success": False,
                        "error": error_msg
                    })
            else:
                print(f"❌ 请求失败: HTTP {response.status_code}")
                print(f"响应内容: {response.text}")
                results.append({
                    "test_case": test_case['name'],
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                })
                
        except requests.exceptions.Timeout:
            print(f"❌ 请求超时")
            results.append({
                "test_case": test_case['name'],
                "success": False,
                "error": "请求超时"
            })
        except requests.exceptions.ConnectionError:
            print(f"❌ 连接失败，请检查服务器是否运行")
            results.append({
                "test_case": test_case['name'],
                "success": False,
                "error": "连接失败"
            })
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "test_case": test_case['name'],
                "success": False,
                "error": str(e)
            })
    
    return results

def test_health_check():
    """
    测试服务器健康状态
    """
    print("\n服务器健康检查")
    print("=" * 60)
    
    try:
        response = requests.get(
            f"{API_BASE}/health",
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 服务器运行正常")
            print(f"状态: {result.get('status', 'unknown')}")
            return True
        else:
            print(f"❌ 服务器异常: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return False

def test_dimensions_api():
    """
    测试维度配置API
    """
    print("\n维度配置API测试")
    print("=" * 60)
    
    try:
        response = requests.get(
            f"{API_BASE}/api/v1/alignment/dimensions",
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 获取维度配置成功")
            
            dimensions = result.get('dimensions', [])
            if dimensions:
                print("\n维度配置:")
                for dim in dimensions:
                    print(f"  - {dim.get('name')}: 权重 {dim.get('weight', 0)*100:.0f}%")
            
            return result
        else:
            print(f"❌ 获取维度配置失败: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return None

def main():
    """
    主函数
    """
    print("人岗适配性API测试脚本")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. 健康检查
    is_healthy = test_health_check()
    
    if not is_healthy:
        print("\n⚠️ 服务器未正常运行，跳过其他测试")
        return
    
    # 2. 获取维度配置
    dimensions_result = test_dimensions_api()
    
    # 3. 测试人岗适配分析API
    alignment_results = test_alignment_api()
    
    # 4. 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print("=" * 60)
    
    success_count = sum(1 for r in alignment_results if r['success'])
    total_count = len(alignment_results)
    
    print(f"总测试数: {total_count}")
    print(f"成功: {success_count}")
    print(f"失败: {total_count - success_count}")
    
    for result in alignment_results:
        status = "✅" if result['success'] else "❌"
        if result['success']:
            data = result['data']
            score = f"得分: {data.get('overall_score', 0):.1f}分"
            eval_str = f"评价: {data.get('evaluation', '未知')}"
            print(f"{status} {result['test_case']} - {score} - {eval_str}")
        else:
            error = f"错误: {result.get('error', '未知')}"
            print(f"{status} {result['test_case']} - {error}")
    
    # 5. 保存结果到文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"alignment_api_test_results_{timestamp}.json"
    
    all_results = {
        "api_base": API_BASE,
        "timestamp": datetime.now().isoformat(),
        "health_check": is_healthy,
        "dimensions": dimensions_result,
        "alignment_tests": alignment_results
    }
    
    # with open(output_file, 'w', encoding='utf-8') as f:
    #     json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n测试结果已保存到: {output_file}")
    print("\n测试完成！")


if __name__ == "__main__":
    main()
