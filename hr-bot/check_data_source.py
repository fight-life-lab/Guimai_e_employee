#!/usr/bin/env python3
"""查询专业能力数据的来源和时间"""
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
        print("=" * 60)
        print("1. 查询胡冰的完整数据（含创建时间）")
        print("=" * 60)
        
        cursor.execute("SELECT emp_code, emp_name FROM emp_roster WHERE emp_name LIKE '%胡冰%'")
        emp = cursor.fetchone()
        if emp:
            print(f'员工: {emp[1]} ({emp[0]})')
            
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
            else:
                print('\n未找到专业能力数据')
        else:
            print('未找到胡冰')
        
        print("\n" + "=" * 60)
        print("2. 查询所有有绩效数据的员工")
        print("=" * 60)
        
        cursor.execute("""
            SELECT 
                emp_code, emp_name, performance_history, created_at, updated_at
            FROM ods_emp_professional_ability 
            WHERE performance_history IS NOT NULL 
              AND performance_history != '[]'
              AND performance_history != ''
            ORDER BY updated_at DESC
        """)
        
        rows = cursor.fetchall()
        print(f"共有 {len(rows)} 条有绩效数据的记录:\n")
        
        for row in rows:
            print(f"  {row[1]} ({row[0]})")
            print(f"    绩效: {row[2]}")
            print(f"    更新: {row[4]}")
            print()
        
        print("=" * 60)
        print("3. 查询所有有试用期分数的员工")
        print("=" * 60)
        
        cursor.execute("""
            SELECT 
                emp_code, emp_name, probation_score, created_at, updated_at
            FROM ods_emp_professional_ability 
            WHERE probation_score IS NOT NULL
            ORDER BY updated_at DESC
        """)
        
        rows4 = cursor.fetchall()
        print(f"共有 {len(rows4)} 条有试用期分数的记录:\n")
        
        for row in rows4:
            print(f"  {row[1]} ({row[0]}): {row[2]}分")
            print(f"    更新: {row[4]}")

finally:
    conn.close()
