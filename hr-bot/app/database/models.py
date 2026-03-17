"""Database models - 使用SQLite数据库."""

import datetime
from typing import Optional, List

from sqlalchemy import Date as SQLDate, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Employee(Base):
    """Employee information model."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    birth_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hire_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)
    contract_end_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    education: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    school: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    major: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    political_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    ethnicity: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    employee_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    job_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    sequence: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    work_location: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    performance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # 学校评分信息（用于创新能力计算）
    school_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 学校类型（国内/海外）
    rank_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 排名信息（JSON格式）
    bonus_score: Mapped[Optional[float]] = mapped_column(Float, default=0.0)  # 加分分值
    bonus_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 加分依据
    
    # 职称信息（与数据库字段名保持一致）
    professional_title: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 职称名称
    professional_major: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # 职称专业
    professional_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 职称级别(初级/中级/高级)
    professional_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)  # 取得职称时间
    professional_cert_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 职称证书编号
    professional_cert_file: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # 职称证书文件路径

    # Relationships
    contracts: Mapped[List["Contract"]] = relationship("Contract", back_populates="employee", lazy="selectin")
    attendance_records: Mapped[List["AttendanceRecord"]] = relationship("AttendanceRecord", back_populates="employee", lazy="selectin")
    salary_records: Mapped[List["SalaryRecord"]] = relationship("SalaryRecord", back_populates="employee", lazy="selectin")
    conversation_records: Mapped[List["ConversationRecord"]] = relationship("ConversationRecord", back_populates="employee", lazy="selectin")
    resume_info: Mapped[Optional["EmployeeResume"]] = relationship("EmployeeResume", back_populates="employee", lazy="selectin", uselist=False)
    interview_records: Mapped[List["InterviewRecord"]] = relationship("InterviewRecord", back_populates="employee", lazy="selectin")
    historical_performances: Mapped[List["EmployeeHistoricalPerformance"]] = relationship("EmployeeHistoricalPerformance", back_populates="employee", lazy="selectin")
    salary_standards: Mapped[List["EmployeeSalaryStandard"]] = relationship("EmployeeSalaryStandard", back_populates="employee", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Employee {self.name} ({self.department})>"


class Contract(Base):
    """Contract information model."""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False)
    contract_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    start_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)
    end_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="contracts")


class AttendanceRecord(Base):
    """Attendance record model."""

    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    date: Mapped[datetime.date] = mapped_column(SQLDate, nullable=False, index=True)
    check_in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    check_out_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    work_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overtime_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    leave_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="attendance_records")


class SalaryRecord(Base):
    """Salary record model."""

    __tablename__ = "salary_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    month: Mapped[str] = mapped_column("salary_period", String(10), nullable=False, index=True)
    mss_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sub_department: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    employee_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    base_salary: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    performance_salary: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    monthly_performance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    benefit_performance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    annual_performance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bonus: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    allowance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overtime_pay: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    other_income: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross_salary: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pension_insurance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    medical_insurance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unemployment_insurance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    housing_fund: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    personal_income_tax: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    other_deductions: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_salary: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="salary_records")


class EmployeeHistoricalPerformance(Base):
    """Employee historical performance record model."""

    __tablename__ = "employee_historical_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    performance_level: Mapped[str] = mapped_column(String(20), nullable=False)
    performance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=70.0)
    adjustment_coefficient: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.0)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="historical_performances")


class EmployeeSalaryStandard(Base):
    """Employee salary standard record model."""

    __tablename__ = "employee_salary_standards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    salary_period: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    annual_salary_standard: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    base_salary_annual: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    performance_salary_annual: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    monthly_performance_annual: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    benefit_performance_annual: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    annual_performance_annual: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    monthly_salary_standard: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    base_salary_monthly: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    monthly_performance_monthly: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    benefit_performance_monthly: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    annual_performance_monthly: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    month_bonus: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="salary_standards")


class ConversationRecord(Base):
    """Conversation record model."""

    __tablename__ = "conversation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    conversation_date: Mapped[datetime.date] = mapped_column(SQLDate, nullable=False, index=True)
    conversation_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    participants: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_meeting_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="conversation_records")


class EmployeeResume(Base):
    """Employee resume information."""

    __tablename__ = "employee_resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False, unique=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    id_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    education_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    work_experience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    skills: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    self_evaluation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_salary: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_file: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="resume_info")


class InterviewRecord(Base):
    """Interview record model."""

    __tablename__ = "interview_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False)
    interview_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)
    interview_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    interviewer: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    professional_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    communication_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evaluation_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strengths: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weaknesses: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    proposed_position: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    proposed_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    proposed_salary: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_file: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="interview_records")


class PolicyDocument(Base):
    """Policy document model."""

    __tablename__ = "policy_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doc_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    publish_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_chunks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_file: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


class PositionCapabilityModel(Base):
    """Position capability model - 岗位能力模型."""

    __tablename__ = "position_capability_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    position_name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    job_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    
    # 6维度能力标准（0-100分）
    professional_standard: Mapped[int] = mapped_column(Integer, default=80)
    adaptability_standard: Mapped[int] = mapped_column(Integer, default=80)
    innovation_standard: Mapped[int] = mapped_column(Integer, default=80)
    learning_standard: Mapped[int] = mapped_column(Integer, default=80)
    attendance_standard: Mapped[int] = mapped_column(Integer, default=80)
    political_standard: Mapped[int] = mapped_column(Integer, default=80)
    
    # 维度权重
    professional_weight: Mapped[float] = mapped_column(Float, default=1.0)
    adaptability_weight: Mapped[float] = mapped_column(Float, default=1.0)
    innovation_weight: Mapped[float] = mapped_column(Float, default=1.0)
    learning_weight: Mapped[float] = mapped_column(Float, default=1.0)
    attendance_weight: Mapped[float] = mapped_column(Float, default=1.0)
    political_weight: Mapped[float] = mapped_column(Float, default=0.8)
    
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


class AttendancePolicy(Base):
    """Attendance policy - 工时管理条例."""

    __tablename__ = "attendance_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    policy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    condition_type: Mapped[str] = mapped_column(String(50), nullable=False)
    threshold_value: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    period_days: Mapped[int] = mapped_column(Integer, default=90)
    
    alert_level: Mapped[str] = mapped_column(String(20), nullable=False)
    alert_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_doc: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Integer, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


class PositionDescription(Base):
    """Position description - 岗位说明书."""

    __tablename__ = "position_descriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    position_name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    job_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    
    position_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    qualifications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    report_to: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    subordinate_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    salary_range_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_range_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


class AlignmentAnalysisRecord(Base):
    """Alignment analysis record - 人岗适配分析记录."""

    __tablename__ = "alignment_analysis_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False)
    analysis_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)

    # 员工实际得分
    professional_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    adaptability_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    innovation_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    learning_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    attendance_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    political_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 岗位标准要求
    professional_standard: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    adaptability_standard: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    innovation_standard: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    learning_standard: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    attendance_standard: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    political_standard: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 匹配度
    overall_match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    match_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # 工时管理情况
    attendance_violations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 分析结论
    conclusion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ProbationAssessment(Base):
    """试用期考核表 - 存储员工试用期考核分数."""

    __tablename__ = "probation_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    # 考核基本信息
    assessment_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)
    assessor: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # 考核人
    assessor_department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # 考核人部门

    # 考核维度分数（原始分数，未归一化）
    work_performance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 工作业绩
    professional_skill_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 专业技能
    work_attitude_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 工作态度
    teamwork_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 团队协作
    learning_ability_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 学习能力

    # 总分（原始分数）
    total_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 考核结果
    assessment_result: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 通过/不通过
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 评语

    # 源文件
    source_file: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    employee: Mapped["Employee"] = relationship("Employee", lazy="selectin")


class SchoolRating(Base):
    """学校评分配置表."""

    __tablename__ = "school_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    school_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)  # 学校名称
    school_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 学校类型（国内/海外）
    rank_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 排名信息（JSON格式）
    bonus_score: Mapped[float] = mapped_column(Float, default=0.0)  # 加分分值
    bonus_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 加分依据
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 备注

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


# ============ 数据库会话管理 ============

# 使用SQLite数据库（本地文件，数据不出域）
DATABASE_URL = "sqlite+aiosqlite:///./data/hr_database.db"

# 创建异步引擎
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
)

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncSession:
    """获取数据库会话（用于依赖注入）."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_database():
    """初始化数据库表结构."""
    # SQLite数据库已存在，不需要创建表
    pass
