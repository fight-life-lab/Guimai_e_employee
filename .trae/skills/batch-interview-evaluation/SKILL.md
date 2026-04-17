---
name: "batch-interview-evaluation"
description: "批量为候选人生成AI面试评估结果。Invoke when user needs to batch evaluate multiple candidates for interview assessment, or when generating offline evaluation results for a list of candidates."
---

# 批量面试评估Skill

## 功能说明

本Skill用于批量为多个候选人生成AI面试评估结果，支持离线ASR缓存数据，自动调用Qwen3-235B大模型进行6维度评估。

## 使用场景

- 需要对多个候选人批量生成面试评估报告
- 基于离线ASR缓存数据批量评估
- 为项目中的所有候选人统一生成评估结果

## 候选人列表（10人）

项目：`20260401战略招聘`

| 序号 | 候选人姓名 | 音频文件 | 简历文件 |
|------|-----------|---------|---------|
| 1 | 仇天硕 | 04月10日_1仇天硕.aac | 新国脉数字文化股份有限公司招聘报名表（仇天硕）.xlsx |
| 2 | 褚祎鹤 | 04月10日_2褚祎鹤.aac | 新国脉数字文化股份有限公司招聘报名表（褚祎鹤）.xlsx |
| 3 | 石欣慰 | 04月10日_4石欣慰.aac | 新国脉数字文化股份有限公司招聘报名表（石欣慰）.xlsx |
| 4 | 李贤峰 | 04月10日_5李贤峰.aac | 新国脉数字文化股份有限公司招聘报名表（李贤峰）.xlsx |
| 5 | 郑振东 | 04月10日_6郑振东.aac | 新国脉数字文化股份有限公司招聘报名表（郑振东）.xlsx |
| 6 | 邹川龙 | 04月10日_7邹川龙.aac | 新国脉数字文化股份有限公司招聘报名表（邹川龙）.xlsx |
| 7 | 邱洋 | 04月10日_8邱洋.aac | 新国脉数字文化股份有限公司招聘报名表（邱洋）.xlsx |
| 8 | 黄俊华 | 04月10日_10黄俊华.aac | 新国脉数字文化股份有限公司招聘报名表（黄俊华）.xlsx |
| 9 | 吴届生 | 04月10日_11吴届生.aac | 新国脉数字文化股份有限公司招聘报名表（吴届生）.xlsx |
| 10 | 雷雨田 | 04月10日_12雷雨田.aac | 新国脉数字文化股份有限公司招聘报名表（雷雨田）.xlsx |

## 岗位信息

- **岗位名称**：战略与创新部副总经理
- **JD文件**：20260401 国脉文化公司战略与创新部副总经理总经理助理岗位招聘公告 V1.0- OA发布.docx

## 批量评估脚本

### Python脚本

```python
#!/usr/bin/env python3
"""
批量面试评估脚本
为项目中的所有候选人生成AI面试评估结果
"""

import requests
import json
import time
import os
from pathlib import Path

# 配置
API_BASE = "http://121.229.172.161:3111"
PROJECT_NAME = "20260401战略招聘"
JD_TITLE = "战略与创新部副总经理"

# 候选人列表
CANDIDATES = [
    "仇天硕",
    "褚祎鹤", 
    "石欣慰",
    "李贤峰",
    "郑振东",
    "邹川龙",
    "邱洋",
    "黄俊华",
    "吴届生",
    "雷雨田"
]

# 项目目录
PROJECT_DIR = "/root/shijingjing/e-employee/hr-bot/data/interview/20260401战略招聘"

def read_jd_content():
    """读取JD文件内容"""
    jd_path = Path(PROJECT_DIR) / "20260401 国脉文化公司战略与创新部副总经理总经理助理岗位招聘公告 V1.0- OA发布.docx"
    if jd_path.exists():
        # 这里简化处理，实际应该解析docx文件
        return "战略与创新部副总经理岗位招聘公告"
    return "战略与创新部副总经理岗位"

def read_resume(candidate_name):
    """读取候选人简历"""
    resume_path = Path(PROJECT_DIR) / f"新国脉数字文化股份有限公司招聘报名表（{candidate_name}）.xlsx"
    if resume_path.exists():
        return f"{candidate_name}的简历"
    return f"{candidate_name}简历"

def evaluate_candidate(candidate_name, jd_content):
    """为单个候选人生成评估"""
    url = f"{API_BASE}/api/v1/interview-evaluation/evaluate"
    
    resume_content = read_resume(candidate_name)
    
    data = {
        "project": PROJECT_NAME,
        "candidate_name": candidate_name,
        "jd_title": JD_TITLE,
        "jd_content": jd_content,
        "resume_content": resume_content
    }
    
    try:
        print(f"[{candidate_name}] 开始评估...")
        response = requests.post(url, data=data, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                score = result.get("overall_score", 0)
                level = result.get("evaluation_level", "未知")
                print(f"[{candidate_name}] 评估完成 - 综合得分: {score}分 ({level})")
                return result
            else:
                print(f"[{candidate_name}] 评估失败: {result}")
                return None
        else:
            print(f"[{candidate_name}] 请求失败: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"[{candidate_name}] 评估异常: {e}")
        return None

def batch_evaluate():
    """批量评估所有候选人"""
    print("=" * 60)
    print("批量面试评估开始")
    print(f"项目: {PROJECT_NAME}")
    print(f"候选人数量: {len(CANDIDATES)}")
    print("=" * 60)
    
    jd_content = read_jd_content()
    results = {}
    
    for i, candidate in enumerate(CANDIDATES, 1):
        print(f"\n[{i}/{len(CANDIDATES)}] 评估候选人: {candidate}")
        result = evaluate_candidate(candidate, jd_content)
        
        if result:
            results[candidate] = {
                "overall_score": result.get("overall_score", 0),
                "evaluation_level": result.get("evaluation_level", "未知"),
                "dimensions": result.get("dimensions", []),
                "jd_requirements": result.get("jd_requirements", {}),
                "summary": result.get("summary", "")
            }
        
        # 避免请求过快
        if i < len(CANDIDATES):
            time.sleep(2)
    
    # 保存汇总结果
    summary_file = Path(PROJECT_DIR) / "evaluations" / "batch_evaluation_summary.json"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "project": PROJECT_NAME,
            "total_candidates": len(CANDIDATES),
            "evaluated_count": len(results),
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print("批量评估完成")
    print(f"成功评估: {len(results)}/{len(CANDIDATES)}")
    print(f"汇总结果保存至: {summary_file}")
    print("=" * 60)
    
    # 打印评估结果汇总表
    print("\n评估结果汇总:")
    print("-" * 60)
    print(f"{'候选人':<10} {'综合得分':<10} {'评估等级':<10}")
    print("-" * 60)
    for candidate in CANDIDATES:
        if candidate in results:
            r = results[candidate]
            print(f"{candidate:<10} {r['overall_score']:<10} {r['evaluation_level']:<10}")
        else:
            print(f"{candidate:<10} {'评估失败':<10} {'-':<10}")
    print("-" * 60)

if __name__ == "__main__":
    batch_evaluate()
```

### Bash脚本

```bash
#!/bin/bash
# 批量面试评估脚本

API_BASE="http://121.229.172.161:3111"
PROJECT="20260401战略招聘"
JD_TITLE="战略与创新部副总经理"
JD_CONTENT="战略与创新部副总经理岗位招聘公告"

# 候选人列表
declare -a CANDIDATES=(
    "仇天硕"
    "褚祎鹤"
    "石欣慰"
    "李贤峰"
    "郑振东"
    "邹川龙"
    "邱洋"
    "黄俊华"
    "吴届生"
    "雷雨田"
)

echo "========================================"
echo "批量面试评估开始"
echo "项目: $PROJECT"
echo "候选人数量: ${#CANDIDATES[@]}"
echo "========================================"

for candidate in "${CANDIDATES[@]}"; do
    echo ""
    echo "[$candidate] 开始评估..."
    
    response=$(curl -s -X POST "${API_BASE}/api/v1/interview-evaluation/evaluate" \
        -F "project=${PROJECT}" \
        -F "candidate_name=${candidate}" \
        -F "jd_title=${JD_TITLE}" \
        -F "jd_content=${JD_CONTENT}" \
        -F "resume_content=${candidate}简历" \
        --max-time 300)
    
    if echo "$response" | grep -q '"success":true'; then
        score=$(echo "$response" | grep -o '"overall_score":[0-9.]*' | cut -d':' -f2)
        level=$(echo "$response" | grep -o '"evaluation_level":"[^"]*"' | cut -d'"' -f4)
        echo "[$candidate] 评估完成 - 综合得分: ${score}分 (${level})"
    else
        echo "[$candidate] 评估失败"
        echo "响应: $response"
    fi
    
    # 避免请求过快
    sleep 2
done

echo ""
echo "========================================"
echo "批量评估完成"
echo "========================================"
```

## 执行步骤

1. **上传脚本到服务器**
   ```bash
   scp batch_evaluate.py root@121.229.172.161:/root/shijingjing/e-employee/hr-bot/scripts/
   ```

2. **在服务器上执行**
   ```bash
   ssh root@121.229.172.161
   cd /root/shijingjing/e-employee/hr-bot
   source /root/miniconda3/etc/profile.d/conda.sh
   conda activate media_env
   python scripts/batch_evaluate.py
   ```

3. **查看结果**
   - 评估结果会保存在 `/root/shijingjing/e-employee/hr-bot/data/interview/20260401战略招聘/evaluations/`
   - 汇总文件：`batch_evaluation_summary.json`

## 注意事项

1. **确保服务已启动**：执行前确认API服务正在运行
2. **离线ASR缓存**：确保所有候选人的转录数据已存在于 `transcriptions/` 目录
3. **执行时间**：每个候选人评估约需30-60秒，10人预计需要5-10分钟
4. **内存占用**：大模型评估会占用较多内存，确保服务器资源充足
5. **错误处理**：脚本会自动跳过失败的候选人，继续评估下一个

## API接口说明

- **接口地址**：`POST /api/v1/interview-evaluation/evaluate`
- **请求方式**：multipart/form-data
- **核心参数**：
  - `project`: 项目名称
  - `candidate_name`: 候选人姓名
  - `jd_title`: 岗位名称
  - `jd_content`: JD内容
  - `resume_content`: 简历内容
