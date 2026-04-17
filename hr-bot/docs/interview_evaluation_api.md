# AI面试评价接口文档

## 接口概览

| 项目 | 说明 |
|------|------|
| 基础URL | `http://121.229.172.161:3111` |
| 接口路径 | `/api/v1/interview-evaluation/evaluate` |
| 请求方法 | POST |
| 内容类型 | multipart/form-data |

---

## 1. 面试评价接口

### 1.1 接口说明

AI面试评价接口，基于Qwen3-235B大模型对候选人面试进行多维度评估。

**核心功能：**
- 优先使用离线ASR缓存数据（项目目录/transcriptions/候选人姓名/）
- 如果没有离线缓存，则查找本地预存ASR数据
- 如果都没有，则使用 Whisper API 转录音频
- 基于6个维度进行面试评价，同时生成岗位要求维度数据

### 1.2 请求参数

#### 入参（Form-Data）

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `jd_content` | string | 否 | JD文本内容（与jd_file二选一） |
| `jd_file` | file | 否 | JD文件（支持.docx, .pdf, .txt等） |
| `resume_content` | string | 否 | 简历文本内容（与resume_file二选一） |
| `resume_file` | file | 否 | 简历文件（支持.pdf, .docx, .txt等） |
| `audio_file` | file | 否 | 面试录音文件（AAC/MP3/WAV），如已存在预存ASR数据可不传 |
| `questions_file` | file | 否 | 面试问题Excel文件（.xlsx格式） |
| `candidate_name` | string | 否 | 候选人姓名，用于查找离线缓存 |
| `jd_title` | string | 否 | 岗位名称 |
| `project` | string | 否 | 项目名称，用于查找离线ASR缓存 |

**注意：**
- JD内容必须提供（jd_content或jd_file至少一个）
- 简历内容必须提供（resume_content或resume_file至少一个）
- 如果没有提供audio_file，则必须通过project+candidate_name找到离线ASR缓存

### 1.3 响应参数

#### 出参（JSON）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `success` | boolean | 是否成功 |
| `overall_score` | float | 综合面试评分（0-100） |
| `evaluation_level` | string | 评价等级（优秀/良好/一般/较差） |
| `dimensions` | array | 候选人各维度评分详情 |
| `jd_requirements` | object | **岗位要求维度数据（新增）** |
| `transcript` | string | 录音转文本内容 |
| `summary` | string | 面试总结（100-200字） |
| `strengths` | array | 候选人优势列表 |
| `weaknesses` | array | 候选人不足列表 |
| `recommendations` | array | 建议列表 |
| `question_answers` | array | 问题回答评价列表 |

#### dimensions 数组元素结构

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `name` | string | 维度名称（专业能力/工作经验/沟通表达/逻辑思维/学习能力/综合素质） |
| `score` | int | 维度得分（0-100） |
| `weight` | int | 维度权重（%） |
| `analysis` | string | 详细分析说明 |

#### jd_requirements 对象结构（新增）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `dimensions` | array | 岗位要求维度数组 |

#### jd_requirements.dimensions 数组元素结构

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `name` | string | 维度名称 |
| `score` | int | 岗位要求分数（0-100），**差异化分数，不再是全部100分** |
| `description` | string | 岗位对该维度的具体要求描述 |

#### question_answers 数组元素结构

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `question` | string | 问题内容 |
| `answer_summary` | string | 回答摘要 |
| `score` | int | 回答得分（0-100） |
| `evaluation` | string | 评价说明 |

### 1.4 响应示例

```json
{
    "success": true,
    "overall_score": 82.0,
    "evaluation_level": "良好",
    "dimensions": [
        {
            "name": "专业能力",
            "score": 85,
            "weight": 18,
            "analysis": "候选人在战略规划、行业研究和资本运作方面展现出扎实的专业能力..."
        },
        {
            "name": "工作经验",
            "score": 80,
            "weight": 18,
            "analysis": "候选人拥有15年战略管理经验，现任国企战略规划部总经理..."
        },
        {
            "name": "沟通表达",
            "score": 82,
            "weight": 16,
            "analysis": "表达整体流畅，能够围绕问题展开叙述，逻辑结构基本清晰..."
        },
        {
            "name": "逻辑思维",
            "score": 78,
            "weight": 16,
            "analysis": "在描述规划流程和跨部门协调机制时，能分点阐述..."
        },
        {
            "name": "学习能力",
            "score": 85,
            "weight": 16,
            "analysis": "候选人主动提及拥抱AI时代，并在实际工作中应用大数据模型..."
        },
        {
            "name": "综合素质",
            "score": 80,
            "weight": 16,
            "analysis": "展现出良好的职业素养和目标导向意识..."
        }
    ],
    "jd_requirements": {
        "dimensions": [
            {
                "name": "专业能力",
                "score": 90,
                "description": "要求具备扎实的战略规划与行业研究能力，熟悉资本运作流程，能够主导中长期规划制定与执行"
            },
            {
                "name": "工作经验",
                "score": 85,
                "description": "要求5年以上战略管理或相关领域工作经验，有成功主导重大战略项目的经历"
            },
            {
                "name": "沟通表达",
                "score": 70,
                "description": "要求具备良好的跨部门沟通协调能力，能够清晰传达战略意图并推动执行"
            },
            {
                "name": "逻辑思维",
                "score": 80,
                "description": "要求具备严谨的战略思维和分析能力，能够系统性解决复杂问题"
            },
            {
                "name": "学习能力",
                "score": 75,
                "description": "要求具备快速学习新技术和新领域知识的能力，适应快速变化的商业环境"
            },
            {
                "name": "综合素质",
                "score": 80,
                "description": "要求具备良好的职业素养、团队协作精神和抗压能力，认同企业文化"
            }
        ]
    },
    "transcript": "面试录音转录文本内容...",
    "summary": "黄俊华具备15年战略管理经验，曾任国企战略部总经理...",
    "strengths": [
        "丰富的战略规划与资本运作实战经验",
        "在人工智能与硬科技领域的深度行业积累",
        "具备战略与财务双轮驱动的成功项目成果"
    ],
    "weaknesses": [
        "口语表达不够精炼，存在术语误用",
        "部分回答逻辑结构有待加强"
    ],
    "recommendations": [
        "建议下一轮重点考察其战略方法论体系与跨部门推动力的细节案例",
        "可安排与业务负责人进行深度面谈，评估其战略前瞻性与创新思维"
    ],
    "question_answers": [
        {
            "question": "请介绍一下你的工作经历",
            "answer_summary": "候选人介绍自己在大型国企担任战略规划部总经理...",
            "score": 85,
            "evaluation": "回答内容丰富，突出关键经历与成果..."
        }
    ]
}
```

### 1.5 调用示例

#### cURL示例（使用离线缓存）

```bash
curl -X POST "http://121.229.172.161:3111/api/v1/interview-evaluation/evaluate" \
  -F "project=20260401战略招聘" \
  -F "candidate_name=黄俊华" \
  -F "jd_title=战略与创新部副总经理" \
  -F "jd_content=岗位JD文本内容..." \
  -F "resume_content=候选人简历内容..."
```

#### cURL示例（上传音频文件）

```bash
curl -X POST "http://121.229.172.161:3111/api/v1/interview-evaluation/evaluate" \
  -F "jd_file=@/path/to/job_description.docx" \
  -F "resume_file=@/path/to/resume.pdf" \
  -F "audio_file=@/path/to/interview.aac" \
  -F "candidate_name=张三" \
  -F "jd_title=产品经理"
```

#### Python示例

```python
import requests

url = "http://121.229.172.161:3111/api/v1/interview-evaluation/evaluate"

# 方式1：使用离线缓存
data = {
    "project": "20260401战略招聘",
    "candidate_name": "黄俊华",
    "jd_title": "战略与创新部副总经理",
    "jd_content": "岗位JD文本内容...",
    "resume_content": "候选人简历内容..."
}
response = requests.post(url, data=data)
result = response.json()

# 方式2：上传文件
files = {
    "jd_file": open("job_description.docx", "rb"),
    "resume_file": open("resume.pdf", "rb"),
    "audio_file": open("interview.aac", "rb")
}
data = {
    "candidate_name": "张三",
    "jd_title": "产品经理"
}
response = requests.post(url, files=files, data=data)
result = response.json()

# 获取岗位要求维度数据
jd_requirements = result.get("jd_requirements", {})
jd_dimensions = jd_requirements.get("dimensions", [])
for dim in jd_dimensions:
    print(f"{dim['name']}: {dim['score']}分 - {dim['description']}")
```

---

## 2. 评估缓存检查接口

### 2.1 接口说明

检查候选人的AI评估缓存是否存在。

### 2.2 请求参数

**GET** `/api/v1/interview-evaluation/evaluation-cache`

#### 入参（Query）

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `candidate_name` | string | 是 | 候选人姓名 |
| `project` | string | 是 | 项目名称 |

### 2.3 响应参数

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `success` | boolean | 是否成功 |
| `cached` | boolean | 是否存在缓存 |
| `evaluation` | object | 缓存的评估结果（如果存在） |
| `message` | string | 提示信息 |

### 2.4 调用示例

```bash
curl "http://121.229.172.161:3111/api/v1/interview-evaluation/evaluation-cache?candidate_name=黄俊华&project=20260401战略招聘"
```

---

## 3. 批量获取评估接口

### 3.1 接口说明

批量获取项目中所有候选人的AI评估缓存。

### 3.2 请求参数

**GET** `/api/v1/interview-evaluation/evaluations-batch`

#### 入参（Query）

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `project` | string | 是 | 项目名称 |

### 3.3 响应参数

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `success` | boolean | 是否成功 |
| `project` | string | 项目名称 |
| `total` | int | 候选人总数 |
| `evaluated_count` | int | 已评估人数 |
| `candidates` | array | 候选人评估列表 |

### 3.4 调用示例

```bash
curl "http://121.229.172.161:3111/api/v1/interview-evaluation/evaluations-batch?project=20260401战略招聘"
```

---

## 4. 数据目录结构

### 4.1 离线ASR缓存目录

```
/root/shijingjing/e-employee/hr-bot/data/interview/
└── {项目名称}/
    ├── transcriptions/
    │   ├── _processing_summary.json    # 汇总文件
    │   ├── {候选人姓名}/
    │   │   └── {音频文件名}.json      # 转录缓存
    │   └── {音频文件名}.json          # 转录缓存
    ├── evaluations/
    │   └── {候选人姓名}_evaluation.json  # 评估结果缓存
    └── _shared_resources.json          # 共享资源（JD、问题等）
```

### 4.2 评估缓存文件格式

```json
{
    "candidate_name": "黄俊华",
    "project": "20260401战略招聘",
    "evaluation": {
        "overall_score": 82,
        "evaluation_level": "良好",
        "dimensions": [...],
        "jd_requirements": {
            "dimensions": [...]
        },
        ...
    },
    "cached_at": "2025-04-16T10:30:00"
}
```

---

## 5. 更新说明

### v2.0 更新内容（2025-04-16）

1. **新增岗位要求维度数据**
   - 后端Prompt优化，LLM同时生成岗位要求维度数据
   - 新增 `jd_requirements` 字段，包含6个维度的岗位要求分数
   - 岗位要求分数根据JD内容动态生成，不再是固定的100分

2. **岗位要求分数差异化**
   - 专业能力：85-95分（核心要求）
   - 工作经验：80-90分（重要要求）
   - 逻辑思维：75-85分（中等偏上要求）
   - 综合素质：75-85分（中等偏上要求）
   - 学习能力：70-80分（中等要求）
   - 沟通表达：70-80分（中等要求）

3. **前端展示优化**
   - 优先使用后端返回的真实岗位要求数据
   - 如果没有后端数据，根据维度名称动态生成合理的岗位要求分数

---

## 6. 错误码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误（缺少JD或简历内容，或未找到ASR数据） |
| 404 | 项目或候选人不存在 |
| 500 | 服务器内部错误（转录失败或评价失败） |

---

## 7. 注意事项

1. **离线缓存优先**：接口会优先查找离线ASR缓存，提高响应速度
2. **评估缓存复用**：同一候选人的评估结果会被缓存，避免重复调用LLM
3. **音频格式支持**：支持AAC、MP3、WAV格式
4. **文件大小限制**：建议音频文件不超过100MB
5. **超时时间**：评估接口可能需要较长时间（30-300秒），请设置合适的超时时间
