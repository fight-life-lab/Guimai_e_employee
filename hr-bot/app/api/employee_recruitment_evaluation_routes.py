"""
员工招聘面试评价API路由 - 供HR/面试官对员工候选人进行面试评价
支持音频转录、AI评价、缓存管理等功能
"""

import os
import json
import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
import aiohttp

from app.config import get_settings
from io import BytesIO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/employee-recruitment-evaluation", tags=["员工招聘面试评价"])


# ============ 配置 ============

# Whisper API 配置（本地部署）
WHISPER_API_URL = "http://localhost:8003/transcribe"

# 大模型配置从config获取
# settings.remote_llm_url, settings.remote_llm_api_key, settings.remote_llm_model 已迁移到 app.config

# 转录文本保存目录
TRANSCRIPT_CACHE_DIR = "/root/shijingjing/e-employee/hr-bot/data/transcripts"

# 项目基础目录
BASE_INTERVIEW_DIR = "/root/shijingjing/e-employee/hr-bot/data/interview"


# ============ 请求/响应模型 ============

class EvaluationResponse(BaseModel):
    """面试评价响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    evaluation: Optional[dict] = Field(default=None, description="评价数据")
    candidate_name: str = Field(default="", description="候选人姓名")


class TranscribeResponse(BaseModel):
    """转录响应"""
    success: bool = Field(..., description="是否成功")
    transcript: str = Field(default="", description="转录文本")
    filename: str = Field(default="", description="文件名")
    candidate_name: str = Field(default="", description="候选人姓名")
    cached: bool = Field(default=False, description="是否来自缓存")


# ============ 工具函数 ============

def extract_candidate_name(filename: str) -> str:
    """从文件名提取候选人姓名"""
    try:
        name_part = filename.split('_')[-1]
        name = name_part.split('.')[0]
        for i, char in enumerate(name):
            if not char.isdigit():
                return name[i:]
        return name
    except:
        return filename


def get_project_cache_dir(project_name: str) -> str:
    """获取项目缓存目录"""
    cache_dir = os.path.join(BASE_INTERVIEW_DIR, project_name, "transcriptions")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_eval_dir(project_name: str) -> str:
    """获取评价数据目录"""
    eval_dir = os.path.join(BASE_INTERVIEW_DIR, project_name, "eval")
    os.makedirs(eval_dir, exist_ok=True)
    return eval_dir


def get_qa_dir(project_name: str) -> str:
    """获取问答数据目录"""
    qa_dir = os.path.join(BASE_INTERVIEW_DIR, project_name, "qa_cache")
    os.makedirs(qa_dir, exist_ok=True)
    return qa_dir


def load_cached_transcription(project_name: str, filename: str) -> Optional[dict]:
    """加载项目缓存的转录结果"""
    cache_dir = get_project_cache_dir(project_name)
    cache_file = os.path.join(cache_dir, f"{filename}.json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[员工招聘面试] 读取缓存失败: {e}")
    return None


def save_cached_transcription(project_name: str, filename: str, candidate_name: str, transcript: str):
    """保存转录结果到项目缓存"""
    try:
        cache_dir = get_project_cache_dir(project_name)
        cache_file = os.path.join(cache_dir, f"{filename}.json")
        
        cache_data = {
            "file_name": filename,
            "candidate_name": candidate_name,
            "transcription": transcript,
            "processed_at": datetime.now().isoformat(),
            "cached": True
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[员工招聘面试] 转录结果已缓存: {cache_file}")
    except Exception as e:
        logger.error(f"[员工招聘面试] 保存缓存失败: {e}")


def load_evaluation_cache(project_name: str, candidate_name: str) -> Optional[dict]:
    """加载评估结果缓存"""
    try:
        eval_file = os.path.join(BASE_INTERVIEW_DIR, project_name, "eval", f"{candidate_name}.json")
        
        if not os.path.exists(eval_file):
            return None
        
        with open(eval_file, 'r', encoding='utf-8') as f:
            return json.load(f)
        
    except Exception as e:
        logger.error(f"[员工招聘面试] 加载评估缓存失败: {e}")
        return None


def save_evaluation_cache(project_name: str, candidate_name: str, evaluation: dict):
    """保存评估结果缓存"""
    try:
        eval_dir = get_eval_dir(project_name)
        eval_file = os.path.join(eval_dir, f"{candidate_name}.json")
        
        cache_data = {
            "candidate_name": candidate_name,
            "project": project_name,
            "evaluation": evaluation,
            "cached_at": datetime.now().isoformat()
        }
        
        with open(eval_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[员工招聘面试] 评估结果已缓存: {eval_file}")
        
    except Exception as e:
        logger.error(f"[员工招聘面试] 保存评估缓存失败: {e}")


async def transcribe_audio_with_whisper(audio_path: str, language: str = "zh") -> str:
    """使用 Whisper API 转录音频文件"""
    try:
        logger.info(f"[员工招聘面试] 开始转录音频文件: {audio_path}")
        
        with open(audio_path, 'rb') as f:
            files = {'audio_file': (os.path.basename(audio_path), f, 'audio/aac')}
            data = {'language': language}
            
            import requests
            response = requests.post(
                WHISPER_API_URL,
                files=files,
                data=data,
                timeout=300
            )
        
        if response.status_code == 200:
            result = response.json()
            transcript = result.get('transcript', '')
            logger.info(f"[员工招聘面试] 音频转录成功，长度: {len(transcript)} 字符")
            return transcript
        else:
            logger.error(f"[员工招聘面试] 音频转录失败: {response.status_code}")
            return ""
            
    except Exception as e:
        logger.error(f"[员工招聘面试] 音频转录失败: {e}")
        return ""


def calculate_salary_match_employee(resume_text: str, transcript: str = "") -> Optional[dict]:
    """
    根据简历和面试录音中的薪酬信息计算薪酬匹配度（员工招聘版本）
    岗位预算：24万-30万/年
    公式：匹配率 = (岗位预算上限 / 候选人期望薪资) × 100%
    说明：
    - 匹配度表示企业预算能覆盖候选人期望薪资的比例
    - 100%：预算刚好满足期望
    - < 100%：预算不足以满足期望（如83%表示预算只能满足83%，还差17%）
    - > 100%：预算超出期望（如120%表示预算比期望高20%，有谈判空间）
    - 如果未获取到候选人薪资数据，返回None，不显示薪酬匹配信息
    """
    try:
        JD_MIN_SALARY = 24
        JD_MAX_SALARY = 30
        
        current_salary = None
        current_salary_text = None
        expected_salary = None
        expected_salary_text = None
        
        # 从转录文本中提取当前薪资
        if transcript:
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
        
        # 从转录文本中提取期望薪资
        if transcript:
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
        if expected_salary is None:
            combined_text = (resume_text + " " + (transcript or "")).lower()
            if '面议' in combined_text or 'negotiable' in combined_text:
                expected_salary_text = "面议"
                if current_salary and JD_MIN_SALARY <= current_salary <= JD_MAX_SALARY:
                    expected_salary = current_salary
                elif current_salary:
                    expected_salary = current_salary * 1.1
        
        # 如果没有获取到任何薪资信息，返回None
        if expected_salary is None and current_salary is None and expected_salary_text is None:
            return None
        
        # 计算匹配度
        match_percentage = None
        analysis = ""
        
        if expected_salary and expected_salary > 0:
            match_percentage = round((JD_MAX_SALARY / expected_salary) * 100)
            
            if expected_salary <= JD_MAX_SALARY:
                if expected_salary >= JD_MIN_SALARY:
                    analysis = f"候选人期望薪资{expected_salary_text}，岗位预算{JD_MIN_SALARY}万-{JD_MAX_SALARY}万/年。根据公式：薪酬匹配率 = 岗位预算上限({JD_MAX_SALARY}万) / 候选人期望薪资({expected_salary}万) × 100% = {match_percentage}%。候选人期望薪资在岗位预算范围内，企业预算充足，匹配度良好。"
                else:
                    analysis = f"候选人期望薪资{expected_salary_text}，岗位预算{JD_MIN_SALARY}万-{JD_MAX_SALARY}万/年。根据公式：薪酬匹配率 = 岗位预算上限({JD_MAX_SALARY}万) / 候选人期望薪资({expected_salary}万) × 100% = {match_percentage}%。候选人期望薪资低于岗位预算下限{JD_MIN_SALARY}万，企业有充足的薪酬谈判空间。"
            else:
                shortfall = 100 - match_percentage
                analysis = f"候选人期望薪资{expected_salary_text}，岗位预算{JD_MIN_SALARY}万-{JD_MAX_SALARY}万/年。根据公式：薪酬匹配率 = 岗位预算上限({JD_MAX_SALARY}万) / 候选人期望薪资({expected_salary}万) × 100% = {match_percentage}%。候选人期望薪资高于岗位预算上限{JD_MAX_SALARY}万，企业预算只能满足期望的{match_percentage}%，还差{shortfall}%。"
        elif current_salary:
            match_percentage = round((JD_MAX_SALARY / current_salary) * 100) if current_salary > 0 else None
            if match_percentage is not None:
                analysis = f"候选人当前薪资{current_salary_text}，期望薪资未明确。基于当前薪资估算匹配度为{match_percentage}%。"
        
        result = {
            "name": "薪酬匹配度",
            "jd_salary_range": f"{JD_MIN_SALARY}万-{JD_MAX_SALARY}万/年"
        }
        
        if current_salary_text:
            result["current_salary"] = current_salary_text
        if expected_salary_text:
            result["expected_salary"] = expected_salary_text
        if match_percentage:
            result["score"] = match_percentage
            result["match_percentage"] = match_percentage
        if analysis:
            result["analysis"] = analysis
        
        return result
        
    except Exception as e:
        logger.error(f"[薪酬匹配] 计算失败: {e}")
        return None


async def evaluate_interview_with_qwen(
    jd_content: str,
    resume_content: str,
    transcript: str
) -> Dict[str, Any]:
    """使用 Qwen3-235B 大模型评价面试 - 员工招聘版本"""
    try:
        settings = get_settings()

        prompt = f"""你是一位在大型企业工作多年的资深HR面试官，专门负责员工招聘面试。你熟悉现代企业的用人标准、组织文化和员工管理要求，擅长从专业能力、工作经验、团队协作等多维度对候选人进行严格、客观、有区分度的面试评价。

## 你的角色定位
- **企业HR面试官**：熟悉企业员工招聘标准，注重候选人的专业能力、工作经验、团队协作
- **专业眼光**：能够从岗位需求角度评估候选人的能力和潜力
- **严谨客观**：坚持实事求是，确保评分公正公平
- **经验丰富**：参与过大量员工招聘面试，对人才评价有独到见解

## 核心评价原则
**评分必须有显著区分度**：
- 请根据候选人的实际表现，给予差异化评分，避免所有候选人分数过于接近
- 优秀候选人应获得高分（85-100），表现一般的候选人应获得中等分数（60-75），表现较差的候选人应获得低分（0-59）
- **同一批候选人中，最高分与最低分的差距必须至少达到20分以上**，不能出现所有候选人分数集中在同一区间的情况
- 如果候选人表现确实有明显差异，请大胆给出低分（50-65）或高分（85-95），不要所有候选人都给75-85分

**评分与评语必须严格匹配**：
- 如果analysis中提到"表现优秀"、"能力突出"、"执行力强"等正面评价，分数必须在80分以上
- 如果analysis中提到"表现一般"、"有待提升"、"执行力一般"等中性评价，分数必须在60-75分之间
- 如果analysis中提到"表现较差"、"明显不足"、"执行力弱"等负面评价，分数必须在60分以下
- **严禁出现analysis评价很高但分数很低，或analysis评价很低但分数很高的情况**

**重要：该岗位侧重执行力评估**：
- 执行力是员工岗位的核心要求，在评判所有维度时，必须重点考察候选人的执行力表现
- 执行力包括：目标导向、结果意识、行动效率、任务闭环能力、遇到困难时的推进能力
- 请在各维度分析中，明确指出候选人的执行力表现，并据此调整分数
- **执行力强的候选人应在各维度获得明显更高的分数，执行力弱的候选人应在各维度获得明显更低的分数**

## 岗位JD
{jd_content}

## 候选人简历
{resume_content}

## 面试录音转录
{transcript}

## 评分维度与详细标准

### 第一部分：6个核心维度评分（0-100分，必须严格按照以下标准评分）

**评分档次定义：**
- **A档（90-100分）**：卓越表现，远超岗位要求
- **B档（80-89分）**：优秀表现，完全符合岗位要求
- **C档（60-79分）**：合格表现，基本符合岗位要求
- **D档（0-59分）**：不合格表现，不符合岗位要求

**各维度详细评分标准（员工招聘视角，重点考察执行力）：**

1. **专业能力**（权重20%）- 考察岗位胜任力、专业深度及执行落地能力：
   - A档（90-100）：专业功底深厚，不仅能提出方案，更能高效执行落地，有明确的结果产出
   - B档（80-89）：专业知识扎实，能独立执行复杂任务，按时保质完成工作
   - C档（60-79）：具备基本专业知识，能执行常规工作，但执行效率和结果质量一般
   - D档（0-59）：专业知识不足，执行力弱，任务经常无法按时完成或达不到要求
   - **执行力考察重点**：是否善于将计划转化为行动，执行过程中是否主动推进、及时反馈

2. **工作经验**（权重20%）- 考察相关工作经历、项目经验及执行成果：
   - A档（90-100）：有丰富经验，主导过重要项目并拿到结果，执行力强，有量化业绩证明
   - B档（80-89）：有3-5年经验，参与过重要项目，能按质按量完成任务，有可靠执行记录
   - C档（60-79）：有1-3年经验，参与过项目但执行深度有限，成果不够突出
   - D档（0-59）：经验不足或缺乏相关经验，执行力未得到验证
   - **执行力考察重点**：过往工作中是否以结果为导向，能否举例说明如何克服困难完成任务

3. **沟通表达**（权重15%）- 考察沟通能力、团队协作及执行协同效率：
   - A档（90-100）：表达清晰，善于跨部门协作推进工作，能高效协调资源促成任务落地
   - B档（80-89）：沟通顺畅，能进行有效协作，配合团队完成执行目标
   - C档（60-79）：沟通能力一般，协作效率不高，执行中偶有拖延或信息不同步
   - D档（0-59）：沟通困难，协作意识弱，影响团队执行效率
   - **执行力考察重点**：沟通是否以推进工作为目标，是否能及时同步进展、主动协调解决问题

4. **逻辑思维**（权重15%）- 考察分析判断、解决问题及执行策略能力：
   - A档（90-100）：思维缜密，能快速分析问题并制定可执行方案，执行路径清晰
   - B档（80-89）：逻辑清晰，能分析问题并找到解决方案，执行步骤合理
   - C档（60-79）：思维基本清晰，但分析不够深入，执行方案不够完善
   - D档（0-59）：思维混乱，缺乏逻辑性，无法制定有效执行计划
   - **执行力考察重点**：是否能把复杂问题拆解为可执行步骤，面对障碍时能否灵活调整策略继续推进

5. **学习能力**（权重15%）- 考察适应发展、学习潜力及执行中的自我提升：
   - A档（90-100）：学习意识强，能快速掌握新技能并应用到工作中，执行新任务上手快
   - B档（80-89）：学习态度端正，能主动学习，适应新任务和新环境
   - C档（60-79）：学习意愿一般，掌握新技能较慢，执行新任务需要较多指导
   - D档（0-59）：学习意识淡薄，难以适应变化，影响执行效率
   - **执行力考察重点**：是否能在执行过程中不断总结经验、优化方法，快速提升执行效率

6. **综合素质**（权重15%）- 考察职业素养、责任心、抗压能力及执行韧性：
   - A档（90-100）：职业素养高，责任心极强，抗压能力强，面对困难仍能坚持执行到底
   - B档（80-89）：职业素养良好，有责任心，能承担压力，基本完成执行任务
   - C档（60-79）：职业素养一般，责任心和抗压能力一般，执行中容易放弃或拖延
   - D档（0-59）：职业素养不足，缺乏责任心，遇到困难就退缩，执行力差
   - **执行力考察重点**：是否有强烈的结果导向意识，能否在压力下保持高效执行，是否善于自我驱动

### 第二部分：薪酬匹配度（单独维度，不参与综合评分计算）
**薪酬匹配度计算方法**：
1. 从候选人简历和面试中提取薪酬信息
2. 匹配度评分标准：
   - 90-100分：期望薪资在预算范围内，匹配度高
   - 70-89分：期望薪资略低于预算下限，有谈判空间
   - 50-69分：期望薪资略高于预算上限，需谨慎评估
   - 0-49分：期望薪资严重超出预算，不匹配

## 综合评分计算方法
综合评分 = Σ(维度分数 × 维度权重) / 100

请按以下JSON格式输出结果：

```json
{{
    "overall_score": 72,
    "evaluation_level": "良好",
    "dimensions": [
        {{
            "name": "专业能力",
            "score": 75,
            "weight": 20,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由，必须包含执行力表现的评价"
        }},
        {{
            "name": "工作经验",
            "score": 70,
            "weight": 20,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由，必须包含执行力表现的评价"
        }},
        {{
            "name": "沟通表达",
            "score": 78,
            "weight": 15,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由，必须包含执行力表现的评价"
        }},
        {{
            "name": "逻辑思维",
            "score": 68,
            "weight": 15,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由，必须包含执行力表现的评价"
        }},
        {{
            "name": "学习能力",
            "score": 80,
            "weight": 15,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由，必须包含执行力表现的评价"
        }},
        {{
            "name": "综合素质",
            "score": 72,
            "weight": 15,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由，必须包含执行力表现的评价"
        }}
    ],
    "salary_match": {{
        "name": "薪酬匹配度",
        "score": 85,
        "match_percentage": 85,
        "current_salary": "候选人当前年薪，如'35万'",
        "expected_salary": "候选人期望年薪，如'40-50万'或'面议'",
        "analysis": "详细分析：候选人当前薪资XX万，期望薪资XX万..."
    }},
    "summary": "综合评价总结（100-200字），包括候选人的核心优势、不足和总体评价，重点评价执行力表现",
    "strengths": ["优势1", "优势2", "优势3"],
    "weaknesses": ["不足1", "不足2"],
    "recommendations": ["建议1", "建议2"],
    "question_answers": [
        {{
            "question": "问题内容",
            "answer_summary": "回答摘要",
            "score": 75,
            "evaluation": "评价说明"
        }}
    ]
}}
```

## 重要注意事项
1. **必须严格执行评分标准**：根据候选人的实际表现，给予相应档次的分数，严禁所有候选人分数过于接近
2. **overall_score必须是根据权重计算的真实综合得分**，范围0-100
3. **evaluation_level根据overall_score划分**：90-100优秀，80-89良好，60-79一般，60以下较差
4. **各维度权重必须严格按照规定**：专业能力20%、工作经验20%、沟通表达15%、逻辑思维15%、学习能力15%、综合素质15%
5. **analysis字段必须包含具体依据和执行力评价**：每个维度的分析必须基于面试录音中的具体表现，并明确指出执行力方面的表现
6. **薪酬匹配度单独计算**：不参与综合评分，单独存储
7. **区分度要求**：如果评估多个候选人，必须确保分数有明显差异，最高分与最低分差距至少20分
8. **只输出JSON格式内容**，不要有其他说明文字，确保JSON格式完全正确"""

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
            "temperature": 0.3,
            "stream": False
        }
        
        logger.info(f"[员工招聘面试] 调用 Qwen3-235B 大模型进行面试评价...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(settings.remote_llm_url, headers=headers, json=payload, timeout=300) as response:
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
                        logger.info(f"[员工招聘面试] 评价成功，综合得分: {evaluation.get('overall_score')}")
                        return evaluation
                    except json.JSONDecodeError as e:
                        logger.error(f"[员工招聘面试] JSON解析失败: {e}")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"[员工招聘面试] 评价API错误: {response.status}, {error_text}")
                    return None
                    
    except Exception as e:
        logger.error(f"[员工招聘面试] 评价失败: {e}")
        return None


# ============ API路由 ============

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    audio_file: UploadFile = File(..., description="音频文件(AAC/MP3/WAV)"),
    language: str = Form("zh", description="语言 (默认中文)"),
    project: str = Form("", description="项目名称，用于缓存目录")
):
    """
    音频转文本 - 使用 Whisper API 转录音频，并缓存到项目目录
    """
    temp_audio_path = None
    
    try:
        temp_dir = "/tmp/hr-bot"
        os.makedirs(temp_dir, exist_ok=True)
        
        # 保存音频文件
        audio_content = await audio_file.read()
        temp_audio_path = os.path.join(temp_dir, audio_file.filename)
        with open(temp_audio_path, 'wb') as f:
            f.write(audio_content)
        
        # 检查项目缓存
        candidate_name = extract_candidate_name(audio_file.filename)
        cached_result = None
        
        if project:
            cached_result = load_cached_transcription(project, audio_file.filename)
            if cached_result:
                logger.info(f"[员工招聘面试] 使用项目缓存的转录结果: {audio_file.filename}")
                return TranscribeResponse(
                    success=True,
                    transcript=cached_result.get("transcription", ""),
                    filename=audio_file.filename,
                    candidate_name=candidate_name,
                    cached=True
                )
        
        # 调用Whisper API转录
        transcript = await transcribe_audio_with_whisper(temp_audio_path, language)
        
        if not transcript:
            raise HTTPException(status_code=500, detail="音频转录失败")
        
        # 保存到项目缓存
        if project:
            save_cached_transcription(project, audio_file.filename, candidate_name, transcript)
        
        return TranscribeResponse(
            success=True,
            transcript=transcript,
            filename=audio_file.filename,
            candidate_name=candidate_name,
            cached=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[员工招聘面试] 转录失败: {e}")
        raise HTTPException(status_code=500, detail=f"转录失败: {str(e)}")
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except:
                pass


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_candidate(
    project: str = Form(..., description="项目名称"),
    candidate_name: str = Form(..., description="候选人姓名"),
    jd_content: str = Form("", description="岗位JD内容"),
    resume_content: str = Form("", description="简历内容"),
    transcript: str = Form("", description="面试录音转录文本"),
    force_reevaluate: bool = Form(False, description="是否强制重新评估（覆盖缓存）")
):
    """
    评估候选人 - 使用Qwen3-235B大模型进行面试评价
    """
    try:
        # 检查缓存
        if not force_reevaluate:
            cached_eval = load_evaluation_cache(project, candidate_name)
            if cached_eval:
                logger.info(f"[员工招聘面试] 使用缓存的评估结果: {candidate_name}")
                return EvaluationResponse(
                    success=True,
                    message="使用缓存的评估结果",
                    evaluation=cached_eval.get("evaluation", cached_eval),
                    candidate_name=candidate_name
                )
        
        # 如果没有JD内容，使用默认JD
        if not jd_content.strip():
            jd_content = """岗位职责：
1. 负责日常业务流程执行和优化
2. 完成上级交办的各项任务
3. 与团队成员协作完成项目目标
4. 及时汇报工作进展和问题

岗位要求：
1. 本科及以上学历
2. 1-3年相关工作经验
3. 具备良好的沟通能力和团队协作精神
4. 执行力强，能按时完成工作任务
5. 具备良好的学习能力和适应能力"""
        
        # 调用大模型评估
        evaluation = await evaluate_interview_with_qwen(jd_content, resume_content, transcript)
        
        if not evaluation:
            raise HTTPException(status_code=500, detail="AI评估失败")
        
        # 计算薪酬匹配度
        salary_match = calculate_salary_match_employee(resume_content, transcript)
        if salary_match:
            evaluation["salary_match"] = salary_match
        
        # 提取问答对
        if transcript:
            try:
                qa_pairs = auto_extract_qa_pairs(transcript)
                await save_qa_result(project, candidate_name, qa_pairs, [])
                logger.info(f"[员工招聘面试] 问答对提取完成: {candidate_name}, 共 {len(qa_pairs)} 个")
            except Exception as e:
                logger.error(f"[员工招聘面试] 问答对提取失败: {e}")
        
        # 保存缓存
        save_evaluation_cache(project, candidate_name, evaluation)
        
        return EvaluationResponse(
            success=True,
            message="评估成功",
            evaluation=evaluation,
            candidate_name=candidate_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[员工招聘面试] 评估失败: {e}")
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}")


@router.get("/projects")
async def get_projects():
    """获取所有项目列表"""
    try:
        projects = []
        if os.path.exists(BASE_INTERVIEW_DIR):
            for item in os.listdir(BASE_INTERVIEW_DIR):
                item_path = os.path.join(BASE_INTERVIEW_DIR, item)
                if os.path.isdir(item_path):
                    projects.append(item)
        return {"projects": sorted(projects)}
    except Exception as e:
        logger.error(f"[员工招聘面试] 获取项目列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目列表失败: {str(e)}")


@router.get("/candidates")
async def get_project_candidates(
    project: str = Query(..., description="项目名称")
):
    """获取项目下的所有候选人"""
    try:
        candidates = []
        candidate_names = set()  # 用于去重
        project_dir = os.path.join(BASE_INTERVIEW_DIR, project)
        
        # 检查录音目录
        audio_dir = os.path.join(project_dir, "录音")
        if not os.path.exists(audio_dir):
            audio_dir = project_dir
        
        if os.path.exists(audio_dir):
            for filename in os.listdir(audio_dir):
                if filename.endswith(('.aac', '.mp3', '.wav', '.m4a')):
                    candidate_name = extract_candidate_name(filename)
                    
                    # 去重：跳过已处理过的候选人
                    if candidate_name in candidate_names:
                        continue
                    candidate_names.add(candidate_name)
                    
                    # 检查转录状态
                    transcript_cache = load_cached_transcription(project, filename)
                    has_transcript = transcript_cache is not None
                    transcript_text = transcript_cache.get("transcription", "") if transcript_cache else ""
                    
                    # 检查评估状态
                    eval_cache = load_evaluation_cache(project, candidate_name)
                    has_evaluation = eval_cache is not None
                    evaluation = eval_cache.get("evaluation", eval_cache) if eval_cache else None
                    
                    candidate = {
                        "name": candidate_name,
                        "filename": filename,
                        "has_transcript": has_transcript,
                        "transcript": transcript_text,
                        "transcript_length": len(transcript_text),
                        "has_evaluation": has_evaluation,
                        "evaluation": evaluation
                    }
                    
                    candidates.append(candidate)
        
        return {"candidates": candidates}
    
    except Exception as e:
        logger.error(f"[员工招聘面试] 获取候选人列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取候选人列表失败: {str(e)}")


@router.delete("/candidate")
async def delete_candidate(
    project: str = Query(..., description="项目名称"),
    candidate_name: str = Query(..., description="候选人姓名")
):
    """删除候选人的评估数据"""
    try:
        # 删除评估缓存
        eval_file = os.path.join(BASE_INTERVIEW_DIR, project, "eval", f"{candidate_name}.json")
        if os.path.exists(eval_file):
            os.remove(eval_file)
        
        # 删除问答缓存
        qa_file = os.path.join(BASE_INTERVIEW_DIR, project, "qa_cache", f"{candidate_name}.json")
        if os.path.exists(qa_file):
            os.remove(qa_file)
        
        return {"success": True, "message": "删除成功"}
    
    except Exception as e:
        logger.error(f"[员工招聘面试] 删除候选人数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.post("/parse-jd")
async def parse_jd(file: UploadFile = File(..., description="JD文件(.txt/.docx)")):
    """解析JD文件内容"""
    try:
        if file.filename.endswith('.txt'):
            content = await file.read()
            return {"content": content.decode('utf-8')}
        else:
            raise HTTPException(status_code=400, detail="仅支持.txt格式文件")
    except Exception as e:
        logger.error(f"[员工招聘面试] 解析JD文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.get("/qa/{project}/{candidate_name}")
async def get_candidate_qa(project: str, candidate_name: str):
    """
    获取候选人的结构化问答数据
    """
    try:
        qa_file = os.path.join(BASE_INTERVIEW_DIR, project, "qa_cache", f"{candidate_name}.json")
        
        if not os.path.exists(qa_file):
            return {"success": True, "qa_pairs": []}
        
        with open(qa_file, 'r', encoding='utf-8') as f:
            qa_data = json.load(f)
        
        logger.info(f"[员工招聘面试] 加载问答数据: {project}/{candidate_name}")
        
        return {"success": True, "qa_pairs": qa_data.get('qa_pairs', [])}
        
    except Exception as e:
        logger.error(f"[员工招聘面试] 加载问答数据失败: {e}")
        return {"success": True, "qa_pairs": []}


# ============ 问答对提取函数 ============

def split_transcription(transcription: str) -> List[str]:
    """将转录文本分割成段落"""
    segments = []
    sentences = re.split(r'[。！？\n]+', transcription)
    current_segment = ""
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 5:
            continue
        if len(current_segment) < 200:
            current_segment += sent + "。"
        else:
            if current_segment:
                segments.append(current_segment)
            current_segment = sent + "。"
    if current_segment:
        segments.append(current_segment)
    return segments if segments else [transcription]


def auto_extract_qa_pairs(transcription: str) -> List[Dict]:
    """自动从转录文本中提取问答对"""
    qa_pairs = []
    question_patterns = [
        r'(请|能|可以).*?(介绍|描述|说说|谈谈|分享).*?(吗|？|\?)',
        r'(什么|怎么|如何|为什么|哪里|谁|何时).*?(？|\?)',
        r'(您|你).*?(经验|看法|想法|观点|建议).*?(？|\?)',
    ]
    segments = split_transcription(transcription)
    for i, segment in enumerate(segments[:5]):
        is_question = False
        for pattern in question_patterns:
            if re.search(pattern, segment):
                is_question = True
                break
        if is_question or i == 0:
            question_text = segment[:30] + "..." if len(segment) > 30 else segment
            answer = segment
            qa_pairs.append({
                "question": f"问题{i+1}: {question_text}",
                "answer": answer,
                "category": "自动识别",
                "evaluation_points": "",
                "start_time": 0,
                "end_time": 0
            })
    if not qa_pairs:
        qa_pairs.append({
            "question": "面试交流",
            "answer": transcription[:1000],
            "category": "通用",
            "evaluation_points": "综合考察候选人的表达能力和经验",
            "start_time": 0,
            "end_time": 0
        })
    return qa_pairs


async def save_qa_result(project: str, candidate_name: str, qa_pairs: List[Dict], questions: List):
    """保存QA结果到文件"""
    try:
        project_dir = os.path.join(BASE_INTERVIEW_DIR, project)
        qa_dir = os.path.join(project_dir, "qa_cache")
        os.makedirs(qa_dir, exist_ok=True)
        qa_file = os.path.join(qa_dir, f"{candidate_name}.json")
        qa_data = {
            "candidate_name": candidate_name,
            "project": project,
            "qa_pairs": qa_pairs,
            "total_questions": len(qa_pairs),
            "questions": questions,
            "saved_at": datetime.now().isoformat()
        }
        with open(qa_file, 'w', encoding='utf-8') as f:
            json.dump(qa_data, f, ensure_ascii=False, indent=2)
        logger.info(f"[QA保存] 保存成功: {qa_file}")
    except Exception as e:
        logger.error(f"[QA保存] 保存失败: {e}")