#!/usr/bin/env python3
"""
员工招聘批量面试评估脚本 - 离线两阶段版
阶段1: 使用本地 Whisper 服务批量转录录音
阶段2: 调用 AI 批量评估
"""

import requests
import json
import time
import os
import re
from pathlib import Path

# 配置
API_BASE = "http://localhost:3111"
WHISPER_API_URL = "http://localhost:8003/transcribe"
PROJECT_NAME = "20260420-薪酬招聘"
PROJECT_DIR = "/root/shijingjing/e-employee/hr-bot/data/interview/20260420-薪酬招聘"


def extract_candidate_name(filename: str) -> str:
    """从文件名提取候选人姓名"""
    name = filename.replace('！', '').replace('!', '').replace('_', '').replace('-', '')
    name = re.sub(r'\s*\d+年以上?$', '', name)
    name = re.sub(r'\s*\d+年$', '', name)
    name = name.replace('.pdf', '').replace('.mp3', '').replace('.aac', '').replace('.wav', '')
    return name.strip()


def get_candidates_from_directory():
    """从目录结构扫描候选人列表"""
    candidates = []
    resume_dir = Path(PROJECT_DIR) / "简历"
    audio_dir = Path(PROJECT_DIR) / "录音"
    
    if not audio_dir.exists():
        print(f"[警告] 录音目录不存在: {audio_dir}")
        return candidates
    
    for audio_file in sorted(audio_dir.glob("*.mp3")):
        if audio_file.name.startswith('._'):
            continue
        candidate_name = extract_candidate_name(audio_file.name)
        resume_file = None
        for rf in resume_dir.glob("*.pdf"):
            if rf.name.startswith('._'):
                continue
            if extract_candidate_name(rf.name) == candidate_name:
                resume_file = rf.name
                break
        candidates.append({
            "name": candidate_name,
            "audio_file": audio_file.name,
            "audio_path": str(audio_file),
            "resume_file": resume_file or ""
        })
    
    return candidates


def transcribe_audio(audio_path: str) -> str:
    """使用本地 Whisper 服务转录音频"""
    try:
        print(f"  开始上传音频文件: {os.path.basename(audio_path)}")
        print(f"  文件大小: {os.path.getsize(audio_path) / 1024 / 1024:.1f} MB")
        with open(audio_path, 'rb') as f:
            files = {'audio_file': (os.path.basename(audio_path), f, 'audio/mp3')}
            data = {'language': 'zh'}
            print(f"  正在调用 Whisper API (超时600秒)...")
            response = requests.post(WHISPER_API_URL, files=files, data=data, timeout=600)
        if response.status_code == 200:
            result = response.json()
            transcript = result.get('transcript', '')
            print(f"  Whisper API 返回成功")
            return transcript
        else:
            print(f"  Whisper转录失败: HTTP {response.status_code}")
            print(f"  响应内容: {response.text[:200]}")
            return ""
    except requests.exceptions.Timeout:
        print(f"  Whisper转录超时: 请求超过1800秒未完成")
        return ""
    except Exception as e:
        print(f"  Whisper转录异常: {type(e).__name__}: {e}")
        return ""


def save_transcription(candidate_name: str, transcript: str):
    """保存转录结果"""
    trans_dir = Path(PROJECT_DIR) / "transcriptions"
    trans_dir.mkdir(parents=True, exist_ok=True)
    cache_file = trans_dir / f"{candidate_name}.json"
    cache_data = {
        "candidate_name": candidate_name,
        "transcription": transcript,
        "processed_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    }
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)


def load_transcription(candidate_name: str) -> str:
    """加载已有转录缓存"""
    cache_file = Path(PROJECT_DIR) / "transcriptions" / f"{candidate_name}.json"
    if cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("transcription", "")
    return ""


def read_jd_content():
    """读取JD文件内容"""
    jd_path = Path(PROJECT_DIR) / "JD.docx"
    if not jd_path.exists():
        jd_path = Path(PROJECT_DIR) / "人力资源部-薪酬管理岗JD.docx"
    if jd_path.exists():
        try:
            from docx import Document
            doc = Document(str(jd_path))
            return '\n'.join([para.text for para in doc.paragraphs])
        except Exception:
            return "薪酬管理岗岗位说明"
    return "薪酬管理岗岗位说明"


def read_resume_content(candidate_name: str) -> str:
    """读取候选人简历内容"""
    resume_dir = Path(PROJECT_DIR) / "简历"
    for resume_file in resume_dir.glob("*.pdf"):
        if resume_file.name.startswith('._'):
            continue
        if extract_candidate_name(resume_file.name) == candidate_name:
            try:
                import fitz
                with fitz.open(str(resume_file)) as doc:
                    return '\n'.join([page.get_text() for page in doc])
            except Exception:
                return f"{candidate_name}的简历"
    return f"{candidate_name}的简历"


def evaluate_candidate(candidate_name: str, jd_content: str, resume_content: str, transcript: str):
    """调用AI评估接口"""
    url = f"{API_BASE}/api/v1/employee-recruitment-evaluation/evaluate"
    data = {
        "project": PROJECT_NAME,
        "candidate_name": candidate_name,
        "jd_content": jd_content,
        "resume_content": resume_content,
        "transcript_content": transcript
    }
    try:
        response = requests.post(url, data=data, timeout=300)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                return result.get("evaluation")
        print(f"  评估失败: {response.status_code}")
        return None
    except Exception as e:
        print(f"  评估异常: {e}")
        return None


def stage1_transcribe(candidates):
    """阶段1: 批量转录"""
    print("\n" + "=" * 60)
    print("阶段1: 批量音频转录 (Whisper)")
    print("=" * 60)
    
    for i, c in enumerate(candidates, 1):
        print(f"\n[{i}/{len(candidates)}] 转录: {c['name']}")
        
        # 检查缓存
        cached = load_transcription(c['name'])
        if cached:
            c['transcript'] = cached
            print(f"  [缓存命中] 已存在转录结果 ({len(cached)} 字)")
            continue
        
        print(f"  文件: {c['audio_file']}")
        transcript = transcribe_audio(c['audio_path'])
        
        if transcript:
            c['transcript'] = transcript
            save_transcription(c['name'], transcript)
            print(f"  转录完成 ({len(transcript)} 字)")
        else:
            c['transcript'] = ""
            print(f"  转录失败")
        
        time.sleep(1)


def stage2_evaluate(candidates):
    """阶段2: 批量AI评估"""
    print("\n" + "=" * 60)
    print("阶段2: 批量AI评估 (Qwen3-235B)")
    print("=" * 60)
    
    jd_content = read_jd_content()
    print(f"JD内容长度: {len(jd_content)} 字符")
    
    results = {}
    
    for i, c in enumerate(candidates, 1):
        print(f"\n[{i}/{len(candidates)}] 评估: {c['name']}")
        
        if not c.get('transcript'):
            print(f"  [跳过] 无转录文本")
            continue
        
        resume_content = read_resume_content(c['name'])
        evaluation = evaluate_candidate(c['name'], jd_content, resume_content, c['transcript'])
        
        if evaluation:
            results[c['name']] = {
                "overall_score": evaluation.get("overall_score", 0),
                "evaluation_level": evaluation.get("evaluation_level", "未知"),
                "dimensions": evaluation.get("dimensions", []),
                "summary": evaluation.get("summary", ""),
                "strengths": evaluation.get("strengths", []),
                "weaknesses": evaluation.get("weaknesses", []),
                "salary_match": evaluation.get("salary_match", {})
            }
            score = evaluation.get("overall_score", 0)
            level = evaluation.get("evaluation_level", "")
            print(f"  评估完成 - {score}分 ({level})")
        else:
            print(f"  评估失败")
        
        if i < len(candidates):
            time.sleep(3)
    
    return results


def save_results(candidates, results):
    """保存结果"""
    eval_dir = Path(PROJECT_DIR) / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存汇总
    summary_file = eval_dir / "batch_evaluation_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "project": PROJECT_NAME,
            "total_candidates": len(candidates),
            "transcribed_count": sum(1 for c in candidates if c.get('transcript')),
            "evaluated_count": len(results),
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    # 打印汇总表
    print("\n" + "=" * 60)
    print("评估结果汇总")
    print("=" * 60)
    print(f"{'排名':<6} {'候选人':<10} {'综合得分':<10} {'评估等级':<10}")
    print("-" * 60)
    
    sorted_results = sorted(results.items(), key=lambda x: x[1]['overall_score'], reverse=True)
    for i, (name, r) in enumerate(sorted_results, 1):
        icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        print(f"{icon:<6} {name:<10} {r['overall_score']:<10} {r['evaluation_level']:<10}")
    
    print("-" * 60)
    if results:
        avg = sum(r['overall_score'] for r in results.values()) / len(results)
        print(f"平均分: {avg:.1f}")
    print(f"\n结果保存至: {summary_file}")


def main():
    print("=" * 60)
    print("员工招聘批量面试评估")
    print(f"项目: {PROJECT_NAME}")
    print("=" * 60)
    
    candidates = get_candidates_from_directory()
    
    if not candidates:
        print("[错误] 未找到候选人数据")
        return
    
    print(f"\n扫描到 {len(candidates)} 位候选人:")
    for i, c in enumerate(candidates, 1):
        print(f"  {i}. {c['name']} - {c['audio_file']}")
    
    # 阶段1: 转录
    stage1_transcribe(candidates)
    
    # 阶段2: 评估
    results = stage2_evaluate(candidates)
    
    # 保存结果
    save_results(candidates, results)
    
    print("\n" + "=" * 60)
    print("全部完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
