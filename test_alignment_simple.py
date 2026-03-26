#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人岗适配性测试脚本（简化版）
用于测试核心的人岗适配分析逻辑
"""

import sys
import os
import json
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'hr-bot'))

def test_professional_ability_score():
    """
    测试专业能力得分计算
    """
    print("专业能力得分计算测试")
    print("=" * 50)
    
    # 测试用例
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
    
    # 模拟计算函数
    def calculate_professional_ability_score(emp_info, job_desc, db):
        """
        计算专业能力维度得分（权重30%）
        基于：绩效、职称证书、职业技能、专家聘任
        """
        # 初始化得分和理由
        performance_score = 70  # 绩效基础分70分
        certification_score = 0  # 认证得分
        expert_bonus = 0  # 专家聘任加分
        reasons = ["绩效基础分70分（占比80%）"]
        
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
        
        # 从数据库获取员工专业能力数据
        prof_ability = db.query(None).filter(None).first()
        
        if prof_ability:
            # 1. 绩效计算（二选一）
            performance_adjustment = 0
            performance_reason = ""
            
            # 选项1：试用期分数
            if prof_ability.probation_score is not None:
                if float(prof_ability.probation_score) >= 80:
                    performance_adjustment = 10
                    performance_reason = f"试用期考核{prof_ability.probation_score}分≥80分，+10分"
                else:
                    performance_adjustment = -5
                    performance_reason = f"试用期考核{prof_ability.probation_score}分<80分，-5分"
            
            # 选项2：3年内年度绩效
            elif prof_ability.performance_history:
                perf_history = prof_ability.performance_history
                if isinstance(perf_history, list):
                    excellent_count = 0
                    basic_count = 0
                    # 只统计2023、2024、2025年的绩效
                    valid_years = ['2023', '2024', '2025']
                    for perf in perf_history:
                        year = str(perf.get('year', ''))
                        if year in valid_years:
                            level = str(perf.get('level', '')).lower()
                            if '优秀' in level or 'a' in level or 'p1' in level:
                                excellent_count += 1
                            elif '基本称职' in level or 'c' in level:
                                basic_count += 1
                    
                    if excellent_count > 0:
                        performance_adjustment = 15 * excellent_count
                        performance_reason = f"近3年{excellent_count}次年度绩效优秀，+{performance_adjustment}分"
                    elif basic_count > 0:
                        performance_adjustment = -15 * basic_count
                        performance_reason = f"近3年{basic_count}次年度绩效基本称职，{performance_adjustment}分"
            
            if performance_adjustment != 0:
                performance_score += performance_adjustment
                reasons.append(performance_reason)
            
            # 2. 按照《国脉文化认证目录（2025年版）》计算认证得分
            # 2.1 职称证书（多项取高）
            title_score = 0
            title_str = ''
            title_count = 0
            if prof_ability.professional_titles:
                titles = prof_ability.professional_titles
                if isinstance(titles, list):
                    for title in titles:
                        level = str(title.get('company_level', '')).upper()
                        skill_name = str(title.get('title_name', ''))
                        title_str += skill_name
                        title_count += 1
                        if level == 'A':
                            title_score = max(title_score, 40)
                        elif level == 'B':
                            title_score = max(title_score, 30)
                        elif level == 'C':
                            title_score = max(title_score, 20)
            
            # 2.2 职业技能（可累计）
            skill_score = 0
            skill_str = ''
            skill_count = 0
            if prof_ability.professional_skills:
                skills = prof_ability.professional_skills
                if isinstance(skills, list):
                    for skill in skills:
                        level = str(skill.get('company_level', '')).upper()
                        skill_name = str(skill.get('skill_name', ''))
                        skill_str += skill_name
                        skill_count += 1
                        if level == 'A':
                            skill_score += 30
                        elif level == 'B':
                            skill_score += 20
                        elif level == 'C':
                            skill_score += 10
            
            # 计算认证总分（占比20%）
            certification_score = (title_score + skill_score) * 0.2
            if certification_score > 0:
                cert_reason = []
                if title_score > 0:
                    if title_count > 1:
                        cert_reason.append(f"{title_count}项职称（{title_str}），{title_score}分")
                    else:
                        cert_reason.append(f"{title_str}职称，{title_score}分")
                if skill_score > 0:
                    if skill_count > 1:
                        cert_reason.append(f"{skill_count}项职业技能（{skill_str}），{skill_score}分")
                    else:
                        cert_reason.append(f"{skill_str}职业技能，{skill_score}分")
                if cert_reason:
                    reasons.append(f"认证得分（20%）：{'; '.join(cert_reason)}，转换后+{certification_score:.1f}分")
            
            # 3. 专家聘任加分
            if prof_ability.is_chief_expert:
                expert_bonus = 25
                reasons.append("为首席专家，+25分")
            elif prof_ability.is_senior_expert:
                expert_bonus = 20
                reasons.append("为高级专家，+20分")
            elif prof_ability.is_company_expert:
                expert_bonus = 15
                reasons.append("为公司专家，+15分")
        else:
            reasons.append("暂无专业能力数据")
        
        # 计算最终得分
        # 绩效得分（占比80%） + 认证得分（占比20%） + 专家聘任加分
        score = performance_score * 0.8 + certification_score + expert_bonus
        
        # 确保分数在0-100之间
        score = max(0, min(100, score))

        if len(reasons) == 1:
            employee_reason = ";".join(reasons) + f"近3年绩效都是称职，无任何加分项,最终得分{score:.1f}分"
        else:
            employee_reason = "；".join(reasons) + f",最终得分{score:.1f}分"
        
        # 基于岗位说明书确定岗位要求
        qual_skills = job_desc.get('qualifications_skills') if job_desc else None
        
        job_requirement = 75
        job_reason_parts = []
        
        # 分析专业技能要求
        if qual_skills:
            skills_str = str(qual_skills)
            if any(kw in skills_str for kw in ['精通', '高级', '资深']):
                job_requirement = 85
                job_reason_parts.append("需精通专业技能")
            elif any(kw in skills_str for kw in ['熟练', '掌握']):
                job_requirement = 75
                job_reason_parts.append("需熟练掌握技能")
            else:
                job_requirement = 70
                job_reason_parts.append("需具备基础技能")
        else:
            job_reason_parts.append("需具备岗位技能")
        
        # 精简岗位理由
        job_reason = f"要求：{ '，'.join(job_reason_parts) }，标准分{job_requirement}分"
        
        return score, job_requirement, employee_reason, job_reason
    
    # 测试每个用例
    results = []
    for i, test_case in enumerate(test_cases):
        print(f"\n=== 测试用例 {i+1}: {test_case['name']} ===")
        
        emp_info = {"emp_code": "test_emp"}
        job_desc = {}
        
        try:
            score, job_requirement, employee_reason, job_reason = calculate_professional_ability_score(emp_info, job_desc, None)
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
    
    return results

def test_experience_score():
    """
    测试经验维度得分计算
    """
    print("\n经验维度得分计算测试")
    print("=" * 50)
    
    # 测试用例
    test_cases = [
        {
            "name": "测试用例1: 3年工作经验",
            "work_years": 3,
            "honors": []
        },
        {
            "name": "测试用例2: 6年工作经验 + 公司级荣誉",
            "work_years": 6,
            "honors": [
                {"honor_level": "公司", "honor_name": "优秀员工"}
            ]
        },
        {
            "name": "测试用例3: 10年工作经验 + 国家级荣誉",
            "work_years": 10,
            "honors": [
                {"honor_level": "国家", "honor_name": "国家科技进步奖"}
            ]
        }
    ]
    
    # 模拟计算函数
    def calculate_experience_score(emp_info, job_desc, db):
        """
        计算经验维度得分（权重10%）
        基于：从事本专业或相关专业的工作年限
        """
        experience_dict = {'work_experiences': 0.8, 'honer': 0.8}
        
        relevant_years = emp_info.get('work_years', 0)
        total_years = relevant_years
        
        # 根据相关专业年限计算分数
        if relevant_years >= 10:
            score = 100
            level = "10年以上"
        elif relevant_years >= 8:
            score = 90
            level = "8-10年"
        elif relevant_years >= 5:
            score = 80
            level = "5-8年"
        elif relevant_years >= 3:
            score = 70
            level = "3-5年"
        else:
            score = 60
            level = "3年以下"
        work_score = score * experience_dict['work_experiences']
        
        # 2. 计算荣誉奖项得分
        honor_score = 0
        honor_reasons = []
        
        honors = emp_info.get('honors', [])
        if honors:
            for honor in honors:
                if isinstance(honor, dict):
                    honor_level = honor.get('honor_level', '')
                    honor_name = honor.get('honor_name', '')
                    
                    # 根据荣誉级别计算得分
                    if '国家' in honor_level:
                        points = 100
                        level_name = '国家级'
                    elif '省部' in honor_level or '省级' in honor_level or '部级' in honor_level:
                        points = 75
                        level_name = '省部级'
                    elif '集团' in honor_level:
                        points = 50
                        level_name = '集团级'
                    elif '公司' in honor_level:
                        points = 25
                        level_name = '公司级'
                    else:
                        points = 25
                        level_name = '其他'
                    points = experience_dict.get('honer', 0.8) * points
                    honor_score += points
                    honor_reasons.append(f"{honor_name}({level_name}+{points}分)")
        
        # 荣誉得分最高不超过10分
        honor_score = min(honor_score, 40)
        
        # 3. 汇总得分
        total_score = work_score + honor_score
        
        # 构建员工得分理由
        employee_reason = f"相关专业工作年限{relevant_years:.1f}年（{level}），按照年限得分{work_score}分"
        
        # 添加荣誉奖项理由
        if honor_reasons:
            employee_reason += f"；荣誉奖项：{'、'.join(honor_reasons[:3])}，荣誉加分{honor_score}分"
        
        # 基于岗位说明书确定经验要求
        job_requirement = 75  # 默认要求3-5年
        job_reason = f"要求：3-5年本专业工作经验，标准分{job_requirement}分"
        
        return total_score, job_requirement, employee_reason, job_reason
    
    # 测试每个用例
    results = []
    for i, test_case in enumerate(test_cases):
        print(f"\n=== 测试用例 {i+1}: {test_case['name']} ===")
        
        emp_info = {
            "emp_code": "test_emp",
            "work_years": test_case['work_years'],
            "honors": test_case['honors']
        }
        job_desc = {}
        
        try:
            score, job_requirement, employee_reason, job_reason = calculate_experience_score(emp_info, job_desc, None)
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
    
    return results

def test_overall_alignment():
    """
    测试整体人岗适配性计算
    """
    print("\n整体人岗适配性计算测试")
    print("=" * 50)
    
    # 模拟员工数据
    employee_data = {
        "name": "张三",
        "code": "EMP001",
        "department": "技术部",
        "position": "软件工程师",
        "work_years": 5,
        "education": "本科",
        "highest_degree": "学士",
        "school": "北京大学",
        "school_type": "985"
    }
    
    # 模拟岗位描述
    job_desc = {
        "position_name": "软件工程师",
        "department": "技术部",
        "qualifications_skills": "熟练掌握Python、Java等编程语言",
        "qualifications_education": "本科及以上学历",
        "qualifications_job_work_experience": "3年以上相关工作经验"
    }
    
    # 模拟各维度得分
    dimensions = [
        {
            "name": "专业能力",
            "score": 85.5,
            "weight": 0.3,
            "job_requirement": 80,
            "description": "基于绩效、职称证书、职业技能、专家聘任",
            "employee_reason": "绩效基础分70分，试用期考核85分+10分，认证得分+5分，最终得分85.5分",
            "job_reason": "要求：需熟练掌握技能，标准分80分"
        },
        {
            "name": "经验",
            "score": 72.0,
            "weight": 0.1,
            "job_requirement": 75,
            "description": "基于工作年限和荣誉",
            "employee_reason": "相关专业工作年限5.0年（5-8年），按照年限得分72.0分",
            "job_reason": "要求：3-5年本专业工作经验，标准分75分"
        },
        {
            "name": "创新能力",
            "score": 60.0,
            "weight": 0.1,
            "job_requirement": 70,
            "description": "基于专利",
            "employee_reason": "无专利，得分60分",
            "job_reason": "该岗位对创新能力的基础要求，标准分70分"
        },
        {
            "name": "学习能力",
            "score": 85.0,
            "weight": 0.2,
            "job_requirement": 60,
            "description": "基于学历和专业匹配",
            "employee_reason": "本科学历,基础分为60；毕业学校为本科,为985,加分20；最终得分85.0分",
            "job_reason": "要求：本科及以上学历，标准分60分"
        },
        {
            "name": "工作态度",
            "score": 75.0,
            "weight": 0.2,
            "job_requirement": 70,
            "description": "基于考勤数据",
            "employee_reason": "基础分70分；月平均加班10小时，+5分；最终得分75.0分",
            "job_reason": "要求：遵守考勤纪律，积极主动，标准分70分"
        }
    ]
    
    # 计算加权综合得分
    overall_score = sum(dim['score'] * dim['weight'] for dim in dimensions)
    job_requirement_score = sum(dim['job_requirement'] * dim['weight'] for dim in dimensions)
    
    print(f"员工: {employee_data['name']} ({employee_data['position']})")
    print(f"综合得分: {overall_score:.1f}分 (岗位要求: {job_requirement_score:.1f}分)")
    
    # 生成结论
    if overall_score >= 90:
        conclusion = f"该员工与岗位高度匹配，综合得分{overall_score:.1f}分（岗位要求{job_requirement_score:.1f}分）。建议重点培养。"
        evaluation = "优秀"
    elif overall_score >= 80:
        conclusion = f"该员工与岗位匹配度良好，综合得分{overall_score:.1f}分（岗位要求{job_requirement_score:.1f}分）。整体表现良好。"
        evaluation = "良好"
    elif overall_score >= 60:
        conclusion = f"该员工基本符合岗位要求，综合得分{overall_score:.1f}分（岗位要求{job_requirement_score:.1f}分）。建议持续提升。"
        evaluation = "合格"
    else:
        conclusion = f"该员工与岗位匹配度较低，综合得分{overall_score:.1f}分（岗位要求{job_requirement_score:.1f}分）。建议调整岗位或加强培训。"
        evaluation = "待提升"
    
    print(f"评价: {evaluation}")
    print(f"结论: {conclusion}")
    
    return {
        "employee": employee_data,
        "overall_score": overall_score,
        "job_requirement_score": job_requirement_score,
        "evaluation": evaluation,
        "conclusion": conclusion,
        "dimensions": dimensions
    }

def main():
    """
    主函数
    """
    print("人岗适配性测试脚本")
    print("=" * 60)
    
    # 测试专业能力得分
    prof_results = test_professional_ability_score()
    
    # 测试经验得分
    exp_results = test_experience_score()
    
    # 测试整体适配性
    overall_result = test_overall_alignment()
    
    # 汇总结果
    all_results = {
        "professional_ability_tests": prof_results,
        "experience_tests": exp_results,
        "overall_alignment": overall_result,
        "timestamp": datetime.now().isoformat()
    }
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"alignment_simple_test_results_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n测试结果已保存到: {output_file}")
    print("\n测试完成！")


if __name__ == "__main__":
    main()
