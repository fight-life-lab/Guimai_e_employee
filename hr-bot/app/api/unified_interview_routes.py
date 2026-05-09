"""
统一面试评价API路由 - 合并员工招聘和干部面试评估
支持两种评估方式：employee（员工）和 cadre（干部）

核心设计：
1. 通过 evaluation_type 参数区分员工/干部评估
2. 使用统一的评估引擎模块处理评估逻辑
3. 共享音频转录、问答对提取等功能
"""

import os
import json
import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Body
import aiohttp

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from app.services.evaluation_engine import get_evaluation_engine
from app.services.interview_services import (
    transcribe_audio_file,
    calculate_salary_match,
    extract_salary_with_llm
)
from app.services.shared_utils import (
    get_project_dir,
    get_transcript_dir,
    get_eval_dir,
    get_qa_dir,
    get_audio_dir,
    get_base_interview_dir,
    load_evaluation_cache,
    save_evaluation_cache,
    auto_extract_qa_pairs,
    extract_candidate_name,
    get_projects as get_all_projects,
    check_resume_exists
)
from app.models.interview_models import (
    EvaluateRequest,
    EvaluateResponse,
    TranscribeResponse,
    QAPairsResponse,
    CandidatesResponse,
    ProjectsResponse
)


class EvaluationResultResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    candidate_name: Optional[str] = Field(None, description="候选人姓名")
    evaluation: Optional[dict] = Field(None, description="评估结果")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/interview", tags=["统一面试评价"])


# ============ API路由 ============

@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_candidate(request: EvaluateRequest):
    """
    统一面试评估接口
    支持员工(employee)和干部(cadre)两种评估方式
    
    核心流程：
    1. 检查缓存
    2. 获取评估引擎
    3. 执行评估
    4. 计算薪酬匹配度
    5. 提取问答对
    6. 保存缓存
    """
    evaluation_type = request.evaluation_type or "employee"
    project = request.project
    candidate_name = request.candidate_name
    jd_content = request.jd_content or ""
    resume_content = request.resume_content or ""
    transcript = request.transcript or ""
    force_reevaluate = request.force_reevaluate or False
    
    logger.info(f"[统一面试评价] 开始评估，类型: {evaluation_type}, 项目: {project}, 候选人: {candidate_name}")
    
    try:
        # 检查缓存
        if not force_reevaluate:
            cached_eval = load_evaluation_cache(project, candidate_name, evaluation_type)
            if cached_eval:
                logger.info(f"[统一面试评价] 使用缓存的评估结果: {candidate_name}")
                return EvaluateResponse(
                    success=True,
                    message="使用缓存的评估结果",
                    evaluation=cached_eval.get("evaluation", cached_eval),
                    candidate_name=candidate_name
                )
        
        # 如果没有转录文本，尝试从文件读取
        if not transcript.strip():
            transcript_dir = get_transcript_dir(project, evaluation_type)
            # 尝试多种文件名格式
            for filename in [f"{candidate_name}.json", f"{candidate_name}_asr.json"]:
                transcript_file = os.path.join(transcript_dir, filename)
                if os.path.exists(transcript_file):
                    with open(transcript_file, 'r', encoding='utf-8') as f:
                        transcript_data = json.load(f)
                    transcript = transcript_data.get("transcription", "") or transcript_data.get("transcript", "")
                    break
        
        # 获取评估引擎并执行评估
        engine = get_evaluation_engine(evaluation_type)
        evaluation_result = await engine.evaluate(jd_content, resume_content, transcript)
        
        if not evaluation_result:
            raise HTTPException(status_code=500, detail="AI评估失败")
        
        # 将Pydantic模型转换为字典
        evaluation = evaluation_result.dict()
        
        # 干部评估特殊处理：内部候选人检测和分数差异化调整
        if evaluation_type == "cadre":
            logger.info(f"[统一面试评价] 干部评估，执行内部候选人检测和分数差异化调整")
            evaluation = adjust_scores_for_differentiation(evaluation, resume_content, transcript)
        
        # 计算薪酬匹配度（员工和干部都需要）
        llm_salary_info = await extract_salary_with_llm(transcript)
        salary_match = calculate_salary_match(resume_content, transcript, evaluation_type, llm_salary_info)
        if salary_match:
            evaluation["salary_match"] = salary_match.dict()
        else:
            # 如果没有提取到薪酬信息，明确设置为None，避免使用缓存中的旧数据
            evaluation["salary_match"] = None
        
        # 提取问答对 - 使用结构化问题并调用大模型凝练
        if transcript:
            try:
                project_dir = get_project_dir(project, evaluation_type)
                # 加载结构化面试问题
                structured_questions = load_structured_questions(project_dir)
                
                if structured_questions:
                    # 使用结构化问题提取问答对，并调用大模型凝练答案
                    qa_pairs = await extract_qa_by_questions(transcript, structured_questions)
                    logger.info(f"[统一面试评价] 使用结构化问题提取问答对: {candidate_name}, 共 {len(qa_pairs)} 个")
                else:
                    # 如果没有结构化问题，使用自动提取
                    qa_pairs = auto_extract_qa_pairs(transcript, project_dir)
                    logger.info(f"[统一面试评价] 使用自动提取问答对: {candidate_name}, 共 {len(qa_pairs)} 个")
                
                # 保存问答对结果
                await save_qa_result(project, candidate_name, qa_pairs, structured_questions, evaluation_type)
                logger.info(f"[统一面试评价] 问答对保存完成: {candidate_name}")
            except Exception as e:
                logger.error(f"[统一面试评价] 问答对提取失败: {e}")
        
        # 保存缓存
        save_evaluation_cache(project, candidate_name, evaluation, evaluation_type)
        
        return EvaluateResponse(
            success=True,
            message="评估成功",
            evaluation=evaluation,
            candidate_name=candidate_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[统一面试评价] 评估失败: {e}")
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}")


@router.get("/projects", response_model=ProjectsResponse)
async def get_projects(evaluation_type: str = Query(None, description="评估类型：employee（员工）/ cadre（干部）")):
    """获取项目列表，根据评估类型返回对应目录下的项目"""
    try:
        project_names = get_all_projects(evaluation_type)
        projects = []
        for name in project_names:
            projects.append({
                "name": name,
                "type": evaluation_type or "employee",
                "candidate_count": 0,
                "evaluated_count": 0
            })
        return ProjectsResponse(success=True, projects=projects)
    except Exception as e:
        logger.error(f"获取项目列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目列表失败: {str(e)}")


@router.get("/positions")
async def get_positions(evaluation_type: str = Query("employee", description="评估类型：employee（员工）/ cadre（干部）")):
    """获取岗位列表（即项目列表，岗位和项目在当前设计中是同一概念）"""
    try:
        base_dir = get_base_interview_dir()
        type_dir = os.path.join(base_dir, "员工" if evaluation_type == "employee" else "干部")
        
        if not os.path.exists(type_dir):
            os.makedirs(type_dir, exist_ok=True)
            return {"positions": []}
        
        positions = []
        for entry in os.listdir(type_dir):
            entry_path = os.path.join(type_dir, entry)
            # 过滤掉系统目录（eval, tras, audio）和隐藏文件
            if os.path.isdir(entry_path) and not entry.startswith('.') and entry not in ['eval', 'tras', 'audio', 'qa_cache', 'transcriptions']:
                positions.append(entry)
        
        positions.sort()
        return {"positions": positions}
    except Exception as e:
        logger.error(f"获取岗位列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取岗位列表失败: {str(e)}")


@router.post("/position")
async def create_position(
    position_name: str = Body(..., description="岗位名称"),
    evaluation_type: str = Body("employee", description="评估类型")
):
    """创建新岗位（即创建项目目录）"""
    try:
        base_dir = get_base_interview_dir()
        type_dir = os.path.join(base_dir, "员工" if evaluation_type == "employee" else "干部")
        position_dir = os.path.join(type_dir, position_name)
        
        # 创建目录结构
        os.makedirs(os.path.join(position_dir, "audio"), exist_ok=True)
        os.makedirs(os.path.join(position_dir, "tras"), exist_ok=True)
        os.makedirs(os.path.join(position_dir, "eval"), exist_ok=True)
        
        return {"success": True, "message": f"岗位 '{position_name}' 创建成功"}
    except Exception as e:
        logger.error(f"创建岗位失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建岗位失败: {str(e)}")


@router.get("/candidates", response_model=CandidatesResponse)
async def get_candidates(
    project: str = Query(..., description="项目名称"),
    evaluation_type: str = Query(None, description="评估类型：employee（员工）/ cadre（干部）")
):
    """获取项目下的所有候选人"""
    try:
        # 处理项目名，如果包含类型前缀（如"干部/"或"员工/"），则去掉前缀
        project_name = project
        if project.startswith("干部/"):
            project_name = project[3:]  # 去掉"干部/"前缀
            if not evaluation_type:
                evaluation_type = "cadre"
        elif project.startswith("员工/"):
            project_name = project[3:]  # 去掉"员工/"前缀
            if not evaluation_type:
                evaluation_type = "employee"
        
        project_dir = get_project_dir(project_name, evaluation_type)
        candidates = []
        candidate_names = set()  # 用于去重
        
        # 从音频目录查找候选人（支持中文"录音"和英文"audio"目录）
        audio_dirs = [os.path.join(project_dir, "audio"), os.path.join(project_dir, "录音")]
        for audio_dir in audio_dirs:
            if os.path.exists(audio_dir):
                for filename in os.listdir(audio_dir):
                    if filename.endswith(('.wav', '.mp3', '.aac', '.m4a')) and not filename.startswith('.'):
                        name = extract_candidate_name(filename)
                        
                        # 去重
                        if name in candidate_names:
                            continue
                        candidate_names.add(name)
                        
                        # 检查转录状态
                        transcript_cache = None
                        transcript_text = ""
                        transcript_dir = get_transcript_dir(project, evaluation_type)
                        for cache_name in [f"{name}.json", f"{filename}.json"]:
                            cache_file = os.path.join(transcript_dir, cache_name)
                            if os.path.exists(cache_file):
                                try:
                                    with open(cache_file, 'r', encoding='utf-8') as f:
                                        transcript_cache = json.load(f)
                                        transcript_text = transcript_cache.get("transcription", "") or transcript_cache.get("transcript", "")
                                except:
                                    pass
                            if transcript_cache:
                                break
                        
                        # 检查评估状态
                        eval_cache = load_evaluation_cache(project, name, evaluation_type)
                        has_evaluation = eval_cache is not None
                        evaluation = eval_cache.get("evaluation", eval_cache) if eval_cache else None
                        
                        # 检查简历是否存在
                        has_resume = check_resume_exists(project, name, evaluation_type)
                        
                        # 如果有评估缓存，优先使用评估文件中的candidate_name（可能已修正过名字）
                        display_name = name
                        if eval_cache and "candidate_name" in eval_cache:
                            display_name = eval_cache["candidate_name"]
                        
                        candidate = {
                            "name": display_name,
                            "filename": filename,
                            "has_transcript": transcript_cache is not None,
                            "transcript": transcript_text,
                            "transcript_length": len(transcript_text),
                            "has_evaluation": has_evaluation,
                            "evaluation": evaluation,
                            "has_resume": has_resume
                        }
                        
                        # 添加薪酬匹配度信息（如果有）
                        if evaluation and "salary_match" in evaluation:
                            candidate["salary_match"] = evaluation["salary_match"]
                        
                        candidates.append(candidate)
        
        return CandidatesResponse(success=True, candidates=candidates)
    
    except Exception as e:
        logger.error(f"获取候选人列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取候选人列表失败: {str(e)}")


@router.get("/qa/{project}/{candidate_name}", response_model=QAPairsResponse)
async def get_qa_pairs(
    project: str, 
    candidate_name: str,
    evaluation_type: str = Query(None, description="评估类型：employee（员工）/ cadre（干部）")
):
    """获取候选人的问答对 - 基于结构化面试问题提炼"""
    try:
        project_dir = get_project_dir(project, evaluation_type)
        qa_cache_dir = os.path.join(project_dir, "qa_cache")
        
        # 支持多种文件名格式
        qa_files = [
            os.path.join(qa_cache_dir, f"{candidate_name}.json"),
            os.path.join(qa_cache_dir, f"{candidate_name}_qa.json")
        ]
        
        qa_file = None
        for f in qa_files:
            if os.path.exists(f):
                qa_file = f
                break
        
        if qa_file:
            with open(qa_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                qa_pairs = data.get("qa_pairs", [])
                # 如果有结构化问题信息，一起返回
                structured_questions = data.get("structured_questions", [])
                if structured_questions:
                    # 添加结构化问题总结
                    summary = generate_qa_summary(qa_pairs, structured_questions)
                    return QAPairsResponse(
                        success=True, 
                        qa_pairs=qa_pairs,
                        summary=summary,
                        structured_questions=structured_questions
                    )
                return QAPairsResponse(success=True, qa_pairs=qa_pairs)
        
        # 加载结构化面试问题
        structured_questions = load_structured_questions(project_dir)
        
        # 尝试从转录文本提取问答
        transcript_dir = get_transcript_dir(project, evaluation_type)
        transcript = ""
        for filename in [f"{candidate_name}.json", f"{candidate_name}_asr.json"]:
            transcript_file = os.path.join(transcript_dir, filename)
            if os.path.exists(transcript_file):
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    transcript_data = json.load(f)
                transcript = transcript_data.get("transcription", "") or transcript_data.get("transcript", "")
                break
        
        if transcript:
            # 如果有结构化问题，使用结构化问题来组织问答
            if structured_questions:
                qa_pairs = await extract_qa_by_questions(transcript, structured_questions)
            else:
                # 否则使用自动提取
                qa_pairs = auto_extract_qa_pairs(transcript, project_dir)
            
            # 生成总结
            summary = generate_qa_summary(qa_pairs, structured_questions)
            
            # 保存到缓存
            os.makedirs(qa_cache_dir, exist_ok=True)
            with open(qa_files[0], 'w', encoding='utf-8') as f:
                json.dump({
                    "qa_pairs": qa_pairs,
                    "structured_questions": structured_questions,
                    "summary": summary,
                    "timestamp": datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
            
            return QAPairsResponse(
                success=True, 
                qa_pairs=qa_pairs,
                summary=summary,
                structured_questions=structured_questions
            )
        
        return QAPairsResponse(success=True, qa_pairs=[])
    except Exception as e:
        logger.error(f"获取问答对失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取问答对失败: {str(e)}")


def generate_qa_summary(qa_pairs: List[Dict], structured_questions: List[Dict]) -> Dict[str, Any]:
    """生成问答总结"""
    try:
        total_questions = len(structured_questions) if structured_questions else len(qa_pairs)
        answered_questions = len([qa for qa in qa_pairs if qa.get("answer") and len(qa.get("answer", "")) > 20])
        
        # 按维度统计
        dimension_stats = {}
        for qa in qa_pairs:
            dim = qa.get("dimension", "通用")
            if dim not in dimension_stats:
                dimension_stats[dim] = {"count": 0, "answered": 0}
            dimension_stats[dim]["count"] += 1
            if qa.get("answer") and len(qa.get("answer", "")) > 20:
                dimension_stats[dim]["answered"] += 1
        
        return {
            "total_questions": total_questions,
            "answered_questions": answered_questions,
            "coverage_rate": round(answered_questions / total_questions * 100, 1) if total_questions > 0 else 0,
            "dimension_stats": dimension_stats,
            "summary_text": f"共涉及 {total_questions} 个结构化问题，已回答 {answered_questions} 个，覆盖率 {round(answered_questions / total_questions * 100, 1) if total_questions > 0 else 0}%"
        }
    except Exception as e:
        logger.error(f"生成问答总结失败: {e}")
        return {"summary_text": "总结生成失败"}


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    project: str = Form(..., description="项目名称"),
    candidate_name: str = Form("", description="候选人姓名"),
    audio_file: UploadFile = File(..., description="音频文件(AAC/MP3/WAV)"),
    language: str = Form("zh", description="语言 (默认中文)")
):
    """
    转录音频文件
    使用本地Whisper API进行音频转文本
    """
    try:
        # 如果没有提供候选人姓名，从文件名提取
        if not candidate_name.strip():
            candidate_name = extract_candidate_name(audio_file.filename)
        
        result = await transcribe_audio_file(project, audio_file, language, candidate_name)
        
        if result["success"]:
            return TranscribeResponse(
                success=True,
                transcript=result["transcript"],
                filename=result["filename"],
                candidate_name=result["candidate_name"],
                cached=result["cached"]
            )
        else:
            raise HTTPException(status_code=500, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[统一面试评价] 转录失败: {e}")
        raise HTTPException(status_code=500, detail=f"转录失败: {str(e)}")


@router.get("/evaluation/{project}/{candidate_name}", response_model=EvaluationResultResponse)
async def get_evaluation(
    project: str,
    candidate_name: str,
    evaluation_type: str = Query("employee", description="评估类型：employee（员工）/ cadre（干部）")
):
    """获取候选人的评估结果"""
    try:
        # 处理项目名，如果包含类型前缀（如"干部/"或"员工/"），则去掉前缀
        project_name = project
        if project.startswith("干部/"):
            project_name = project[3:]  # 去掉"干部/"前缀
            if evaluation_type == "employee":
                evaluation_type = "cadre"
        elif project.startswith("员工/"):
            project_name = project[3:]  # 去掉"员工/"前缀
            if evaluation_type == "cadre":
                evaluation_type = "employee"
        
        # 首先尝试按文件名查找
        eval_cache = load_evaluation_cache(project_name, candidate_name, evaluation_type)
        
        # 如果按文件名找不到，遍历所有评估文件查找匹配的candidate_name
        if not eval_cache:
            eval_dir = get_eval_dir(project_name, evaluation_type)
            if os.path.exists(eval_dir):
                for filename in os.listdir(eval_dir):
                    if filename.endswith('.json'):
                        file_path = os.path.join(eval_dir, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                                # 检查candidate_name是否匹配
                                if cache_data.get('candidate_name') == candidate_name:
                                    eval_cache = cache_data
                                    break
                        except Exception as e:
                            logger.error(f"读取评估文件失败 {filename}: {e}")
        
        if eval_cache:
            evaluation = eval_cache.get("evaluation", eval_cache)
            return EvaluationResultResponse(
                success=True,
                candidate_name=candidate_name,
                evaluation=evaluation
            )
        else:
            raise HTTPException(status_code=404, detail="未找到评估数据")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取评估结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取评估结果失败: {str(e)}")


@router.get("/transcript/{project}/{candidate_name}")
async def get_transcript(
    project: str,
    candidate_name: str,
    evaluation_type: str = Query("employee", description="评估类型：employee（员工）/ cadre（干部）")
):
    """获取候选人的转录文本"""
    try:
        transcript_dir = get_transcript_dir(project, evaluation_type)
        
        # 尝试多种文件名格式
        transcript_files = [
            os.path.join(transcript_dir, f"{candidate_name}.json"),
            os.path.join(transcript_dir, f"{candidate_name}_asr.json"),
        ]
        
        for transcript_file in transcript_files:
            if os.path.exists(transcript_file):
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    transcript = data.get("transcription", "") or data.get("transcript", "")
                    return {
                        "success": True,
                        "candidate_name": candidate_name,
                        "transcript": transcript
                    }
        
        raise HTTPException(status_code=404, detail="未找到转录文本")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取转录文本失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取转录文本失败: {str(e)}")


@router.post("/upload")
async def upload_audio_files(
    project: str = Form(..., description="项目名称"),
    evaluation_type: str = Form("employee", description="评估类型"),
    audio_files: List[UploadFile] = File(..., description="音频文件列表")
):
    """上传多个音频文件"""
    try:
        uploaded_count = 0
        for audio_file in audio_files:
            # 提取候选人姓名
            candidate_name = extract_candidate_name(audio_file.filename)
            
            # 保存音频文件
            project_dir = get_project_dir(project, evaluation_type)
            audio_dir = os.path.join(project_dir, "audio")
            os.makedirs(audio_dir, exist_ok=True)
            
            audio_path = os.path.join(audio_dir, audio_file.filename)
            with open(audio_path, 'wb') as f:
                f.write(await audio_file.read())
            
            uploaded_count += 1
        
        return {"success": True, "message": f"成功上传 {uploaded_count} 个文件", "uploaded_count": uploaded_count}
    except Exception as e:
        logger.error(f"上传文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.delete("/candidate")
async def delete_candidate(
    project: str = Query(..., description="项目名称"), 
    candidate_name: str = Query(..., description="候选人姓名"),
    evaluation_type: str = Query(None, description="评估类型")
):
    """删除候选人数据"""
    try:
        # 删除评估缓存
        eval_dir = get_eval_dir(project, evaluation_type)
        eval_file = os.path.join(eval_dir, f"{candidate_name}.json")
        if os.path.exists(eval_file):
            os.remove(eval_file)
        
        # 删除问答对
        qa_dir = get_qa_dir(project, evaluation_type)
        qa_file = os.path.join(qa_dir, f"{candidate_name}.json")
        if os.path.exists(qa_file):
            os.remove(qa_file)
        
        # 删除转录缓存
        transcript_dir = get_transcript_dir(project, evaluation_type)
        for filename in [f"{candidate_name}.json", f"{candidate_name}_asr.json"]:
            transcript_file = os.path.join(transcript_dir, filename)
            if os.path.exists(transcript_file):
                os.remove(transcript_file)
        
        return {"success": True, "message": "删除成功"}
    except Exception as e:
        logger.error(f"删除候选人数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.post("/batch-evaluate")
async def batch_evaluate(
    project: str = Body(..., description="项目名称"),
    evaluation_type: str = Body("employee", description="评估类型"),
    force_reevaluate: bool = Body(False, description="是否强制重新评估")
):
    """批量评估项目下的所有候选人"""
    try:
        candidates_response = await get_candidates(project, evaluation_type)
        candidates = candidates_response.candidates
        
        if not candidates:
            return {"success": True, "message": "没有可评估的候选人", "evaluated_count": 0}
        
        evaluated_count = 0
        failed_count = 0
        results = []
        
        for candidate in candidates:
            # 跳过没有转录文本的候选人
            if not candidate.get("transcript"):
                continue
            
            # 如果不是强制重新评估且已有评估结果，跳过
            if not force_reevaluate and candidate.get("has_evaluation"):
                continue
            
            try:
                result = await evaluate_candidate(
                    evaluation_type=evaluation_type,
                    project=project,
                    candidate_name=candidate["name"],
                    transcript=candidate.get("transcript", ""),
                    force_reevaluate=force_reevaluate
                )
                results.append({
                    "candidate_name": candidate["name"],
                    "success": result.success,
                    "overall_score": result.evaluation.get("overall_score") if result.evaluation else None
                })
                evaluated_count += 1
            except Exception as e:
                results.append({
                    "candidate_name": candidate["name"],
                    "success": False,
                    "error": str(e)
                })
                failed_count += 1
        
        return {
            "success": True,
            "message": f"批量评估完成，成功: {evaluated_count}, 失败: {failed_count}",
            "evaluated_count": evaluated_count,
            "failed_count": failed_count,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"批量评估失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量评估失败: {str(e)}")


@router.post("/batch-reset-evaluation")
async def batch_reset_evaluation(
    project: str = Body(..., description="项目名称"),
    evaluation_type: str = Body("employee", description="评估类型：employee（员工）/ cadre（干部）"),
    candidate_names: List[str] = Body(None, description="指定候选人列表，为空则重置所有")
):
    """批量重置评估结果 - 删除评估缓存文件"""
    try:
        project_dir = get_project_dir(project, evaluation_type)
        eval_dir = os.path.join(project_dir, "eval")
        
        if not os.path.exists(eval_dir):
            return {
                "success": True,
                "message": "没有评估数据需要重置",
                "deleted_count": 0
            }
        
        deleted_count = 0
        failed_count = 0
        deleted_files = []
        
        # 如果指定了候选人列表，只删除这些候选人的评估
        if candidate_names and len(candidate_names) > 0:
            for candidate_name in candidate_names:
                eval_file = os.path.join(eval_dir, f"{candidate_name}.json")
                if os.path.exists(eval_file):
                    try:
                        os.remove(eval_file)
                        deleted_count += 1
                        deleted_files.append(candidate_name)
                        logger.info(f"删除评估文件: {eval_file}")
                    except Exception as e:
                        logger.error(f"删除评估文件失败 {eval_file}: {e}")
                        failed_count += 1
        else:
            # 删除所有评估文件
            for filename in os.listdir(eval_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(eval_dir, filename)
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        deleted_files.append(filename.replace('.json', ''))
                        logger.info(f"删除评估文件: {file_path}")
                    except Exception as e:
                        logger.error(f"删除评估文件失败 {file_path}: {e}")
                        failed_count += 1
        
        return {
            "success": True,
            "message": f"评估重置完成，成功删除: {deleted_count}个，失败: {failed_count}个",
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "deleted_candidates": deleted_files
        }
        
    except Exception as e:
        logger.error(f"批量重置评估失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量重置评估失败: {str(e)}")


# ============ 干部招聘特殊逻辑 ============

def is_internal_candidate(resume_text: str, transcript: str = "") -> tuple:
    """
    检测候选人是否是内部员工（本单位/本集团工作经验）
    精确检测：必须是当前在新国脉/中国电信/联通等内部单位工作
    
    Returns:
        (is_internal: bool, company_name: str, bonus_points: int)
    """
    combined_text = (resume_text + " " + transcript)
    combined_lower = combined_text.lower()
    
    # 检查是否在当前单位工作（通过"现单位所任职位"或"至今/迄今"等关键词判断）
    # 模式1: 现单位所任职位 + 新国脉/中国电信等
    current_position_patterns = [
        r'现单位所任职位[^\n]*新国脉',
        r'现单位[^\n]*新国脉',
        r'现任[^\n]*新国脉',
        r'至今[^\n]*新国脉',
        r'迄今[^\n]*新国脉',
    ]
    
    for pattern in current_position_patterns:
        if re.search(pattern, combined_text, re.IGNORECASE):
            return True, "新国脉", 15
    
    # 模式2: 工作简历中最后一段工作经历是内部单位且时间包含"至今/迄今"
    # 检查工作简历部分
    work_exp_section = ""
    if '工作简历' in combined_text or '工作经历' in combined_text:
        # 提取工作简历部分
        lines = combined_text.split('\n')
        in_work_section = False
        for line in lines:
            if '工作简历' in line or '工作经历' in line:
                in_work_section = True
            elif in_work_section and line.strip() and ('教育' in line or '家庭' in line or '受过' in line):
                break
            if in_work_section:
                work_exp_section += line + "\n"
    
    # 在工作简历中查找"至今"或"迄今"且包含内部单位
    internal_units = [
        ("新国脉", ["新国脉数字文化", "新国脉"], 15),
        ("号百控股", ["号百控股"], 15),  # 号百控股是新国脉的前身/关联公司
        ("中国电信", ["中国电信", "上海电信"], 10),
        ("中国联通", ["中国联通", "上海联通"], 10),
        ("中国移动", ["中国移动"], 10),
    ]
    
    for company, keywords, bonus in internal_units:
        for keyword in keywords:
            # 查找包含"至今"或"迄今"且包含内部单位名称的行
            pattern1 = rf'{keyword}.*(?:至今|迄今|现在|当前)'
            pattern2 = rf'(?:至今|迄今|现在|当前).*{keyword}'
            if re.search(pattern1, work_exp_section, re.IGNORECASE) or \
               re.search(pattern2, work_exp_section, re.IGNORECASE):
                return True, company, bonus
    
    # 检查是否有内部单位工作经历（不限制时间）
    for company, keywords, bonus in internal_units:
        for keyword in keywords:
            if keyword in combined_text:
                # 有内部单位工作经历，但不确定是否当前在职
                return True, company, 5
    
    return False, "", 0


def adjust_scores_for_differentiation(evaluation: Dict[str, Any], resume_text: str, transcript: str) -> Dict[str, Any]:
    """
    强制分数差异化调整 - 确保评分有区分度
    参考interview_evaluation_routes.py中的逻辑
    """
    if not evaluation:
        return evaluation
    
    dimensions = evaluation.get("dimensions", [])
    if not dimensions:
        return evaluation
    
    # 检测是否是内部候选人
    is_internal, company_name, bonus_points = is_internal_candidate(resume_text, transcript)
    
    if is_internal:
        logger.info(f"[干部评估] 检测到内部候选人，单位: {company_name}, 加分: {bonus_points}")
        # 内部候选人在工作经验维度加分
        for dim in dimensions:
            if dim.get("name") == "工作经验":
                old_score = dim.get("score", 0)
                new_score = min(100, old_score + bonus_points)
                dim["score"] = new_score
                dim["analysis"] = f"【内部员工加分+{bonus_points}】{dim.get('analysis', '')}"
                logger.info(f"[干部评估] 工作经验维度加分: {old_score} -> {new_score}")
                break
    
    # 重新计算综合得分
    total_weight = sum(dim.get("weight", 0) for dim in dimensions)
    if total_weight > 0:
        overall_score = sum(dim.get("score", 0) * dim.get("weight", 0) for dim in dimensions) / total_weight
        evaluation["overall_score"] = round(overall_score)
    
    # 更新评价等级
    overall_score = evaluation.get("overall_score", 0)
    if overall_score >= 90:
        evaluation["evaluation_level"] = "优秀"
    elif overall_score >= 80:
        evaluation["evaluation_level"] = "良好"
    elif overall_score >= 60:
        evaluation["evaluation_level"] = "一般"
    else:
        evaluation["evaluation_level"] = "较差"
    
    return evaluation


# ============ 辅助函数 ============

def load_structured_questions(project_dir: str) -> List[Dict[str, Any]]:
    """加载结构化面试问题"""
    try:
        # 查找面试结构化问题.xlsx文件
        xlsx_file = os.path.join(project_dir, "面试结构化问题.xlsx")
        if not os.path.exists(xlsx_file):
            # 尝试其他可能的位置
            for root, dirs, files in os.walk(project_dir):
                for file in files:
                    if "结构化" in file and file.endswith(".xlsx"):
                        xlsx_file = os.path.join(root, file)
                        break
        
        if not os.path.exists(xlsx_file) or not PANDAS_AVAILABLE:
            return []
        
        # 读取Excel文件，跳过第一行（可能是标题），使用第二行作为表头
        df = pd.read_excel(xlsx_file, header=1)
        questions = []
        
        logger.info(f"Excel列名: {list(df.columns)}")
        logger.info(f"Excel行数: {len(df)}")
        
        # 解析问题列表
        for idx, row in df.iterrows():
            # 查找面试问题列 - 支持多种可能的列名
            question_text = None
            dimension = "通用"
            
            # 遍历所有列查找问题文本
            for col in df.columns:
                col_str = str(col)
                # 查找包含"问题"的列
                if '问题' in col_str or 'question' in col_str.lower():
                    val = row[col]
                    if pd.notna(val) and len(str(val).strip()) > 5:
                        question_text = str(val).strip()
                        break
            
            # 如果没找到，尝试所有列，找最长的文本作为问题
            if not question_text:
                for col in df.columns:
                    val = row[col]
                    if pd.notna(val):
                        text = str(val).strip()
                        if len(text) > 10 and '?' in text:  # 包含问号的问题
                            question_text = text
                            break
            
            # 查找维度/考核模块
            for col in df.columns:
                col_str = str(col)
                if '维度' in col_str or '考核' in col_str or '模块' in col_str:
                    val = row[col]
                    if pd.notna(val):
                        dim_text = str(val).strip()
                        if dim_text and dim_text.lower() != 'nan':
                            dimension = dim_text
                            break
            
            if question_text and len(question_text) > 5:
                questions.append({
                    "id": len(questions) + 1,
                    "question": question_text,
                    "dimension": dimension,
                    "category": "结构化面试"
                })
        
        logger.info(f"加载结构化面试问题: {len(questions)} 个")
        return questions
    except Exception as e:
        logger.error(f"加载结构化面试问题失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


async def extract_qa_by_questions(transcript: str, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    根据结构化问题从转录文本中提取问答对，并调用大模型进行总结
    
    流程：
    1. 从结构化问题中提炼核心问题
    2. 在转录文本中查找对应答案
    3. 调用大模型凝练答案（去除口语化、结构化呈现）
    """
    if not transcript or not questions:
        return []
    
    qa_pairs = []
    
    for q in questions:
        question_text = q.get("question", "")
        if not question_text:
            continue
        
        # 步骤1：提炼问题的核心要点（去除冗余描述）
        condensed_question = await condense_question_with_llm(question_text)
        
        # 步骤2：提取问题的关键词进行匹配
        question_keywords = extract_keywords(condensed_question)
        
        # 步骤3：在转录文本中查找答案
        raw_answer = find_answer_in_transcript(transcript, condensed_question, question_keywords)
        
        # 步骤4：调用大模型凝练答案
        condensed_answer = ""
        if raw_answer and len(raw_answer) > 50:
            try:
                condensed_answer = await condense_answer_with_llm(condensed_question, raw_answer)
            except Exception as e:
                logger.error(f"凝练答案失败: {e}")
                condensed_answer = raw_answer[:200] + "..." if len(raw_answer) > 200 else raw_answer
        else:
            condensed_answer = raw_answer if raw_answer else "[该问题在录音中未找到明确回答]"
        
        qa_pairs.append({
            "question": condensed_question,  # 使用凝练后的问题
            "question_original": question_text,  # 保留原始问题
            "answer": condensed_answer,
            "answer_raw": raw_answer,  # 保留原始答案
            "answer_summary": condensed_answer[:150] + "..." if len(condensed_answer) > 150 else condensed_answer,
            "dimension": q.get("dimension", "通用"),
            "category": q.get("category", "结构化面试"),
            "evaluation_points": "根据候选人回答评估",
            "score": None,
            "evaluation": ""
        })
    
    return qa_pairs


async def condense_question_with_llm(question: str) -> str:
    """调用大模型凝练问题，去除冗余描述，提取核心问题"""
    try:
        from app.services.interview_services import call_qwen_api
        
        prompt = f"""你是一位专业的面试问题提炼专家。请将以下结构化面试问题进行凝练，去除冗余描述，提取核心问题。

## 原始问题（可能包含背景描述、考察要点等冗余信息）
{question}

## 你的任务
请将上述问题提炼成**简洁、明确、直接**的核心问题：
1. **去除背景描述**：删除岗位背景、考察目的等说明性文字
2. **去除考察要点**：删除"考察...能力"、"了解...情况"等评价性描述  
3. **保留核心问题**：只保留候选人需要回答的具体问题
4. **控制长度**：凝练后的问题控制在30-80字之间

## 示例
原始问题："请候选人结合过往工作经历，谈谈对积分运营工作的理解，重点考察其对积分业务模式的认知深度、对用户需求的洞察力以及对积分运营核心逻辑的掌握程度，时间3分钟。"
凝练后："请谈谈您对积分运营工作的理解，包括业务模式、用户需求洞察和运营核心逻辑。"

## 输出格式
直接输出凝练后的问题文字，不要有任何前缀说明或解释。"""

        response = await call_qwen_api(prompt, temperature=0.3, max_tokens=200)
        
        if response:
            # 清理响应内容
            condensed = response.strip()
            # 移除可能的引号
            if condensed.startswith('"') and condensed.endswith('"'):
                condensed = condensed[1:-1]
            if condensed.startswith("'") and condensed.endswith("'"):
                condensed = condensed[1:-1]
            return condensed if condensed else question
        
        return question
        
    except Exception as e:
        logger.error(f"调用LLM凝练问题失败: {e}")
        return question


async def condense_answer_with_llm(question: str, answer: str) -> str:
    """调用大模型凝练答案"""
    try:
        from app.services.interview_services import call_qwen_api
        
        prompt = f"""你是一位专业的面试记录整理专家。请将候选人的面试回答进行凝练总结。

## 原始问题
{question}

## 候选人的原始回答（可能包含口语化表达、重复内容、语气词等）
{answer[:1500]}  # 限制长度避免超出token限制

## 你的任务
请将上述回答整理成一段**简洁、专业、逻辑清晰**的文字：
1. **去除口语化表达**：删除"嗯"、"啊"、"这个"、"那个"等语气词
2. **去除重复内容**：合并重复表达，保留核心信息
3. **结构化呈现**：按逻辑顺序组织内容（背景->做法->结果）
4. **保留关键信息**：保留具体数据、案例、成果等重要信息
5. **控制长度**：凝练后的回答控制在150-300字之间

## 输出格式
直接输出凝练后的回答文字，不要有任何前缀说明或解释。"""

        response = await call_qwen_api(prompt, temperature=0.3, max_tokens=800)
        
        if response:
            # 清理响应内容
            condensed = response.strip()
            # 移除可能的引号
            if condensed.startswith('"') and condensed.endswith('"'):
                condensed = condensed[1:-1]
            if condensed.startswith("'") and condensed.endswith("'"):
                condensed = condensed[1:-1]
            return condensed
        
        return answer[:300] + "..." if len(answer) > 300 else answer
        
    except Exception as e:
        logger.error(f"调用LLM凝练答案失败: {e}")
        return answer[:300] + "..." if len(answer) > 300 else answer


def extract_keywords(question: str) -> List[str]:
    """从问题中提取关键词"""
    # 去掉常见的疑问词和标点
    stop_words = ['什么', '怎么', '如何', '为什么', '吗', '呢', '请', '您', '你', '的', '是', '有', '在', '及', '对', '并', '与', '为', '了', '从']
    
    # 提取问题中的关键短语
    keywords = []
    
    # 如果问题很长，取前30个字符作为核心
    if len(question) > 30:
        keywords.append(question[:30])
    
    # 提取包含数字、专业术语的部分
    import re
    # 匹配专业术语（如：薪酬、预算、绩效等）
    professional_terms = re.findall(r'(薪酬|绩效|预算|激励|股权|期权|福利|成本|工资|考核|管理|制度|体系|方案|调研|分析|数据|财务|业务|部门|团队|项目|经验|案例|背景|学历|能力|沟通|协调|领导|决策|战略|规划|目标|指标|流程|标准|规范|制度|政策|市场|行业|竞争|趋势|变化|发展|创新|优化|改进|提升|解决|处理|应对|挑战|困难|压力|冲突|风险|机会|优势|劣势|特点|特征|性质|类型|模式|方法|手段|途径|渠道|资源|条件|环境|氛围|文化|价值观|理念|愿景|使命|责任|义务|权利|利益|关系|网络|平台|系统|工具|技术|技能|知识|信息|数据|资料|文件|报告|方案|计划|总结|汇报|反馈|评价|考核|评估|鉴定|认证|资格|资质|证书|职称|职务|岗位|职位|职责|任务|工作|业务|项目|产品|服务|客户|用户|市场|销售|营销|推广|宣传|品牌|形象|声誉|口碑|影响|效果|成果|业绩|成绩|贡献|价值|意义|作用|功能|用途|目的|目标|方向|重点|关键|核心|基础|根本|本质|实质|内容|形式|结构|框架|体系|系统|机制|体制|模式|方式|方法|手段|工具|技术|技巧|诀窍|秘诀|窍门|门道|套路|招式|打法|战法|战术|战略|策略|谋略|筹划|规划|计划|方案|设计|构思|设想|想法|观点|看法|意见|建议|提议|倡议|主张|立场|态度|观点|角度|层面|维度|方面|领域|范围|范畴|界限|边界|边缘|外围|内部|外部|表面|深层|本质|实质|核心|关键|重点|要点|难点|疑点|热点|焦点|亮点|特点|优点|缺点|长处|短处|优势|劣势|强项|弱项|亮点|盲点|误区|陷阱|坑|雷|炸弹|火药桶|定时炸弹|隐患|风险|危机|危险|威胁|挑战|考验|磨练|锻炼|成长|进步|提升|提高|改善|改进|优化|完善|健全|规范|标准|统一|一致|协调|配合|协作|合作|协同|联动|互动|交流|沟通|联络|联系|关系|往来|交往|交际|社交|应酬|接待|招待|服务|帮助|支持|协助|援助|救助|救援|支援|赞助|资助|捐赠|捐献|奉献|贡献|付出|投入|投资|出资|融资|筹资|募捐|筹集|征集|收集|搜集|采集|采摘|捕获|捕捉|抓住|把握|掌握|控制|管理|治理|统治|管辖|管辖|管理|经营|运营|运作|运行|运转|转动|移动|运动|活动|行动|行为|作为|做法|办法|措施|举措|手段|方式|方法|途径|渠道|路径|路线|方向|方位|位置|地点|场所|场合|场景|情景|情境|环境|背景|条件|前提|基础|基石|根基|根本|本质|实质|核心|中心|重心|重点|焦点|热点|亮点|特点|优点|缺点|优势|劣势)', question)
    keywords.extend(professional_terms)
    
    return keywords[:5]  # 最多返回5个关键词


def find_answer_in_transcript(transcript: str, question: str, keywords: List[str]) -> str:
    """在转录文本中查找问题的答案"""
    if not transcript:
        return ""
    
    # 将转录文本按句子分割
    sentences = re.split(r'[。！？\n]+', transcript)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    
    # 方法1: 查找包含问题关键词的句子
    matching_sentences = []
    for sentence in sentences:
        sentence_lower = sentence.lower()
        # 检查是否包含问题的核心内容
        match_score = 0
        for keyword in keywords:
            if keyword.lower() in sentence_lower:
                match_score += 1
        if match_score > 0:
            matching_sentences.append((sentence, match_score))
    
    # 按匹配度排序
    matching_sentences.sort(key=lambda x: x[1], reverse=True)
    
    # 方法2: 如果找不到匹配，尝试提取候选人的陈述性内容
    if not matching_sentences:
        # 提取候选人的长句回答（可能是对问题的回答）
        for sentence in sentences:
            # 过滤掉太短的句子
            if len(sentence) > 20:
                # 排除问候语、自我介绍等
                if not any(word in sentence for word in ['你好', '您好', '谢谢', '再见', '我是', '我叫']):
                    matching_sentences.append((sentence, 1))
    
    # 返回最匹配的句子，最多返回3个
    if matching_sentences:
        top_answers = [s[0] for s in matching_sentences[:3]]
        return '。'.join(top_answers) + '。'
    
    return ""


async def save_qa_result(project: str, candidate_name: str, qa_pairs: List[dict], questions: List[dict], evaluation_type: str = None):
    """保存问答对结果"""
    try:
        project_dir = get_project_dir(project, evaluation_type)
        qa_dir = os.path.join(project_dir, "qa_cache")
        os.makedirs(qa_dir, exist_ok=True)
        qa_file = os.path.join(qa_dir, f"{candidate_name}.json")
        result = {
            "qa_pairs": qa_pairs,
            "questions": questions,
            "timestamp": datetime.now().isoformat()
        }
        with open(qa_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存问答对失败: {e}")
