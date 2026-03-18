"""Database CRUD operations."""

from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import Contract, Employee


class EmployeeCRUD:
    """CRUD operations for Employee model."""

    @staticmethod
    async def create(db: AsyncSession, employee_data: dict) -> Employee:
        """Create a new employee."""
        employee = Employee(**employee_data)
        db.add(employee)
        await db.commit()
        await db.refresh(employee)
        return employee

    @staticmethod
    async def get_by_id(db: AsyncSession, employee_id: int) -> Optional[Employee]:
        """Get employee by ID."""
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(db: AsyncSession, name: str) -> Optional[Employee]:
        """Get employee by name."""
        result = await db.execute(
            select(Employee).where(Employee.name == name)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(
        db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[Employee]:
        """Get all employees with pagination."""
        result = await db.execute(select(Employee).offset(skip).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_department(
        db: AsyncSession, department: str
    ) -> List[Employee]:
        """Get employees by department."""
        result = await db.execute(
            select(Employee).where(Employee.department == department)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_low_performance(
        db: AsyncSession, threshold: Optional[float] = None
    ) -> List[Employee]:
        """Get employees with low performance."""
        if threshold is None:
            threshold = get_settings().performance_threshold

        result = await db.execute(
            select(Employee).where(
                Employee.performance_score < threshold,
                Employee.performance_score.isnot(None),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_contract_expiring(
        db: AsyncSession, days: Optional[int] = None
    ) -> List[Employee]:
        """Get employees with contracts expiring within days."""
        if days is None:
            days = get_settings().contract_alert_days

        target_date = date.today() + timedelta(days=days)

        result = await db.execute(
            select(Employee).where(
                Employee.contract_end_date <= target_date,
                Employee.contract_end_date >= date.today(),
            )
        )
        return list(result.scalars().all())


class ContractCRUD:
    """CRUD operations for Contract model."""

    @staticmethod
    async def create(db: AsyncSession, contract_data: dict) -> Contract:
        """Create a new contract."""
        contract = Contract(**contract_data)
        db.add(contract)
        await db.commit()
        await db.refresh(contract)
        return contract

    @staticmethod
    async def get_by_id(db: AsyncSession, contract_id: int) -> Optional[Contract]:
        """Get contract by ID."""
        result = await db.execute(
            select(Contract).where(Contract.id == contract_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_employee(
        db: AsyncSession, employee_id: int
    ) -> List[Contract]:
        """Get contracts by employee ID."""
        result = await db.execute(
            select(Contract).where(Contract.employee_id == employee_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_expiring_contracts(
        db: AsyncSession, days: Optional[int] = None
    ) -> List[Contract]:
        """Get contracts expiring within days."""
        if days is None:
            days = get_settings().contract_alert_days

        target_date = date.today() + timedelta(days=days)

        result = await db.execute(
            select(Contract)
            .where(
                Contract.end_date <= target_date,
                Contract.end_date >= date.today(),
                Contract.status == "active",
            )
            .join(Employee)
        )
        return list(result.scalars().all())
