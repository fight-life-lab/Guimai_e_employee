"""
员工工作经历模型
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.database import Base


class EmpWorkExperience(Base):
    """员工工作经历表"""
    __tablename__ = "ods_emp_work_experience"
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    emp_code = Column(String(50), nullable=False, comment="员工编号")
    emp_name = Column(String(100), nullable=False, comment="员工姓名")
    start_date = Column(Date, comment="开始日期")
    end_date = Column(Date, comment="结束日期")
    company_name = Column(String(200), comment="工作单位")
    department = Column(String(200), comment="部门")
    position = Column(String(100), comment="职务/岗位")
    is_current = Column(Integer, default=0, comment="是否当前在职（1是，0否）")
    source_file = Column(String(255), comment="来源PDF文件名")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "emp_code": self.emp_code,
            "emp_name": self.emp_name,
            "start_date": self.start_date.strftime("%Y-%m-%d") if self.start_date else None,
            "end_date": self.end_date.strftime("%Y-%m-%d") if self.end_date else None,
            "company_name": self.company_name,
            "department": self.department,
            "position": self.position,
            "is_current": self.is_current,
            "source_file": self.source_file,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None
        }
