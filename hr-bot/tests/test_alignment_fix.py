"""
人岗适配API修复测试脚本
测试数据库字段查询是否正确
"""
import sys
sys.path.insert(0, '/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# MySQL数据库配置
MYSQL_HOST = "121.229.172.161"
MYSQL_PORT = 3306
MYSQL_DATABASE = "hr_employee_db"
MYSQL_USER = "hr_user"
MYSQL_PASSWORD = "hr_password"
MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

def test_employee_query():
    """测试员工信息查询"""
    print("=" * 60)
    print("测试1: 员工信息查询")
    print("=" * 60)
    
    engine = create_engine(MYSQL_URL, pool_pre_ping=True)
    
    with engine.connect() as conn:
        sql = text("""
            SELECT emp_code, emp_name, dept_level1, dept_level2, position_name,
                   highest_education, highest_degree_school, highest_degree_school_type,
                   entry_date, job_level, work_years, company_years
            FROM emp_roster
            WHERE emp_name LIKE :emp_name
            LIMIT 1
        """)
        result = conn.execute(sql, {'emp_name': '%石京京%'})
        row = result.fetchone()
        
        if row:
            print(f"✅ 查询成功!")
            print(f"   员工编号: {row.emp_code}")
            print(f"   员工姓名: {row.emp_name}")
            print(f"   部门: {row.dept_level1} {row.dept_level2}")
            print(f"   岗位: {row.position_name}")
            print(f"   学历: {row.highest_education}")
            print(f"   学校: {row.highest_degree_school}")
            print(f"   职级: {row.job_level}")
            return True
        else:
            print(f"❌ 未找到员工")
            return False

def test_job_description_query():
    """测试岗位描述查询"""
    print("\n" + "=" * 60)
    print("测试2: 岗位描述查询")
    print("=" * 60)
    
    engine = create_engine(MYSQL_URL, pool_pre_ping=True)
    
    with engine.connect() as conn:
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
        result = conn.execute(sql, {'position_name': '%推荐算法%'})
        row = result.fetchone()
        
        if row:
            print(f"✅ 查询成功!")
            print(f"   岗位名称: {row.position_name}")
            print(f"   部门: {row.department}")
            print(f"   学历要求: {row.qualifications_education}")
            print(f"   专业要求: {row.qualifications_major}")
            print(f"   工作经验: {row.qualifications_job_work_experience}")
            return True
        else:
            print(f"⚠️ 未找到岗位描述（可能是没有该岗位数据）")
            # 查询所有岗位
            result = conn.execute(text("SELECT position_name FROM ods_emp_job_description LIMIT 5"))
            rows = result.fetchall()
            if rows:
                print(f"   数据库中的岗位: {[r.position_name for r in rows]}")
            return True  # 没有数据不代表查询失败

def test_attendance_query():
    """测试考勤查询"""
    print("\n" + "=" * 60)
    print("测试3: 考勤数据查询")
    print("=" * 60)
    
    engine = create_engine(MYSQL_URL, pool_pre_ping=True)
    
    with engine.connect() as conn:
        # 先查询一个员工编号
        result = conn.execute(text("SELECT emp_code FROM emp_roster LIMIT 1"))
        emp_row = result.fetchone()
        
        if not emp_row:
            print("⚠️ 没有员工数据，跳过考勤测试")
            return True
            
        emp_code = emp_row.emp_code
        print(f"测试员工编号: {emp_code}")
        
        sql = text("""
            SELECT 
                SUM(normal_attendance_days) as total_normal_days,
                SUM(expected_attendance_days) as total_expected_days,
                SUM(late_count) as total_late,
                SUM(early_leave_count) as total_early_leave,
                SUM(leave_count) as total_leave,
                SUM(outing_count) as total_outing,
                SUM(overtime_count) as total_overtime,
                SUM(overtime_hours) as total_overtime_hours
            FROM ods_attendance_summary
            WHERE emp_code = :emp_code
        """)
        result = conn.execute(sql, {'emp_code': emp_code})
        row = result.fetchone()
        
        print(f"✅ 考勤查询成功!")
        print(f"   正常出勤天数: {row.total_normal_days}")
        print(f"   迟到次数: {row.total_late}")
        return True

if __name__ == "__main__":
    print("开始测试人岗适配API数据库查询...")
    print(f"数据库: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")
    
    try:
        test1 = test_employee_query()
        test2 = test_job_description_query()
        test3 = test_attendance_query()
        
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)
        print(f"员工查询: {'✅ 通过' if test1 else '❌ 失败'}")
        print(f"岗位查询: {'✅ 通过' if test2 else '❌ 失败'}")
        print(f"考勤查询: {'✅ 通过' if test3 else '❌ 失败'}")
        
        if test1 and test2 and test3:
            print("\n🎉 所有测试通过！可以部署上线。")
            sys.exit(0)
        else:
            print("\n❌ 有测试未通过，请检查修复。")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
