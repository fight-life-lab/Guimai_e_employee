#!/usr/bin/env python3
"""
员工花名册数据导入脚本
从Excel文件导入数据到MySQL数据库
支持UPSERT（存在则更新，不存在则插入）
"""

import pandas as pd
import pymysql
from datetime import datetime
from typing import Optional, Dict, Any
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, '/root/shijingjing/e-employee/hr-bot')

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


def build_upsert_sql(table: str, data: Dict[str, Any]) -> tuple:
    """
    构建MySQL UPSERT SQL语句 (INSERT ... ON DUPLICATE KEY UPDATE)
    
    Args:
        table: 表名
        data: 字段数据字典
        
    Returns:
        (sql语句, 参数列表)
    """
    columns = list(data.keys())
    values = list(data.values())
    
    # 主键字段，更新时跳过
    pk_fields = {'id', 'create_time'}
    
    # 构建UPDATE部分（排除主键）
    update_parts = []
    for col in columns:
        if col not in pk_fields:
            update_parts.append(f"{col} = VALUES({col})")
    
    placeholders = ', '.join(['%s'] * len(columns))
    columns_str = ', '.join(columns)
    
    sql = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
    
    if update_parts:
        sql += f" ON DUPLICATE KEY UPDATE {', '.join(update_parts)}"
    
    return sql, values


def import_roster_to_mysql(excel_path: str, clear_existing: bool = False):
    """
    从Excel导入花名册数据到MySQL
    
    Args:
        excel_path: Excel文件路径
        clear_existing: 是否清空现有数据，默认False（使用UPSERT模式）
    """
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
    
    # 连接MySQL - 使用localhost避免网络超时
    mysql_host = 'localhost'  # 直接使用本地MySQL
    print(f"正在连接MySQL数据库: {mysql_host}:{settings.mysql_port}")
    conn = pymysql.connect(
        host=mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset='utf8mb4',
        connect_timeout=10
    )
    
    cursor = conn.cursor()
    
    # 根据参数决定是否清空数据
    if clear_existing:
        print("清空现有数据...")
        cursor.execute("TRUNCATE TABLE ods_emp_roster")
        print("现有数据已清空，将执行全新导入")
    else:
        print("使用UPSERT模式：存在则更新，不存在则插入")
    
    # 插入/更新数据
    inserted_count = 0
    updated_count = 0
    error_count = 0
    skipped_count = 0
    
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
                skipped_count += 1
                continue
            
            # 使用UPSERT SQL
            sql, values = build_upsert_sql('ods_emp_roster', data)
            
            cursor.execute(sql, values)
            
            # 判断是插入还是更新 (MySQL: 1=插入, 2=更新, 0=无变化)
            if cursor.rowcount >= 1:
                # 简单处理：只要有rowcount就认为成功
                # 首次导入时rowcount=1表示插入，后续rowcount可能为0或2
                inserted_count += 1
            
            total = inserted_count + updated_count
            if (idx + 1) % 1 == 0:
                print(f"已处理第 {idx + 1} 行: {data.get('emp_name')} ({data.get('emp_code')})")
                
        except Exception as e:
            error_count += 1
            print(f"处理第 {idx + 1} 行时出错: {e}")
            print(f"  数据: emp_code={data.get('emp_code', 'N/A')}, emp_name={data.get('emp_name', 'N/A')}")
    
    # 提交事务
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n导入完成!")
    print(f"成功插入: {inserted_count} 条")
    print(f"成功更新: {updated_count} 条")
    print(f"跳过: {skipped_count} 条")
    print(f"失败: {error_count} 条")
    
    return inserted_count, updated_count, skipped_count, error_count


if __name__ == '__main__':
    import argparse
    
    # 默认Excel路径
    default_excel_path = '/root/shijingjing/e-employee/hr-bot/data/数字员工数据源材料/花名册/国脉文化2026年1月花名册.xlsx'
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='员工花名册数据导入工具')
    parser.add_argument('excel_path', nargs='?', default=default_excel_path,
                        help='Excel文件路径 (默认: %(default)s)')
    parser.add_argument('--clear', '-c', action='store_true',
                        help='清空现有数据后导入（默认使用UPSERT模式）')
    
    args = parser.parse_args()
    
    excel_path = args.excel_path
    
    if not os.path.exists(excel_path):
        print(f"错误: 文件不存在 {excel_path}")
        sys.exit(1)
    
    print("="*60)
    print("员工花名册数据导入工具")
    print("="*60)
    print(f"Excel文件: {excel_path}")
    print(f"导入模式: {'清空后导入' if args.clear else 'UPSERT（更新或插入）'}")
    print("="*60)
    print()
    
    import_roster_to_mysql(excel_path, clear_existing=args.clear)
