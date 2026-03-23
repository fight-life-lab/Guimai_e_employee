#!/usr/bin/env python3
"""
岗位说明书管理API路由

功能：
1. 接收前端上传的Excel文件
2. 解析岗位说明书内容
3. 将数据保存到数据库
4. 支持MCP工具调用

路由：
- POST /api/v1/job-description/upload - 上传并解析岗位说明书
- POST /api/v1/job-description/parse - 仅解析不保存
- GET /api/v1/job-description/list - 查询已导入的岗位说明书列表
"""

import base64
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
router = APIRouter(prefix="/api/v1/job-description", tags=["岗位说明书管理"])

# MySQL数据库配置
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_DATABASE = "hr_employee_db"
MYSQL_USER = "hr_user"
MYSQL_PASSWORD = "hr_password"
MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# 请求模型
class JobDescriptionUploadRequest(BaseModel):
    """岗位说明书上传请求"""
    file_content: str  # Base64编码的文件内容
    file_name: str
    emp_id: str
    emp_name: str


class JobDescriptionParseRequest(BaseModel):
    """岗位说明书解析请求"""
    file_path: str
    emp_id: str
    emp_name: Optional[str] = None


# ============ Excel解析函数 ============

def parse_job_description_excel(file_path: str, emp_id: str, emp_name: str) -> Dict[str, Any]:
    """
    解析岗位说明书Excel文件
    
    Args:
        file_path: Excel文件路径
        emp_id: 员工ID
        emp_name: 员工姓名
        
    Returns:
        解析后的数据字典
    """
    try:
        import pandas as pd
        
        # 读取Excel文件
        df = pd.read_excel(file_path, header=None)
        
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
        raise HTTPException(status_code=400, detail=f"解析Excel文件失败: {str(e)}")


# ============ 数据库操作 ============

def save_to_database(data: Dict[str, Any]) -> bool:
    """保存数据到MySQL数据库，如果存在则更新"""
    engine = create_engine(MYSQL_URL, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    
    # 先检查是否已存在
    check_sql = """
    SELECT id FROM ods_emp_job_description 
    WHERE emp_id = :emp_id OR emp_name = :emp_name
    LIMIT 1
    """
    
    # 插入SQL
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
    
    # 更新SQL
    update_sql = """
    UPDATE ods_emp_job_description SET
        emp_id = :emp_id,
        emp_name = :emp_name,
        position_name = :position_name,
        department = :department,
        report_to = :report_to,
        position_purpose = :position_purpose,
        duties_and_responsibilities = :duties_and_responsibilities,
        qualifications_education = :qualifications_education,
        qualifications_major = :qualifications_major,
        qualifications_job_work_experience = :qualifications_job_work_experience,
        qualifications_required_professional_certification = :qualifications_required_professional_certification,
        qualifications_skills = :qualifications_skills,
        qualifications_others = :qualifications_others,
        kpis = :kpis,
        working_hours_conditions = :working_hours_conditions,
        updated_at = NOW()
    WHERE id = :id
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
            
            # 检查是否已存在
            result = session.execute(text(check_sql), {
                'emp_id': data['emp_id'],
                'emp_name': data['emp_name']
            })
            existing = result.fetchone()
            
            if existing:
                # 更新现有记录
                params['id'] = existing[0]
                session.execute(text(update_sql), params)
                session.commit()
                return True
            else:
                # 插入新记录
                session.execute(text(insert_sql), params)
                session.commit()
                return True
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存到数据库失败: {str(e)}")


# ============ API路由 ============

@router.post("/upload")
async def upload_job_description(
    file: UploadFile = File(...),
    emp_id: str = Form(...),
    emp_name: str = Form(...)
):
    """
    上传岗位说明书Excel文件并解析入库
    
    Args:
        file: Excel文件
        emp_id: 员工编号
        emp_name: 员工姓名
        
    Returns:
        解析后的数据
    """
    # 检查文件类型
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持.xlsx或.xls格式的Excel文件")
    
    # 保存上传的文件到临时目录
    temp_file_path = None
    try:
        # 创建临时文件
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            temp_file_path = tmp.name
        
        # 解析Excel文件
        data = parse_job_description_excel(temp_file_path, emp_id, emp_name)
        
        # 保存到数据库
        save_to_database(data)
        
        return JSONResponse({
            "success": True,
            "message": "岗位说明书上传并解析成功",
            "data": {
                "emp_id": data['emp_id'],
                "emp_name": data['emp_name'],
                "position_name": data['position_name'],
                "department": data['department'],
                "report_to": data['report_to'],
                "position_purpose": data['position_purpose'][:100] + "..." if len(data['position_purpose']) > 100 else data['position_purpose'],
                "duties_count": len(data['duties_and_responsibilities']),
                "kpi_count": len(data['kpis'])
            }
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")
    finally:
        # 删除临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


@router.post("/parse")
async def parse_job_description(request: JobDescriptionParseRequest):
    """
    仅解析岗位说明书Excel文件，不保存到数据库
    
    Args:
        request: 包含file_path, emp_id, emp_name的请求体
        
    Returns:
        解析后的数据
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        data = parse_job_description_excel(
            request.file_path, 
            request.emp_id, 
            request.emp_name or ""
        )
        
        return JSONResponse({
            "success": True,
            "message": "解析成功",
            "data": data
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")


@router.get("/list")
async def list_job_descriptions():
    """
    查询已导入的岗位说明书列表
    
    Returns:
        岗位说明书列表
    """
    engine = create_engine(MYSQL_URL, echo=False)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT emp_id, emp_name, position_name, department, created_at 
                FROM ods_emp_job_description 
                ORDER BY created_at DESC
            """))
            
            records = []
            for row in result:
                records.append({
                    "emp_id": row[0],
                    "emp_name": row[1],
                    "position_name": row[2],
                    "department": row[3],
                    "created_at": row[4].strftime("%Y-%m-%d %H:%M:%S") if row[4] else None
                })
            
            return JSONResponse({
                "success": True,
                "count": len(records),
                "data": records
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/query")
async def query_job_description_by_nlp(request: dict):
    """
    通过自然语言查询岗位说明书
    
    支持查询格式：
    - "胡冰的岗位信息"
    - "查询胡冰的岗位说明书"
    - "唐峥嵘是做什么的"
    - "前端开发的岗位描述"
    
    Args:
        request: 包含message字段的请求体
        
    Returns:
        查询结果
    """
    message = request.get('message', '').strip()
    if not message:
        raise HTTPException(status_code=400, detail="请输入查询内容")
    
    # 提取员工姓名（支持多种查询模式）
    emp_name = None
    position_name = None
    
    # 模式1: XXX的岗位信息/岗位说明书/岗位描述
    match = re.search(r'(.+?)的(?:岗位信息|岗位说明书|岗位描述|岗位)', message)
    if match:
        emp_name = match.group(1).strip()
    
    # 模式2: 查询XXX的...
    match = re.search(r'查询(.+?)的', message)
    if match and not emp_name:
        emp_name = match.group(1).strip()
    
    # 模式3: XXX是做什么的
    match = re.search(r'(.+?)是做什么的', message)
    if match and not emp_name:
        emp_name = match.group(1).strip()
    
    # 模式4: 按岗位名称查询
    match = re.search(r'(.+?)(?:岗位|职位).*?(?:描述|说明|信息)', message)
    if match and not emp_name:
        position_name = match.group(1).strip()
    
    engine = create_engine(MYSQL_URL, echo=False)
    
    try:
        with engine.connect() as conn:
            # 先尝试按姓名查询
            if emp_name:
                result = conn.execute(text("""
                    SELECT * FROM ods_emp_job_description 
                    WHERE emp_name LIKE :name
                    LIMIT 1
                """), {"name": f"%{emp_name}%"})
            elif position_name:
                result = conn.execute(text("""
                    SELECT * FROM ods_emp_job_description 
                    WHERE position_name LIKE :position
                    LIMIT 1
                """), {"position": f"%{position_name}%"})
            else:
                return JSONResponse({
                    "success": False,
                    "message": "未能识别查询意图，请尝试使用以下格式：\n- 胡冰的岗位信息\n- 查询唐峥嵘的岗位说明书\n- 前端开发的岗位描述"
                })
            
            row = result.fetchone()
            if not row:
                return JSONResponse({
                    "success": False,
                    "message": f"未找到{'员工' if emp_name else '岗位'}：{emp_name or position_name}"
                })
            
            # 构建返回数据
            data = {
                "emp_id": row[1],
                "emp_name": row[2],
                "position_name": row[3],
                "department": row[4],
                "report_to": row[5],
                "position_purpose": row[6],
                "duties_and_responsibilities": json.loads(row[7]) if row[7] else [],
                "qualifications_education": json.loads(row[8]) if row[8] else {},
                "qualifications_major": json.loads(row[9]) if row[9] else {},
                "qualifications_job_work_experience": json.loads(row[10]) if row[10] else {},
                "qualifications_required_professional_certification": json.loads(row[11]) if row[11] else {},
                "qualifications_skills": json.loads(row[12]) if row[12] else {},
                "qualifications_others": json.loads(row[13]) if row[13] else {},
                "kpis": json.loads(row[14]) if row[14] else [],
                "working_hours_conditions": row[15]
            }
            
            # 格式化回复内容
            reply = format_job_description_reply(data)
            
            return JSONResponse({
                "success": True,
                "message": "查询成功",
                "data": data,
                "reply": reply
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


def format_job_description_reply(data: dict) -> str:
    """格式化岗位说明书为可读文本"""
    lines = []
    
    # 标题
    lines.append(f"## {data['emp_name']} - {data['position_name']}")
    lines.append("")
    
    # 基本信息
    lines.append(f"**员工编号**: {data['emp_id']}")
    lines.append(f"**所在部门**: {data['department']}")
    lines.append(f"**汇报对象**: {data['report_to']}")
    lines.append("")
    
    # 岗位目的
    if data['position_purpose']:
        lines.append("### 岗位目的")
        lines.append(data['position_purpose'])
        lines.append("")
    
    # 岗位职责
    if data['duties_and_responsibilities']:
        lines.append("### 岗位职责")
        for i, duty in enumerate(data['duties_and_responsibilities'], 1):
            lines.append(f"{i}. **{duty.get('module', '')}** - {duty.get('content', '')}")
        lines.append("")
    
    # 任职资格
    qualifications = []
    if data['qualifications_education'].get('requirement'):
        qualifications.append(f"**学历**: {data['qualifications_education']['requirement']}")
    if data['qualifications_major'].get('requirement'):
        qualifications.append(f"**专业**: {data['qualifications_major']['requirement']}")
    if data['qualifications_job_work_experience'].get('requirement'):
        qualifications.append(f"**工作经验**: {data['qualifications_job_work_experience']['requirement']}")
    if data['qualifications_skills'].get('requirement'):
        qualifications.append(f"**知识技能**: {data['qualifications_skills']['requirement']}")
    
    if qualifications:
        lines.append("### 任职资格")
        lines.extend(qualifications)
        lines.append("")
    
    # KPI
    if data['kpis']:
        lines.append("### 关键绩效指标")
        for i, kpi in enumerate(data['kpis'], 1):
            lines.append(f"{i}. {kpi.get('indicator', '')}")
        lines.append("")
    
    return "\n".join(lines)


@router.get("/detail/{emp_id}")
async def get_job_description_detail(emp_id: str):
    """
    获取指定员工的岗位说明书详情
    
    Args:
        emp_id: 员工编号
        
    Returns:
        岗位说明书详情
    """
    engine = create_engine(MYSQL_URL, echo=False)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT * FROM ods_emp_job_description WHERE emp_id = :emp_id
            """), {"emp_id": emp_id})
            
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="未找到该员工的岗位说明书")
            
            # 构建返回数据
            data = {
                "id": row[0],
                "emp_id": row[1],
                "emp_name": row[2],
                "position_name": row[3],
                "department": row[4],
                "report_to": row[5],
                "position_purpose": row[6],
                "duties_and_responsibilities": json.loads(row[7]) if row[7] else [],
                "qualifications_education": json.loads(row[8]) if row[8] else {},
                "qualifications_major": json.loads(row[9]) if row[9] else {},
                "qualifications_job_work_experience": json.loads(row[10]) if row[10] else {},
                "qualifications_required_professional_certification": json.loads(row[11]) if row[11] else {},
                "qualifications_skills": json.loads(row[12]) if row[12] else {},
                "qualifications_others": json.loads(row[13]) if row[13] else {},
                "kpis": json.loads(row[14]) if row[14] else [],
                "working_hours_conditions": row[15],
                "created_at": row[16].strftime("%Y-%m-%d %H:%M:%S") if row[16] else None,
                "updated_at": row[17].strftime("%Y-%m-%d %H:%M:%S") if row[17] else None
            }
            
            return JSONResponse({
                "success": True,
                "data": data
            })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
