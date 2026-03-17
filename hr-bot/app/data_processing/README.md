# HR Data Processing System

This module provides comprehensive data processing capabilities for HR data, including Excel file reading, conversation record processing, and database ingestion.

## Features

### 1. Excel Data Reader (`excel_reader.py`)
- **Employee Roster Processing**: Reads employee information from Excel files
- **Attendance Records**: Processes attendance data with check-in/out times
- **Salary Records**: Handles salary information including bonuses, deductions, and social benefits
- **Flexible Column Mapping**: Automatically detects common Chinese and English column names
- **Date/Time Parsing**: Supports multiple date formats and Excel date serial numbers

### 2. Conversation Processor (`conversation_processor.py`)
- **Text File Processing**: Extracts conversation records from text files
- **Markdown Support**: Handles markdown-formatted conversation records
- **Intelligent Parsing**: Automatically extracts:
  - Employee names
  - Conversation dates
  - Conversation types (谈心谈话, 绩效面谈, 离职面谈, etc.)
  - Participants
  - Follow-up actions
  - Next meeting dates

### 3. Data Ingestion Pipeline (`data_ingestion.py`)
- **Complete Data Pipeline**: Orchestrates the entire data processing workflow
- **Database Integration**: Seamlessly stores processed data in the database
- **Duplicate Detection**: Prevents duplicate entries
- **Error Handling**: Robust error handling and logging
- **Batch Processing**: Efficiently processes large datasets

### 4. Data Models (`data_models.py`)
- **EmployeeData**: Structured employee information
- **AttendanceData**: Attendance record data
- **SalaryData**: Salary and compensation information
- **ConversationRecord**: Conversation and meeting records

## Usage

### Basic Usage

```python
from app.data_processing import DataIngestionPipeline

# Initialize the pipeline
pipeline = DataIngestionPipeline()

# Process data directory
stats = await pipeline.process_data_directory(db_session, "./hr-bot/data")
print(f"Processed {stats['employees_processed']} employees")
```

### Processing Specific Files

```python
# Process employee roster
employee_count = await pipeline.process_employee_roster(db_session, "path/to/roster.xlsx")

# Process attendance records
attendance_count = await pipeline.process_attendance_records(db_session, "path/to/attendance.xlsx")

# Process salary records
salary_count = await pipeline.process_salary_records(db_session, "path/to/salary.xlsx")
```

### Processing Conversation Files

```python
from app.data_processing.conversation_processor import ConversationProcessor

processor = ConversationProcessor()

# Process text file
conversations = processor.process_text_file("path/to/conversations.txt")

# Process markdown file
conversations = processor.process_markdown_file("path/to/conversations.md")

# Store in database
count = await pipeline.process_conversation_records(db_session, conversations)
```

## Command Line Usage

### Process Entire Data Directory

```bash
cd hr-bot
python scripts/ingest_data.py --data-dir ./data
```

### Process Specific File

```bash
# Process employee roster
python scripts/ingest_data.py --file ./data/roster.xlsx --file-type employee_roster

# Process attendance records
python scripts/ingest_data.py --file ./data/attendance.xlsx --file-type attendance

# Process salary records
python scripts/ingest_data.py --file ./data/salary.xlsx --file-type salary
```

### Run Tests

```bash
python scripts/test_data_processing.py
```

## Supported File Types

### Excel Files (.xlsx)
- Employee rosters (花名册)
- Attendance records (考勤)
- Salary records (薪酬)

### Text Files (.txt, .md)
- Conversation records
- Meeting minutes
- Interview notes

## Database Schema

The system extends the existing database schema with new tables:

### AttendanceRecord
- Employee attendance tracking
- Check-in/out times
- Work hours and overtime
- Leave types and status

### SalaryRecord
- Monthly salary information
- Base salary, bonuses, deductions
- Social security and housing fund
- Tax information

### ConversationRecord
- Employee conversation history
- Meeting types and participants
- Content summaries and follow-up actions

## Configuration

The system uses the existing configuration from `app.config`:

- **Database URL**: SQLite database path
- **Data Directory**: Location of HR data files
- **Logging**: Configurable log levels and output

## Error Handling

The system includes comprehensive error handling:

- **File Format Validation**: Checks for valid Excel and text formats
- **Data Validation**: Validates dates, numbers, and required fields
- **Database Constraints**: Handles unique constraints and foreign key relationships
- **Logging**: Detailed error logging for troubleshooting

## Performance Considerations

- **Batch Processing**: Processes large datasets efficiently
- **Caching**: Employee ID caching to reduce database queries
- **Memory Management**: Streams large Excel files to prevent memory issues
- **Async Operations**: Uses async database operations for better performance

## Testing

Run the comprehensive test suite:

```bash
python scripts/test_data_processing.py
```

Tests include:
- Excel file parsing
- Conversation text processing
- Database operations
- End-to-end data ingestion

## Integration with LLM

Once data is processed and stored in the database, it can be easily accessed by the LLM for analysis:

```python
# Query employee data
employee = await EmployeeCRUD.get_by_name(db_session, "张三")
attendance_records = await AttendanceRecordCRUD.get_by_employee(db_session, employee.id)

# Analyze with LLM
analysis = await hr_agent.analyze_employee_performance(employee, attendance_records)
```

## Troubleshooting

### Common Issues

1. **Excel File Reading Errors**
   - Ensure files are in .xlsx format
   - Check for proper column headers
   - Verify date formats are consistent

2. **Database Connection Issues**
   - Check database URL configuration
   - Ensure database tables are created
   - Verify database permissions

3. **Conversation Parsing Issues**
   - Check text file encoding (UTF-8 recommended)
   - Ensure consistent date formats
   - Verify employee names match database records

### Debug Mode

Enable debug logging:

```bash
python scripts/ingest_data.py --data-dir ./data --verbose
```

## Future Enhancements

- **PDF Processing**: Add support for PDF documents
- **Image Processing**: Extract text from scanned documents
- **Advanced NLP**: Use LLM for better conversation understanding
- **Real-time Processing**: Implement real-time data ingestion
- **Data Validation**: Add more sophisticated data validation rules