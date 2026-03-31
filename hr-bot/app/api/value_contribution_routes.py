"""
价值贡献分数管理API
支持批量导入和查询员工价值贡献分数
基于绩效酬金偏离度计算
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import pandas as pd
import logging
from datetime import datetime

from app.models.value_contribution import ValueContributionScore
from app.database import get_db

router = APIRouter(prefix="/api/v1/value-contribution", tags=["价值贡献分数管理"])

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


class ValueContributionScoreItem(BaseModel):
    """价值贡献分数项"""
    emp_code: str
    emp_name: str
    performance_standard: Optional[float] = None
    actual_performance: Optional[float] = None
    deviation_rate: Optional[float] = None
    score: float
    evaluation_year: Optional[int] = None
    evaluator: Optional[str] = None
    evaluation_basis: Optional[str] = None
    remark: Optional[str] = None


class ValueContributionScoreResponse(BaseModel):
    """价值贡献分数响应"""
    success: bool
    message: str
    data: Optional[List[ValueContributionScoreItem]] = None
    errors: Optional[List[str]] = None


def get_db_session():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def calculate_value_contribution_score(deviation_rate: float) -> float:
    """
    根据偏离度计算价值贡献分数
    
    计分规则：
    - 基础分70分，满分上限100分
    - 偏离度为100%时，不加分、不扣分
    - 偏离度较100%，每高出0.5个百分点，加3分
    - 偏离度较100%，每低出0.5个百分点，扣3分
    """
    base_score = 70
    
    # 计算偏离100%的差值
    diff = deviation_rate - 100
    
    # 每0.5个百分点变化3分
    score_change = (diff / 0.5) * 3
    
    # 计算最终分数
    final_score = base_score + score_change
    
    # 限制在0-100范围内
    final_score = max(0, min(100, final_score))
    
    return round(final_score, 2)


@router.post("/import", response_model=ValueContributionScoreResponse)
async def import_value_contribution_scores(
    file: UploadFile = File(...),
    evaluation_year: Optional[int] = None,
    evaluator: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """
    批量导入价值贡献分数
    
    支持Excel文件格式，文件需包含以下列：
    - MSS人员编码/工号/员工编号
    - 姓名/员工姓名
    - 绩效酬金标准（可选）
    - 实际发放绩效（可选）
    - 偏离度（可选，如果没有则根据绩效酬金标准和实际发放绩效计算）
    - 扣分/加分（可选，直接作为分数调整）
    
    参数:
    - file: Excel文件
    - evaluation_year: 考核年度（可选，默认当前年份）
    - evaluator: 评定人（可选）
    """
    try:
        # 检查文件类型
        if not file.filename.endswith(('.xlsx', '.xls')):
            return ValueContributionScoreResponse(
                success=False,
                message="只支持Excel文件格式(.xlsx, .xls)",
                errors=["文件格式错误"]
            )
        
        # 读取Excel文件
        df = pd.read_excel(file.file)
        
        # 标准化列名
        column_mapping = {
            'MSS人员编码': 'emp_code',
            '工号': 'emp_code',
            '员工编号': 'emp_code',
            '员工号': 'emp_code',
            '编号': 'emp_code',
            '姓名': 'emp_name',
            '员工姓名': 'emp_name',
            '名字': 'emp_name',
            '绩效酬金标准': 'performance_standard',
            '标准': 'performance_standard',
            '实际发放绩效': 'actual_performance',
            '实际发放': 'actual_performance',
            '实际绩效': 'actual_performance',
            '偏离度': 'deviation_rate',
            '偏离': 'deviation_rate',
            '扣分': 'score_adjustment',
            '加分': 'score_adjustment',
            '调整分': 'score_adjustment',
            '备注': 'remark'
        }
        
        # 重命名列
        df.rename(columns=lambda x: column_mapping.get(str(x).strip(), x), inplace=True)
        
        # 检查必需列
        required_columns = ['emp_code', 'emp_name']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return ValueContributionScoreResponse(
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
                
                # 获取绩效数据
                performance_standard = None
                actual_performance = None
                deviation_rate = None
                
                if 'performance_standard' in df.columns and pd.notna(row['performance_standard']):
                    performance_standard = float(row['performance_standard'])
                
                if 'actual_performance' in df.columns and pd.notna(row['actual_performance']):
                    actual_performance = float(row['actual_performance'])
                
                if 'deviation_rate' in df.columns and pd.notna(row['deviation_rate']):
                    # 处理百分比格式（如"98.6%"）
                    deviation_str = str(row['deviation_rate']).replace('%', '').strip()
                    deviation_rate = float(deviation_str)
                elif performance_standard and actual_performance and performance_standard > 0:
                    # 根据绩效酬金标准和实际发放绩效计算偏离度
                    deviation_rate = (actual_performance / performance_standard) * 100
                
                # 计算价值贡献分数
                if deviation_rate is not None:
                    score = calculate_value_contribution_score(deviation_rate)
                elif 'score_adjustment' in df.columns and pd.notna(row['score_adjustment']):
                    # 如果有直接的分数调整，使用基础分70分加上调整分
                    adjustment = float(row['score_adjustment'])
                    score = 70 + adjustment
                    score = max(0, min(100, score))
                    deviation_rate = 100 + (adjustment / 3) * 0.5
                else:
                    error_list.append(f"第{index + 2}行: 缺少偏离度或绩效数据，无法计算分数")
                    continue
                
                # 验证分数范围
                if score < 0 or score > 100:
                    error_list.append(f"第{index + 2}行: 分数{score}超出范围(0-100)")
                    continue
                
                # 获取备注
                remark = None
                if 'remark' in df.columns and pd.notna(row['remark']):
                    remark = str(row['remark'])
                
                # 检查是否已存在记录
                existing = db.query(ValueContributionScore).filter(
                    ValueContributionScore.emp_code == emp_code,
                    ValueContributionScore.evaluation_year == evaluation_year
                ).first()
                
                if existing:
                    # 更新现有记录
                    existing.score = score
                    existing.emp_name = emp_name
                    existing.performance_standard = performance_standard
                    existing.actual_performance = actual_performance
                    existing.deviation_rate = deviation_rate
                    existing.evaluator = evaluator
                    existing.evaluation_basis = f"批量导入于{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    existing.remark = remark
                else:
                    # 创建新记录
                    new_score = ValueContributionScore(
                        emp_code=emp_code,
                        emp_name=emp_name,
                        performance_standard=performance_standard,
                        actual_performance=actual_performance,
                        deviation_rate=deviation_rate,
                        score=score,
                        evaluation_year=evaluation_year,
                        evaluator=evaluator,
                        evaluation_basis=f"批量导入于{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        remark=remark
                    )
                    db.add(new_score)
                
                success_count += 1
                imported_data.append(ValueContributionScoreItem(
                    emp_code=emp_code,
                    emp_name=emp_name,
                    performance_standard=performance_standard,
                    actual_performance=actual_performance,
                    deviation_rate=deviation_rate,
                    score=score,
                    evaluation_year=evaluation_year,
                    evaluator=evaluator,
                    remark=remark
                ))
                
            except Exception as e:
                error_list.append(f"第{index + 2}行: {str(e)}")
                logger.error(f"处理第{index + 2}行数据时出错: {e}")
        
        # 提交事务
        db.commit()
        
        return ValueContributionScoreResponse(
            success=True,
            message=f"成功导入{success_count}条记录",
            data=imported_data,
            errors=error_list if error_list else None
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"批量导入价值贡献分数失败: {e}")
        return ValueContributionScoreResponse(
            success=False,
            message=f"导入失败: {str(e)}",
            errors=[str(e)]
        )


@router.get("/score/{emp_code}")
async def get_value_contribution_score(
    emp_code: str,
    evaluation_year: Optional[int] = None,
    db: Session = Depends(get_db_session)
):
    """
    获取员工价值贡献分数
    
    参数:
    - emp_code: 员工工号
    - evaluation_year: 考核年度（可选，默认当前年份）
    """
    try:
        if evaluation_year is None:
            evaluation_year = datetime.now().year
        
        score_record = db.query(ValueContributionScore).filter(
            ValueContributionScore.emp_code == emp_code,
            ValueContributionScore.evaluation_year == evaluation_year
        ).first()
        
        if score_record:
            return {
                "success": True,
                "data": {
                    "emp_code": score_record.emp_code,
                    "emp_name": score_record.emp_name,
                    "performance_standard": score_record.performance_standard,
                    "actual_performance": score_record.actual_performance,
                    "deviation_rate": score_record.deviation_rate,
                    "score": score_record.score,
                    "evaluation_year": score_record.evaluation_year,
                    "evaluator": score_record.evaluator,
                    "evaluation_basis": score_record.evaluation_basis,
                    "remark": score_record.remark,
                    "updated_at": score_record.updated_at.strftime("%Y-%m-%d %H:%M:%S") if score_record.updated_at else None
                }
            }
        else:
            return {
                "success": False,
                "message": f"未找到员工{emp_code}在{evaluation_year}年的价值贡献分数"
            }
            
    except Exception as e:
        logger.error(f"获取价值贡献分数失败: {e}")
        return {
            "success": False,
            "message": f"查询失败: {str(e)}"
        }


@router.get("/scores")
async def list_value_contribution_scores(
    evaluation_year: Optional[int] = None,
    emp_name: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db_session)
):
    """
    查询价值贡献分数列表
    
    参数:
    - evaluation_year: 考核年度（可选）
    - emp_name: 员工姓名（可选，支持模糊查询）
    - page: 页码（默认1）
    - page_size: 每页数量（默认50）
    """
    try:
        query = db.query(ValueContributionScore)
        
        if evaluation_year:
            query = query.filter(ValueContributionScore.evaluation_year == evaluation_year)
        
        if emp_name:
            query = query.filter(ValueContributionScore.emp_name.like(f"%{emp_name}%"))
        
        # 计算总数
        total = query.count()
        
        # 分页
        scores = query.order_by(ValueContributionScore.score.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return {
            "success": True,
            "data": [
                {
                    "emp_code": s.emp_code,
                    "emp_name": s.emp_name,
                    "performance_standard": s.performance_standard,
                    "actual_performance": s.actual_performance,
                    "deviation_rate": s.deviation_rate,
                    "score": s.score,
                    "evaluation_year": s.evaluation_year,
                    "evaluator": s.evaluator,
                    "remark": s.remark,
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
        logger.error(f"查询价值贡献分数列表失败: {e}")
        return {
            "success": False,
            "message": f"查询失败: {str(e)}"
        }


@router.post("/score")
async def create_or_update_value_contribution_score(
    item: ValueContributionScoreItem,
    db: Session = Depends(get_db_session)
):
    """
    创建或更新单个员工价值贡献分数
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
        existing = db.query(ValueContributionScore).filter(
            ValueContributionScore.emp_code == item.emp_code,
            ValueContributionScore.evaluation_year == item.evaluation_year
        ).first()
        
        if existing:
            # 更新现有记录
            existing.score = item.score
            existing.emp_name = item.emp_name
            existing.performance_standard = item.performance_standard
            existing.actual_performance = item.actual_performance
            existing.deviation_rate = item.deviation_rate
            existing.evaluator = item.evaluator
            existing.evaluation_basis = item.evaluation_basis
            existing.remark = item.remark
            message = "更新成功"
        else:
            # 创建新记录
            new_score = ValueContributionScore(
                emp_code=item.emp_code,
                emp_name=item.emp_name,
                performance_standard=item.performance_standard,
                actual_performance=item.actual_performance,
                deviation_rate=item.deviation_rate,
                score=item.score,
                evaluation_year=item.evaluation_year,
                evaluator=item.evaluator,
                evaluation_basis=item.evaluation_basis,
                remark=item.remark
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
        logger.error(f"保存价值贡献分数失败: {e}")
        return {
            "success": False,
            "message": f"保存失败: {str(e)}"
        }


@router.delete("/score/{emp_code}")
async def delete_value_contribution_score(
    emp_code: str,
    evaluation_year: Optional[int] = None,
    db: Session = Depends(get_db_session)
):
    """
    删除员工价值贡献分数
    
    参数:
    - emp_code: 员工工号
    - evaluation_year: 考核年度（可选，默认当前年份）
    """
    try:
        if evaluation_year is None:
            evaluation_year = datetime.now().year
        
        score_record = db.query(ValueContributionScore).filter(
            ValueContributionScore.emp_code == emp_code,
            ValueContributionScore.evaluation_year == evaluation_year
        ).first()
        
        if score_record:
            db.delete(score_record)
            db.commit()
            return {
                "success": True,
                "message": f"成功删除员工{emp_code}在{evaluation_year}年的价值贡献分数"
            }
        else:
            return {
                "success": False,
                "message": f"未找到员工{emp_code}在{evaluation_year}年的价值贡献分数"
            }
            
    except Exception as e:
        db.rollback()
        logger.error(f"删除价值贡献分数失败: {e}")
        return {
            "success": False,
            "message": f"删除失败: {str(e)}"
        }
