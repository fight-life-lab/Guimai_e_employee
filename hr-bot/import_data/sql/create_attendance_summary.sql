-- 考勤汇总数据表
CREATE TABLE IF NOT EXISTS ods_attendance_summary (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    attendance_month VARCHAR(20) NOT NULL COMMENT '考勤月份（格式：YYYY-MM）',
    emp_code VARCHAR(50) NOT NULL COMMENT '员工ID/编号',
    emp_name VARCHAR(100) COMMENT '员工姓名',
    department VARCHAR(255) COMMENT '部门/事业部',
    normal_attendance_days DECIMAL(5,1) DEFAULT 0 COMMENT '正常出勤天（月度汇总）',
    expected_attendance_days DECIMAL(5,1) DEFAULT 0 COMMENT '理应出勤天（月度汇总）',
    late_count INT DEFAULT 0 COMMENT '迟到次数（月度汇总）',
    early_leave_count INT DEFAULT 0 COMMENT '早退次数（月度汇总）',
    leave_count INT DEFAULT 0 COMMENT '请假次数（月度汇总）',
    outing_count INT DEFAULT 0 COMMENT '外出次数（月度汇总）',
    overtime_count INT DEFAULT 0 COMMENT '加班次数（月度汇总）',
    overtime_hours DECIMAL(5,2) DEFAULT 0 COMMENT '加班时长-小时（20:30以后）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    -- 索引
    INDEX idx_emp_code (emp_code),
    INDEX idx_attendance_month (attendance_month),
    INDEX idx_emp_month (emp_code, attendance_month),
    INDEX idx_department (department),
    
    -- 唯一约束：同一员工同一月份只有一条汇总记录
    UNIQUE KEY uk_emp_month (emp_code, attendance_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='考勤汇总数据表';
