"""
员工专利明细模型
"""
from sqlalchemy import Column, Integer, String, Date, DateTime
from sqlalchemy.sql import func
from app.database import Base


class EmpPatent(Base):
    """员工专利明细表"""
    __tablename__ = "ods_emp_patent_detail"
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    emp_code = Column(String(50), nullable=False, comment="员工编号")
    emp_name = Column(String(100), nullable=False, comment="员工姓名")
    patent_name = Column(String(500), comment="专利名称")
    patent_type = Column(String(50), comment="专利类型：发明专利、实用新型专利、外观设计专利")
    patent_no = Column(String(100), comment="专利号")
    authorize_date = Column(Date, comment="授权日期")
    is_authorized = Column(Integer, default=1, comment="是否已授权（1是，0否）")
    rank_inventors = Column(Integer, comment="发明人排名")
    source_file = Column(String(255), comment="来源文件名")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "emp_code": self.emp_code,
            "emp_name": self.emp_name,
            "patent_name": self.patent_name,
            "patent_type": self.patent_type,
            "patent_no": self.patent_no,
            "authorize_date": self.authorize_date.strftime("%Y-%m-%d") if self.authorize_date else None,
            "is_authorized": self.is_authorized,
            "rank_inventors": self.rank_inventors,
            "source_file": self.source_file,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None
        }
