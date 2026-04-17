#!/usr/bin/env python3
"""
离线批量AI评估处理脚本
批量对候选人进行AI面试评估并存储结果
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
import requests
import pandas as pd

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 配置
API_BASE_URL = "http://localhost:3111"
BASE_DIR = Path("/root/shijingjing/e-employee/hr-bot/data/interview")


def get_project_dir(project_name: str) -> Path:
    """获取项目目录"""
    return BASE_DIR / project_name


def get_evaluation_cache_path(project_name: str, candidate_name: str) -> Path:
    """获取评估结果缓存路径"""
    cache_dir = BASE_DIR / project_name / "evaluations"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{candidate_name}_evaluation.json"


def load_evaluation_cache(project_name: str, candidate_name: str) -> Optional[Dict]:
    """加载评估结果缓存"""
    cache_path = get_evaluation_cache_path(project_name, candidate_name)
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"读取评估缓存失败: {e}")
    return None


def save_evaluation_cache(project_name: str, candidate_name: str, evaluation: Dict):
    """保存评估结果缓存"""
    cache_path = get_evaluation_cache_path(project_name, candidate_name)
    try:
        cache_data = {
            "candidate_name": candidate_name,
            "project": project_name,
            "evaluation": evaluation,
            "cached_at": datetime.now().isoformat()
        }
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        logger.info(f"  ✓ 评估结果已缓存: {cache_path}")
    except Exception as e:
        logger.error(f"  ✗ 保存评估缓存失败: {e}")


def get_candidates_from_transcriptions(project_name: str) -> List[Dict]:
    """从转录缓存中获取所有候选人
    
    优先从 _processing_summary.json 读取转录数据
    如果没有，则从子目录中的转录文件读取
    """
    candidates = []
    transcriptions_dir = BASE_DIR / project_name / "transcriptions"
    
    if not transcriptions_dir.exists():
        logger.warning(f"转录目录不存在: {transcriptions_dir}")
        return candidates
    
    # 首先尝试从 _processing_summary.json 读取转录数据
    summary_file = transcriptions_dir / "_processing_summary.json"
    if summary_file.exists():
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary_data = json.load(f)
            
            results = summary_data.get("results", [])
            for result in results:
                candidate_name = result.get("candidate_name", "")
                transcription = result.get("transcription", "")
                
                if candidate_name and transcription:
                    candidates.append({
                        "name": candidate_name,
                        "transcript_file": str(summary_file),
                        "transcription": transcription,
                        "has_transcript": bool(transcription.strip())
                    })
                    logger.info(f"  ✓ 从汇总文件加载转录: {candidate_name} ({len(transcription)} 字符)")
            
            if candidates:
                return candidates
        except Exception as e:
            logger.warning(f"读取汇总文件失败: {e}")
    
    # 如果没有汇总文件或读取失败，则从子目录读取
    logger.info("  从子目录读取转录文件...")
    for candidate_dir in transcriptions_dir.iterdir():
        if candidate_dir.is_dir() and not candidate_dir.name.startswith('_'):
            candidate_name = candidate_dir.name
            
            # 查找该候选人的转录文件
            transcript_files = list(candidate_dir.glob("*.json"))
            if transcript_files:
                # 读取最新的转录文件
                latest_file = max(transcript_files, key=lambda p: p.stat().st_mtime)
                try:
                    with open(latest_file, 'r', encoding='utf-8') as f:
                        transcript_data = json.load(f)
                    
                    candidates.append({
                        "name": candidate_name,
                        "transcript_file": str(latest_file),
                        "transcription": transcript_data.get("transcription", ""),
                        "has_transcript": bool(transcript_data.get("transcription", "").strip())
                    })
                except Exception as e:
                    logger.warning(f"读取转录文件失败 {latest_file}: {e}")
    
    return candidates


def find_resume_excel_files(project_name: str) -> List[Path]:
    """查找项目目录下的所有Excel简历文件
    
    优先查找报名表格式的文件，避免解析其他无关的Excel文件
    """
    project_dir = BASE_DIR / project_name
    excel_files = []
    
    # 首先查找报名表格式的文件（最准确的简历文件）
    报名表_files = list(project_dir.glob("*招聘报名表*.xlsx")) + list(project_dir.glob("*招聘报名表*.xls"))
    if 报名表_files:
        return 报名表_files  # 如果找到报名表，直接返回这些文件
    
    # 如果没有找到报名表，再查找其他可能的简历文件
    patterns = ["*简历*.xlsx", "*简历*.xls", "*candidate*.xlsx", "*候选人*.xlsx"]
    for pattern in patterns:
        excel_files.extend(project_dir.glob(pattern))
    
    # 也去resumes子目录查找
    resumes_dir = project_dir / "resumes"
    if resumes_dir.exists():
        for pattern in ["*.xlsx", "*.xls"]:
            excel_files.extend(resumes_dir.glob(pattern))
    
    return list(set(excel_files))  # 去重


def parse_resume_from_excel(excel_path: Path) -> Optional[Dict]:
    """从Excel文件中解析简历信息
    
    支持两种格式:
    1. 标准表格格式: 第一行是列标题，每行是一个候选人的数据
    2. 报名表格式: 表格形式，需要从特定位置提取姓名和简历内容
    """
    try:
        df = pd.read_excel(excel_path)
        
        if df.empty:
            return None
        
        resumes = {}
        
        # 方法1: 尝试从文件名提取候选人姓名（针对报名表格式）
        filename = excel_path.stem  # 获取文件名（不含扩展名）
        candidate_name_from_file = None
        
        # 尝试从文件名中提取姓名（在括号中的内容）
        if '（' in filename and '）' in filename:
            start = filename.find('（') + 1
            end = filename.find('）')
            if start > 0 and end > start:
                candidate_name_from_file = filename[start:end]
        
        # 方法2: 检查是否是标准表格格式（有明确的列标题）
        # 注意：排除Unnamed列（pandas自动生成的列名）
        has_header = False
        name_col = None
        
        for col in df.columns:
            col_str = str(col)
            # 排除pandas自动生成的Unnamed列
            if col_str.startswith('Unnamed:'):
                continue
            col_str_lower = col_str.lower()
            if any(keyword in col_str_lower for keyword in ['姓名', 'name', '候选人', 'candidate']):
                name_col = col
                has_header = True
                break
        
        # 如果是标准表格格式，按行解析
        if has_header and name_col:
            for _, row in df.iterrows():
                name = str(row.get(name_col, '')).strip() if name_col else ''
                if not name or pd.isna(name) or name in ['nan', 'None']:
                    continue
                
                # 构建简历文本
                resume_text = []
                for col in df.columns:
                    value = row.get(col)
                    if pd.notna(value) and str(value).strip():
                        resume_text.append(f"{col}: {value}")
                
                if resume_text:
                    resumes[name] = "\n".join(resume_text)
        
        # 方法3: 处理报名表格式（表格形式，没有标准列标题）
        else:
            # 将整个表格内容作为一份简历
            # 尝试从表格中找到姓名
            candidate_name = None
            resume_lines = []
            
            # 第一遍遍历：收集所有内容
            for idx, row in df.iterrows():
                for col in df.columns:
                    value = str(row.get(col, '')).strip()
                    if value and value != 'nan':
                        resume_lines.append(value)
            
            # 第二遍遍历：查找姓名
            for idx, row in df.iterrows():
                for col in df.columns:
                    value = str(row.get(col, '')).strip()
                    if not value or value == 'nan':
                        continue
                    
                    # 查找"姓名"标签旁边的值
                    if value in ['姓 名', '姓名']:
                        # 在当前行查找姓名值（通常在后面的列）
                        for next_col in df.columns:
                            if next_col != col:
                                name_value = str(row.get(next_col, '')).strip()
                                if name_value and name_value != 'nan' and name_value not in ['姓 名', '姓名']:
                                    # 验证这个值不是标签
                                    if not any(keyword in name_value for keyword in ['性别', '民族', '籍贯', '出生']):
                                        candidate_name = name_value
                                        break
                        if candidate_name:
                            break
                
                if candidate_name:
                    break
            
            # 如果没有从表格中找到姓名，使用文件名中的姓名
            if not candidate_name and candidate_name_from_file:
                candidate_name = candidate_name_from_file
            
            # 如果找到了姓名，保存简历
            if candidate_name and resume_lines:
                # 清理简历内容，去除标题行
                filtered_lines = []
                skip_patterns = ['新国脉数字文化股份有限公司', '招聘报名表', 'NaN', 'nan']
                for line in resume_lines:
                    if not any(pattern in line for pattern in skip_patterns):
                        filtered_lines.append(line)
                
                if filtered_lines:
                    resumes[candidate_name] = "\n".join(filtered_lines)
        
        return resumes if resumes else None
        
    except Exception as e:
        logger.warning(f"解析Excel简历文件失败 {excel_path}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None


def load_all_resumes(project_name: str) -> Dict[str, str]:
    """加载项目中的所有简历"""
    all_resumes = {}
    
    # 查找所有Excel简历文件
    excel_files = find_resume_excel_files(project_name)
    logger.info(f"  找到 {len(excel_files)} 个Excel文件")
    
    for excel_file in excel_files:
        logger.info(f"    解析: {excel_file.name}")
        resumes = parse_resume_from_excel(excel_file)
        if resumes:
            all_resumes.update(resumes)
            logger.info(f"    ✓ 解析出 {len(resumes)} 份简历")
    
    return all_resumes


def load_shared_resources(project_name: str) -> Dict[str, str]:
    """加载共享资源（JD、评价标准）"""
    resources = {
        "jd_content": "",
        "evaluation_criteria": "",
        "interview_questions": []
    }
    
    # 尝试加载共享资源文件
    resources_file = BASE_DIR / project_name / "_shared_resources.json"
    if resources_file.exists():
        try:
            with open(resources_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                resources["jd_content"] = data.get("job_description", "")
                resources["evaluation_criteria"] = data.get("evaluation_criteria", "")
                resources["interview_questions"] = data.get("interview_questions", [])
        except Exception as e:
            logger.warning(f"读取共享资源失败: {e}")
    
    # 如果没有JD，尝试读取招聘公告
    if not resources["jd_content"]:
        for doc_file in (BASE_DIR / project_name).glob("*.docx"):
            if "公告" in doc_file.name or "JD" in doc_file.name:
                logger.info(f"发现招聘公告: {doc_file.name}")
                # 这里可以添加docx解析逻辑
                break
    
    return resources


def evaluate_candidate_via_api(
    project_name: str,
    candidate_name: str,
    jd_content: str,
    resume_content: str,
    evaluation_criteria: str,
    questions: List[Dict]
) -> Optional[Dict]:
    """调用API进行AI评估"""
    try:
        url = f"{API_BASE_URL}/api/v1/interview-evaluation/evaluate"
        
        # 构建表单数据
        data = {
            "candidate_name": candidate_name,
            "project": project_name,
            "jd_content": jd_content,
            "resume_content": resume_content,
            "evaluation_criteria": evaluation_criteria
        }
        
        # 如果有面试问题，转换为JSON字符串
        if questions:
            data["questions"] = json.dumps(questions, ensure_ascii=False)
        
        response = requests.post(url, data=data, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                return result
            else:
                logger.error(f"评估失败: {result.get('message', '未知错误')}")
        else:
            logger.error(f"API错误: {response.status_code}, {response.text}")
        
        return None
        
    except Exception as e:
        logger.error(f"调用评估API失败: {e}")
        return None


def process_single_candidate(
    project_name: str,
    candidate: Dict,
    resources: Dict,
    resumes: Dict[str, str],
    force_reevaluate: bool = False
) -> Dict:
    """处理单个候选人的评估"""
    candidate_name = candidate["name"]
    
    logger.info(f"\n处理候选人: {candidate_name}")
    
    # 检查是否已有评估缓存
    if not force_reevaluate:
        cached = load_evaluation_cache(project_name, candidate_name)
        if cached:
            logger.info(f"  ✓ 使用已有评估缓存")
            return {
                "success": True,
                "candidate_name": candidate_name,
                "cached": True,
                "evaluation": cached.get("evaluation", {})
            }
    
    # 检查是否有转录文本
    if not candidate.get("has_transcript"):
        logger.warning(f"  ⚠ 没有转录文本，跳过评估")
        return {
            "success": False,
            "candidate_name": candidate_name,
            "error": "没有转录文本"
        }
    
    # 检查是否有JD
    if not resources.get("jd_content", "").strip():
        logger.warning(f"  ⚠ 没有JD内容，跳过评估")
        return {
            "success": False,
            "candidate_name": candidate_name,
            "error": "没有JD内容"
        }
    
    # 获取候选人简历
    resume_content = resumes.get(candidate_name, "")
    if not resume_content:
        logger.warning(f"  ⚠ 未找到候选人简历，尝试模糊匹配...")
        # 尝试模糊匹配
        for name, content in resumes.items():
            if candidate_name in name or name in candidate_name:
                resume_content = content
                logger.info(f"    ✓ 模糊匹配到简历: {name}")
                break
    
    if not resume_content:
        logger.warning(f"  ⚠ 没有简历内容，跳过评估")
        return {
            "success": False,
            "candidate_name": candidate_name,
            "error": "没有简历内容"
        }
    
    # 调用API进行AI评估
    logger.info(f"  🔄 开始AI评估...")
    logger.info(f"    JD长度: {len(resources['jd_content'])} 字符")
    logger.info(f"    简历长度: {len(resume_content)} 字符")
    logger.info(f"    转录长度: {len(candidate.get('transcription', ''))} 字符")
    
    start_time = datetime.now()
    
    evaluation = evaluate_candidate_via_api(
        project_name=project_name,
        candidate_name=candidate_name,
        jd_content=resources["jd_content"],
        resume_content=resume_content,
        evaluation_criteria=resources["evaluation_criteria"],
        questions=resources.get("interview_questions", [])
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    if evaluation:
        # 保存评估结果到缓存
        save_evaluation_cache(project_name, candidate_name, evaluation)
        
        logger.info(f"  ✓ 评估完成，综合得分: {evaluation.get('overall_score', 0)}, 耗时: {duration:.2f}秒")
        
        return {
            "success": True,
            "candidate_name": candidate_name,
            "cached": False,
            "evaluation": evaluation,
            "processing_time": duration
        }
    else:
        logger.error(f"  ✗ 评估失败")
        return {
            "success": False,
            "candidate_name": candidate_name,
            "error": "AI评估失败"
        }


def process_project(
    project_name: str,
    force_reevaluate: bool = False
) -> Dict:
    """处理整个项目的所有候选人评估"""
    logger.info(f"=" * 60)
    logger.info(f"开始离线AI评估: {project_name}")
    logger.info(f"=" * 60)
    
    # 1. 加载共享资源
    logger.info("\n加载共享资源...")
    resources = load_shared_resources(project_name)
    logger.info(f"  JD内容: {'已加载' if resources['jd_content'] else '未加载'} ({len(resources['jd_content'])} 字符)")
    logger.info(f"  评价标准: {'已加载' if resources['evaluation_criteria'] else '未加载'}")
    logger.info(f"  面试问题: {len(resources['interview_questions'])} 个")
    
    # 2. 加载所有简历
    logger.info("\n加载简历数据...")
    resumes = load_all_resumes(project_name)
    logger.info(f"  共加载 {len(resumes)} 份简历")
    for name in list(resumes.keys())[:5]:  # 显示前5个
        logger.info(f"    - {name}")
    if len(resumes) > 5:
        logger.info(f"    ... 还有 {len(resumes) - 5} 份")
    
    # 3. 获取所有候选人
    logger.info("\n获取候选人列表...")
    candidates = get_candidates_from_transcriptions(project_name)
    logger.info(f"  找到 {len(candidates)} 个候选人")
    
    if not candidates:
        logger.warning("没有找到候选人，请确保已完成ASR转录")
        return {"success": False, "error": "没有找到候选人"}
    
    # 4. 批量评估
    logger.info("\n开始批量AI评估...")
    results = []
    success_count = 0
    cached_count = 0
    failed_count = 0
    
    for i, candidate in enumerate(candidates, 1):
        logger.info(f"\n[{i}/{len(candidates)}]")
        
        result = process_single_candidate(
            project_name=project_name,
            candidate=candidate,
            resources=resources,
            resumes=resumes,
            force_reevaluate=force_reevaluate
        )
        
        results.append(result)
        
        if result.get("success"):
            if result.get("cached"):
                cached_count += 1
            else:
                success_count += 1
        else:
            failed_count += 1
    
    # 5. 保存汇总结果
    summary = {
        "project": project_name,
        "processed_at": datetime.now().isoformat(),
        "total_candidates": len(candidates),
        "success": success_count,
        "cached": cached_count,
        "failed": failed_count,
        "results": results
    }
    
    summary_path = BASE_DIR / project_name / "evaluations" / "_evaluation_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n" + "=" * 60)
    logger.info(f"评估完成!")
    logger.info(f"  总计: {len(candidates)}")
    logger.info(f"  新评估: {success_count}")
    logger.info(f"  使用缓存: {cached_count}")
    logger.info(f"  失败: {failed_count}")
    logger.info(f"  汇总文件: {summary_path}")
    logger.info(f"=" * 60)
    
    return summary


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='离线批量AI评估脚本')
    parser.add_argument('project', help='项目名称，如：20260401战略招聘')
    parser.add_argument('--force', '-f', action='store_true', help='强制重新评估（忽略缓存）')
    
    args = parser.parse_args()
    
    # 运行处理
    result = process_project(args.project, args.force)
    
    # 返回退出码
    if result.get("failed", 0) > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
