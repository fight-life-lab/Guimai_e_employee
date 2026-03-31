"""
战略匹配分数管理API
支持批量导入和查询员工战略匹配分数
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import pandas as pd
import logging
from datetime import datetime

from app.models.strategic_alignment import StrategicAlignmentScore
from app.database import get_db

router = APIRouter(prefix="/api/v1/strategic-alignment", tags=["战略匹配分数管理"])

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


class StrategicAlignmentScoreItem(BaseModel):
    """战略匹配分数项"""
    emp_code: str
    emp_name: str
    score: float
    evaluation_year: Optional[int] = None
    evaluator: Optional[str] = None
    evaluation_basis: Optional[str] = None


class StrategicAlignmentScoreResponse(BaseModel):
    """战略匹配分数响应"""
    success: bool
    message: str
    data: Optional[List[StrategicAlignmentScoreItem]] = None
    errors: Optional[List[str]] = None


class StrategicAlignmentScoreQuery(BaseModel):
    """战略匹配分数查询"""
    emp_code: Optional[str] = None
    emp_name: Optional[str] = None
    evaluation_year: Optional[int] = None


def get_db_session():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/import", response_model=StrategicAlignmentScoreResponse)
async def import_strategic_alignment_scores(
    file: UploadFile = File(...),
    evaluation_year: Optional[int] = None,
    evaluator: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """
    批量导入战略匹配分数
    
    支持Excel文件格式，文件需包含以下列：
    - 工号/员工编号
    - 姓名/员工姓名
    - 分数/战略匹配分数
    
    参数:
    - file: Excel文件
    - evaluation_year: 考核年度（可选，默认当前年份）
    - evaluator: 评定人（可选）
    """
    try:
        # 检查文件类型
        if not file.filename.endswith(('.xlsx', '.xls')):
            return StrategicAlignmentScoreResponse(
                success=False,
                message="只支持Excel文件格式(.xlsx, .xls)",
                errors=["文件格式错误"]
            )
        
        # 读取Excel文件
        df = pd.read_excel(file.file)
        
        # 标准化列名
        column_mapping = {
            '工号': 'emp_code',
            '员工编号': 'emp_code',
            '员工号': 'emp_code',
            '编号': 'emp_code',
            '姓名': 'emp_name',
            '员工姓名': 'emp_name',
            '名字': 'emp_name',
            '分数': 'score',
            '战略匹配分数': 'score',
            '得分': 'score',
            '成绩': 'score'
        }
        
        # 重命名列
        df.rename(columns=lambda x: column_mapping.get(str(x).strip(), x), inplace=True)
        
        # 检查必需列
        required_columns = ['emp_code', 'emp_name', 'score']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return StrategicAlignmentScoreResponse(
                success=False,
                message=f"Excel文件缺少必需列: {', '.join(missing_columns)}",
                errors=[f"缺少列: {missing_columns}"]
            )
        
        # 设置默认考核年度
        if evaluation_year is None:
            evaluation_year = datetime.now().year
        
        # 处理数据
        success_count = 0
        error_list = []
        imported_data = []
        
        for index, row in df.iterrows():
            try:
                emp_code = str(row['emp_code']).strip()
                emp_name = str(row['emp_name']).strip()
                score = float(row['score'])
                
                # 验证分数范围
                if score < 0 or score > 100:
                    error_list.append(f"第{index + 2}行: 分数{score}超出范围(0-100)")
                    continue
                
                # 检查是否已存在记录
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
                else:
                    # 创建新记录
                    new_score = StrategicAlignmentScore(
                        emp_code=emp_code,
                        emp_name=emp_name,
                        score=score,
                        evaluation_year=evaluation_year,
                        evaluator=evaluator,
                        evaluation_basis=f"批量导入于{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    db.add(new_score)
                
                success_count += 1
                imported_data.append(StrategicAlignmentScoreItem(
                    emp_code=emp_code,
                    emp_name=emp_name,
                    score=score,
                    evaluation_year=evaluation_year,
                    evaluator=evaluator
                ))
                
            except Exception as e:
                error_list.append(f"第{index + 2}行: {str(e)}")
                logger.error(f"处理第{index + 2}行数据时出错: {e}")
        
        # 提交事务
        db.commit()
        
        return StrategicAlignmentScoreResponse(
            success=True,
            message=f"成功导入{success_count}条记录",
            data=imported_data,
            errors=error_list if error_list else None
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"批量导入战略匹配分数失败: {e}")
        return StrategicAlignmentScoreResponse(
            success=False,
            message=f"导入失败: {str(e)}",
            errors=[str(e)]
        )


@router.get("/score/{emp_code}")
async def get_strategic_alignment_score(
    emp_code: str,
    evaluation_year: Optional[int] = None,
    db: Session = Depends(get_db_session)
):
    """
    获取员工战略匹配分数
    
    参数:
    - emp_code: 员工工号
    - evaluation_year: 考核年度（可选，默认当前年份）
    """
    try:
        if evaluation_year is None:
            evaluation_year = datetime.now().year
        
        score_record = db.query(StrategicAlignmentScore).filter(
            StrategicAlignmentScore.emp_code == emp_code,
            StrategicAlignmentScore.evaluation_year == evaluation_year
        ).first()
        
        if score_record:
            return {
                "success": True,
                "data": {
                    "emp_code": score_record.emp_code,
                    "emp_name": score_record.emp_name,
                    "score": score_record.score,
                    "evaluation_year": score_record.evaluation_year,
                    "evaluator": score_record.evaluator,
                    "evaluation_basis": score_record.evaluation_basis,
                    "updated_at": score_record.updated_at.strftime("%Y-%m-%d %H:%M:%S") if score_record.updated_at else None
                }
            }
        else:
            return {
                "success": False,
                "message": f"未找到员工{emp_code}在{evaluation_year}年的战略匹配分数"
            }
            
    except Exception as e:
        logger.error(f"获取战略匹配分数失败: {e}")
        return {
            "success": False,
            "message": f"查询失败: {str(e)}"
        }


@router.get("/scores")
async def list_strategic_alignment_scores(
    evaluation_year: Optional[int] = None,
    emp_name: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db_session)
):
    """
    查询战略匹配分数列表
    
    参数:
    - evaluation_year: 考核年度（可选）
    - emp_name: 员工姓名（可选，支持模糊查询）
    - page: 页码（默认1）
    - page_size: 每页数量（默认50）
    """
    try:
        query = db.query(StrategicAlignmentScore)
        
        if evaluation_year:
            query = query.filter(StrategicAlignmentScore.evaluation_year == evaluation_year)
        
        if emp_name:
            query = query.filter(StrategicAlignmentScore.emp_name.like(f"%{emp_name}%"))
        
        # 计算总数
        total = query.count()
        
        # 分页
        scores = query.order_by(StrategicAlignmentScore.score.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return {
            "success": True,
            "data": [
                {
                    "emp_code": s.emp_code,
                    "emp_name": s.emp_name,
                    "score": s.score,
                    "evaluation_year": s.evaluation_year,
                    "evaluator": s.evaluator,
                    "updated_at": s.updated_at.strftime("%Y-%m-%d %H:%M:%S") if s.updated_at else None
                }
                for s in scores
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
        
    except Exception as e:
        logger.error(f"查询战略匹配分数列表失败: {e}")
        return {
            "success": False,
            "message": f"查询失败: {str(e)}"
        }


@router.post("/score")
async def create_or_update_strategic_alignment_score(
    item: StrategicAlignmentScoreItem,
    db: Session = Depends(get_db_session)
):
    """
    创建或更新单个员工战略匹配分数
    """
    try:
        # 验证分数范围
        if item.score < 0 or item.score > 100:
            return {
                "success": False,
                "message": "分数必须在0-100之间"
            }
        
        # 设置默认考核年度
        if item.evaluation_year is None:
            item.evaluation_year = datetime.now().year
        
        # 检查是否已存在记录
        existing = db.query(StrategicAlignmentScore).filter(
            StrategicAlignmentScore.emp_code == item.emp_code,
            StrategicAlignmentScore.evaluation_year == item.evaluation_year
        ).first()
        
        if existing:
            # 更新现有记录
            existing.score = item.score
            existing.emp_name = item.emp_name
            existing.evaluator = item.evaluator
            existing.evaluation_basis = item.evaluation_basis
            message = "更新成功"
        else:
            # 创建新记录
            new_score = StrategicAlignmentScore(
                emp_code=item.emp_code,
                emp_name=item.emp_name,
                score=item.score,
                evaluation_year=item.evaluation_year,
                evaluator=item.evaluator,
                evaluation_basis=item.evaluation_basis
            )
            db.add(new_score)
            message = "创建成功"
        
        db.commit()
        
        return {
            "success": True,
            "message": message,
            "data": item.dict()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"保存战略匹配分数失败: {e}")
        return {
            "success": False,
            "message": f"保存失败: {str(e)}"
        }


@router.delete("/score/{emp_code}")
async def delete_strategic_alignment_score(
    emp_code: str,
    evaluation_year: Optional[int] = None,
    db: Session = Depends(get_db_session)
):
    """
    删除员工战略匹配分数
    
    参数:
    - emp_code: 员工工号
    - evaluation_year: 考核年度（可选，默认当前年份）
    """
    try:
        if evaluation_year is None:
            evaluation_year = datetime.now().year
        
        score_record = db.query(StrategicAlignmentScore).filter(
            StrategicAlignmentScore.emp_code == emp_code,
            StrategicAlignmentScore.evaluation_year == evaluation_year
        ).first()
        
        if score_record:
            db.delete(score_record)
            db.commit()
            return {
                "success": True,
                "message": f"成功删除员工{emp_code}在{evaluation_year}年的战略匹配分数"
            }
        else:
            return {
                "success": False,
                "message": f"未找到员工{emp_code}在{evaluation_year}年的战略匹配分数"
            }
            
    except Exception as e:
        db.rollback()
        logger.error(f"删除战略匹配分数失败: {e}")
        return {
            "success": False,
            "message": f"删除失败: {str(e)}"
        }
