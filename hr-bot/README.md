# 人力数字员工 - 人岗适配智能评估系统

## 项目概述

**人力数字员工**是基于国央企员工人岗适配管理体系的智能评估系统，采用私有化部署的Qwen大模型，确保数据不出域。系统支持对话式查询员工信息、人岗适配分析等功能。

## 核心特性

### 1. 数据安全（数据不出域）
- **大模型**: 本地vLLM部署的Qwen-14B模型，不调用外部API
- **数据库**: SQLite本地文件存储
- **所有数据**: 仅在本地服务器处理，不传输到外部

### 2. 评估维度（基于国央企管理体系）

#### 能力画像 (权重40%)
- 专业能力 (40%): 技术技能、业务精通度
- 管理能力 (25%): 团队领导、协调沟通
- 创新能力 (15%): 问题解决、改进创新
- 学习能力 (10%): 知识更新、技能提升
- 适应能力 (10%): 环境适应、压力应对

#### 政治画像 (权重25%)
- 政治立场: 对党的路线方针政策的认同度和执行力
- 廉洁自律: 遵守党纪国法和廉洁从业规定
- 组织观念: 服从组织安排、维护组织权威
- 群众基础: 在员工群众中的认可度和影响力

#### 时间维度 (权重15%)
- 稳定性指标: 连续6-12个月的考勤数据分析
- 响应能力: 紧急任务响应速度和加班完成质量
- 持续性表现: 长时间段内工作表现的一致性

#### 绩效表现 (权重20%)
- 绩效分数: 近期绩效考核得分
- 绩效趋势: 绩效变化趋势
- 目标达成: 工作目标完成情况

## 技术架构

### 部署环境
- **服务器**: 121.229.172.161
- **端口**: 3111 (Web服务)
- **Python环境**: Conda media_env
- **GPU**: NVIDIA A100 40GB

### 依赖服务（Docker部署）
| 服务 | 端口 | 状态 |
|------|------|------|
| vLLM + Qwen-14B | 8002 | 本地Docker |

### 技术栈
- **后端**: FastAPI + Python 3.10
- **数据库**: SQLite (本地文件)
- **大模型**: Qwen-14B-Chat (vLLM部署)
- **前端**: HTML5 + CSS3 + JavaScript
- **AI框架**: LangChain + LangGraph

## 访问地址

- **主页面**: http://121.229.172.161:3111/
- **智能对话**: http://121.229.172.161:3111/static/chat.html
- **API文档**: http://121.229.172.161:3111/docs

## API接口

### 1. 分析单个员工
```bash
POST http://121.229.172.161:3111/api/v1/alignment/analyze
Content-Type: application/json

{
    "employee_name": "石京京",
    "include_details": true
}
```

### 2. 流式分析（实时返回）
```bash
POST http://121.229.172.161:3111/api/v1/alignment/analyze/stream
Content-Type: application/json

{
    "employee_name": "石京京"
}
```

### 3. 对比多个员工
```bash
POST http://121.229.172.161:3111/api/v1/alignment/compare
Content-Type: application/json

{
    "employee_names": ["石京京", "余祯", "周灏"]
}
```

### 4. 获取评估维度
```bash
GET http://121.229.172.161:3111/api/v1/alignment/dimensions
```

### 5. 对话式查询
```bash
POST http://121.229.172.161:3111/api/v1/alignment/chat
Content-Type: application/json

{
    "message": "石京京是哪个学校的"
}
```

### 6. 流式对话
```bash
POST http://121.229.172.161:3111/api/v1/alignment/chat/stream
Content-Type: application/json

{
    "message": "石京京是哪个学校的"
}
```

## 前端功能

### 智能对话界面
- **历史记录保存**: 使用localStorage保存聊天记录，刷新不丢失
- **清除历史**: 点击"🗑️ 清除历史"按钮可清除所有记录
- **自动识别**: 自动识别员工姓名和查询意图
- **流式响应**: 实时显示AI回复

### 支持的查询类型
- 员工基本信息查询（学校、岗位、部门等）
- 绩效信息查询
- 人岗适配分析（包含"分析"、"适配"、"评估"关键词）

### 示例问题
- "石京京是哪个学校的？"
- "余祯的绩效怎么样？"
- "周灏是什么岗位？"
- "分析一下石京京的人岗适配情况"

## 文件结构

```
hr-bot/
├── app/
│   ├── agent/
│   │   ├── alignment_agent.py    # 人岗适配评估Agent
│   │   ├── hr_agent.py           # HR Agent
│   │   ├── prompts.py            # 提示词模板
│   │   └── state.py              # Agent状态定义
│   ├── api/
│   │   ├── alignment_routes.py   # 人岗适配API路由
│   │   └── feishu_webhook.py     # 飞书Webhook
│   ├── database/
│   │   ├── crud.py               # 数据库CRUD操作
│   │   └── models.py             # 数据库模型
│   ├── config.py                 # 应用配置
│   └── main.py                   # FastAPI主应用
├── static/
│   ├── index.html                # 主页面
│   ├── chat.html                 # 智能对话界面
│   └── 国脉底图.png              # 国脉logo
├── data/
│   └── hr_database.db            # SQLite数据库
├── logs/
│   └── alignment_bot.log         # 应用日志
├── start_alignment_bot.sh        # 启动脚本
└── requirements.txt              # Python依赖
```

## 部署步骤

### 1. 部署到远程服务器
```bash
# 在本地运行部署脚本
chmod +x deploy_alignment_bot.sh
./deploy_alignment_bot.sh
```

### 2. 在远程服务器启动服务
```bash
# SSH连接到远程服务器
ssh root@121.229.172.161

# 进入应用目录
cd /root/shijingjing/e-employee/hr-bot

# 启动服务
./start_alignment_bot.sh
```

### 3. 验证服务状态
```bash
curl http://121.229.172.161:3111/health
```

## 日志查看

```bash
# 实时查看日志
tail -f /root/shijingjing/e-employee/hr-bot/logs/alignment_bot.log
```

## 安全确认

### 本地模型验证
系统配置已确保：
1. ✅ vLLM服务运行在本地服务器 (localhost:8002)
2. ✅ Qwen-14B模型本地部署，模型路径 `/models/qwen/Qwen-14B-Chat`
3. ✅ 不调用任何外部大模型API

### 数据不出域验证
1. ✅ SQLite数据库本地文件存储
2. ✅ 所有员工数据仅在本地处理
3. ✅ 不传输到外部服务器

## 故障排查

### 服务无法启动
```bash
# 检查端口占用
netstat -tlnp | grep 3111

# 检查依赖
pip list | grep -E "fastapi|uvicorn|aiosqlite|langchain"
```

### 模型服务异常
```bash
# 检查vLLM容器
docker ps | grep vllm

# 测试模型API
curl http://localhost:8002/v1/models
```

## 更新记录

### v1.0.0 (2026-03-07)
- ✅ 实现人岗适配评估核心功能
- ✅ 支持对话式查询员工信息
- ✅ 集成国脉品牌标识
- ✅ 实现历史记录保存功能
- ✅ 支持流式响应

## 联系方式

如有问题，请联系系统管理员。

---

**注意**: 本系统所有数据均在本地处理，符合国央企数据安全要求。
