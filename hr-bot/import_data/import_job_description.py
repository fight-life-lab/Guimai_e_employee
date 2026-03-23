#!/usr/bin/env python3
"""
岗位说明书数据导入脚本

功能：
1. 读取Excel格式的岗位说明书文件
2. 解析并提取关键信息
3. 将数据导入到MySQL数据库的ods_emp_job_description表

数据来源：
- /root/shijingjing/e-employee/hr-bot/data/20260309补充材料/岗位说明书/

运行环境：
- Python 3.13
- MySQL (远程服务器: 121.229.172.161)

安装依赖：
    pip install pandas openpyxl sqlalchemy pymysql

运行方式：
    python import_job_description.py
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import pandas as pd
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
except ImportError as e:
    print(f"错误：缺少必要的依赖包 - {e}")
    print("请安装依赖：pip install pandas openpyxl sqlalchemy pymysql")
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

# 数据目录
DATA_DIR = "/root/shijingjing/e-employee/hr-bot/data/20260309补充材料/岗位说明书"

# ============ Excel解析函数 ============

def parse_job_description_excel(file_path: str) -> Optional[Dict[str, Any]]:
    """
    解析岗位说明书Excel文件
    
    Args:
        file_path: Excel文件路径
        
    Returns:
        解析后的数据字典
    """
    try:
        # 读取Excel文件
        df = pd.read_excel(file_path, header=None)
        
        # 从文件名提取员工信息
        file_name = os.path.basename(file_path)
        emp_name = file_name.split('-')[0] if '-' in file_name else ''
        
        # 生成员工ID (使用姓名拼音或随机生成)
        emp_id = generate_emp_id(emp_name)
        
        # 初始化数据结构
        data = {
            'emp_id': emp_id,
            'emp_name': emp_name,
            'position_name': '',
            'department': '',
            'report_to': '',
            'position_purpose': '',
            'duties_and_responsibilities': [],
            'qualifications_education': {},
            'qualifications_major': {},
            'qualifications_job_work_experience': {},
            'qualifications_required_professional_certification': {},
            'qualifications_skills': {},
            'qualifications_others': {},
            'kpis': [],
            'working_hours_conditions': ''
        }
        
        # 解析基本信息 (第1-3行)
        for idx, row in df.iterrows():
            row_values = row.tolist()
            
            # 岗位名称、所在部门
            if '岗位名称' in str(row_values[0]):
                data['position_name'] = str(row_values[1]) if pd.notna(row_values[1]) else ''
                if '所在部门' in str(row_values[2]):
                    data['department'] = str(row_values[3]) if pd.notna(row_values[3]) else ''
            
            # 汇报对象
            if '汇报对象' in str(row_values[0]):
                data['report_to'] = str(row_values[1]) if pd.notna(row_values[1]) else ''
        
        # 解析岗位目的 (在"一、岗位目的："之后)
        purpose_started = False
        for idx, row in df.iterrows():
            row_values = row.tolist()
            
            if '一、岗位目的：' in str(row_values[0]):
                purpose_started = True
                continue
            
            if purpose_started and pd.notna(row_values[0]):
                # 检查是否是下一个章节
                if str(row_values[0]).startswith('二、'):
                    break
                # 累加岗位目的内容
                if data['position_purpose']:
                    data['position_purpose'] += '\n'
                data['position_purpose'] += str(row_values[0])
        
        # 解析岗位职责 (在"二、岗位职责："之后)
        duties_started = False
        current_duty = {}
        for idx, row in df.iterrows():
            row_values = row.tolist()
            
            if '二、岗位职责：' in str(row_values[0]):
                duties_started = True
                continue
            
            if duties_started:
                # 检查是否是下一个章节
                if str(row_values[0]).startswith('三、'):
                    break
                
                # 跳过表头行
                if '职责模块' in str(row_values[0]) or '工作内容' in str(row_values[0]):
                    continue
                
                # 解析职责内容
                if pd.notna(row_values[0]) and pd.notna(row_values[1]):
                    duty_module = str(row_values[0]).strip()
                    duty_content = str(row_values[1]).strip()
                    if duty_module and duty_content:
                        data['duties_and_responsibilities'].append({
                            'module': duty_module,
                            'content': duty_content
                        })
        
        # 解析任职资格 (在"三、任职资格："之后)
        qualifications_started = False
        for idx, row in df.iterrows():
            row_values = row.tolist()
            
            if '三、任职资格：' in str(row_values[0]):
                qualifications_started = True
                continue
            
            if qualifications_started:
                # 检查是否是下一个章节
                if str(row_values[0]).startswith('四、'):
                    break
                
                # 跳过表头行
                if '维度' in str(row_values[0]) or '明细' in str(row_values[0]):
                    continue
                
                # 解析任职资格各维度
                if pd.notna(row_values[0]) and pd.notna(row_values[1]):
                    dim_name = str(row_values[0]).strip()
                    dim_value = str(row_values[1]).strip()
                    
                    if '学历' in dim_name:
                        data['qualifications_education'] = {'requirement': dim_value}
                    elif '专业' in dim_name:
                        data['qualifications_major'] = {'requirement': dim_value}
                    elif '工作经验' in dim_name or '岗位工作经验' in dim_name:
                        data['qualifications_job_work_experience'] = {'requirement': dim_value}
                    elif '专业认证' in dim_name or '必备专业认证' in dim_name:
                        data['qualifications_required_professional_certification'] = {'requirement': dim_value}
                    elif '知识技能' in dim_name or '知识技能能力' in dim_name:
                        data['qualifications_skills'] = {'requirement': dim_value}
                    elif '其他' in dim_name:
                        data['qualifications_others'] = {'requirement': dim_value}
        
        # 解析KPI (在"四、关键绩效指标（KPI）："之后)
        kpi_started = False
        for idx, row in df.iterrows():
            row_values = row.tolist()
            
            if '四、关键绩效指标' in str(row_values[0]):
                kpi_started = True
                continue
            
            if kpi_started:
                # 检查是否是下一个章节
                if str(row_values[0]).startswith('五、'):
                    break
                
                # 跳过表头行
                if 'KPI指标' in str(row_values[0]):
                    continue
                
                # 解析KPI内容
                if pd.notna(row_values[0]):
                    kpi_name = str(row_values[0]).strip()
                    kpi_desc = str(row_values[2]).strip() if len(row_values) > 2 and pd.notna(row_values[2]) else ''
                    if kpi_name:
                        data['kpis'].append({
                            'indicator': kpi_name,
                            'description': kpi_desc
                        })
        
        # 解析工作条件说明 (在"五、工作条件说明"之后)
        conditions_started = False
        conditions_text = []
        for idx, row in df.iterrows():
            row_values = row.tolist()
            
            if '五、工作条件说明' in str(row_values[0]):
                conditions_started = True
                continue
            
            if conditions_started and pd.notna(row_values[0]):
                condition_item = str(row_values[0]).strip()
                condition_desc = str(row_values[1]).strip() if len(row_values) > 1 and pd.notna(row_values[1]) else ''
                if condition_item and condition_desc:
                    conditions_text.append(f"{condition_item}: {condition_desc}")
        
        data['working_hours_conditions'] = '\n'.join(conditions_text)
        
        return data
        
    except Exception as e:
        print(f"解析文件失败 {file_path}: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_emp_id(emp_name: str) -> str:
    """根据员工姓名生成员工ID"""
    # 员工ID映射表
    emp_id_map = {
        '钱晓莹': '67311096',
        '唐峥嵘': '71070090',
        '刘天隽': '71122058',
        '张谦乐': '71122233'
    }
    
    return emp_id_map.get(emp_name, '00000000')


# ============ 数据库操作 ============

def save_to_database(data: Dict[str, Any]) -> bool:
    """保存数据到MySQL数据库"""
    engine = create_engine(MYSQL_URL, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    
    insert_sql = """
    INSERT INTO ods_emp_job_description (
        emp_id, emp_name, position_name, department, report_to,
        position_purpose, duties_and_responsibilities,
        qualifications_education, qualifications_major,
        qualifications_job_work_experience,
        qualifications_required_professional_certification,
        qualifications_skills, qualifications_others,
        kpis, working_hours_conditions
    ) VALUES (
        :emp_id, :emp_name, :position_name, :department, :report_to,
        :position_purpose, :duties_and_responsibilities,
        :qualifications_education, :qualifications_major,
        :qualifications_job_work_experience,
        :qualifications_required_professional_certification,
        :qualifications_skills, :qualifications_others,
        :kpis, :working_hours_conditions
    )
    """
    
    try:
        with SessionLocal() as session:
            # 转换JSON字段
            params = {
                'emp_id': data['emp_id'],
                'emp_name': data['emp_name'],
                'position_name': data['position_name'],
                'department': data['department'],
                'report_to': data['report_to'],
                'position_purpose': data['position_purpose'],
                'duties_and_responsibilities': json.dumps(data['duties_and_responsibilities'], ensure_ascii=False),
                'qualifications_education': json.dumps(data['qualifications_education'], ensure_ascii=False),
                'qualifications_major': json.dumps(data['qualifications_major'], ensure_ascii=False),
                'qualifications_job_work_experience': json.dumps(data['qualifications_job_work_experience'], ensure_ascii=False),
                'qualifications_required_professional_certification': json.dumps(data['qualifications_required_professional_certification'], ensure_ascii=False),
                'qualifications_skills': json.dumps(data['qualifications_skills'], ensure_ascii=False),
                'qualifications_others': json.dumps(data['qualifications_others'], ensure_ascii=False),
                'kpis': json.dumps(data['kpis'], ensure_ascii=False),
                'working_hours_conditions': data['working_hours_conditions']
            }
            
            session.execute(text(insert_sql), params)
            session.commit()
            return True
    except Exception as e:
        print(f"保存到数据库失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def clear_existing_data():
    """清空现有数据"""
    engine = create_engine(MYSQL_URL, echo=False)
    
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM ods_emp_job_description"))
            conn.commit()
            print("✓ 已清空现有数据")
    except Exception as e:
        print(f"✗ 清空数据失败: {e}")


# ============ 主流程 ============

def main():
    """主流程"""
    print("="*80)
    print("岗位说明书数据导入")
    print("="*80)
    
    # 检查数据目录
    if not os.path.exists(DATA_DIR):
        print(f"错误：数据目录不存在 {DATA_DIR}")
        sys.exit(1)
    
    # 获取所有Excel文件
    excel_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.xlsx') and not f.startswith('.')]
    
    if not excel_files:
        print(f"错误：未找到Excel文件")
        sys.exit(1)
    
    print(f"\n找到 {len(excel_files)} 个Excel文件:")
    for f in excel_files:
        print(f"  - {f}")
    
    # 清空现有数据
    print("\n" + "-"*80)
    print("清空现有数据...")
    clear_existing_data()
    
    # 处理每个文件
    print("\n" + "-"*80)
    print("开始导入数据...")
    
    success_count = 0
    fail_count = 0
    
    for i, file_name in enumerate(excel_files, 1):
        file_path = os.path.join(DATA_DIR, file_name)
        print(f"\n[{i}/{len(excel_files)}] 处理: {file_name}")
        
        # 解析Excel
        data = parse_job_description_excel(file_path)
        
        if data:
            print(f"  员工: {data['emp_name']}")
            print(f"  岗位: {data['position_name']}")
            print(f"  部门: {data['department']}")
            
            # 保存到数据库
            if save_to_database(data):
                print(f"  ✓ 导入成功")
                success_count += 1
            else:
                print(f"  ✗ 导入失败")
                fail_count += 1
        else:
            print(f"  ✗ 解析失败")
            fail_count += 1
    
    # 输出统计
    print("\n" + "="*80)
    print("导入完成统计")
    print("="*80)
    print(f"  成功: {success_count} 条")
    print(f"  失败: {fail_count} 条")
    print(f"  总计: {len(excel_files)} 条")
    
    # 验证数据
    print("\n" + "-"*80)
    print("验证数据...")
    engine = create_engine(MYSQL_URL, echo=False)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) as count FROM ods_emp_job_description"))
            count = result.fetchone()[0]
            print(f"  数据库中共有 {count} 条记录")
            
            # 显示导入的数据
            result = conn.execute(text("SELECT emp_name, position_name, department FROM ods_emp_job_description"))
            print("\n  导入的数据:")
            for row in result:
                print(f"    - {row[0]} | {row[1]} | {row[2]}")
    except Exception as e:
        print(f"  验证失败: {e}")
    
    print("\n" + "="*80)
    print("导入结束")
    print("="*80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n导入被用户中断")
    except Exception as e:
        print(f"\n\n导入执行出错: {e}")
        import traceback
        traceback.print_exc()
