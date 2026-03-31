"""
人岗适配分析API
基于5维度模型进行员工与岗位的匹配度分析
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging

router = APIRouter(prefix="/api/v1/alignment", tags=["人岗适配分析"])

logger = logging.getLogger(__name__)

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
               entry_date, job_level, work_years, company_years
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
            'company_years': row.company_years
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
    基于：试用期分数、绩效、专家聘任、职称证书、职业技能
    规则：
    - 基础分70分
    - 绩效（二选一）：试用期>=80加10分，<80减5分；或3年内年度绩效一次优秀+15分，一次基本称职-15分
    - 专家聘任：公司专家+10分，高级专家+15分，首席专家+20分
    - 职称证书：A级+10分，B级+7分，C级+5分，多项取高
    - 职业技能：A级+7分，B级+5分，C级+3分，累计不超过14分
    """
    from app.models.emp_professional_ability import EmpProfessionalAbility
    
    score = 70  # 基础分70分
    reasons = ["基础分70分"]
    
    emp_code = emp_info.get('emp_code')
    
    # 从数据库获取员工专业能力数据
    prof_ability = None
    if db and emp_code:
        prof_ability = db.query(EmpProfessionalAbility).filter(
            EmpProfessionalAbility.emp_code == emp_code
        ).first()
    
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
                # 只统计2023、2024、2025年的绩效
                valid_years = ['2023', '2024', '2022']
                for perf in perf_history:
                    year = str(perf.get('year', ''))
                    if year in valid_years:
                        level = str(perf.get('level', '')).lower()
                        if '优秀' in level or 'a' in level or 'p1' in level:
                            excellent_count += 1
                        elif '基本称职' in level or 'c' in level:
                            basic_count += 1
                
                if excellent_count > 0:
                    performance_bonus = 15 * excellent_count
                    performance_reason = f"2022-2024年{excellent_count}次年度绩效优秀，+{performance_bonus}分"
                elif basic_count > 0:
                    performance_bonus = -10 * basic_count
                    performance_reason = f"2022-2024年{basic_count}次年度绩效基本称职，{performance_bonus}分"
        
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

    if len(reasons) ==1:
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
    基于：从事本专业或相关专业的工作年限
    工作年限权重为0.6   荣誉是0.4
    
    评分标准：
    - 3年：70分
    - 5年：80分
    - 8年：90分
    - 10年以上：100分

    荣誉
    （1）国家级荣誉：20分
    （2）省部级荣誉：15分
    （3）集团级荣誉：10分
    （4）公司级荣誉：5分
    """
    experience_dict  = {'work_experiences': 0.8,'honer':0.2}
    from datetime import datetime, date
    from app.models.emp_work_experience import EmpWorkExperience
    
    emp_code = emp_info.get('emp_code')
    current_position = emp_info.get('position', '')
    
    # 从岗位描述中提取相关关键词
    related_keywords = []
    if job_desc:
        # 从岗位名称、职责、技能要求中提取关键词
        position_name = job_desc.get('position_name', '')
        duties = job_desc.get('duties', '')
        skills = job_desc.get('qualifications_skills', '')
        
        # 合并所有文本并提取关键词
        all_text = f"{position_name} {duties} {skills}".lower()
        
        # 提取技术/专业关键词（可以根据实际需求扩展）
        tech_keywords = [
            'java', 'python', '前端', '后端', '开发', '工程师', '架构', '测试',
            '运维', '产品', '设计', '运营', '销售', '市场', '人力', '财务',
            'java', 'python', '前端', '后端', '开发', '工程师', '架构', '测试',
            '运维', '产品', '设计', '运营', '销售', '市场', '人力', '财务',
            'h5', 'web', 'app', '小程序', '大数据', 'ai', '人工智能', '算法',
            '数据库', '网络', '安全', '云计算', 'devops', '敏捷', '项目管理'
        ]
        
        for keyword in tech_keywords:
            if keyword in all_text:
                related_keywords.append(keyword)
    
    # 如果没有提取到关键词，使用当前岗位名称作为关键词
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
            
            # 计算这段工作的时长
            start_date = exp.start_date
            end_date = exp.end_date if exp.end_date else today
            
            # 计算工作时长（年）
            duration_days = (end_date - start_date).days
            duration_years = duration_days / 365.0
            
            total_years += duration_years
            
            # 判断是否与当前岗位相关
            is_relevant = False
            
            # 优先使用大模型的判断结果
            if llm_relevant_indices:
                is_relevant = idx in llm_relevant_indices
            else:
                # 大模型调用失败，使用备用逻辑（关键词匹配）
                position_text = (exp.position or '').lower()
                company_text = (exp.company_name or '').lower()
                dept_text = (exp.department or '').lower()
                
                # 检查是否包含相关关键词
                for keyword in related_keywords:
                    if keyword in position_text or keyword in company_text or keyword in dept_text:
                        is_relevant = True
                        break
                
                # 如果在天翼视讯/国脉等公司工作，且岗位是技术/开发相关，也算相关
                if not is_relevant:
                    company_keywords = ['天翼', '视讯', '国脉', '电信', '传媒', '科技']
                    position_keywords = ['开发', '工程师', '技术', '研发', '前端', '后端', '测试', '运维', '架构']
                    
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
    # experience_dict = {'work_experiences': 0.6, 'honer': 0.4}
    work_score = score * experience_dict['work_experiences']
    # 构建员工得分理由
    if relevant_experiences:
        exp_details = []
        for exp in relevant_experiences[:3]:  # 只显示前3条
            exp_details.append(f"{exp['company']}({exp['duration']:.1f}年)")
        
        employee_reason = f"相关专业工作年限{relevant_years:.1f}年（{level}），其中相关经历：{'；'.join(exp_details)},按年限档次得{work_score}分"
    else:
        if relevant_years > 0:
            employee_reason = f"相关专业工作年限{relevant_years:.1f}年（{level}，按年限档次得{work_score}分"
        else:
            employee_reason = f"总工作年限{total_years:.1f}年，未能识别相关专业经历,按年限档次得{work_score}分"
    
    # 基于岗位说明书确定经验要求
    qual_exp = job_desc.get('qualifications_job_work_experience') if job_desc else None
    
    job_requirement = 75  # 默认要求3-5年
    job_reason_parts = []
    
    if qual_exp:
        exp_str = str(qual_exp)
        import re
        years_match = re.search(r'(\d+)', exp_str)
        if years_match:
            req_years = int(years_match.group(1))
            if req_years >= 10:
                job_requirement = 100
            elif req_years >= 8:
                job_requirement = 90
            elif req_years >= 5:
                job_requirement = 80
            elif req_years >= 3:
                job_requirement = 70
            else:
                job_requirement = 60
            job_reason_parts.append(f"要求{req_years}年以上本专业经验")
        else:
            job_reason_parts.append("要求相关专业工作经验")
    else:
        job_reason_parts.append("要求3-5年本专业经验")
    
    # 2. 计算荣誉奖项得分
    honor_score = 0
    honor_reasons = []
    
    if db and emp_code:
        from app.models.emp_professional_ability import EmpProfessionalAbility
        import json
        prof_ability = db.query(EmpProfessionalAbility).filter(
            EmpProfessionalAbility.emp_code == emp_code
        ).first()
        
        if prof_ability and prof_ability.honors:
            honors = prof_ability.honors
            # 如果是字符串，尝试解析成JSON
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
                        points =  experience_dict[honor_level] * points
                        honor_score += points
                        honor_reasons.append(f"{honor_name}({level_name}+{points}分)")
    
    # 荣誉得分最高不超过10分
    honor_score = min(honor_score, 40 )
    
    # 3. 汇总得分（工作年限得分 * 0.4 + 荣誉得分 * 0.6，最高100分）
    # total_score = min(score * 0.4 + honor_score * 0.6, 100)
    total_score = work_score + honor_score
    
    # 构建员工得分理由
    if relevant_experiences:
        exp_details = []
        for exp in relevant_experiences[:3]:  # 只显示前3条
            exp_details.append(f"{exp['company']}({exp['duration']:.1f}年)")
        
        employee_reason = f"相关专业工作年限{relevant_years:.1f}年（{level}），其中相关经历：{'；'.join(exp_details)},按照年限得分{work_score}分"
    else:
        if relevant_years > 0:
            employee_reason = f"相关专业工作年限{relevant_years:.1f}年（{level}）按照年限得分{work_score}分"
        else:
            employee_reason = f"总工作年限{total_years:.1f}年，未能识别相关专业经历，按照年限得分{work_score}分"
    
    # 添加荣誉奖项理由
    if honor_reasons:
        employee_reason += f"；荣誉奖项：{'、'.join(honor_reasons[:3])}，荣誉加分{honor_score}分"
    
    # employee_reason += f"。累计得分{honor_score}分"
    
    # 精简岗位理由
    if job_reason_parts:
        job_reason = f"要求：{ '，'.join(job_reason_parts) }，标准分{job_requirement}分"
    else:
        job_reason = f"要求：3-5年本专业工作经验，标准分{job_requirement}分"
    
    return total_score, job_requirement, employee_reason, job_reason


def calculate_strategic_alignment_score(emp_info: dict, job_desc: dict, db) -> tuple:
    """
    计算战略匹配维度得分（权重15%）
    基于：员工战略匹配评分
    
    评分标准：
    - 紧密关联：≥90分
    - 一般关联：80分≤关联度≤90分
    - 较差关联：<80分
    """
    from app.models.strategic_alignment import StrategicAlignmentScore
    from datetime import datetime
    
    emp_code = emp_info.get('emp_code')
    
    # 从数据库获取员工战略匹配分数
    score_record = None
    if db and emp_code:
        current_year = datetime.now().year
        score_record = db.query(StrategicAlignmentScore).filter(
            StrategicAlignmentScore.emp_code == emp_code,
            StrategicAlignmentScore.evaluation_year == current_year
        ).first()
    
    if score_record:
        score = score_record.score
        employee_reason = f"战略匹配评分{score}分，由{score_record.evaluator or '部门负责人'}评定"
    else:
        # 如果没有找到记录，使用默认分数
        score = 70.0
        employee_reason = "暂无战略匹配评分数据，默认70分"
    
    # 岗位战略匹配要求（默认80分）
    job_requirement = 80.0
    job_reason = "岗位要求员工工作内容与公司战略及部门年度重点工作直接相关，或参与所在部门年度专项任务并承担明确职责"
    
    return score, job_requirement, employee_reason, job_reason


def calculate_value_contribution_score(emp_info: dict, job_desc: dict, db) -> tuple:
    """
    计算价值贡献维度得分（权重10%）
    基于：绩效酬金偏离度
    
    计分规则：
    - 基础分70分，满分上限100分
    - 偏离度为100%时，不加分、不扣分
    - 偏离度较100%，每高出0.5个百分点，加3分
    - 偏离度较100%，每低出0.5个百分点，扣3分
    """
    from app.models.value_contribution import ValueContributionScore
    from datetime import datetime
    
    emp_code = emp_info.get('emp_code')
    
    # 从数据库获取员工价值贡献分数
    score_record = None
    if db and emp_code:
        current_year = datetime.now().year
        score_record = db.query(ValueContributionScore).filter(
            ValueContributionScore.emp_code == emp_code,
            ValueContributionScore.evaluation_year == current_year
        ).first()
    
    if score_record:
        score = score_record.score
        deviation_rate = score_record.deviation_rate or 100
        employee_reason = f"绩效酬金偏离度{deviation_rate}%，价值贡献评分{score}分"
    else:
        # 如果没有找到记录，使用默认分数
        score = 70.0
        employee_reason = "暂无价值贡献评分数据，默认70分"
    
    # 岗位价值贡献要求（默认80分）
    job_requirement = 80.0
    job_reason = "岗位要求员工绩效酬金偏离度达到100%，即实际发放绩效与标准绩效一致"
    
    return score, job_requirement, employee_reason, job_reason


def calculate_learning_score(emp_info: dict, job_desc: dict) -> tuple:
    """
    计算学习能力维度得分（权重20%）
    基于：学历、持续学习
    """
    import json
    education = emp_info.get('education') or ''
    school = emp_info.get('school') or ''
    school_type = emp_info.get('school_type') or ''
    highest_degree = emp_info.get('highest_degree') or ''
    major = emp_info.get('highest_degree_major') or ''
    reasons = []


    if  "学士" in highest_degree:
        base_score  = 60
        reasons.append(f"本科学历,基础分为{base_score}")
    elif "硕士" in highest_degree:
        base_score = 70
        reasons.append(f"硕士学历,基础分为{base_score}")
    elif '博士' in highest_degree:
        base_score = 80
        reasons.append(f"博士学历,基础分为{base_score}")
    elif '本科' in education and '无学位' in highest_degree:
        base_score = 55
        reasons.append(f"本科毕业，但无学位,基础分为{base_score}")
    elif '专科' in education:
        base_score = 55
        reasons.append(f"专科学校，基础分为{base_score}")
    else:
        base_score = 50
        reasons.append(f"专科以下，基础分为{base_score}")
    # 学历基础分
    add_score = 0
    if '985' in school_type or 'QS前50' in school_type:
        add_score = 20
        reasons.append(f"毕业学校为{education},为{school_type},加分{add_score}")
    elif '211' in school_type or 'QS前100' in school_type:
        add_score = 10
        reasons.append(f"毕业学校为{education},为{school_type},加分{add_score}")
    
    # 专业匹配加分
    if major and job_desc:
        qual_major = job_desc.get('qualifications_major')
        if qual_major:
            # 提取岗位要求的专业
            import json
            try:
                if isinstance(qual_major, str):
                    qual_major = json.loads(qual_major)
                job_major = qual_major.get('requirement', '')
                if job_major:
                    # 使用大模型判断专业匹配度
                    import requests
                    from app.config import get_settings
                    
                    settings = get_settings()
                    
                    # 构建提示词
                    prompt = f"""请判断以下员工的专业是否与岗位要求的专业匹配。

员工专业：{major}
岗位要求专业：{job_major}

请分析员工专业是否与岗位要求的专业匹配，返回"匹配"或"不匹配"。

判断标准：
1. 员工专业与岗位要求的专业名称完全相同
2. 员工专业与岗位要求的专业属于同一学科门类
3. 员工专业与岗位要求的专业在知识结构和技能要求上有较高的相关性

只返回"匹配"或"不匹配"，不要返回其他内容。"""
                    
                    # 调用大模型 API
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
                            if  '匹配' in content:
                                add_score += 5
                                reasons.append(f"员工是{major}，与岗位要求专业{job_major}匹配，加分5分")
                    except Exception as e:
                        # 如果大模型调用失败，跳过专业匹配加分
                        pass
            except Exception as e:
                # 如果解析失败，跳过专业匹配加分
                pass
    
    score = base_score + add_score

    
    employee_reason = "；".join(reasons) + f"，最终得分{score}分"
    
    # 基于岗位说明书确定学习要求
    qual_edu = job_desc.get('qualifications_education') if job_desc else None
    qual_major = job_desc.get('qualifications_major') if job_desc else None
    print('')

    job_reason_parts = []
    
    if qual_edu:
        edu_str = str(qual_edu)
        if '博士' in edu_str  :
            job_requirement= 80
            job_reason_parts.append("博士学历")
        elif '研究生' in edu_str:
            job_requirement= 70
            job_reason_parts.append("硕士及以上学历")
        elif '本科' in edu_str:
            job_requirement = 60
            job_reason_parts.append("本科及以上学历")
        else:
            job_requirement = 55
            job_reason_parts.append("大专及以上")
    else:
        job_requirement = 60
        job_reason_parts.append("未获取信息，默认为本科及以上学历")
    major  = json.loads(qual_major).get('requirement', '')
    if major and not '不限专业' in major:
        job_requirement += 5
        job_reason_parts.append(f"需要{major}相关专业")
    
    # 精简岗位理由
    job_reason = f"要求：{ '，'.join(job_reason_parts) }，标准分{job_requirement}分"
    
    return score, job_requirement, employee_reason, job_reason


def calculate_attitude_score(attendance: dict, job_desc: dict) -> tuple:
    """
    计算工作态度维度得分（权重20%）
    基于：考勤数据（迟到、早退、加班）
    """
    if not attendance:
        score = 70
        employee_reason = "基础分70分，暂无考勤数据"
    else:
        score = 70  # 基础分70分
        reasons = ["基础分70分"]
        
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
    
    # 工作态度要求相对固定，基于通用职业规范
    job_requirement = 70
    job_reason = "要求：遵守考勤纪律，积极主动，标准分70分"
    
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
    基于6维度模型：专业能力、经验、战略匹配、学习能力、工作态度、创新能力
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
        
        # 维度1: 专业能力（权重25%）
        prof_score, prof_req, prof_emp_reason, prof_job_reason = calculate_professional_ability_score(emp_info, job_desc or {}, db)
        dimensions.append(DimensionScore(
            name="专业能力",
            score=prof_score,
            weight=25,
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
        
        # 维度3: 战略匹配（权重15%）- 新增维度
        strategic_score, strategic_req, strategic_emp_reason, strategic_job_reason = calculate_strategic_alignment_score(emp_info, job_desc or {}, db)
        dimensions.append(DimensionScore(
            name="战略匹配",
            score=strategic_score,
            weight=15,
            job_requirement=strategic_req,
            description="基于战略匹配评分",
            employee_reason=strategic_emp_reason,
            job_reason=strategic_job_reason
        ))
        
        # 维度4: 学习能力（权重20%）
        learn_score, learn_req, learn_emp_reason, learn_job_reason = calculate_learning_score(emp_info, job_desc or {})
        dimensions.append(DimensionScore(
            name="学习能力",
            score=learn_score,
            weight=20,
            job_requirement=learn_req,
            description="基于学历、持续学习",
            employee_reason=learn_emp_reason,
            job_reason=learn_job_reason
        ))
        
        # 维度5: 工作态度（权重20%）
        attitude_score, attitude_req, attitude_emp_reason, attitude_job_reason = calculate_attitude_score(attendance, job_desc or {})
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
                "name": "战略匹配",
                "weight": 15,
                "description": "基于战略匹配评分",
                "criteria": [
                    "紧密关联：≥90分",
                    "一般关联：80分≤关联度≤90分",
                    "较差关联：<80分",
                    "由部门负责人综合评定"
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
