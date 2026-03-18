"""Initialize database with sample data."""

import asyncio
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database.models import Base, Employee, Contract
from app.database.crud import EmployeeCRUD, ContractCRUD

settings = get_settings()

# Sample employee data
SAMPLE_EMPLOYEES = [
    {
        "name": "张三",
        "department": "技术部",
        "position": "高级工程师",
        "hire_date": date(2020, 3, 15),
        "performance_score": 85.5,
        "contract_end_date": date(2025, 6, 30),
        "phone": "13800138001",
        "email": "zhangsan@company.com",
    },
    {
        "name": "李四",
        "department": "技术部",
        "position": "工程师",
        "hire_date": date(2021, 6, 1),
        "performance_score": 55.0,
        "contract_end_date": date(2025, 5, 31),
        "phone": "13800138002",
        "email": "lisi@company.com",
    },
    {
        "name": "王五",
        "department": "市场部",
        "position": "市场经理",
        "hire_date": date(2019, 1, 10),
        "performance_score": 78.0,
        "contract_end_date": date(2025, 12, 31),
        "phone": "13800138003",
        "email": "wangwu@company.com",
    },
    {
        "name": "赵六",
        "department": "人事部",
        "position": "HR专员",
        "hire_date": date(2022, 9, 1),
        "performance_score": 45.5,
        "contract_end_date": date(2025, 8, 31),
        "phone": "13800138004",
        "email": "zhaoliu@company.com",
    },
    {
        "name": "孙七",
        "department": "财务部",
        "position": "会计",
        "hire_date": date(2020, 5, 20),
        "performance_score": 92.0,
        "contract_end_date": date(2025, 4, 15),
        "phone": "13800138005",
        "email": "sunqi@company.com",
    },
]

SAMPLE_CONTRACTS = [
    {
        "employee_id": 1,
        "contract_type": "劳动合同",
        "start_date": date(2022, 7, 1),
        "end_date": date(2025, 6, 30),
        "status": "active",
        "remarks": "续签合同",
    },
    {
        "employee_id": 2,
        "contract_type": "劳动合同",
        "start_date": date(2022, 6, 1),
        "end_date": date(2025, 5, 31),
        "status": "active",
        "remarks": "",
    },
    {
        "employee_id": 5,
        "contract_type": "劳动合同",
        "start_date": date(2022, 4, 16),
        "end_date": date(2025, 4, 15),
        "status": "active",
        "remarks": "即将到期",
    },
]


async def init_database():
    """Initialize database with tables and sample data."""
    print("Initializing database...")

    # Create engine
    engine = create_async_engine(settings.database_url, echo=True)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created.")

    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Insert employees
        print("Inserting sample employees...")
        for emp_data in SAMPLE_EMPLOYEES:
            await EmployeeCRUD.create(session, emp_data)
        print(f"Inserted {len(SAMPLE_EMPLOYEES)} employees.")

        # Insert contracts
        print("Inserting sample contracts...")
        for contract_data in SAMPLE_CONTRACTS:
            await ContractCRUD.create(session, contract_data)
        print(f"Inserted {len(SAMPLE_CONTRACTS)} contracts.")

        await session.commit()

    print("Database initialization completed!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_database())
