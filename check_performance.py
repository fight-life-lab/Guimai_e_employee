#!/usr/bin/env python3
"""
查询钱晓莹近三年绩效记录
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'hr-bot'))

from app.database.session import SessionLocal
from app.database.models import Employee, EmployeeHistoricalPerformance

def check_qian_xiaoying_performance():
    """检查钱晓莹近三年绩效"""
    db = SessionLocal()
    try:
        # 查找钱晓莹的员工信息
        qian_xiaoying = db.query(Employee).filter(
            Employee.emp_name == '钱晓莹'
        ).first()
        
        if not qian_xiaoying:
            print("未找到钱晓莹的员工信息")
            return
        
        print(f"找到钱晓莹：")
        print(f"  员工编号: {qian_xiaoying.emp_code}")
        print(f"  员工ID: {qian_xiaoying.id}")
        print(f"  姓名: {qian_xiaoying.emp_name}")
        
        # 查询近三年的绩效记录
        years = ['2022', '2023', '2024', '2025']
        print(f"\n近三年绩效记录：")
        
        performance_records = db.query(EmployeeHistoricalPerformance).filter(
            EmployeeHistoricalPerformance.employee_id == qian_xiaoying.id,
            EmployeeHistoricalPerformance.year.in_(years)
        ).all()
        
        if not performance_records:
            print("  未找到绩效记录")
            return
        
        # 按年份排序
        performance_records.sort(key=lambda x: x.year)
        
        performance_map = {}
        for record in performance_records:
            performance_map[record.year] = record.performance_level
            print(f"  {record.year}年: {record.performance_level}")
        
        # 检查连续三年称职
        print(f"\n连续三年称职检查：")
        
        # 检查 2022-2023-2024
        if all(performance_map.get(year) == 'competent' for year in ['2022', '2023', '2024']):
            print("  ✅ 2022-2023-2024 连续三年称职")
        else:
            print("  ❌ 2022-2023-2024 不是连续三年称职")
        
        # 检查 2023-2024-2025
        if all(performance_map.get(year) == 'competent' for year in ['2023', '2024', '2025']):
            print("  ✅ 2023-2024-2025 连续三年称职")
        else:
            print("  ❌ 2023-2024-2025 不是连续三年称职")
            
    except Exception as e:
        print(f"查询出错: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_qian_xiaoying_performance()
