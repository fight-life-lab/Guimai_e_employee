#!/usr/bin/env python3
"""
岗位说明书数据查询脚本

功能：
1. 从MySQL数据库查询ods_emp_job_description表的数据
2. 打印查询结果到控制台和日志文件
3. 支持按员工姓名、岗位名称、部门等条件查询
4. 支持查询全部数据

运行环境：
- Python 3.9+
- MySQL (本地Docker容器)
- Conda环境: media_env

安装依赖：
    pip install sqlalchemy pymysql

运行方式：
    # 查询所有数据
    python query_job_description.py
    
    # 按员工姓名查询
    python query_job_description.py --name 钱晓莹
    
    # 按岗位名称查询
    python query_job_description.py --position 用户接待
    
    # 按部门查询
    python query_job_description.py --department 销售服务中心
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
except ImportError as e:
    print(f"错误：缺少必要的依赖包 - {e}")
    print("请安装依赖：pip install sqlalchemy pymysql")
    sys.exit(1)

# ============ 配置参数 ============

# MySQL数据库配置（本地Docker容器）
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_DATABASE = "hr_employee_db"
MYSQL_USER = "hr_user"
MYSQL_PASSWORD = "hr_password"

# 构建MySQL连接URL
MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# 日志配置
LOG_DIR = "/root/shijingjing/e-employee/hr-bot/logs"
LOG_FILE = os.path.join(LOG_DIR, "query_job_description.log")

# ============ 日志设置 ============

def setup_logging() -> logging.Logger:
    """设置日志记录"""
    # 创建日志目录
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # 创建logger
    logger = logging.getLogger("query_job_description")
    logger.setLevel(logging.INFO)
    
    # 清除已有的handler
    logger.handlers = []
    
    # 创建文件handler
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加handler
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# ============ 数据库查询函数 ============

def get_db_connection():
    """获取数据库连接"""
    engine = create_engine(MYSQL_URL, echo=False)
    return engine


def query_all_records(logger: logging.Logger) -> List[Dict[str, Any]]:
    """查询所有记录"""
    engine = get_db_connection()
    
    sql = """
    SELECT 
        id, emp_id, emp_name, position_name, department, report_to,
        position_purpose, duties_and_responsibilities,
        qualifications_education, qualifications_major,
        qualifications_job_work_experience,
        qualifications_required_professional_certification,
        qualifications_skills, qualifications_others,
        kpis, working_hours_conditions,
        created_at, updated_at
    FROM ods_emp_job_description
    ORDER BY id
    """
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            records = []
            for row in result:
                record = {
                    'id': row[0],
                    'emp_id': row[1],
                    'emp_name': row[2],
                    'position_name': row[3],
                    'department': row[4],
                    'report_to': row[5],
                    'position_purpose': row[6],
                    'duties_and_responsibilities': json.loads(row[7]) if row[7] else [],
                    'qualifications_education': json.loads(row[8]) if row[8] else {},
                    'qualifications_major': json.loads(row[9]) if row[9] else {},
                    'qualifications_job_work_experience': json.loads(row[10]) if row[10] else {},
                    'qualifications_required_professional_certification': json.loads(row[11]) if row[11] else {},
                    'qualifications_skills': json.loads(row[12]) if row[12] else {},
                    'qualifications_others': json.loads(row[13]) if row[13] else {},
                    'kpis': json.loads(row[14]) if row[14] else [],
                    'working_hours_conditions': row[15],
                    'created_at': row[16],
                    'updated_at': row[17]
                }
                records.append(record)
            
            logger.info(f"查询到 {len(records)} 条记录")
            return records
    except Exception as e:
        logger.error(f"查询失败: {e}")
        return []


def query_by_name(logger: logging.Logger, name: str) -> List[Dict[str, Any]]:
    """按员工姓名查询"""
    engine = get_db_connection()
    
    sql = """
    SELECT 
        id, emp_id, emp_name, position_name, department, report_to,
        position_purpose, duties_and_responsibilities,
        qualifications_education, qualifications_major,
        qualifications_job_work_experience,
        qualifications_required_professional_certification,
        qualifications_skills, qualifications_others,
        kpis, working_hours_conditions,
        created_at, updated_at
    FROM ods_emp_job_description
    WHERE emp_name LIKE :name
    ORDER BY id
    """
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), {'name': f'%{name}%'})
            records = []
            for row in result:
                record = {
                    'id': row[0],
                    'emp_id': row[1],
                    'emp_name': row[2],
                    'position_name': row[3],
                    'department': row[4],
                    'report_to': row[5],
                    'position_purpose': row[6],
                    'duties_and_responsibilities': json.loads(row[7]) if row[7] else [],
                    'qualifications_education': json.loads(row[8]) if row[8] else {},
                    'qualifications_major': json.loads(row[9]) if row[9] else {},
                    'qualifications_job_work_experience': json.loads(row[10]) if row[10] else {},
                    'qualifications_required_professional_certification': json.loads(row[11]) if row[11] else {},
                    'qualifications_skills': json.loads(row[12]) if row[12] else {},
                    'qualifications_others': json.loads(row[13]) if row[13] else {},
                    'kpis': json.loads(row[14]) if row[14] else [],
                    'working_hours_conditions': row[15],
                    'created_at': row[16],
                    'updated_at': row[17]
                }
                records.append(record)
            
            logger.info(f"按姓名 '{name}' 查询到 {len(records)} 条记录")
            return records
    except Exception as e:
        logger.error(f"查询失败: {e}")
        return []


def query_by_position(logger: logging.Logger, position: str) -> List[Dict[str, Any]]:
    """按岗位名称查询"""
    engine = get_db_connection()
    
    sql = """
    SELECT 
        id, emp_id, emp_name, position_name, department, report_to,
        position_purpose, duties_and_responsibilities,
        qualifications_education, qualifications_major,
        qualifications_job_work_experience,
        qualifications_required_professional_certification,
        qualifications_skills, qualifications_others,
        kpis, working_hours_conditions,
        created_at, updated_at
    FROM ods_emp_job_description
    WHERE position_name LIKE :position
    ORDER BY id
    """
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), {'position': f'%{position}%'})
            records = []
            for row in result:
                record = {
                    'id': row[0],
                    'emp_id': row[1],
                    'emp_name': row[2],
                    'position_name': row[3],
                    'department': row[4],
                    'report_to': row[5],
                    'position_purpose': row[6],
                    'duties_and_responsibilities': json.loads(row[7]) if row[7] else [],
                    'qualifications_education': json.loads(row[8]) if row[8] else {},
                    'qualifications_major': json.loads(row[9]) if row[9] else {},
                    'qualifications_job_work_experience': json.loads(row[10]) if row[10] else {},
                    'qualifications_required_professional_certification': json.loads(row[11]) if row[11] else {},
                    'qualifications_skills': json.loads(row[12]) if row[12] else {},
                    'qualifications_others': json.loads(row[13]) if row[13] else {},
                    'kpis': json.loads(row[14]) if row[14] else [],
                    'working_hours_conditions': row[15],
                    'created_at': row[16],
                    'updated_at': row[17]
                }
                records.append(record)
            
            logger.info(f"按岗位 '{position}' 查询到 {len(records)} 条记录")
            return records
    except Exception as e:
        logger.error(f"查询失败: {e}")
        return []


def query_by_department(logger: logging.Logger, department: str) -> List[Dict[str, Any]]:
    """按部门查询"""
    engine = get_db_connection()
    
    sql = """
    SELECT 
        id, emp_id, emp_name, position_name, department, report_to,
        position_purpose, duties_and_responsibilities,
        qualifications_education, qualifications_major,
        qualifications_job_work_experience,
        qualifications_required_professional_certification,
        qualifications_skills, qualifications_others,
        kpis, working_hours_conditions,
        created_at, updated_at
    FROM ods_emp_job_description
    WHERE department LIKE :department
    ORDER BY id
    """
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), {'department': f'%{department}%'})
            records = []
            for row in result:
                record = {
                    'id': row[0],
                    'emp_id': row[1],
                    'emp_name': row[2],
                    'position_name': row[3],
                    'department': row[4],
                    'report_to': row[5],
                    'position_purpose': row[6],
                    'duties_and_responsibilities': json.loads(row[7]) if row[7] else [],
                    'qualifications_education': json.loads(row[8]) if row[8] else {},
                    'qualifications_major': json.loads(row[9]) if row[9] else {},
                    'qualifications_job_work_experience': json.loads(row[10]) if row[10] else {},
                    'qualifications_required_professional_certification': json.loads(row[11]) if row[11] else {},
                    'qualifications_skills': json.loads(row[12]) if row[12] else {},
                    'qualifications_others': json.loads(row[13]) if row[13] else {},
                    'kpis': json.loads(row[14]) if row[14] else [],
                    'working_hours_conditions': row[15],
                    'created_at': row[16],
                    'updated_at': row[17]
                }
                records.append(record)
            
            logger.info(f"按部门 '{department}' 查询到 {len(records)} 条记录")
            return records
    except Exception as e:
        logger.error(f"查询失败: {e}")
        return []


# ============ 打印函数 ============

def print_record(logger: logging.Logger, record: Dict[str, Any], index: int):
    """打印单条记录"""
    logger.info("="*80)
    logger.info(f"记录 {index}")
    logger.info("="*80)
    
    # 基本信息
    logger.info("【基本信息】")
    logger.info(f"  ID: {record['id']}")
    logger.info(f"  员工ID: {record['emp_id']}")
    logger.info(f"  员工姓名: {record['emp_name']}")
    logger.info(f"  岗位名称: {record['position_name']}")
    logger.info(f"  所在部门: {record['department']}")
    logger.info(f"  汇报对象: {record['report_to']}")
    
    # 岗位目的
    logger.info("\n【岗位目的】")
    if record['position_purpose']:
        logger.info(f"  {record['position_purpose']}")
    else:
        logger.info("  无")
    
    # 岗位职责
    logger.info("\n【岗位职责】")
    if record['duties_and_responsibilities']:
        for i, duty in enumerate(record['duties_and_responsibilities'], 1):
            logger.info(f"  {i}. {duty.get('module', '')}: {duty.get('content', '')}")
    else:
        logger.info("  无")
    
    # 任职资格
    logger.info("\n【任职资格】")
    if record['qualifications_education']:
        logger.info(f"  学历: {record['qualifications_education'].get('requirement', '')}")
    if record['qualifications_major']:
        logger.info(f"  专业: {record['qualifications_major'].get('requirement', '')}")
    if record['qualifications_job_work_experience']:
        logger.info(f"  工作经验: {record['qualifications_job_work_experience'].get('requirement', '')}")
    if record['qualifications_required_professional_certification']:
        logger.info(f"  专业认证: {record['qualifications_required_professional_certification'].get('requirement', '')}")
    if record['qualifications_skills']:
        logger.info(f"  知识技能: {record['qualifications_skills'].get('requirement', '')}")
    if record['qualifications_others']:
        logger.info(f"  其他: {record['qualifications_others'].get('requirement', '')}")
    
    # KPI
    logger.info("\n【关键绩效指标】")
    if record['kpis']:
        for i, kpi in enumerate(record['kpis'], 1):
            logger.info(f"  {i}. {kpi.get('indicator', '')}: {kpi.get('description', '')}")
    else:
        logger.info("  无")
    
    # 工作条件
    logger.info("\n【工作条件说明】")
    if record['working_hours_conditions']:
        logger.info(f"  {record['working_hours_conditions']}")
    else:
        logger.info("  无")
    
    # 时间戳
    logger.info("\n【时间信息】")
    logger.info(f"  创建时间: {record['created_at']}")
    logger.info(f"  更新时间: {record['updated_at']}")
    
    logger.info("")


def print_summary(logger: logging.Logger, records: List[Dict[str, Any]]):
    """打印汇总信息"""
    logger.info("="*80)
    logger.info("查询结果汇总")
    logger.info("="*80)
    logger.info(f"总记录数: {len(records)}")
    
    if records:
        logger.info("\n记录列表:")
        for i, record in enumerate(records, 1):
            logger.info(f"  {i}. {record['emp_name']} | {record['position_name']} | {record['department']}")
    
    logger.info("")


# ============ 主流程 ============

def main():
    """主流程"""
    # 设置日志
    logger = setup_logging()
    
    logger.info("="*80)
    logger.info("岗位说明书数据查询")
    logger.info("="*80)
    logger.info(f"日志文件: {LOG_FILE}")
    logger.info("")
    
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description='查询岗位说明书数据')
    parser.add_argument('--name', type=str, help='按员工姓名查询')
    parser.add_argument('--position', type=str, help='按岗位名称查询')
    parser.add_argument('--department', type=str, help='按部门查询')
    args = parser.parse_args()
    
    # 执行查询
    if args.name:
        logger.info(f"按员工姓名查询: {args.name}")
        records = query_by_name(logger, args.name)
    elif args.position:
        logger.info(f"按岗位名称查询: {args.position}")
        records = query_by_position(logger, args.position)
    elif args.department:
        logger.info(f"按部门查询: {args.department}")
        records = query_by_department(logger, args.department)
    else:
        logger.info("查询所有记录")
        records = query_all_records(logger)
    
    # 打印汇总
    print_summary(logger, records)
    
    # 打印详细记录
    if records:
        logger.info("详细记录信息:")
        logger.info("")
        for i, record in enumerate(records, 1):
            print_record(logger, record, i)
    else:
        logger.info("未找到任何记录")
    
    logger.info("="*80)
    logger.info("查询结束")
    logger.info("="*80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n查询被用户中断")
    except Exception as e:
        print(f"\n\n查询执行出错: {e}")
        import traceback
        traceback.print_exc()
