"""
价值贡献模型 - 存储员工价值贡献评分
基于绩效酬金偏离度计算
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Date
from sqlalchemy.sql import func
from app.database import Base


class ValueContributionScore(Base):
    """员工价值贡献分数表"""
    
    __tablename__ = "value_contribution_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    emp_code = Column(String(50), nullable=False, index=True, comment='员工工号')
    emp_name = Column(String(100), nullable=False, comment='员工姓名')
    performance_standard = Column(Float, nullable=True, comment='绩效酬金标准')
    actual_performance = Column(Float, nullable=True, comment='实际发放绩效')
    deviation_rate = Column(Float, nullable=True, comment='偏离度(%)')
    score = Column(Float, nullable=True, comment='价值贡献分数(0-100)，当前不存储')
    evaluation_year = Column(Integer, nullable=True, comment='考核年度')
    evaluator = Column(String(100), nullable=True, comment='评定人')
    evaluation_basis = Column(Text, nullable=True, comment='评定依据')
    remark = Column(Text, nullable=True, comment='备注')
    created_at = Column(DateTime, server_default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment='更新时间')
    
    def __repr__(self):
        return f"<ValueContributionScore {self.emp_name}: {self.score}>"
