#!/usr/bin/env python3
"""查询胡冰的详细数据"""
import pymysql

conn = pymysql.connect(
    host='localhost',
    port=3306,
    user='hr_user',
    password='hr_password',
    database='hr_employee_db',
    charset='utf8mb4'
)

try:
    with conn.cursor() as cursor:
        # 查找胡冰
        cursor.execute("SELECT emp_code, emp_name FROM emp_roster WHERE emp_name LIKE '%胡冰%'")
        emp = cursor.fetchone()
        if emp:
            print(f'员工: {emp[1]} ({emp[0]})')
            
            # 查询专业能力数据
            cursor.execute("""
                SELECT 
                    emp_code, emp_name, probation_score, performance_history,
                    is_company_expert, is_senior_expert, is_chief_expert,
                    professional_titles, professional_skills, patents_count,
                    created_at, updated_at
                FROM ods_emp_professional_ability 
                WHERE emp_code = %s
            """, (emp[0],))
            prof = cursor.fetchone()
            if prof:
                print(f'\n创建时间: {prof[10]}')
                print(f'更新时间: {prof[11]}')
                print(f'试用期分数: {prof[2]}')
                print(f'绩效历史: {prof[3]}')
                print(f'公司专家: {prof[4]}')
                print(f'高级专家: {prof[5]}')
                print(f'首席专家: {prof[6]}')
                print(f'职称: {prof[7]}')
                print(f'技能: {prof[8]}')
                print(f'专利数: {prof[9]}')
            else:
                print('\n未找到专业能力数据')
        else:
            print('未找到胡冰')
finally:
    conn.close()
