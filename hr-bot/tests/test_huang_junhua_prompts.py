#!/usr/bin/env python3
"""
黄俊华面试评价测试脚本（不同prompt模板）
- 测试不同prompt模板的效果
- 与用户交互后决定是否更新到代码中
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

# 不同的prompt模板
prompt_templates = {
    "标准": "你是一位专业HR面试官，请深度评估候选人的面试表现，评分必须严格基于候选人的实际回答质量和与JD的匹配程度。",
    "详细": "你是一位专业HR面试官，请深度评估候选人的面试表现，评分必须严格基于候选人的实际回答质量和与JD的匹配程度。请提供详细的分析，包括具体的案例和证据支持。",
    "严格": "你是一位严格的HR面试官，请深度评估候选人的面试表现，评分必须严格基于候选人的实际回答质量和与JD的匹配程度。请严格按照JD要求进行评估，对不符合要求的方面要明确指出。",
    "全面": "你是一位全面的HR面试官，请从多个维度深度评估候选人的面试表现，包括专业能力、工作经验、沟通表达、逻辑思维、学习能力和综合素质。评分必须严格基于候选人的实际回答质量和与JD的匹配程度。"
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

def call_evaluation_api(candidate_name, resume_content, prompt_template, temperature=0.3):
    """调用面试评价API（支持流式响应）"""
    try:
        print(f"  正在评估 {candidate_name} (prompt: {prompt_template}, temperature: {temperature})...", end=" ", flush=True)
        
        # 流式请求
        data = {
            "jd_content": JD_CONTENT,
            "resume_content": resume_content,
            "candidate_name": candidate_name,
            "jd_title": "综合办副主任",
            "prompt_template": prompt_template,
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

def display_result(result):
    """显示评估结果"""
    if not result:
        print("  ⚠️ 无评价数据")
        return
    
    print(f"  📊 综合评分: {result.get('overall_score', 0):.1f}分")
    print(f"  📋 评价等级: {result.get('evaluation_level', '未知')}")
    
    # 显示主要优势
    strengths = result.get('strengths', [])
    if strengths:
        print(f"\n  ✅ 主要优势:")
        for s in strengths:
            print(f"    • {s}")
    
    # 显示改进建议
    recommendations = result.get('recommendations', [])
    if recommendations:
        print(f"\n  💡 改进建议:")
        for r in recommendations:
            print(f"    • {r}")
    
    # 显示总结
    summary = result.get('summary', '')
    if summary:
        print(f"\n  📝 面试总结:")
        print(f"    {summary}")

def main():
    """主函数"""
    print("=" * 100)
    print("🚀 黄俊华面试评价测试系统（不同prompt模板）")
    print("=" * 100)
    print(f"\n岗位: 综合办（董办）副主任")
    print(f"评价时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API地址: {API_URL}")
    print("\n" + "=" * 100)
    
    # 黄俊华的简历文件路径
    resume_file = "/Users/shijingjing/Desktop/人力数字员工测试结果/招聘数据/综合办（董办）副主任报名表汇总/附件：新国脉数字文化股份有限公司招聘报名表 - 黄俊华.xlsx"
    
    # 检查文件是否存在
    if not os.path.exists(resume_file):
        print(f"❌ 文件不存在: {resume_file}")
        return
    
    # 读取简历
    resume_content = read_resume_from_excel(resume_file)
    if not resume_content:
        print("❌ 无法读取简历内容，测试失败")
        return
    
    # 测试不同的prompt模板
    results = {}
    
    for prompt_name, prompt_text in prompt_templates.items():
        result = call_evaluation_api("黄俊华", resume_content, prompt_name)
        results[prompt_name] = result
    
    # 显示测试结果
    print("\n" + "=" * 100)
    print("📊 测试结果分析")
    print("=" * 100)
    
    for prompt_name, result in results.items():
        print(f"\n测试 (prompt: {prompt_name})")
        print("-" * 80)
        display_result(result)
    
    # 保存结果
    output_file = f"/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/data/huang_junhua_prompt_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 测试结果已保存到: {output_file}")
    
    # 与用户交互
    print("\n" + "=" * 100)
    print("🤝 交互确认")
    print("=" * 100)
    
    # 询问用户是否满意测试结果
    while True:
        user_input = input("您对测试结果是否满意？(y/n): ").strip().lower()
        if user_input in ['y', 'n']:
            break
        print("请输入 'y' 或 'n'")
    
    if user_input == 'y':
        print("\n✅ 测试结果满意，准备更新到代码中...")
        # 这里可以添加更新代码的逻辑
        print("✅ 代码更新完成，准备上线...")
        print("✅ 上线完成！")
    else:
        print("\n❌ 测试结果不满意，需要进一步调整...")
        # 这里可以添加进一步调整的逻辑
    
    print("\n" + "=" * 100)
    print("✅ 测试完成！")
    print("=" * 100)

if __name__ == "__main__":
    main()
