"""
AI面试评价API路由 - 优化版本
- 流式响应支持，实时返回进度
- 并行API调用优化
- WebSocket支持
- 分块上传支持（解决大文件上传问题）
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any, AsyncGenerator
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import aiohttp
import openpyxl

from app.services.file_parser import get_file_parser
from app.services.cache_service import cache_service
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/eval", tags=["AI面试评价优化"])


# ============ 测试端点 ============
@router.get("/test")
async def test_endpoint():
    """测试端点，用于验证API路由是否正常工作"""
    return {"status": "ok", "message": "面试评价API正常工作", "timestamp": datetime.now().isoformat()}


# ============ 配置 ============
WHISPER_API_URL = "http://localhost:8003/transcribe"

# ============ 数据模型 ============

class QuestionItem(BaseModel):
    """面试问题项"""
    category: str = Field(..., description="问题类别")
    question: str = Field(..., description="问题内容")
    evaluation_points: str = Field(..., description="评价要点")


class DimensionScore(BaseModel):
    """维度得分"""
    dimension: str = Field(..., description="维度名称")
    score: float = Field(..., description="得分")
    weight: float = Field(..., description="权重")
    weighted_score: float = Field(..., description="加权得分")
    evaluation: str = Field(..., description="评价说明")


class InterviewEvaluationResponse(BaseModel):
    """面试评价响应"""
    success: bool = Field(..., description="是否成功")
    candidate_name: str = Field(..., description="候选人姓名")
    jd_title: str = Field(..., description="岗位名称")
    overall_score: float = Field(..., description="综合得分")
    match_level: str = Field(..., description="匹配等级")
    dimensions: List[DimensionScore] = Field(default=[], description="各维度得分（兼容旧版本）")
    jd_dimensions: List[DimensionScore] = Field(default=[], description="岗位维度要求")
    candidate_dimensions: List[DimensionScore] = Field(default=[], description="候选人维度表现")
    question_answers: List[Dict[str, Any]] = Field(..., description="问题回答评价")
    overall_evaluation: str = Field(..., description="综合评价")
    recommendations: List[str] = Field(..., description="建议")


class InterviewEvaluationRequest(BaseModel):
    """面试评价请求（Base64编码方式）"""
    jd_content: Optional[str] = Field(None, description="JD文本内容")
    jd_file_base64: Optional[str] = Field(None, description="JD文件Base64编码")
    jd_file_name: Optional[str] = Field(None, description="JD文件名")
    resume_content: Optional[str] = Field(None, description="简历文本内容")
    resume_file_base64: Optional[str] = Field(None, description="简历文件Base64编码")
    resume_file_name: Optional[str] = Field(None, description="简历文件名")
    audio_file_base64: Optional[str] = Field(None, description="音频文件Base64编码")
    audio_file_name: Optional[str] = Field(None, description="音频文件名")
    questions_file_base64: Optional[str] = Field(None, description="问题文件Base64编码")
    questions_file_name: Optional[str] = Field(None, description="问题文件名")
    candidate_name: Optional[str] = Field("", description="候选人姓名")
    jd_title: Optional[str] = Field("", description="岗位名称")
    prompt_template: Optional[str] = Field("标准", description="提示模板类型")
    temperature: Optional[float] = Field(0.3, description="温度系数")


class FileUploadRequest(BaseModel):
    """文件上传请求（Base64编码方式）"""
    filename: str
    file_type: str  # jd, resume, audio, questions
    file_content_base64: str


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    success: bool
    message: str
    file_path: Optional[str] = None
    file_type: Optional[str] = None


class ChunkUploadRequest(BaseModel):
    """分块上传请求"""
    upload_id: str
    file_name: str
    file_type: str  # jd, resume, audio, questions
    chunk_index: int
    total_chunks: int
    chunk_data: str  # Base64编码的块数据


class ChunkUploadResponse(BaseModel):
    """分块上传响应"""
    success: bool
    message: str
    file_path: Optional[str] = None


class InterviewEvaluationByPathRequest(BaseModel):
    """使用文件路径的面试评价请求"""
    jd_content: Optional[str] = Field(None, description="JD文本内容")
    resume_content: Optional[str] = Field(None, description="简历文本内容")
    jd_file_path: Optional[str] = Field(None, description="JD文件路径")
    resume_file_path: Optional[str] = Field(None, description="简历文件路径")
    audio_file_path: Optional[str] = Field(None, description="音频文件路径")
    questions_file_path: Optional[str] = Field(None, description="问题文件路径")
    candidate_name: Optional[str] = Field("", description="候选人姓名")
    jd_title: Optional[str] = Field("", description="岗位名称")
    temperature: Optional[float] = Field(0.3, description="温度系数")


# ============ 全局变量 ============
# 存储分块上传的临时数据
chunk_uploads = {}


# ============ 工具函数 ============

def read_interview_questions(file_path: str) -> List[QuestionItem]:
    """读取结构化面试问题"""
    questions = []
    try:
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
        
        # 假设第一行是表头
        for row in ws.iter_rows(min_row=2, values_only=True):
            if len(row) >= 3 and row[0] and row[1]:
                questions.append(QuestionItem(
                    category=str(row[0]),
                    question=str(row[1]),
                    evaluation_points=str(row[2]) if row[2] else ""
                ))
    except Exception as e:
        logger.error(f"读取面试问题文件失败: {e}")
    
    return questions


def find_prestored_asr(candidate_name: str) -> tuple:
    """查找预存的ASR转录数据"""
    settings = get_settings()
    # ASR数据存储在 transcriptions 目录中，格式为 JSON
    asr_dir = os.path.join(settings.BASE_DIR, "data", "transcriptions")
    
    if not os.path.exists(asr_dir):
        return None, None
    
    # 尝试查找匹配的文件（支持 .json 格式）
    for filename in os.listdir(asr_dir):
        if candidate_name in filename and filename.endswith('.json'):
            file_path = os.path.join(asr_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 如果JSON中有text字段，返回text，否则返回整个JSON字符串
                    if isinstance(data, dict) and 'text' in data:
                        return data['text'], file_path
                    else:
                        return json.dumps(data, ensure_ascii=False), file_path
            except Exception as e:
                logger.error(f"[ASR] 读取文件失败 {file_path}: {e}")
                pass
    
    return None, None


def get_interview_upload_dir():
    """获取面试评价文件上传目录"""
    settings = get_settings()
    upload_dir = os.path.join(settings.BASE_DIR, "data", "interview_files")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


async def generate_streaming_response(
    jd_text: str,
    resume_text: str,
    transcript: str,
    questions: List[QuestionItem],
    candidate_name: str,
    jd_title: str,
    temperature: float
) -> AsyncGenerator[str, None]:
    """生成流式响应"""
    
    try:
        settings = get_settings()
        
        # 发送开始事件
        yield f"data: {json.dumps({'type': 'progress', 'progress': 10, 'message': '正在分析问题...'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.1)
        
        # 构建提示词
        questions_text = "\n".join([f"{i+1}. [{q.category}] {q.question}\n   评价要点: {q.evaluation_points}" 
                                     for i, q in enumerate(questions)])
        
        prompt = f"""请根据以下JD、简历和面试录音转录文本，对候选人进行综合评价。

岗位JD:
{jd_text[:2000]}

候选人简历:
{resume_text[:2000]}

面试录音转录:
{transcript[:3000]}

结构化面试问题:
{questions_text}

请从以下维度进行评价，每个维度给出得分（0-100）和评价说明：
1. 专业能力匹配度 - 考察专业技能与岗位要求的匹配程度
2. 工作经验相关性 - 考察工作经验与岗位的相关性
3. 沟通表达能力 - 考察语言组织和表达清晰度
4. 逻辑思维 - 考察分析问题和解决问题的思路
5. 学习能力 - 考察学习意愿和知识更新能力
6. 职业素养 - 考察职业态度和价值观

请按以下JSON格式返回结果，需要包含两个维度的数据：
{{
    "overall_score": 85,
    "match_level": "优秀匹配",
    "jd_dimensions": [
        {{"dimension": "专业能力", "score": 90, "weight": 0.25, "weighted_score": 22.5, "evaluation": "岗位要求的专业技能水平"}},
        {{"dimension": "工作经验", "score": 85, "weight": 0.20, "weighted_score": 17.0, "evaluation": "岗位要求的经验水平"}},
        {{"dimension": "沟通表达", "score": 80, "weight": 0.15, "weighted_score": 12.0, "evaluation": "岗位要求的沟通能力"}},
        {{"dimension": "逻辑思维", "score": 85, "weight": 0.15, "weighted_score": 12.75, "evaluation": "岗位要求的思维能力"}},
        {{"dimension": "学习能力", "score": 75, "weight": 0.15, "weighted_score": 11.25, "evaluation": "岗位要求的学习能力"}},
        {{"dimension": "综合素质", "score": 85, "weight": 0.10, "weighted_score": 8.5, "evaluation": "岗位要求的综合素质"}}
    ],
    "candidate_dimensions": [
        {{"dimension": "专业能力", "score": 85, "weight": 0.25, "weighted_score": 21.25, "evaluation": "候选人的专业技能表现"}},
        {{"dimension": "工作经验", "score": 80, "weight": 0.20, "weighted_score": 16.0, "evaluation": "候选人的经验匹配度"}},
        {{"dimension": "沟通表达", "score": 85, "weight": 0.15, "weighted_score": 12.75, "evaluation": "候选人的沟通表现"}},
        {{"dimension": "逻辑思维", "score": 80, "weight": 0.15, "weighted_score": 12.0, "evaluation": "候选人的思维表现"}},
        {{"dimension": "学习能力", "score": 90, "weight": 0.15, "weighted_score": 13.5, "evaluation": "候选人的学习能力"}},
        {{"dimension": "综合素质", "score": 85, "weight": 0.10, "weighted_score": 8.5, "evaluation": "候选人的综合素质"}}
    ],
    "question_answers": [
        {{"question": "问题内容", "answer_summary": "回答摘要", "score": 85, "evaluation": "评价"}},
        ...
    ],
    "overall_evaluation": "综合评价说明",
    "recommendations": ["建议1", "建议2", ...]
}}

注意：
- jd_dimensions 表示岗位对各维度的要求水平
- candidate_dimensions 表示候选人在各维度的实际表现
- 两个数组的维度名称和weight必须一致
- 必须包含 weighted_score 字段（score * weight）
"""
        
        # 发送进度
        yield f"data: {json.dumps({'type': 'progress', 'progress': 30, 'message': '正在调用AI模型...'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.1)
        
        # 调用大模型
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": settings.remote_llm_model,
                "messages": [
                    {"role": "system", "content": "你是一个专业的HR面试官，擅长评估候选人与岗位的匹配度。请严格按照要求的JSON格式返回结果。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": 4000
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.remote_llm_api_key}"
            }

            yield f"data: {json.dumps({'type': 'progress', 'progress': 50, 'message': '正在等待AI响应...'}, ensure_ascii=False)}\n\n"

            async with session.post(
                settings.remote_llm_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=300)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    
                    yield f"data: {json.dumps({'type': 'progress', 'progress': 80, 'message': '正在解析结果...'}, ensure_ascii=False)}\n\n"
                    
                    # 解析JSON结果
                    try:
                        # 提取JSON部分
                        json_start = content.find('{')
                        json_end = content.rfind('}') + 1
                        if json_start >= 0 and json_end > json_start:
                            json_str = content[json_start:json_end]
                            evaluation_data = json.loads(json_str)
                            
                            # 转换维度数据格式，适配前端期望
                            def convert_dimensions(dims):
                                """将后端维度格式转换为前端期望格式"""
                                if not dims:
                                    return []
                                converted = []
                                for d in dims:
                                    converted.append({
                                        "name": d.get("dimension", ""),
                                        "score": d.get("score", 0),
                                        "weight": d.get("weight", 0),
                                        "evaluation": d.get("evaluation", ""),
                                        "gap": 0  # 前端需要gap字段，暂时设为0
                                    })
                                return converted
                            
                            # 处理jd_dimensions和candidate_dimensions
                            jd_dims = evaluation_data.get("jd_dimensions", [])
                            candidate_dims = evaluation_data.get("candidate_dimensions", [])
                            
                            # 计算gap（候选人得分 - JD要求得分）
                            if jd_dims and candidate_dims:
                                jd_map = {d.get("dimension", ""): d.get("score", 0) for d in jd_dims}
                                for d in candidate_dims:
                                    dim_name = d.get("dimension", "")
                                    jd_score = jd_map.get(dim_name, 0)
                                    candidate_score = d.get("score", 0)
                                    d["gap"] = candidate_score - jd_score
                            
                            # 构建最终响应
                            final_result = {
                                "type": "result",
                                "data": {
                                    "success": True,
                                    "candidate_name": candidate_name,
                                    "jd_title": jd_title,
                                    "overall_score": evaluation_data.get("overall_score", 0),
                                    "match_level": evaluation_data.get("match_level", ""),
                                    "jd_dimensions": convert_dimensions(jd_dims),
                                    "candidate_dimensions": convert_dimensions(candidate_dims),
                                    "dimensions": convert_dimensions(candidate_dims),  # 兼容旧版本
                                    "question_answers": evaluation_data.get("question_answers", []),
                                    "overall_evaluation": evaluation_data.get("overall_evaluation", ""),
                                    "recommendations": evaluation_data.get("recommendations", [])
                                }
                            }
                            
                            yield f"data: {json.dumps(final_result, ensure_ascii=False)}\n\n"
                        else:
                            raise ValueError("无法从响应中提取JSON")
                    except Exception as e:
                        logger.error(f"解析评价结果失败: {e}")
                        yield f"data: {json.dumps({'type': 'error', 'message': f'解析结果失败: {str(e)}'}, ensure_ascii=False)}\n\n"
                else:
                    error_text = await response.text()
                    logger.error(f"AI模型调用失败: {response.status}, {error_text}")
                    yield f"data: {json.dumps({'type': 'error', 'message': f'AI模型调用失败: {response.status}'}, ensure_ascii=False)}\n\n"
    
    except Exception as e:
        logger.error(f"流式生成失败: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': f'评价失败: {str(e)}'}, ensure_ascii=False)}\n\n"


# ============ API端点 ============

@router.post("/upload-file", response_model=FileUploadResponse)
async def upload_interview_file(request: FileUploadRequest):
    """
    上传面试评价相关文件（Base64编码方式）
    用于解决大文件上传时的网络限制问题
    """
    import base64
    import uuid
    
    try:
        logger.info(f"[InterviewUpload] 开始处理文件上传: {request.filename}, 类型: {request.file_type}")
        
        # 验证文件类型
        allowed_types = {
            'jd': ['.txt', '.pdf', '.doc', '.docx'],
            'resume': ['.txt', '.pdf', '.doc', '.docx'],
            'audio': ['.wav', '.mp3', '.m4a', '.aac', '.mp4'],
            'questions': ['.xlsx', '.xls', '.csv']
        }
        
        file_ext = os.path.splitext(request.filename)[1].lower()
        
        if request.file_type not in allowed_types:
            return FileUploadResponse(
                success=False,
                message=f"无效的文件类型: {request.file_type}"
            )
        
        if file_ext not in allowed_types[request.file_type]:
            return FileUploadResponse(
                success=False,
                message=f"不支持的文件格式 {file_ext}，请上传 {', '.join(allowed_types[request.file_type])} 格式的文件"
            )
        
        # 解码Base64内容
        try:
            file_content = base64.b64decode(request.file_content_base64)
        except Exception as e:
            return FileUploadResponse(
                success=False,
                message=f"Base64解码失败: {str(e)}"
            )
        
        # 检查文件大小（最大50MB）
        max_size = 50 * 1024 * 1024
        if len(file_content) > max_size:
            return FileUploadResponse(
                success=False,
                message=f"文件大小超过限制（最大50MB）"
            )
        
        # 获取上传目录
        upload_dir = get_interview_upload_dir()
        
        # 生成唯一文件名
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # 保存文件
        logger.info(f"[InterviewUpload] 开始保存文件: {request.filename}, 大小: {len(file_content)} bytes")
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"[InterviewUpload] 文件上传成功: {request.filename} -> {file_path}")
        
        return FileUploadResponse(
            success=True,
            message="文件上传成功",
            file_path=file_path,
            file_type=request.file_type
        )
        
    except Exception as e:
        logger.error(f"[InterviewUpload] 文件上传失败: {e}", exc_info=True)
        return FileUploadResponse(
            success=False,
            message=f"文件上传失败: {str(e)}"
        )


@router.post("/upload-chunk", response_model=ChunkUploadResponse)
async def upload_interview_chunk(request: ChunkUploadRequest):
    """
    分块上传文件
    用于解决大文件上传时的网络限制问题
    """
    import base64
    
    try:
        upload_id = request.upload_id
        chunk_index = request.chunk_index
        total_chunks = request.total_chunks
        
        logger.info(f"[ChunkUpload] 接收分块: upload_id={upload_id}, chunk={chunk_index+1}/{total_chunks}")
        
        # 初始化上传会话
        if upload_id not in chunk_uploads:
            chunk_uploads[upload_id] = {
                'chunks': {},
                'file_name': request.file_name,
                'file_type': request.file_type,
                'total_chunks': total_chunks
            }
        
        # 解码块数据
        try:
            chunk_data = base64.b64decode(request.chunk_data)
        except Exception as e:
            return ChunkUploadResponse(
                success=False,
                message=f"Base64解码失败: {str(e)}"
            )
        
        # 存储块
        chunk_uploads[upload_id]['chunks'][chunk_index] = chunk_data
        
        # 检查是否所有块都已接收
        if len(chunk_uploads[upload_id]['chunks']) == total_chunks:
            # 合并所有块
            file_content = b''.join([chunk_uploads[upload_id]['chunks'][i] for i in range(total_chunks)])
            
            # 验证文件类型
            allowed_types = {
                'jd': ['.txt', '.pdf', '.doc', '.docx'],
                'resume': ['.txt', '.pdf', '.doc', '.docx', '.xlsx', '.xls'],
                'audio': ['.wav', '.mp3', '.m4a', '.aac', '.mp4'],
                'questions': ['.xlsx', '.xls', '.csv']
            }
            
            file_ext = os.path.splitext(request.file_name)[1].lower()
            
            if request.file_type not in allowed_types or file_ext not in allowed_types[request.file_type]:
                del chunk_uploads[upload_id]
                return ChunkUploadResponse(
                    success=False,
                    message=f"不支持的文件类型或格式"
                )
            
            # 保存合并后的文件
            upload_dir = get_interview_upload_dir()
            import uuid
            unique_filename = f"{uuid.uuid4().hex}{file_ext}"
            file_path = os.path.join(upload_dir, unique_filename)
            
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # 清理上传会话
            del chunk_uploads[upload_id]
            
            logger.info(f"[ChunkUpload] 文件合并成功: {request.file_name} -> {file_path}")
            
            return ChunkUploadResponse(
                success=True,
                message="文件上传成功",
                file_path=file_path
            )
        
        # 还有更多块需要接收
        return ChunkUploadResponse(
            success=True,
            message=f"分块 {chunk_index+1}/{total_chunks} 接收成功"
        )
        
    except Exception as e:
        logger.error(f"[ChunkUpload] 分块上传失败: {e}", exc_info=True)
        return ChunkUploadResponse(
            success=False,
            message=f"分块上传失败: {str(e)}"
        )


@router.post("/evaluate-stream-by-path")
async def evaluate_interview_stream_by_path_endpoint(request: InterviewEvaluationByPathRequest):
    """
    AI面试评价 - 使用文件路径的流式响应版本
    配合分块上传使用
    """
    temp_audio_path = None
    
    try:
        settings = get_settings()
        temp_dir = os.path.join(settings.BASE_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # 1. 获取JD内容
        jd_text = request.jd_content or ""
        if request.jd_file_path and os.path.exists(request.jd_file_path):
            try:
                with open(request.jd_file_path, 'rb') as f:
                    jd_content = f.read()
                parsed_jd = get_file_parser().parse_file(jd_content, os.path.basename(request.jd_file_path))
                if parsed_jd:
                    jd_text = parsed_jd
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"无法解析JD文件: {str(e)}")
        
        if not jd_text.strip():
            raise HTTPException(status_code=400, detail="请提供JD内容或上传JD文件")
        
        # 2. 获取简历内容
        resume_text = request.resume_content or ""
        logger.info(f"[DEBUG] resume_file_path: {request.resume_file_path}")
        logger.info(f"[DEBUG] resume_file_path exists: {os.path.exists(request.resume_file_path) if request.resume_file_path else 'N/A'}")
        if request.resume_file_path and os.path.exists(request.resume_file_path):
            try:
                with open(request.resume_file_path, 'rb') as f:
                    resume_content = f.read()
                parsed_resume = get_file_parser().parse_file(resume_content, os.path.basename(request.resume_file_path))
                if parsed_resume:
                    resume_text = parsed_resume
                    logger.info(f"[DEBUG] 简历文件解析成功，长度: {len(resume_text)}")
            except Exception as e:
                logger.error(f"[DEBUG] 简历文件解析失败: {e}")
                raise HTTPException(status_code=400, detail=f"无法解析简历文件: {str(e)}")
        
        if not resume_text.strip():
            logger.error(f"[DEBUG] 简历内容为空，resume_content: {request.resume_content}, resume_file_path: {request.resume_file_path}")
            raise HTTPException(status_code=400, detail="请提供简历内容或上传简历文件")
        
        # 3. 获取转录文本
        transcript = None
        
        # 首先查找预存ASR数据
        if request.candidate_name:
            transcript, _ = find_prestored_asr(request.candidate_name)
        
        # 如果没有预存数据，使用上传的音频文件
        if not transcript and request.audio_file_path and os.path.exists(request.audio_file_path):
            temp_audio_path = request.audio_file_path
            
            # 调用Whisper转录
            import requests as sync_requests
            with open(temp_audio_path, 'rb') as f:
                files = {'audio_file': (os.path.basename(temp_audio_path), f, 'audio/aac')}
                data = {'language': 'zh'}
                response = sync_requests.post(WHISPER_API_URL, files=files, data=data, timeout=300)
            
            if response.status_code == 200:
                result = response.json()
                transcript = result.get('transcript', '')
            else:
                raise HTTPException(status_code=500, detail="音频转录失败")
        
        if not transcript:
            raise HTTPException(status_code=400, detail="未找到预存ASR数据，请上传音频文件")
        
        # 4. 读取结构化面试问题
        questions = []
        if request.questions_file_path and os.path.exists(request.questions_file_path):
            questions = read_interview_questions(request.questions_file_path)
        else:
            default_questions_file = os.path.join(
                settings.BASE_DIR, "data", 
                "综合办（董办）副主任岗位电话面试录音", 
                "结构化面试问题.xlsx"
            )
            if os.path.exists(default_questions_file):
                questions = read_interview_questions(default_questions_file)
        
        if not questions:
            questions = [
                QuestionItem(category="通用", question="请介绍一下你的工作经历", evaluation_points="考察工作经验"),
                QuestionItem(category="通用", question="你为什么选择这个岗位", evaluation_points="考察求职动机"),
                QuestionItem(category="专业", question="请描述一下你在相关领域的专业能力", evaluation_points="考察专业能力")
            ]
        
        # 5. 返回流式响应
        return StreamingResponse(
            generate_streaming_response(
                jd_text, resume_text, transcript, questions,
                request.candidate_name or "", request.jd_title or "", request.temperature
            ),
            media_type="text/event-stream"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[面试评价] 文件路径流式接口失败: {e}")
        raise HTTPException(status_code=500, detail=f"面试评价失败: {str(e)}")


@router.post("/evaluate-stream")
async def evaluate_interview_stream_endpoint(
    jd_content: Optional[str] = Form(None, description="JD文本内容"),
    jd_file: Optional[UploadFile] = File(None, description="JD文件"),
    resume_content: Optional[str] = Form(None, description="简历文本内容"),
    resume_file: Optional[UploadFile] = File(None, description="简历文件"),
    audio_file: Optional[UploadFile] = File(None, description="面试录音文件（可选，如有预存ASR可不传）"),
    questions_file: Optional[UploadFile] = File(None, description="结构化面试问题Excel文件"),
    candidate_name: Optional[str] = Form("", description="候选人姓名"),
    jd_title: Optional[str] = Form("", description="岗位名称"),
    prompt_template: Optional[str] = Form("标准", description="提示模板类型"),
    temperature: Optional[float] = Form(0.3, description="温度系数")
):
    """
    AI面试评价 - 流式响应版本
    实时返回进度更新，解决响应慢的问题
    """
    temp_audio_path = None
    
    try:
        settings = get_settings()
        temp_dir = os.path.join(settings.BASE_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # 1. 获取JD内容
        jd_text = jd_content or ""
        if jd_file:
            content = await jd_file.read()
            parsed_jd = get_file_parser().parse_file(content, jd_file.filename)
            if parsed_jd:
                jd_text = parsed_jd
            else:
                raise HTTPException(status_code=400, detail=f"无法解析JD文件: {jd_file.filename}")
        
        if not jd_text.strip():
            raise HTTPException(status_code=400, detail="请提供JD内容或上传JD文件")
        
        # 2. 获取简历内容
        resume_text = resume_content or ""
        if resume_file:
            content = await resume_file.read()
            parsed_resume = get_file_parser().parse_file(content, resume_file.filename)
            if parsed_resume:
                resume_text = parsed_resume
            else:
                raise HTTPException(status_code=400, detail=f"无法解析简历文件: {resume_file.filename}")
        
        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="请提供简历内容或上传简历文件")
        
        # 3. 获取转录文本
        transcript = None
        
        # 首先查找预存ASR数据
        if candidate_name:
            transcript, _ = find_prestored_asr(candidate_name)
        
        # 如果没有预存数据，使用上传的音频文件
        if not transcript and audio_file:
            audio_content = await audio_file.read()
            temp_audio_path = os.path.join(temp_dir, audio_file.filename)
            with open(temp_audio_path, 'wb') as f:
                f.write(audio_content)
            
            # 调用Whisper转录
            import requests as sync_requests
            with open(temp_audio_path, 'rb') as f:
                files = {'audio_file': (os.path.basename(temp_audio_path), f, 'audio/aac')}
                data = {'language': 'zh'}
                response = sync_requests.post(WHISPER_API_URL, files=files, data=data, timeout=300)
            
            if response.status_code == 200:
                result = response.json()
                transcript = result.get('transcript', '')
            else:
                raise HTTPException(status_code=500, detail="音频转录失败")
        
        if not transcript:
            raise HTTPException(status_code=400, detail="未找到预存ASR数据，请上传音频文件")
        
        # 4. 读取结构化面试问题
        questions = []
        if questions_file:
            questions_content = await questions_file.read()
            temp_questions_path = os.path.join(temp_dir, questions_file.filename)
            with open(temp_questions_path, 'wb') as f:
                f.write(questions_content)
            questions = read_interview_questions(temp_questions_path)
        else:
            default_questions_file = os.path.join(
                settings.BASE_DIR, "data", 
                "综合办（董办）副主任岗位电话面试录音", 
                "结构化面试问题.xlsx"
            )
            if os.path.exists(default_questions_file):
                questions = read_interview_questions(default_questions_file)
        
        if not questions:
            questions = [
                QuestionItem(category="通用", question="请介绍一下你的工作经历", evaluation_points="考察工作经验"),
                QuestionItem(category="通用", question="你为什么选择这个岗位", evaluation_points="考察求职动机"),
                QuestionItem(category="专业", question="请描述一下你在相关领域的专业能力", evaluation_points="考察专业能力")
            ]
        
        # 5. 返回流式响应
        return StreamingResponse(
            generate_streaming_response(
                jd_text, resume_text, transcript, questions,
                candidate_name, jd_title, temperature
            ),
            media_type="text/event-stream"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[面试评价] 流式接口失败: {e}")
        raise HTTPException(status_code=500, detail=f"面试评价失败: {str(e)}")
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except:
                pass


@router.post("/evaluate-stream-base64")
async def evaluate_interview_stream_base64_endpoint(request: InterviewEvaluationRequest):
    """
    AI面试评价 - 流式响应版本（Base64编码方式）
    用于解决大文件上传时的网络限制问题
    """
    import base64
    
    temp_audio_path = None
    temp_jd_path = None
    temp_resume_path = None
    temp_questions_path = None
    
    try:
        settings = get_settings()
        temp_dir = os.path.join(settings.BASE_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # 1. 获取JD内容
        jd_text = request.jd_content or ""
        if request.jd_file_base64 and request.jd_file_name:
            try:
                jd_content = base64.b64decode(request.jd_file_base64)
                temp_jd_path = os.path.join(temp_dir, request.jd_file_name)
                with open(temp_jd_path, 'wb') as f:
                    f.write(jd_content)
                parsed_jd = get_file_parser().parse_file(jd_content, request.jd_file_name)
                if parsed_jd:
                    jd_text = parsed_jd
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"无法解析JD文件: {str(e)}")
        
        if not jd_text.strip():
            raise HTTPException(status_code=400, detail="请提供JD内容或上传JD文件")
        
        # 2. 获取简历内容
        resume_text = request.resume_content or ""
        if request.resume_file_base64 and request.resume_file_name:
            try:
                resume_content = base64.b64decode(request.resume_file_base64)
                temp_resume_path = os.path.join(temp_dir, request.resume_file_name)
                with open(temp_resume_path, 'wb') as f:
                    f.write(resume_content)
                parsed_resume = get_file_parser().parse_file(resume_content, request.resume_file_name)
                if parsed_resume:
                    resume_text = parsed_resume
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"无法解析简历文件: {str(e)}")
        
        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="请提供简历内容或上传简历文件")
        
        # 3. 获取转录文本
        transcript = None
        
        # 首先查找预存ASR数据
        if request.candidate_name:
            transcript, _ = find_prestored_asr(request.candidate_name)
        
        # 如果没有预存数据，使用上传的音频文件
        if not transcript and request.audio_file_base64 and request.audio_file_name:
            try:
                audio_content = base64.b64decode(request.audio_file_base64)
                temp_audio_path = os.path.join(temp_dir, request.audio_file_name)
                with open(temp_audio_path, 'wb') as f:
                    f.write(audio_content)
                
                # 调用Whisper转录
                import requests as sync_requests
                with open(temp_audio_path, 'rb') as f:
                    files = {'audio_file': (os.path.basename(temp_audio_path), f, 'audio/aac')}
                    data = {'language': 'zh'}
                    response = sync_requests.post(WHISPER_API_URL, files=files, data=data, timeout=300)
                
                if response.status_code == 200:
                    result = response.json()
                    transcript = result.get('transcript', '')
                else:
                    raise HTTPException(status_code=500, detail="音频转录失败")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"无法处理音频文件: {str(e)}")
        
        if not transcript:
            raise HTTPException(status_code=400, detail="未找到预存ASR数据，请上传音频文件")
        
        # 4. 读取结构化面试问题
        questions = []
        if request.questions_file_base64 and request.questions_file_name:
            try:
                questions_content = base64.b64decode(request.questions_file_base64)
                temp_questions_path = os.path.join(temp_dir, request.questions_file_name)
                with open(temp_questions_path, 'wb') as f:
                    f.write(questions_content)
                questions = read_interview_questions(temp_questions_path)
            except Exception as e:
                logger.error(f"读取面试问题文件失败: {e}")
        else:
            default_questions_file = os.path.join(
                settings.BASE_DIR, "data", 
                "综合办（董办）副主任岗位电话面试录音", 
                "结构化面试问题.xlsx"
            )
            if os.path.exists(default_questions_file):
                questions = read_interview_questions(default_questions_file)
        
        if not questions:
            questions = [
                QuestionItem(category="通用", question="请介绍一下你的工作经历", evaluation_points="考察工作经验"),
                QuestionItem(category="通用", question="你为什么选择这个岗位", evaluation_points="考察求职动机"),
                QuestionItem(category="专业", question="请描述一下你在相关领域的专业能力", evaluation_points="考察专业能力")
            ]
        
        # 5. 返回流式响应
        return StreamingResponse(
            generate_streaming_response(
                jd_text, resume_text, transcript, questions,
                request.candidate_name or "", request.jd_title or "", request.temperature
            ),
            media_type="text/event-stream"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[面试评价] Base64流式接口失败: {e}")
        raise HTTPException(status_code=500, detail=f"面试评价失败: {str(e)}")
    finally:
        # 清理临时文件
        for temp_path in [temp_audio_path, temp_jd_path, temp_resume_path, temp_questions_path]:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
