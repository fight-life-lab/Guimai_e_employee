"""HR tools for LangChain agent."""

from datetime import date
from typing import Optional

from langchain.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.crud import EmployeeCRUD


@tool
def query_employee_info(name: str) -> str:
    """Query employee information by name.
    
    Args:
        name: Employee name
        
    Returns:
        Employee information as formatted string
    """
    # This is a synchronous wrapper for async operation
    # In actual implementation, this would query the database
    return f"查询员工: {name} 的信息（需要数据库连接）"


@tool
def get_contract_alerts(days: int = 30) -> str:
    """Get employees with contracts expiring within specified days.
    
    Args:
        days: Number of days to check (default: 30)
        
    Returns:
        List of employees with expiring contracts
    """
    return f"查询未来 {days} 天内合同到期的员工（需要数据库连接）"


@tool
def get_low_performance(threshold: float = 60.0) -> str:
    """Get employees with performance score below threshold.
    
    Args:
        threshold: Performance threshold (default: 60.0)
        
    Returns:
        List of low performance employees
    """
    return f"查询绩效分数低于 {threshold} 分的员工（需要数据库连接）"


@tool
def query_policy(keyword: str) -> str:
    """Query company policies by keyword.
    
    Args:
        keyword: Policy keyword to search
        
    Returns:
        Relevant policy information
    """
    return f"查询包含关键词 '{keyword}' 的规章制度（需要向量数据库）"


# Async versions for actual implementation
async def query_employee_info_async(
    db: AsyncSession, name: str
) -> str:
    """Async version of query_employee_info."""
    employee = await EmployeeCRUD.get_by_name(db, name)
    
    if not employee:
        return f"未找到员工: {name}"
    
    info = f"""员工信息:
姓名: {employee.name}
部门: {employee.department or '未知'}
职位: {employee.position or '未知'}
入职日期: {employee.hire_date or '未知'}
绩效分数: {employee.performance_score or '未评分'}
合同到期: {employee.contract_end_date or '未知'}
"""
    return info


async def get_contract_alerts_async(
    db: AsyncSession, days: Optional[int] = None
) -> str:
    """Async version of get_contract_alerts."""
    if days is None:
        days = get_settings().contract_alert_days
    
    employees = await EmployeeCRUD.get_contract_expiring(db, days)
    
    if not employees:
        return f"未来 {days} 天内没有合同到期的员工"
    
    result = f"未来 {days} 天内合同到期的员工:\n\n"
    for emp in employees:
        result += f"- {emp.name} ({emp.department}): 合同到期 {emp.contract_end_date}\n"
    
    return result


async def get_low_performance_async(
    db: AsyncSession, threshold: Optional[float] = None
) -> str:
    """Async version of get_low_performance."""
    if threshold is None:
        threshold = get_settings().performance_threshold
    
    employees = await EmployeeCRUD.get_low_performance(db, threshold)
    
    if not employees:
        return f"没有绩效分数低于 {threshold} 分的员工"
    
    result = f"绩效分数低于 {threshold} 分的员工:\n\n"
    for emp in employees:
        result += f"- {emp.name} ({emp.department}): {emp.performance_score}分\n"
    
    return result
