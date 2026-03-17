"""Data models for HR data processing."""

from datetime import date, datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class EmployeeData:
    """Employee data model."""
    
    name: str
    employee_id: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    hire_date: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    contract_type: Optional[str] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    performance_score: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "name": self.name,
            "department": self.department,
            "position": self.position,
            "hire_date": self.hire_date,
            "phone": self.phone,
            "email": self.email,
            "performance_score": self.performance_score,
            "contract_end_date": self.contract_end_date,
        }


@dataclass
class AttendanceData:
    """Attendance data model."""
    
    employee_name: str
    date: date
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    work_hours: Optional[float] = None
    overtime_hours: Optional[float] = None
    leave_type: Optional[str] = None
    status: Optional[str] = None  # 正常、迟到、早退、请假、旷工
    remarks: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "employee_name": self.employee_name,
            "date": self.date,
            "check_in_time": self.check_in_time,
            "check_out_time": self.check_out_time,
            "work_hours": self.work_hours,
            "overtime_hours": self.overtime_hours,
            "leave_type": self.leave_type,
            "status": self.status,
            "remarks": self.remarks,
        }


@dataclass
class SalaryData:
    """Salary data model."""
    
    employee_name: str
    month: date
    base_salary: Optional[float] = None
    bonus: Optional[float] = None
    overtime_pay: Optional[float] = None
    deductions: Optional[float] = None
    net_salary: Optional[float] = None
    social_security: Optional[float] = None
    housing_fund: Optional[float] = None
    tax: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "employee_name": self.employee_name,
            "month": self.month,
            "base_salary": self.base_salary,
            "bonus": self.bonus,
            "overtime_pay": self.overtime_pay,
            "deductions": self.deductions,
            "net_salary": self.net_salary,
            "social_security": self.social_security,
            "housing_fund": self.housing_fund,
            "tax": self.tax,
        }


@dataclass
class ConversationRecord:
    """Conversation record data model."""
    
    employee_name: str
    conversation_date: date
    conversation_type: Optional[str] = None  # 谈心谈话、绩效面谈、离职面谈等
    participants: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    follow_up_actions: Optional[str] = None
    next_meeting_date: Optional[date] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "employee_name": self.employee_name,
            "conversation_date": self.conversation_date,
            "conversation_type": self.conversation_type,
            "participants": self.participants,
            "content": self.content,
            "summary": self.summary,
            "follow_up_actions": self.follow_up_actions,
            "next_meeting_date": self.next_meeting_date,
        }