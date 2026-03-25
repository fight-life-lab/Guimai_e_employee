"""
AI面试评价 WebSocket 路由 - 实时推送处理进度
"""

import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio

from app.api.interview_evaluation_routes_v2 import (
    analyze_jd_requirements,
    evaluate_candidate_vs_jd,
    evaluate_question_answers,
    check_authenticity,
    find_prestored_asr,
    read_interview_questions,
    EVALUATION_DIMENSIONS
)
from app.services.file_parser import get_file_parser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws/interview-evaluation", tags=["AI面试评价WebSocket"])


async def send_progress(websocket: WebSocket, step: str, percent: int, message: str):
    """发送进度更新"""
    await websocket.send_json({
        "type": "progress",
        "step": step,
        "percent": percent,
        "message": message
    })


async def send_result(websocket: WebSocket, result: Dict[str, Any]):
    """发送最终结果"""
    await websocket.send_json({
        "type": "result",
        "data": result
    })


async def send_error(websocket: WebSocket, error: str):
    """发送错误信息"""
    await websocket.send_json({
        "type": "error",
        "error": error
    })


@router.websocket("/evaluate")
async def websocket_evaluate(websocket: WebSocket):
    """WebSocket 实时面试评价"""
    await websocket.accept()
    
    try:
        # 接收初始数据
        data = await websocket.receive_json()
        
        jd_content = data.get("jd_content", "")
        resume_content = data.get("resume_content", "")
        candidate_name = data.get("candidate_name", "")
        jd_title = data.get("jd_title", "")
        transcript_text = data.get("transcript", "")  # 可选：直接传入转录文本
        questions_data = data.get("questions", [])
        
        # 验证必要参数
        if not jd_content or not resume_content:
            await send_error(websocket, "请提供JD内容和简历内容")
            return
        
        await send_progress(websocket, "init", 5, "初始化...")
        
        # 1. 获取转录文本
        transcript = transcript_text
        if not transcript and candidate_name:
            await send_progress(websocket, "transcript", 10, "查找预存转录数据...")
            transcript, _ = find_prestored_asr(candidate_name)
        
        if not transcript:
            await send_error(websocket, "未找到转录数据，请先上传音频或提供转录文本")
            return
        
        await send_progress(websocket, "transcript", 15, "转录数据准备完成")
        
        # 2. 解析面试问题
        questions = []
        if questions_data:
            questions = [read_interview_questions(q) for q in questions_data]
        if not questions:
            questions = [{"category": "通用", "question": "请介绍工作经历", "evaluation_points": "考察经验"}]
        
        # 3. 并行执行JD分析和候选人评估
        await send_progress(websocket, "jd_analysis", 20, "分析JD岗位要求...")
        jd_analysis = await analyze_jd_requirements(jd_content)
        await send_progress(websocket, "jd_analysis", 35, "JD分析完成")
        
        await send_progress(websocket, "candidate_eval", 40, "评估候选人表现...")
        candidate_eval = await evaluate_candidate_vs_jd(
            jd_content=jd_content,
            resume_content=resume_content,
            transcript=transcript,
            jd_dimensions=jd_analysis.get("dimensions", [])
        )
        await send_progress(websocket, "candidate_eval", 60, "候选人评估完成")
        
        # 4. 并行执行问题评估和真伪验证
        await send_progress(websocket, "question_eval", 65, "评估问题回答...")
        question_answers = await evaluate_question_answers(transcript, questions)
        await send_progress(websocket, "question_eval", 80, "问题评估完成")
        
        await send_progress(websocket, "authenticity", 82, "进行真伪验证...")
        authenticity = await check_authenticity(resume_content, transcript)
        await send_progress(websocket, "authenticity", 95, "真伪验证完成")
        
        # 5. 组装结果
        await send_progress(websocket, "finalize", 98, "生成报告...")
        
        result = {
            "success": True,
            "jd_analysis": jd_analysis,
            "jd_dimensions": jd_analysis.get("dimensions", []),
            "candidate_dimensions": candidate_eval.get("dimensions", []),
            "overall_score": candidate_eval.get("overall_score", 0),
            "evaluation_level": candidate_eval.get("evaluation_level", "未知"),
            "question_answers": question_answers,
            "authenticity_check": authenticity,
            "summary": candidate_eval.get("summary", ""),
            "strengths": candidate_eval.get("strengths", []),
            "recommendations": candidate_eval.get("recommendations", [])
        }
        
        await send_progress(websocket, "complete", 100, "完成！")
        await send_result(websocket, result)
        
    except WebSocketDisconnect:
        logger.info("[面试评价WebSocket] 客户端断开连接")
    except Exception as e:
        logger.error(f"[面试评价WebSocket] 错误: {e}")
        await send_error(websocket, str(e))
    finally:
        try:
            await websocket.close()
        except:
            pass
