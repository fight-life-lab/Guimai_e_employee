"""
战略匹配评分API
支持批量导入员工战略匹配评分数据
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
from io import BytesIO
from datetime import datetime
import logging

from app.models.strategic_alignment import StrategicAlignmentScore

router = APIRouter(prefix="/api/v1/strategic-alignment", tags=["战略匹配评分"])

logger = logging.getLogger(__name__)


class StrategicAlignmentImportResponse(BaseModel):
    """战略匹配数据导入响应"""
    success: bool
    message: str
    total_count: int
    success_count: int
    error_count: int
    errors: List[dict]


class StrategicAlignmentScoreItem(BaseModel):
    """战略匹配评分项"""
    emp_code: str
    emp_name: str
    score: float
    evaluation_year: Optional[int] = None
    evaluator: Optional[str] = None
    evaluation_basis: Optional[str] = None
    remark: Optional[str] = None


class StrategicAlignmentListResponse(BaseModel):
    """战略匹配评分列表响应"""
    success: bool
    message: str
    data: List[StrategicAlignmentScoreItem]
    total: int


# MySQL数据库配置
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_DATABASE = "hr_employee_db"
MYSQL_USER = "hr_user"
MYSQL_PASSWORD = "hr_password"
MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"


def get_db():
    """获取数据库连接"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(MYSQL_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/import", response_model=StrategicAlignmentImportResponse)
async def import_strategic_alignment_scores(
    file: UploadFile = File(...),
    evaluation_year: Optional[int] = None,
    evaluator: Optional[str] = None
):
    """
    批量导入战略匹配评分数据
    
    Excel文件格式要求：
    - 工号/员工编号
    - 姓名/员工姓名
    - 分数/战略匹配分数/评分
    
    如果同一员工同一年度已存在记录，则覆盖更新
    """
    try:
        logger.info(f"[StrategicAlignment] 开始导入战略匹配数据: {file.filename}")
        
        # 读取上传的文件
        contents = await file.read()
        
        # 根据文件扩展名选择读取方式
        if file.filename.endswith('.csv'):
            df = pd.read_csv(BytesIO(contents))
        else:
            df = pd.read_excel(BytesIO(contents))
        
        if df.empty:
            return StrategicAlignmentImportResponse(
                success=False,
                message="文件为空",
                total_count=0,
                success_count=0,
                error_count=0,
                errors=[]
            )
        
        # 标准化列名
        column_mapping = {
            '工号': 'emp_code',
            '员工编号': 'emp_code',
            '编号': 'emp_code',
            '姓名': 'emp_name',
            '员工姓名': 'emp_name',
            '名字': 'emp_name',
            '分数': 'score',
            '战略匹配分数': 'score',
            '评分': 'score',
            '得分': 'score',
            '战略分数': 'score'
        }
        
        # 重命名列
        df.rename(columns=lambda x: column_mapping.get(x.strip(), x.strip()), inplace=True)
        
        # 检查必需的列
        required_columns = ['emp_code', 'emp_name', 'score']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return StrategicAlignmentImportResponse(
                success=False,
                message=f"缺少必需的列: {', '.join(missing_columns)}。请确保文件包含工号、姓名、分数列",
                total_count=0,
                success_count=0,
                error_count=0,
                errors=[]
            )
        
        # 如果没有提供考核年度，使用当前年份
        if evaluation_year is None:
            evaluation_year = datetime.now().year
        
        # 从数据库连接
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(MYSQL_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        success_count = 0
        error_count = 0
        errors = []
        
        try:
            for index, row in df.iterrows():
                try:
                    emp_code = str(row.get('emp_code', '')).strip()
                    emp_name = str(row.get('emp_name', '')).strip()
                    score = float(row.get('score', 0))
                    
                    if not emp_code or not emp_name:
                        error_count += 1
                        errors.append({
                            'row': index + 2,
                            'error': '工号或姓名为空'
                        })
                        continue
                    
                    # 检查是否已存在该员工该年度的记录
                    existing = db.query(StrategicAlignmentScore).filter(
                        StrategicAlignmentScore.emp_code == emp_code,
                        StrategicAlignmentScore.evaluation_year == evaluation_year
                    ).first()
                    
                    if existing:
                        # 更新现有记录
                        existing.score = score
                        existing.emp_name = emp_name
                        existing.evaluator = evaluator
                        existing.evaluation_basis = f"批量导入于{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        logger.info(f"[StrategicAlignment] 更新记录: {emp_name} ({emp_code}) - {score}分")
                    else:
                        # 创建新记录
                        new_record = StrategicAlignmentScore(
                            emp_code=emp_code,
                            emp_name=emp_name,
                            score=score,
                            evaluation_year=evaluation_year,
                            evaluator=evaluator,
                            evaluation_basis=f"批量导入于{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        db.add(new_record)
                        logger.info(f"[StrategicAlignment] 新增记录: {emp_name} ({emp_code}) - {score}分")
                    
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    errors.append({
                        'row': index + 2,
                        'error': str(e)
                    })
                    logger.error(f"[StrategicAlignment] 处理第{index + 2}行出错: {str(e)}")
            
            db.commit()
            
            return StrategicAlignmentImportResponse(
                success=True,
                message=f"导入完成：成功{success_count}条，失败{error_count}条",
                total_count=len(df),
                success_count=success_count,
                error_count=error_count,
                errors=errors
            )
            
        except Exception as e:
            db.rollback()
            logger.error(f"[StrategicAlignment] 导入失败: {str(e)}")
            return StrategicAlignmentImportResponse(
                success=False,
                message=f"导入失败: {str(e)}",
                total_count=len(df),
                success_count=success_count,
                error_count=error_count,
                errors=errors
            )
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"[StrategicAlignment] 文件处理失败: {str(e)}")
        return StrategicAlignmentImportResponse(
            success=False,
            message=f"文件处理失败: {str(e)}",
            total_count=0,
            success_count=0,
            error_count=0,
            errors=[]
        )


@router.get("/scores", response_model=StrategicAlignmentListResponse)
async def get_strategic_alignment_scores(
    emp_code: Optional[str] = None,
    emp_name: Optional[str] = None,
    evaluation_year: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
):
    """
    获取战略匹配评分列表
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(MYSQL_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            query = db.query(StrategicAlignmentScore)
            
            if emp_code:
                query = query.filter(StrategicAlignmentScore.emp_code == emp_code)
            if emp_name:
                query = query.filter(StrategicAlignmentScore.emp_name.like(f"%{emp_name}%"))
            if evaluation_year:
                query = query.filter(StrategicAlignmentScore.evaluation_year == evaluation_year)
            
            total = query.count()
            records = query.offset(skip).limit(limit).all()
            
            data = [
                StrategicAlignmentScoreItem(
                    emp_code=r.emp_code,
                    emp_name=r.emp_name,
                    score=r.score,
                    evaluation_year=r.evaluation_year,
                    evaluator=r.evaluator,
                    evaluation_basis=r.evaluation_basis,
                    remark=r.remark
                )
                for r in records
            ]
            
            return StrategicAlignmentListResponse(
                success=True,
                message="获取成功",
                data=data,
                total=total
            )
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"[StrategicAlignment] 获取数据失败: {str(e)}")
        return StrategicAlignmentListResponse(
            success=False,
            message=f"获取数据失败: {str(e)}",
            data=[],
            total=0
        )


@router.get("/score/{emp_code}")
async def get_employee_strategic_alignment_score(emp_code: str, evaluation_year: Optional[int] = None):
    """
    获取指定员工的战略匹配评分
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(MYSQL_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            query = db.query(StrategicAlignmentScore).filter(
                StrategicAlignmentScore.emp_code == emp_code
            )
            
            if evaluation_year:
                query = query.filter(StrategicAlignmentScore.evaluation_year == evaluation_year)
            else:
                # 获取最新年份的记录
                query = query.order_by(StrategicAlignmentScore.evaluation_year.desc())
            
            record = query.first()
            
            if record:
                return {
                    "success": True,
                    "data": {
                        "emp_code": record.emp_code,
                        "emp_name": record.emp_name,
                        "score": record.score,
                        "evaluation_year": record.evaluation_year,
                        "evaluator": record.evaluator,
                        "evaluation_basis": record.evaluation_basis,
                        "remark": record.remark
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "未找到该员工的战略匹配评分数据"
                }
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"[StrategicAlignment] 获取员工数据失败: {str(e)}")
        return {
            "success": False,
            "message": f"获取数据失败: {str(e)}"
        }
