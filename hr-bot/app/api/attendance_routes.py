"""
考勤明细数据管理API
提供考勤数据的批量导入、查询等功能
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

router = APIRouter(prefix="/api/v1/attendance", tags=["考勤管理"])

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


class AttendanceQuery(BaseModel):
    """考勤查询模型"""
    emp_code: Optional[str] = None
    emp_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    department: Optional[str] = None


class AttendanceResponse(BaseModel):
    """考勤响应模型"""
    id: int
    attendance_date: str
    emp_code: str
    emp_name: Optional[str]
    department: Optional[str]
    normal_attendance_days: float
    expected_attendance_days: float
    late_count: int
    early_leave_count: int
    leave_count: int
    outing_count: int
    overtime_info: Optional[str]
    original_checkin_time: Optional[str]
    original_checkout_time: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/batch-upload")
async def batch_upload_attendance(file: UploadFile = File(...)):
    """
    批量导入考勤明细数据
    支持Excel文件，包含多行考勤数据
    """
    logger.info(f"[Attendance] 开始批量导入考勤数据，文件名: {file.filename}")
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="请上传Excel文件(.xlsx或.xls)")
    
    db = SessionLocal()
    try:
        # 读取Excel文件
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        logger.info(f"[Attendance] Excel读取成功，共 {len(df)} 行数据")
        
        # 列名映射（中文列名 -> 英文字段名）
        column_mapping = {
            '考勤日期': 'attendance_date',
            '员工ID': 'emp_code',
            '员工编号': 'emp_code',
            '员工姓名': 'emp_name',
            '部门/事业部': 'department',
            '正常出勤天': 'normal_attendance_days',
            '理应出勤天': 'expected_attendance_days',
            '迟到次数': 'late_count',
            '早退次数': 'early_leave_count',
            '请假次数': 'leave_count',
            '外出次数': 'outing_count',
            '加班次数及20:30以后': 'overtime_info',
            '原始签到时间': 'original_checkin_time',
            '原始签退时间': 'original_checkout_time'
        }
        
        # 重命名列
        df.rename(columns=column_mapping, inplace=True)
        
        # 检查必需列
        required_columns = ['attendance_date', 'emp_code']
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
        
        for idx, row in df.iterrows():
            try:
                # 跳过空行
                if pd.isna(row.get('emp_code')) or pd.isna(row.get('attendance_date')):
                    continue
                
                # 处理日期格式
                attendance_date = row.get('attendance_date')
                if isinstance(attendance_date, pd.Timestamp):
                    attendance_date = attendance_date.strftime('%Y-%m-%d')
                elif isinstance(attendance_date, str):
                    # 尝试多种日期格式
                    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y']:
                        try:
                            attendance_date = datetime.strptime(attendance_date, fmt).strftime('%Y-%m-%d')
                            break
                        except:
                            continue
                
                # 构建插入/更新SQL
                sql = text("""
                    INSERT INTO ods_attendance_detail (
                        attendance_date, emp_code, emp_name, department,
                        normal_attendance_days, expected_attendance_days,
                        late_count, early_leave_count, leave_count, outing_count,
                        overtime_info, original_checkin_time, original_checkout_time
                    ) VALUES (
                        :attendance_date, :emp_code, :emp_name, :department,
                        :normal_attendance_days, :expected_attendance_days,
                        :late_count, :early_leave_count, :leave_count, :outing_count,
                        :overtime_info, :original_checkin_time, :original_checkout_time
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
                        overtime_info = VALUES(overtime_info),
                        original_checkin_time = VALUES(original_checkin_time),
                        original_checkout_time = VALUES(original_checkout_time),
                        updated_at = CURRENT_TIMESTAMP
                """)
                
                params = {
                    'attendance_date': attendance_date,
                    'emp_code': str(row.get('emp_code', '')).strip(),
                    'emp_name': str(row.get('emp_name', '')).strip() if pd.notna(row.get('emp_name')) else None,
                    'department': str(row.get('department', '')).strip() if pd.notna(row.get('department')) else None,
                    'normal_attendance_days': float(row.get('normal_attendance_days', 0)) if pd.notna(row.get('normal_attendance_days')) else 0,
                    'expected_attendance_days': float(row.get('expected_attendance_days', 0)) if pd.notna(row.get('expected_attendance_days')) else 0,
                    'late_count': int(row.get('late_count', 0)) if pd.notna(row.get('late_count')) else 0,
                    'early_leave_count': int(row.get('early_leave_count', 0)) if pd.notna(row.get('early_leave_count')) else 0,
                    'leave_count': int(row.get('leave_count', 0)) if pd.notna(row.get('leave_count')) else 0,
                    'outing_count': int(row.get('outing_count', 0)) if pd.notna(row.get('outing_count')) else 0,
                    'overtime_info': str(row.get('overtime_info', '')).strip() if pd.notna(row.get('overtime_info')) else None,
                    'original_checkin_time': str(row.get('original_checkin_time', '')).strip() if pd.notna(row.get('original_checkin_time')) else None,
                    'original_checkout_time': str(row.get('original_checkout_time', '')).strip() if pd.notna(row.get('original_checkout_time')) else None
                }
                
                db.execute(sql, params)
                success_count += 1
                
            except Exception as e:
                fail_count += 1
                error_msg = f"第{idx + 2}行导入失败: {str(e)}"
                error_messages.append(error_msg)
                logger.error(f"[Attendance] {error_msg}")
                continue
        
        db.commit()
        
        logger.info(f"[Attendance] 批量导入完成，成功: {success_count}, 失败: {fail_count}")
        
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
        logger.error(f"[Attendance] 批量导入失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量导入失败: {str(e)}")
    finally:
        db.close()


@router.post("/query")
async def query_attendance(query: AttendanceQuery):
    """
    查询考勤明细数据
    """
    db = SessionLocal()
    try:
        sql = "SELECT * FROM ods_attendance_detail WHERE 1=1"
        params = {}
        
        if query.emp_code:
            sql += " AND emp_code = :emp_code"
            params['emp_code'] = query.emp_code
        
        if query.emp_name:
            sql += " AND emp_name LIKE :emp_name"
            params['emp_name'] = f"%{query.emp_name}%"
        
        if query.start_date:
            sql += " AND attendance_date >= :start_date"
            params['start_date'] = query.start_date
        
        if query.end_date:
            sql += " AND attendance_date <= :end_date"
            params['end_date'] = query.end_date
        
        if query.department:
            sql += " AND department LIKE :department"
            params['department'] = f"%{query.department}%"
        
        sql += " ORDER BY attendance_date DESC, emp_code LIMIT 1000"
        
        result = db.execute(text(sql), params)
        rows = result.fetchall()
        
        data = []
        for row in rows:
            data.append({
                "id": row.id,
                "attendance_date": row.attendance_date.strftime('%Y-%m-%d') if row.attendance_date else None,
                "emp_code": row.emp_code,
                "emp_name": row.emp_name,
                "department": row.department,
                "normal_attendance_days": float(row.normal_attendance_days) if row.normal_attendance_days else 0,
                "expected_attendance_days": float(row.expected_attendance_days) if row.expected_attendance_days else 0,
                "late_count": row.late_count,
                "early_leave_count": row.early_leave_count,
                "leave_count": row.leave_count,
                "outing_count": row.outing_count,
                "overtime_info": row.overtime_info,
                "original_checkin_time": row.original_checkin_time,
                "original_checkout_time": row.original_checkout_time,
                "created_at": row.created_at.strftime('%Y-%m-%d %H:%M:%S') if row.created_at else None
            })
        
        return {
            "success": True,
            "count": len(data),
            "data": data
        }
        
    except Exception as e:
        logger.error(f"[Attendance] 查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
    finally:
        db.close()


@router.get("/list")
async def list_attendance(
    emp_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    获取考勤列表
    """
    query = AttendanceQuery(
        emp_code=emp_code,
        start_date=start_date,
        end_date=end_date
    )
    return await query_attendance(query)


@router.get("/stats/{emp_code}")
async def get_attendance_stats(
    emp_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    获取员工考勤统计
    """
    db = SessionLocal()
    try:
        sql = """
            SELECT 
                COUNT(*) as total_days,
                SUM(normal_attendance_days) as total_normal_days,
                SUM(expected_attendance_days) as total_expected_days,
                SUM(late_count) as total_late,
                SUM(early_leave_count) as total_early_leave,
                SUM(leave_count) as total_leave,
                SUM(outing_count) as total_outing
            FROM ods_attendance_detail
            WHERE emp_code = :emp_code
        """
        params = {'emp_code': emp_code}
        
        if start_date:
            sql += " AND attendance_date >= :start_date"
            params['start_date'] = start_date
        
        if end_date:
            sql += " AND attendance_date <= :end_date"
            params['end_date'] = end_date
        
        result = db.execute(text(sql), params)
        row = result.fetchone()
        
        if not row or row.total_days == 0:
            return {
                "success": True,
                "message": "未找到该员工的考勤记录",
                "data": None
            }
        
        return {
            "success": True,
            "data": {
                "emp_code": emp_code,
                "total_days": row.total_days,
                "total_normal_days": float(row.total_normal_days) if row.total_normal_days else 0,
                "total_expected_days": float(row.total_expected_days) if row.total_expected_days else 0,
                "total_late": row.total_late or 0,
                "total_early_leave": row.total_early_leave or 0,
                "total_leave": row.total_leave or 0,
                "total_outing": row.total_outing or 0,
                "attendance_rate": round(
                    (float(row.total_normal_days) / float(row.total_expected_days) * 100), 2
                ) if row.total_expected_days and row.total_expected_days > 0 else 0
            }
        }
        
    except Exception as e:
        logger.error(f"[Attendance] 统计查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"统计查询失败: {str(e)}")
    finally:
        db.close()
