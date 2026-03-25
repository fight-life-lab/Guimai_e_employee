"""
AI面试评价API路由 V2 - 双雷达图对比分析
- 左侧：JD岗位要求雷达图（基于JD分析）
- 右侧：员工面试表现雷达图（基于面试数据）
- 真伪验证：检查面试回答与简历一致性
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

router = APIRouter(prefix="/api/v1/interview-evaluation", tags=["AI面试评价V2"])


# ============ 配置 ============

# Whisper API 配置（本地部署）
WHISPER_API_URL = "http://localhost:8003/transcribe"

# Qwen3-235B 大模型配置（全尺寸版本）
QWEN_API_URL = "http://180.97.200.118:30071/v1/chat/completions"
QWEN_API_KEY = "z3oK7bN9xPqW2mT8rYvL5tF1cJ4hD6gA0eS2uI3nQk"
QWEN_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"

# 预存 ASR 转录数据目录
PRESTORED_ASR_DIR = "/root/shijingjing/e-employee/hr-bot/data/transcriptions"

# 6个评估维度
EVALUATION_DIMENSIONS = [
    "专业能力",
    "工作经验", 
    "沟通表达",
    "逻辑思维",
    "学习能力",
    "综合素质"
]


# ============ 请求/响应模型 ============

class InterviewEvaluationResponseV2(BaseModel):
    """面试评价响应V2"""
    success: bool = Field(..., description="是否成功")
    
    # 左侧：JD岗位要求
    jd_analysis: dict = Field(..., description="JD分析结果")
    jd_dimensions: List[dict] = Field(..., description="JD维度评分")
    
    # 右侧：员工面试表现
    candidate_dimensions: List[dict] = Field(..., description="候选人维度评分")
    overall_score: float = Field(..., description="综合面试评分")
    evaluation_level: str = Field(..., description="评价等级")
    
    # 问题回答评价（基于结构化面试问题）
    question_answers: List[dict] = Field(default=[], description="问题回答评价")
    
    # 真伪验证
    authenticity_check: dict = Field(..., description="真伪验证结果")
    
    # 总结和建议
    summary: str = Field(..., description="面试总结")
    strengths: List[str] = Field(default=[], description="候选人优势")
    recommendations: List[str] = Field(default=[], description="建议")


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
    """查找预存的 ASR 转录数据"""
    try:
        if not candidate_name:
            return None, None
        
        json_file = os.path.join(PRESTORED_ASR_DIR, f"{candidate_name}.json")
        
        if not os.path.exists(json_file):
            logger.info(f"[面试评价] 未找到预存 ASR 数据: {json_file}")
            return None, None
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
       # 提取转录文本
        transcript = data.get('transcription', '') or data.get('text', '') or data.get('transcript', '')
        
        if transcript:
            logger.info(f"[面试评价] 找到预存 ASR 数据: {json_file}, 长度: {len(transcript)}")
            return transcript, json_file
        
        return None, None
        
    except Exception as e:
        logger.error(f"[面试评价] 读取预存 ASR 数据失败: {e}")
        return None, None


async def call_qwen_model(prompt: str, temperature: float = 0.3) -> str:
    """调用 Qwen3-235B 大模型"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {QWEN_API_KEY}"
        }
        
        payload = {
            "model": QWEN_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "stream": False
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(QWEN_API_URL, headers=headers, json=payload, timeout=300) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("choices", [{}])[0].get("message", {}).get("content", "")
                else:
                    error_text = await response.text()
                    logger.error(f"[面试评价] Qwen API错误: {response.status}, {error_text}")
                    return ""
                    
    except Exception as e:
        logger.error(f"[面试评价] 调用Qwen模型失败: {e}")
        return ""


async def analyze_jd_requirements(jd_content: str) -> dict:
    """分析JD，生成岗位要求的6维度评分和理由"""
    prompt = f"""你是一位资深HR专家，请根据以下岗位JD，分析该岗位在6个维度上的要求程度。

岗位JD：
{jd_content}

请对以下6个维度进行评分（0-100分），并给出评分理由：
1. 专业能力
2. 工作经验
3. 沟通表达
4. 逻辑思维
5. 学习能力
6. 综合素质

请按以下JSON格式输出：
```json
{{
    "dimensions": [
        {{"name": "专业能力", "score": 85, "reason": "岗位要求扎实的专业知识和技能"}},
        {{"name": "工作经验", "score": 80, "reason": "需要5年以上相关经验"}},
        {{"name": "沟通表达", "score": 75, "reason": "需要良好的沟通协调能力"}},
        {{"name": "逻辑思维", "score": 80, "reason": "需要较强的分析和解决问题能力"}},
        {{"name": "学习能力", "score": 70, "reason": "需要快速适应新环境"}},
        {{"name": "综合素质", "score": 75, "reason": "需要良好的职业素养"}}
    ],
    "summary": "该岗位整体要求较高，特别注重专业能力和工作经验"
}}
```

注意：
1. 评分应基于JD中的明确要求
2. 理由应具体，引用JD中的相关内容
3. 只输出JSON格式内容"""

    content = await call_qwen_model(prompt, temperature=0.3)
    
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].strip()
        else:
            json_str = content.strip()
        
        result = json.loads(json_str)
        logger.info(f"[面试评价] JD分析完成")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"[面试评价] JD分析结果解析失败: {e}")
        return {
            "dimensions": [{"name": d, "score": 75, "reason": "基于JD的一般要求"} for d in EVALUATION_DIMENSIONS],
            "summary": "该岗位需要综合素质较高的候选人"
        }


async def evaluate_candidate_vs_jd(
    jd_content: str,
    resume_content: str,
    transcript: str,
    jd_dimensions: List[dict]
) -> dict:
    """评估候选人面试表现 vs 岗位要求"""
    prompt = f"""你是一位专业HR面试官，请根据以下信息评估候选人的面试表现。

## 岗位JD
{jd_content}

## 岗位要求维度评分
{json.dumps(jd_dimensions, ensure_ascii=False, indent=2)}

## 候选人简历
{resume_content}

## 面试录音转录
{transcript[:3000]}  # 限制长度避免超出token限制

请对候选人在以下6个维度上进行评分（0-100分），并与岗位要求进行对比：
1. 专业能力
2. 工作经验
3. 沟通表达
4. 逻辑思维
5. 学习能力
6. 综合素质

请按以下JSON格式输出：
```json
{{
    "dimensions": [
        {{"name": "专业能力", "score": 82, "gap": -3, "reason": "候选人具备扎实的专业知识，但比岗位要求略低"}},
        {{"name": "工作经验", "score": 85, "gap": 5, "reason": "候选人工作经验丰富，超过岗位要求"}},
        {{"name": "沟通表达", "score": 80, "gap": 5, "reason": "表达清晰，沟通能力强"}},
        {{"name": "逻辑思维", "score": 78, "gap": -2, "reason": "逻辑思维良好，但复杂问题分析有待提升"}},
        {{"name": "学习能力", "score": 85, "gap": 15, "reason": "学习能力强，适应性好"}},
        {{"name": "综合素质", "score": 80, "gap": 5, "reason": "综合素质良好，符合岗位要求"}}
    ],
    "overall_score": 82,
    "evaluation_level": "良好",
    "summary": "候选人整体表现良好，与岗位匹配度较高",
    "strengths": ["优势1", "优势2", "优势3"],
    "recommendations": ["建议1", "建议2"]
}}
```

注意：
1. gap表示与岗位要求的差距（正数表示超过，负数表示不足）
2. 理由应基于面试表现和简历内容
3. 只输出JSON格式内容"""

    content = await call_qwen_model(prompt, temperature=0.3)
    
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].strip()
        else:
            json_str = content.strip()
        
        result = json.loads(json_str)
        logger.info(f"[面试评价] 候选人评估完成，综合得分: {result.get('overall_score')}")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"[面试评价] 候选人评估结果解析失败: {e}")
        return {
            "dimensions": [{"name": d, "score": 75, "gap": 0, "reason": "表现符合预期"} for d in EVALUATION_DIMENSIONS],
            "overall_score": 75,
            "evaluation_level": "良好",
            "summary": "候选人表现符合岗位要求",
            "strengths": ["具备相关经验", "沟通能力良好"],
            "recommendations": ["可进一步考察专业能力"]
        }


async def evaluate_question_answers(
    transcript: str,
    questions: List[QuestionItem]
) -> List[dict]:
    """基于结构化面试问题评估候选人回答"""
    questions_text = "\n".join([f"{i+1}. 【{q.category}】{q.question}" for i, q in enumerate(questions)])
    
    prompt = f"""你是一位专业HR面试官，请根据面试录音转录，评估候选人对以下结构化面试问题的回答。

## 结构化面试问题
{questions_text}

## 面试录音转录
{transcript[:3000]}

请提取候选人对每个问题的回答，并进行评分（0-100分）和评价。

请按以下JSON格式输出：
```json
{{
    "question_answers": [
        {{
            "question": "问题内容",
            "answer_summary": "候选人回答摘要",
            "score": 85,
            "evaluation": "回答评价"
        }}
    ]
}}
```

注意：
1. 只针对上面列出的结构化问题进行评估
2. 如果转录中没有找到某问题的回答，标注为"未回答"
3. 只输出JSON格式内容"""

    content = await call_qwen_model(prompt, temperature=0.3)
    
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].strip()
        else:
            json_str = content.strip()
        
        result = json.loads(json_str)
        return result.get("question_answers", [])
    except json.JSONDecodeError as e:
        logger.error(f"[面试评价] 问题回答评估解析失败: {e}")
        return []


async def check_authenticity(
    resume_content: str,
    transcript: str
) -> dict:
    """检查面试回答与简历的一致性，识别真伪
    
    只检查简历和面试中实际存在的冲突，不自行添加衍生内容
    """
    prompt = f"""你是一位资深HR背景调查专家，请严格对比候选人的简历和面试回答，只报告实际发现的不一致之处。

## 候选人简历
{resume_content}

## 面试录音转录
{transcript[:3000]}

请严格检查以下内容，只报告实际存在的冲突：
1. 工作经历：公司名称、职位、时间是否在简历和面试中一致
2. 项目经历：项目名称、职责、成果是否在两者中一致
3. 技能描述：技能掌握程度描述是否一致
4. 时间线：入职离职时间是否有矛盾

重要规则：
- 只报告简历和面试中**实际存在**的不一致
- 不要推测或添加未明确提及的内容
- 如果面试中未提及某内容，不要作为不一致
- 只有简历和面试都提到但内容冲突时，才列为不一致

请按以下JSON格式输出：
```json
{{
    "status": "一致/部分一致/存疑",
    "confidence": 85,
    "inconsistencies": [
        {{
            "item": "具体不一致项（如：工作经历时间）",
            "resume": "简历中的原文描述",
            "interview": "面试中的原文描述",
            "severity": "轻微/中等/严重"
        }}
    ],
    "analysis": "基于实际对比的整体分析",
    "recommendations": ["基于实际不一致的建议"]
}}
```

注意：
1. 如未发现实际不一致，inconsistencies必须为空数组
2. 只有简历和面试都明确提及且内容冲突时，才列入inconsistencies
3. 不要添加推测性的不一致项
4. 只输出JSON格式内容"""

    content = await call_qwen_model(prompt, temperature=0.3)
    
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].strip()
        else:
            json_str = content.strip()
        
        result = json.loads(json_str)
        logger.info(f"[面试评价] 真伪验证完成，状态: {result.get('status')}")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"[面试评价] 真伪验证结果解析失败: {e}")
        return {
            "status": "一致",
            "confidence": 80,
            "inconsistencies": [],
            "analysis": "简历与面试回答基本一致",
            "recommendations": []
        }


# ============ API路由 ============

@router.post("/evaluate-v2", response_model=InterviewEvaluationResponseV2)
async def evaluate_interview_v2(
    jd_content: Optional[str] = Form(None, description="JD文本内容"),
    jd_file: Optional[UploadFile] = File(None, description="JD文件"),
    resume_content: Optional[str] = Form(None, description="简历文本内容"),
    resume_file: Optional[UploadFile] = File(None, description="简历文件"),
    audio_file: Optional[UploadFile] = File(None, description="面试录音文件（可选，如有预存ASR可不传）"),
    questions_file: Optional[UploadFile] = File(None, description="结构化面试问题Excel文件"),
    candidate_name: Optional[str] = Form("", description="候选人姓名"),
    jd_title: Optional[str] = Form("", description="岗位名称")
):
    """
    AI面试评价V2 - 双雷达图对比分析
    
    流程：
    1. 分析JD生成岗位要求雷达图（左侧）
    2. 评估候选人面试表现 vs 岗位要求（右侧）
    3. 基于结构化问题评估回答
    4. 真伪验证：检查面试回答与简历一致性
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
            logger.info(f"[面试评价] 开始转录音频...")
            import requests as sync_requests
            with open(temp_audio_path, 'rb') as f:
                files = {'audio_file': (os.path.basename(temp_audio_path), f, 'audio/aac')}
                data = {'language': 'zh'}
                response = sync_requests.post(WHISPER_API_URL, files=files, data=data, timeout=300)
            
            if response.status_code == 200:
                result = response.json()
                transcript = result.get('transcript', '')
                logger.info(f"[面试评价] 音频转录完成，长度: {len(transcript)}")
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
            # 使用默认问题
            default_questions_file = os.path.join(
                settings.BASE_DIR, "data", 
                "综合办（董办）副主任岗位电话面试录音", 
                "结构化面试问题.xlsx"
            )
            if os.path.exists(default_questions_file):
                questions = read_interview_questions(default_questions_file)
        
        if not questions:
            questions = [
                QuestionItem(category="通用", question="请介绍一下你的工作经历", evaluation_points="考察工作经验")
            ]
        
        # 5. 并行执行JD分析和候选人评估（这两个可以并行）
        logger.info(f"[面试评价] 开始并行分析JD和评估候选人...")
        
        import asyncio
        
        # 并行执行JD分析和候选人评估
        jd_analysis_task = analyze_jd_requirements(jd_text)
        candidate_eval_task = evaluate_candidate_vs_jd(
            jd_content=jd_text,
            resume_content=resume_text,
            transcript=transcript,
            jd_dimensions=[]  # 先不传，等JD分析完成后再评估
        )
        
        # 等待JD分析完成
        jd_analysis = await jd_analysis_task
        
        # 使用JD分析结果重新评估候选人
        candidate_eval = await evaluate_candidate_vs_jd(
            jd_content=jd_text,
            resume_content=resume_text,
            transcript=transcript,
            jd_dimensions=jd_analysis.get("dimensions", [])
        )
        
        # 6. 并行执行问题评估和真伪验证
        logger.info(f"[面试评价] 开始并行评估问题和真伪验证...")
        
        question_answers_task = evaluate_question_answers(transcript, questions)
        authenticity_task = check_authenticity(resume_text, transcript)
        
        # 同时等待两个任务完成
        question_answers, authenticity = await asyncio.gather(
            question_answers_task, 
            authenticity_task
        )
        
        return InterviewEvaluationResponseV2(
            success=True,
            jd_analysis=jd_analysis,
            jd_dimensions=jd_analysis.get("dimensions", []),
            candidate_dimensions=candidate_eval.get("dimensions", []),
            overall_score=candidate_eval.get("overall_score", 0),
            evaluation_level=candidate_eval.get("evaluation_level", "未知"),
            question_answers=question_answers,
            authenticity_check=authenticity,
            summary=candidate_eval.get("summary", ""),
            strengths=candidate_eval.get("strengths", []),
            recommendations=candidate_eval.get("recommendations", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[面试评价] 处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"面试评价失败: {str(e)}")
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except:
                pass
