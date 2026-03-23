#!/usr/bin/env python3
"""
清空专业能力相关数据表
用于重新导入前的清理
"""
import pymysql

def clear_professional_ability_data():
    """清空ods_emp_professional_ability表的所有数据"""
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
            # 先查询有多少条数据
            cursor.execute("SELECT COUNT(*) FROM ods_emp_professional_ability")
            count = cursor.fetchone()[0]
            print(f"当前表中共有 {count} 条数据")
            
            if count > 0:
                # 查看前5条数据的更新时间
                cursor.execute("""
                    SELECT emp_code, emp_name, updated_at 
                    FROM ods_emp_professional_ability 
                    ORDER BY updated_at DESC 
                    LIMIT 5
                """)
                print("\n最近更新的5条数据:")
                for row in cursor.fetchall():
                    print(f"  {row[1]} ({row[0]}) - 更新于: {row[2]}")
                
                confirm = input(f"\n确定要清空这 {count} 条数据吗? (输入 'yes' 确认): ")
                if confirm.lower() == 'yes':
                    cursor.execute("TRUNCATE TABLE ods_emp_professional_ability")
                    conn.commit()
                    print(f"✅ 已清空所有数据")
                else:
                    print("❌ 操作已取消")
            else:
                print("表中没有任何数据")
                
    finally:
        conn.close()

if __name__ == "__main__":
    clear_professional_ability_data()
