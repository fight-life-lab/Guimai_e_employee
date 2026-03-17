"""人岗适配评估API路由 - Web对话机器人接口."""

import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.alignment_agent import get_alignment_agent
from app.database.models import get_async_session

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

router = APIRouter(prefix="/api/v1/alignment", tags=["人岗适配评估"])


# ============ 请求/响应模型 ============

class AlignmentAnalysisRequest(BaseModel):
    """人岗适配分析请求."""
    employee_name: str = Field(..., description="员工姓名", min_length=1, max_length=64)
    include_details: bool = Field(True, description="是否包含详细分析")


class AlignmentCompareRequest(BaseModel):
    """人岗适配对比请求."""
    employee_names: List[str] = Field(..., description="员工姓名列表", min_items=2, max_items=10)


class AlignmentChatRequest(BaseModel):
    """对话式人岗适配咨询请求."""
    message: str = Field(..., description="用户消息", min_length=1, max_length=1000)
    session_id: Optional[str] = Field(None, description="会话ID，用于保持上下文")


class AlignmentAnalysisResponse(BaseModel):
    """人岗适配分析响应."""
    employee_name: str
    overall_score: Optional[int] = None
    alignment_level: Optional[str] = None
    dimension_scores: dict = {}
    raw_analysis: str = ""
    analysis_date: str = ""
    error: Optional[str] = None


# ============ API端点 ============

@router.post("/analyze", response_model=AlignmentAnalysisResponse)
async def analyze_employee_alignment(
    request: AlignmentAnalysisRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    分析单个员工的人岗适配情况.
    
    - **employee_name**: 员工姓名
    - **include_details**: 是否包含详细分析（默认true）
    """
    logger.info(f"[人岗适配分析] 开始分析员工: {request.employee_name}")
    start_time = datetime.now()
    
    try:
        agent = get_alignment_agent()
        result = await agent.analyze_employee_alignment(request.employee_name, db)
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[人岗适配分析] 完成分析员工: {request.employee_name}, 耗时: {elapsed_time:.2f}s")
        
        if "error" in result:
            logger.error(f"[人岗适配分析] 分析失败: {result['error']}")
            raise HTTPException(status_code=404 if "未找到" in result["error"] else 500, detail=result["error"])
        
        return AlignmentAnalysisResponse(
            employee_name=result.get("employee_name", request.employee_name),
            overall_score=result.get("overall_score"),
            alignment_level=result.get("alignment_level"),
            dimension_scores=result.get("dimension_scores", {}),
            raw_analysis=result.get("raw_analysis", ""),
            analysis_date=result.get("analysis_date", str(datetime.now().date())),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[人岗适配分析] 分析异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"分析过程中出现错误: {str(e)}")


@router.post("/analyze/stream")
async def analyze_employee_alignment_stream(
    request: AlignmentAnalysisRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    流式分析单个员工的人岗适配情况.
    
    实时返回大模型的分析结果，支持SSE流式输出.
    
    - **employee_name**: 员工姓名
    """
    logger.info(f"[人岗适配分析-流式] 开始分析员工: {request.employee_name}")
    start_time = datetime.now()
    
    async def generate_stream():
        try:
            agent = get_alignment_agent()
            chunk_count = 0
            
            async for chunk in agent.analyze_employee_alignment_stream(request.employee_name, db):
                chunk_count += 1
                # SSE格式: data: {...}\n\n
                yield f"data: {json.dumps({'chunk': chunk, 'index': chunk_count}, ensure_ascii=False)}\n\n"
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"[人岗适配分析-流式] 完成分析员工: {request.employee_name}, 共{chunk_count}个片段, 耗时: {elapsed_time:.2f}s")
            
            # 发送结束标记
            yield f"data: {json.dumps({'done': True, 'total_chunks': chunk_count}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.exception(f"[人岗适配分析-流式] 流式分析异常: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
        }
    )


@router.post("/compare")
async def compare_employees_alignment(
    request: AlignmentCompareRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    对比多个员工的人岗适配情况.
    
    - **employee_names**: 员工姓名列表（2-10人）
    """
    logger.info(f"[人岗适配对比] 开始对比员工: {request.employee_names}")
    start_time = datetime.now()
    
    try:
        agent = get_alignment_agent()
        result = await agent.compare_employees(request.employee_names, db)
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[人岗适配对比] 完成对比, 耗时: {elapsed_time:.2f}s")
        
        if "error" in result:
            logger.error(f"[人岗适配对比] 对比失败: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[人岗适配对比] 对比异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"对比过程中出现错误: {str(e)}")


@router.post("/chat")
async def alignment_chat(
    request: AlignmentChatRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    对话式人岗适配咨询.
    
    支持自然语言询问，例如：
    - "石京京是哪个学校的？"
    - "余祯的绩效怎么样？"
    - "帮我分析一下李四是否适合当前岗位"
    
    - **message**: 用户消息
    - **session_id**: 会话ID（可选）
    """
    logger.info(f"[人岗适配对话] 用户消息: {request.message}")
    start_time = datetime.now()
    
    try:
        agent = get_alignment_agent()
        reply = await agent.chat_about_employee(request.message, db)
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[人岗适配对话] 完成回答, 耗时: {elapsed_time:.2f}s")
        
        return {
            "reply": reply,
            "session_id": request.session_id or "new_session",
        }
        
    except Exception as e:
        logger.exception(f"[人岗适配对话] 对话异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"对话过程中出现错误: {str(e)}")


@router.post("/chat/stream")
async def alignment_chat_stream(
    request: AlignmentChatRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    流式对话式人岗适配咨询.
    
    实时返回大模型的回复，支持SSE流式输出.
    """
    logger.info(f"[人岗适配对话-流式] 用户消息: {request.message}")
    start_time = datetime.now()
    
    async def generate_chat_stream():
        try:
            agent = get_alignment_agent()
            chunk_count = 0
            
            async for chunk in agent.chat_about_employee_stream(request.message, db):
                chunk_count += 1
                yield f"data: {json.dumps({'chunk': chunk, 'index': chunk_count}, ensure_ascii=False)}\n\n"
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"[人岗适配对话-流式] 完成回答, 共{chunk_count}个片段, 耗时: {elapsed_time:.2f}s")
            
            yield f"data: {json.dumps({'done': True, 'total_chunks': chunk_count}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.exception(f"[人岗适配对话-流式] 流式对话异常: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_chat_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============ 健康检查和元数据端点 ============

@router.get("/dimensions")
async def get_alignment_dimensions():
    """获取人岗适配评估维度定义."""
    from app.agent.alignment_agent import ALIGNMENT_DIMENSIONS, SEQUENCE_STANDARDS
    
    return {
        "dimensions": ALIGNMENT_DIMENSIONS,
        "sequence_standards": SEQUENCE_STANDARDS,
    }


@router.get("/health")
async def alignment_health_check():
    """人岗适配服务健康检查."""
    return {
        "status": "healthy",
        "service": "alignment-agent",
        "timestamp": datetime.now().isoformat(),
    }
