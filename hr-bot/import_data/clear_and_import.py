#!/usr/bin/env python3
"""
清空专业能力数据并重新导入
在远程服务器上运行
"""
import pymysql
import sys

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
                
                # 直接清空，不需要确认
                cursor.execute("TRUNCATE TABLE ods_emp_professional_ability")
                conn.commit()
                print(f"\n✅ 已清空所有 {count} 条数据")
            else:
                print("表中没有任何数据，无需清空")
                
    finally:
        conn.close()

def verify_data_cleared():
    """验证数据是否已清空"""
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
            cursor.execute("SELECT COUNT(*) FROM ods_emp_professional_ability")
            count = cursor.fetchone()[0]
            if count == 0:
                print("✅ 验证成功：表中数据已清空")
                return True
            else:
                print(f"❌ 验证失败：表中仍有 {count} 条数据")
                return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("清空专业能力数据表")
    print("=" * 60)
    
    clear_professional_ability_data()
    
    print("\n" + "=" * 60)
    print("验证清空结果")
    print("=" * 60)
    
    if verify_data_cleared():
        print("\n📝 数据已清空，现在可以通过前端页面上传Excel文件重新导入")
        print("   访问: http://121.229.172.161:3111/static/chat.html")
        print("   点击上传按钮，选择数据类型和Excel文件进行导入")
    else:
        print("\n❌ 数据清空失败，请检查数据库连接")
        sys.exit(1)
