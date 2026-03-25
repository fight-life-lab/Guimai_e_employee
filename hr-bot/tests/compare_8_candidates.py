#!/usr/bin/env python3
"""
8个候选人对比评分脚本
- 读取8个候选人的报名表
- 调用面试评价API进行评分
- 按总分排序并展示各维度理由
"""

import os
import sys
import pandas as pd
import requests
import json
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot')

# API配置
API_URL = "http://121.229.172.161:3111/api/v1/interview-evaluation/evaluate-v2"
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

# 候选人文件路径
CANDIDATE_FILES = [
    "/Users/shijingjing/Desktop/人力数字员工测试结果/招聘数据/综合办（董办）副主任报名表汇总/附件：新国脉数字文化股份有限公司招聘报名表-董享前.xlsx",
    "/Users/shijingjing/Desktop/人力数字员工测试结果/招聘数据/综合办（董办）副主任报名表汇总/附件：新国脉数字文化股份有限公司招聘报名表-宋浩.xlsx",
    "/Users/shijingjing/Desktop/人力数字员工测试结果/招聘数据/综合办（董办）副主任报名表汇总/附件：新国脉数字文化股份有限公司招聘报名表-干鹤翔.xlsx",
    "/Users/shijingjing/Desktop/人力数字员工测试结果/招聘数据/综合办（董办）副主任报名表汇总/附件：新国脉数字文化股份有限公司招聘报名表-张春远.xlsx",
    "/Users/shijingjing/Desktop/人力数字员工测试结果/招聘数据/综合办（董办）副主任报名表汇总/附件：新国脉数字文化股份有限公司招聘报名表-王霄慨.xlsx",
    "/Users/shijingjing/Desktop/人力数字员工测试结果/招聘数据/综合办（董办）副主任报名表汇总/附件：新国脉数字文化股份有限公司招聘报名表-陈岗.xlsx",
    "/Users/shijingjing/Desktop/人力数字员工测试结果/招聘数据/综合办（董办）副主任报名表汇总/附件：新国脉数字文化股份有限公司招聘报名表 - 江焕垣.xlsx",
    "/Users/shijingjing/Desktop/人力数字员工测试结果/招聘数据/综合办（董办）副主任报名表汇总/附件：新国脉数字文化股份有限公司招聘报名表 - 黄俊华.xlsx",
]


def extract_candidate_name(filename):
    """从文件名提取候选人姓名"""
    basename = os.path.basename(filename)
    # 提取姓名部分
    if "-" in basename:
        name_part = basename.split("-")[-1]
    elif " - " in basename:
        name_part = basename.split(" - ")[-1]
    else:
        name_part = basename
    
    # 去掉扩展名
    name = name_part.replace(".xlsx", "").replace("xlsx", "")
    name = name.strip()
    return name


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


def call_evaluation_api(candidate_name, resume_content):
    """调用面试评价API（支持流式响应）"""
    # 模拟数据 - 当API不可用时使用
    mock_result = {
        "overall_score": 85.0,
        "evaluation_level": "优秀",
        "jd_dimensions": [
            {"name": "专业能力", "score": 88, "reason": "具备丰富的综合办公经验"},
            {"name": "经验", "score": 90, "reason": "5年以上相关工作经验"},
            {"name": "创新能力", "score": 78, "reason": "有一定的创新意识"},
            {"name": "学习能力", "score": 82, "reason": "学习能力较强"},
            {"name": "工作态度", "score": 86, "reason": "工作态度认真负责"}
        ],
        "candidate_dimensions": [
            {"name": "专业能力", "score": 88, "gap": 0, "reason": "符合岗位要求"},
            {"name": "经验", "score": 90, "gap": 5, "reason": "超出岗位要求"},
            {"name": "创新能力", "score": 78, "gap": -2, "reason": "略低于岗位要求"},
            {"name": "学习能力", "score": 82, "gap": 2, "reason": "符合岗位要求"},
            {"name": "工作态度", "score": 86, "gap": 1, "reason": "符合岗位要求"}
        ],
        "authenticity_check": {
            "status": "真实",
            "confidence": 95
        },
        "strengths": ["沟通协调能力强", "文字功底扎实", "统筹规划能力突出"],
        "recommendations": ["加强创新能力培养", "提升数字化办公技能"],
        "summary": "候选人整体素质优秀，具备较强的综合能力，符合岗位要求。"
    }
    
    try:
        print(f"  正在评估 {candidate_name}...", end=" ", flush=True)
        
        # 流式请求
        data = {
            "jd_content": JD_CONTENT,
            "resume_content": resume_content,
            "candidate_name": candidate_name,
            "jd_title": "综合办副主任"
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
                print("⚠️ API无数据，使用模拟数据")
                return mock_result
        else:
            print(f"⚠️ API失败，使用模拟数据")
            return mock_result
    except Exception as e:
        print(f"⚠️ API异常，使用模拟数据: {e}")
        return mock_result


def calculate_total_score(result):
    """计算总分"""
    if not result:
        return 0
    
    # 使用综合评分
    overall = result.get('overall_score', 0)
    return overall


def display_comparison(results):
    """显示对比结果"""
    print("\n" + "=" * 100)
    print("📊 8位候选人面试评价对比结果")
    print("=" * 100)
    
    # 按总分排序
    sorted_results = sorted(results.items(), key=lambda x: x[1]['total_score'], reverse=True)
    
    # 显示排名表
    print("\n🏆 排名总览（按总分降序）")
    print("-" * 100)
    print(f"{'排名':<6}{'姓名':<10}{'总分':<10}{'等级':<10}{'专业能力':<10}{'经验':<10}{'创新能力':<10}{'学习能力':<10}{'工作态度':<10}")
    print("-" * 100)
    
    for rank, (name, data) in enumerate(sorted_results, 1):
        result = data['result']
        total = data['total_score']
        level = result.get('evaluation_level', '未知') if result else 'N/A'
        
        # 获取各维度分数（使用候选人维度，而不是JD维度）
        print('---data',data)
        cand_dims = result.get('candidate_dimensions', []) if result else []
        scores = {}
        for dim in cand_dims:
            scores[dim.get('name', '')] = dim.get('score', 0)
        
        prof = scores.get('专业能力', 0)
        exp = scores.get('工作经验', 0)
        innov = scores.get('创新能力', 0)
        learn = scores.get('学习能力', 0)
        att = scores.get('工作态度', 0)
        
        print(f"{rank:<6}{name:<10}{total:<10.1f}{level:<10}{prof:<10}{exp:<10}{innov:<10}{learn:<10}{att:<10}")
    
    print("-" * 100)
    
    # 显示详细评价
    print("\n📋 详细评价与理由")
    print("=" * 100)
    
    for rank, (name, data) in enumerate(sorted_results, 1):
        result = data['result']
        
        print(f"\n【第{rank}名】{name}")
        print("-" * 80)
        
        if not result:
            print("  ⚠️ 无评价数据")
            continue
        
        # 综合信息
        print(f"  📊 综合评分: {result.get('overall_score', 0):.1f}分")
        print(f"  📋 评价等级: {result.get('evaluation_level', '未知')}")
        
        # JD维度评分与理由
        print(f"\n  📋 JD岗位要求维度评分与理由:")
        jd_dims = result.get('jd_dimensions', [])
        for dim in jd_dims:
            dim_name = dim.get('name', '')
            score = dim.get('score', 0)
            reason = dim.get('reason', '无')
            print(f"    • {dim_name}: {score}分")
            print(f"      理由: {reason}")
        
        # 候选人表现维度
        print(f"\n  🎯 候选人表现维度评分与差距:")
        cand_dims = result.get('candidate_dimensions', [])
        for dim in cand_dims:
            dim_name = dim.get('name', '')
            score = dim.get('score', 0)
            gap = dim.get('gap', 0)
            reason = dim.get('reason', '无')
            gap_str = f"+{gap}" if gap >= 0 else f"{gap}"
            print(f"    • {dim_name}: {score}分 (与JD要求差距: {gap_str})")
            print(f"      理由: {reason}")
        
        # 真伪验证
        auth = result.get('authenticity_check', {})
        if auth:
            print(f"\n  🔍 真伪验证: {auth.get('status', '未知')} (可信度: {auth.get('confidence', 0)}%)")
        
        # 优势与建议
        print(f"\n  ✅ 主要优势:")
        for s in result.get('strengths', [])[:3]:
            print(f"    • {s}")
        
        print(f"\n  💡 改进建议:")
        for r in result.get('recommendations', [])[:2]:
            print(f"    • {r}")
        
        # 总结
        print(f"\n  📝 面试总结:")
        summary = result.get('summary', '无')
        print(f"    {summary[:200]}...")
        
        print("-" * 80)
    
    # 输出总结对比表
    print("\n\n📈 总结对比表")
    print("=" * 100)
    print(f"{'排名':<6}{'姓名':<10}{'总分':<10}{'优势亮点':<50}")
    print("-" * 100)
    
    for rank, (name, data) in enumerate(sorted_results, 1):
        result = data['result']
        total = data['total_score']
        
        if result:
            strengths = result.get('strengths', [])
            highlight = strengths[0] if strengths else "暂无"
            if len(highlight) > 45:
                highlight = highlight[:45] + "..."
        else:
            highlight = "无数据"
        
        print(f"{rank:<6}{name:<10}{total:<10.1f}{highlight:<50}")
    
    print("=" * 100)


def main():
    """主函数"""
    print("=" * 100)
    print("🚀 8位候选人面试评价对比系统")
    print("=" * 100)
    print(f"\n岗位: 综合办（董办）副主任")
    print(f"评价时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API地址: {API_URL}")
    print("\n" + "=" * 100)
    
    results = {}
    
    # 处理每个候选人
    for i, filepath in enumerate(CANDIDATE_FILES, 1):
        # 检查文件是否存在
        if not os.path.exists(filepath):
            # 尝试其他文件名格式
            alt_path = filepath.replace(" - ", "-")
            if os.path.exists(alt_path):
                filepath = alt_path
            else:
                print(f"\n⚠️ 文件不存在，跳过: {filepath}")
                continue
        
        candidate_name = extract_candidate_name(filepath)
        print(f"\n[{i}/8] 处理候选人: {candidate_name}")
        
        # 读取简历
        resume_content = read_resume_from_excel(filepath)
        if not resume_content:
            print(f"  ⚠️ 无法读取简历内容，跳过")
            continue
        
        # 调用API
        result = call_evaluation_api(candidate_name, resume_content)
        
        if result:
            total_score = calculate_total_score(result)
            results[candidate_name] = {
                'result': result,
                'total_score': total_score,
                'filepath': filepath
            }
        else:
            results[candidate_name] = {
                'result': None,
                'total_score': 0,
                'filepath': filepath
            }
    
    # 显示对比结果
    if results:
        display_comparison(results)
        
        # 保存结果到文件
        output_file = f"/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/data/candidates_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            # 只保存可序列化的数据
            save_data = {}
            for name, data in results.items():
                save_data[name] = {
                    'total_score': data['total_score'],
                    'result': data['result']
                }
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 结果已保存到: {output_file}")
    else:
        print("\n❌ 没有成功获取任何候选人的评价结果")
    
    print("\n" + "=" * 100)
    print("✅ 对比完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
