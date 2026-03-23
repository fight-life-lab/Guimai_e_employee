-- ========================================================
-- 表名: ods_emp_job_description
-- 描述: 员工岗位说明书表 - 存储员工详细的岗位信息
-- 数据库: hr_employee_db
-- 创建时间: 2026-03-20
-- ========================================================

CREATE TABLE IF NOT EXISTS ods_emp_job_description (
    -- 主键
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID，自增',
    
    -- 员工基本信息
    emp_id VARCHAR(64) NOT NULL COMMENT '员工ID',
    emp_name VARCHAR(128) NOT NULL COMMENT '员工姓名',
    
    -- 岗位基本信息
    position_name VARCHAR(255) COMMENT '岗位名称，如：用户接待',
    department VARCHAR(255) COMMENT '所在部门，如：销售服务中心',
    report_to VARCHAR(255) COMMENT '汇报对象，如：销售服务中心主任',
    
    -- 岗位目的
    position_purpose TEXT COMMENT '岗位目的，一、岗位目的下的段落内容',
    
    -- 岗位职责（多条，JSON格式存储）
    duties_and_responsibilities JSON COMMENT '岗位职责（多条），二、岗位职责下的列表项',
    
    -- 任职资格 - 学历
    qualifications_education JSON COMMENT '任职资格-学历，三、任职资格下的维度与明细',
    
    -- 任职资格 - 专业
    qualifications_major JSON COMMENT '任职资格-专业，三、任职资格下的维度与明细',
    
    -- 任职资格 - 工作经验
    qualifications_job_work_experience JSON COMMENT '任职资格-工作经验，三、任职资格下的维度与明细',
    
    -- 任职资格 - 专业认可/职称证书
    qualifications_required_professional_certification JSON COMMENT '任职资格-专业认可/职称证书，三、任职资格下的维度与明细',
    
    -- 任职资格 - 知识技能
    qualifications_skills JSON COMMENT '任职资格-知识技能，三、任职资格下的维度与明细',
    
    -- 任职资格 - 其他
    qualifications_others JSON COMMENT '任职资格-其他，三、任职资格下的维度与明细',
    
    -- 关键绩效指标（多条，JSON格式存储）
    kpis JSON COMMENT '关键绩效指标（多条），四、关键绩效指标下的表格内容',
    
    -- 工作条件说明
    working_hours_conditions TEXT COMMENT '工作条件说明，五、工作条件说明下的段落',
    
    -- 时间戳字段
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    -- 索引
    INDEX idx_emp_id (emp_id),
    INDEX idx_emp_name (emp_name),
    INDEX idx_position_name (position_name),
    INDEX idx_department (department),
    INDEX idx_created_at (created_at)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='员工岗位说明书表';

-- ========================================================
-- 表结构说明
-- ========================================================
/*
字段说明：
1. id: 主键，自增BIGINT
2. emp_id: 员工ID，字符串类型
3. emp_name: 员工姓名，字符串类型
4. position_name: 岗位名称，如"用户接待"
5. department: 所在部门，如"销售服务中心"
6. report_to: 汇报对象，如"销售服务中心主任"
7. position_purpose: 岗位目的，TEXT类型存储段落内容
8. duties_and_responsibilities: 岗位职责，JSON数组格式存储多条职责
9. qualifications_education: 任职资格-学历，JSON格式
10. qualifications_major: 任职资格-专业，JSON格式
11. qualifications_job_work_experience: 任职资格-工作经验，JSON格式
12. qualifications_required_professional_certification: 任职资格-专业认可/职称证书，JSON格式
13. qualifications_skills: 任职资格-知识技能，JSON格式
14. qualifications_others: 任职资格-其他，JSON格式
15. kpis: 关键绩效指标，JSON数组格式存储多条KPI
16. working_hours_conditions: 工作条件说明，TEXT类型
17. created_at: 创建时间，默认当前时间
18. updated_at: 更新时间，自动更新

JSON字段示例格式：
- duties_and_responsibilities: ["职责1", "职责2", "职责3"]
- qualifications_education: {"requirement": "本科及以上", "description": "..."}
- kpis: [{"indicator": "指标1", "weight": "30%", "target": "目标值"}, ...]
*/
