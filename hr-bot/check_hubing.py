#!/usr/bin/env python3
"""查询胡冰的专业能力数据"""
from sqlalchemy import create_engine, text

engine = create_engine('mysql+pymysql://hr_user:hr_password@localhost:3306/hr_employee_db', pool_pre_ping=True)

with engine.connect() as conn:
    # 先查找胡冰的员工编号
    result = conn.execute(text("SELECT emp_code, emp_name FROM emp_roster WHERE emp_name LIKE '%胡冰%'"))
    emp = result.fetchone()
    if emp:
        print(f'员工: {emp.emp_name} ({emp.emp_code})')
        
        # 查询专业能力数据
        result2 = conn.execute(text("SELECT * FROM ods_emp_professional_ability WHERE emp_code = :code"), {'code': emp.emp_code})
        prof = result2.fetchone()
        if prof:
            print(f'\n专业能力数据:')
            print(f'试用期分数: {prof.probation_score}')
            print(f'绩效历史: {prof.performance_history}')
            print(f'公司专家: {prof.is_company_expert}')
            print(f'高级专家: {prof.is_senior_expert}')
            print(f'首席专家: {prof.is_chief_expert}')
            print(f'职称: {prof.professional_titles}')
            print(f'技能: {prof.professional_skills}')
        else:
            print('\n未找到专业能力数据')
    else:
        print('未找到胡冰')
