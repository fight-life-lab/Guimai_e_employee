#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专业能力得分测试脚本
用于测试专业能力分数计算逻辑
"""

import sys
import os
import json
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'hr-bot'))


def calculate_professional_ability_score_test():
    """
    测试专业能力得分计算逻辑
    """
    print("专业能力得分计算测试")
    print("=" * 50)
    
    # 模拟员工数据
    test_cases = [
        {
            "name": "测试用例1: 基础分 + 试用期优秀 + 无其他加分",
            "probation_score": 85,
            "performance_history": None,
            "titles": [],
            "skills": [],
            "is_company_expert": False,
            "is_senior_expert": False,
            "is_chief_expert": False
        },
        {
            "name": "测试用例2: 基础分 + 试用期不达标 + 公司专家",
            "probation_score": 75,
            "performance_history": None,
            "titles": [],
            "skills": [],
            "is_company_expert": True,
            "is_senior_expert": False,
            "is_chief_expert": False
        },
        {
            "name": "测试用例3: 基础分 + 年度优秀 + 高级专家 + 职称A + 技能B",
            "probation_score": None,
            "performance_history": [
                {"year": "2025", "level": "优秀"},
                {"year": "2024", "level": "称职"}
            ],
            "titles": [
                {"company_level": "A", "title_name": "高级工程师"}
            ],
            "skills": [
                {"company_level": "B", "skill_name": "Python开发"}
            ],
            "is_company_expert": False,
            "is_senior_expert": True,
            "is_chief_expert": False
        }
    ]
    
    # 导入计算函数
    try:
        from app.api.alignment_routes import calculate_professional_ability_score
        print("✅ 成功导入计算函数")
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return
    
    # 测试每个用例
    results = []
    for i, test_case in enumerate(test_cases):
        print(f"\n=== 测试用例 {i+1}: {test_case['name']} ===")
        
        # 构建员工信息
        emp_info = {"emp_code": "test_emp"}
        job_desc = {}
        
        # 模拟数据库对象
        class MockDB:
            def query(self, model):
                class MockQuery:
                    def filter(self, condition):
                        class MockResult:
                            probation_score = test_case['probation_score']
                            performance_history = test_case['performance_history']
                            professional_titles = test_case['titles']
                            professional_skills = test_case['skills']
                            is_company_expert = test_case['is_company_expert']
                            is_senior_expert = test_case['is_senior_expert']
                            is_chief_expert = test_case['is_chief_expert']
                            
                            def first(self):
                                return self
                        return MockResult()
                return MockQuery()
        
        db = MockDB()
        
        try:
            score, job_requirement, employee_reason, job_reason = calculate_professional_ability_score(emp_info, job_desc, db)
            print(f"✅ 计算成功")
            print(f"得分: {score:.1f}")
            print(f"岗位要求: {job_requirement}")
            print(f"理由: {employee_reason}")
            results.append({
                "test_case": test_case['name'],
                "score": score,
                "success": True
            })
        except Exception as e:
            print(f"❌ 计算失败: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "test_case": test_case['name'],
                "success": False,
                "error": str(e)
            })
    
    # 输出测试结果
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        score = f"得分: {result.get('score', 'N/A'):.1f}" if result['success'] else f"错误: {result.get('error', '未知')}"
        print(f"{status} {result['test_case']} - {score}")
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"professional_score_test_results_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n测试结果已保存到: {output_file}")


def main():
    """
    主函数
    """
    calculate_professional_ability_score_test()


if __name__ == "__main__":
    main()
