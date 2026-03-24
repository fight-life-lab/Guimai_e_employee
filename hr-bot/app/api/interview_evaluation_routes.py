"""
AI面试评价API路由 - 提供面试录音分析和评价接口
音频转录使用 whisper-api，面试评价使用 Qwen3-235B 大模型
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import aiohttp
import openpyxl
import requests

from app.services.file_parser import get_file_parser
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/interview-evaluation", tags=["AI面试评价"])


# ============ 配置 ============

# Whisper API 配置（本地部署）
WHISPER_API_URL = "http://localhost:8003/transcribe"

# Qwen3-235B 大模型配置（全尺寸版本）
QWEN_API_URL = "http://180.97.200.118:30071/v1/chat/completions"
QWEN_API_KEY = "z3oK7bN9xPqW2mT8rYvL5tF1cJ4hD6gA0eS2uI3nQk"
QWEN_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"

# 转录文本保存目录
TRANSCRIPT_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "transcripts")

# 预存 ASR 转录数据目录
PRESTORED_ASR_DIR = "/root/shijingjing/e-employee/hr-bot/data/transcriptions"


# ============ 请求/响应模型 ============

class InterviewEvaluationResponse(BaseModel):
    """面试评价响应"""
    success: bool = Field(..., description="是否成功")
    overall_score: float = Field(..., description="综合面试评分")
    evaluation_level: str = Field(..., description="评价等级")
    dimensions: List[dict] = Field(..., description="各维度评分详情")
    transcript: str = Field(..., description="录音转文本内容")
    summary: str = Field(..., description="面试总结")
    strengths: List[str] = Field(default=[], description="候选人优势")
    weaknesses: List[str] = Field(default=[], description="候选人不足")
    recommendations: List[str] = Field(default=[], description="建议")
    question_answers: List[dict] = Field(default=[], description="问题回答评价")


class QuestionItem(BaseModel):
    """面试问题项"""
    category: str = Field(..., description="问题类别")
    question: str = Field(..., description="问题内容")
    evaluation_points: str = Field(..., description="考察要点")


# ============ 工具函数 ============

def read_interview_questions(excel_path: str) -> List[QuestionItem]:
    """读取结构化面试问题Excel文件"""
    questions = []
    try:
        workbook = openpyxl.load_workbook(excel_path)
        sheet = workbook.active
        
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if len(row) >= 3 and row[0] and row[1]:
                questions.append(QuestionItem(
                    category=str(row[0]) if row[0] else "",
                    question=str(row[1]) if row[1] else "",
                    evaluation_points=str(row[2]) if len(row) > 2 and row[2] else ""
                ))
        
        logger.info(f"[面试评价] 成功读取 {len(questions)} 个面试问题")
        return questions
    except Exception as e:
        logger.error(f"[面试评价] 读取面试问题文件失败: {e}")
        return []


def find_prestored_asr(candidate_name: str) -> tuple:
    """查找预存的 ASR 转录数据
    
    Args:
        candidate_name: 候选人姓名
    
    Returns:
        (transcript, filepath) 元组，如果没有找到返回 (None, None)
    """
    try:
        if not candidate_name:
            return None, None
        
        # 构建 JSON 文件路径
        json_file = os.path.join(PRESTORED_ASR_DIR, f"{candidate_name}.json")
        
        if not os.path.exists(json_file):
            logger.info(f"[面试评价] 未找到预存 ASR 数据: {json_file}")
            return None, None
        
        # 读取 JSON 文件
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 提取转录文本
        transcript = data.get('text', '') or data.get('transcript', '')
        
        if transcript:
            logger.info(f"[面试评价] 找到预存 ASR 数据: {json_file}, 长度: {len(transcript)}")
            return transcript, json_file
        
        return None, None
        
    except Exception as e:
        logger.error(f"[面试评价] 读取预存 ASR 数据失败: {e}")
        return None, None


def find_existing_transcript(candidate_name: str, jd_title: str = "") -> tuple:
    """查找本地是否已有该候选人的转录文本
    
    Args:
        candidate_name: 候选人姓名
        jd_title: 岗位名称（可选）
    
    Returns:
        (transcript, filepath) 元组，如果没有找到返回 (None, None)
    """
    try:
        if not candidate_name:
            return None, None
        
        # 首先查找预存的 ASR 数据
        prestored_transcript, prestored_path = find_prestored_asr(candidate_name)
        if prestored_transcript:
            return prestored_transcript, prestored_path
        
        # 然后查找本地缓存的转录文本
        os.makedirs(TRANSCRIPT_CACHE_DIR, exist_ok=True)
        
        safe_name = candidate_name.replace(" ", "_").replace("/", "_")
        
        # 查找匹配的文件
        matching_files = []
        for filename in os.listdir(TRANSCRIPT_CACHE_DIR):
            if filename.startswith(safe_name) and filename.endswith('.txt'):
                filepath = os.path.join(TRANSCRIPT_CACHE_DIR, filename)
                # 获取文件修改时间
                mtime = os.path.getmtime(filepath)
                matching_files.append((filepath, mtime))
        
        if not matching_files:
            return None, None
        
        # 按修改时间排序，取最新的
        matching_files.sort(key=lambda x: x[1], reverse=True)
        latest_file = matching_files[0][0]
        
        # 读取文件内容
        with open(latest_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取转录文本（跳过头部信息）
        lines = content.split('\n')
        transcript_lines = []
        header_ended = False
        for line in lines:
            if header_ended:
                transcript_lines.append(line)
            elif line.startswith('=' * 50):
                header_ended = True
        
        transcript = '\n'.join(transcript_lines).strip()
        
        logger.info(f"[面试评价] 找到已有转录文本: {latest_file}")
        return transcript, latest_file
        
    except Exception as e:
        logger.error(f"[面试评价] 查找转录文本失败: {e}")
        return None, None


def save_transcript_to_file(candidate_name: str, audio_filename: str, transcript: str, jd_title: str = "") -> str:
    """保存转录文本到本地文件
    
    Args:
        candidate_name: 候选人姓名
        audio_filename: 音频文件名
        transcript: 转录文本
        jd_title: 岗位名称
    
    Returns:
        保存的文件路径
    """
    try:
        # 创建保存目录
        os.makedirs(TRANSCRIPT_CACHE_DIR, exist_ok=True)
        
        # 生成文件名：候选人姓名_岗位_日期.txt
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = candidate_name.replace(" ", "_").replace("/", "_") if candidate_name else "未知候选人"
        safe_jd = jd_title.replace(" ", "_").replace("/", "_")[:20] if jd_title else ""
        
        if safe_jd:
            filename = f"{safe_name}_{safe_jd}_{date_str}.txt"
        else:
            filename = f"{safe_name}_{date_str}.txt"
        
        filepath = os.path.join(TRANSCRIPT_CACHE_DIR, filename)
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"候选人: {candidate_name}\n")
            f.write(f"音频文件: {audio_filename}\n")
            f.write(f"岗位: {jd_title}\n")
            f.write(f"转录时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            f.write(transcript)
        
        logger.info(f"[面试评价] 转录文本已保存到: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"[面试评价] 保存转录文本失败: {e}")
        return ""


async def transcribe_audio_with_whisper(audio_path: str, language: str = "zh", 
                                        candidate_name: str = "", jd_title: str = "") -> tuple:
    """使用 Whisper API 转录音频文件，并保存到本地
    
    Returns:
        (transcript, saved_filepath) 元组
    """
    try:
        logger.info(f"[面试评价] 开始转录音频文件: {audio_path}")
        
        with open(audio_path, 'rb') as f:
            files = {'audio_file': (os.path.basename(audio_path), f, 'audio/aac')}
            data = {'language': language}
            
            # 使用同步的 requests（因为在 async 函数中）
            response = requests.post(
                WHISPER_API_URL,
                files=files,
                data=data,
                timeout=300
            )
        
        if response.status_code == 200:
            result = response.json()
            transcript = result.get('transcript', '')
            logger.info(f"[面试评价] 音频转录成功，长度: {len(transcript)} 字符")
            
            # 保存转录文本到本地
            saved_path = save_transcript_to_file(
                candidate_name=candidate_name,
                audio_filename=os.path.basename(audio_path),
                transcript=transcript,
                jd_title=jd_title
            )
            
            return transcript, saved_path
        else:
            logger.error(f"[面试评价] 音频转录失败: {response.status_code}, {response.text}")
            return "", ""
            
    except Exception as e:
        logger.error(f"[面试评价] 音频转录失败: {e}")
        return "", ""


async def evaluate_interview_with_qwen(
    jd_content: str,
    resume_content: str,
    transcript: str,
    questions: List[QuestionItem]
) -> Dict[str, Any]:
    """使用 Qwen3-235B 大模型评价面试"""
    try:
        # 构建面试问题列表
        questions_text = "\n".join([
            f"{i+1}. 【{q.category}】{q.question}\n   考察要点: {q.evaluation_points}"
            for i, q in enumerate(questions)
        ])
        
        # 构建6维度评价提示词
        prompt = f"""你是一位专业的HR面试官，请根据以下信息对候选人进行全面的面试评价。

## 岗位JD
{jd_content}

## 候选人简历
{resume_content}

## 面试录音转录
{transcript}

## 结构化面试问题清单
{questions_text}

请根据以上信息，对候选人进行综合评价，按以下6个维度进行评分：

1. **专业能力**：考察候选人的专业技能和知识储备
2. **工作经验**：考察候选人的工作经历与岗位的匹配度
3. **沟通表达**：考察候选人的语言表达和沟通能力
4. **逻辑思维**：考察候选人的思维逻辑和分析能力
5. **学习能力**：考察候选人的学习潜力和成长空间
6. **综合素质**：考察候选人的团队协作、职业素养等

请按以下JSON格式输出结果：

```json
{{
    "overall_score": 85,
    "evaluation_level": "优秀/良好/一般/较差",
    "dimensions": [
        {{
            "name": "专业能力",
            "score": 85,
            "weight": 20,
            "analysis": "详细分析说明"
        }},
        {{
            "name": "工作经验",
            "score": 80,
            "weight": 20,
            "analysis": "详细分析说明"
        }},
        {{
            "name": "沟通表达",
            "score": 82,
            "weight": 15,
            "analysis": "详细分析说明"
        }},
        {{
            "name": "逻辑思维",
            "score": 78,
            "weight": 15,
            "analysis": "详细分析说明"
        }},
        {{
            "name": "学习能力",
            "score": 85,
            "weight": 15,
            "analysis": "详细分析说明"
        }},
        {{
            "name": "综合素质",
            "score": 80,
            "weight": 15,
            "analysis": "详细分析说明"
        }}
    ],
    "summary": "综合评价总结（100-200字）",
    "strengths": ["优势1", "优势2", "优势3"],
    "weaknesses": ["不足1", "不足2"],
    "recommendations": ["建议1", "建议2"],
    "question_answers": [
        {{
            "question": "问题内容",
            "answer_summary": "回答摘要",
            "score": 85,
            "evaluation": "评价说明"
        }}
    ]
}}
```

注意：
1. overall_score为0-100的综合评分
2. evaluation_level根据分数划分：90-100优秀，80-89良好，60-79一般，60以下较差
3. 各维度权重总和必须为100%
4. 只输出JSON格式内容，不要有其他说明文字"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {QWEN_API_KEY}"
        }
        
        payload = {
            "model": QWEN_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "stream": False
        }
        
        logger.info(f"[面试评价] 调用 Qwen3-235B 大模型进行面试评价...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(QWEN_API_URL, headers=headers, json=payload, timeout=300) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    # 解析JSON结果
                    try:
                        if "```json" in content:
                            json_str = content.split("```json")[1].split("```")[0].strip()
                        elif "```" in content:
                            json_str = content.split("```")[1].strip()
                        else:
                            json_str = content.strip()
                        
                        evaluation = json.loads(json_str)
                        logger.info(f"[面试评价] 评价成功，综合得分: {evaluation.get('overall_score')}")
                        return evaluation
                    except json.JSONDecodeError as e:
                        logger.error(f"[面试评价] JSON解析失败: {e}")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"[面试评价] 评价API错误: {response.status}, {error_text}")
                    return None
                    
    except Exception as e:
        logger.error(f"[面试评价] 评价失败: {e}")
        return None


# ============ API路由 ============

@router.post("/evaluate", response_model=InterviewEvaluationResponse)
async def evaluate_interview(
    jd_content: Optional[str] = Form(None, description="JD文本内容"),
    jd_file: Optional[UploadFile] = File(None, description="JD文件"),
    resume_content: Optional[str] = Form(None, description="简历文本内容"),
    resume_file: Optional[UploadFile] = File(None, description="简历文件"),
    audio_file: Optional[UploadFile] = File(None, description="面试录音文件(AAC/MP3/WAV)，如已存在预存ASR数据可不传"),
    questions_file: Optional[UploadFile] = File(None, description="面试问题Excel文件"),
    candidate_name: Optional[str] = Form("", description="候选人姓名"),
    jd_title: Optional[str] = Form("", description="岗位名称")
):
    """
    AI面试评价 - Whisper转录 + 大模型评价
    
    流程：
    1. 优先使用预存 ASR 转录数据，如果没有则使用 Whisper API 转录音频
    2. Qwen3-235B 大模型基于6个维度进行面试评价
    """
    temp_audio_path = None
    temp_questions_path = None
    saved_transcript_path = None
    
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
        
        # 3. 保存音频文件（如果上传了）
        if audio_file:
            audio_content = await audio_file.read()
            temp_audio_path = os.path.join(temp_dir, audio_file.filename)
            with open(temp_audio_path, 'wb') as f:
                f.write(audio_content)
            logger.info(f"[面试评价] 音频文件已保存: {temp_audio_path}")
        
        # 4. 保存面试问题文件
        questions = []
        if questions_file:
            questions_content = await questions_file.read()
            temp_questions_path = os.path.join(temp_dir, questions_file.filename)
            with open(temp_questions_path, 'wb') as f:
                f.write(questions_content)
            questions = read_interview_questions(temp_questions_path)
        else:
            # 使用默认路径
            default_questions_file = os.path.join(
                settings.BASE_DIR, "data", 
                "综合办（董办）副主任岗位电话面试录音", 
                "结构化面试问题.xlsx"
            )
            if os.path.exists(default_questions_file):
                questions = read_interview_questions(default_questions_file)
        
        if not questions:
            logger.warning(f"[面试评价] 未找到面试问题，使用默认问题")
            questions = [
                QuestionItem(
                    category="通用",
                    question="请介绍一下你的工作经历",
                    evaluation_points="考察工作经验和职业发展"
                )
            ]
        
        # 5. 检查本地是否已有该候选人的转录文本
        logger.info(f"[面试评价] 检查本地缓存...")
        cached_transcript, cached_path = find_existing_transcript(candidate_name, jd_title)
        
        if cached_transcript:
            # 使用缓存的转录文本
            logger.info(f"[面试评价] 使用本地缓存的转录文本: {cached_path}")
            transcript = cached_transcript
            saved_transcript_path = cached_path
        elif temp_audio_path:
            # 调用 Whisper API 转录音频
            logger.info(f"[面试评价] 本地未找到缓存，开始转录音频...")
            transcript, saved_transcript_path = await transcribe_audio_with_whisper(
                temp_audio_path, 
                candidate_name=candidate_name,
                jd_title=jd_title
            )
            if not transcript:
                raise HTTPException(status_code=500, detail="音频转录失败")
            
            logger.info(f"[面试评价] 转录文本已保存到: {saved_transcript_path}")
        else:
            raise HTTPException(status_code=400, detail="未找到预存ASR数据，请上传音频文件")
        
        # 6. Qwen3-235B 大模型评价
        logger.info(f"[面试评价] 开始AI评价...")
        evaluation = await evaluate_interview_with_qwen(
            jd_content=jd_text,
            resume_content=resume_text,
            transcript=transcript,
            questions=questions
        )
        
        if not evaluation:
            raise HTTPException(status_code=500, detail="面试评价失败")
        
        return InterviewEvaluationResponse(
            success=True,
            overall_score=evaluation.get("overall_score", 0),
            evaluation_level=evaluation.get("evaluation_level", "未知"),
            dimensions=evaluation.get("dimensions", []),
            transcript=transcript,
            summary=evaluation.get("summary", ""),
            strengths=evaluation.get("strengths", []),
            weaknesses=evaluation.get("weaknesses", []),
            recommendations=evaluation.get("recommendations", []),
            question_answers=evaluation.get("question_answers", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[面试评价] 处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"面试评价失败: {str(e)}")
    finally:
        # 清理临时文件
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except:
                pass
        if temp_questions_path and os.path.exists(temp_questions_path):
            try:
                os.remove(temp_questions_path)
            except:
                pass


@router.post("/transcribe")
async def transcribe_audio(
    audio_file: UploadFile = File(..., description="音频文件(AAC/MP3/WAV)"),
    language: str = Form("zh", description="语言 (默认中文)")
):
    """
    音频转文本 - 使用 Whisper API 转录音频
    """
    temp_audio_path = None
    
    try:
        settings = get_settings()
        temp_dir = os.path.join(settings.BASE_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # 保存音频文件
        audio_content = await audio_file.read()
        temp_audio_path = os.path.join(temp_dir, audio_file.filename)
        with open(temp_audio_path, 'wb') as f:
            f.write(audio_content)
        
        # 转录
        transcript = await transcribe_audio_with_whisper(temp_audio_path, language)
        
        if not transcript:
            raise HTTPException(status_code=500, detail="音频转录失败")
        
        return {
            "success": True,
            "transcript": transcript,
            "filename": audio_file.filename,
            "language": language
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[面试评价] 转录失败: {e}")
        raise HTTPException(status_code=500, detail=f"转录失败: {str(e)}")
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except:
                pass
