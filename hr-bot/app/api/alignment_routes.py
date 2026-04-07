"""
人岗适配分析API
基于5维度模型进行员工与岗位的匹配度分析
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional, Dict
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging
import os
import uuid
import asyncio

router = APIRouter(prefix="/api/v1/alignment", tags=["人岗适配分析"])

logger = logging.getLogger(__name__)

# 创新能力文件上传目录（延迟初始化）
INNOVATION_UPLOAD_DIR = None

def get_innovation_upload_dir():
    """获取创新能力文件上传目录，如果不存在则创建"""
    global INNOVATION_UPLOAD_DIR
    if INNOVATION_UPLOAD_DIR is None:
        # 获取项目根目录（假设当前文件在 app/api/ 目录下）
        current_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = os.path.dirname(current_dir)
        project_dir = os.path.dirname(app_dir)
        INNOVATION_UPLOAD_DIR = os.path.join(project_dir, "data", "innovation_files")
        os.makedirs(INNOVATION_UPLOAD_DIR, exist_ok=True)
    return INNOVATION_UPLOAD_DIR

# MySQL数据库配置
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_DATABASE = "hr_employee_db"
MYSQL_USER = "hr_user"
MYSQL_PASSWORD = "hr_password"
MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# 创建数据库引擎
engine = create_engine(MYSQL_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class AlignmentAnalyzeRequest(BaseModel):
    """人岗适配分析请求"""
    employee_name: str
    position_name: Optional[str] = None
    innovation_audio_file: Optional[str] = None  # 创新能力评估录音文件路径（wav/mp3）
    innovation_questions_file: Optional[str] = None  # 创新能力评估提问问题Excel文件路径


class DimensionScore(BaseModel):
    """维度评分"""
    name: str
    score: float
    weight: float
    job_requirement: float
    description: str
    employee_reason: str  # 员工该维度得分的详细理由
    job_reason: str  # 岗位该维度要求的详细理由


class AlignmentAnalyzeResponse(BaseModel):
    """人岗适配分析响应"""
    success: bool
    employee_name: str
    employee_code: Optional[str]
    department: Optional[str]
    position: Optional[str]
    overall_score: float
    job_requirement_score: float  # 岗位要求的综合得分
    dimensions: List[DimensionScore]
    attendance: Optional[Dict]
    conclusion: str
    evaluation: str
    recommendations: List[str]
    quadrant: Optional[Dict]  # 四象限图数据
    radar_data: Optional[Dict]  # 雷达图数据
    gap_analysis: Optional[List[Dict]]  # 差距分析


def get_employee_info(db, emp_name: str):
    """从MySQL获取员工信息"""
    sql = text("""
        SELECT emp_code, emp_name, dept_level1, dept_level2, position_name,
               highest_education, highest_degree, highest_degree_school, highest_degree_school_type,
               entry_date, job_level, work_years, company_years, contract_end_date
        FROM emp_roster
        WHERE emp_name LIKE :emp_name
        LIMIT 1
    """)
    result = db.execute(sql, {'emp_name': f'%{emp_name}%'})
    row = result.fetchone()
    if row:
        return {
            'emp_code': row.emp_code,
            'emp_name': row.emp_name,
            'department': f"{row.dept_level1 or ''} {row.dept_level2 or ''}".strip(),
            'position': row.position_name,
            'education': row.highest_education,
            'highest_degree': row.highest_degree,
            'school': row.highest_degree_school,
            'school_type': row.highest_degree_school_type,
            'entry_date': row.entry_date,
            'job_level': row.job_level,
            'work_years': row.work_years,
            'company_years': row.company_years,
            'contract_end_date': row.contract_end_date
        }
    return None


def get_job_description(db, position_name: str, emp_name: str = None):
    """从MySQL获取岗位描述"""
    if emp_name:
        # 优先根据员工姓名查询岗位信息
        sql = text("""
            SELECT position_name, department, position_purpose,
                   duties_and_responsibilities, 
                   qualifications_education, qualifications_major,
                   qualifications_job_work_experience, 
                   qualifications_required_professional_certification,
                   qualifications_skills, qualifications_others,
                   kpis
            FROM ods_emp_job_description
            WHERE emp_name = :emp_name
            LIMIT 1
        """)
        result = db.execute(sql, {'emp_name': emp_name})
        row = result.fetchone()
        if row:
            return {
                'position_name': row.position_name,
                'department': row.department,
                'position_purpose': row.position_purpose,
                'duties': row.duties_and_responsibilities,
                'qualifications_education': row.qualifications_education,
                'qualifications_major': row.qualifications_major,
                'qualifications_job_work_experience': row.qualifications_job_work_experience,
                'qualifications_cert': row.qualifications_required_professional_certification,
                'qualifications_skills': row.qualifications_skills,
                'qualifications_others': row.qualifications_others,
                'kpis': row.kpis
            }
    
    # 如果没有提供员工姓名，或者根据员工姓名没有找到岗位信息，再根据岗位名称查询
    if position_name:
        sql = text("""
            SELECT position_name, department, position_purpose,
                   duties_and_responsibilities, 
                   qualifications_education, qualifications_major,
                   qualifications_job_work_experience, 
                   qualifications_required_professional_certification,
                   qualifications_skills, qualifications_others,
                   kpis
            FROM ods_emp_job_description
            WHERE position_name LIKE :position_name
            LIMIT 1
        """)
        result = db.execute(sql, {'position_name': f'%{position_name}%'})
        row = result.fetchone()
        if row:
            return {
                'position_name': row.position_name,
                'department': row.department,
                'position_purpose': row.position_purpose,
                'duties': row.duties_and_responsibilities,
                'qualifications_education': row.qualifications_education,
                'qualifications_major': row.qualifications_major,
                'qualifications_job_work_experience': row.qualifications_job_work_experience,
                'qualifications_cert': row.qualifications_required_professional_certification,
                'qualifications_skills': row.qualifications_skills,
                'qualifications_others': row.qualifications_others,
                'kpis': row.kpis
            }
    return None


def get_attendance_summary(db, emp_code: str):
    """从MySQL获取考勤汇总数据"""
    sql = text("""
        SELECT 
            avg(normal_attendance_days) as total_normal_days,
            avg(expected_attendance_days) as total_expected_days,
            avg(late_count) as total_late,
            avg(early_leave_count) as total_early_leave,
            avg(leave_count) as total_leave,
            avg(outing_count) as total_outing,
            avg(overtime_count) as total_overtime,
            avg(overtime_hours) as total_overtime_hours
        FROM ods_attendance_summary
        WHERE emp_code = :emp_code
        AND normal_attendance_days>0 
    """)
    result = db.execute(sql, {'emp_code': emp_code})
    row = result.fetchone()
    if row:
        return {
            'normal_days': float(row.total_normal_days or 0),
            'expected_days': float(row.total_expected_days or 0),
            'late_count': row.total_late or 0,
            'early_leave_count': row.total_early_leave or 0,
            'leave_count': row.total_leave or 0,
            'outing_count': row.total_outing or 0,
            'overtime_count': row.total_overtime or 0,
            'overtime_hours': float(row.total_overtime_hours or 0)
        }
    return None


def calculate_professional_ability_score(emp_info: dict, job_desc: dict, db) -> tuple:
    """
    计算专业能力维度得分（权重30%）
    区分三种员工类型：
    1. 试用期员工（入职≤6个月）：按试用期规则
    2. 合同到期员工（即将合同到期）：按合同到期规则
    3. 普通正式员工：按普通规则
    """
    from app.models.emp_professional_ability import EmpProfessionalAbility
    from datetime import datetime, date
    
    emp_code = emp_info.get('emp_code')
    entry_date = emp_info.get('entry_date')
    contract_end_date = emp_info.get('contract_end_date')
    
    # 判断员工类型
    is_probation = False
    is_contract_expiring = False
    today = date.today()
    
    # 判断是否为试用期员工（入职≤6个月）
    if entry_date:
        if isinstance(entry_date, str):
            try:
                entry_date = datetime.strptime(entry_date, '%Y-%m-%d').date()
            except:
                try:
                    entry_date = datetime.strptime(entry_date, '%Y-%m-%d %H:%M:%S').date()
                except:
                    entry_date = None
        if isinstance(entry_date, date):
            months_since_entry = (today.year - entry_date.year) * 12 + (today.month - entry_date.month)
            if today.day < entry_date.day:
                months_since_entry -= 1
            is_probation = months_since_entry <= 6
    
    # 判断是否为合同到期员工（合同终止日期在3个月内）
    if contract_end_date:
        if isinstance(contract_end_date, str):
            try:
                contract_end_date = datetime.strptime(contract_end_date, '%Y-%m-%d').date()
            except:
                try:
                    contract_end_date = datetime.strptime(contract_end_date, '%Y-%m-%d %H:%M:%S').date()
                except:
                    contract_end_date = None
        if isinstance(contract_end_date, date):
            days_to_end = (contract_end_date - today).days
            is_contract_expiring = 0 <= days_to_end <= 90  # 3个月内到期
    
    # 从数据库获取员工专业能力数据
    prof_ability = None
    if db and emp_code:
        prof_ability = db.query(EmpProfessionalAbility).filter(
            EmpProfessionalAbility.emp_code == emp_code
        ).first()
    
    # 根据员工类型选择计算逻辑
    if is_probation:
        # 试用期员工逻辑
        return _calculate_professional_ability_probation(emp_info, prof_ability, job_desc)
    elif is_contract_expiring:
        # 合同到期员工逻辑
        return _calculate_professional_ability_contract_expiring(emp_info, prof_ability, job_desc, db, emp_code)
    else:
        # 普通正式员工逻辑
        return _calculate_professional_ability_regular(emp_info, prof_ability, job_desc, db, emp_code)


def _calculate_professional_ability_probation(emp_info: dict, prof_ability, job_desc: dict) -> tuple:
    """
    试用期员工（入职≤6个月）专业能力计算
    规则（第二个图片）：
    - 基础分70分
    - 绩效：试用期考核分数，90≤得分+15分，80≤得分<90+10分，60≤得分<80+0分，得分<60不予录用
    - 职称证书：A:10分、B:7分、C:5分，多项取高
    - 职业技能：A:7分、B:5分、C:3分，累计不超过14分
    """
    score = 70  # 基础分70分
    reasons = ["基础分70分"]
    
    if prof_ability:
        # 1. 试用期绩效
        performance_bonus = 0
        performance_reason = ""
        
        if prof_ability.probation_score is not None:
            probation_score = float(prof_ability.probation_score)
            if probation_score >= 90:
                performance_bonus = 15
                performance_reason = f"试用期考核{probation_score}分≥90分，+15分"
            elif probation_score >= 80:
                performance_bonus = 10
                performance_reason = f"试用期考核{probation_score}分≥80分，+10分"
            elif probation_score >= 60:
                performance_bonus = 0
                performance_reason = f"试用期考核{probation_score}分≥60分，+0分"
            else:
                performance_bonus = -100  # 不予录用，直接0分
                performance_reason = f"试用期考核{probation_score}分<60分，不予录用"
        else:
            performance_reason = "暂无试用期考核分数"
        
        if performance_bonus != 0:
            score += performance_bonus
            reasons.append(performance_reason)
        else:
            reasons.append(performance_reason)
        
        # 2. 职称证书（多项取高）
        title_bonus = 0
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
                        title_bonus = max(title_bonus, 10)
                    elif level == 'B':
                        title_bonus = max(title_bonus, 7)
                    elif level == 'C':
                        title_bonus = max(title_bonus, 5)
        
        if title_bonus > 0:
            score += title_bonus
            if title_count > 1:
                reasons.append(f"获得{title_count}项职称，取高+{title_bonus}分")
            else:
                reasons.append(f"获得{title_str}职称，+{title_bonus}分")
        
        # 3. 职业技能（累计不超过14分）
        skill_bonus = 0
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
                        skill_bonus += 7
                    elif level == 'B':
                        skill_bonus += 5
                    elif level == 'C':
                        skill_bonus += 3
        
        skill_bonus = min(skill_bonus, 14)  # 不超过14分
        if skill_bonus > 0:
            score += skill_bonus
            if skill_count > 1:
                reasons.append(f"获得{skill_count}项职业技能，累计+{skill_bonus}分（上限14分）")
            else:
                reasons.append(f"获得{skill_name}职业技能，+{skill_bonus}分")
    else:
        reasons.append("暂无专业能力数据")
    
    # 试用期员工不予录用则直接0分
    if score <= 0:
        score = 0
        employee_reason = "试用期考核不合格，不予录用"
    else:
        score = min(score, 100)
        employee_reason = "；".join(reasons) + f"，最终得分{score}分"
    
    # 岗位侧要求
    job_requirement = 75
    job_reason = "要求：具备岗位所需专业技能，标准分75分"
    
    return score, job_requirement, employee_reason, job_reason


def _calculate_professional_ability_contract_expiring(emp_info: dict, prof_ability, job_desc: dict, db, emp_code) -> tuple:
    """
    合同到期员工（即将合同到期）专业能力计算
    规则（第一个图片）：
    - 基础分70分
    - 绩效：近3年内年度绩效，一次"优秀"+15分，一次"基本称职"-15分，连续3年"称职"的-5分
    - 职称证书：A:10分、B:7分、C:5分，多项取高
    - 职业技能：A:7分、B:5分、C:3分，累计不超过14分
    """
    score = 70  # 基础分70分
    reasons = ["基础分70分"]
    
    if prof_ability:
        # 1. 绩效计算（近3年年度绩效）
        performance_bonus = 0
        performance_reason = ""
        
        if prof_ability.performance_history:
            perf_history = prof_ability.performance_history
            if isinstance(perf_history, list):
                excellent_count = 0
                basic_count = 0
                # 收集近3年的绩效记录，按年份排序
                valid_years = ['2022', '2023', '2024', '2025']
                year_performance = {}  # 存储每年的绩效等级
                
                for perf in perf_history:
                    year = str(perf.get('year', ''))
                    if year in valid_years:
                        level = str(perf.get('level', '')).lower()
                        # 标准化绩效等级
                        if '优秀' in level or 'a' in level or 'p1' in level:
                            year_performance[year] = 'excellent'
                            excellent_count += 1
                        elif '基本称职' in level or 'c' in level:
                            year_performance[year] = 'basic'
                            basic_count += 1
                        elif '称职' in level or 'b' in level or 'p2' in level:
                            year_performance[year] = 'competent'
                
                # 计算绩效加分/扣分
                if excellent_count > 0:
                    performance_bonus += 15 * excellent_count
                    performance_reason += f"{excellent_count}次年度绩效优秀+{15 * excellent_count}分；"
                
                if basic_count > 0:
                    performance_bonus -= 15 * basic_count
                    performance_reason += f"{basic_count}次年度绩效基本称职-{15 * basic_count}分；"
                
                # 判断是否有连续3年称职（需要检查2022、2023、2024或2023、2024、2025）
                # 连续3年称职指的是连续的三个年份都是称职
                consecutive_competent = False
                # 检查 2022-2023-2024
                if (year_performance.get('2022') == 'competent' and 
                    year_performance.get('2023') == 'competent' and 
                    year_performance.get('2024') == 'competent'):
                    consecutive_competent = True
                # 检查 2023-2024-2025
                elif (year_performance.get('2023') == 'competent' and 
                      year_performance.get('2024') == 'competent' and 
                      year_performance.get('2025') == 'competent'):
                    consecutive_competent = True

                if consecutive_competent:
                    # performance_bonus -= 5
                    performance_reason += "连续3年称职不加分；"
        
        if performance_bonus != 0:
            score += performance_bonus
            reasons.append(performance_reason.rstrip('；'))
        
        # 2. 职称证书（多项取高）
        title_bonus = 0
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
                        title_bonus = max(title_bonus, 10)
                    elif level == 'B':
                        title_bonus = max(title_bonus, 7)
                    elif level == 'C':
                        title_bonus = max(title_bonus, 5)
        
        if title_bonus > 0:
            score += title_bonus
            if title_count > 1:
                reasons.append(f"获得{title_count}项职称，取高+{title_bonus}分")
            else:
                reasons.append(f"获得{title_str}职称，+{title_bonus}分")
        
        # 3. 职业技能（累计不超过14分）
        skill_bonus = 0
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
                        skill_bonus += 7
                    elif level == 'B':
                        skill_bonus += 5
                    elif level == 'C':
                        skill_bonus += 3
        
        skill_bonus = min(skill_bonus, 14)  # 不超过14分
        if skill_bonus > 0:
            score += skill_bonus
            if skill_count > 1:
                reasons.append(f"获得{skill_count}项职业技能，累计+{skill_bonus}分（上限14分）")
            else:
                reasons.append(f"获得{skill_name}职业技能，+{skill_bonus}分")
    else:
        reasons.append("暂无专业能力数据")
    
    score = min(score, 100)
    employee_reason = "；".join(reasons) + f"，最终得分{score}分"
    
    # 岗位侧要求
    job_requirement = 75
    job_reason = "要求：具备岗位所需专业技能，标准分75分"
    
    return score, job_requirement, employee_reason, job_reason


def _calculate_professional_ability_regular(emp_info: dict, prof_ability, job_desc: dict, db, emp_code) -> tuple:
    """
    普通正式员工专业能力计算（原有逻辑）
    """
    from app.models.emp_professional_ability import EmpProfessionalAbility
    
    score = 70  # 基础分70分
    reasons = ["基础分70分"]
    
    if prof_ability:
        # 1. 绩效计算（二选一）
        performance_bonus = 0
        performance_reason = ""
        
        # 选项1：试用期分数
        if prof_ability.probation_score is not None:
            if float(prof_ability.probation_score) >= 80:
                performance_bonus = 10
                performance_reason = f"试用期考核{prof_ability.probation_score}分≥80分，+10分"
            else:
                performance_bonus = -5
                performance_reason = f"试用期考核{prof_ability.probation_score}分<80分，-5分"
        
        # 选项2：3年内年度绩效（2023、2024、2025年）
        elif prof_ability.performance_history:
            perf_history = prof_ability.performance_history
            if isinstance(perf_history, list):
                excellent_count = 0
                basic_count = 0
                competent_count = 0
                # 只统计2023、2024、2025年的绩效
                valid_years = ['2023', '2024', '2022']
                year_performance = {}  # 存储每年的绩效等级
                
                for perf in perf_history:
                    year = str(perf.get('year', ''))
                    if year in valid_years:
                        level = str(perf.get('level', '')).lower()
                        if '优秀' in level or 'a' in level or 'p1' in level:
                            excellent_count += 1
                            year_performance[year] = 'excellent'
                        elif '基本称职' in level or 'c' in level:
                            basic_count += 1
                            year_performance[year] = 'basic'
                        elif '称职' in level or 'b' in level or 'p2' in level:
                            competent_count += 1
                            year_performance[year] = 'competent'
                
                # 计算优秀和基本称职的加减分
                if excellent_count > 0:
                    performance_bonus = 15 * excellent_count
                    performance_reason = f"2022-2025年{excellent_count}次年度绩效优秀，+{performance_bonus}分"
                
                if basic_count > 0:
                    performance_bonus += -10 * basic_count
                    if performance_reason:
                        performance_reason += f"；{basic_count}次年度绩效基本称职，{-10 * basic_count}分"
                    else:
                        performance_reason = f"2022-2025年{basic_count}次年度绩效基本称职，{-10 * basic_count}分"
                
                # 【新增】判断是否有连续3年称职（需要检查2022、2023、2024或2023、2024、2025）
                # 注意：这个扣分独立于优秀/基本称职的计算，只要连续3年称职就扣分
                consecutive_competent = False
                # 检查 2022-2023-2024
                if (year_performance.get('2022') == 'competent' and 
                    year_performance.get('2023') == 'competent' and 
                    year_performance.get('2024') == 'competent'):
                    consecutive_competent = True
                # 检查 2023-2024-2025
                elif (year_performance.get('2023') == 'competent' and 
                      year_performance.get('2024') == 'competent' and 
                      year_performance.get('2025') == 'competent'):
                    consecutive_competent = True
                
                if consecutive_competent:
                    performance_bonus -= 5
                    if performance_reason:
                        performance_reason += "；连续3年称职-5分"
                    else:
                        performance_reason = "连续3年称职-5分"
        
        if performance_bonus != 0:
            score += performance_bonus
            reasons.append(performance_reason)
        
        # 2. 专家聘任（最高20分）
        expert_bonus = 0
        expert_reason = ""
        if prof_ability.is_chief_expert:
            expert_bonus = 20
            expert_reason = "为首席专家，+20分"
        elif prof_ability.is_senior_expert:
            expert_bonus = 15
            expert_reason = "为高级专家，+15分"
        elif prof_ability.is_company_expert:
            expert_bonus = 10
            expert_reason = "为公司专家，+10分"
        
        if expert_bonus > 0:
            score += expert_bonus
            reasons.append(expert_reason)
        
        # 3. 职称证书（多项取高）
        title_bonus = 0
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
                        title_bonus = max(title_bonus, 10)
                    elif level == 'B':
                        title_bonus = max(title_bonus, 7)
                    elif level == 'C':
                        title_bonus = max(title_bonus, 5)
        
        if title_bonus > 0:
            score += title_bonus
            if title_count > 1:
                reasons.append(f"获得{title_count}项职称，有{title_str},累积+{title_bonus}分")
            else:
                reasons.append(f"获得{title_str}职称，+{title_bonus}分")
        
        # 4. 职业技能（累计不超过14分）
        skill_bonus = 0
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
                        skill_bonus += 7
                    elif level == 'B':
                        skill_bonus += 5
                    elif level == 'C':
                        skill_bonus += 3
        
        skill_bonus = min(skill_bonus, 14)  # 不超过14分
        if skill_bonus > 0:
            score += skill_bonus
            if skill_count > 1:
                reasons.append(f"获得{skill_count}项职业技能，包括{skill_str},累积+{skill_bonus}分（上限14分）")
            else:
                reasons.append(f"获得{skill_name}职业技能，+{skill_bonus}分（上限14分）")
    else:
        reasons.append("暂无专业能力数据")
    
    score = min(score, 100)
    
    if len(reasons) == 1:
        employee_reason = ";".join(reasons) + f"近3年绩效都是称职，无任何加分项,最终得分{score}分"
    else:
        employee_reason = "；".join(reasons) + f",最终得分{score}分"
    
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


def check_work_experience_relevance_with_llm(work_experiences: list, job_desc: dict, emp_info: dict) -> list:
    """
    使用大模型判断工作经历是否与当前岗位相关
    
    Args:
        work_experiences: 工作经历列表
        job_desc: 岗位描述
        emp_info: 员工信息
    
    Returns:
        相关经历的索引列表
    """
    import requests
    import json
    from app.config import get_settings
    
    settings = get_settings()
    
    if not work_experiences:
        return []
    
    # 构建提示词
    position_name = job_desc.get('position_name', '当前岗位') if job_desc else '当前岗位'
    position_duties = job_desc.get('duties', '') if job_desc else ''
    position_skills = job_desc.get('qualifications_skills', '') if job_desc else ''
    
    # 构建工作经历文本
    exp_texts = []
    for idx, exp in enumerate(work_experiences):
        exp_text = f"{idx + 1}. {exp.get('company_name', '')} - {exp.get('position', '')}"
        if exp.get('department'):
            exp_text += f" ({exp.get('department')})"
        exp_texts.append(exp_text)
    
    prompt = f"""请判断以下工作经历是否与目标岗位相关。

目标岗位：{position_name}
岗位职责：{position_duties}
技能要求：{position_skills}

工作经历列表：
{chr(10).join(exp_texts)}

请分析每条工作经历是否与目标岗位相关，返回相关经历的序号（从1开始）。
只返回序号列表，格式如：[1, 3, 5]

判断标准：
1. 职位名称、工作内容与目标岗位相同或相近
2. 使用的技术栈、技能与目标岗位要求匹配
3. 行业领域与目标岗位相关

请只返回JSON数组格式，不要其他解释。"""

    try:
        # 调用远程大模型API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.remote_llm_api_key}"
        }
        
        payload = {
            "model": settings.remote_llm_model,
            "messages": [
                {"role": "system", "content": "你是一个专业的人力资源助手，擅长判断工作经历与岗位的匹配度。请只返回JSON数组格式。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        response = requests.post(
            settings.remote_llm_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        # 解析大模型返回的结果
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        # 尝试从返回内容中提取JSON数组
        import re
        # 查找方括号包围的内容
        match = re.search(r'\[([\d,\s]*)\]', content)
        if match:
            indices_str = match.group(1)
            # 解析序号列表（从1开始，需要转换为从0开始）
            relevant_indices = [int(x.strip()) - 1 for x in indices_str.split(',') if x.strip().isdigit()]
            return relevant_indices
        
        # 如果没有找到数组格式，尝试逐行解析
        relevant_indices = []
        for line in content.split('\n'):
            line = line.strip()
            # 查找数字
            numbers = re.findall(r'\d+', line)
            for num in numbers:
                idx = int(num) - 1  # 转换为从0开始的索引
                if idx >= 0 and idx not in relevant_indices:
                    relevant_indices.append(idx)
        
        return relevant_indices
        
    except Exception as e:
        logger.error(f"[Experience] 大模型判断工作经历相关性失败: {e}")
        # 如果大模型调用失败，返回空列表，后续使用备用逻辑
        return []


def calculate_experience_score(emp_info: dict, job_desc: dict, db) -> tuple:
    """
    计算经验维度得分（权重10%）
    基于附件要求：
    1. 工作履历（占比80%）：按照岗位说明书要求的工作年限赋分，满足得满分，不满足按比例折算
    2. 荣誉奖项（占比20%）：
       - 国家级荣誉：100分
       - 省部级荣誉：75分
       - 集团级荣誉：50分
       - 公司级荣誉：25分
    
    岗位侧固定80分，并写明需要几年什么方面的工作经验
    """
    from datetime import datetime, date
    from app.models.emp_work_experience import EmpWorkExperience
    
    emp_code = emp_info.get('emp_code')
    current_position = emp_info.get('position', '')
    
    # ========== 1. 解析岗位要求（从岗位说明书）==========
    # 默认要求5年相关经验
    required_years = 5
    required_experience_type = "本专业或相关专业"
    
    if job_desc:
        qual_exp = job_desc.get('qualifications_job_work_experience', '')
        if qual_exp:
            import re
            # 提取年限要求
            years_match = re.search(r'(\d+)', str(qual_exp))
            if years_match:
                required_years = int(years_match.group(1))
            # 提取经验类型要求
            if '相关' in str(qual_exp):
                required_experience_type = "相关专业"
            elif '本' in str(qual_exp):
                required_experience_type = "本专业"
        
        # 从岗位名称、职责中提取专业方向
        position_name = job_desc.get('position_name', '')
        duties = job_desc.get('duties', '')
        if position_name:
            required_experience_type = f"{position_name}相关"
    
    # 岗位侧固定80分，写明具体要求
    job_requirement = 80.0
    job_reason = f"要求{required_years}年{required_experience_type}工作经验，标准分80分"
    
    # ========== 2. 计算员工工作履历得分（占比80%）==========
    # 从岗位描述中提取相关关键词
    related_keywords = []
    if job_desc:
        position_name = job_desc.get('position_name', '')
        duties = job_desc.get('duties', '')
        skills = job_desc.get('qualifications_skills', '')
        
        all_text = f"{position_name} {duties} {skills}".lower()
        
        tech_keywords = [
            'java', 'python', '前端', '后端', '开发', '工程师', '架构', '测试',
            '运维', '产品', '设计', '运营', '销售', '市场', '人力', '财务',
            'h5', 'web', 'app', '小程序', '大数据', 'ai', '人工智能', '算法',
            '数据库', '网络', '安全', '云计算', 'devops', '敏捷', '项目管理',
            '经营分析', '数据分析', '财务管理', '人力资源', '运营管理'
        ]
        
        for keyword in tech_keywords:
            if keyword in all_text:
                related_keywords.append(keyword)
    
    if not related_keywords and current_position:
        related_keywords = [current_position.lower()]
    
    # 查询员工工作经历
    relevant_years = 0.0
    total_years = 0.0
    relevant_experiences = []
    
    if db and emp_code:
        work_experiences = db.query(EmpWorkExperience).filter(
            EmpWorkExperience.emp_code == emp_code
        ).order_by(EmpWorkExperience.start_date.desc()).all()
        
        today = date.today()
        
        # 将工作经历转换为字典列表，用于大模型判断
        exp_dict_list = []
        for exp in work_experiences:
            if exp.start_date:
                exp_dict_list.append({
                    'company_name': exp.company_name,
                    'position': exp.position,
                    'department': exp.department,
                    'start_date': exp.start_date,
                    'end_date': exp.end_date
                })
        
        # 使用大模型判断哪些工作经历与当前岗位相关
        llm_relevant_indices = []
        if exp_dict_list and job_desc:
            logger.info(f"[Experience] 使用大模型判断工作经历相关性，员工: {emp_code}")
            llm_relevant_indices = check_work_experience_relevance_with_llm(
                exp_dict_list, job_desc, emp_info
            )
            logger.info(f"[Experience] 大模型判断相关经历索引: {llm_relevant_indices}")
        
        # 遍历工作经历，计算相关年限
        for idx, exp in enumerate(work_experiences):
            if not exp.start_date:
                continue
            
            start_date = exp.start_date
            end_date = exp.end_date if exp.end_date else today
            
            duration_days = (end_date - start_date).days
            duration_years = duration_days / 365.0
            
            total_years += duration_years
            
            # 判断是否与当前岗位相关
            is_relevant = False
            
            # 优先使用大模型的判断结果
            if llm_relevant_indices:
                is_relevant = idx in llm_relevant_indices
            else:
                # 备用逻辑（关键词匹配）
                position_text = (exp.position or '').lower()
                company_text = (exp.company_name or '').lower()
                dept_text = (exp.department or '').lower()
                
                for keyword in related_keywords:
                    if keyword in position_text or keyword in company_text or keyword in dept_text:
                        is_relevant = True
                        break
                
                # 如果在目标公司工作，且岗位是技术相关，也算相关
                if not is_relevant:
                    company_keywords = ['天翼', '视讯', '国脉', '电信', '传媒', '科技']
                    position_keywords = ['开发', '工程师', '技术', '研发', '前端', '后端', '测试', '运维', '架构', '分析']
                    
                    is_target_company = any(kw in company_text for kw in company_keywords)
                    is_tech_position = any(kw in position_text for kw in position_keywords)
                    
                    if is_target_company and is_tech_position:
                        is_relevant = True
            
            if is_relevant:
                relevant_years += duration_years
                relevant_experiences.append({
                    'company': exp.company_name,
                    'position': exp.position,
                    'duration': duration_years,
                    'start': exp.start_date.strftime('%Y-%m') if exp.start_date else '',
                    'end': exp.end_date.strftime('%Y-%m') if exp.end_date else '至今'
                })
    
    # 如果没有工作经历数据，使用花名册中的工作年限
    if relevant_years == 0 and total_years == 0:
        work_years = emp_info.get('work_years', 0)
        if work_years:
            relevant_years = float(work_years)
            total_years = float(work_years)
    
    # 计算工作履历得分：按满足岗位要求的程度赋分（满分100，占比80%）
    # 满足要求得100分，不满足按比例折算
    if relevant_years >= required_years:
        work_experience_score = 100.0
        work_level = "满足要求"
    else:
        # 按比例折算
        work_experience_score = (relevant_years / required_years) * 100.0 if required_years > 0 else 0
        work_level = f"{relevant_years:.1f}年/{required_years}年"
    
    # 工作履历权重80%
    work_score = work_experience_score * 0.8
    
    # ========== 3. 计算荣誉奖项得分（占比20%）==========
    honor_raw_score = 0  # 原始分（按标准）
    honor_reasons = []
    
    if db and emp_code:
        from app.models.emp_professional_ability import EmpProfessionalAbility
        import json
        prof_ability = db.query(EmpProfessionalAbility).filter(
            EmpProfessionalAbility.emp_code == emp_code
        ).first()
        
        if prof_ability and prof_ability.honors:
            honors = prof_ability.honors
            if isinstance(honors, str):
                try:
                    honors = json.loads(honors)
                except:
                    honors = None
            
            if isinstance(honors, list):
                for honor in honors:
                    if isinstance(honor, dict):
                        honor_level = honor.get('honor_level', '')
                        honor_name = honor.get('honor_name', '')
                        
                        # 根据荣誉级别计算原始分
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
                        
                        honor_raw_score = max(honor_raw_score, points)  # 取最高荣誉
                        honor_reasons.append(f"{honor_name}({level_name}{points}分)")
    
    # 荣誉奖项权重20%
    honor_score = honor_raw_score * 0.2
    
    # ========== 4. 汇总得分 ==========
    total_score = work_score + honor_score
    
    # ========== 5. 构建员工得分理由 ==========
    # 工作履历部分
    if relevant_experiences:
        exp_details = []
        for exp in relevant_experiences[:3]:
            exp_details.append(f"{exp['company']}({exp['duration']:.1f}年)")
        
        employee_reason = f"相关专业工作年限{relevant_years:.1f}年（{work_level}），相关经历：{'；'.join(exp_details)}，工作履历得分{work_score:.1f}分"
    else:
        if relevant_years > 0:
            employee_reason = f"相关专业工作年限{relevant_years:.1f}年（{work_level}），工作履历得分{work_score:.1f}分"
        else:
            employee_reason = f"总工作年限{total_years:.1f}年，未能识别相关专业经历，工作履历得分{work_score:.1f}分"
    
    # 荣誉奖项部分
    if honor_reasons:
        employee_reason += f"；荣誉奖项：{'、'.join(honor_reasons[:3])}，荣誉得分{honor_score:.1f}分"
    else:
        employee_reason += f"；无荣誉奖项记录，荣誉得分{honor_score:.1f}分"
    
    employee_reason += f"，累计得分{total_score:.1f}分"
    
    return total_score, job_requirement, employee_reason, job_reason


def calculate_strategic_alignment_score(emp_info: dict, job_desc: dict, db) -> tuple:
    """
    计算战略匹配维度得分（权重10%）
    基于：员工战略匹配评分表
    
    评分标准：
    - 紧密关联：≥90分
    - 一般关联：80分≤关联度<90分
    - 较差关联：<80分
    
    规则：
    - 如果数据库中有该员工的战略匹配评分数据，直接使用该分数
    - 如果没有数据，员工默认95分，岗位默认95分
    """
    from app.models.strategic_alignment import StrategicAlignmentScore
    from datetime import datetime
    
    emp_code = emp_info.get('emp_code')
    
    # 从数据库获取员工战略匹配评分数据
    score = None
    
    if db and emp_code:
        # 查询该员工最新的战略匹配评分记录（按年份降序）
        score_record = db.query(StrategicAlignmentScore).filter(
            StrategicAlignmentScore.emp_code == emp_code
        ).order_by(StrategicAlignmentScore.evaluation_year.desc()).first()
        
        if score_record:
            score = score_record.score
    
    # 根据是否有数据生成评分理由
    if score is not None:
        # 有数据，根据分数判断关联等级
        if score >= 90:
            level = "紧密关联"
        elif score >= 80:
            level = "一般关联"
        else:
            level = "较差关联"
        
        employee_reason = f"战略匹配评分为{score}分（{level}），根据部门负责人综合评定"
    else:
        # 无数据，默认95分
        score = 95.0
        employee_reason = "暂无战略匹配评分数据，按默认分95分计算"
    
    # 岗位战略匹配要求（默认95分）
    job_requirement = 95.0
    job_reason = "岗位要求员工工作内容与公司战略及部门年度重点工作直接相关（紧密关联≥90分，一般关联80-90分，较差关联<80分），默认标准分95分"
    
    return score, job_requirement, employee_reason, job_reason


def calculate_value_contribution_score(emp_info: dict, job_desc: dict, db) -> tuple:
    """
    计算价值贡献维度得分（权重10%）
    基于：绩效酬金偏离度
    
    计分规则：
    【非试用期员工】
    - 基础分70分，满分上限100分
    - 偏离度为100%时，不加分、不扣分（保持基础分70分）
    - 偏离度较100%，每高出0.5个百分点，加3分
    - 偏离度较100%，每低出0.5个百分点，扣3分
    
    【试用期员工（入职≤6个月）】
    - 基础分100分，满分上限100分
    - 入职以来N个月（剔除入职首月）绩效酬金偏离度≥100%时，不加分、不扣分
    - 入职以来N个月（剔除入职首月）绩效酬金偏离度较100%，每低出0.5个百分点，扣5分
    """
    from app.models.value_contribution import ValueContributionScore
    from datetime import datetime, date
    
    emp_code = emp_info.get('emp_code')
    entry_date = emp_info.get('entry_date')
    
    # 判断是否为试用期员工（入职≤6个月）
    is_probation = False
    months_since_entry = 0
    if entry_date:
        if isinstance(entry_date, str):
            try:
                entry_date = datetime.strptime(entry_date, '%Y-%m-%d').date()
            except:
                try:
                    entry_date = datetime.strptime(entry_date, '%Y-%m-%d %H:%M:%S').date()
                except:
                    entry_date = None
        
        if isinstance(entry_date, date):
            today = date.today()
            months_since_entry = (today.year - entry_date.year) * 12 + (today.month - entry_date.month)
            # 如果入职日期还没到，减去1个月
            if today.day < entry_date.day:
                months_since_entry -= 1
            is_probation = months_since_entry <= 6
    
    # 从数据库获取员工绩效数据（偏离度）
    deviation_rate = None
    performance_standard = None
    actual_performance = None
    
    if db and emp_code:
        # 查询该员工最新的价值贡献记录（按年份降序）
        score_record = db.query(ValueContributionScore).filter(
            ValueContributionScore.emp_code == emp_code
        ).order_by(ValueContributionScore.evaluation_year.desc()).first()
        
        if score_record:
            deviation_rate = score_record.deviation_rate
            performance_standard = score_record.performance_standard
            actual_performance = score_record.actual_performance
    
    # 根据员工类型和偏离度计算价值贡献分数
    if deviation_rate is not None:
        if is_probation:
            # 【试用期员工计分规则】
            # 基础分100分
            base_score = 100.0
            
            # 计算与100%的偏差
            diff = deviation_rate - 100.0
            
            if diff >= 0:
                # 偏离度≥100%时，不加分、不扣分
                score = base_score
                score_change = 0
                employee_reason = f"试用期员工（入职{months_since_entry}个月），绩效酬金偏离度为{deviation_rate:.1f}%（≥100%），不加分不扣分，价值贡献得分{score:.1f}分"
            else:
                # 偏离度<100%时，每低出0.5个百分点，扣5分
                score_change = (abs(diff) / 0.5) * 5
                score = base_score - score_change
                
                # 限制在0-100范围内
                score = max(0.0, min(100.0, score))
                
                employee_reason = f"试用期员工（入职{months_since_entry}个月），绩效酬金偏离度为{deviation_rate:.1f}%（低于100% {abs(diff):.1f}个百分点），每低出0.5个百分点扣5分，价值贡献得分{score:.1f}分"
            
            # 岗位价值贡献要求（试用期）
            job_requirement = 100.0
            job_reason = f"试用期员工（入职{months_since_entry}个月）岗位要求：绩效酬金偏离度≥100%时不扣分，每低出0.5个百分点扣5分，基础分100分"
        else:
            # 【非试用期员工计分规则】
            # 基础分70分
            base_score = 70.0
            
            # 计算与100%的偏差
            diff = deviation_rate - 100.0
            
            # 每0.5个百分点变化3分
            score_change = (diff / 0.5) * 3
            
            # 计算最终分数
            score = base_score + score_change
            
            # 限制在0-100范围内
            score = max(0.0, min(100.0, score))
            
            # 生成评分理由
            if diff > 0:
                employee_reason = f"正式员工，绩效酬金偏离度为{deviation_rate:.1f}%（高于100% {diff:.1f}个百分点），每高出0.5个百分点加3分，价值贡献得分{score:.1f}分"
            elif diff < 0:
                employee_reason = f"正式员工，绩效酬金偏离度为{deviation_rate:.1f}%（低于100% {abs(diff):.1f}个百分点），每低出0.5个百分点扣3分，价值贡献得分{score:.1f}分"
            else:
                employee_reason = f"正式员工，绩效酬金偏离度正好为100%，不加分不扣分，价值贡献得分{score:.1f}分"
            
            # 岗位价值贡献要求（非试用期）
            job_requirement = 70.0
            job_reason = "正式员工岗位要求：绩效酬金偏离度达到100%（即实际发放绩效与标准绩效一致），基础分70分，每高出0.5个百分点加3分，每低出0.5个百分点扣3分"
    else:
        # 如果没有找到记录，根据员工类型使用默认分数
        if is_probation:
            score = 100.0
            employee_reason = f"试用期员工（入职{months_since_entry}个月），暂无价值贡献数据，按基础分100分计算"
            job_requirement = 100.0
            job_reason = f"试用期员工（入职{months_since_entry}个月）岗位要求：绩效酬金偏离度≥100%时不扣分，基础分100分"
        else:
            score = 70.0
            employee_reason = "正式员工，暂无价值贡献数据，按基础分70分计算"
            job_requirement = 70.0
            job_reason = "正式员工岗位要求：绩效酬金偏离度达到100%，基础分70分"
    
    return score, job_requirement, employee_reason, job_reason


# 全局Whisper模型缓存
_whisper_model = None

def get_whisper_model():
    """获取或初始化Whisper模型"""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            logger.info("[Innovation] 正在加载Whisper模型...")
            _whisper_model = whisper.load_model("base")
            logger.info("[Innovation] Whisper模型加载完成")
        except Exception as e:
            logger.error(f"[Innovation] 加载Whisper模型失败: {e}")
            return None
    return _whisper_model


def transcribe_audio_file(audio_file_path: str) -> str:
    """
    使用本地Whisper模型将录音文件转为文字
    
    Args:
        audio_file_path: 录音文件路径
    
    Returns:
        转录后的文字内容
    """
    try:
        model = get_whisper_model()
        if model is None:
            return "[语音识别模型加载失败]"
        
        logger.info(f"[Innovation] 开始转录音频文件: {audio_file_path}")
        
        # 执行转录
        result = model.transcribe(
            audio_file_path,
            language="zh",  # 指定中文
            task="transcribe",
            verbose=False
        )
        
        transcription_text = result["text"]
        logger.info(f"[Innovation] 音频转录完成，文本长度: {len(transcription_text)} 字符")
        
        return transcription_text
        
    except Exception as e:
        logger.error(f"[Innovation] 音频转录失败: {e}")
        return f"[音频转录失败: {str(e)}]"


async def calculate_innovation_score_from_interview(
    emp_info: dict, 
    job_desc: dict, 
    db, 
    audio_file_path: Optional[str] = None,
    questions_file_path: Optional[str] = None
) -> tuple:
    """
    计算创新能力维度得分（权重10%）
    基于：面试录音（先本地转文字）和提问回答，通过大模型评估
    
    计分规则：
    - 满分100分
    - 根据谈话录音转文字后的内容，结合岗位说明书的要求，进行综合打分
    - 岗位侧要求根据岗位说明书通过大模型生成
    """
    import aiohttp
    import pandas as pd
    
    # 默认分数和理由
    default_score = 70.0
    default_job_requirement = 70.0
    default_reason = "暂无录音和提问数据，按默认分70分计算"
    default_job_reason = "岗位要求员工具备一定的创新思维和能力，能够提出改进建议，标准分70分"
    
    # 获取岗位信息
    position_name = job_desc.get('position_name', emp_info.get('position', '未知岗位')) if job_desc else emp_info.get('position', '未知岗位')
    
    # 构建岗位说明书内容
    job_description_content = ""
    if job_desc:
        job_parts = []
        if job_desc.get('position_purpose'):
            job_parts.append(f"岗位目的：{job_desc['position_purpose']}")
        if job_desc.get('duties'):
            job_parts.append(f"岗位职责：{job_desc['duties']}")
        if job_desc.get('qualifications_skills'):
            job_parts.append(f"技能要求：{job_desc['qualifications_skills']}")
        if job_desc.get('qualifications_others'):
            job_parts.append(f"其他要求：{job_desc['qualifications_others']}")
        if job_desc.get('kpis'):
            job_parts.append(f"KPI指标：{job_desc['kpis']}")
        job_description_content = "\n".join(job_parts) if job_parts else "暂无详细岗位说明书"
    else:
        job_description_content = "暂无岗位说明书"
    
    # 如果没有提供文件，返回默认分数，但岗位侧仍需调用大模型生成要求
    if not audio_file_path and not questions_file_path:
        # 调用大模型生成岗位要求
        job_requirement, job_reason = await _calculate_job_innovation_requirement(
            position_name, job_description_content
        )
        return default_score, job_requirement, default_reason, job_reason
    
    try:
        # 转录音频文件（如果有）
        transcription_text = ""
        if audio_file_path and os.path.exists(audio_file_path):
            logger.info(f"[Innovation] 开始处理音频文件: {audio_file_path}")
            transcription_text = transcribe_audio_file(audio_file_path)
        
        # 读取提问问题文件（如果有）
        questions_content = ""
        if questions_file_path and os.path.exists(questions_file_path):
            if questions_file_path.endswith('.xlsx') or questions_file_path.endswith('.xls'):
                df = pd.read_excel(questions_file_path)
                questions_content = df.to_string()
            elif questions_file_path.endswith('.csv'):
                df = pd.read_csv(questions_file_path)
                questions_content = df.to_string()
            else:
                with open(questions_file_path, 'r', encoding='utf-8') as f:
                    questions_content = f.read()
        
        # 并行调用两个大模型请求：员工评分 + 岗位要求
        employee_task = _evaluate_employee_innovation(
            emp_info.get('emp_name', '未知'),
            position_name,
            job_description_content,
            transcription_text,
            questions_content
        )
        job_task = _calculate_job_innovation_requirement(
            position_name,
            job_description_content
        )
        
        # 等待两个任务完成
        employee_result, job_result = await asyncio.gather(employee_task, job_task)
        
        score, employee_reason = employee_result
        job_requirement, job_reason = job_result
        
        return score, job_requirement, employee_reason, job_reason
                    
    except Exception as e:
        logger.error(f"评估创新能力时出错: {e}")
        # 即使出错，也尝试获取岗位要求
        try:
            job_requirement, job_reason = await _calculate_job_innovation_requirement(
                position_name, job_description_content
            )
        except:
            job_requirement, job_reason = default_job_requirement, default_job_reason
        return default_score, job_requirement, default_reason, job_reason


async def _evaluate_employee_innovation(
    emp_name: str,
    position_name: str,
    job_description: str,
    transcription_text: str,
    questions_content: str
) -> tuple:
    """评估员工创新能力，返回(分数, 精简理由)"""
    import aiohttp
    
    default_score = 70.0
    
    # 构建提示词 - 要求精简理由
    prompt = f"""请根据以下信息评估该员工的创新能力。

员工：{emp_name}
岗位：{position_name}

岗位说明书：
{job_description[:1500]}

{f'面试录音转录：{transcription_text[:2000]}' if transcription_text and not transcription_text.startswith('[') else ''}

{f'提问回答：{questions_content[:1500]}' if questions_content else ''}

评估要求：
1. 满分100分，重点关注：创新思维、问题解决能力、提出改进建议的能力
2. 理由必须精简，控制在50字以内，只说核心评价点

请按以下JSON格式返回：
{{
    "score": 0-100的整数,
    "reason": "精简理由（50字以内）"
}}
"""
    
    async with aiohttp.ClientSession() as session:
        payload = {
            "model": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "messages": [
                {"role": "system", "content": "你是人力资源专家，评估员工创新能力。理由必须精简，控制在50字以内。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer z3oK7bN9xPqW2mT8rYvL5tF1cJ4hD6gA0eS2uI3nQk"
        }

        async with session.post(
            "http://180.97.200.118:30071/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as response:
            if response.status == 200:
                result = await response.json()
                content = result['choices'][0]['message']['content']

                try:
                    import json
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = content[json_start:json_end]
                        evaluation = json.loads(json_str)
                        score = float(evaluation.get('score', default_score))
                        reason = evaluation.get('reason', '评估完成')
                    else:
                        score = default_score
                        reason = content[:50] if content else '评估完成'

                    score = max(0, min(100, score))
                    # 确保理由精简
                    if len(reason) > 60:
                        reason = reason[:57] + "..."

                    employee_reason = f"{reason}，得分{score:.1f}分"
                    return score, employee_reason
                except Exception as e:
                    logger.error(f"解析员工创新能力评估结果失败: {e}")
                    return default_score, f"评估完成，得分{default_score:.1f}分"
            else:
                logger.error(f"调用大模型评估员工创新能力失败，状态码: {response.status}")
                return default_score, f"评估完成，得分{default_score:.1f}分"


async def _calculate_job_innovation_requirement(
    position_name: str,
    job_description: str
) -> tuple:
    """根据岗位说明书计算岗位创新能力要求，返回(要求分数, 理由)"""
    import aiohttp
    
    default_requirement = 70.0
    default_reason = "岗位要求员工具备一定的创新思维和能力，标准分70分"
    
    # 如果没有岗位说明书，返回默认值
    if not job_description or job_description == "暂无岗位说明书":
        return default_requirement, default_reason
    
    try:
        prompt = f"""请根据以下岗位说明书，分析该岗位对创新能力的具体要求，并给出标准分数。

岗位名称：{position_name}

岗位说明书：
{job_description[:2000]}

分析要求：
1. 根据岗位职责的复杂程度、是否需要持续改进、是否要求创新思维等因素，确定创新能力要求分数
2. 满分100分，一般岗位60-75分，需要较强创新能力的岗位75-90分
3. 理由控制在50字以内，说明为什么这个岗位需要这个分数

请按以下JSON格式返回：
{{
    "requirement_score": 60-100的整数,
    "reason": "精简理由（50字以内）"
}}
"""
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "Qwen/Qwen3-235B-A22B-Instruct-2507",
                "messages": [
                    {"role": "system", "content": "你是人力资源专家，分析岗位对创新能力的要求。理由必须精简，控制在50字以内。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer z3oK7bN9xPqW2mT8rYvL5tF1cJ4hD6gA0eS2uI3nQk"
            }

            async with session.post(
                "http://180.97.200.118:30071/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    
                    try:
                        import json
                        json_start = content.find('{')
                        json_end = content.rfind('}') + 1
                        if json_start >= 0 and json_end > json_start:
                            json_str = content[json_start:json_end]
                            evaluation = json.loads(json_str)
                            requirement_score = float(evaluation.get('requirement_score', default_requirement))
                            reason = evaluation.get('reason', '基于岗位分析')
                        else:
                            requirement_score = default_requirement
                            reason = '基于岗位分析'
                        
                        requirement_score = max(50, min(100, requirement_score))
                        # 确保理由精简
                        if len(reason) > 60:
                            reason = reason[:57] + "..."
                        
                        job_reason = f"{reason}，标准分{requirement_score:.1f}分"
                        return requirement_score, job_reason
                    except Exception as e:
                        logger.error(f"解析岗位创新能力要求结果失败: {e}")
                        return default_requirement, default_reason
                else:
                    logger.error(f"调用大模型分析岗位要求失败，状态码: {response.status}")
                    return default_requirement, default_reason
                    
    except Exception as e:
        logger.error(f"计算岗位创新能力要求时出错: {e}")
        return default_requirement, default_reason


async def calculate_learning_score(emp_info: dict, job_desc: dict, db=None, audio_file_path: str = None, questions_file_path: str = None) -> tuple:
    """
    计算学习能力维度得分（权重20%）
    基于附件要求：
    一、基础学习能力（占比70%）：学历+学校类型+专业对口
    二、持续学习能力-学位提升（占比10%）：在职教育提升
    三、持续学习能力-综合评价（占比20%）：谈话录音评价（调用大模型，温度系数0.3）
    """
    import json
    education = emp_info.get('education') or ''
    school = emp_info.get('school') or ''
    school_type = emp_info.get('school_type') or ''
    highest_degree = emp_info.get('highest_degree') or ''
    major = emp_info.get('highest_degree_major') or ''
    emp_code = emp_info.get('emp_code')
    emp_name = emp_info.get('emp_name', '未知')
    reasons = []
    
    # ========== 一、基础学习能力（占比70%）==========
    # 根据学位和学校类型确定基础分
    base_score = 0
    
    # 判断学校类型
    is_985 = '985' in school_type or 'QS前50' in school_type
    is_211 = '211' in school_type or 'QS50-100' in school_type or 'QS前100' in school_type
    is_normal = not is_985 and not is_211
    
    # 学士阶段
    if "学士" in highest_degree or ("本科" in education and "无学位" not in highest_degree):
        if is_985:
            base_score = 80
            reasons.append(f"本科学历+985/QS前50院校，基础分80分")
        elif is_211:
            base_score = 70
            reasons.append(f"本科学历+211/QS50-100院校，基础分70分")
        else:
            base_score = 60
            reasons.append(f"本科学历+普通院校，基础分60分")
    # 硕士阶段
    elif "硕士" in highest_degree or "研究生" in highest_degree:
        if is_985:
            base_score = 90
            reasons.append(f"硕士学历+985/QS前50院校，基础分90分")
        elif is_211:
            base_score = 80
            reasons.append(f"硕士学历+211/QS50-100院校，基础分80分")
        else:
            base_score = 70
            reasons.append(f"硕士学历+普通院校，基础分70分")
    # 博士阶段
    elif "博士" in highest_degree:
        if is_985:
            base_score = 100
            reasons.append(f"博士学历+985/QS前50院校，基础分100分")
        elif is_211:
            base_score = 90
            reasons.append(f"博士学历+211/QS50-100院校，基础分90分")
        else:
            base_score = 80
            reasons.append(f"博士学历+普通院校，基础分80分")
    # 专科阶段（扣分）
    elif "专科" in education or "大专" in education:
        base_score = 55  # 60 - 5 = 55
        reasons.append(f"专科学历，基础分60分-5分=55分")
    else:
        base_score = 55  # 60 - 5 = 55
        reasons.append(f"专科学历，基础分60分-5分=55分")
    # 专科以下（扣分）
    # else:
    #     base_score = 50  # 60 - 10 = 50
    #     reasons.append(f"专科以下学历，基础分60分-10分=50分")
    
    # 专业对口加分（+5分）
    major_bonus = 0
    if major and job_desc:
        qual_major = job_desc.get('qualifications_major')
        if qual_major:
            try:
                if isinstance(qual_major, str):
                    qual_major = json.loads(qual_major)
                job_major = qual_major.get('requirement', '')
                if job_major and '不限' not in job_major:
                    # 使用大模型判断专业匹配度
                    import requests
                    from app.config import get_settings
                    
                    settings = get_settings()
                    
                    prompt = f"""请判断以下员工的专业是否与岗位要求的专业匹配。

员工专业：{major}
岗位要求专业：{job_major}

请分析员工专业是否与岗位要求的专业匹配，返回"匹配"或"不匹配"。

判断标准：
1. 员工专业与岗位要求的专业名称完全相同
2. 员工专业与岗位要求的专业属于同一学科门类
3. 员工专业与岗位要求的专业在知识结构和技能要求上有较高的相关性

只返回"匹配"或"不匹配"，不要返回其他内容。"""
                    
                    try:
                        response = requests.post(
                            settings.LLM_URL,
                            headers={
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {settings.LLM_API_KEY}"
                            },
                            json={
                                "model": settings.LLM_MODEL,
                                "messages": [
                                    {"role": "system", "content": "你是一个专业的HR分析师，擅长判断员工专业与岗位要求的匹配度。"},
                                    {"role": "user", "content": prompt}
                                ],
                                "temperature": 0.3,
                                "max_tokens": 50
                            },
                            timeout=10
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                            if '匹配' in content:
                                major_bonus = 5
                                reasons.append(f"专业{major}与岗位要求匹配，+5分")
                    except Exception as e:
                        pass
            except Exception as e:
                pass
    
    # 基础学习能力总分（最高100分）
    basic_learning_score = min(base_score + major_bonus, 100)
    
    # ========== 二、持续学习能力-学位提升（占比10%）==========
    degree_upgrade_score = 0
    degree_upgrade_reason = ""
    
    # 从数据库查询在职教育提升记录
    if db and emp_code:
        try:
            from app.models.emp_learning import EmpLearning
            learning_records = db.query(EmpLearning).filter(
                EmpLearning.emp_code == emp_code,
                EmpLearning.learning_type == 'degree_upgrade'
            ).all()
            
            if learning_records:
                for record in learning_records:
                    degree_type = record.degree_type or ''
                    school_type_upgrade = record.school_type or ''
                    
                    # 学士阶段（专升本）
                    if '学士' in degree_type or '本科' in degree_type:
                        if '985' in school_type_upgrade:
                            score = 50
                        elif '211' in school_type_upgrade:
                            score = 40
                        else:
                            score = 30
                    # 硕士阶段
                    elif '硕士' in degree_type:
                        if '985' in school_type_upgrade:
                            score = 60
                        elif '211' in school_type_upgrade:
                            score = 50
                        else:
                            score = 40
                    # 博士阶段
                    elif '博士' in degree_type:
                        if '985' in school_type_upgrade:
                            score = 70
                        elif '211' in school_type_upgrade:
                            score = 60
                        else:
                            score = 50
                    else:
                        score = 30
                    
                    if score > degree_upgrade_score:
                        degree_upgrade_score = score
                        degree_upgrade_reason = f"在职提升{degree_type}({school_type_upgrade})"
            
            if degree_upgrade_score > 0:
                reasons.append(f"{degree_upgrade_reason}，学位提升得分{degree_upgrade_score}分")
            else:
                reasons.append("无在职学位提升记录，学位提升得分0分")
        except Exception as e:
            reasons.append("无在职学位提升记录，学位提升得分0分")
    else:
        reasons.append("无在职学位提升记录，学位提升得分0分")
    
    # ========== 三、持续学习能力-综合评价（占比20%）==========
    # 根据谈话录音和问题对调用大模型进行评估
    comprehensive_score = 70  # 默认中等水平
    comprehensive_reason = "默认综合评价得分70分"
    
    if audio_file_path or questions_file_path:
        try:
            # 转录音频文件（如果有）
            transcription_text = ""
            if audio_file_path and os.path.exists(audio_file_path):
                logger.info(f"[Learning] 开始处理学习能力音频文件: {audio_file_path}")
                transcription_text = transcribe_audio_file(audio_file_path)
            
            # 读取提问问题文件（如果有）
            questions_content = ""
            if questions_file_path and os.path.exists(questions_file_path):
                import pandas as pd
                if questions_file_path.endswith('.xlsx') or questions_file_path.endswith('.xls'):
                    df = pd.read_excel(questions_file_path)
                    questions_content = df.to_string()
                elif questions_file_path.endswith('.csv'):
                    df = pd.read_csv(questions_file_path)
                    questions_content = df.to_string()
                else:
                    with open(questions_file_path, 'r', encoding='utf-8') as f:
                        questions_content = f.read()
            
            # 获取岗位信息
            position_name = job_desc.get('position_name', emp_info.get('position', '未知岗位')) if job_desc else emp_info.get('position', '未知岗位')
            
            # 构建提示词
            prompt = f"""请根据以下信息评估该员工的学习能力，并给出分数和评价。

员工信息：
- 姓名：{emp_name}
- 岗位：{position_name}
- 学历：{highest_degree}
- 毕业院校：{school} ({school_type})

评估要求：
1. 满分100分，根据面试录音转录的文字内容和提问回答，评估员工的学习能力
2. 重点关注：
   - 学习态度和学习意愿
   - 知识更新和能力提升的意识
   - 对新知识、新技能的接受能力
   - 自我学习和持续成长的表现
3. 给出分数和简要评价理由（控制在50字以内）

{f'面试录音转录内容：{transcription_text[:2000]}' if transcription_text and not transcription_text.startswith('[') else ''}

{f'提问回答：{questions_content[:1500]}' if questions_content else ''}

请按以下JSON格式返回结果：
{{
    "score": 0-100的整数,
    "reason": "简要评价理由（50字以内）"
}}
"""
            
            # 调用远程大模型（温度系数0.3）
            import aiohttp
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "Qwen/Qwen3-235B-A22B-Instruct-2507",
                    "messages": [
                        {"role": "system", "content": "你是一个专业的人力资源评估专家，擅长评估员工的学习能力。请根据提供的面试录音转录文字和提问回答，客观、公正地评估员工的学习能力。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer z3oK7bN9xPqW2mT8rYvL5tF1cJ4hD6gA0eS2uI3nQk"
                }
                
                async with session.post(
                    "http://180.97.200.118:30071/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result['choices'][0]['message']['content']
                        
                        # 解析JSON结果
                        try:
                            json_start = content.find('{')
                            json_end = content.rfind('}') + 1
                            if json_start >= 0 and json_end > json_start:
                                json_str = content[json_start:json_end]
                                evaluation = json.loads(json_str)
                                comprehensive_score = float(evaluation.get('score', 70))
                                eval_reason = evaluation.get('reason', '评估完成')
                                # 确保理由精简
                                if len(eval_reason) > 60:
                                    eval_reason = eval_reason[:57] + "..."
                                comprehensive_reason = f"{eval_reason}，综合评价得分{comprehensive_score:.0f}分"
                            else:
                                comprehensive_reason = "大模型评估完成，综合评价得分70分"
                        except Exception as e:
                            logger.error(f"解析学习能力综合评价结果失败: {e}")
                            comprehensive_reason = "评估解析失败，使用默认得分70分"
                    else:
                        logger.error(f"调用大模型评估学习能力失败，状态码: {response.status}")
                        comprehensive_reason = "大模型调用失败，使用默认得分70分"
                        
        except Exception as e:
            logger.error(f"评估学习能力综合评价时出错: {e}")
            comprehensive_reason = "评估过程出错，使用默认得分70分"
    
    reasons.append(comprehensive_reason)
    
    # ========== 汇总得分 ==========
    # 判断是否为专科学历，决定权重分配
    is_specialist = "专科" in education or "大专" in education
    
    # if is_specialist:
    #     # 专科学历：基础学历:学位提升:综合评价 = 7:1:2
    #     final_score = (basic_learning_score * 0.7) + (degree_upgrade_score * 0.1) + (comprehensive_score * 0.2)
    #     weight_reason = f"专科学历按7:1:2权重计算：基础学历{basic_learning_score:.0f}分×70%={basic_learning_score * 0.7:.1f}分"
    #     if degree_upgrade_score > 0:
    #         weight_reason += f"，学位提升{degree_upgrade_score:.0f}分×10%={degree_upgrade_score * 0.1:.1f}分"
    #     else:
    #         weight_reason += "，学位提升0分×10%=0分"
    #     weight_reason += f"，综合评价{comprehensive_score:.0f}分×20%={comprehensive_score * 0.2:.1f}分"
    # else:
        # 非专科学历：基础学历:综合评价 = 8:2（不含学位提升）
    final_score = (basic_learning_score * 0.8) + (comprehensive_score * 0.2)
    weight_reason = f"非专科学历按8:2权重计算：基础学历{basic_learning_score:.0f}分×80%={basic_learning_score * 0.8:.1f}分，综合评价{comprehensive_score:.0f}分×20%={comprehensive_score * 0.2:.1f}分"

    employee_reason = "；".join(reasons) + f"；{weight_reason}，最终得分{final_score:.1f}分"
    
    # ========== 岗位侧要求 ==========
    qual_edu = job_desc.get('qualifications_education') if job_desc else None
    qual_major = job_desc.get('qualifications_major') if job_desc else None
    
    job_reason_parts = []
    
    if qual_edu:
        edu_str = str(qual_edu)
        if '博士' in edu_str:
            job_requirement = 80
            job_reason_parts.append("博士学历")
        elif '研究生' in edu_str:
            job_requirement = 70
            job_reason_parts.append("硕士及以上学历")
        elif '本科' in edu_str:
            job_requirement = 60
            job_reason_parts.append("本科及以上学历")
        else:
            job_requirement = 55
            job_reason_parts.append("大专及以上")
    else:
        job_requirement = 60
        job_reason_parts.append("本科及以上学历")
    
    if qual_major:
        try:
            if isinstance(qual_major, str):
                qual_major = json.loads(qual_major)
            job_major = qual_major.get('requirement', '')
            if job_major and '不限' not in job_major:
                job_requirement += 5
                job_reason_parts.append(f"需要{job_major}相关专业")
        except:
            pass
    
    job_reason = f"要求：{ '，'.join(job_reason_parts) }，标准分{job_requirement}分"
    
    return final_score, job_requirement, employee_reason, job_reason


def calculate_attitude_score(attendance: dict, job_desc: dict, emp_info: dict = None) -> tuple:
    """
    计算工作态度维度得分（权重20%）
    基于：考勤数据（迟到、早退、加班）
    
    计分规则：
    【非试用期员工】
    - 基础分70分，上限100分
    - 迟到/早退：每月大于3次，3次以上每次扣1分，最多扣10分
    - 加班加分：月度加班时间达到36小时及以上，加20分
    
    【试用期员工（入职≤6个月）】
    - 基础分70分，上限100分
    - 扣分项（自然年）：
      - 迟到/早退：豁免3次/月，在豁免的基础上每多一次每次扣1分，最多扣10分
      - 旷工：每旷工1次，扣10分，年度旷工超过3次以上，本大项目直接0分
    - 加分项（累计得分）：
      - 工作日按照17点30分为下班时间，最晚打卡时间为18点30分及以后的，加3分，20点30分及以后的，加6分，最多加30分
      - 月度加班时间达到36小时及以上的，加30分
      - 以上条件二选一
    - 政治面貌：中共党员加5分
    - 党工团兼职：党10、团7、工4，最高10分
    """
    from datetime import datetime, date
    
    # 判断是否为试用期员工（入职≤6个月）
    is_probation = False
    months_since_entry = 0
    if emp_info:
        entry_date = emp_info.get('entry_date')
        if entry_date:
            if isinstance(entry_date, str):
                try:
                    entry_date = datetime.strptime(entry_date, '%Y-%m-%d').date()
                except:
                    try:
                        entry_date = datetime.strptime(entry_date, '%Y-%m-%d %H:%M:%S').date()
                    except:
                        entry_date = None
            
            if isinstance(entry_date, date):
                today = date.today()
                months_since_entry = (today.year - entry_date.year) * 12 + (today.month - entry_date.month)
                # 如果入职日期还没到，减去1个月
                if today.day < entry_date.day:
                    months_since_entry -= 1
                is_probation = months_since_entry <= 6
    
    if not attendance:
        if is_probation:
            score = 70
            employee_reason = f"试用期员工（入职{months_since_entry}个月），基础分70分，暂无考勤数据"
            job_requirement = 70
            job_reason = f"试用期员工（入职{months_since_entry}个月）要求：遵守考勤纪律，积极主动，标准分70分"
        else:
            score = 70
            employee_reason = "正式员工，基础分70分，暂无考勤数据"
            job_requirement = 70
            job_reason = "正式员工要求：遵守考勤纪律，积极主动，标准分70分"
        return score, job_requirement, employee_reason, job_reason
    
    if is_probation:
        # 【试用期员工计分规则】
        score = 70  # 基础分70分
        reasons = [f"试用期员工（入职{months_since_entry}个月），基础分70分"]
        
        # 扣分项（自然年）
        late_count = attendance.get('late_count', 0)
        early_leave_count = attendance.get('early_leave_count', 0)
        absenteeism_count = attendance.get('absenteeism_count', 0)  # 旷工次数
        
        # 迟到/早退：豁免3次/月，在豁免的基础上每多一次每次扣1分，最多扣10分
        if late_count > 0:
            if late_count > 3:
                late_deduction = min(int((late_count - 3)), 10)
                score -= late_deduction
                reasons.append(f"月平均迟到{late_count}次（豁免3次），扣{late_deduction}分")
            else:
                reasons.append(f"月平均迟到{late_count}次（3次以内不扣分）")
        
        if early_leave_count > 0:
            if early_leave_count > 3:
                early_deduction = min(int((early_leave_count - 3)), 10)
                score -= early_deduction
                reasons.append(f"月平均早退{early_leave_count}次（豁免3次），扣{early_deduction}分")
            else:
                reasons.append(f"月平均早退{early_leave_count}次（3次以内不扣分）")
        
        # 旷工：每旷工1次，扣10分，年度旷工超过3次以上，本大项目直接0分
        if absenteeism_count > 0:
            if absenteeism_count > 3:
                score = 0
                reasons.append(f"年度旷工{absenteeism_count}次（超过3次），工作态度直接0分")
            else:
                absenteeism_deduction = int(absenteeism_count) * 10
                score -= absenteeism_deduction
                reasons.append(f"旷工{absenteeism_count}次，扣{absenteeism_deduction}分")
        
        # 加分项（累计得分）- 二选一
        overtime_hours = attendance.get('overtime_hours', 0)
        
        # 条件1：月度加班时间达到36小时及以上的，加30分
        if overtime_hours >= 36:
            score += 30
            reasons.append(f"月平均加班{overtime_hours:.1f}小时（≥36小时），+30分")
        else:
            # 条件2：工作日按照17点30分为下班时间，最晚打卡时间为18点30分及以后的，加3分，20点30分及以后的，加6分，最多加30分
            overtime_count = attendance.get('overtime_count', 0)  # 18:30后打卡次数
            very_late_checkout_count = attendance.get('very_late_checkout_count', 0)  # 20:30后打卡次数
            
            if very_late_checkout_count > 0:
                bonus = min(int(very_late_checkout_count) * 6, 30)
                score += bonus
                reasons.append(f"20:30后打卡{very_late_checkout_count}次，+{bonus}分")
            elif overtime_count > 0:
                bonus = min(int(overtime_count) * 3, 30)
                score += bonus
                reasons.append(f"18:30后打卡{overtime_count}次，+{bonus}分")
        
        # 政治面貌：中共党员加5分
        political_status = emp_info.get('political_status', '') if emp_info else ''
        if political_status and '党员' in political_status:
            score += 5
            reasons.append("中共党员，+5分")
        
        # 党工团兼职：党10、团7、工4，最高10分
        party_union_role = emp_info.get('party_union_role', '') if emp_info else ''
        if party_union_role:
            if '党' in party_union_role:
                score += 10
                reasons.append("党工团兼职（党），+10分")
            elif '团' in party_union_role:
                score += 7
                reasons.append("党工团兼职（团），+7分")
            elif '工' in party_union_role:
                score += 4
                reasons.append("党工团兼职（工），+4分")
        
        score = max(0, min(score, 100))
        employee_reason = "；".join(reasons) + f"，最终得分{score:.1f}分"
        
        # 试用期员工岗位要求
        job_requirement = 70
        job_reason = f"试用期员工（入职{months_since_entry}个月）要求：基础分70分，迟到/早退豁免3次/月，旷工每次扣10分（超过3次直接0分），加班或晚打卡可加分，中共党员+5分，党工团兼职最高+10分"
    else:
        # 【非试用期员工计分规则】
        score = 70  # 基础分70分
        reasons = ["正式员工，基础分70分"]
        
        # 扣分项
        late_count = attendance.get('late_count', 0)
        early_leave_count = attendance.get('early_leave_count', 0)
        
        # 迟到/早退扣分：每月大于3次，3次以上每次扣1分，最多扣10分
        if late_count > 0:
            if late_count > 3:
                late_deduction = min(int((late_count - 3)), 10)
                score -= late_deduction
                reasons.append(f"月平均迟到{late_count}次，扣{late_deduction}分")
            else:
                reasons.append(f"月平均迟到{late_count}次（3次以内不扣分）")
        
        if early_leave_count > 0:
            early_deduction = min(int(early_leave_count), 10)
            score -= early_deduction
            reasons.append(f"月平均早退{early_leave_count}次，扣{early_deduction}分")
        
        # 加分项
        overtime_hours = attendance.get('overtime_hours', 0)
        overtime_count = attendance.get('overtime_count', 0)
        
        # 月度加班时间达到36小时及以上，加20分
        if overtime_hours >= 36:
            score += 20
            reasons.append(f"月平均加班{overtime_hours:.1f}小时，+20分")
        elif overtime_count > 0:
            bonus = min(int(overtime_count), 20)
            score += bonus
            reasons.append(f"月平均加班{overtime_hours:.1f}小时，+{bonus:.1f}分")
        
        if overtime_count > 0:
            reasons.append(f"月平均加班天数{overtime_count}天")   
        
        score = max(0, min(score, 100))
        employee_reason = "；".join(reasons) + f"，最终得分{score:.1f}分"
        
        # 非试用期员工岗位要求
        job_requirement = 70
        job_reason = "正式员工要求：遵守考勤纪律，积极主动，标准分70分"
    
    return score, job_requirement, employee_reason, job_reason


def generate_conclusion(dimensions: List[DimensionScore], overall_score: float, job_requirement_score: float, emp_info: dict = None, job_desc: dict = None) -> tuple:
    """生成分析结论和评价"""
    
    # 找出最高和最低维度
    sorted_dims = sorted(dimensions, key=lambda x: x.score, reverse=True)
    highest = sorted_dims[0]
    lowest = sorted_dims[-1]
    
    # 计算差距最大的维度
    gap_dims = sorted(dimensions, key=lambda x: x.job_requirement - x.score, reverse=True)
    biggest_gap = gap_dims[0] if gap_dims else None
    
    # 计算人岗匹配率
    match_rate = 0
    if job_requirement_score > 0:
        match_rate = (overall_score / job_requirement_score) * 100
    
    # 生成结论
    if overall_score >= 90:
        conclusion = f"该员工与岗位高度匹配，综合得分{overall_score:.1f}分（岗位要求{job_requirement_score:.1f}分）。在{highest.name}方面表现突出（{highest.score:.1f}分），建议重点培养。"
        evaluation = "优秀"
    elif overall_score >= 80:
        conclusion = f"该员工与岗位匹配度良好，综合得分{overall_score:.1f}分（岗位要求{job_requirement_score:.1f}分）。{highest.name}是优势项，但{lowest.name}需要提升。"
        evaluation = "良好"
    elif overall_score >= 60:
        if biggest_gap and biggest_gap.job_requirement - biggest_gap.score > 15:
            conclusion = f"该员工基本符合岗位要求，综合得分{overall_score:.1f}分（岗位要求{job_requirement_score:.1f}分）。{biggest_gap.name}方面存在明显差距（要求{biggest_gap.job_requirement:.0f}分，实际{biggest_gap.score:.0f}分），需要针对性培训。"
        else:
            conclusion = f"该员工基本符合岗位要求，综合得分{overall_score:.1f}分（岗位要求{job_requirement_score:.1f}分）。整体表现平稳，建议持续提升。"
        evaluation = "合格"
    else:
        conclusion = f"该员工与岗位匹配度较低，综合得分{overall_score:.1f}分（岗位要求{job_requirement_score:.1f}分）。多项能力指标未达到岗位要求，建议调整岗位或加强培训。"
        evaluation = "待提升"
    
    # 生成建议
    recommendations = []
    
    # 使用大模型生成智能建议
    if emp_info and job_desc:
        import requests
        
        # 大模型配置
        LLM_URL = "http://180.97.200.118:30071/v1/chat/completions"
        LLM_API_KEY = "z3oK7bN9xPqW2mT8rYvL5tF1cJ4hD6gA0eS2uI3nQk"
        LLM_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"
        
        # 准备维度信息
        dimension_info = []
        for dim in dimensions:
            gap = dim.job_requirement - dim.score
            dimension_info.append(f"{dim.name}：员工得分{dim.score:.1f}分，岗位要求{dim.job_requirement:.1f}分，差距{gap:+.1f}分")
        
        # 构建提示词
        prompt = f"""请根据以下员工和岗位信息，生成详细的发展建议：

员工信息：
- 姓名：{emp_info.get('emp_name', '未知')}
- 岗位：{emp_info.get('position', '未知')}
- 部门：{emp_info.get('department', '未知')}
- 综合得分：{overall_score:.1f}分
- 人岗匹配率：{match_rate:.1f}%

岗位信息：
- 岗位名称：{job_desc.get('position_name', '未知')}
- 岗位职责：{job_desc.get('duties', '未知')}
- 技能要求：{job_desc.get('qualifications_skills', '未知')}

各维度得分：
{chr(10).join(dimension_info)}

分析要求：
1. 如果人岗匹配率较高（>=80%）但员工个人分数偏低（<70分），建议提高个人技能，根据岗位提出具体要求
2. 如果人岗匹配率较低（<80%），分析哪个维度差距最大，根据缺少的维度提出针对性建议
3. 建议要具体、可操作，结合岗位要求和员工现状
4. 给出3-5条具体建议

请返回格式：
建议：
1. [具体建议1]
2. [具体建议2]
3. [具体建议3]
4. [具体建议4]
5. [具体建议5]

不要返回其他内容。"""
        
        try:
            response = requests.post(
                LLM_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {LLM_API_KEY}"
                },
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是一个专业的HR分析师，擅长根据人岗匹配数据给出具体的发展建议。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500
                },
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                
                # 解析大模型返回的建议
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('1.') or line.startswith('2.') or line.startswith('3.') or line.startswith('4.') or line.startswith('5.'):
                        # 提取建议内容
                        suggestion = line.split('.', 1)[1].strip()
                        if suggestion:
                            recommendations.append(suggestion)
        except Exception as e:
            # 如果大模型调用失败，使用默认逻辑
            pass
    
    # 如果大模型没有返回建议，使用默认逻辑
    if not recommendations:
        # 根据差距生成建议
        for dim in gap_dims[:2]:  # 取差距最大的前2个
            gap = dim.job_requirement - dim.score
            if gap > 10:
                if dim.name == "专业能力":
                    recommendations.append(f"重点提升专业能力：建议参加技能培训，考取相关职称证书")
                elif dim.name == "经验":
                    recommendations.append(f"积累经验：建议多参与项目实践，向资深同事学习")
                elif dim.name == "创新能力":
                    recommendations.append(f"培养创新思维：建议参与创新项目，积极申请专利")
                elif dim.name == "学习能力":
                    recommendations.append(f"加强学习：建议制定学习计划，提升学历或专业技能")
                elif dim.name == "工作态度":
                    recommendations.append(f"改善工作态度：注意考勤纪律，提高工作积极性")
        
        if not recommendations:
            if overall_score >= 85:
                recommendations.append("继续保持优秀表现，争取晋升机会")
                recommendations.append("可考虑担任导师，帮助团队其他成员成长")
            else:
                recommendations.append("继续保持良好表现，争取更高绩效")
    
    return conclusion, evaluation, recommendations


def generate_quadrant_data(dimensions: List[DimensionScore], overall_score: float, job_requirement_score: float) -> Dict:
    """
    生成四象限图数据
    象限划分：
    - 第一象限（右上）：高能力高匹配 - 核心人才
    - 第二象限（左上）：高能力低匹配 - 潜力人才
    - 第三象限（左下）：低能力低匹配 - 待观察
    - 第四象限（右下）：低能力高匹配 - 稳定贡献者
    """
    # 计算能力指数（综合得分的归一化）
    ability_index = overall_score / 100  # 0-1
    
    # 计算匹配度指数（员工得分与岗位要求的比值）
    if job_requirement_score > 0:
        match_index = overall_score / job_requirement_score
    else:
        match_index = 1.0
    
    # 确定象限
    if ability_index >= 0.75 and match_index >= 0.9:
        quadrant = "第一象限"
        quadrant_name = "核心人才区"
        quadrant_desc = "能力优秀且与岗位高度匹配，是团队的核心骨干"
        color = "#52c41a"  # 绿色
    elif ability_index >= 0.75 and match_index < 0.9:
        quadrant = "第二象限"
        quadrant_name = "潜力人才区"
        quadrant_desc = "能力优秀但与当前岗位匹配度有差距，建议调整岗位或拓展职责"
        color = "#1890ff"  # 蓝色
    elif ability_index < 0.75 and match_index < 0.9:
        quadrant = "第三象限"
        quadrant_name = "待发展区"
        quadrant_desc = "能力和匹配度都有待提升，需要重点关注和培养"
        color = "#faad14"  # 橙色
    else:
        quadrant = "第四象限"
        quadrant_name = "稳定贡献区"
        quadrant_desc = "能力符合岗位要求，能稳定完成工作，是团队的稳定力量"
        color = "#722ed1"  # 紫色
    
    return {
        "quadrant": quadrant,
        "quadrant_name": quadrant_name,
        "quadrant_desc": quadrant_desc,
        "color": color,
        "ability_index": round(ability_index * 100, 1),  # 能力指数 0-100
        "match_index": round(match_index * 100, 1),  # 匹配度指数
        "x": round(match_index * 100, 1),  # X轴：匹配度
        "y": round(ability_index * 100, 1),  # Y轴：能力指数
        "center_x": 90,  # 中心点X（岗位要求）
        "center_y": 75   # 中心点Y（能力基准）
    }


def generate_radar_data(dimensions: List[DimensionScore]) -> Dict:
    """生成雷达图数据"""
    categories = [d.name for d in dimensions]
    
    # 员工实际得分
    employee_scores = [round(d.score, 1) for d in dimensions]
    
    # 岗位要求得分
    job_requirements = [round(d.job_requirement, 1) for d in dimensions]
    
    # 计算每个维度的差距
    gaps = [round(d.job_requirement - d.score, 1) for d in dimensions]
    
    return {
        "categories": categories,
        "employee_scores": employee_scores,
        "job_requirements": job_requirements,
        "gaps": gaps,
        "max_scale": 100
    }


def generate_gap_analysis(dimensions: List[DimensionScore]) -> List[Dict]:
    """生成详细的差距分析"""
    analysis = []
    
    for dim in dimensions:
        gap = dim.score - dim.job_requirement
        
        if gap < -15:
            level = "严重不足"
            color = "#ff4d4f"
            suggestion = f"急需提升，建议制定专项培训计划"
        elif gap < -5:
            level = "有待提升"
            color = "#faad14"
            suggestion = f"存在差距，建议针对性学习提升"
        elif gap < 5:
            level = "基本匹配"
            color = "#52c41a"
            suggestion = f"符合要求，继续保持"
        else:
            level = "超出要求"
            color = "#1890ff"
            suggestion = f"表现优秀，可作为团队标杆"
        
        analysis.append({
            "dimension": dim.name,
            "employee_score": round(dim.score, 1),
            "job_requirement": round(dim.job_requirement, 1),
            "gap": round(gap, 1),
            "weight": dim.weight,
            "level": level,
            "color": color,
            "suggestion": suggestion,
            "description": dim.description
        })
    
    # 按差距从大到小排序
    analysis.sort(key=lambda x: x["gap"], reverse=True)
    
    return analysis


@router.post("/analyze")
async def analyze_alignment(request: AlignmentAnalyzeRequest):
    """
    人岗适配分析
    基于6维度模型：专业能力(30%)、经验(10%)、战略匹配(10%)、学习能力(20%)、工作态度(20%)、价值贡献(10%)
    """
    logger.info(f"[Alignment] 开始人岗适配分析，员工: {request.employee_name}")
    
    db = SessionLocal()
    try:
        # 1. 获取员工信息
        emp_info = get_employee_info(db, request.employee_name)
        if not emp_info:
            return {
                "success": False,
                "message": f"未找到员工: {request.employee_name}"
            }
        
        # 2. 获取岗位描述
        position_name = request.position_name or emp_info.get('position', '')
        job_desc = get_job_description(db, position_name, emp_info['emp_name']) if position_name else None
        
        # 3. 获取考勤数据
        attendance = get_attendance_summary(db, emp_info['emp_code'])
        
        # 4. 计算6维度得分
        dimensions = []
        
        # 维度1: 专业能力（权重30%）
        prof_score, prof_req, prof_emp_reason, prof_job_reason = calculate_professional_ability_score(emp_info, job_desc or {}, db)
        dimensions.append(DimensionScore(
            name="专业能力",
            score=prof_score,
            weight=30,
            job_requirement=prof_req,
            description="基于绩效、专家聘任、职称证书、职业技能",
            employee_reason=prof_emp_reason,
            job_reason=prof_job_reason
        ))
        
        # 维度2: 经验（权重10%）
        exp_score, exp_req, exp_emp_reason, exp_job_reason = calculate_experience_score(emp_info, job_desc or {}, db)
        dimensions.append(DimensionScore(
            name="经验",
            score=exp_score,
            weight=10,
            job_requirement=exp_req,
            description="基于本专业/相关专业工作年限",
            employee_reason=exp_emp_reason,
            job_reason=exp_job_reason
        ))
        
        # 维度3: 创新能力（权重10%）- 基于录音和提问评估
        innovation_score, innovation_req, innovation_emp_reason, innovation_job_reason = await calculate_innovation_score_from_interview(
            emp_info, job_desc or {}, db, request.innovation_audio_file, request.innovation_questions_file
        )
        dimensions.append(DimensionScore(
            name="创新能力",
            score=innovation_score,
            weight=10,
            job_requirement=innovation_req,
            description="基于面试录音和提问回答评估创新能力",
            employee_reason=innovation_emp_reason,
            job_reason=innovation_job_reason
        ))
        
        # 维度4: 学习能力（权重20%）- 复用创新能力的录音和提问文件进行综合评价
        learn_score, learn_req, learn_emp_reason, learn_job_reason = await calculate_learning_score(
            emp_info, job_desc or {}, db, request.innovation_audio_file, request.innovation_questions_file
        )
        dimensions.append(DimensionScore(
            name="学习能力",
            score=learn_score,
            weight=20,
            job_requirement=learn_req,
            description="基于学历、持续学习、谈话录音综合评价",
            employee_reason=learn_emp_reason,
            job_reason=learn_job_reason
        ))
        
        # 维度5: 工作态度（权重20%）
        attitude_score, attitude_req, attitude_emp_reason, attitude_job_reason = calculate_attitude_score(attendance, job_desc or {}, emp_info)
        dimensions.append(DimensionScore(
            name="工作态度",
            score=attitude_score,
            weight=20,
            job_requirement=attitude_req,
            description="基于考勤数据（迟到、早退、加班）",
            employee_reason=attitude_emp_reason,
            job_reason=attitude_job_reason
        ))
        
        # 维度6: 价值贡献（权重10%）
        value_score, value_req, value_emp_reason, value_job_reason = calculate_value_contribution_score(emp_info, job_desc or {}, db)
        dimensions.append(DimensionScore(
            name="价值贡献",
            score=value_score,
            weight=10,
            job_requirement=value_req,
            description="基于绩效酬金偏离度",
            employee_reason=value_emp_reason,
            job_reason=value_job_reason
        ))
        
        # 5. 计算综合得分（加权平均）
        overall_score = sum(float(d.score) * d.weight / 100 for d in dimensions)
        job_requirement_score = sum(float(d.job_requirement) * d.weight / 100 for d in dimensions)
        
        # 6. 生成结论和建议
        conclusion, evaluation, recommendations = generate_conclusion(dimensions, overall_score, job_requirement_score, emp_info, job_desc)
        
        # 7. 生成四象限图数据
        quadrant_data = generate_quadrant_data(dimensions, overall_score, job_requirement_score)
        
        # 8. 生成雷达图数据
        radar_data = generate_radar_data(dimensions)
        
        # 9. 生成差距分析
        gap_analysis = generate_gap_analysis(dimensions)
        
        logger.info(f"[Alignment] 分析完成，员工: {emp_info['emp_name']}, 综合得分: {overall_score:.1f}, 象限: {quadrant_data['quadrant_name']}")
        
        return {
            "success": True,
            "data": {
                "employee_name": emp_info['emp_name'],
                "employee_code": emp_info['emp_code'],
                "department": emp_info['department'],
                "position": emp_info['position'],
                "overall_score": overall_score,
                "job_requirement_score": job_requirement_score,
                "dimensions": [d.dict() for d in dimensions],
                "attendance": attendance,
                "conclusion": conclusion,
                "evaluation": evaluation,
                "recommendations": recommendations,
                "quadrant": quadrant_data,
                "radar_data": radar_data,
                "gap_analysis": gap_analysis
            }
        }
        
    except Exception as e:
        logger.error(f"[Alignment] 分析失败: {str(e)}")
        return {
            "success": False,
            "message": f"分析失败: {str(e)}"
        }
    finally:
        db.close()


@router.get("/dimensions")
async def get_alignment_dimensions():
    """
    获取人岗适配分析维度说明
    """
    return {
        "success": True,
        "dimensions": [
            {
                "name": "专业能力",
                "weight": 25,
                "description": "基于绩效、专家聘任、职称证书、职业技能",
                "criteria": [
                    "基础分70分",
                    "绩效：3年内年度绩效，一次优秀得10分，一次基本称职扣10分",
                    "专家聘任：公司专家10分，高级专家15分，首席专家20分",
                    "职称证书：A级10分、B级7分、C级5分",
                    "职业技能：A级7分、B级5分、C级3分"
                ]
            },
            {
                "name": "经验",
                "weight": 10,
                "description": "基于工作年限",
                "criteria": [
                    "基础分70分",
                    "3年：70分",
                    "5年：80分",
                    "8年：90分",
                    "10年以上：100分"
                ]
            },
            {
                "name": "创新能力",
                "weight": 10,
                "description": "基于面试录音和提问回答评估",
                "criteria": [
                    "满分100分",
                    "根据谈话录音，结合岗位说明书的要求，进行综合打分",
                    "重点关注：创新思维、问题解决能力、提出改进建议的能力、学习新知识的意愿",
                    "可选上传：面试录音文件（wav/mp3）、提问问题Excel"
                ]
            },
            {
                "name": "学习能力",
                "weight": 20,
                "description": "基于学历、持续学习",
                "criteria": [
                    "博士：90-100分",
                    "硕士：80-90分",
                    "本科：70-80分",
                    "专升本：+2分",
                    "在职硕士：+6分",
                    "在职博士：+10分"
                ]
            },
            {
                "name": "工作态度",
                "weight": 20,
                "description": "基于考勤数据",
                "criteria": [
                    "基础分70分",
                    "迟到/早退：每月大于3次，3次以上每次扣1分，最多扣10分",
                    "加班：月度加班36小时以上，+20分",
                    "20:30后加班：+3分",
                    "党员：+5分"
                ]
            },
            {
                "name": "价值贡献",
                "weight": 10,
                "description": "基于绩效酬金偏离度",
                "criteria": [
                    "基础分70分，满分上限100分",
                    "偏离度为100%时，不加分、不扣分",
                    "偏离度较100%，每高出0.5个百分点，加3分",
                    "偏离度较100%，每低出0.5个百分点，扣3分"
                ]
            }
        ]
    }


# 文件大小限制（50MB）
MAX_FILE_SIZE = 50 * 1024 * 1024

class InnovationFileUploadRequest(BaseModel):
    """创新能力文件上传请求（Base64编码方式）"""
    filename: str
    file_type: str  # innovation_audio 或 innovation_questions
    file_content_base64: str  # Base64编码的文件内容


@router.post("/upload/innovation-file")
async def upload_innovation_file(
    file: UploadFile = File(...),
    file_type: str = Form(...)
):
    """
    上传创新能力评估文件（录音或提问问题）- 传统multipart方式
    
    Args:
        file: 上传的文件
        file_type: 文件类型，可选值：innovation_audio, innovation_questions
    
    Returns:
        文件路径信息
    """
    try:
        logger.info(f"[InnovationUpload] 开始处理文件上传: {file.filename}, 类型: {file_type}")
        
        # 验证文件类型
        allowed_audio_types = ['.wav', '.mp3', '.m4a', '.mp4']
        allowed_doc_types = ['.xlsx', '.xls', '.csv', '.txt']
        
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_type == 'innovation_audio':
            if file_ext not in allowed_audio_types:
                return {
                    "success": False,
                    "message": f"不支持的音频格式，请上传 {', '.join(allowed_audio_types)} 格式的文件"
                }
        elif file_type == 'innovation_questions':
            if file_ext not in allowed_doc_types:
                return {
                    "success": False,
                    "message": f"不支持的文档格式，请上传 {', '.join(allowed_doc_types)} 格式的文件"
                }
        else:
            return {
                "success": False,
                "message": "无效的文件类型"
            }
        
        # 获取上传目录
        upload_dir = get_innovation_upload_dir()
        
        # 生成唯一文件名
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # 流式保存文件，避免内存溢出
        logger.info(f"[InnovationUpload] 开始保存文件: {file.filename}")
        total_size = 0
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 每次读取1MB
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    os.remove(file_path)
                    return {
                        "success": False,
                        "message": f"文件大小超过限制（最大{MAX_FILE_SIZE // (1024*1024)}MB）"
                    }
                f.write(chunk)
        
        logger.info(f"[InnovationUpload] 文件上传成功: {file.filename} -> {file_path}, 大小: {total_size} bytes")
        
        return {
            "success": True,
            "message": "文件上传成功",
            "file_path": file_path,
            "original_name": file.filename,
            "file_type": file_type
        }
        
    except Exception as e:
        logger.error(f"[InnovationUpload] 文件上传失败: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"文件上传失败: {str(e)}"
        }


@router.post("/upload/innovation-file-base64")
async def upload_innovation_file_base64(request: InnovationFileUploadRequest):
    """
    上传创新能力评估文件（Base64编码方式）- 用于绕过multipart/form-data限制
    
    Args:
        request: 包含文件名、文件类型和Base64编码内容的请求
    
    Returns:
        文件路径信息
    """
    try:
        logger.info(f"[InnovationUpload-Base64] 开始处理文件上传: {request.filename}, 类型: {request.file_type}")
        
        # 验证文件类型
        allowed_audio_types = ['.wav', '.mp3', '.m4a', '.mp4']
        allowed_doc_types = ['.xlsx', '.xls', '.csv', '.txt']
        
        file_ext = os.path.splitext(request.filename)[1].lower()
        
        if request.file_type == 'innovation_audio':
            if file_ext not in allowed_audio_types:
                return {
                    "success": False,
                    "message": f"不支持的音频格式，请上传 {', '.join(allowed_audio_types)} 格式的文件"
                }
        elif request.file_type == 'innovation_questions':
            if file_ext not in allowed_doc_types:
                return {
                    "success": False,
                    "message": f"不支持的文档格式，请上传 {', '.join(allowed_doc_types)} 格式的文件"
                }
        else:
            return {
                "success": False,
                "message": "无效的文件类型"
            }
        
        # 解码Base64内容
        import base64
        try:
            file_content = base64.b64decode(request.file_content_base64)
        except Exception as e:
            return {
                "success": False,
                "message": f"Base64解码失败: {str(e)}"
            }
        
        total_size = len(file_content)
        if total_size > MAX_FILE_SIZE:
            return {
                "success": False,
                "message": f"文件大小超过限制（最大{MAX_FILE_SIZE // (1024*1024)}MB）"
            }
        
        # 获取上传目录
        upload_dir = get_innovation_upload_dir()
        
        # 生成唯一文件名
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # 保存文件
        logger.info(f"[InnovationUpload-Base64] 开始保存文件: {request.filename}, 大小: {total_size} bytes")
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"[InnovationUpload-Base64] 文件上传成功: {request.filename} -> {file_path}")
        
        return {
            "success": True,
            "message": "文件上传成功",
            "file_path": file_path,
            "original_name": request.filename,
            "file_type": request.file_type
        }
        
    except Exception as e:
        logger.error(f"[InnovationUpload-Base64] 文件上传失败: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"文件上传失败: {str(e)}"
        }
