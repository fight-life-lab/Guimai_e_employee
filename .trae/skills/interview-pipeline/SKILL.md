---
name: "interview-pipeline"
description: "面试数据处理全流程Skill。Invoke when user needs to process interview audio data, generate ASR transcripts, create QA pairs, or evaluate candidates using AI. Handles the complete pipeline from audio to evaluation."
---

# 面试数据处理全流程 Skill

## 功能说明

本Skill用于处理面试数据的全流程，包括ASR转录、QA问题对生成、AI评分三个核心步骤。

## 数据目录结构

```
/root/shijingjing/e-employee/hr-bot/data/interview/
└── {项目名称}/                    # 例如: 20260401战略招聘
    ├── tras/                     # ASR转录结果
    │   ├── {候选人}.json         # 转录文本
    │   └── ...
    ├── qa/                       # QA问题对
    │   ├── {候选人}.json         # 问题-回答对
    │   └── ...
    ├── eval/                     # AI评估结果
    │   ├── {候选人}.json         # 评估报告
    │   └── ...
    └── process.log               # 处理日志
```

## 处理流程

### 步骤1: ASR转录 (Audio → Text)

**接口**: `POST http://localhost:8003/transcribe` (本地Whisper ASR服务)

**功能**: 将面试录音文件转换为文本

**输入**:
- 音频文件 (.aac, .mp3, .wav, .m4a)
- 语言参数 (zh)

**输出保存到**: `{项目}/tras/{候选人}.json`

```json
{
  "candidate_name": "黄俊华",
  "audio_file": "04月10日_10黄俊华.aac",
  "transcription": "完整的面试转录文本...",
  "duration": 1800,
  "processed_at": "2025-04-16T10:30:00"
}
```

### 步骤2: QA问题对生成 (Text → QA)

**接口**: `POST /api/v1/interview-batch/qa-extract`

**功能**: 从转录文本中提取问题-回答对

**输入**:
- 转录文本
- 面试问题文件 (可选)

**输出保存到**: `{项目}/qa/{候选人}.json`

```json
{
  "candidate_name": "黄俊华",
  "qa_pairs": [
    {
      "question": "请介绍一下你的工作经历",
      "answer": "候选人回答内容...",
      "start_time": 120,
      "end_time": 300
    }
  ],
  "processed_at": "2025-04-16T10:35:00"
}
```

### 步骤3: AI评估生成 (QA → Evaluation)

**接口**: `POST /api/v1/interview-evaluation/evaluate`

**功能**: 基于QA和JD生成AI评估报告

**输入**:
- QA问题对
- JD岗位描述
- 候选人简历

**输出保存到**: `{项目}/eval/{候选人}.json`

```json
{
  "candidate_name": "黄俊华",
  "overall_score": 82,
  "evaluation_level": "良好",
  "dimensions": [...],
  "jd_requirements": {
    "dimensions": [...]
  },
  "summary": "综合评价...",
  "strengths": [...],
  "weaknesses": [...],
  "recommendations": [...],
  "processed_at": "2025-04-16T10:40:00"
}
```

## 候选人列表（10人）

项目：`20260401战略招聘`

| 序号 | 候选人姓名 | 音频文件 |
|------|-----------|---------|
| 1 | 仇天硕 | 04月10日_1仇天硕.aac |
| 2 | 褚祎鹤 | 04月10日_2褚祎鹤.aac |
| 3 | 石欣慰 | 04月10日_4石欣慰.aac |
| 4 | 李贤峰 | 04月10日_5李贤峰.aac |
| 5 | 郑振东 | 04月10日_6郑振东.aac |
| 6 | 邹川龙 | 04月10日_7邹川龙.aac |
| 7 | 邱洋 | 04月10日_8邱洋.aac |
| 8 | 黄俊华 | 04月10日_10黄俊华.aac |
| 9 | 吴届生 | 04月10日_11吴届生.aac |
| 10 | 雷雨田 | 04月10日_12雷雨田.aac |

## 完整处理脚本

```python
#!/usr/bin/env python3
"""
面试数据处理全流程脚本
步骤1: ASR转录 → 步骤2: QA提取 → 步骤3: AI评估
"""

import requests
import json
import os
import time
from pathlib import Path
from datetime import datetime

# 配置
API_BASE = "http://121.229.172.161:3111"
PROJECT_NAME = "20260401战略招聘"
JD_TITLE = "战略与创新部副总经理"
PROJECT_DIR = f"/root/shijingjing/e-employee/hr-bot/data/interview/{PROJECT_NAME}"

# 候选人列表
CANDIDATES = [
    "仇天硕", "褚祎鹤", "石欣慰", "李贤峰", "郑振东",
    "邹川龙", "邱洋", "黄俊华", "吴届生", "雷雨田"
]

def log(message):
    """记录日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    
    # 写入日志文件
    log_file = Path(PROJECT_DIR) / "process.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_msg + '\n')

def step1_asr(candidate_name):
    """步骤1: ASR转录"""
    log(f"[{candidate_name}] 步骤1: 开始ASR转录...")
    
    # 查找音频文件
    audio_files = list(Path(PROJECT_DIR).glob(f"*{candidate_name}*.aac")) + \
                  list(Path(PROJECT_DIR).glob(f"*{candidate_name}*.mp3")) + \
                  list(Path(PROJECT_DIR).glob(f"*{candidate_name}*.wav"))
    
    if not audio_files:
        log(f"[{candidate_name}] 未找到音频文件")
        return None
    
    audio_file = audio_files[0]
    log(f"[{candidate_name}] 找到音频文件: {audio_file.name}")
    
    # 调用ASR接口
    url = f"{API_BASE}/api/v1/interview-batch/asr"
    
    try:
        with open(audio_file, 'rb') as f:
            files = {'audio': f}
            data = {
                'candidate_name': candidate_name,
                'project': PROJECT_NAME
            }
            response = requests.post(url, files=files, data=data, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                # 保存ASR结果
                tras_dir = Path(PROJECT_DIR) / "tras"
                tras_dir.mkdir(parents=True, exist_ok=True)
                
                tras_file = tras_dir / f"{candidate_name}.json"
                tras_data = {
                    "candidate_name": candidate_name,
                    "audio_file": audio_file.name,
                    "transcription": result.get('transcription', ''),
                    "duration": result.get('duration', 0),
                    "processed_at": datetime.now().isoformat()
                }
                
                with open(tras_file, 'w', encoding='utf-8') as f:
                    json.dump(tras_data, f, ensure_ascii=False, indent=2)
                
                log(f"[{candidate_name}] ASR转录完成，保存到: {tras_file}")
                return tras_data
            else:
                log(f"[{candidate_name}] ASR转录失败: {result.get('message')}")
                return None
        else:
            log(f"[{candidate_name}] ASR请求失败: {response.status_code}")
            return None
            
    except Exception as e:
        log(f"[{candidate_name}] ASR异常: {e}")
        return None

def step2_qa(candidate_name, tras_data):
    """步骤2: QA问题对提取"""
    log(f"[{candidate_name}] 步骤2: 开始QA提取...")
    
    url = f"{API_BASE}/api/v1/interview-batch/qa-extract"
    
    data = {
        'candidate_name': candidate_name,
        'project': PROJECT_NAME,
        'transcription': tras_data.get('transcription', '')
    }
    
    try:
        response = requests.post(url, data=data, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                # 保存QA结果
                qa_dir = Path(PROJECT_DIR) / "qa"
                qa_dir.mkdir(parents=True, exist_ok=True)
                
                qa_file = qa_dir / f"{candidate_name}.json"
                qa_data = {
                    "candidate_name": candidate_name,
                    "qa_pairs": result.get('qa_pairs', []),
                    "processed_at": datetime.now().isoformat()
                }
                
                with open(qa_file, 'w', encoding='utf-8') as f:
                    json.dump(qa_data, f, ensure_ascii=False, indent=2)
                
                log(f"[{candidate_name}] QA提取完成，保存到: {qa_file}")
                return qa_data
            else:
                log(f"[{candidate_name}] QA提取失败: {result.get('message')}")
                return None
        else:
            log(f"[{candidate_name}] QA请求失败: {response.status_code}")
            return None
            
    except Exception as e:
        log(f"[{candidate_name}] QA异常: {e}")
        return None

def step3_evaluate(candidate_name, qa_data):
    """步骤3: AI评估"""
    log(f"[{candidate_name}] 步骤3: 开始AI评估...")
    
    url = f"{API_BASE}/api/v1/interview-evaluation/evaluate"
    
    # 读取JD和简历
    jd_content = "战略与创新部副总经理岗位招聘公告"
    resume_content = f"{candidate_name}简历"
    
    data = {
        'project': PROJECT_NAME,
        'candidate_name': candidate_name,
        'jd_title': JD_TITLE,
        'jd_content': jd_content,
        'resume_content': resume_content,
        'qa_pairs': json.dumps(qa_data.get('qa_pairs', []))
    }
    
    try:
        response = requests.post(url, data=data, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                # 保存评估结果
                eval_dir = Path(PROJECT_DIR) / "eval"
                eval_dir.mkdir(parents=True, exist_ok=True)
                
                eval_file = eval_dir / f"{candidate_name}.json"
                eval_data = {
                    "candidate_name": candidate_name,
                    "overall_score": result.get('overall_score', 0),
                    "evaluation_level": result.get('evaluation_level', '未知'),
                    "dimensions": result.get('dimensions', []),
                    "jd_requirements": result.get('jd_requirements', {}),
                    "summary": result.get('summary', ''),
                    "strengths": result.get('strengths', []),
                    "weaknesses": result.get('weaknesses', []),
                    "recommendations": result.get('recommendations', []),
                    "processed_at": datetime.now().isoformat()
                }
                
                with open(eval_file, 'w', encoding='utf-8') as f:
                    json.dump(eval_data, f, ensure_ascii=False, indent=2)
                
                log(f"[{candidate_name}] AI评估完成，综合得分: {eval_data['overall_score']}分 ({eval_data['evaluation_level']})")
                return eval_data
            else:
                log(f"[{candidate_name}] AI评估失败: {result}")
                return None
        else:
            log(f"[{candidate_name}] AI评估请求失败: {response.status_code}")
            return None
            
    except Exception as e:
        log(f"[{candidate_name}] AI评估异常: {e}")
        return None

def process_candidate(candidate_name):
    """处理单个候选人"""
    log(f"\n{'='*60}")
    log(f"开始处理候选人: {candidate_name}")
    log(f"{'='*60}")
    
    # 步骤1: ASR转录
    tras_data = step1_asr(candidate_name)
    if not tras_data:
        log(f"[{candidate_name}] ASR转录失败，跳过后续步骤")
        return False
    
    # 步骤2: QA提取
    qa_data = step2_qa(candidate_name, tras_data)
    if not qa_data:
        log(f"[{candidate_name}] QA提取失败，跳过后续步骤")
        return False
    
    # 步骤3: AI评估
    eval_data = step3_evaluate(candidate_name, qa_data)
    if not eval_data:
        log(f"[{candidate_name}] AI评估失败")
        return False
    
    log(f"[{candidate_name}] 全流程处理完成!")
    return True

def main():
    """主函数"""
    log("\n" + "="*60)
    log("面试数据处理全流程开始")
    log(f"项目: {PROJECT_NAME}")
    log(f"候选人数量: {len(CANDIDATES)}")
    log("="*60)
    
    success_count = 0
    fail_count = 0
    
    for i, candidate in enumerate(CANDIDATES, 1):
        log(f"\n[{i}/{len(CANDIDATES)}] 处理第 {i} 个候选人")
        
        if process_candidate(candidate):
            success_count += 1
        else:
            fail_count += 1
        
        # 避免请求过快
        if i < len(CANDIDATES):
            time.sleep(3)
    
    log("\n" + "="*60)
    log("全流程处理完成!")
    log(f"成功: {success_count}/{len(CANDIDATES)}")
    log(f"失败: {fail_count}/{len(CANDIDATES)}")
    log("="*60)

if __name__ == "__main__":
    main()
```

## 执行步骤

### 1. 上传脚本到服务器

```bash
scp interview_pipeline.py root@121.229.172.161:/root/shijingjing/e-employee/hr-bot/scripts/
```

### 2. 在服务器上执行

```bash
ssh root@121.229.172.161
cd /root/shijingjing/e-employee/hr-bot
source /root/miniconda3/etc/profile.d/conda.sh
conda activate media_env
python scripts/interview_pipeline.py
```

### 3. 查看处理日志

```bash
tail -f /root/shijingjing/e-employee/hr-bot/data/interview/20260401战略招聘/process.log
```

## 注意事项

1. **目录结构**: 确保项目目录存在且包含音频文件
2. **接口依赖**: 确保API服务已启动 (`uvicorn app.main:app --port 3111`)
3. **执行时间**: 每个候选人约需1-2分钟（ASR+QA+评估），10人预计15-20分钟
4. **错误处理**: 脚本会自动跳过失败的步骤，继续处理下一个候选人
5. **日志记录**: 所有操作都会记录到 `process.log` 文件中
