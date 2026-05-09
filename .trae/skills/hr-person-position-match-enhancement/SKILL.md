---
name: hr-person-position-match-enhancement
description: 人岗适配分析界面功能增强技能。用于在人岗适配分析报告界面中新增展示模块（如问答概要、能力维度详情等），包含后端接口修改、前端页面更新、远程部署调试的完整流程。
version: 1.0.0
---

# 人岗适配分析界面功能增强技能

## 功能概述

本技能用于在人岗适配分析报告中添加新的展示模块。典型应用场景包括：
- 在综合评价和发展建议之间添加面试问答概要
- 添加新的能力维度详情展示
- 添加新的图表或数据展示区域

## 技术栈

- **后端**：Python 3.13 + FastAPI
- **前端**：HTML + JavaScript（原生）
- **包管理**：Conda 环境 `media_env`
- **远程服务器**：121.229.172.161
- **工作目录**：/root/shijingjing/e-employee/hr-bot

## 文件结构

```
hr-bot/
├── app/
│   └── api/
│       └── alignment_routes.py    # 人岗适配分析API接口
├── static/
│   └── chat.html                  # 前端页面（包含人岗适配报告展示）
├── data/
│   └── innovation_files/          # 上传的录音和问题文件存储目录
└── logs/
    └── uvicorn.log                # 服务日志
```

## 开发流程

### 第一阶段：后端接口开发

#### 1. 确定新增功能的数据需求

首先明确需要展示什么数据，例如：
- 面试问答概要（问题 + 答案概要）
- 能力维度详情
- 其他结构化数据

#### 2. 修改数据模型（Pydantic）

在 `alignment_routes.py` 中添加新的响应模型：

```python
class QASummaryItem(BaseModel):
    """问答概要项"""
    question: str           # 问题内容
    answer_summary: str     # 答案概要
```

然后在响应模型中添加新字段：

```python
class AlignmentAnalyzeResponse(BaseModel):
    """人岗适配分析响应"""
    # ... 其他字段 ...
    qa_summary: Optional[List[QASummaryItem]]  # 新增字段
```

#### 3. 开发数据处理函数

添加从原始数据中提取/生成新展示数据的函数：

```python
async def generate_qa_summary_from_interview(
    audio_file_path: Optional[str] = None,
    questions_file_path: Optional[str] = None
) -> List[Dict]:
    """从面试录音和提问文件中提取问答概要"""
    # 实现逻辑
```

**关键要点**：
- 处理可选文件参数（用户可能不上传文件）
- 支持多种文件格式（wav/mp3, xlsx/csv/txt）
- 调用大模型提取结构化数据
- 包含完善的错误处理和日志记录

#### 4. 修改主分析接口

在 `analyze_alignment` 函数中集成新数据的生成：

```python
# 10. 生成问答概要（从录音和提问文件中提取）
qa_summary = await generate_qa_summary_from_interview(
    request.innovation_audio_file,
    request.innovation_questions_file
)

return {
    "success": True,
    "data": {
        # ... 其他字段 ...
        "qa_summary": qa_summary  # 添加到返回数据中
    }
}
```

### 第二阶段：前端页面开发

#### 1. 定位显示位置

在 `chat.html` 中找到需要插入新模块的位置。人岗适配报告显示函数是 `displayAlignmentResultInChat(data)`。

#### 2. 编写HTML模板

根据需求编写HTML模板：

```javascript
// 5. 问答概要（无论是否上传文件都显示区域）
let qaSummaryHtml = '';

if (data.qa_summary && data.qa_summary.length > 0) {
    // 有问答数据，显示具体内容
    qaSummaryHtml = `
        <div style="font-weight: 600; color: #1976d2; margin-bottom: 10px;">🎤 面试问答概要</div>
        <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 15px;">
            ${data.qa_summary.map(qa => `
                <div style="background: white; padding: 12px; border-radius: 8px; border-left: 3px solid #1976d2;">
                    <div style="font-weight: 600; color: #333; margin-bottom: 6px;">问题：${qa.question}</div>
                    <div style="color: #666; line-height: 1.6;">答案概要：${qa.answer_summary}</div>
                </div>
            `).join('')}
        </div>
    `;
} else {
    // 无问答数据，显示提示信息
    qaSummaryHtml = `
        <div style="font-weight: 600; color: #1976d2; margin-bottom: 10px;">🎤 面试问答概要</div>
        <div style="background: white; padding: 12px; border-radius: 8px; border-left: 3px solid #1976d2; margin-bottom: 15px;">
            <div style="color: #999; line-height: 1.6; text-align: center; padding: 20px;">
                未上传面试录音和问题对<br>
                <span style="font-size: 12px; color: #bbb;">上传录音文件和问题列表后可自动提取问答概要</span>
            </div>
        </div>
    `;
}
```

#### 3. 插入到报告模板中

将新模块插入到适当位置：

```javascript
const conclusionHtml = `
    <div style="background: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
        <div style="font-weight: 600; color: #2e7d32; margin-bottom: 10px;">📝 综合评价</div>
        <div style="line-height: 1.6; margin-bottom: 15px; background: white; padding: 12px; border-radius: 8px;">${data.conclusion}</div>
        ${qaSummaryHtml}  <!-- 插入新模块 -->
        <div style="font-weight: 600; color: #333; margin-bottom: 10px;">💡 发展建议</div>
        <!-- ... -->
    </div>
`;
```

#### 4. 添加调试日志

为了排查问题，添加控制台日志：

```javascript
console.log('[QA Summary] data.qa_summary:', data.qa_summary);
console.log('[QA Summary] data keys:', Object.keys(data));
```

### 第三阶段：远程部署

#### 1. 上传修改的文件到远程服务器

```bash
# 上传后端代码
scp /本地路径/hr-bot/app/api/alignment_routes.py root@121.229.172.161:/root/shijingjing/e-employee/hr-bot/app/api/

# 上传前端代码
scp /本地路径/hr-bot/static/chat.html root@121.229.172.161:/root/shijingjing/e-employee/hr-bot/static/
```

#### 2. 重启远程服务

```bash
# SSH连接到远程服务器
ssh root@121.229.172.161

# 停止旧服务
cd /root/shijingjing/e-employee/hr-bot
ps aux | grep uvicorn | grep 3111 | grep -v grep | awk '{print $2}' | xargs kill -9

# 启动新服务
source /root/miniconda3/bin/activate media_env
nohup uvicorn app.main:app --host 0.0.0.0 --port 3111 > /root/shijingjing/e-employee/hr-bot/logs/uvicorn.log 2>&1 &

# 等待服务启动
sleep 5

# 验证服务状态
curl -s http://localhost:3111/api/v1/alignment/dimensions
```

#### 3. 检查服务日志

```bash
tail -30 /root/shijingjing/e-employee/hr-bot/logs/uvicorn.log
```

正常启动日志应包含：
```
INFO:     Started server process [PID]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:3111
```

### 第四阶段：功能验证与调试

#### 1. 前端验证

1. 打开浏览器，访问人岗适配分析页面
2. 按 `Ctrl+F5` 强制刷新（清除缓存）
3. 进行人岗适配分析，上传录音文件和问题文件
4. 查看报告中是否正确显示新模块

#### 2. 调试技巧

**如果新模块不显示**：

1. **检查浏览器控制台**：
   - 按 F12 打开开发者工具
   - 查看 Console 中的日志信息
   - 确认 `data.qa_summary` 是否存在且格式正确

2. **检查网络请求**：
   - 查看 Network 面板中的 API 响应
   - 确认后端是否返回了 `qa_summary` 字段

3. **检查后端日志**：
   ```bash
   ssh root@121.229.172.161 "tail -50 /root/shijingjing/e-employee/hr-bot/logs/uvicorn.log"
   ```

4. **常见问题排查**：
   - 浏览器缓存：按 `Ctrl+F5` 强制刷新
   - 文件未上传：确认 scp 成功
   - 服务未重启：确认进程已更新
   - 数据为空：确认后端逻辑正确执行

## 大模型调用示例

### 调用远程 LLM 提取结构化数据

```python
async def _extract_qa_summary_with_llm(transcription_text: str, questions_content: str) -> List[Dict]:
    """使用大模型从转录文本中提取问答概要"""
    import aiohttp
    
    prompt = f"""请从以下面试录音转录文本中提取问答概要。

面试录音转录内容：{transcription_text[:3000]}
提问问题列表：{questions_content[:1500]}

提取要求：
1. 识别面试中的关键问题和对应的回答
2. 每个问题提取核心要点，答案概要控制在50字以内

请按以下JSON格式返回：
{{
    "qa_summary": [
        {{
            "question": "问题内容",
            "answer_summary": "答案概要（50字以内）"
        }}
    ]
}}"""
    
    async with aiohttp.ClientSession() as session:
        payload = {
            "model": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "messages": [
                {"role": "system", "content": "你是一个专业的人力资源助手，擅长从面试录音中提取关键问答信息。请严格按照JSON格式输出。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer z3oK7bN9xPqW2mT8rYvL5tF1cJ4hD6gA0eS2uI3nQk"
        }
        
        async with session.post(
            "http://180.97.200.118:30071/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as response:
            if response.status == 200:
                result = await response.json()
                content = result['choices'][0]['message']['content']
                # 解析JSON...
```

## 安全与合规要求

- **数据不出域**：所有数据库操作在本地/内网完成
- **API调用**：仅允许调用指定的远程LLM服务（180.97.200.118）
- **异常处理**：必须包含完善的错误捕获机制
- **文件上传**：限制文件类型和大小，防止恶意文件上传

## 配置参数

### 大模型配置
- **远程 LLM URL**: `http://180.97.200.118:30071/v1/chat/completions`
- **API Key**: `z3oK7bN9xPqW2mT8rYvL5tF1cJ4hD6gA0eS2uI3nQk`
- **模型名称**: `Qwen/Qwen3-235B-A22B-Instruct-2507`

### 服务器配置
- **运行主机**: 121.229.172.161
- **服务端口**: 3111
- **Conda环境**: media_env（位于 /root/miniconda3）

## 相关文件

- 后端接口：`hr-bot/app/api/alignment_routes.py`
- 前端页面：`hr-bot/static/chat.html`
- 服务配置：`hr-bot/app/config.py`
- 服务日志：`hr-bot/logs/uvicorn.log`
