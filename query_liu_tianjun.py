import pymysql

# 数据库连接参数
config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'hr_user',
    'password': 'hr_password',
    'database': 'hr_employee_db',
    'charset': 'utf8mb4'
}

try:
    # 连接数据库
    connection = pymysql.connect(**config)
    cursor = connection.cursor()
    
    # 查询刘天隽的学历信息
    query = "SELECT emp_name, highest_education, highest_degree, highest_degree_major FROM emp_roster WHERE emp_name = '刘天隽'"
    cursor.execute(query)
    
    # 获取结果
    result = cursor.fetchone()
    
    if result:
        print(f"员工姓名: {result[0]}")
        print(f"最高学历: {result[1]}")
        print(f"最高学位: {result[2]}")
        print(f"最高学位专业: {result[3]}")
    else:
        print("未找到刘天隽的记录")
        
    # 关闭连接
    cursor.close()
    connection.close()
    
except Exception as e:
    print(f"查询失败: {e}")
