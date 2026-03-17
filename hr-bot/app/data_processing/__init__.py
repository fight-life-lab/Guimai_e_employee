"""Data processing module for HR data ingestion."""

from .excel_reader import ExcelReader
from .data_models import EmployeeData, AttendanceData, SalaryData
from .data_ingestion import DataIngestionPipeline

__all__ = ["ExcelReader", "EmployeeData", "AttendanceData", "SalaryData", "DataIngestionPipeline"]