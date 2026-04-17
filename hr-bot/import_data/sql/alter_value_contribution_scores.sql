-- 修改value_contribution_scores表，将score字段改为可为空
ALTER TABLE value_contribution_scores MODIFY COLUMN score DECIMAL(5,2) COMMENT '价值贡献分数(0-100)';
