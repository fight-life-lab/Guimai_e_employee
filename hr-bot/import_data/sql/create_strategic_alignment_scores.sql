-- 员工战略匹配分数表
CREATE TABLE IF NOT EXISTS strategic_alignment_scores (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    emp_code VARCHAR(50) NOT NULL COMMENT '员工工号',
    emp_name VARCHAR(100) NOT NULL COMMENT '员工姓名',
    score DECIMAL(5,2) NOT NULL COMMENT '战略匹配分数(0-100)',
    evaluation_year INT COMMENT '考核年度',
    evaluator VARCHAR(100) COMMENT '评定人',
    evaluation_basis TEXT COMMENT '评定依据',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX idx_emp_code (emp_code),
    INDEX idx_evaluation_year (evaluation_year),
    INDEX idx_emp_year (emp_code, evaluation_year),
    UNIQUE KEY uk_emp_year (emp_code, evaluation_year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='员工战略匹配分数表';
