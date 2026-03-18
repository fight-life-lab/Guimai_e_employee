-- 根据提取的文件内容更新数据库

-- 1. 清空并重新插入工时管理条例（根据《国脉文化公司工作时间管理办法》）
DELETE FROM attendance_policies;

INSERT INTO attendance_policies 
(policy_name, condition_type, threshold_value, threshold_unit, period_days, alert_level, alert_message, description)
VALUES 
-- 标准工时管理 - 迟到/早退
('月度迟到/早退超过3次', 'late', 3, 'times', 30, 'warning', '本月迟到/早退{value}次，超过阈值{threshold}次，将给予考勤通报处理', '员工每月累计迟到/早退超过3次，将给予考勤通报处理'),
('月度迟到/早退超过5次', 'late', 5, 'times', 30, 'critical', '本月迟到/早退{value}次，严重超过阈值{threshold}次，属于严重违纪', '员工每月累计迟到/早退超过5次，属于严重违纪'),

-- 标准工时管理 - 旷工（按12个月统计）
('连续12个月旷工超过3天', 'absent', 3, 'days', 365, 'critical', '连续12个月旷工{value}天，超过阈值{threshold}天，可按严重违纪解除劳动合同', '员工连续12个月内累计旷工超过3天，可按严重违纪解除劳动合同'),
('连续12个月旷工超过3次', 'absent_count', 3, 'times', 365, 'critical', '连续12个月旷工记录{value}次，超过阈值{threshold}次，可按严重违纪解除劳动合同', '员工连续12个月内旷工记录累计达到3次以上，可按严重违纪解除劳动合同'),

-- 当月旷工（触发提醒谈话）
('当月出现旷工记录', 'absent_monthly', 1, 'days', 30, 'warning', '当月出现旷工{value}天，需进行提醒谈话并扣除相应薪资', '员工当月出现旷工记录，需进行提醒谈话并扣除相应薪资'),

-- 弹性工时管理 - 工作时长不足
('弹性工时月度平均不足8小时', 'work_hours', 8, 'hours', 30, 'warning', '本月平均工作时长{value}小时，未达到{threshold}小时标准，需计算旷工时长', '弹性工时员工平均每个有效工作日的工作时长不少于8小时'),
('弹性工时旷工时长超过2小时', 'absent_hours', 2, 'hours', 30, 'warning', '本月旷工时长{value}小时，超过{threshold}小时，计为旷工半天', '单个自然月总旷工时长超过2小时不满4小时计为旷工半天'),
('弹性工时旷工时长超过4小时', 'absent_hours_critical', 4, 'hours', 30, 'critical', '本月旷工时长{value}小时，超过{threshold}小时，计为旷工一天', '单日旷工超过4小时计为旷工一天'),

-- 非固定工时管理 - 失联/违规
('非固定工时失联半小时以上', 'unreachable', 1, 'times', 30, 'warning', '无正当理由失联半小时以上，计为违规', '无正当理由失联半小时以上不满2小时计为违规'),
('连续12个月违规2次', 'violation', 2, 'times', 365, 'warning', '连续12个月累计违规{value}次，达到{threshold}次，进行通报批评', '连续12个月内累计出现2次违规进行通报批评'),
('连续12个月违规3次及以上', 'violation_critical', 3, 'times', 365, 'critical', '连续12个月累计违规{value}次，超过{threshold}次，将加大处罚力度', '连续12个月内出现3次及以上违规，将加大处罚力度'),

-- 加班（正面激励）
('月度加班超过10天', 'overtime', 10, 'days', 30, 'info', '本月加班{value}天，工作积极性高', '加班超过10天给予表扬'),
('月度加班超过20天', 'overtime_high', 20, 'days', 30, 'warning', '本月加班{value}天，超过{threshold}天，请注意劳逸结合', '加班过多提醒注意休息');

-- 2. 更新推荐算法工程师岗位能力模型（根据JD内容提炼）
UPDATE position_capability_models 
SET 
    professional_standard = 90,      -- 专业能力：需要扎实的算法基础、机器学习经验
    adaptability_standard = 85,      -- 适应能力：需要与多团队协作
    innovation_standard = 90,        -- 创新能力：需要探索LLM等前沿技术
    learning_standard = 90,          -- 学习能力：需要跟进前沿技术
    attendance_standard = 80,        -- 工时维度：标准
    political_standard = 80,         -- 品质态度：标准
    professional_weight = 1.2,       -- 专业能力权重更高
    innovation_weight = 1.1,         -- 创新能力权重较高
    learning_weight = 1.1,           -- 学习能力权重较高
    description = '负责推荐系统的算法设计与优化，包括召回、排序及混排模型，构建用户标签体系，探索LLM等前沿技术在推荐系统中的应用',
    requirements = '1. 本科及以上学历，理工类专业（计算机、机器学习、数学、统计等）
2. 扎实的数据结构和算法基础
3. 熟悉机器学习算法（LR、GBDT、SVM等）和深度学习框架（TensorFlow、PyTorch）
4. 有推荐系统、信息检索、搜索推荐相关经验优先
5. 优秀的分析和解决问题能力
6. 良好的沟通表达和团队协作能力',
    responsibilities = '1. 设计并实现APP、权益平台等核心场景的推荐系统算法研发
2. 优化召回、排序及混排模型，提升推荐精准度
3. 构建用户标签体系，分析用户兴趣、意图
4. 建立推荐效果评估体系
5. 主导模型部署和离在线调用
6. 探索大模型（LLM）等前沿技术在推荐系统中的融合应用'
WHERE position_name = '推荐算法工程师' AND department = '权益运营事业部';

-- 3. 更新岗位说明书
UPDATE position_descriptions 
SET 
    position_summary = '负责推荐系统的算法设计与优化，提升推荐精准度和用户体验',
    responsibilities = '1. 设计并实现APP、权益平台等核心场景的推荐系统算法研发，包括优化召回、排序及混排模型
2. 构建用户标签体系，基于海量用户行为数据分析用户兴趣、意图，优化特征工程与画像系统
3. 建立推荐效果评估体系，提升推荐系统的效率和精准度
4. 基于业务逻辑，主导模型部署和离在线调用
5. 探索大模型（LLM）等前沿技术在推荐系统中的融合应用',
    requirements = '学历要求：本科及以上学历
专业要求：理工类专业，包括但不限于计算机科学与技术、机器学习、应用数学、统计学等
工作技能：
1. 具备扎实的数据结构和算法基础
2. 熟悉常用机器学习算法（LR、GBDT、SVM等）和深度学习框架（TensorFlow、PyTorch），有大规模机器学习项目经验
3. 对数据分析和算法设计有比较强烈的兴趣，具有推荐系统、信息检索、搜索推荐相关工作或项目经验者优先
4. 具备优秀的分析问题和解决问题的能力
5. 具有良好的沟通表达能力和团队协作精神',
    salary_range_min = 25000,
    salary_range_max = 30000
WHERE position_name = '推荐算法工程师' AND department = '权益运营事业部';

-- 验证更新结果
SELECT '工时管理条例' as category, COUNT(*) as count FROM attendance_policies
UNION ALL
SELECT '推荐算法工程师能力模型', 1 FROM position_capability_models WHERE position_name = '推荐算法工程师'
UNION ALL
SELECT '推荐算法工程师岗位说明', 1 FROM position_descriptions WHERE position_name = '推荐算法工程师';
