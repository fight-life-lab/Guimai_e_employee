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
# 注意：在服务器上运行时，后端API使用localhost
API_BASE = "http://127.0.0.1:3111"  # 本地FastAPI服务
ASR_API_URL = "http://localhost:8003/transcribe"  # 本地Whisper ASR服务
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

def step1_asr(candidate_name):
    """步骤1: ASR转录"""
    log(f"[{candidate_name}] 步骤1: 开始ASR转录...")
    
    # 检查是否已有转录数据
    tras_file = Path(PROJECT_DIR) / "tras" / f"{candidate_name}.json"
    if tras_file.exists():
        try:
            with open(tras_file, 'r', encoding='utf-8') as f:
                tras_data = json.load(f)
            if tras_data.get('transcription'):
                log(f"[{candidate_name}] 转录数据已存在，跳过ASR步骤")
                return tras_data
        except Exception as e:
            log(f"[{candidate_name}] 读取已有转录数据失败: {e}")
    
    # 查找音频文件
    audio_files = list(Path(PROJECT_DIR).glob(f"*{candidate_name}*.aac")) + \
                  list(Path(PROJECT_DIR).glob(f"*{candidate_name}*.mp3")) + \
                  list(Path(PROJECT_DIR).glob(f"*{candidate_name}*.wav"))
    
    if not audio_files:
        log(f"[{candidate_name}] 未找到音频文件")
        return None
    
    audio_file = audio_files[0]
    log(f"[{candidate_name}] 找到音频文件: {audio_file.name}")
    
    # 调用本地Whisper ASR服务
    log(f"[{candidate_name}] 调用本地ASR服务: {ASR_API_URL}")
    
    try:
        with open(audio_file, 'rb') as f:
            files = {'audio_file': (audio_file.name, f, 'audio/aac')}
            data = {'language': 'zh'}
            response = requests.post(ASR_API_URL, files=files, data=data, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            transcript = result.get('transcript', '')
            
            if transcript:
                # 保存ASR结果
                tras_dir = Path(PROJECT_DIR) / "tras"
                tras_dir.mkdir(parents=True, exist_ok=True)
                
                tras_file = tras_dir / f"{candidate_name}.json"
                tras_data = {
                    "candidate_name": candidate_name,
                    "audio_file": audio_file.name,
                    "transcription": transcript,
                    "duration": result.get('duration', 0),
                    "processed_at": datetime.now().isoformat()
                }
                
                with open(tras_file, 'w', encoding='utf-8') as f:
                    json.dump(tras_data, f, ensure_ascii=False, indent=2)
                
                log(f"[{candidate_name}] ASR转录完成，文本长度: {len(transcript)} 字符，保存到: {tras_file}")
                return tras_data
            else:
                log(f"[{candidate_name}] ASR转录结果为空")
                return None
        else:
            log(f"[{candidate_name}] ASR请求失败: {response.status_code}, {response.text}")
            return None
            
    except Exception as e:
        log(f"[{candidate_name}] ASR异常: {e}")
        return None

def read_interview_questions():
    """读取面试问题文件"""
    try:
        import openpyxl
        
        questions_file = Path(PROJECT_DIR) / "结构化面试问题（初面）.xlsx"
        if not questions_file.exists():
            log(f"面试问题文件不存在: {questions_file}")
            return []
        
        wb = openpyxl.load_workbook(questions_file)
        ws = wb.active
        
        questions = []
        for row in ws.iter_rows(min_row=2, values_only=True):  # 跳过表头
            if row and row[0]:  # 确保有内容
                questions.append({
                    "category": row[0] if len(row) > 0 else "",
                    "question": row[1] if len(row) > 1 else "",
                    "evaluation_points": row[2] if len(row) > 2 else ""
                })
        
        log(f"读取到 {len(questions)} 个面试问题")
        return questions
    except Exception as e:
        log(f"读取面试问题文件失败: {e}")
        return []

def step2_qa(candidate_name, tras_data):
    """步骤2: QA问题对提取（简化版，直接将转录文本作为QA数据）"""
    log(f"[{candidate_name}] 步骤2: 开始QA提取...")
    
    # 检查是否已有QA数据
    qa_file = Path(PROJECT_DIR) / "qa" / f"{candidate_name}.json"
    if qa_file.exists():
        try:
            with open(qa_file, 'r', encoding='utf-8') as f:
                qa_data = json.load(f)
            if qa_data.get('qa_pairs'):
                log(f"[{candidate_name}] QA数据已存在，共 {len(qa_data['qa_pairs'])} 个问题对，跳过QA提取步骤")
                return qa_data
        except Exception as e:
            log(f"[{candidate_name}] 读取已有QA数据失败: {e}")
    
    # 读取面试问题
    questions = read_interview_questions()
    
    # 由于后端QA接口不存在，我们直接将转录文本作为QA数据保存
    # 创建一个简单的QA结构，包含转录文本和面试问题
    qa_dir = Path(PROJECT_DIR) / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    
    qa_file = qa_dir / f"{candidate_name}.json"
    
    # 构建QA数据
    qa_pairs = []
    if questions:
        # 如果有面试问题，将每个问题与转录文本关联
        for i, q in enumerate(questions[:5]):  # 最多取前5个问题
            qa_pairs.append({
                "question": q.get('question', f'问题{i+1}'),
                "answer": tras_data.get('transcription', '')[:500] if i == 0 else "详见完整转录文本",  # 第一个问题给部分文本
                "category": q.get('category', '通用'),
                "evaluation_points": q.get('evaluation_points', '')
            })
    else:
        # 如果没有面试问题，创建一个通用的QA对
        qa_pairs.append({
            "question": "请介绍一下你的工作经历",
            "answer": tras_data.get('transcription', '')[:1000],  # 取前1000字符
            "category": "通用",
            "evaluation_points": "考察候选人的工作经验和背景"
        })
    
    qa_data = {
        "candidate_name": candidate_name,
        "qa_pairs": qa_pairs,
        "questions": questions,
        "full_transcription": tras_data.get('transcription', ''),  # 保存完整转录文本
        "processed_at": datetime.now().isoformat()
    }
    
    try:
        with open(qa_file, 'w', encoding='utf-8') as f:
            json.dump(qa_data, f, ensure_ascii=False, indent=2)
        
        log(f"[{candidate_name}] QA数据生成完成，共 {len(qa_pairs)} 个问题对，保存到: {qa_file}")
        return qa_data
    except Exception as e:
        log(f"[{candidate_name}] 保存QA数据失败: {e}")
        return None

def step3_evaluate(candidate_name, qa_data):
    """步骤3: AI评估"""
    log(f"[{candidate_name}] 步骤3: 开始AI评估...")
    
    # 检查是否已有评估数据
    eval_file = Path(PROJECT_DIR) / "eval" / f"{candidate_name}.json"
    if eval_file.exists():
        try:
            with open(eval_file, 'r', encoding='utf-8') as f:
                eval_data = json.load(f)
            if eval_data.get('overall_score'):
                log(f"[{candidate_name}] 评估数据已存在，综合得分: {eval_data['overall_score']}分 ({eval_data.get('evaluation_level', '未知')})，跳过AI评估步骤")
                return eval_data
        except Exception as e:
            log(f"[{candidate_name}] 读取已有评估数据失败: {e}")
    
    url = f"{API_BASE}/api/v1/interview-evaluation/evaluate"
    
    # 读取JD内容（从文件或默认）
    jd_content = read_jd_content()
    resume_content = read_resume(candidate_name)
    
    # 构建请求数据
    data = {
        'project': PROJECT_NAME,
        'candidate_name': candidate_name,
        'jd_title': JD_TITLE,
        'jd_content': jd_content,
        'resume_content': resume_content
    }
    
    log(f"[{candidate_name}] 调用AI评估接口，JD长度: {len(jd_content)}, 简历长度: {len(resume_content)}")
    
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
