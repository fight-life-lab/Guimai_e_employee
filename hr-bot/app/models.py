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

    # Relationships
    contracts: Mapped[List["Contract"]] = relationship("Contract", back_populates="employee", lazy="selectin")
    attendance_records: Mapped[List["AttendanceRecord"]] = relationship("AttendanceRecord", back_populates="employee", lazy="selectin")
    salary_records: Mapped[List["SalaryRecord"]] = relationship("SalaryRecord", back_populates="employee", lazy="selectin")
    conversation_records: Mapped[List["ConversationRecord"]] = relationship("ConversationRecord", back_populates="employee", lazy="selectin")
    resume_info: Mapped[Optional["EmployeeResume"]] = relationship("EmployeeResume", back_populates="employee", lazy="selectin", uselist=False)
    interview_records: Mapped[List["InterviewRecord"]] = relationship("InterviewRecord", back_populates="employee", lazy="selectin")

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
    month: Mapped[datetime.date] = mapped_column(SQLDate, nullable=False, index=True)
    base_salary: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bonus: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overtime_pay: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deductions: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_salary: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    social_security: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    housing_fund: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tax: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="salary_records")


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
