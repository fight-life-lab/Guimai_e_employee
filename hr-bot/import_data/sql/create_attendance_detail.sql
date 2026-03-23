-- 考勤明细数据表
CREATE TABLE IF NOT EXISTS ods_attendance_detail (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    attendance_date DATE NOT NULL COMMENT '考勤日期',
    emp_code VARCHAR(50) NOT NULL COMMENT '员工ID/编号',
    emp_name VARCHAR(100) COMMENT '员工姓名',
    department VARCHAR(255) COMMENT '部门/事业部',
    normal_attendance_days DECIMAL(3,1) DEFAULT 0 COMMENT '正常出勤天',
    expected_attendance_days DECIMAL(3,1) DEFAULT 0 COMMENT '理应出勤天',
    late_count INT DEFAULT 0 COMMENT '迟到次数',
    early_leave_count INT DEFAULT 0 COMMENT '早退次数',
    leave_count INT DEFAULT 0 COMMENT '请假次数',
    outing_count INT DEFAULT 0 COMMENT '外出次数',
    overtime_info VARCHAR(255) COMMENT '加班次数及20:30以后',
    original_checkin_time VARCHAR(50) COMMENT '原始签到时间',
    original_checkout_time VARCHAR(50) COMMENT '原始签退时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    -- 索引
    INDEX idx_emp_code (emp_code),
    INDEX idx_attendance_date (attendance_date),
    INDEX idx_emp_date (emp_code, attendance_date),
    INDEX idx_department (department),
    
    -- 唯一约束：同一员工同一天只有一条记录
    UNIQUE KEY uk_emp_date (emp_code, attendance_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='考勤明细数据表';
