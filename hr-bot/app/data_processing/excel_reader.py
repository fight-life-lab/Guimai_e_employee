"""Excel file reader for HR data processing."""

import pandas as pd
import numpy as np
from datetime import date, datetime
from typing import List, Optional, Dict, Any
import logging
from pathlib import Path

from .data_models import EmployeeData, AttendanceData, SalaryData


logger = logging.getLogger(__name__)


class ExcelReader:
    """Excel file reader for HR data."""
    
    def __init__(self):
        """Initialize the Excel reader."""
        self.employee_name_cache = {}
    
    def read_employee_roster(self, file_path: str) -> List[EmployeeData]:
        """Read employee roster from Excel file.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            List of EmployeeData objects
        """
        try:
            df = pd.read_excel(file_path)
            logger.info(f"Reading employee roster from {file_path}, found {len(df)} rows")
            
            employees = []
            for _, row in df.iterrows():
                employee = self._parse_employee_row(row)
                if employee:
                    employees.append(employee)
            
            logger.info(f"Successfully parsed {len(employees)} employees")
            return employees
            
        except Exception as e:
            logger.error(f"Error reading employee roster from {file_path}: {e}")
            return []
    
    def read_attendance_records(self, file_path: str) -> List[AttendanceData]:
        """Read attendance records from Excel file.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            List of AttendanceData objects
        """
        try:
            df = pd.read_excel(file_path)
            logger.info(f"Reading attendance records from {file_path}, found {len(df)} rows")
            
            attendance_records = []
            for _, row in df.iterrows():
                record = self._parse_attendance_row(row)
                if record:
                    attendance_records.append(record)
            
            logger.info(f"Successfully parsed {len(attendance_records)} attendance records")
            return attendance_records
            
        except Exception as e:
            logger.error(f"Error reading attendance records from {file_path}: {e}")
            return []
    
    def read_salary_records(self, file_path: str) -> List[SalaryData]:
        """Read salary records from Excel file.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            List of SalaryData objects
        """
        try:
            df = pd.read_excel(file_path)
            logger.info(f"Reading salary records from {file_path}, found {len(df)} rows")
            
            salary_records = []
            for _, row in df.iterrows():
                record = self._parse_salary_row(row)
                if record:
                    salary_records.append(record)
            
            logger.info(f"Successfully parsed {len(salary_records)} salary records")
            return salary_records
            
        except Exception as e:
            logger.error(f"Error reading salary records from {file_path}: {e}")
            return []
    
    def _parse_employee_row(self, row: pd.Series) -> Optional[EmployeeData]:
        """Parse a single employee row from Excel.
        
        Args:
            row: pandas Series representing a row
            
        Returns:
            EmployeeData object or None if parsing fails
        """
        try:
            # Try to find common column names for employee data
            name = self._get_cell_value(row, ["姓名", "员工姓名", "Name", "员工", "name"])
            if not name:
                return None
            
            department = self._get_cell_value(row, ["部门", "Department", "department", "所在部门"])
            position = self._get_cell_value(row, ["职位", "岗位", "Position", "position", "职务"])
            
            # Parse dates
            hire_date = self._parse_date(self._get_cell_value(row, ["入职日期", "Hire Date", "hire_date", "入职时间"]))
            contract_start_date = self._parse_date(self._get_cell_value(row, ["合同开始日期", "Contract Start", "contract_start"]))
            contract_end_date = self._parse_date(self._get_cell_value(row, ["合同结束日期", "Contract End", "contract_end"]))
            
            # Parse contact info
            phone = self._get_cell_value(row, ["电话", "手机", "Phone", "phone", "联系电话"])
            email = self._get_cell_value(row, ["邮箱", "Email", "email", "电子邮箱"])
            
            # Parse performance score
            performance_score = self._parse_float(self._get_cell_value(row, ["绩效分数", "Performance", "performance_score", "绩效"]))
            
            # Parse employee ID
            employee_id = self._get_cell_value(row, ["员工编号", "Employee ID", "employee_id", "工号"])
            
            # Parse status
            status = self._get_cell_value(row, ["状态", "Status", "status", "员工状态"])
            
            # Parse contract type
            contract_type = self._get_cell_value(row, ["合同类型", "Contract Type", "contract_type", "合同"])
            
            return EmployeeData(
                name=name,
                employee_id=employee_id,
                department=department,
                position=position,
                hire_date=hire_date,
                phone=phone,
                email=email,
                status=status,
                contract_type=contract_type,
                contract_start_date=contract_start_date,
                contract_end_date=contract_end_date,
                performance_score=performance_score,
            )
            
        except Exception as e:
            logger.warning(f"Error parsing employee row: {e}")
            return None
    
    def _parse_attendance_row(self, row: pd.Series) -> Optional[AttendanceData]:
        """Parse a single attendance row from Excel.
        
        Args:
            row: pandas Series representing a row
            
        Returns:
            AttendanceData object or None if parsing fails
        """
        try:
            # Try to find employee name
            employee_name = self._get_cell_value(row, ["姓名", "员工姓名", "Name", "员工", "name"])
            if not employee_name:
                return None
            
            # Parse date
            attendance_date = self._parse_date(self._get_cell_value(row, ["日期", "Date", "date", "考勤日期"]))
            if not attendance_date:
                return None
            
            # Parse times
            check_in_time = self._parse_datetime(self._get_cell_value(row, ["签到时间", "Check In", "check_in", "上班时间"]))
            check_out_time = self._parse_datetime(self._get_cell_value(row, ["签退时间", "Check Out", "check_out", "下班时间"]))
            
            # Parse hours
            work_hours = self._parse_float(self._get_cell_value(row, ["工作时长", "Work Hours", "work_hours", "工作小时"]))
            overtime_hours = self._parse_float(self._get_cell_value(row, ["加班时长", "Overtime", "overtime_hours", "加班小时"]))
            
            # Parse leave and status
            leave_type = self._get_cell_value(row, ["请假类型", "Leave Type", "leave_type", "请假"])
            status = self._get_cell_value(row, ["状态", "Status", "status", "考勤状态"])
            remarks = self._get_cell_value(row, ["备注", "Remarks", "remarks", "说明"])
            
            return AttendanceData(
                employee_name=employee_name,
                date=attendance_date,
                check_in_time=check_in_time,
                check_out_time=check_out_time,
                work_hours=work_hours,
                overtime_hours=overtime_hours,
                leave_type=leave_type,
                status=status,
                remarks=remarks,
            )
            
        except Exception as e:
            logger.warning(f"Error parsing attendance row: {e}")
            return None
    
    def _parse_salary_row(self, row: pd.Series) -> Optional[SalaryData]:
        """Parse a single salary row from Excel.
        
        Args:
            row: pandas Series representing a row
            
        Returns:
            SalaryData object or None if parsing fails
        """
        try:
            # Try to find employee name
            employee_name = self._get_cell_value(row, ["姓名", "员工姓名", "Name", "员工", "name"])
            if not employee_name:
                return None
            
            # Parse month (assume it's the first day of the month)
            month_str = self._get_cell_value(row, ["月份", "Month", "month", "薪资月份", "发薪月份"])
            month = self._parse_date(month_str)
            if not month:
                # Try to parse from current row context
                month = date.today().replace(day=1)
            
            # Parse salary components
            base_salary = self._parse_float(self._get_cell_value(row, ["基本工资", "Base Salary", "base_salary", "基本工资"]))
            bonus = self._parse_float(self._get_cell_value(row, ["奖金", "Bonus", "bonus", "绩效奖金"]))
            overtime_pay = self._parse_float(self._get_cell_value(row, ["加班费", "Overtime Pay", "overtime_pay", "加班工资"]))
            deductions = self._parse_float(self._get_cell_value(row, ["扣款", "Deductions", "deductions", "扣款"]))
            net_salary = self._parse_float(self._get_cell_value(row, ["实发工资", "Net Salary", "net_salary", "实发"]))
            
            # Parse social benefits
            social_security = self._parse_float(self._get_cell_value(row, ["社保", "Social Security", "social_security", "社会保险"]))
            housing_fund = self._parse_float(self._get_cell_value(row, ["公积金", "Housing Fund", "housing_fund", "住房公积金"]))
            tax = self._parse_float(self._get_cell_value(row, ["个税", "Tax", "tax", "个人所得税"]))
            
            return SalaryData(
                employee_name=employee_name,
                month=month,
                base_salary=base_salary,
                bonus=bonus,
                overtime_pay=overtime_pay,
                deductions=deductions,
                net_salary=net_salary,
                social_security=social_security,
                housing_fund=housing_fund,
                tax=tax,
            )
            
        except Exception as e:
            logger.warning(f"Error parsing salary row: {e}")
            return None
    
    def _get_cell_value(self, row: pd.Series, possible_columns: List[str]) -> Optional[str]:
        """Get cell value from row using possible column names.
        
        Args:
            row: pandas Series representing a row
            possible_columns: List of possible column names
            
        Returns:
            Cell value or None if not found
        """
        for col in possible_columns:
            if col in row.index and pd.notna(row[col]):
                value = row[col]
                if isinstance(value, str):
                    return value.strip()
                return str(value).strip()
        return None
    
    def _parse_date(self, date_value: Optional[str]) -> Optional[date]:
        """Parse date string to date object.
        
        Args:
            date_value: Date string
            
        Returns:
            date object or None if parsing fails
        """
        if not date_value:
            return None
        
        try:
            # Try different date formats
            date_formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%d/%m/%Y", "%d-%m-%Y"]
            
            if isinstance(date_value, datetime):
                return date_value.date()
            elif isinstance(date_value, date):
                return date_value
            elif isinstance(date_value, str):
                for fmt in date_formats:
                    try:
                        return datetime.strptime(date_value.strip(), fmt).date()
                    except ValueError:
                        continue
            elif isinstance(date_value, (int, float)):
                # Handle Excel date numbers
                try:
                    return datetime.fromordinal(datetime(1900, 1, 1).toordinal() + int(date_value) - 2).date()
                except:
                    pass
            
            return None
            
        except Exception as e:
            logger.warning(f"Error parsing date '{date_value}': {e}")
            return None
    
    def _parse_datetime(self, datetime_value: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object.
        
        Args:
            datetime_value: Datetime string
            
        Returns:
            datetime object or None if parsing fails
        """
        if not datetime_value:
            return None
        
        try:
            if isinstance(datetime_value, datetime):
                return datetime_value
            elif isinstance(datetime_value, str):
                # Try different datetime formats
                datetime_formats = [
                    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M",
                    "%H:%M:%S", "%H:%M"
                ]
                
                for fmt in datetime_formats:
                    try:
                        return datetime.strptime(datetime_value.strip(), fmt)
                    except ValueError:
                        continue
            
            return None
            
        except Exception as e:
            logger.warning(f"Error parsing datetime '{datetime_value}': {e}")
            return None
    
    def _parse_float(self, float_value: Optional[str]) -> Optional[float]:
        """Parse float string to float object.
        
        Args:
            float_value: Float string
            
        Returns:
            float object or None if parsing fails
        """
        if float_value is None:
            return None
        
        try:
            if isinstance(float_value, (int, float)):
                return float(float_value)
            elif isinstance(float_value, str):
                # Remove currency symbols and spaces
                cleaned = float_value.replace("￥", "").replace("¥", "").replace(",", "").replace("元", "").strip()
                return float(cleaned)
            
            return None
            
        except Exception as e:
            logger.warning(f"Error parsing float '{float_value}': {e}")
            return None