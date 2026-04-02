"""
创建战略匹配评分表
"""
from sqlalchemy import create_engine
from app.models.strategic_alignment import StrategicAlignmentScore
from app.models.value_contribution import ValueContributionScore
from app.models.emp_professional_ability import EmpProfessionalAbility

# MySQL数据库配置
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_DATABASE = "hr_employee_db"
MYSQL_USER = "hr_user"
MYSQL_PASSWORD = "hr_password"
MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# 创建引擎
engine = create_engine(MYSQL_URL, pool_pre_ping=True)

# 创建表
print("正在创建战略匹配评分表...")
StrategicAlignmentScore.__table__.create(engine, checkfirst=True)
print("战略匹配评分表创建成功！")

print("正在检查价值贡献表...")
ValueContributionScore.__table__.create(engine, checkfirst=True)
print("价值贡献表检查完成！")

print("正在检查员工专业能力表...")
EmpProfessionalAbility.__table__.create(engine, checkfirst=True)
print("员工专业能力表检查完成！")

print("所有表创建/检查完成！")
