# 人力数字员工 - API使用指南

## 基础信息

- **基础URL**: `http://121.229.172.161:3111`
- **API版本**: `v1`
- **内容类型**: `application/json`

## 接口列表

### 1. 健康检查

检查服务运行状态。

**请求**:
```http
GET /health
```

**响应示例**:
```json
{
    "status": "healthy",
    "service": "hr-bot",
    "version": "1.0.0",
    "features": {
        "alignment_analysis": true,
        "streaming": true,
        "local_model": true
    }
}
```

---

### 2. 分析单个员工

对指定员工进行人岗适配评估分析。

**请求**:
```http
POST /api/v1/alignment/analyze
Content-Type: application/json

{
    "employee_name": "石京京",
    "include_details": true
}
```

**参数说明**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| employee_name | string | 是 | 员工姓名 |
| include_details | boolean | 否 | 是否包含详细信息，默认true |

**响应示例**:
```json
{
    "employee_name": "石京京",
    "overall_score": 75,
    "alignment_level": "基本匹配",
    "raw_analysis": "综合评分: 75，适配等级: 基本匹配\n\n各维度评分和评价..."
}
```

---

### 3. 流式分析员工

实时流式返回分析结果。

**请求**:
```http
POST /api/v1/alignment/analyze/stream
Content-Type: application/json

{
    "employee_name": "石京京"
}
```

**响应**: SSE流式数据
```
data: {"chunk": "综合评分", "index": 1}

data: {"chunk": ": 75", "index": 2}

data: {"done": true, "total_chunks": 50}
```

---

### 4. 对比多个员工

对比多个员工的人岗适配情况。

**请求**:
```http
POST /api/v1/alignment/compare
Content-Type: application/json

{
    "employee_names": ["石京京", "余祯", "周灏"]
}
```

**参数说明**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| employee_names | array | 是 | 员工姓名列表 |

**响应示例**:
```json
{
    "comparison": "石京京 vs 余祯 vs 周灏\n\n综合对比分析...",
    "employee_names": ["石京京", "余祯", "周灏"]
}
```

---

### 5. 获取评估维度

获取人岗适配评估的维度定义。

**请求**:
```http
GET /api/v1/alignment/dimensions
```

**响应示例**:
```json
{
    "dimensions": [
        {
            "name": "能力画像",
            "weight": 0.4,
            "sub_dimensions": [
                {"name": "专业能力", "weight": 0.4},
                {"name": "管理能力", "weight": 0.25}
            ]
        }
    ]
}
```

---

### 6. 对话式查询

通过自然语言查询员工信息。

**请求**:
```http
POST /api/v1/alignment/chat
Content-Type: application/json

{
    "message": "石京京是哪个学校的",
    "session_id": "optional-session-id"
}
```

**参数说明**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | 是 | 用户查询消息 |
| session_id | string | 否 | 会话ID |

**响应示例**:
```json
{
    "reply": "石京京的学校是天津理工大学。",
    "session_id": "new_session"
}
```

---

### 7. 流式对话

实时流式返回对话回复。

**请求**:
```http
POST /api/v1/alignment/chat/stream
Content-Type: application/json

{
    "message": "石京京是哪个学校的"
}
```

**响应**: SSE流式数据
```
data: {"chunk": "石京京", "index": 1}

data: {"chunk": "的学校是", "index": 2}

data: {"chunk": "天津理工大学", "index": 3}

data: {"done": true, "total_chunks": 10}
```

---

## 错误处理

### 错误响应格式
```json
{
    "detail": "错误描述信息"
}
```

### 常见错误码
| HTTP状态码 | 说明 |
|-----------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 员工未找到 |
| 500 | 服务器内部错误 |

---

## 使用示例

### Python示例
```python
import requests

# 分析员工
response = requests.post(
    "http://121.229.172.161:3111/api/v1/alignment/analyze",
    json={"employee_name": "石京京"}
)
result = response.json()
print(result["raw_analysis"])

# 对话查询
response = requests.post(
    "http://121.229.172.161:3111/api/v1/alignment/chat",
    json={"message": "石京京是哪个学校的"}
)
result = response.json()
print(result["reply"])
```

### JavaScript示例
```javascript
// 分析员工
fetch('http://121.229.172.161:3111/api/v1/alignment/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ employee_name: '石京京' })
})
.then(res => res.json())
.then(data => console.log(data.raw_analysis));

// 流式对话
const eventSource = new EventSource(
    'http://121.229.172.161:3111/api/v1/alignment/chat/stream',
    { body: JSON.stringify({ message: '石京京是哪个学校的' }) }
);

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.done) {
        eventSource.close();
    } else {
        console.log(data.chunk);
    }
};
```

### cURL示例
```bash
# 分析员工
curl -X POST http://121.229.172.161:3111/api/v1/alignment/analyze \
  -H "Content-Type: application/json" \
  -d '{"employee_name": "石京京"}'

# 对话查询
curl -X POST http://121.229.172.161:3111/api/v1/alignment/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "石京京是哪个学校的"}'
```

---

## 支持的查询类型

### 员工信息查询
- "石京京是哪个学校的？"
- "余祯的绩效怎么样？"
- "周灏是什么岗位？"
- "张三在哪个部门？"

### 人岗适配分析
- "分析一下石京京的人岗适配情况"
- "评估余祯的适配度"
- "周灏适合当前岗位吗？"

---

## 注意事项

1. **数据安全**: 所有API请求都在本地服务器处理，数据不出域
2. **员工姓名**: 查询时必须使用数据库中存在的员工姓名
3. **流式接口**: 流式接口使用SSE协议，前端需要相应处理
4. **超时设置**: 建议设置合理的超时时间（30-60秒）

---

## 更新日志

### v1.0.0 (2026-03-07)
- 初始版本发布
- 支持人岗适配分析
- 支持对话式查询
- 支持流式响应
