"""
员工专业能力模型
存储员工的专业能力相关信息：试用期分数、绩效、专家等级、职称、职业技能
"""
from sqlalchemy import Column, Integer, String, DateTime, Date, DECIMAL, JSON, Index
from sqlalchemy.sql import func
from app.database import Base


class EmpProfessionalAbility(Base):
    """员工专业能力表"""
    __tablename__ = "ods_emp_professional_ability"
    
    # 主键和员工标识
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    emp_code = Column(String(50), nullable=False, comment="员工编号")
    emp_name = Column(String(100), nullable=False, comment="员工姓名")
    
    # 试用期信息
    probation_score = Column(DECIMAL(5, 2), comment="试用期分数（0-100分）")
    
    # 历史绩效（JSON格式存储多年绩效）
    # 格式：[{"year":"2023","score":85,"level":"A"},...]
    performance_history = Column(JSON, comment="历往绩效记录")
    
    # 专家等级
    is_company_expert = Column(Integer, default=0, comment="是否为公司专家（0-否，1-是）")
    is_senior_expert = Column(Integer, default=0, comment="是否为高级专家（0-否，1-是）")
    is_chief_expert = Column(Integer, default=0, comment="是否为首席专家（0-否，1-是）")
    expert_appointment_date = Column(Date, comment="专家聘任日期")
    
    # 职称信息（JSON格式，支持多个职称）
    # 格式：[{"title_name":"高级工程师","cert_level":"高级","company_level":"公司级"},...]
    professional_titles = Column(JSON, comment="职称信息")
    
    # 职业技能信息（JSON格式，支持多个技能证书）
    # 格式：[{"skill_name":"Python开发","cert_level":"高级","company_level":"部门级"},...]
    professional_skills = Column(JSON, comment="职业技能信息")
    
    # 其他能力证明
    patents_count = Column(Integer, default=0, comment="专利数量")
    honors_count = Column(Integer, default=0, comment="荣誉奖项数量")
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 索引
    __table_args__ = (
        Index("idx_emp_code", "emp_code"),
        Index("idx_emp_name", "emp_name"),
        Index("idx_expert_level", "is_company_expert", "is_senior_expert", "is_chief_expert"),
        {"comment": "员工专业能力表：存储试用期分数、绩效、专家等级、职称、职业技能等专业能力相关信息"}
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "emp_code": self.emp_code,
            "emp_name": self.emp_name,
            "probation_score": float(self.probation_score) if self.probation_score else None,
            "performance_history": self.performance_history,
            "is_company_expert": bool(self.is_company_expert),
            "is_senior_expert": bool(self.is_senior_expert),
            "is_chief_expert": bool(self.is_chief_expert),
            "expert_appointment_date": self.expert_appointment_date.isoformat() if self.expert_appointment_date else None,
            "professional_titles": self.professional_titles,
            "professional_skills": self.professional_skills,
            "patents_count": self.patents_count,
            "honors_count": self.honors_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
