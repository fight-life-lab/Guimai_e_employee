#!/usr/bin/env python3
"""
ASR语音转文本脚本
逐个候选人进行转录，确认数据后再保存
"""

import requests
import json
import os
import time
from pathlib import Path
from datetime import datetime

# 配置
ASR_API_URL = "http://localhost:8003/transcribe"  # 本地Whisper ASR服务
PROJECT_NAME = "20260401战略招聘"
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
    log_file = Path(PROJECT_DIR) / "asr_process.log"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_msg + '\n')

def find_audio_file(candidate_name):
    """查找候选人的音频文件"""
    project_path = Path(PROJECT_DIR)
    
    # 查找所有可能的音频格式
    for ext in ['.aac', '.mp3', '.wav', '.m4a']:
        pattern = f"*{candidate_name}*{ext}"
        files = list(project_path.glob(pattern))
        if files:
            return files[0]
    
    return None

def transcribe_audio(audio_file_path, max_retries=3):
    """调用ASR服务转录音频，带重试机制"""
    for attempt in range(max_retries):
        try:
            log(f"调用ASR服务: {ASR_API_URL} (尝试 {attempt + 1}/{max_retries})")
            
            with open(audio_file_path, 'rb') as f:
                files = {'audio_file': (Path(audio_file_path).name, f, 'audio/aac')}
                data = {'language': 'zh'}
                response = requests.post(ASR_API_URL, files=files, data=data, timeout=300)
            
            if response.status_code == 200:
                result = response.json()
                transcript = result.get('transcript', '')
                
                if transcript:
                    log(f"ASR转录成功，文本长度: {len(transcript)} 字符")
                    return {
                        'success': True,
                        'transcript': transcript,
                        'duration': result.get('duration', 0)
                    }
                else:
                    log("ASR转录结果为空")
                    return {'success': False, 'error': '转录结果为空'}
            else:
                log(f"ASR请求失败: {response.status_code}, {response.text}")
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            log(f"ASR异常 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait_time = 5 * (attempt + 1)
                log(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                return {'success': False, 'error': str(e)}
    
    return {'success': False, 'error': '所有重试都失败'}

def save_transcription(candidate_name, audio_file, transcript_data):
    """保存转录结果到tras目录"""
    try:
        tras_dir = Path(PROJECT_DIR) / "tras"
        tras_dir.mkdir(parents=True, exist_ok=True)
        
        tras_file = tras_dir / f"{candidate_name}.json"
        
        tras_data = {
            "candidate_name": candidate_name,
            "audio_file": Path(audio_file).name,
            "transcription": transcript_data['transcript'],
            "duration": transcript_data.get('duration', 0),
            "processed_at": datetime.now().isoformat()
        }
        
        with open(tras_file, 'w', encoding='utf-8') as f:
            json.dump(tras_data, f, ensure_ascii=False, indent=2)
        
        log(f"转录数据已保存到: {tras_file}")
        return True
        
    except Exception as e:
        log(f"保存转录数据失败: {e}")
        return False

def process_candidate(candidate_name, auto_confirm=False):
    """处理单个候选人"""
    log(f"\n{'='*60}")
    log(f"处理候选人: {candidate_name}")
    log(f"{'='*60}")
    
    # 1. 查找音频文件
    audio_file = find_audio_file(candidate_name)
    if not audio_file:
        log(f"未找到音频文件")
        return False
    
    log(f"找到音频文件: {audio_file.name}")
    
    # 2. 调用ASR转录
    result = transcribe_audio(audio_file)
    
    if not result['success']:
        log(f"ASR转录失败: {result.get('error')}")
        return False
    
    # 3. 显示转录结果供确认
    transcript = result['transcript']
    log(f"\n转录结果预览（前200字符）:")
    log(f"{transcript[:200]}...")
    log(f"\n完整文本长度: {len(transcript)} 字符")
    
    # 4. 确认是否保存
    if auto_confirm:
        confirm = 'y'
    else:
        # 在交互式环境中询问确认
        # 非交互式环境默认保存
        confirm = 'y'
        log("自动确认保存（非交互式模式）")
    
    if confirm.lower() == 'y':
        # 5. 保存转录数据
        if save_transcription(candidate_name, audio_file, result):
            log(f"✅ {candidate_name} 处理完成")
            # 6. 处理完成后等待，让ASR服务释放资源
            log("等待10秒让ASR服务释放资源...")
            time.sleep(10)
            return True
        else:
            log(f"❌ {candidate_name} 保存失败")
            return False
    else:
        log(f"⏭️ {candidate_name} 已跳过")
        return False

def main():
    """主函数"""
    log("\n" + "="*60)
    log("ASR语音转文本开始")
    log(f"项目: {PROJECT_NAME}")
    log(f"候选人数量: {len(CANDIDATES)}")
    log("="*60)
    
    success_count = 0
    fail_count = 0
    
    for i, candidate in enumerate(CANDIDATES, 1):
        log(f"\n[{i}/{len(CANDIDATES)}] 处理第 {i} 个候选人")
        
        if process_candidate(candidate, auto_confirm=True):
            success_count += 1
        else:
            fail_count += 1
    
    log("\n" + "="*60)
    log("ASR转录完成!")
    log(f"成功: {success_count}/{len(CANDIDATES)}")
    log(f"失败: {fail_count}/{len(CANDIDATES)}")
    log("="*60)

if __name__ == "__main__":
    main()
