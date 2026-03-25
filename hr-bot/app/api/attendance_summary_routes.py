"""
考勤汇总数据管理API
提供考勤汇总数据的批量导入、查询等功能
"""

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
from datetime import datetime
import io
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

router = APIRouter(prefix="/api/v1/attendance-summary", tags=["考勤汇总管理"])

logger = logging.getLogger(__name__)

# MySQL数据库配置
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_DATABASE = "hr_employee_db"
MYSQL_USER = "hr_user"
MYSQL_PASSWORD = "hr_password"
MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# 创建数据库引擎
engine = create_engine(MYSQL_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class AttendanceSummaryQuery(BaseModel):
    """考勤汇总查询模型"""
    emp_code: Optional[str] = None
    emp_name: Optional[str] = None
    attendance_month: Optional[str] = None
    department: Optional[str] = None


@router.post("/batch-upload")
async def batch_upload_attendance_summary(file: UploadFile = File(...)):
    """
    批量导入考勤汇总数据
    支持Excel文件，包含多行考勤汇总数据
    """
    logger.info(f"[AttendanceSummary] 开始批量导入考勤汇总数据，文件名: {file.filename}")
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="请上传Excel文件(.xlsx或.xls)")
    
    db = SessionLocal()
    try:
        # 读取Excel文件
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        logger.info(f"[AttendanceSummary] Excel读取成功，共 {len(df)} 行数据")
        
        # 列名映射（中文列名 -> 英文字段名）
        column_mapping = {
            '考勤月份': 'attendance_month',
            '员工ID': 'emp_code',
            '员工编号': 'emp_code',
            '员工姓名': 'emp_name',
            '部门/事业部': 'department',
            '正常出勤天数': 'normal_attendance_days',
            '正常出勤天': 'normal_attendance_days',
            '理应出勤天数': 'expected_attendance_days',
            '理应出勤天': 'expected_attendance_days',
            '迟到次数': 'late_count',
            '早退次数': 'early_leave_count',
            '请假次数': 'leave_count',
            '外出次数': 'outing_count',
            '加班次数': 'overtime_count',
            '加班时长（小时）': 'overtime_hours',
            '加班时长（20:30以后加班时长-小时）': 'overtime_hours',
            '加班时长': 'overtime_hours'
        }
        
        # 重命名列
        df.rename(columns=column_mapping, inplace=True)
        
        # 检查必需列
        required_columns = ['attendance_month', 'emp_code']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400, 
                detail=f"Excel文件缺少必需列: {missing_columns}"
            )
        
        # 数据清洗和转换
        success_count = 0
        fail_count = 0
        error_messages = []
        
        # 打印所有列名，用于调试
        logger.info(f"[AttendanceSummary] Excel列名: {list(df.columns)}")
        
        for idx, row in df.iterrows():
            try:
                # 跳过空行
                if pd.isna(row.get('emp_code')) or pd.isna(row.get('attendance_month')):
                    continue
                
                # 处理月份格式
                attendance_month = row.get('attendance_month')
                if isinstance(attendance_month, pd.Timestamp):
                    attendance_month = attendance_month.strftime('%Y-%m')
                elif isinstance(attendance_month, str):
                    # 尝试多种日期格式
                    for fmt in ['%Y-%m', '%Y/%m', '%m/%Y']:
                        try:
                            attendance_month = datetime.strptime(attendance_month, fmt).strftime('%Y-%m')
                            break
                        except:
                            continue
                
                # 构建插入/更新SQL
                sql = text("""
                    INSERT INTO ods_attendance_summary (
                        attendance_month, emp_code, emp_name, department,
                        normal_attendance_days, expected_attendance_days,
                        late_count, early_leave_count, leave_count, outing_count,
                        overtime_count, overtime_hours
                    ) VALUES (
                        :attendance_month, :emp_code, :emp_name, :department,
                        :normal_attendance_days, :expected_attendance_days,
                        :late_count, :early_leave_count, :leave_count, :outing_count,
                        :overtime_count, :overtime_hours
                    )
                    ON DUPLICATE KEY UPDATE
                        emp_name = VALUES(emp_name),
                        department = VALUES(department),
                        normal_attendance_days = VALUES(normal_attendance_days),
                        expected_attendance_days = VALUES(expected_attendance_days),
                        late_count = VALUES(late_count),
                        early_leave_count = VALUES(early_leave_count),
                        leave_count = VALUES(leave_count),
                        outing_count = VALUES(outing_count),
                        overtime_count = VALUES(overtime_count),
                        overtime_hours = VALUES(overtime_hours),
                        updated_at = CURRENT_TIMESTAMP
                """)
                
                # 处理数值字段，确保正确转换
                def get_numeric_value(value, default=0):
                    if pd.isna(value):
                        return default
                    try:
                        # 尝试转换为数字
                        if isinstance(value, str):
                            # 移除可能的非数字字符
                            value = ''.join(c for c in value if c.isdigit() or c == '.')
                        return float(value)
                    except:
                        return default
                
                # 处理整数字段
                def get_integer_value(value, default=0):
                    if pd.isna(value):
                        return default
                    try:
                        # 尝试转换为整数
                        if isinstance(value, str):
                            # 移除可能的非数字字符
                            value = ''.join(c for c in value if c.isdigit())
                        return int(float(value))
                    except:
                        return default
                
                # 打印原始数据
                logger.info(f"[AttendanceSummary] 第{idx + 2}行数据: normal_attendance_days={row.get('normal_attendance_days')}, overtime_hours={row.get('overtime_hours')}")
                
                params = {
                    'attendance_month': attendance_month,
                    'emp_code': str(row.get('emp_code', '')).strip(),
                    'emp_name': str(row.get('emp_name', '')).strip() if pd.notna(row.get('emp_name')) else None,
                    'department': str(row.get('department', '')).strip() if pd.notna(row.get('department')) else None,
                    'normal_attendance_days': get_numeric_value(row.get('normal_attendance_days')),
                    'expected_attendance_days': get_numeric_value(row.get('expected_attendance_days')),
                    'late_count': get_integer_value(row.get('late_count')),
                    'early_leave_count': get_integer_value(row.get('early_leave_count')),
                    'leave_count': get_integer_value(row.get('leave_count')),
                    'outing_count': get_integer_value(row.get('outing_count')),
                    'overtime_count': get_integer_value(row.get('overtime_count')),
                    'overtime_hours': get_numeric_value(row.get('overtime_hours'))
                }
                
                # 打印处理后的数据
                logger.info(f"[AttendanceSummary] 第{idx + 2}行处理后: normal_attendance_days={params['normal_attendance_days']}, overtime_hours={params['overtime_hours']}")
                
                db.execute(sql, params)
                success_count += 1
                
            except Exception as e:
                fail_count += 1
                error_msg = f"第{idx + 2}行导入失败: {str(e)}"
                error_messages.append(error_msg)
                logger.error(f"[AttendanceSummary] {error_msg}")
                continue
        
        db.commit()
        
        logger.info(f"[AttendanceSummary] 批量导入完成，成功: {success_count}, 失败: {fail_count}")
        
        return {
            "success": True,
            "message": f"导入完成，成功：{success_count} 条，失败：{fail_count} 条",
            "data": {
                "total": len(df),
                "success": success_count,
                "fail": fail_count,
                "errors": error_messages[:10]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[AttendanceSummary] 批量导入失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量导入失败: {str(e)}")
    finally:
        db.close()


@router.post("/query")
async def query_attendance_summary(query: AttendanceSummaryQuery):
    """
    查询考勤汇总数据
    """
    db = SessionLocal()
    try:
        sql = "SELECT * FROM ods_attendance_summary WHERE 1=1"
        params = {}
        
        if query.emp_code:
            sql += " AND emp_code = :emp_code"
            params['emp_code'] = query.emp_code
        
        if query.emp_name:
            sql += " AND emp_name LIKE :emp_name"
            params['emp_name'] = f"%{query.emp_name}%"
        
        if query.attendance_month:
            sql += " AND attendance_month = :attendance_month"
            params['attendance_month'] = query.attendance_month
        
        if query.department:
            sql += " AND department LIKE :department"
            params['department'] = f"%{query.department}%"
        
        sql += " ORDER BY attendance_month DESC, emp_code LIMIT 1000"
        
        result = db.execute(text(sql), params)
        rows = result.fetchall()
        
        data = []
        for row in rows:
            data.append({
                "id": row.id,
                "attendance_month": row.attendance_month,
                "emp_code": row.emp_code,
                "emp_name": row.emp_name,
                "department": row.department,
                "normal_attendance_days": float(row.normal_attendance_days) if row.normal_attendance_days else 0,
                "expected_attendance_days": float(row.expected_attendance_days) if row.expected_attendance_days else 0,
                "late_count": row.late_count,
                "early_leave_count": row.early_leave_count,
                "leave_count": row.leave_count,
                "outing_count": row.outing_count,
                "overtime_count": row.overtime_count,
                "overtime_hours": float(row.overtime_hours) if row.overtime_hours else 0,
                "created_at": row.created_at.strftime('%Y-%m-%d %H:%M:%S') if row.created_at else None
            })
        
        return {
            "success": True,
            "count": len(data),
            "data": data
        }
        
    except Exception as e:
        logger.error(f"[AttendanceSummary] 查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
    finally:
        db.close()


@router.get("/list")
async def list_attendance_summary(
    emp_code: Optional[str] = None,
    attendance_month: Optional[str] = None
):
    """
    获取考勤汇总列表
    """
    query = AttendanceSummaryQuery(
        emp_code=emp_code,
        attendance_month=attendance_month
    )
    return await query_attendance_summary(query)
