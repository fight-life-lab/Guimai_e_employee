import pandas as pd
import pymysql
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 读取Excel
df = pd.read_excel('hr-bot/data/全汇总.xlsx')
logger.info(f"Excel total rows: {len(df)}")
logger.info(f"Columns: {list(df.columns)}")

# 连接MySQL
conn = pymysql.connect(
    host='121.229.172.161',
    port=3306,
    user='hr_user',
    password='hr_password',
    database='hr_employee_db',
    autocommit=False
)

try:
    with conn.cursor() as cursor:
        # 先清空旧数据
        cursor.execute("DELETE FROM ods_attendance_summary")
        logger.info("Old data cleared")
        
        # 列名映射 - 避免重复列名
        column_mapping = {
            '考勤月份': 'attendance_month',
            '员工ID': 'emp_code',
            '员工姓名': 'emp_name',
            '部门/事业部': 'department',
            '正常出勤天数': 'normal_attendance_days',
            '理应出勤天数': 'expected_attendance_days',
            '迟到次数': 'late_count',
            '早退次数': 'early_leave_count',
            '缺勤次数': 'absent_count',
            '请假次数': 'leave_count',
            '外出次数': 'outing_count',
            '出差次数': 'business_trip_count',
            '加班次数': 'overtime_count',
            '加班时长（小时）': 'overtime_hours',
            '加班时长（20:30以后加班时长-小时）': 'overtime_hours_backup',
            '加班时长': 'overtime_hours_backup2',
            '20:30以后加班次数': 'overtime_2030_count',
            '20:30以后加班时长（小时）': 'overtime_2030_hours',
        }
        
        df.rename(columns=column_mapping, inplace=True)
        
        # 检查非零数据
        if 'overtime_2030_count' in df.columns:
            non_zero = (df['overtime_2030_count'] > 0).sum()
            total_sum = df['overtime_2030_count'].sum()
            logger.info(f"overtime_2030_count: non_zero={non_zero}, sum={total_sum}")
        
        sql = """
            INSERT INTO ods_attendance_summary (
                attendance_month, emp_code, emp_name, department,
                normal_attendance_days, expected_attendance_days,
                late_count, early_leave_count, leave_count, outing_count,
                overtime_count, overtime_hours, overtime_2030_count
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                emp_name = VALUES(emp_name),
                department = VALUES(department),
                normal_attendance_days = VALUES(normal_attendance_days),
                expected_attendance_days = VALUES(expected_attendance_days),
                late_count = VALUES(late_count),
                early_leave_count = VALUES(early_leave_count),
                leave_count = VALUES(leave_count),
                outing_count = VALUES(outing_count),
                overtime_count = VALUES(overtime_count),
                overtime_hours = VALUES(overtime_hours),
                overtime_2030_count = VALUES(overtime_2030_count),
                updated_at = CURRENT_TIMESTAMP
        """
        
        batch_params = []
        success_count = 0
        fail_count = 0
        
        for idx, row in df.iterrows():
            try:
                emp_code = str(row.get('emp_code', '')).strip()
                attendance_month = row.get('attendance_month')
                
                if pd.isna(emp_code) or pd.isna(attendance_month) or not emp_code:
                    continue
                
                if isinstance(attendance_month, pd.Timestamp):
                    attendance_month = attendance_month.strftime('%Y-%m')
                
                params = (
                    attendance_month,
                    emp_code,
                    str(row.get('emp_name', '')).strip() if pd.notna(row.get('emp_name')) else None,
                    str(row.get('department', '')).strip() if pd.notna(row.get('department')) else None,
                    float(row.get('normal_attendance_days', 0)) if pd.notna(row.get('normal_attendance_days')) else 0,
                    float(row.get('expected_attendance_days', 0)) if pd.notna(row.get('expected_attendance_days')) else 0,
                    int(row.get('late_count', 0)) if pd.notna(row.get('late_count')) else 0,
                    int(row.get('early_leave_count', 0)) if pd.notna(row.get('early_leave_count')) else 0,
                    int(row.get('leave_count', 0)) if pd.notna(row.get('leave_count')) else 0,
                    int(row.get('outing_count', 0)) if pd.notna(row.get('outing_count')) else 0,
                    int(row.get('overtime_count', 0)) if pd.notna(row.get('overtime_count')) else 0,
                    float(row.get('overtime_hours', 0)) if pd.notna(row.get('overtime_hours')) else 0,
                    int(row.get('overtime_2030_count', 0)) if pd.notna(row.get('overtime_2030_count')) else 0,
                )
                
                batch_params.append(params)
                
                # 每100条提交一次
                if len(batch_params) >= 100:
                    cursor.executemany(sql, batch_params)
                    conn.commit()
                    success_count += len(batch_params)
                    batch_params = []
                    if success_count % 1000 == 0:
                        logger.info(f"Imported {success_count} rows...")
            except Exception as e:
                fail_count += 1
                if fail_count <= 3:
                    logger.error(f"Row {idx}: {e}")
        
        # 提交剩余的
        if batch_params:
            cursor.executemany(sql, batch_params)
            conn.commit()
            success_count += len(batch_params)
        
        logger.info(f"Import done: success={success_count}, fail={fail_count}")
        
        # 验证
        cursor.execute("SELECT COUNT(*) as total, SUM(overtime_2030_count) as sum_ot, COUNT(CASE WHEN overtime_2030_count > 0 THEN 1 END) as non_zero FROM ods_attendance_summary")
        result = cursor.fetchone()
        logger.info(f"DB verification: total={result[0]}, sum_ot2030={result[1]}, non_zero={result[2]}")
        
        if result[2] and result[2] > 0:
            cursor.execute("SELECT emp_code, emp_name, attendance_month, overtime_count, overtime_hours, overtime_2030_count FROM ods_attendance_summary WHERE overtime_2030_count > 0 ORDER BY overtime_2030_count DESC LIMIT 5")
            for r in cursor.fetchall():
                logger.info(f"  Sample: emp={r[0]}, name={r[1]}, month={r[2]}, ot_count={r[3]}, ot_hours={r[4]}, ot2030={r[5]}")
        
finally:
    conn.close()
