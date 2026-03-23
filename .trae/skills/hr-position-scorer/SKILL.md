---
name: "hr-position-scorer"
description: "HR岗位能力多维度评分工具。用于调用远程LLM对岗位描述进行5维度能力打分（专业能力、经验、创新能力、学习能力、工作态度）。Invoke when user needs to evaluate job positions with AI scoring or create position capability models."
---

# HR岗位能力多维度评分工具

## 功能概述

本工具用于对HR系统中的岗位进行5维度能力要求评分，通过调用远程大模型API（Qwen/Qwen3-235B-A22B-Instruct-2507）生成标准化的岗位能力模型。

## 5个评分维度

1. **专业能力（professional）**：岗位对专业技能的要求程度
2. **经验（experience）**：岗位对工作年限、履历、职称证书的要求
3. **创新能力（innovation）**：岗位对创新思维、新技术应用的要求
4. **学习能力（learning）**：岗位对持续学习、知识更新的要求（知识+潜力）
5. **工作态度（attitude）**：岗位对出勤、加班、党工团参与、团队协作的要求

## 评分原则

不同岗位对不同维度的要求应该有所差异，不要所有维度都给高分：

| 维度 | 技术岗位 | 产品岗位 | 运营/行政岗位 |
|------|----------|----------|---------------|
| 专业能力 | 90-100分 | 85-95分 | 70-85分 |
| 经验 | 高级岗位90-100分 | 中级岗位75-85分 | 初级岗位60-75分 |
| 创新能力 | 90-100分 | 85-95分 | 60-75分 |
| 学习能力 | 85-95分 | 80-90分 | 70-85分 |
| 工作态度 | 管理岗位85-95分 | 普通岗位75-85分 | 75-85分 |

## 使用方法

### 1. 配置环境变量

```bash
export REMOTE_LLM_URL="http://180.97.200.118:30071/v1/chat/completions"
export REMOTE_LLM_API_KEY="z3oK7bN9xPqW2mT8rYvL5tF1cJ4hD6gA0eS2uI3nQk"
export REMOTE_LLM_MODEL="Qwen/Qwen3-235B-A22B-Instruct-2507"
export MYSQL_HOST="121.229.172.161"
export MYSQL_PORT="3306"
export MYSQL_DATABASE="hr_employee_db"
export MYSQL_USER="hr_user"
export MYSQL_PASSWORD="hr_password"
```

### 2. 运行测试脚本

```bash
cd /Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/tests
python test_position_scoring_5d.py
```

### 3. 查看结果

测试结果将保存到MySQL数据库的 `position_capability_models_5d` 表中。

## 数据库表结构

**position_capability_models_5d** 表：
- `position_name`: 岗位名称
- `department`: 所属部门
- `job_level`: 岗位级别
- `professional_standard`: 专业能力标准分
- `experience_standard`: 经验标准分
- `innovation_standard`: 创新能力标准分
- `learning_standard`: 学习能力标准分
- `attitude_standard`: 工作态度标准分
- `description`: 岗位描述
- `responsibilities`: 岗位职责

## 安全要求

- 数据不出域：所有数据库操作在本地/内网完成
- API调用限制：仅允许调用指定的远程LLM服务
- 异常处理：包含完善的错误捕获机制

## 相关文件

- 测试脚本：`hr-bot/tests/test_position_scoring_5d.py`
- 配置文件：`hr-bot/app/config.py`
- 数据模型：`hr-bot/app/database/models.py`
