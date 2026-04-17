#!/usr/bin/env python3
"""
在远程服务器上查询刘天隽的学历信息
"""
import pymysql

def query_liu_tianjun():
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
            # 首先查询所有员工，看看有没有刘天隽
            cursor.execute("SELECT emp_name FROM emp_roster WHERE emp_name LIKE '%刘%' OR emp_name LIKE '%天%' OR emp_name LIKE '%隽%'")
            results = cursor.fetchall()
            
            print("=== 查找包含刘/天/隽的员工 ===")
            for row in results:
                print(f"员工: {row[0]}")
            
            # 尝试直接查询刘天隽
            print("\n=== 直接查询刘天隽 ===")
            cursor.execute("SELECT emp_name, highest_education, highest_degree, highest_degree_major FROM emp_roster WHERE emp_name = '刘天隽'")
            result = cursor.fetchone()
            
            if result:
                print(f"员工姓名: {result[0]}")
                print(f"最高学历: {result[1]}")
                print(f"最高学位: {result[2]}")
                print(f"最高学位专业: {result[3]}")
            else:
                print("未找到刘天隽的记录")
                
    finally:
        conn.close()

if __name__ == "__main__":
    query_liu_tianjun()
