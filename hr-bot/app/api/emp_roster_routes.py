#!/usr/bin/env python3
"""
员工花名册管理API路由

功能：
1. 批量导入员工花名册Excel文件
2. 支持单条/批量查询员工信息
3. 支持更新已有员工信息

路由：
- POST /api/v1/emp-roster/batch-upload - 批量上传员工花名册
- GET /api/v1/emp-roster/list - 查询员工列表
- GET /api/v1/emp-roster/detail/{emp_code} - 查询员工详情
- POST /api/v1/emp-roster/query - 自然语言查询
"""

import json
import os
import re
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 创建路由
router = APIRouter(prefix="/api/v1/emp-roster", tags=["员工花名册管理"])

# MySQL数据库配置
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_DATABASE = "hr_employee_db"
MYSQL_USER = "hr_user"
MYSQL_PASSWORD = "hr_password"
MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"


# ============ Excel解析函数 ============

def parse_emp_roster_excel(file_path: str) -> List[Dict[str, Any]]:
    """
    解析员工花名册Excel文件
    
    Args:
        file_path: Excel文件路径
        
    Returns:
        员工列表
    """
    try:
        import pandas as pd
        
        # 读取Excel文件
        df = pd.read_excel(file_path)
        
        # 列名映射（中文列名 -> 英文字段名）
        column_mapping = {
            '人员编码': 'emp_code',
            '姓名': 'emp_name',
            '一级部门': 'dept_level1',
            '二级部门': 'dept_level2',
            '员工类型': 'emp_type',
            '岗位': 'position_name',
            '职级': 'job_level',
            '五大序列': 'five_sequence',
            '性别': 'gender',
            '出生日期': 'birth_date',
            '年龄': 'age',
            '政治面貌': 'political_status',
            '民族': 'ethnicity',
            '最高学历': 'highest_education',
            '最高学位': 'highest_degree',
            '最高学位毕业学校': 'highest_degree_school',
            '最高学位毕业学校类别': 'highest_degree_school_type',
            '最高学位专业': 'highest_degree_major',
            '全日制最高学位(PG)': 'fulltime_degree',
            '全日制最高学位毕业学校': 'fulltime_school',
            '全日制最高学位毕业学校类别': 'fulltime_school_type',
            '入职时间': 'entry_date',
            '参加工作时间': 'work_start_date',
            '合同期限类型': 'contract_type',
            '合同终止日期': 'contract_end_date',
            '工龄': 'work_years',
            '司龄': 'company_years',
            '部门类别': 'dept_category',
            '劳动关系公司名称': 'labor_company',
            '工作地': 'work_location'
        }
        
        # 重命名列
        df = df.rename(columns=column_mapping)
        
        # 转换为字典列表
        records = []
        for _, row in df.iterrows():
            record = {}
            for col in column_mapping.values():
                value = row.get(col)
                # 处理NaN值
                if pd.isna(value):
                    record[col] = None
                else:
                    record[col] = str(value) if col not in ['age', 'work_years', 'company_years'] else float(value)
            records.append(record)
        
        return records
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析Excel文件失败: {str(e)}")


# ============ 数据库操作 ============

def save_emp_to_database(emp_data: Dict[str, Any]) -> bool:
    """保存或更新员工数据到MySQL数据库"""
    engine = create_engine(MYSQL_URL, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    
    # 检查是否已存在
    check_sql = """
    SELECT id FROM emp_roster 
    WHERE emp_code = :emp_code
    LIMIT 1
    """
    
    # 插入SQL
    insert_sql = """
    INSERT INTO emp_roster (
        emp_code, emp_name, dept_level1, dept_level2, dept_category,
        emp_type, position_name, job_level, five_sequence,
        gender, birth_date, age, political_status, ethnicity,
        highest_education, highest_degree, highest_degree_school,
        highest_degree_school_type, highest_degree_major,
        fulltime_degree, fulltime_school, fulltime_school_type,
        entry_date, work_start_date, contract_type, contract_end_date,
        work_years, company_years, labor_company, work_location
    ) VALUES (
        :emp_code, :emp_name, :dept_level1, :dept_level2, :dept_category,
        :emp_type, :position_name, :job_level, :five_sequence,
        :gender, :birth_date, :age, :political_status, :ethnicity,
        :highest_education, :highest_degree, :highest_degree_school,
        :highest_degree_school_type, :highest_degree_major,
        :fulltime_degree, :fulltime_school, :fulltime_school_type,
        :entry_date, :work_start_date, :contract_type, :contract_end_date,
        :work_years, :company_years, :labor_company, :work_location
    )
    """
    
    # 更新SQL
    update_sql = """
    UPDATE emp_roster SET
        emp_name = :emp_name,
        dept_level1 = :dept_level1,
        dept_level2 = :dept_level2,
        dept_category = :dept_category,
        emp_type = :emp_type,
        position_name = :position_name,
        job_level = :job_level,
        five_sequence = :five_sequence,
        gender = :gender,
        birth_date = :birth_date,
        age = :age,
        political_status = :political_status,
        ethnicity = :ethnicity,
        highest_education = :highest_education,
        highest_degree = :highest_degree,
        highest_degree_school = :highest_degree_school,
        highest_degree_school_type = :highest_degree_school_type,
        highest_degree_major = :highest_degree_major,
        fulltime_degree = :fulltime_degree,
        fulltime_school = :fulltime_school,
        fulltime_school_type = :fulltime_school_type,
        entry_date = :entry_date,
        work_start_date = :work_start_date,
        contract_type = :contract_type,
        contract_end_date = :contract_end_date,
        work_years = :work_years,
        company_years = :company_years,
        labor_company = :labor_company,
        work_location = :work_location,
        updated_at = NOW()
    WHERE id = :id
    """
    
    try:
        with SessionLocal() as session:
            # 处理日期字段
            for date_field in ['birth_date', 'entry_date', 'work_start_date', 'contract_end_date']:
                if emp_data.get(date_field):
                    try:
                        # 尝试解析各种日期格式
                        date_str = str(emp_data[date_field])
                        if '/' in date_str:
                            parts = date_str.split('/')
                            if len(parts) == 3:
                                emp_data[date_field] = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                        elif '-' in date_str and len(date_str.split('-')[0]) == 2:
                            # YY-MM-DD 格式
                            parts = date_str.split('-')
                            year = int(parts[0])
                            if year < 50:
                                year = 2000 + year
                            else:
                                year = 1900 + year
                            emp_data[date_field] = f"{year}-{parts[1]}-{parts[2]}"
                    except:
                        emp_data[date_field] = None
                else:
                    emp_data[date_field] = None
            
            # 检查是否已存在
            result = session.execute(text(check_sql), {'emp_code': emp_data['emp_code']})
            existing = result.fetchone()
            
            if existing:
                # 更新现有记录
                emp_data['id'] = existing[0]
                session.execute(text(update_sql), emp_data)
            else:
                # 插入新记录
                session.execute(text(insert_sql), emp_data)
            
            session.commit()
            return True
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存到数据库失败: {str(e)}")


# ============ API路由 ============

@router.post("/batch-import")
async def batch_upload_emp_roster(file: UploadFile = File(...)):
    """
    批量上传员工花名册Excel文件
    
    Args:
        file: Excel文件（包含多行员工数据）
        
    Returns:
        导入结果统计
    """
    # 检查文件类型
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持.xlsx或.xls格式的Excel文件")
    
    temp_file_path = None
    try:
        # 保存上传的文件到临时目录
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            temp_file_path = tmp.name
        
        # 解析Excel文件
        employees = parse_emp_roster_excel(temp_file_path)
        
        if not employees:
            return JSONResponse({
                "success": False,
                "message": "Excel文件中没有找到员工数据"
            })
        
        # 批量保存到数据库
        success_count = 0
        fail_count = 0
        fail_list = []
        
        for emp in employees:
            try:
                save_emp_to_database(emp)
                success_count += 1
            except Exception as e:
                fail_count += 1
                fail_list.append({
                    "emp_code": emp.get('emp_code'),
                    "emp_name": emp.get('emp_name'),
                    "error": str(e)
                })
        
        return JSONResponse({
            "success": True,
            "message": f"批量导入完成：成功 {success_count} 条，失败 {fail_count} 条",
            "data": {
                "total": len(employees),
                "success": success_count,
                "fail": fail_count,
                "fail_details": fail_list if fail_list else None
            }
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")
    finally:
        # 删除临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


@router.get("/list")
async def list_emp_roster():
    """
    查询员工花名册列表
    
    Returns:
        员工列表
    """
    engine = create_engine(MYSQL_URL, echo=False)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT emp_code, emp_name, dept_level1, dept_level2, position_name, 
                       job_level, gender, entry_date, created_at 
                FROM emp_roster 
                ORDER BY created_at DESC
            """))
            
            records = []
            for row in result:
                records.append({
                    "emp_code": row[0],
                    "emp_name": row[1],
                    "dept_level1": row[2],
                    "dept_level2": row[3],
                    "position_name": row[4],
                    "job_level": row[5],
                    "gender": row[6],
                    "entry_date": row[7].strftime("%Y-%m-%d") if row[7] else None,
                    "created_at": row[8].strftime("%Y-%m-%d %H:%M:%S") if row[8] else None
                })
            
            return JSONResponse({
                "success": True,
                "count": len(records),
                "data": records
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/detail/{emp_code}")
async def get_emp_detail(emp_code: str):
    """
    获取指定员工的详细信息
    
    Args:
        emp_code: 员工编号
        
    Returns:
        员工详细信息
    """
    engine = create_engine(MYSQL_URL, echo=False)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT * FROM emp_roster WHERE emp_code = :emp_code
            """), {"emp_code": emp_code})
            
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="未找到该员工")
            
            # 构建返回数据
            data = {
                "emp_code": row[1],
                "emp_name": row[2],
                "dept_level1": row[3],
                "dept_level2": row[4],
                "dept_category": row[5],
                "emp_type": row[6],
                "position_name": row[7],
                "job_level": row[8],
                "five_sequence": row[9],
                "gender": row[10],
                "birth_date": row[11].strftime("%Y-%m-%d") if row[11] else None,
                "age": row[12],
                "political_status": row[13],
                "ethnicity": row[14],
                "highest_education": row[15],
                "highest_degree": row[16],
                "highest_degree_school": row[17],
                "highest_degree_school_type": row[18],
                "highest_degree_major": row[19],
                "fulltime_degree": row[20],
                "fulltime_school": row[21],
                "fulltime_school_type": row[22],
                "entry_date": row[23].strftime("%Y-%m-%d") if row[23] else None,
                "work_start_date": row[24].strftime("%Y-%m-%d") if row[24] else None,
                "contract_type": row[25],
                "contract_end_date": row[26].strftime("%Y-%m-%d") if row[26] else None,
                "work_years": float(row[27]) if row[27] else None,
                "company_years": float(row[28]) if row[28] else None,
                "labor_company": row[29],
                "work_location": row[30],
                "created_at": row[31].strftime("%Y-%m-%d %H:%M:%S") if row[31] else None,
                "updated_at": row[32].strftime("%Y-%m-%d %H:%M:%S") if row[32] else None
            }
            
            return JSONResponse({
                "success": True,
                "data": data
            })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/query")
async def query_emp_by_nlp(request: dict):
    """
    通过自然语言查询员工信息
    
    支持查询格式：
    - "石京京的信息"
    - "查询67311096的员工"
    - "技术部的员工有哪些"
    
    Args:
        request: 包含message字段的请求体
        
    Returns:
        查询结果
    """
    message = request.get('message', '').strip()
    if not message:
        raise HTTPException(status_code=400, detail="请输入查询内容")
    
    # 提取查询条件
    emp_name = None
    emp_code = None
    dept = None
    
    # 模式1: XXX的信息/员工信息
    match = re.search(r'(.+?)的(?:信息|员工信息)', message)
    if match:
        emp_name = match.group(1).strip()
    
    # 模式2: 查询XXX的
    match = re.search(r'查询(.+?)的', message)
    if match and not emp_name:
        emp_name = match.group(1).strip()
    
    # 模式3: XXX部门的员工
    match = re.search(r'(.+?)(?:部门|事业部).*?(?:员工|有哪些)', message)
    if match:
        dept = match.group(1).strip()
    
    engine = create_engine(MYSQL_URL, echo=False)
    
    try:
        with engine.connect() as conn:
            # 构建查询
            if emp_name:
                result = conn.execute(text("""
                    SELECT * FROM emp_roster 
                    WHERE emp_name LIKE :name
                    LIMIT 5
                """), {"name": f"%{emp_name}%"})
            elif dept:
                result = conn.execute(text("""
                    SELECT * FROM emp_roster 
                    WHERE dept_level1 LIKE :dept OR dept_level2 LIKE :dept
                    LIMIT 10
                """), {"dept": f"%{dept}%"})
            else:
                return JSONResponse({
                    "success": False,
                    "message": "未能识别查询意图，请尝试使用以下格式：\n- 石京京的信息\n- 查询技术部的员工"
                })
            
            rows = result.fetchall()
            if not rows:
                return JSONResponse({
                    "success": False,
                    "message": f"未找到{'员工' if emp_name else '部门'}：{emp_name or dept}"
                })
            
            # 格式化返回数据
            employees = []
            for row in rows:
                emp = {
                    "emp_code": row[1],
                    "emp_name": row[2],
                    "dept_level1": row[3],
                    "dept_level2": row[4],
                    "position_name": row[7],
                    "job_level": row[8],
                    "gender": row[10],
                    "highest_education": row[15],
                    "entry_date": row[23].strftime("%Y-%m-%d") if row[23] else None
                }
                employees.append(emp)
            
            return JSONResponse({
                "success": True,
                "message": f"找到 {len(employees)} 条记录",
                "data": employees
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
