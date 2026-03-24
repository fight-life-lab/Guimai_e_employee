#!/usr/bin/env python3
"""
面试录音转录脚本
将音频/视频文件转录为文本并存储
"""

import os
import json
import whisper
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# 配置路径
AUDIO_DIR = Path("/root/shijingjing/e-employee/hr-bot/data/面试录音")
OUTPUT_DIR = Path("/root/shijingjing/e-employee/hr-bot/data/transcriptions")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 支持的音频/视频格式
SUPPORTED_EXTENSIONS = {'.mp4', '.aac', '.mp3', '.wav', '.m4a', '.flac', '.ogg', '.wma'}


def get_audio_files(directory: Path) -> List[Path]:
    """获取目录下所有支持的音频/视频文件"""
    audio_files = []
    if directory.exists():
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                audio_files.append(file_path)
    return sorted(audio_files)


def transcribe_audio(file_path: Path, model) -> Dict:
    """
    使用 Whisper 转录音频文件
    """
    print(f"正在转录: {file_path.name}")
    start_time = datetime.now()

    try:
        # 执行转录
        result = model.transcribe(
            str(file_path),
            language="zh",  # 指定中文
            task="transcribe",
            verbose=False
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 构建转录结果
        transcription_data = {
            "file_name": file_path.name,
            "file_path": str(file_path),
            "candidate_name": file_path.stem,  # 使用文件名（不含扩展名）作为候选人姓名
            "transcription": result["text"],
            "segments": [
                {
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"]
                }
                for segment in result["segments"]
            ],
            "language": result.get("language", "zh"),
            "processed_at": end_time.isoformat(),
            "processing_time_seconds": duration
        }

        print(f"  ✓ 转录完成，耗时 {duration:.2f} 秒，文本长度: {len(result['text'])} 字符")
        return transcription_data

    except Exception as e:
        print(f"  ✗ 转录失败: {str(e)}")
        return {
            "file_name": file_path.name,
            "candidate_name": file_path.stem,
            "error": str(e),
            "processed_at": datetime.now().isoformat()
        }


def save_transcription(data: Dict, output_dir: Path):
    """保存转录结果到 JSON 文件"""
    candidate_name = data.get("candidate_name", "unknown")
    output_file = output_dir / f"{candidate_name}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  ✓ 已保存到: {output_file}")
    return output_file


def save_all_transcriptions(all_data: List[Dict], output_dir: Path):
    """保存所有转录结果的汇总文件"""
    summary_file = output_dir / "_all_transcriptions.json"

    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_files": len(all_data),
        "successful": len([d for d in all_data if "error" not in d]),
        "failed": len([d for d in all_data if "error" in d]),
        "transcriptions": all_data
    }

    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 汇总文件已保存到: {summary_file}")
    return summary_file


def main():
    """主函数"""
    print("=" * 60)
    print("面试录音转录工具")
    print("=" * 60)

    # 加载 Whisper 模型
    print("\n[1/4] 加载 Whisper 模型...")
    model = whisper.load_model("base")  # 使用 base 模型，平衡速度和准确度
    print("✓ 模型加载完成")

    # 获取音频文件列表
    print(f"\n[2/4] 扫描音频文件目录: {AUDIO_DIR}")
    audio_files = get_audio_files(AUDIO_DIR)
    print(f"✓ 找到 {len(audio_files)} 个音频/视频文件")

    if not audio_files:
        print("✗ 未找到任何音频文件，退出")
        return

    for i, f in enumerate(audio_files, 1):
        print(f"  {i}. {f.name}")

    # 执行转录
    print(f"\n[3/4] 开始转录...")
    all_results = []

    for i, audio_file in enumerate(audio_files, 1):
        print(f"\n[{i}/{len(audio_files)}] ", end="")
        result = transcribe_audio(audio_file, model)
        all_results.append(result)

        # 保存单个转录结果
        if "error" not in result:
            save_transcription(result, OUTPUT_DIR)

    # 保存汇总
    print(f"\n[4/4] 保存转录结果...")
    save_all_transcriptions(all_results, OUTPUT_DIR)

    # 输出统计信息
    successful = len([d for d in all_results if "error" not in d])
    failed = len([d for d in all_results if "error" in d])

    print("\n" + "=" * 60)
    print("转录完成!")
    print("=" * 60)
    print(f"总计文件: {len(all_results)}")
    print(f"成功: {successful}")
    print(f"失败: {failed}")
    print(f"输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
