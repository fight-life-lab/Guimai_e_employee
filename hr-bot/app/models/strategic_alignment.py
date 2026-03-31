"""
战略匹配分数模型 - 存储员工战略匹配评分
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Date
from sqlalchemy.sql import func
from app.database import Base


class StrategicAlignmentScore(Base):
    """员工战略匹配分数表"""
    
    __tablename__ = "strategic_alignment_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    emp_code = Column(String(50), nullable=False, index=True, comment='员工工号')
    emp_name = Column(String(100), nullable=False, comment='员工姓名')
    score = Column(Float, nullable=False, comment='战略匹配分数(0-100)')
    evaluation_year = Column(Integer, nullable=True, comment='考核年度')
    evaluator = Column(String(100), nullable=True, comment='评定人')
    evaluation_basis = Column(Text, nullable=True, comment='评定依据')
    created_at = Column(DateTime, server_default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment='更新时间')
    
    def __repr__(self):
        return f"<StrategicAlignmentScore {self.emp_name}: {self.score}>"
