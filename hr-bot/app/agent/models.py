"""Database models - 适配现有数据库结构."""

import datetime
from typing import Optional, List

from sqlalchemy import Date as SQLDate, DateTime, Float, ForeignKey, Integer, String, Text, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Employee(Base):
    """Employee information model - 适配现有数据库结构."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    position: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entry_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)  # 入职日期
    contract_end_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)
    performance_rating: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)  # 绩效等级 A/B/C/D
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="active")
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True, default=datetime.datetime.now)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    def __repr__(self) -> str:
        return f"<Employee {self.name} ({self.department})>"


class Contract(Base):
    """Contract information model."""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id"), nullable=False
    )
    contract_type: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )  # 劳动合同、劳务合同等
    start_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)
    end_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="active", nullable=False
    )  # active, expired, terminated
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Contract {self.id} for Employee {self.employee_id}>"


class AttendanceRecord(Base):
    """Attendance record model."""

    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id"), nullable=False, index=True
    )
    date: Mapped[datetime.date] = mapped_column(SQLDate, nullable=False, index=True)
    check_in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    check_out_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    work_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overtime_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    leave_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 正常、迟到、早退、请假、旷工
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AttendanceRecord {self.id} for Employee {self.employee_id} on {self.date}>"


class ConversationRecord(Base):
    """Conversation record model."""

    __tablename__ = "conversation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id"), nullable=False, index=True
    )
    conversation_date: Mapped[datetime.date] = mapped_column(SQLDate, nullable=False, index=True)
    conversation_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 谈心谈话、绩效面谈、离职面谈等
    participants: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_meeting_date: Mapped[Optional[datetime.date]] = mapped_column(SQLDate, nullable=True)

    def __repr__(self) -> str:
        return f"<ConversationRecord {self.id} for Employee {self.employee_id} on {self.conversation_date}>"


# ============ 数据库会话管理 ============

# 使用MySQL数据库（数据不出域，本地Docker部署）
DATABASE_URL = "mysql+aiomysql://hr_user:hr_password@localhost:3306/hr_employee_db"

# 创建异步引擎
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # 自动检测连接是否有效
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
    # 不自动创建表，因为表已存在
    pass
