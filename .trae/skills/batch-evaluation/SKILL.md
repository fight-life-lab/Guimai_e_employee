---
name: "batch-evaluation"
description: "批量生成候选人AI面试评估报告。Invoke when user needs to batch generate AI evaluation results for multiple candidates, or when regenerating evaluation results with updated prompts."
---

# 批量生成AI面试评估报告

## 执行步骤

### 步骤1：上传更新后的后端代码
```bash
scp /Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/app/api/interview_evaluation_routes.py root@121.229.172.161:/root/shijingjing/e-employee/hr-bot/app/api/interview_evaluation_routes.py
```

### 步骤2：重启后端服务
```bash
ssh root@121.229.172.161 "cd /root/shijingjing/e-employee/hr-bot && source /root/miniconda3/bin/activate media_env && pkill -f uvicorn; sleep 2; nohup uvicorn app.main:app --host 0.0.0.0 --port 3111 --reload > /tmp/hr-bot.log 2>&1 &"
```

等待5秒后验证服务是否启动：
```bash
ssh root@121.229.172.161 "curl -s http://localhost:3111/docs | head -5"
```

### 步骤3：清除评估缓存
```bash
ssh root@121.229.172.161 "rm -rf /root/shijingjing/e-employee/hr-bot/data/interview/20260401战略招聘/evaluations/* && rm -rf /root/shijingjing/e-employee/hr-bot/data/interview/20260401战略招聘/eval/* && echo '缓存已清除'"
```

### 步骤4：执行批量生成脚本
```bash
ssh root@121.229.172.161 "cd /root/shijingjing/e-employee/hr-bot && source /root/miniconda3/bin/activate media_env && python scripts/batch_generate_evaluation.py"
```

## 候选人列表
- 仇天硕
- 吴届生
- 李贤峰
- 石欣慰
- 褚祎鹤
- 邱洋
- 邹川龙
- 郑振东
- 雷雨田
- 黄俊华

## 注意事项
1. 必须先重启后端服务，使新的Prompt和分数调整逻辑生效
2. 必须清除evaluations和eval目录的缓存，确保使用新的评分逻辑
3. 批量生成大约需要15-20分钟（每个候选人约1-2分钟）
4. 评估结果会保存到 `/root/shijingjing/e-employee/hr-bot/data/interview/20260401战略招聘/eval/` 目录
