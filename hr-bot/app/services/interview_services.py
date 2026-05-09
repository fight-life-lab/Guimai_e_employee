"""
共享服务模块 - 员工和干部面试评估通用服务

包含：
1. 音频转录服务
2. 薪酬匹配度计算服务
3. LLM客户端服务
"""

import os
import json
import re
import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime

import aiohttp

from app.config import get_settings

from .shared_utils import (
    get_transcript_dir,
    save_transcription_cache,
    load_transcription_cache
)
from app.models.interview_models import (
    get_evaluation_config,
    SalaryMatch
)

logger = logging.getLogger(__name__)


# ============ 配置 ============

# Whisper API 配置（本地部署）
WHISPER_API_URL = "http://localhost:8003/transcribe"

# 大模型配置从config获取
# settings.remote_llm_url, settings.remote_llm_api_key, settings.remote_llm_model 已迁移到 app.config


# ============ 音频转录服务 ============

async def transcribe_audio_with_whisper(audio_path: str, language: str = "zh") -> str:
    """使用 Whisper API 转录音频文件"""
    try:
        logger.info(f"[音频转录] 开始转录音频文件: {audio_path}")
        
        with open(audio_path, 'rb') as f:
            files = {'audio_file': (os.path.basename(audio_path), f, 'audio/aac')}
            data = {'language': language}
            
            response = requests.post(
                WHISPER_API_URL,
                files=files,
                data=data,
                timeout=300
            )
    
        if response.status_code == 200:
            result = response.json()
            transcript = result.get('transcript', '')
            logger.info(f"[音频转录] 音频转录成功，长度: {len(transcript)} 字符")
            return transcript
        else:
            logger.error(f"[音频转录] 音频转录失败: {response.status_code}")
            return ""
            
    except Exception as e:
        logger.error(f"[音频转录] 音频转录失败: {e}")
        return ""


async def transcribe_audio_file(
    project: str,
    audio_file,
    language: str = "zh",
    candidate_name: str = ""
) -> Dict[str, Any]:
    """
    转录音频文件（带缓存）
    
    Returns:
        {
            "success": bool,
            "transcript": str,
            "filename": str,
            "candidate_name": str,
            "cached": bool
        }
    """
    try:
        # 检查缓存
        cached_result = load_transcription_cache(project, audio_file.filename)
        if cached_result:
            logger.info(f"[音频转录] 使用缓存的转录结果: {audio_file.filename}")
            return {
                "success": True,
                "transcript": cached_result.get("transcription", ""),
                "filename": audio_file.filename,
                "candidate_name": candidate_name,
                "cached": True
            }
        
        # 保存临时文件
        temp_dir = "/tmp/hr-bot"
        os.makedirs(temp_dir, exist_ok=True)
        temp_audio_path = os.path.join(temp_dir, audio_file.filename)
        
        audio_content = await audio_file.read()
        with open(temp_audio_path, 'wb') as f:
            f.write(audio_content)
        
        # 调用Whisper API转录
        transcript = await transcribe_audio_with_whisper(temp_audio_path, language)
        
        if not transcript:
            return {"success": False, "message": "音频转录失败"}
        
        # 保存到缓存
        save_transcription_cache(project, audio_file.filename, candidate_name, transcript)
        
        # 清理临时文件
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
        
        return {
            "success": True,
            "transcript": transcript,
            "filename": audio_file.filename,
            "candidate_name": candidate_name,
            "cached": False
        }
        
    except Exception as e:
        logger.error(f"[音频转录] 转录失败: {e}")
        return {"success": False, "message": f"转录失败: {str(e)}"}


# ============ 薪酬匹配度计算服务 ============

async def extract_salary_with_llm(transcript: str) -> dict:
    """
    使用大模型从面试录音转录文本中提取薪酬信息

    Returns:
        {
            "current_salary": 当前年薪（万）,
            "current_salary_text": 当前薪资描述,
            "expected_salary": 期望年薪（万）,
            "expected_salary_text": 期望薪资描述,
            "salary_details": 薪酬详情
        }
    """
    try:
        if not transcript or len(transcript) < 50:
            return {}

        settings = get_settings()

        prompt = f"""请从以下面试录音转录文本中提取候选人的薪酬信息。

## 提取要求：
1. **当前年薪**：候选人目前工作的年薪（单位：万元/年）
2. **期望年薪**：候选人期望的年薪（单位：万元/年）
3. **薪酬详情**：如月薪、年终奖、股票期权等其他薪酬组成部分

## 注意事项：
- 如果提到月薪，请转换为年薪（月薪×12，如有年终奖则加上）
- 如果提到"以上"、"起"等字样，请保留在描述中
- 如果提到范围（如40-50万），请取中间值作为数值，保留范围作为描述
- 如果没有提到某一项，对应字段返回null

## 面试录音转录文本：
{transcript}

## 输出格式（JSON）：
```json
{{
    "current_salary": 30,
    "current_salary_text": "30万（在合肥，底薪）",
    "expected_salary": 40,
    "expected_salary_text": "40万以上",
    "salary_details": "当前在合肥工作年薪30万，期望回上海后年薪40万以上。之前在浦发工作时年薪接近60万。"
}}
```

请只输出JSON格式内容，不要有其他说明。"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.remote_llm_api_key}"
        }
        
        payload = {
            "model": settings.remote_llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "stream": False
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(settings.remote_llm_url, headers=headers, json=payload, timeout=60) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    try:
                        if "```json" in content:
                            json_str = content.split("```json")[1].split("```")[0].strip()
                        elif "```" in content:
                            json_str = content.split("```")[1].strip()
                        else:
                            json_str = content.strip()
                        
                        salary_info = json.loads(json_str)
                        logger.info(f"[薪酬匹配] LLM提取薪酬信息: {salary_info}")
                        return salary_info
                    except json.JSONDecodeError as e:
                        logger.error(f"[薪酬匹配] LLM返回JSON解析失败: {e}")
                        return {}
                else:
                    logger.error(f"[薪酬匹配] LLM API错误: {response.status}")
                    return {}
                    
    except Exception as e:
        logger.error(f"[薪酬匹配] LLM提取薪酬信息失败: {e}")
        return {}


def calculate_salary_match(
    resume_content: str,
    transcript: str = "",
    evaluation_type: str = "employee",
    llm_salary_info: dict = None
) -> Optional[SalaryMatch]:
    """
    根据简历和面试录音中的薪酬信息计算薪酬匹配度
    参考干部招聘逻辑：interview_evaluation_routes.py 中的 calculate_salary_match
    
    岗位预算：40万-60万/年
    公式：匹配率 = (岗位预算上限 / 候选人期望薪资) × 100%
    
    Args:
        resume_content: 简历内容
        transcript: 转录文本
        evaluation_type: 评估类型（employee/cadre）
        llm_salary_info: LLM提取的薪酬信息（可选）
    
    Returns:
        SalaryMatch 对象或 None
    """
    try:
        import re
        
        config = get_evaluation_config(evaluation_type)
        JD_MIN_SALARY = config.salary_min
        JD_MAX_SALARY = config.salary_max
        
        # 优先使用LLM提取的薪酬信息
        current_salary = None
        current_salary_text = None
        expected_salary = None
        expected_salary_text = None
        salary_details = ""
        
        if llm_salary_info:
            current_salary = llm_salary_info.get("current_salary")
            current_salary_text = llm_salary_info.get("current_salary_text")
            expected_salary = llm_salary_info.get("expected_salary")
            expected_salary_text = llm_salary_info.get("expected_salary_text")
            salary_details = llm_salary_info.get("salary_details", "")
            
            if current_salary or expected_salary:
                logger.info(f"[薪酬匹配] 使用LLM提取的薪酬信息: 当前={current_salary}, 期望={expected_salary}")
        
        # 如果LLM没有提取到，使用正则提取作为备选（参考干部逻辑）
        if current_salary is None and transcript:
            # 从转录文本中提取当前薪资
            current_patterns = [
                r'(?:现在|目前|当前).*?(?:年薪|薪资|薪酬|收入|工资).*?(\d+)[\s]*(?:万|w|W)?',
                r'(?:现在|目前|当前)[^\n]{0,30}?(\d+)[\s]*(?:万|w|W)?[^\n]{0,20}?(?:年薪|薪资|薪酬)',
            ]
            for pattern in current_patterns:
                match = re.search(pattern, transcript, re.IGNORECASE)
                if match:
                    val = int(match.group(1))
                    if 10 <= val <= 500:
                        current_salary = val
                        current_salary_text = f"{val}万"
                        break
        
        if expected_salary is None and transcript:
            # 从转录文本中提取期望薪资
            expected_patterns = [
                r'(?:期望|希望|目标|想|要|至少|最少)[^\n]{0,50}?(?:年薪|薪资|薪酬|待遇)[^\n]{0,30}?(\d+)[\s]*(?:万|w|W)?',
            ]
            for pattern in expected_patterns:
                match = re.search(pattern, transcript, re.IGNORECASE)
                if match:
                    val = int(match.group(1))
                    if 10 <= val <= 500:
                        expected_salary = val
                        expected_salary_text = f"{val}万"
                        break
        
        # 如果没有提取到期望薪资，检查是否有"面议"
        combined_text = (resume_content + " " + (transcript or "")).lower()
        if expected_salary is None:
            if '面议' in combined_text or 'negotiable' in combined_text:
                expected_salary_text = "面议"
                # 如果当前薪资在范围内，期望按当前薪资计算
                if current_salary and JD_MIN_SALARY <= current_salary <= JD_MAX_SALARY:
                    expected_salary = current_salary
                elif current_salary:
                    expected_salary = current_salary * 1.1
        
        # 计算匹配度 - 参考干部逻辑
        # 公式：薪酬匹配率 = (岗位预算上限 / 候选人期望薪资) × 100%
        match_percentage = 0
        analysis = ""
        
        if expected_salary and expected_salary > 0:
            # 使用公式计算：岗位预算上限 / 候选人期望薪资 × 100%
            match_percentage = int((JD_MAX_SALARY / expected_salary) * 100)
            
            if expected_salary < JD_MIN_SALARY:
                # 期望薪资低于预算下限（如25万 < 40万）
                # 匹配率 = 60/25 = 240%，表示候选人期望远低于预算，匹配度极高
                analysis = f"候选人期望薪资{expected_salary_text}，岗位预算上限{JD_MAX_SALARY}万。根据公式：薪酬匹配率 = 岗位预算上限({JD_MAX_SALARY}万) / 候选人期望薪资({expected_salary}万) × 100% = {match_percentage}%。候选人期望薪资低于岗位预算下限{JD_MIN_SALARY}万，企业有充足的薪酬谈判空间，匹配度极高。"
            elif JD_MIN_SALARY <= expected_salary <= JD_MAX_SALARY:
                # 期望薪资在预算范围内（40-60万）
                # 匹配率 = 60/50 = 120%，表示候选人期望在预算内，匹配度高
                analysis = f"候选人期望薪资{expected_salary_text}，岗位预算上限{JD_MAX_SALARY}万。根据公式：薪酬匹配率 = 岗位预算上限({JD_MAX_SALARY}万) / 候选人期望薪资({expected_salary}万) × 100% = {match_percentage}%。候选人期望薪资在岗位预算{JD_MIN_SALARY}万-{JD_MAX_SALARY}万范围内，匹配度高。"
            else:
                # 期望薪资高于预算上限（如70万 > 60万）
                # 匹配率 = 60/70 = 86%，表示候选人期望略高于预算
                analysis = f"候选人期望薪资{expected_salary_text}，岗位预算上限{JD_MAX_SALARY}万。根据公式：薪酬匹配率 = 岗位预算上限({JD_MAX_SALARY}万) / 候选人期望薪资({expected_salary}万) × 100% = {match_percentage}%。候选人期望薪资高于岗位预算上限{JD_MAX_SALARY}万，需要进一步沟通。"
        elif current_salary:
            # 只有当前薪资，没有期望薪资，使用当前薪资估算
            match_percentage = int((JD_MAX_SALARY / current_salary) * 100) if current_salary > 0 else 0
            analysis = f"候选人未明确期望薪资，当前薪资{current_salary_text}。基于当前薪资估算匹配度为{match_percentage}%，建议进一步沟通确认期望。"
        else:
            # 无法提取薪资信息 - 返回未明确，不设置默认匹配度
            match_percentage = 0
            analysis = "无法从面试录音中提取薪资信息。建议面试时主动询问候选人当前及期望薪资。"
        
        # 构建结果 - 参考干部逻辑的字段结构
        # 如果没有获取到任何薪资信息，返回None让前端显示"未明确"
        if not current_salary and not expected_salary and not expected_salary_text:
            return None
        
        result = SalaryMatch(
            name="薪酬匹配度",
            score=match_percentage,
            match_percentage=match_percentage,
            jd_salary_range=f"{JD_MIN_SALARY}万-{JD_MAX_SALARY}万/年",
            current_salary=current_salary_text if current_salary_text else (f"{current_salary}万" if current_salary else "未明确"),
            expected_salary=expected_salary_text if expected_salary_text else (f"{expected_salary}万" if expected_salary else "未明确"),
            analysis=analysis,
            salary_details=salary_details if salary_details else analysis
        )
        
        logger.info(f"[薪酬匹配] {result}")
        return result
        
    except Exception as e:
        logger.error(f"[薪酬匹配] 计算失败: {e}")
        # 返回None让前端显示"未明确"
        return None


# ============ LLM客户端服务 ============

async def call_qwen_api(prompt: str, temperature: float = 0.3, max_tokens: int = 2000) -> Optional[str]:
    """
    调用Qwen3-235B大模型API

    Args:
        prompt: 提示词
        temperature: 温度参数
        max_tokens: 最大token数

    Returns:
        模型返回的内容，失败返回None
    """
    try:
        settings = get_settings()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.remote_llm_api_key}"
        }
        
        payload = {
            "model": settings.remote_llm_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        logger.info(f"[LLM调用] 调用 Qwen3-235B 大模型...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(settings.remote_llm_url, headers=headers, json=payload, timeout=300) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    logger.info(f"[LLM调用] 调用成功，返回内容长度: {len(content)}")
                    return content
                else:
                    error_text = await response.text()
                    logger.error(f"[LLM调用] API错误: {response.status}, {error_text}")
                    return None
                    
    except Exception as e:
        logger.error(f"[LLM调用] 调用失败: {e}")
        return None


async def parse_json_from_response(content: str) -> Optional[dict]:
    """
    从LLM响应中解析JSON内容
    
    Args:
        content: LLM返回的内容
    
    Returns:
        解析后的JSON对象，失败返回None
    """
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].strip()
        else:
            json_str = content.strip()
        
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"[JSON解析] 解析失败: {e}")
        return None