"""Database models."""

from datetime import date
from typing import Optional

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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
    hire_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    performance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    contract_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Relationship
    contracts: Mapped[list["Contract"]] = relationship(
        "Contract", back_populates="employee", lazy="selectin"
    )

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
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="active", nullable=False
    )  # active, expired, terminated
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    employee: Mapped["Employee"] = relationship("Employee", back_populates="contracts")

    def __repr__(self) -> str:
        return f"<Contract {self.id} for Employee {self.employee_id}>"
