---
name: "batch-asr-generation"
description: "批量生成候选人ASR语音转文本数据。Invoke when user needs to batch transcribe audio files for multiple candidates using local ASR service."
---

# 批量生成ASR语音转文本数据

## 功能说明
调用本地8003端口的ASR服务，将候选人的面试录音文件转换为文本，并保存到tras目录。

## 执行步骤

### 步骤1：检查ASR服务状态
```bash
ssh root@121.229.172.161 "curl -s http://localhost:8003/health || echo 'ASR服务未启动'"
```

### 步骤2：创建批量ASR脚本
脚本路径：`/root/shijingjing/e-employee/hr-bot/scripts/batch_asr_transcribe.py`

### 步骤3：执行批量ASR转录
```bash
ssh root@121.229.172.161 "cd /root/shijingjing/e-employee/hr-bot && source /root/miniconda3/bin/activate media_env && python scripts/batch_asr_transcribe.py"
```

## 音频文件映射关系

| 文件名 | 候选人姓名 |
|--------|-----------|
| 04月10日_1仇天硕.aac | 仇天硕 |
| 04月10日_2褚祎鹤.aac | 褚祎鹤 |
| 04月10日_4石欣慰.aac | 石欣慰 |
| 04月10日_5李贤峰.aac | 李贤峰 |
| 04月10日_6郑振东.aac | 郑振东 |
| 04月10日_7邹川龙.aac | 邹川龙 |
| 04月10日_8邱洋.aac | 邱洋 |
| 04月10日_10黄俊华.aac | 黄俊华 |
| 04月10日_11吴届生.aac | 吴届生 |
| 04月10日_12雷雨田.aac | 雷雨田 |

## 输出格式
转录结果保存到：`/root/shijingjing/e-employee/hr-bot/data/interview/20260401战略招聘/tras/{候选人姓名}.json`

JSON格式：
```json
{
  "candidate_name": "候选人姓名",
  "transcription": "转录文本内容",
  "audio_file": "原始音频文件名",
  "processed_at": "处理时间"
}
```

## 注意事项
1. ASR服务必须在8003端口正常运行
2. 每个音频文件转录需要1-3分钟
3. 转录结果会覆盖tras目录下的同名文件
4. 确保音频文件格式为AAC或MP3
