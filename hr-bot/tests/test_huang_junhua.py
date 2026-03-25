#!/usr/bin/env python3
"""
黄俊华面试评价测试脚本
- 测试不同的prompt和温度系数
- 分析测试结果
"""

import os
import sys
import pandas as pd
import requests
import json
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot')

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

# 测试参数
test_parameters = [
    {"prompt": "标准", "temperature": 0.3},
    {"prompt": "详细", "temperature": 0.3},
    {"prompt": "标准", "temperature": 0.5},
    {"prompt": "标准", "temperature": 0.7},
    {"prompt": "详细", "temperature": 0.5},
]

# 不同的prompt模板
prompt_templates = {
    "标准": "你是一位专业HR面试官，请深度评估候选人的面试表现，评分必须严格基于候选人的实际回答质量和与JD的匹配程度。",
    "详细": "你是一位专业HR面试官，请深度评估候选人的面试表现，评分必须严格基于候选人的实际回答质量和与JD的匹配程度。请提供详细的分析，包括具体的案例和证据支持。"
}

def read_resume_from_excel(filepath):
    """从Excel文件读取简历内容"""
    try:
        df = pd.read_excel(filepath)
        
        # 提取关键信息
        resume_text = []
        
        # 遍历所有单元格，提取非空文本
        for col in df.columns:
            for val in df[col].dropna():
                if isinstance(val, str) and val.strip():
                    resume_text.append(val.strip())
        
        resume_content = "\n".join(resume_text)
        # 限制内容长度，避免API错误
        if len(resume_content) > 5000:
            resume_content = resume_content[:5000]
            print(f"  简历内容过长，已截断至5000字符")
        return resume_content
    except Exception as e:
        print(f"❌ 读取文件失败 {filepath}: {e}")
        return None

def call_evaluation_api(candidate_name, resume_content, prompt_type, temperature):
    """调用面试评价API（支持流式响应）"""
    try:
        print(f"  正在评估 {candidate_name} (prompt: {prompt_type}, temperature: {temperature})...", end=" ", flush=True)
        
        # 流式请求
        data = {
            "jd_content": JD_CONTENT,
            "resume_content": resume_content,
            "candidate_name": candidate_name,
            "jd_title": "综合办副主任",
            "prompt_template": prompt_type,
            "temperature": temperature
        }
        
        response = requests.post(API_URL, data=data, timeout=600, stream=True)
        
        if response.status_code == 200:
            # 解析SSE格式
            final_data = None
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        json_str = line[6:]
                        try:
                            event_data = json.loads(json_str)
                            if event_data.get('type') == 'result':
                                final_data = event_data.get('data')
                                break
                        except json.JSONDecodeError:
                            continue
            
            if final_data:
                print("✅ 成功")
                return final_data
            else:
                print("❌ 失败: 未收到结果数据")
                return None
        else:
            print(f"❌ 失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ 异常: {e}")
        return None

def analyze_results(results):
    """分析测试结果"""
    print("\n" + "=" * 100)
    print("📊 测试结果分析")
    print("=" * 100)
    
    for i, (param, result) in enumerate(results.items()):
        print(f"\n测试 {i+1}: {param}")
        print("-" * 80)
        
        if result:
            print(f"  📊 综合评分: {result.get('overall_score', 0):.1f}分")
            print(f"  📋 评价等级: {result.get('evaluation_level', '未知')}")
            
            # 显示主要优势
            strengths = result.get('strengths', [])
            if strengths:
                print(f"  ✅ 主要优势:")
                for s in strengths[:3]:
                    print(f"    • {s}")
            
            # 显示改进建议
            recommendations = result.get('recommendations', [])
            if recommendations:
                print(f"  💡 改进建议:")
                for r in recommendations[:2]:
                    print(f"    • {r}")
        else:
            print("  ⚠️ 无评价数据")

def main():
    """主函数"""
    print("=" * 100)
    print("🚀 黄俊华面试评价测试系统")
    print("=" * 100)
    print(f"\n岗位: 综合办（董办）副主任")
    print(f"评价时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API地址: {API_URL}")
    print("\n" + "=" * 100)
    
    # 黄俊华的简历文件路径
    resume_file = "/Users/shijingjing/Desktop/人力数字员工测试结果/招聘数据/综合办（董办）副主任报名表汇总/附件：新国脉数字文化股份有限公司招聘报名表 - 黄俊华.xlsx"
    
    # 读取简历
    resume_content = read_resume_from_excel(resume_file)
    if not resume_content:
        print("❌ 无法读取简历内容，测试失败")
        return
    
    # 执行测试
    results = {}
    for param in test_parameters:
        prompt_type = param["prompt"]
        temperature = param["temperature"]
        key = f"prompt: {prompt_type}, temperature: {temperature}"
        
        result = call_evaluation_api("黄俊华", resume_content, prompt_type, temperature)
        results[key] = result
    
    # 分析结果
    analyze_results(results)
    
    # 保存结果
    output_file = f"/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/data/huang_junhua_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 测试结果已保存到: {output_file}")
    
    print("\n" + "=" * 100)
    print("✅ 测试完成！")
    print("=" * 100)

if __name__ == "__main__":
    main()
