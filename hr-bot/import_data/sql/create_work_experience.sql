-- 员工工作经历表
-- 存储从PDF履历中提取的工作经历信息

CREATE TABLE IF NOT EXISTS ods_emp_work_experience (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    emp_code VARCHAR(50) NOT NULL COMMENT '员工编号',
    emp_name VARCHAR(100) NOT NULL COMMENT '员工姓名',
    start_date DATE COMMENT '开始日期',
    end_date DATE COMMENT '结束日期',
    company_name VARCHAR(200) COMMENT '工作单位',
    department VARCHAR(200) COMMENT '部门',
    position VARCHAR(100) COMMENT '职务/岗位',
    is_current TINYINT(1) DEFAULT 0 COMMENT '是否当前在职（1是，0否）',
    source_file VARCHAR(255) COMMENT '来源PDF文件名',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_emp_code (emp_code),
    INDEX idx_emp_name (emp_name),
    INDEX idx_start_date (start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='员工工作经历表';
