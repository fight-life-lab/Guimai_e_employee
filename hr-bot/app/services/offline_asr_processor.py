#!/usr/bin/env python3
"""
离线批量ASR处理脚本
将项目目录下的所有录音文件进行ASR转录并缓存
缓存结构：data/interview/{项目名}/transcriptions/{候选人姓名}/{文件名}.json
"""

import os
import sys
import json
import asyncio
import aiohttp
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import requests

# 配置
WHISPER_API_URL = "http://localhost:8003/transcribe"
BASE_DIR = Path("/root/shijingjing/e-employee/hr-bot/data/interview")
SUPPORTED_AUDIO_FORMATS = {'.aac', '.mp3', '.wav', '.m4a', '.mp4'}

# 日志文件路径（在BASE_DIR下）
LOG_FILE = BASE_DIR / "asr_processing.log"

# 配置日志 - 同时输出到控制台和文件
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8', mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

logger.info(f"日志文件位置: {LOG_FILE}")


def extract_candidate_name(filename: str) -> str:
    """从文件名提取候选人姓名"""
    # 格式1: 04月10日_10黄俊华.aac
    # 格式2: 新国脉数字文化股份有限公司招聘报名表（仇天硕）.xlsx
    try:
        # 尝试匹配录音文件名格式
        if '_' in filename:
            name_part = filename.split('_')[-1]
            name = name_part.split('.')[0]
            # 移除数字前缀
            for i, char in enumerate(name):
                if not char.isdigit():
                    return name[i:]
        
        # 尝试匹配报名表文件名格式
        if '（' in filename and '）' in filename:
            start = filename.find('（') + 1
            end = filename.find('）')
            return filename[start:end]
        
        return filename.split('.')[0]
    except:
        return filename


def get_cache_path(project_name: str, candidate_name: str, filename: str) -> Path:
    """获取缓存文件路径"""
    cache_dir = BASE_DIR / project_name / "transcriptions" / candidate_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{filename}.json"


def load_cached_transcription(cache_path: Path) -> Optional[Dict]:
    """加载缓存的转录结果"""
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"  ✓ 使用缓存: {cache_path.name}")
                return data
        except Exception as e:
            logger.warning(f"  ⚠ 读取缓存失败: {e}")
    return None


def save_cached_transcription(cache_path: Path, data: Dict):
    """保存转录结果到缓存"""
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"  ✓ 已缓存: {cache_path}")
    except Exception as e:
        logger.error(f"  ✗ 保存缓存失败: {e}")


async def transcribe_audio_file(audio_path: Path) -> Tuple[str, List[Dict]]:
    """调用Whisper API转录音频文件"""
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('audio_file',
                         open(audio_path, 'rb'),
                         filename=audio_path.name,
                         content_type='audio/aac')
            data.add_field('language', 'zh')
            
            async with session.post(
                WHISPER_API_URL, 
                data=data, 
                timeout=aiohttp.ClientTimeout(total=600)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    transcript = result.get('transcript', '')
                    segments = result.get('segments', [])
                    return transcript, segments
                else:
                    error_text = await response.text()
                    raise Exception(f"API错误 {response.status}: {error_text}")
    except Exception as e:
        raise Exception(f"转录失败: {e}")


async def process_single_audio(
    project_name: str,
    audio_path: Path,
    force_retranscribe: bool = False
) -> Dict:
    """处理单个音频文件"""
    filename = audio_path.name
    candidate_name = extract_candidate_name(filename)
    cache_path = get_cache_path(project_name, candidate_name, filename)
    
    logger.info(f"处理: {filename} -> 候选人: {candidate_name}")
    
    # 检查缓存
    if not force_retranscribe:
        cached = load_cached_transcription(cache_path)
        if cached:
            return {
                "success": True,
                "filename": filename,
                "candidate_name": candidate_name,
                "transcription": cached.get("transcription", ""),
                "cached": True,
                "cache_path": str(cache_path)
            }
    
    # 执行转录
    try:
        start_time = datetime.now()
        transcript, segments = await transcribe_audio_file(audio_path)
        duration = (datetime.now() - start_time).total_seconds()
        
        # 构建转录数据
        transcription_data = {
            "file_name": filename,
            "candidate_name": candidate_name,
            "transcription": transcript,
            "segments": segments,
            "language": "zh",
            "processed_at": datetime.now().isoformat(),
            "processing_time_seconds": duration,
            "source": "whisper_api"
        }
        
        # 保存缓存
        save_cached_transcription(cache_path, transcription_data)
        
        logger.info(f"  ✓ 转录完成: {len(transcript)} 字符, 耗时 {duration:.2f}秒")
        
        return {
            "success": True,
            "filename": filename,
            "candidate_name": candidate_name,
            "transcription": transcript,
            "cached": False,
            "cache_path": str(cache_path),
            "processing_time": duration
        }
        
    except Exception as e:
        logger.error(f"  ✗ 转录失败: {e}")
        return {
            "success": False,
            "filename": filename,
            "candidate_name": candidate_name,
            "error": str(e)
        }


async def process_project(
    project_name: str,
    force_retranscribe: bool = False
) -> Dict:
    """处理整个项目的所有音频文件"""
    project_dir = BASE_DIR / project_name
    
    if not project_dir.exists():
        logger.error(f"项目不存在: {project_name}")
        return {"success": False, "error": f"项目不存在: {project_name}"}
    
    # 获取所有音频文件
    audio_files = []
    for ext in SUPPORTED_AUDIO_FORMATS:
        audio_files.extend(project_dir.glob(f"*{ext}"))
    
    logger.info(f"=" * 60)
    logger.info(f"开始处理项目: {project_name}")
    logger.info(f"找到 {len(audio_files)} 个音频文件")
    logger.info(f"=" * 60)
    
    results = []
    success_count = 0
    cached_count = 0
    failed_count = 0
    
    for i, audio_path in enumerate(audio_files, 1):
        logger.info(f"\n[{i}/{len(audio_files)}] {audio_path.name}")
        
        result = await process_single_audio(project_name, audio_path, force_retranscribe)
        results.append(result)
        
        if result.get("success"):
            if result.get("cached"):
                cached_count += 1
            else:
                success_count += 1
        else:
            failed_count += 1
    
    # 保存处理汇总
    summary = {
        "project": project_name,
        "processed_at": datetime.now().isoformat(),
        "total_files": len(audio_files),
        "success": success_count,
        "cached": cached_count,
        "failed": failed_count,
        "results": results
    }
    
    summary_path = BASE_DIR / project_name / "transcriptions" / "_processing_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n" + "=" * 60)
    logger.info(f"处理完成!")
    logger.info(f"  总计: {len(audio_files)}")
    logger.info(f"  新转录: {success_count}")
    logger.info(f"  使用缓存: {cached_count}")
    logger.info(f"  失败: {failed_count}")
    logger.info(f"  汇总文件: {summary_path}")
    logger.info(f"=" * 60)
    
    return summary


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='离线批量ASR处理脚本')
    parser.add_argument('project', help='项目名称，如：20260401战略招聘')
    parser.add_argument('--force', '-f', action='store_true', help='强制重新转录（忽略缓存）')
    
    args = parser.parse_args()
    
    # 运行异步处理
    result = asyncio.run(process_project(args.project, args.force))
    
    # 返回退出码
    if result.get("failed", 0) > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
