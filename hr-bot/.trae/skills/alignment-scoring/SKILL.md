---
name: "alignment-scoring"
description: "人岗适配评分计算工具，用于计算候选人和岗位的6维度匹配分数。Invoke when user needs to calculate employee-job alignment scores, generate dimension scores, or analyze person-position matching data."
---

# 人岗适配评分计算 Skill

## 概述

本 Skill 提供了人岗适配分析的核心计算逻辑，基于 **6维度模型** 对员工与岗位的匹配度进行量化评分。

## 6维度模型及权重

| 维度 | 权重 | 说明 |
|------|------|------|
| 专业能力 | 30% | 基于绩效、专家聘任、职称证书、职业技能 |
| 经验 | 10% | 基于工作年限和荣誉奖项 |
| 创新能力 | 10% | 基于面试录音和提问回答评估 |
| 学习能力 | 20% | 基于学历、持续学习、谈话录音综合评价 |
| 工作态度 | 20% | 基于考勤数据（迟到、早退、加班） |
| 价值贡献 | 10% | 基于绩效酬金偏离度 |

## 核心数据结构

### 1. 维度评分结构 (DimensionScore)

```python
{
    "name": str,              # 维度名称
    "score": float,           # 员工该维度得分 (0-100)
    "weight": float,          # 维度权重 (百分比)
    "job_requirement": float, # 岗位要求分数 (0-100)
    "description": str,       # 维度描述
    "employee_reason": str,   # 员工得分理由
    "job_reason": str         # 岗位要求理由
}
```

### 2. 分析结果结构 (AlignmentResult)

```python
{
    "success": bool,
    "employee_name": str,
    "employee_code": str,
    "department": str,
    "position": str,
    "overall_score": float,           # 员工综合得分
    "job_requirement_score": float,   # 岗位综合要求分
    "dimensions": List[DimensionScore],
    "conclusion": str,                # 分析结论
    "evaluation": str,                # 评价等级
    "recommendations": List[str],     # 发展建议
    "quadrant": Dict,                 # 四象限图数据
    "radar_data": Dict,               # 雷达图数据
    "gap_analysis": List[Dict]        # 差距分析
}
```

## 核心计算公式

### 1. 综合得分计算

```python
# 员工综合得分 = Σ(各维度得分 × 维度权重) / 100
overall_score = sum(d.score * d.weight / 100 for d in dimensions)

# 岗位综合要求分 = Σ(各维度要求 × 维度权重) / 100
job_requirement_score = sum(d.job_requirement * d.weight / 100 for d in dimensions)

# 人岗适配率 = (员工综合得分 / 岗位综合要求分) × 100%
match_rate = (overall_score / job_requirement_score) * 100
```

### 2. 各维度计算逻辑

#### 2.1 专业能力 (30%)

**员工得分计算：**
- 基础分：70分
- 绩效加分：
  - 试用期考核≥90分：+15分
  - 试用期考核≥80分：+10分
  - 年度绩效优秀：+15分/次
  - 年度绩效基本称职：-15分/次
  - 连续3年称职：-5分
- 专家聘任：
  - 首席专家：+20分
  - 高级专家：+15分
  - 公司专家：+10分
- 职称证书（取最高）：
  - A级：+10分
  - B级：+7分
  - C级：+5分
- 职业技能（累计不超过14分）：
  - A级：+7分/项
  - B级：+5分/项
  - C级：+3分/项

**岗位要求计算：**
```python
# 根据岗位说明书技能要求
if "精通" or "高级" or "资深" in skills:
    job_requirement = 85 / 0.9
elif "熟练" or "掌握" in skills:
    job_requirement = 75 / 0.9
else:
    job_requirement = 70 / 0.9
```

#### 2.2 经验 (10%)

**员工得分计算：**
```python
# 工作履历得分（占比80%）
if relevant_years >= required_years:
    work_experience_score = 100.0
else:
    work_experience_score = (relevant_years / required_years) * 100.0

work_score = work_experience_score * 0.8

# 荣誉奖项得分（占比20%，取最高）
if "国家级" in honors:
    honor_raw_score = 100
elif "省部级" in honors:
    honor_raw_score = 75
elif "集团级" in honors:
    honor_raw_score = 50
elif "公司级" in honors:
    honor_raw_score = 25

honor_score = honor_raw_score * 0.2

# 总分
total_score = work_score + honor_score
```

**岗位要求：**
```python
# 从岗位说明书提取要求年限
job_requirement = 80.0
job_reason = f"要求{required_years}年{experience_type}工作经验"
```

#### 2.3 创新能力 (10%)

**员工得分：**
- 基于面试录音转文字 + 提问回答
- 通过大模型评估（温度系数0.3）
- 满分100分

**岗位要求：**
- 通过大模型分析岗位说明书生成
- 一般岗位：60-75分
- 需较强创新岗位：75-90分

#### 2.4 学习能力 (20%)

**员工得分计算：**
```python
# 基础学习能力（占比80%）
# 根据学历和学校类型
if bachelor:
    if 985/QS前50: base_score = 80
    elif 211/QS50-100: base_score = 70
    else: base_score = 60
elif master:
    if 985/QS前50: base_score = 90
    elif 211/QS50-100: base_score = 80
    else: base_score = 70
elif phd:
    if 985/QS前50: base_score = 100
    elif 211/QS50-100: base_score = 90
    else: base_score = 80

# 专业对口加分
if major_matches: base_score += 5

# 综合评价（占比20%）
# 基于谈话录音，大模型评估
comprehensive_score = 70  # 默认

# 最终得分
final_score = (base_score * 0.8) + (comprehensive_score * 0.2)
```

**岗位要求：**
```python
if "博士" in requirements:
    job_requirement = 80 / 0.9
elif "研究生" in requirements:
    job_requirement = 70 / 0.9
elif "本科" in requirements:
    job_requirement = 60 / 0.9
else:
    job_requirement = 55 / 0.9
```

#### 2.5 工作态度 (20%)

**非试用期员工：**
```python
score = 70  # 基础分

# 扣分项
if late_count > 3:
    score -= min(late_count - 3, 10)
if early_leave_count > 0:
    score -= min(early_leave_count, 10)

# 加分项
if overtime_hours >= 36:
    score += 20
elif overtime_count > 0:
    score += min(overtime_count, 20)

score = max(0, min(score, 100))
```

**试用期员工（入职≤6个月）：**
```python
score = 70  # 基础分

# 扣分项（豁免3次/月）
if late_count > 3:
    score -= min(late_count - 3, 10)
if absenteeism_count > 0:
    if absenteeism_count > 3:
        score = 0  # 直接0分
    else:
        score -= absenteeism_count * 10

# 加分项（二选一）
if overtime_hours >= 36:
    score += 30
elif very_late_checkout_count > 0:  # 20:30后
    score += min(very_late_checkout_count * 6, 30)
elif overtime_count > 0:  # 18:30后
    score += min(overtime_count * 3, 30)

# 政治面貌
if "党员" in political_status:
    score += 5

# 党工团兼职
if "党" in party_union_role: score += 10
elif "团" in party_union_role: score += 7
elif "工" in party_union_role: score += 4

score = max(0, min(score, 100))
```

**岗位要求：**
```python
job_requirement = 70 / 0.9
job_reason = "要求：遵守考勤纪律，积极主动"
```

#### 2.6 价值贡献 (10%)

**非试用期员工：**
```python
base_score = 70.0
diff = deviation_rate - 100.0  # 偏离度与100%的差
score_change = (diff / 1.0) * 3  # 每1个百分点变化3分
score = base_score + score_change
score = max(0.0, min(100.0, score))
```

**试用期员工：**
```python
base_score = 100.0
if deviation_rate >= 100%:
    score = base_score  # 不加分不扣分
else:
    diff = 100.0 - deviation_rate
    score_change = diff * 5  # 每低1个百分点扣5分
    score = base_score - score_change
score = max(0.0, min(100.0, score))
```

**岗位要求：**
```python
if is_probation:
    job_requirement = 100.0 / 0.9
else:
    job_requirement = 70.0 / 0.9
```

## 辅助计算函数

### 1. 四象限图数据生成

```python
def generate_quadrant_data(dimensions, overall_score, job_requirement_score):
    ability_index = overall_score / 100  # 能力指数 0-1
    match_index = overall_score / job_requirement_score if job_requirement_score > 0 else 1.0
    
    # 象限判定
    if ability_index >= 0.75 and match_index >= 0.9:
        quadrant = "第一象限"
        quadrant_name = "核心人才区"
        color = "#52c41a"  # 绿色
    elif ability_index >= 0.75 and match_index < 0.9:
        quadrant = "第二象限"
        quadrant_name = "潜力人才区"
        color = "#1890ff"  # 蓝色
    elif ability_index < 0.75 and match_index < 0.9:
        quadrant = "第三象限"
        quadrant_name = "待发展区"
        color = "#faad14"  # 橙色
    else:
        quadrant = "第四象限"
        quadrant_name = "稳定贡献区"
        color = "#722ed1"  # 紫色
    
    return {
        "quadrant": quadrant,
        "quadrant_name": quadrant_name,
        "ability_index": round(ability_index * 100, 1),
        "match_index": round(match_index * 100, 1),
        "x": round(match_index * 100, 1),
        "y": round(ability_index * 100, 1),
        "center_x": 90,
        "center_y": 75
    }
```

### 2. 雷达图数据生成

```python
def generate_radar_data(dimensions):
    return {
        "categories": [d.name for d in dimensions],
        "employee_scores": [round(d.score, 1) for d in dimensions],
        "job_requirements": [round(d.job_requirement, 1) for d in dimensions],
        "gaps": [round(d.job_requirement - d.score, 1) for d in dimensions],
        "max_scale": 100
    }
```

### 3. 差距分析生成

```python
def generate_gap_analysis(dimensions):
    analysis = []
    for dim in dimensions:
        gap = dim.score - dim.job_requirement
        if gap < -15:
            level = "严重不足"
            color = "#ff4d4f"
        elif gap < -5:
            level = "有待提升"
            color = "#faad14"
        elif gap < 5:
            level = "基本匹配"
            color = "#52c41a"
        else:
            level = "超出要求"
            color = "#1890ff"
        
        analysis.append({
            "dimension": dim.name,
            "employee_score": round(dim.score, 1),
            "job_requirement": round(dim.job_requirement, 1),
            "gap": round(gap, 1),
            "weight": dim.weight,
            "level": level,
            "color": color
        })
    
    # 按差距从大到小排序
    analysis.sort(key=lambda x: x["gap"], reverse=True)
    return analysis
```

### 4. 评价等级判定

```python
def determine_evaluation_level(match_rate):
    if match_rate >= 90:
        return "优秀", "该员工与岗位高度匹配，建议重点培养"
    elif match_rate >= 60:
        return "合格", "该员工与岗位要求存在一定差距，建议员工不续签"
    else:
        return "待提升", "该员工与岗位匹配度较低，建议调整岗位或加强培训"
```

## 使用示例

### 示例1：计算完整人岗适配分析

```python
# 准备6维度数据
dimensions = [
    DimensionScore(name="专业能力", score=85, weight=30, job_requirement=80),
    DimensionScore(name="经验", score=75, weight=10, job_requirement=80),
    DimensionScore(name="创新能力", score=70, weight=10, job_requirement=75),
    DimensionScore(name="学习能力", score=80, weight=20, job_requirement=75),
    DimensionScore(name="工作态度", score=90, weight=20, job_requirement=78),
    DimensionScore(name="价值贡献", score=75, weight=10, job_requirement=78),
]

# 计算综合得分
overall_score = sum(d.score * d.weight / 100 for d in dimensions)  # 82.0
job_requirement_score = sum(d.job_requirement * d.weight / 100 for d in dimensions)  # 77.9

# 计算适配率
match_rate = (overall_score / job_requirement_score) * 100  # 105.3%

# 生成四象限数据
quadrant = generate_quadrant_data(dimensions, overall_score, job_requirement_score)

# 生成雷达图数据
radar_data = generate_radar_data(dimensions)

# 生成差距分析
gap_analysis = generate_gap_analysis(dimensions)
```

### 示例2：前端展示数据结构

```javascript
// 双雷达图数据
const radarData = {
    categories: ["专业能力", "经验", "创新能力", "学习能力", "工作态度", "价值贡献"],
    employee_scores: [85, 75, 70, 80, 90, 75],  // 员工实际得分
    job_requirements: [80, 80, 75, 75, 78, 78],  // 岗位要求
    gaps: [-5, 5, 5, -5, -12, 3]  // 差距（正数表示超出，负数表示不足）
};

// 四象限图数据
const quadrantData = {
    x: 105.3,  // 匹配度
    y: 82.0,   // 能力指数
    quadrant_name: "核心人才区",
    color: "#52c41a"
};

// 差距分析表格数据
const gapAnalysis = [
    {dimension: "工作态度", employee_score: 90, job_requirement: 78, gap: 12, level: "超出要求"},
    {dimension: "学习能力", employee_score: 80, job_requirement: 75, gap: 5, level: "超出要求"},
    {dimension: "经验", employee_score: 75, job_requirement: 80, gap: -5, level: "有待提升"},
    // ...
];
```

## 注意事项

1. **权重调整**：6维度权重总和必须为100%
2. **分数范围**：所有维度得分范围均为0-100分
3. **岗位调整系数**：岗位需求分通常需要除以0.9进行调整，最高不超过100分
4. **员工类型区分**：试用期员工和非试用期员工的计算逻辑不同
5. **大模型调用**：创新能力和学习能力的综合评价需要调用大模型（温度系数0.3）
