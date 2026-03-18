# 人力数字员工智能体系统

基于大模型的HR智能问答和管理预警系统，使用 FastAPI + LangChain + LangGraph 构建。

## 功能特性

- **智能问答**: 基于 RAG 架构回答员工信息相关问题
- **合同预警**: 自动识别合同即将到期的员工
- **绩效预警**: 识别绩效异常员工
- **飞书集成**: 通过 Webhook 接入飞书机器人
- **私有化部署**: 本地部署，数据安全

## 技术栈

- **大模型**: Qwen-14B-Chat (通过 vLLM 部署)
- **开发框架**: LangChain + LangGraph
- **向量数据库**: ChromaDB
- **Embedding模型**: BAAI/bge-base-zh-v1.5
- **后端框架**: FastAPI
- **数据库**: SQLite

## 项目结构

```
hr-bot/
├── app/
│   ├── agent/           # LangGraph 智能体
│   │   ├── hr_agent.py  # HR智能体核心
│   │   ├── prompts.py   # 提示词模板
│   │   └── state.py     # 状态定义
│   ├── api/             # API 接口
│   │   └── feishu_webhook.py  # 飞书Webhook
│   ├── database/        # 数据库模块
│   │   ├── models.py    # SQLAlchemy 模型
│   │   └── crud.py      # CRUD 操作
│   ├── knowledge/       # 知识库模块
│   │   └── builder.py   # 知识库构建器
│   ├── tools/           # 工具集
│   │   └── hr_tools.py  # HR工具
│   ├── config.py        # 配置管理
│   └── main.py          # FastAPI 入口
├── scripts/             # 脚本工具
│   ├── init_database.py      # 初始化数据库
│   ├── build_knowledge_base.py # 构建知识库
│   └── download_models.py    # 下载模型
├── deploy.sh            # 部署脚本
├── start_server.sh      # 本地启动脚本
├── requirements.txt     # 依赖列表
└── .env.example         # 环境变量示例

```

## 快速开始

### 1. 环境准备

确保已安装：
- Python 3.9+
- Conda
- (可选) CUDA 支持

### 2. 本地开发

```bash
# 进入项目目录
cd hr-bot

# 启动服务
./start_server.sh
```

服务将在 http://localhost:8000 启动

### 3. 远程部署

```bash
# 一键部署到远程服务器
./deploy.sh
```

部署完成后，服务将在 http://121.229.172.161:8000 运行

## 配置说明

复制 `.env.example` 为 `.env`，并修改以下配置：

```env
# LLM 配置 (vLLM)
VLLM_HOST=localhost
VLLM_PORT=8001
VLLM_MODEL=Qwen/Qwen-14B-Chat
OPENAI_API_BASE=http://localhost:8001/v1

# 飞书 Webhook
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
FEISHU_WEBHOOK_SECRET=your_secret

# 预警设置
CONTRACT_ALERT_DAYS=30
PERFORMANCE_THRESHOLD=60.0
```

## API 接口

### 健康检查
```
GET /health
```

### 飞书 Webhook
```
POST /api/v1/feishu/webhook
```

### 获取配置
```
GET /api/v1/config
```

## 数据初始化

### 初始化数据库
```bash
python scripts/init_database.py
```

### 构建知识库
```bash
python scripts/build_knowledge_base.py
```

## 飞书机器人配置

1. 在飞书开放平台创建机器人
2. 获取 Webhook URL 和 Secret
3. 配置到 `.env` 文件
4. 订阅 `im.message.receive_v1` 事件

## 许可证

MIT
