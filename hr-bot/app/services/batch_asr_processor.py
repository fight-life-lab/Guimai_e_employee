#!/usr/bin/env python3
"""
批量面试录音ASR处理服务
用于20260401战略招聘项目的录音转录和缓存
"""

import os
import json
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置
WHISPER_API_URL = "http://localhost:8003/transcribe"
PROJECT_DIR = Path("/root/shijingjing/e-employee/hr-bot/data/interview/20260401战略招聘")
CACHE_DIR = Path("/root/shijingjing/e-employee/hr-bot/data/interview/20260401战略招聘/transcriptions")
SUPPORTED_AUDIO_FORMATS = {'.aac', '.mp3', '.wav', '.m4a', '.mp4'}


class BatchASRProcessor:
    """批量ASR处理器"""
    
    def __init__(self, project_dir: Path = PROJECT_DIR, cache_dir: Path = CACHE_DIR):
        self.project_dir = project_dir
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def get_audio_files(self) -> List[Path]:
        """获取项目中所有音频文件"""
        audio_files = []
        if self.project_dir.exists():
            for file_path in self.project_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_AUDIO_FORMATS:
                    audio_files.append(file_path)
        return sorted(audio_files)
    
    def get_cached_transcription(self, file_name: str) -> Optional[Dict]:
        """检查是否有缓存的转录结果"""
        cache_file = self.cache_dir / f"{file_name}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"读取缓存文件失败 {cache_file}: {e}")
        return None
    
    async def transcribe_audio(self, file_path: Path) -> Dict:
        """调用Whisper API转录音频文件"""
        file_name = file_path.name
        
        # 检查缓存
        cached = self.get_cached_transcription(file_name)
        if cached:
            logger.info(f"[ASR] 使用缓存: {file_name}")
            return cached
        
        logger.info(f"[ASR] 开始转录: {file_name}")
        start_time = datetime.now()
        
        try:
            async with aiohttp.ClientSession() as session:
                # 准备文件上传
                data = aiohttp.FormData()
                data.add_field('audio_file',
                             open(file_path, 'rb'),
                             filename=file_name,
                             content_type='audio/aac')
                
                async with session.post(WHISPER_API_URL, data=data, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # 构建转录结果
                        transcription_data = {
                            "file_name": file_name,
                            "file_path": str(file_path),
                            "candidate_name": self._extract_candidate_name(file_name),
                            "transcription": result.get("text", ""),
                            "segments": result.get("segments", []),
                            "language": result.get("language", "zh"),
                            "processed_at": datetime.now().isoformat(),
                            "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                            "source": "whisper_api"
                        }
                        
                        # 保存缓存
                        self._save_cache(file_name, transcription_data)
                        
                        logger.info(f"[ASR] 转录完成: {file_name}, 耗时 {(datetime.now() - start_time).total_seconds():.2f}s")
                        return transcription_data
                    else:
                        error_text = await response.text()
                        raise Exception(f"API返回错误: {response.status}, {error_text}")
                        
        except Exception as e:
            logger.error(f"[ASR] 转录失败 {file_name}: {e}")
            return {
                "file_name": file_name,
                "candidate_name": self._extract_candidate_name(file_name),
                "error": str(e),
                "processed_at": datetime.now().isoformat()
            }
    
    def _extract_candidate_name(self, file_name: str) -> str:
        """从文件名中提取候选人姓名"""
        # 文件名格式: 04月10日_10黄俊华.aac
        try:
            # 移除日期前缀和扩展名
            name_part = file_name.split('_')[-1]  # 10黄俊华.aac
            name = name_part.split('.')[0]  # 10黄俊华
            # 移除数字前缀
            for i, char in enumerate(name):
                if not char.isdigit():
                    return name[i:]
            return name
        except:
            return file_name
    
    def _save_cache(self, file_name: str, data: Dict):
        """保存转录结果到缓存"""
        cache_file = self.cache_dir / f"{file_name}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[ASR] 缓存已保存: {cache_file}")
        except Exception as e:
            logger.error(f"[ASR] 保存缓存失败: {e}")
    
    async def process_all(self) -> List[Dict]:
        """处理所有音频文件"""
        audio_files = self.get_audio_files()
        logger.info(f"[ASR] 发现 {len(audio_files)} 个音频文件")
        
        results = []
        for file_path in audio_files:
            result = await self.transcribe_audio(file_path)
            results.append(result)
        
        # 保存汇总结果
        self._save_summary(results)
        
        return results
    
    def _save_summary(self, results: List[Dict]):
        """保存处理汇总"""
        summary_file = self.cache_dir / "_processing_summary.json"
        summary = {
            "project": "20260401战略招聘",
            "processed_at": datetime.now().isoformat(),
            "total_files": len(results),
            "successful": len([r for r in results if "error" not in r]),
            "failed": len([r for r in results if "error" in r]),
            "results": results
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[ASR] 汇总结果已保存: {summary_file}")


async def main():
    """主函数 - 用于命令行执行"""
    processor = BatchASRProcessor()
    results = await processor.process_all()
    
    # 打印结果
    print("\n" + "="*60)
    print("ASR处理完成")
    print("="*60)
    
    success_count = len([r for r in results if "error" not in r])
    failed_count = len([r for r in results if "error" in r])
    
    print(f"成功: {success_count} 个")
    print(f"失败: {failed_count} 个")
    print(f"缓存目录: {CACHE_DIR}")
    
    for result in results:
        status = "✓" if "error" not in result else "✗"
        print(f"{status} {result['file_name']}: {result.get('candidate_name', 'Unknown')}")


if __name__ == "__main__":
    asyncio.run(main())
