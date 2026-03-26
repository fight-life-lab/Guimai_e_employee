#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人岗适配性测试脚本
用于测试完整的人岗适配分析流程
"""

import sys
import os
import json
from datetime import datetime
import logging

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'hr-bot'))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_alignment_analysis():
    """
    测试人岗适配分析流程
    """
    print("人岗适配性测试")
    print("=" * 60)
    
    # 测试用例：不同员工的适配性分析
    test_cases = [
        {
            "name": "测试用例1: 张三 - 软件工程师",
            "employee_name": "张三",
            "position_name": "软件工程师"
        },
        {
            "name": "测试用例2: 李四 - 产品经理",
            "employee_name": "李四",
            "position_name": "产品经理"
        },
        {
            "name": "测试用例3: 王五 - 销售经理",
            "employee_name": "王五",
            "position_name": "销售经理"
        }
    ]
    
    # 导入必要的模块
    try:
        from app.api.alignment_routes import (
            get_employee_info,
            get_job_description,
            get_attendance_summary,
            calculate_professional_ability_score,
            calculate_experience_score,
            calculate_innovation_score,
            calculate_learning_score,
            calculate_attitude_score,
            generate_conclusion,
            generate_quadrant_data
        )
        from app.database.models import EmpProfessionalAbility, EmpWorkExperience, EmpPatent
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine
        print("✅ 成功导入所需模块")
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 数据库配置
    MYSQL_HOST = "localhost"
    MYSQL_PORT = 3306
    MYSQL_DATABASE = "hr_employee_db"
    MYSQL_USER = "hr_user"
    MYSQL_PASSWORD = "hr_password"
    MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    
    # 创建数据库引擎和会话
    try:
        engine = create_engine(MYSQL_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        print("✅ 成功连接数据库")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 测试每个用例
    results = []
    for i, test_case in enumerate(test_cases):
        print(f"\n=== 测试用例 {i+1}: {test_case['name']} ===")
        
        try:
            # 1. 获取员工信息
            emp_info = get_employee_info(db, test_case['employee_name'])
            if not emp_info:
                print(f"❌ 未找到员工: {test_case['employee_name']}")
                results.append({
                    "test_case": test_case['name'],
                    "success": False,
                    "error": f"未找到员工: {test_case['employee_name']}"
                })
                continue
            
            print(f"✅ 找到员工: {emp_info['emp_name']} ({emp_info['emp_code']})")
            print(f"   部门: {emp_info['department']}")
            print(f"   岗位: {emp_info['position']}")
            
            # 2. 获取岗位描述
            job_desc = get_job_description(db, test_case['position_name'], test_case['employee_name'])
            if not job_desc:
                print(f"❌ 未找到岗位描述: {test_case['position_name']}")
                results.append({
                    "test_case": test_case['name'],
                    "success": False,
                    "error": f"未找到岗位描述: {test_case['position_name']}"
                })
                continue
            
            print(f"✅ 找到岗位描述: {job_desc['position_name']}")
            
            # 3. 获取考勤数据
            attendance = get_attendance_summary(db, emp_info['emp_code'])
            if attendance:
                print(f"✅ 获取考勤数据: 正常出勤{attendance['normal_days']:.1f}天")
            else:
                print("⚠️  未找到考勤数据")
            
            # 4. 计算各维度得分
            print("\n🔍 计算各维度得分:")
            
            # 专业能力
            prof_score, prof_req, prof_emp_reason, prof_job_reason = calculate_professional_ability_score(emp_info, job_desc, db)
            print(f"   专业能力: {prof_score:.1f}分 (要求: {prof_req:.1f}分)")
            
            # 经验
            exp_score, exp_req, exp_emp_reason, exp_job_reason = calculate_experience_score(emp_info, job_desc, db)
            print(f"   经验: {exp_score:.1f}分 (要求: {exp_req:.1f}分)")
            
            # 创新能力
            try:
                inn_score, inn_req, inn_emp_reason, inn_job_reason = calculate_innovation_score(emp_info, job_desc, db)
                print(f"   创新能力: {inn_score:.1f}分 (要求: {inn_req:.1f}分)")
            except Exception as e:
                print(f"   ⚠️  创新能力计算失败: {e}")
                inn_score, inn_req, inn_emp_reason, inn_job_reason = 0, 70, "计算失败", "默认要求"
            
            # 学习能力
            try:
                learn_score, learn_req, learn_emp_reason, learn_job_reason = calculate_learning_score(emp_info, job_desc)
                print(f"   学习能力: {learn_score:.1f}分 (要求: {learn_req:.1f}分)")
            except Exception as e:
                print(f"   ⚠️  学习能力计算失败: {e}")
                learn_score, learn_req, learn_emp_reason, learn_job_reason = 0, 60, "计算失败", "默认要求"
            
            # 工作态度
            atti_score, atti_req, atti_emp_reason, atti_job_reason = calculate_attitude_score(attendance, job_desc)
            print(f"   工作态度: {atti_score:.1f}分 (要求: {atti_req:.1f}分)")
            
            # 5. 计算综合得分
            # 权重：专业能力30%，经验10%，创新10%，学习20%，工作态度20%
            weights = {
                "专业能力": 0.3,
                "经验": 0.1,
                "创新能力": 0.1,
                "学习能力": 0.2,
                "工作态度": 0.2
            }
            
            # 构建维度列表
            dimensions = [
                {
                    "name": "专业能力",
                    "score": prof_score,
                    "weight": weights["专业能力"],
                    "job_requirement": prof_req,
                    "description": "基于绩效、职称证书、职业技能、专家聘任",
                    "employee_reason": prof_emp_reason,
                    "job_reason": prof_job_reason
                },
                {
                    "name": "经验",
                    "score": exp_score,
                    "weight": weights["经验"],
                    "job_requirement": exp_req,
                    "description": "基于工作年限和荣誉",
                    "employee_reason": exp_emp_reason,
                    "job_reason": exp_job_reason
                },
                {
                    "name": "创新能力",
                    "score": inn_score,
                    "weight": weights["创新能力"],
                    "job_requirement": inn_req,
                    "description": "基于专利",
                    "employee_reason": inn_emp_reason,
                    "job_reason": inn_job_reason
                },
                {
                    "name": "学习能力",
                    "score": learn_score,
                    "weight": weights["学习能力"],
                    "job_requirement": learn_req,
                    "description": "基于学历和专业匹配",
                    "employee_reason": learn_emp_reason,
                    "job_reason": learn_job_reason
                },
                {
                    "name": "工作态度",
                    "score": atti_score,
                    "weight": weights["工作态度"],
                    "job_requirement": atti_req,
                    "description": "基于考勤数据",
                    "employee_reason": atti_emp_reason,
                    "job_reason": atti_job_reason
                }
            ]
            
            # 计算加权综合得分
            overall_score = sum(dim['score'] * dim['weight'] for dim in dimensions)
            job_requirement_score = sum(dim['job_requirement'] * dim['weight'] for dim in dimensions)
            
            print(f"\n📊 综合得分: {overall_score:.1f}分 (岗位要求: {job_requirement_score:.1f}分)")
            
            # 6. 生成结论和建议
            conclusion, evaluation, recommendations = generate_conclusion(dimensions, overall_score, job_requirement_score)
            print(f"\n📝 结论: {conclusion}")
            print(f"   评价: {evaluation}")
            print("   建议:")
            for i, rec in enumerate(recommendations, 1):
                print(f"     {i}. {rec}")
            
            # 7. 生成四象限图数据
            quadrant_data = generate_quadrant_data(dimensions, overall_score, job_requirement_score)
            if quadrant_data:
                print(f"\n📍 四象限分析: {quadrant_data.get('quadrant_name', '未知')}")
            
            # 保存结果
            results.append({
                "test_case": test_case['name'],
                "success": True,
                "employee_info": {
                    "name": emp_info['emp_name'],
                    "code": emp_info['emp_code'],
                    "department": emp_info['department'],
                    "position": emp_info['position']
                },
                "overall_score": overall_score,
                "job_requirement_score": job_requirement_score,
                "evaluation": evaluation,
                "dimensions": dimensions,
                "conclusion": conclusion,
                "recommendations": recommendations
            })
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "test_case": test_case['name'],
                "success": False,
                "error": str(e)
            })
    
    # 关闭数据库连接
    try:
        db.close()
        print("\n✅ 数据库连接已关闭")
    except:
        pass
    
    # 输出测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        if result['success']:
            score = f"综合得分: {result['overall_score']:.1f}分 (要求: {result['job_requirement_score']:.1f}分)"
            eval_str = f"评价: {result['evaluation']}"
            print(f"{status} {result['test_case']} - {score} - {eval_str}")
        else:
            error = f"错误: {result.get('error', '未知')}"
            print(f"{status} {result['test_case']} - {error}")
    
    # 保存结果到文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"alignment_test_results_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n测试结果已保存到: {output_file}")

def main():
    """
    主函数
    """
    test_alignment_analysis()


if __name__ == "__main__":
    main()
