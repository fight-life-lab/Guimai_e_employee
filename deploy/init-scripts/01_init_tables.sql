-- 初始化HR员工数据库表结构

-- 员工基本信息表
CREATE TABLE IF NOT EXISTS employees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id VARCHAR(50) NOT NULL UNIQUE COMMENT '员工工号',
    name VARCHAR(100) NOT NULL COMMENT '姓名',
    department VARCHAR(100) COMMENT '部门',
    position VARCHAR(100) COMMENT '职位',
    entry_date DATE COMMENT '入职日期',
    contract_end_date DATE COMMENT '合同到期日',
    performance_rating VARCHAR(20) COMMENT '绩效评级(A/B/C/D)',
    phone VARCHAR(20) COMMENT '联系电话',
    email VARCHAR(100) COMMENT '邮箱',
    status ENUM('active', 'inactive', 'terminated') DEFAULT 'active' COMMENT '状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_department (department),
    INDEX idx_contract_end (contract_end_date),
    INDEX idx_performance (performance_rating)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='员工基本信息表';

-- 合同信息表
CREATE TABLE IF NOT EXISTS contracts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id VARCHAR(50) NOT NULL COMMENT '员工工号',
    contract_type ENUM('fixed', 'indefinite', 'probation') COMMENT '合同类型',
    start_date DATE NOT NULL COMMENT '合同开始日期',
    end_date DATE COMMENT '合同结束日期',
    status ENUM('active', 'expired', 'terminated') DEFAULT 'active' COMMENT '合同状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE,
    INDEX idx_employee (employee_id),
    INDEX idx_end_date (end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='合同信息表';

-- 谈心谈话记录表
CREATE TABLE IF NOT EXISTS conversation_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id VARCHAR(50) NOT NULL COMMENT '员工工号',
    conversation_date DATE NOT NULL COMMENT '谈话日期',
    conversation_type ENUM('regular', 'performance', 'complaint', 'resignation') COMMENT '谈话类型',
    content TEXT COMMENT '谈话内容',
    summary TEXT COMMENT '谈话摘要',
    action_items TEXT COMMENT '后续行动',
    created_by VARCHAR(100) COMMENT '记录人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE,
    INDEX idx_employee_date (employee_id, conversation_date),
    INDEX idx_type (conversation_type),
    FULLTEXT INDEX idx_content (content, summary)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='谈心谈话记录表';

-- 预警记录表
CREATE TABLE IF NOT EXISTS alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    alert_type ENUM('contract_expiry', 'poor_performance', 'no_conversation') NOT NULL COMMENT '预警类型',
    employee_id VARCHAR(50) NOT NULL COMMENT '员工工号',
    alert_date DATE NOT NULL COMMENT '预警日期',
    description TEXT COMMENT '预警描述',
    severity ENUM('low', 'medium', 'high') DEFAULT 'medium' COMMENT '严重程度',
    status ENUM('pending', 'resolved', 'ignored') DEFAULT 'pending' COMMENT '处理状态',
    resolved_by VARCHAR(100) COMMENT '处理人',
    resolved_at TIMESTAMP NULL COMMENT '处理时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE,
    INDEX idx_type_date (alert_type, alert_date),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='预警记录表';

-- 飞书机器人配置表
CREATE TABLE IF NOT EXISTS feishu_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    webhook_url VARCHAR(500) NOT NULL COMMENT 'Webhook地址',
    secret VARCHAR(200) COMMENT '签名密钥',
    bot_name VARCHAR(100) DEFAULT 'HR助手' COMMENT '机器人名称',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='飞书机器人配置表';

-- 插入示例数据
INSERT INTO employees (employee_id, name, department, position, entry_date, contract_end_date, performance_rating, phone, email) VALUES
('E001', '张三', '技术部', '高级工程师', '2022-03-15', '2025-03-15', 'A', '13800138001', 'zhangsan@company.com'),
('E002', '李四', '技术部', '工程师', '2023-06-01', '2026-06-01', 'C', '13800138002', 'lisi@company.com'),
('E003', '王五', '人力资源部', 'HR专员', '2021-01-10', '2024-12-31', 'B', '13800138003', 'wangwu@company.com'),
('E004', '赵六', '销售部', '销售经理', '2020-08-20', '2025-02-28', 'D', '13800138004', 'zhaoliu@company.com'),
('E005', '钱七', '财务部', '会计', '2022-11-01', '2025-11-01', 'B', '13800138005', 'qianqi@company.com');

INSERT INTO contracts (employee_id, contract_type, start_date, end_date, status) VALUES
('E001', 'fixed', '2022-03-15', '2025-03-15', 'active'),
('E002', 'fixed', '2023-06-01', '2026-06-01', 'active'),
('E003', 'fixed', '2021-01-10', '2024-12-31', 'active'),
('E004', 'fixed', '2020-08-20', '2025-02-28', 'active'),
('E005', 'fixed', '2022-11-01', '2025-11-01', 'active');

INSERT INTO conversation_records (employee_id, conversation_date, conversation_type, content, summary, created_by) VALUES
('E002', '2024-01-15', 'performance', '与李四讨论近期工作表现，存在拖延情况', '工作态度需改进，设定改进目标', '王经理'),
('E004', '2024-02-20', 'regular', '定期沟通，了解工作状态', '整体良好，关注业绩压力', '刘总监');
