-- ========================================================
-- 员工专业能力表
-- 存储员工的专业能力相关信息：试用期分数、绩效、专家等级、职称、职业技能
-- ========================================================

CREATE TABLE IF NOT EXISTS ods_emp_professional_ability (
    -- 主键和员工标识
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    emp_code VARCHAR(50) NOT NULL COMMENT '员工编号',
    emp_name VARCHAR(100) NOT NULL COMMENT '员工姓名',
    
    -- 试用期信息
    probation_score DECIMAL(5,2) COMMENT '试用期分数（0-100分）',
    
    -- 历史绩效（JSON格式存储多年绩效）
    performance_history JSON COMMENT '历往绩效记录，格式：[{"year":"2023","score":85,"level":"A"},...]',
    
    -- 专家等级
    is_company_expert TINYINT(1) DEFAULT 0 COMMENT '是否为公司专家（0-否，1-是）',
    is_senior_expert TINYINT(1) DEFAULT 0 COMMENT '是否为高级专家（0-否，1-是）',
    is_chief_expert TINYINT(1) DEFAULT 0 COMMENT '是否为首席专家（0-否，1-是）',
    expert_appointment_date DATE COMMENT '专家聘任日期',
    
    -- 职称信息（JSON格式，支持多个职称）
    professional_titles JSON COMMENT '职称信息，格式：[{"title_name":"高级工程师","cert_level":"高级","company_level":"公司级"},...]',
    
    -- 职业技能信息（JSON格式，支持多个技能证书）
    professional_skills JSON COMMENT '职业技能信息，格式：[{"skill_name":"Python开发","cert_level":"高级","company_level":"部门级"},...]',
    
    -- 其他能力证明
    patents_count INT DEFAULT 0 COMMENT '专利数量',
    honors_count INT DEFAULT 0 COMMENT '荣誉奖项数量',
    
    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    -- 索引
    INDEX idx_emp_code (emp_code),
    INDEX idx_emp_name (emp_name),
    INDEX idx_expert_level (is_company_expert, is_senior_expert, is_chief_expert)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='员工专业能力表';

-- 添加表注释
ALTER TABLE ods_emp_professional_ability COMMENT = '员工专业能力表：存储试用期分数、绩效、专家等级、职称、职业技能等专业能力相关信息';
