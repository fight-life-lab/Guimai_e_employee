#!/usr/bin/env python3
"""
员工花名册数据导入脚本
从Excel文件导入数据到MySQL数据库
"""

import pandas as pd
import pymysql
from datetime import datetime
from typing import Optional
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import get_settings


def parse_date(date_val) -> Optional[str]:
    """解析日期字段"""
    if pd.isna(date_val) or date_val == '' or date_val == '-':
        return None
    if isinstance(date_val, datetime):
        return date_val.strftime('%Y-%m-%d')
    if isinstance(date_val, str):
        # 尝试多种日期格式
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y']:
            try:
                return datetime.strptime(date_val.strip(), fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
    return None


def clean_string(val) -> Optional[str]:
    """清理字符串字段"""
    if pd.isna(val) or val == '' or val == '-':
        return None
    return str(val).strip()


def import_roster_to_mysql(excel_path: str):
    """从Excel导入花名册数据到MySQL"""
    settings = get_settings()
    
    # 读取Excel文件，第2行是表头
    print(f"正在读取Excel文件: {excel_path}")
    df = pd.read_excel(excel_path, header=1)
    print(f"读取到 {len(df)} 行数据")
    
    # 列名映射 (Excel列名 -> 数据库字段名)
    column_mapping = {
        '列1': 'emp_code',           # 人员编码
        '姓名': 'emp_name',          # 姓名
        '部门': 'dept_name',         # 部门
        '下设部门': 'sub_dept_name', # 下设部门
        '人员类别': 'emp_category',  # 人员类别
        '岗位名称': 'post_name',     # 岗位名称
        '岗位等级': 'post_grade',    # 岗位等级
        '五大序列': 'five_series',   # 五大序列
        '性别': 'gender',            # 性别
        '出生日期': 'birth_date',    # 出生日期
        '政治面貌': 'political_status',  # 政治面貌
        '民族': 'nation',            # 民族
        '最高学历': 'highest_edu',   # 最高学历
        '最高学历毕业学校': 'highest_edu_school',  # 最高学历毕业学校
        '最高学历专业': 'highest_edu_major',       # 最高学历专业
        '合同期限类型': 'contract_term_type',      # 合同期限类型
        '合同终止日期': 'contract_end_date',       # 合同终止日期
        '部门类别': 'dept_category',               # 部门类别
        '劳动关系公司名称': 'labor_relation_company',  # 劳动关系公司名称
        '工作地': 'work_location',   # 工作地
    }
    
    # 连接MySQL
    print(f"正在连接MySQL数据库: {settings.mysql_host}:{settings.mysql_port}")
    conn = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset='utf8mb4'
    )
    
    cursor = conn.cursor()
    
    # 清空现有数据
    print("清空现有数据...")
    cursor.execute("TRUNCATE TABLE ods_emp_roster")
    
    # 插入数据
    inserted_count = 0
    error_count = 0
    
    for idx, row in df.iterrows():
        try:
            # 构建插入数据
            data = {}
            for excel_col, db_col in column_mapping.items():
                if excel_col in df.columns:
                    val = row[excel_col]
                    if db_col in ['birth_date', 'contract_end_date']:
                        data[db_col] = parse_date(val)
                    else:
                        data[db_col] = clean_string(val)
            
            # 检查必填字段
            if not data.get('emp_code') or not data.get('emp_name'):
                print(f"跳过第 {idx + 1} 行: 缺少人员编码或姓名")
                continue
            
            # 构建SQL
            columns = list(data.keys())
            placeholders = ', '.join(['%s'] * len(columns))
            sql = f"INSERT INTO ods_emp_roster ({', '.join(columns)}) VALUES ({placeholders})"
            
            cursor.execute(sql, list(data.values()))
            inserted_count += 1
            
            if inserted_count % 10 == 0:
                print(f"已插入 {inserted_count} 条数据...")
                
        except Exception as e:
            error_count += 1
            print(f"处理第 {idx + 1} 行时出错: {e}")
            print(f"  数据: {dict(row)}")
    
    # 提交事务
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n导入完成!")
    print(f"成功插入: {inserted_count} 条")
    print(f"失败: {error_count} 条")
    
    return inserted_count, error_count


if __name__ == '__main__':
    # 默认Excel路径
    default_excel_path = '/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/data/数字员工数据源材料/花名册/国脉文化2026年1月花名册.xlsx'
    
    # 支持命令行参数指定路径
    excel_path = sys.argv[1] if len(sys.argv) > 1 else default_excel_path
    
    if not os.path.exists(excel_path):
        print(f"错误: 文件不存在 {excel_path}")
        sys.exit(1)
    
    import_roster_to_mysql(excel_path)
