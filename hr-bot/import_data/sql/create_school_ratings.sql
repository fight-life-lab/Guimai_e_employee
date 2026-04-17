-- ========================================================
-- 表名: school_ratings
-- 描述: 学校评分配置表 - 存储学校名称、类型标签和评分配置
-- 数据库: hr_employee_db
-- 创建时间: 2026-04-09
-- ========================================================

CREATE TABLE IF NOT EXISTS school_ratings (
    -- 主键
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID，自增',
    
    -- 学校基本信息
    school_name VARCHAR(128) NOT NULL COMMENT '学校名称',
    school_type VARCHAR(32) DEFAULT NULL COMMENT '学校类型（国内-985/国内-211/国内-普通/海外-QS前50/海外-QS50-100/海外-其他）',
    
    -- 排名信息
    rank_info TEXT DEFAULT NULL COMMENT '排名信息（JSON格式，如{"qs_rank": 50, "the_rank": 100}）',
    
    -- 评分配置
    bonus_score DECIMAL(5,2) DEFAULT 0.00 COMMENT '加分分值（0-100）',
    bonus_reason TEXT DEFAULT NULL COMMENT '加分依据（如：985工程重点建设高校、QS排名前50等）',
    
    -- 备注
    remark TEXT DEFAULT NULL COMMENT '备注信息',
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    -- 索引
    INDEX idx_school_name (school_name),
    INDEX idx_school_type (school_type),
    UNIQUE KEY uk_school_name (school_name)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='学校评分配置表';

-- ========================================================
-- 表结构说明
-- ========================================================
/*
字段说明：
1. id: 主键ID，自增
2. school_name: 学校全称，唯一约束
3. school_type: 学校类型标签
   - 国内-985: 985工程重点建设高校
   - 国内-211: 211工程重点建设高校
   - 国内-普通: 国内普通本科院校
   - 海外-QS前50: QS世界大学排名前50
   - 海外-QS50-100: QS世界大学排名50-100
   - 海外-其他: 其他海外院校
4. rank_info: JSON格式存储各类排名信息
5. bonus_score: 基础学习能力评分中的加分分值
6. bonus_reason: 加分的依据说明
7. remark: 其他补充信息
8. created_at: 记录创建时间
9. updated_at: 记录最后更新时间

使用场景：
- 员工学历评估时查询学校类型和加分
- 基础学习能力评分计算
- 学校清单管理和维护
*/
