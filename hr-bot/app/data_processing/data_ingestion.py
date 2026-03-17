"""Data ingestion pipeline for HR data processing."""

import logging
from datetime import date
from typing import List, Optional, Dict, Any
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.models import Employee, AttendanceRecord, SalaryRecord, ConversationRecord
from app.database.crud import EmployeeCRUD, AttendanceRecordCRUD, SalaryRecordCRUD, ConversationRecordCRUD
from app.data_processing.excel_reader import ExcelReader
from app.data_processing.conversation_processor import ConversationProcessor
from app.data_processing.data_models import EmployeeData, AttendanceData, SalaryData


logger = logging.getLogger(__name__)


class DataIngestionPipeline:
    """Data ingestion pipeline for HR data."""
    
    def __init__(self):
        """Initialize the data ingestion pipeline."""
        self.excel_reader = ExcelReader()
        self.conversation_processor = ConversationProcessor()
        self.employee_cache = {}  # Cache for employee ID lookups
    
    async def process_employee_roster(self, db: AsyncSession, file_path: str) -> int:
        """Process employee roster file and store in database.
        
        Args:
            db: Database session
            file_path: Path to employee roster Excel file
            
        Returns:
            Number of employees processed
        """
        logger.info(f"Processing employee roster from {file_path}")
        
        # Read employee data from Excel
        employee_data_list = self.excel_reader.read_employee_roster(file_path)
        if not employee_data_list:
            logger.warning("No employee data found in file")
            return 0
        
        processed_count = 0
        
        for employee_data in employee_data_list:
            try:
                # Check if employee already exists
                existing_employee = await EmployeeCRUD.get_by_name(db, employee_data.name)
                
                if existing_employee:
                    # Update existing employee
                    await self._update_employee(db, existing_employee, employee_data)
                    employee_id = existing_employee.id
                    logger.info(f"Updated existing employee: {employee_data.name}")
                else:
                    # Create new employee
                    employee_dict = employee_data.to_dict()
                    new_employee = await EmployeeCRUD.create(db, employee_dict)
                    employee_id = new_employee.id
                    logger.info(f"Created new employee: {employee_data.name}")
                
                # Cache employee ID for later use
                self.employee_cache[employee_data.name] = employee_id
                processed_count += 1
                
                # Process contract information if available
                if employee_data.contract_type or employee_data.contract_end_date:
                    await self._process_contract(db, employee_id, employee_data)
                
            except Exception as e:
                logger.error(f"Error processing employee {employee_data.name}: {e}")
                continue
        
        logger.info(f"Successfully processed {processed_count} employees from roster")
        return processed_count
    
    async def process_attendance_records(self, db: AsyncSession, file_path: str) -> int:
        """Process attendance records file and store in database.
        
        Args:
            db: Database session
            file_path: Path to attendance records Excel file
            
        Returns:
            Number of attendance records processed
        """
        logger.info(f"Processing attendance records from {file_path}")
        
        # Read attendance data from Excel
        attendance_data_list = self.excel_reader.read_attendance_records(file_path)
        if not attendance_data_list:
            logger.warning("No attendance data found in file")
            return 0
        
        processed_count = 0
        
        for attendance_data in attendance_data_list:
            try:
                # Get employee ID from cache or database
                employee_id = await self._get_employee_id(db, attendance_data.employee_name)
                if not employee_id:
                    logger.warning(f"Employee not found: {attendance_data.employee_name}")
                    continue
                
                # Check if attendance record already exists for this date
                existing_record = await AttendanceRecordCRUD.get_by_employee_and_date(
                    db, employee_id, attendance_data.date
                )
                
                if existing_record:
                    # Update existing record
                    await self._update_attendance_record(db, existing_record, attendance_data)
                    logger.info(f"Updated attendance record for {attendance_data.employee_name} on {attendance_data.date}")
                else:
                    # Create new record
                    attendance_dict = attendance_data.to_dict()
                    attendance_dict["employee_id"] = employee_id
                    await AttendanceRecordCRUD.create(db, attendance_dict)
                    logger.info(f"Created attendance record for {attendance_data.employee_name} on {attendance_data.date}")
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing attendance record for {attendance_data.employee_name}: {e}")
                continue
        
        logger.info(f"Successfully processed {processed_count} attendance records")
        return processed_count
    
    async def process_salary_records(self, db: AsyncSession, file_path: str) -> int:
        """Process salary records file and store in database.
        
        Args:
            db: Database session
            file_path: Path to salary records Excel file
            
        Returns:
            Number of salary records processed
        """
        logger.info(f"Processing salary records from {file_path}")
        
        # Read salary data from Excel
        salary_data_list = self.excel_reader.read_salary_records(file_path)
        if not salary_data_list:
            logger.warning("No salary data found in file")
            return 0
        
        processed_count = 0
        
        for salary_data in salary_data_list:
            try:
                # Get employee ID from cache or database
                employee_id = await self._get_employee_id(db, salary_data.employee_name)
                if not employee_id:
                    logger.warning(f"Employee not found: {salary_data.employee_name}")
                    continue
                
                # Check if salary record already exists for this month
                existing_record = await SalaryRecordCRUD.get_by_employee_and_month(
                    db, employee_id, salary_data.month
                )
                
                if existing_record:
                    # Update existing record
                    await self._update_salary_record(db, existing_record, salary_data)
                    logger.info(f"Updated salary record for {salary_data.employee_name} in {salary_data.month}")
                else:
                    # Create new record
                    salary_dict = salary_data.to_dict()
                    salary_dict["employee_id"] = employee_id
                    await SalaryRecordCRUD.create(db, salary_dict)
                    logger.info(f"Created salary record for {salary_data.employee_name} in {salary_data.month}")
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing salary record for {salary_data.employee_name}: {e}")
                continue
        
        logger.info(f"Successfully processed {processed_count} salary records")
        return processed_count
    
    async def process_conversation_records(self, db: AsyncSession, conversation_data_list: List[Dict[str, Any]]) -> int:
        """Process conversation records and store in database.
        
        Args:
            db: Database session
            conversation_data_list: List of conversation record data
            
        Returns:
            Number of conversation records processed
        """
        logger.info(f"Processing {len(conversation_data_list)} conversation records")
        
        processed_count = 0
        
        for conversation_data in conversation_data_list:
            try:
                # Get employee ID from cache or database
                employee_name = conversation_data.get("employee_name")
                if not employee_name:
                    logger.warning("Conversation record missing employee name")
                    continue
                
                employee_id = await self._get_employee_id(db, employee_name)
                if not employee_id:
                    logger.warning(f"Employee not found: {employee_name}")
                    continue
                
                # Create conversation record
                conversation_dict = conversation_data.copy()
                conversation_dict["employee_id"] = employee_id
                await ConversationRecordCRUD.create(db, conversation_dict)
                
                processed_count += 1
                logger.info(f"Created conversation record for {employee_name}")
                
            except Exception as e:
                logger.error(f"Error processing conversation record for {employee_name}: {e}")
                continue
        
        logger.info(f"Successfully processed {processed_count} conversation records")
        return processed_count
    
    async def process_data_directory(self, db: AsyncSession, data_dir: str) -> Dict[str, int]:
        """Process all data files in a directory.
        
        Args:
            db: Database session
            data_dir: Path to data directory
            
        Returns:
            Dictionary with processing statistics
        """
        logger.info(f"Processing data directory: {data_dir}")
        
        data_path = Path(data_dir)
        if not data_path.exists():
            logger.error(f"Data directory does not exist: {data_dir}")
            return {}
        
        stats = {
            "employees_processed": 0,
            "attendance_records_processed": 0,
            "salary_records_processed": 0,
            "conversation_records_processed": 0,
            "files_processed": 0,
            "errors": 0,
        }
        
        # Process employee roster files
        roster_files = list(data_path.glob("**/*花名册*.xlsx")) + list(data_path.glob("**/*roster*.xlsx"))
        for file_path in roster_files:
            try:
                count = await self.process_employee_roster(db, str(file_path))
                stats["employees_processed"] += count
                stats["files_processed"] += 1
                logger.info(f"Processed employee roster file: {file_path}")
            except Exception as e:
                logger.error(f"Error processing employee roster file {file_path}: {e}")
                stats["errors"] += 1
        
        # Process attendance files
        attendance_files = list(data_path.glob("**/*考勤*.xlsx")) + list(data_path.glob("**/*attendance*.xlsx"))
        for file_path in attendance_files:
            try:
                count = await self.process_attendance_records(db, str(file_path))
                stats["attendance_records_processed"] += count
                stats["files_processed"] += 1
                logger.info(f"Processed attendance file: {file_path}")
            except Exception as e:
                logger.error(f"Error processing attendance file {file_path}: {e}")
                stats["errors"] += 1
        
        # Process salary files
        salary_files = list(data_path.glob("**/*薪酬*.xlsx")) + list(data_path.glob("**/*salary*.xlsx"))
        for file_path in salary_files:
            try:
                count = await self.process_salary_records(db, str(file_path))
                stats["salary_records_processed"] += count
                stats["files_processed"] += 1
                logger.info(f"Processed salary file: {file_path}")
            except Exception as e:
                logger.error(f"Error processing salary file {file_path}: {e}")
                stats["errors"] += 1
        
        # Process conversation files (text and markdown)
        conversation_files = list(data_path.glob("**/*.txt")) + list(data_path.glob("**/*.md"))
        for file_path in conversation_files:
            try:
                if file_path.suffix.lower() == '.txt':
                    conversations = self.conversation_processor.process_text_file(str(file_path))
                else:
                    conversations = self.conversation_processor.process_markdown_file(str(file_path))
                
                count = await self.process_conversation_records(db, conversations)
                stats["conversation_records_processed"] += count
                stats["files_processed"] += 1
                logger.info(f"Processed conversation file: {file_path}")
            except Exception as e:
                logger.error(f"Error processing conversation file {file_path}: {e}")
                stats["errors"] += 1
        
        logger.info(f"Data directory processing completed. Stats: {stats}")
        return stats
    
    async def _get_employee_id(self, db: AsyncSession, employee_name: str) -> Optional[int]:
        """Get employee ID from cache or database.
        
        Args:
            db: Database session
            employee_name: Employee name
            
        Returns:
            Employee ID or None if not found
        """
        # Check cache first
        if employee_name in self.employee_cache:
            return self.employee_cache[employee_name]
        
        # Query database
        employee = await EmployeeCRUD.get_by_name(db, employee_name)
        if employee:
            self.employee_cache[employee_name] = employee.id
            return employee.id
        
        return None
    
    async def _update_employee(self, db: AsyncSession, existing_employee: Employee, new_data: EmployeeData) -> None:
        """Update existing employee with new data.
        
        Args:
            db: Database session
            existing_employee: Existing employee object
            new_data: New employee data
        """
        # Update fields that are not None in new data
        if new_data.department is not None:
            existing_employee.department = new_data.department
        if new_data.position is not None:
            existing_employee.position = new_data.position
        if new_data.hire_date is not None:
            existing_employee.hire_date = new_data.hire_date
        if new_data.phone is not None:
            existing_employee.phone = new_data.phone
        if new_data.email is not None:
            existing_employee.email = new_data.email
        if new_data.performance_score is not None:
            existing_employee.performance_score = new_data.performance_score
        if new_data.contract_end_date is not None:
            existing_employee.contract_end_date = new_data.contract_end_date
        
        await db.commit()
    
    async def _process_contract(self, db: AsyncSession, employee_id: int, employee_data: EmployeeData) -> None:
        """Process contract information for employee.
        
        Args:
            db: Database session
            employee_id: Employee ID
            employee_data: Employee data with contract information
        """
        try:
            # Check if contract already exists
            existing_contracts = await ContractCRUD.get_by_employee(db, employee_id)
            
            if existing_contracts:
                # Update existing contract
                contract = existing_contracts[0]  # Assume first contract is current
                if employee_data.contract_type:
                    contract.contract_type = employee_data.contract_type
                if employee_data.contract_start_date:
                    contract.start_date = employee_data.contract_start_date
                if employee_data.contract_end_date:
                    contract.end_date = employee_data.contract_end_date
                await db.commit()
            else:
                # Create new contract
                contract_data = {
                    "employee_id": employee_id,
                    "contract_type": employee_data.contract_type,
                    "start_date": employee_data.contract_start_date,
                    "end_date": employee_data.contract_end_date,
                    "status": "active",
                }
                await ContractCRUD.create(db, contract_data)
                
        except Exception as e:
            logger.error(f"Error processing contract for employee {employee_id}: {e}")
    
    async def _update_attendance_record(self, db: AsyncSession, existing_record: AttendanceRecord, new_data: AttendanceData) -> None:
        """Update existing attendance record with new data.
        
        Args:
            db: Database session
            existing_record: Existing attendance record
            new_data: New attendance data
        """
        # Update fields that are not None in new data
        if new_data.check_in_time is not None:
            existing_record.check_in_time = new_data.check_in_time
        if new_data.check_out_time is not None:
            existing_record.check_out_time = new_data.check_out_time
        if new_data.work_hours is not None:
            existing_record.work_hours = new_data.work_hours
        if new_data.overtime_hours is not None:
            existing_record.overtime_hours = new_data.overtime_hours
        if new_data.leave_type is not None:
            existing_record.leave_type = new_data.leave_type
        if new_data.status is not None:
            existing_record.status = new_data.status
        if new_data.remarks is not None:
            existing_record.remarks = new_data.remarks
        
        await db.commit()
    
    async def _update_salary_record(self, db: AsyncSession, existing_record: SalaryRecord, new_data: SalaryData) -> None:
        """Update existing salary record with new data.
        
        Args:
            db: Database session
            existing_record: Existing salary record
            new_data: New salary data
        """
        # Update fields that are not None in new data
        if new_data.base_salary is not None:
            existing_record.base_salary = new_data.base_salary
        if new_data.bonus is not None:
            existing_record.bonus = new_data.bonus
        if new_data.overtime_pay is not None:
            existing_record.overtime_pay = new_data.overtime_pay
        if new_data.deductions is not None:
            existing_record.deductions = new_data.deductions
        if new_data.net_salary is not None:
            existing_record.net_salary = new_data.net_salary
        if new_data.social_security is not None:
            existing_record.social_security = new_data.social_security
        if new_data.housing_fund is not None:
            existing_record.housing_fund = new_data.housing_fund
        if new_data.tax is not None:
            existing_record.tax = new_data.tax
        
        await db.commit()