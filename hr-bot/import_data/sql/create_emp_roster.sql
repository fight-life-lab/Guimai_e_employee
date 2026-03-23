-- ========================================================-- 表名: emp_roster-- 描述: 员工花名册表 - 存储员工基本信息-- 数据库: hr_employee_db-- 创建时间: 2026-03-22-- ========================================================

CREATE TABLE IF NOT EXISTS emp_roster (
    -- 主键
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID，自增',
    
    -- 基本信息
    emp_code VARCHAR(64) NOT NULL COMMENT '人员编码/员工编号',
    emp_name VARCHAR(128) NOT NULL COMMENT '姓名',
    
    -- 部门信息
    dept_level1 VARCHAR(255) COMMENT '一级部门',
    dept_level2 VARCHAR(255) COMMENT '二级部门',
    dept_category VARCHAR(100) COMMENT '部门类别',
    
    -- 岗位信息
    emp_type VARCHAR(100) COMMENT '员工类型',
    position_name VARCHAR(255) COMMENT '岗位',
    job_level VARCHAR(100) COMMENT '职级',
    five_sequence VARCHAR(100) COMMENT '五大序列',
    
    -- 个人信息
    gender VARCHAR(10) COMMENT '性别',
    birth_date DATE COMMENT '出生日期',
    age INT COMMENT '年龄',
    political_status VARCHAR(50) COMMENT '政治面貌',
    ethnicity VARCHAR(50) COMMENT '民族',
    
    -- 学历信息
    highest_education VARCHAR(100) COMMENT '最高学历',
    highest_degree VARCHAR(100) COMMENT '最高学位',
    highest_degree_school VARCHAR(255) COMMENT '最高学位毕业学校',
    highest_degree_school_type VARCHAR(100) COMMENT '最高学位毕业学校类别',
    highest_degree_major VARCHAR(255) COMMENT '最高学位专业',
    
    -- 全日制学历
    fulltime_degree VARCHAR(100) COMMENT '全日制最高学位(PG)',
    fulltime_school VARCHAR(255) COMMENT '全日制最高学位毕业学校',
    fulltime_school_type VARCHAR(100) COMMENT '全日制最高学位毕业学校类别',
    
    -- 工作信息
    entry_date DATE COMMENT '入职时间',
    work_start_date DATE COMMENT '参加工作时间',
    contract_type VARCHAR(100) COMMENT '合同期限类型',
    contract_end_date DATE COMMENT '合同终止日期',
    work_years DECIMAL(5,2) COMMENT '工龄',
    company_years DECIMAL(5,2) COMMENT '司龄',
    
    -- 其他信息
    labor_company VARCHAR(255) COMMENT '劳动关系公司名称',
    work_location VARCHAR(255) COMMENT '工作地',
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    -- 索引
    INDEX idx_emp_code (emp_code),
    INDEX idx_emp_name (emp_name),
    INDEX idx_dept_level1 (dept_level1),
    INDEX idx_dept_level2 (dept_level2),
    INDEX idx_position_name (position_name),
    UNIQUE KEY uk_emp_code (emp_code)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='员工花名册表';

-- ========================================================-- 表结构说明-- ========================================================
/*
字段说明：
1. emp_code: 人员编码/员工编号，唯一标识
2. emp_name: 员工姓名
3. dept_level1: 一级部门
4. dept_level2: 二级部门
5. emp_type: 员工类型（正式/外包/实习等）
6. position_name: 岗位名称
7. job_level: 职级
8. five_sequence: 五大序列
9. gender: 性别
10. birth_date: 出生日期
11. age: 年龄
12. political_status: 政治面貌
13. ethnicity: 民族
14. highest_education: 最高学历
15. highest_degree: 最高学位
16. highest_degree_school: 最高学位毕业学校
17. highest_degree_school_type: 最高学位毕业学校类别
18. highest_degree_major: 最高学位专业
19. fulltime_degree: 全日制最高学位
20. fulltime_school: 全日制最高学位毕业学校
21. fulltime_school_type: 全日制最高学位毕业学校类别
22. entry_date: 入职时间
23. work_start_date: 参加工作时间
24. contract_type: 合同期限类型
25. contract_end_date: 合同终止日期
26. work_years: 工龄
27. company_years: 司龄
28. dept_category: 部门类别
29. labor_company: 劳动关系公司名称
30. work_location: 工作地
*/
