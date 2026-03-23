-- 员工专利明细表
-- 存储员工的专利详细信息，包括专利类型

CREATE TABLE IF NOT EXISTS ods_emp_patent_detail (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    emp_code VARCHAR(50) NOT NULL COMMENT '员工编号',
    emp_name VARCHAR(100) NOT NULL COMMENT '员工姓名',
    patent_name VARCHAR(500) COMMENT '专利名称',
    patent_type VARCHAR(50) COMMENT '专利类型：发明专利、实用新型专利、外观设计专利',
    patent_no VARCHAR(100) COMMENT '专利号',
    authorize_date DATE COMMENT '授权日期',
    is_authorized TINYINT(1) DEFAULT 1 COMMENT '是否已授权（1是，0否）',
    rank_inventors INT COMMENT '发明人排名',
    source_file VARCHAR(255) COMMENT '来源文件名',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_emp_code (emp_code),
    INDEX idx_patent_type (patent_type),
    INDEX idx_emp_type (emp_code, patent_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='员工专利明细表';
