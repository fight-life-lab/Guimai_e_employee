#!/usr/bin/env python3
"""
创建员工专业能力表
通过SQLAlchemy直接在MySQL中创建表
"""
import sys
sys.path.insert(0, '/root/shijingjing/e-employee/hr-bot')

from sqlalchemy import create_engine, text
from app.models.emp_professional_ability import EmpProfessionalAbility
from app.database import Base

# MySQL配置
MYSQL_URL = "mysql+pymysql://hr_user:hr_password@localhost:3306/hr_employee_db"

def create_table():
    """创建表"""
    engine = create_engine(MYSQL_URL, pool_pre_ping=True)
    
    # 创建表
    Base.metadata.create_all(bind=engine, tables=[EmpProfessionalAbility.__table__])
    print("✅ 员工专业能力表创建成功！")
    
    # 验证表是否存在
    with engine.connect() as conn:
        result = conn.execute(text("SHOW TABLES LIKE 'ods_emp_professional_ability'"))
        if result.fetchone():
            print("✅ 表验证成功：ods_emp_professional_ability 已存在")
        else:
            print("❌ 表验证失败")

if __name__ == "__main__":
    create_table()
