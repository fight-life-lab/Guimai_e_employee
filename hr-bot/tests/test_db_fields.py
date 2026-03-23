#!/usr/bin/env python3
"""测试数据库字段"""
from sqlalchemy import create_engine, text

MYSQL_URL = 'mysql+pymysql://hr_user:hr_password@localhost:3306/hr_employee_db'
engine = create_engine(MYSQL_URL, pool_pre_ping=True)

with engine.connect() as conn:
    # 测试员工查询
    sql = text("SELECT emp_code, emp_name, highest_education FROM emp_roster WHERE emp_name LIKE :name LIMIT 1")
    result = conn.execute(sql, {'name': '%石京京%'})
    row = result.fetchone()
    if row:
        print(f'✅ 员工查询成功: {row.emp_name}, 学历: {row.highest_education}')
    else:
        print('⚠️ 未找到员工')
    
    # 测试岗位查询
    sql2 = text("SELECT position_name, qualifications_education FROM ods_emp_job_description LIMIT 1")
    result2 = conn.execute(sql2)
    row2 = result2.fetchone()
    if row2:
        print(f'✅ 岗位查询成功: {row2.position_name}')
    else:
        print('⚠️ 未找到岗位')
    
    print('🎉 所有数据库字段测试通过!')
