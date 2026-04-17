"""
AI面试评价API路由 - 提供面试录音分析和评价接口
音频转录使用 whisper-api，面试评价使用 Qwen3-235B 大模型
通过优化prompt引导模型输出有区分度的评分
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


# ============ 强制分数差异化调整函数 ============

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
    
    import re
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
    
    # 模式3: 检查邮箱是否是内部邮箱
    if '@chinatelecom.cn' in combined_lower or '@chinatelecom.com.cn' in combined_lower:
        return True, "中国电信集团", 10
    
    return False, "", 0


def adjust_scores_for_differentiation(evaluation: dict, resume_text: str, transcript: str) -> dict:
    """
    根据候选人的硬性条件强制调整分数，确保差异化
    重点关注：管理经验、规划能力、项目规模
    新增：内部候选人检测和加分
    """
    try:
        dimensions = evaluation.get("dimensions", [])
        if not dimensions:
            return evaluation
        
        # 找到工作经验维度
        work_exp_dim = None
        work_exp_idx = -1
        for idx, dim in enumerate(dimensions):
            if "工作经验" in dim.get("name", ""):
                work_exp_dim = dim
                work_exp_idx = idx
                break
        
        if work_exp_dim is None:
            return evaluation
        
        # 分析简历和转录文本，提取关键信息
        resume_lower = resume_text.lower()
        transcript_lower = transcript.lower()
        combined_text = resume_lower + " " + transcript_lower
        
        # ===== 检测是否是内部候选人 =====
        is_internal, internal_company, internal_bonus = is_internal_candidate(resume_text, transcript)
        
        if is_internal:
            logger.info(f"[内部候选人] 检测到内部员工: 公司={internal_company}, 加分={internal_bonus}")
        
        # 计算管理经验得分（内部候选人标准放宽）
        management_score = 0
        if is_internal:
            # 内部候选人：有项目管理或团队协调经验即可
            if any(kw in combined_text for kw in ["项目负责人", "项目协调", "跨部门", "部门协作", "项目管理"]):
                management_score = 85
            elif any(kw in combined_text for kw in ["团队", "小组", "带领", "协调"]):
                management_score = 80
            else:
                management_score = 75  # 内部候选人基础分较高
        else:
            # 外部候选人：必须有正式管理岗位经历
            if any(kw in combined_text for kw in ["10人", "15人", "20人", "30人", "50人", "100人", "团队负责人", "部门负责人", "总监", "经理"]):
                management_score = 90
            elif any(kw in combined_text for kw in ["5人", "8人", "团队管理", "项目经理", "组长"]):
                management_score = 80
            elif any(kw in combined_text for kw in ["3人", "几人", "小团队"]):
                management_score = 70
            else:
                management_score = 60  # 无明确管理经验
        
        # 计算规划能力得分
        planning_score = 0
        if is_internal:
            # 内部候选人：参与过规划或战略执行即可
            if any(kw in combined_text for kw in ["战略规划", "五年规划", "三年规划", "战略制定", "顶层设计", "战略落地"]):
                planning_score = 90
            elif any(kw in combined_text for kw in ["参与规划", "协助规划", "执行规划", "规划编制", "战略执行"]):
                planning_score = 85
            elif any(kw in combined_text for kw in ["执行", "实施", "落地"]):
                planning_score = 80
            else:
                planning_score = 75
        else:
            # 外部候选人：必须有主导规划经验
            if any(kw in combined_text for kw in ["战略规划", "五年规划", "三年规划", "战略制定", "顶层设计", "战略落地"]):
                planning_score = 90
            elif any(kw in combined_text for kw in ["参与规划", "协助规划", "执行规划", "规划编制"]):
                planning_score = 80
            elif any(kw in combined_text for kw in ["执行", "实施", "落地"]):
                planning_score = 70
            else:
                planning_score = 60
        
        # 计算项目规模得分
        project_score = 0
        if any(kw in combined_text for kw in ["千万", "亿", "大型项目", "重大项目", "集团级", "公司级"]):
            project_score = 90
        elif any(kw in combined_text for kw in ["百万", "中型项目", "重要项目", "部门级"]):
            project_score = 80
        elif any(kw in combined_text for kw in ["项目", "项目经验"]):
            project_score = 70
        else:
            project_score = 60
        
        # 计算工作经验维度新分数（加权平均）
        new_work_exp_score = int(management_score * 0.4 + planning_score * 0.4 + project_score * 0.2)
        
        # ===== 内部候选人加分 =====
        if is_internal:
            new_work_exp_score = min(100, new_work_exp_score + internal_bonus)
            logger.info(f"[内部候选人加分] 工作经验维度加{internal_bonus}分，调整后: {new_work_exp_score}")
        
        # 确保分数在合理范围内
        old_score = work_exp_dim.get("score", 82)
        
        # 如果AI评分与硬性条件差异过大，进行调整
        if abs(new_work_exp_score - old_score) > 5:  # 降低阈值，更敏感地调整
            # 融合AI评分和硬性条件评分（内部候选人更依赖硬性条件）
            if is_internal:
                final_score = int(old_score * 0.2 + new_work_exp_score * 0.8)  # 内部候选人80%依赖硬性条件
            else:
                final_score = int(old_score * 0.3 + new_work_exp_score * 0.7)  # 外部候选人70%依赖硬性条件
            
            # 确保分数在合理范围
            final_score = max(60, min(100, final_score))
            
            logger.info(f"[分数调整] 工作经验维度: {old_score} -> {final_score} (管理:{management_score}, 规划:{planning_score}, 项目:{project_score}, 内部:{is_internal})")
            
            # 更新维度分数
            dimensions[work_exp_idx]["score"] = final_score
            
            # 更新analysis，说明调整原因
            original_analysis = dimensions[work_exp_idx].get("analysis", "")
            if is_internal:
                adjustment_note = f"【内部候选人评估】该候选人有{internal_company}工作经验，属内部晋升渠道。管理经验:{management_score}分, 规划能力:{planning_score}分, 项目规模:{project_score}分, 内部加分:{internal_bonus}分。"
            else:
                adjustment_note = f"【硬性条件评估】管理经验:{management_score}分, 规划能力:{planning_score}分, 项目规模:{project_score}分。"
            dimensions[work_exp_idx]["analysis"] = adjustment_note + original_analysis
            
            # 重新计算综合得分
            total_weighted_score = 0
            total_weight = 0
            for dim in dimensions:
                weight = dim.get("weight", 16.67)
                score = dim.get("score", 0)
                total_weighted_score += score * weight
                total_weight += weight
            
            if total_weight > 0:
                new_overall_score = round(total_weighted_score / total_weight, 1)
                logger.info(f"[分数调整] 综合得分: {evaluation.get('overall_score')} -> {new_overall_score}")
                evaluation["overall_score"] = new_overall_score
                
                # 更新评价等级
                if new_overall_score >= 90:
                    evaluation["evaluation_level"] = "优秀"
                elif new_overall_score >= 80:
                    evaluation["evaluation_level"] = "良好"
                elif new_overall_score >= 60:
                    evaluation["evaluation_level"] = "一般"
                else:
                    evaluation["evaluation_level"] = "较差"
        
        return evaluation
        
    except Exception as e:
        logger.error(f"[分数调整] 调整失败: {e}")
        return evaluation


async def extract_salary_with_llm(transcript: str) -> dict:
    """
    使用大模型从面试录音转录文本中提取薪酬信息
    
    Returns:
        {
            "current_salary": 当前年薪（万）,
            "current_salary_text": 当前薪资描述,
            "expected_salary": 期望年薪（万）,
            "expected_salary_text": 期望薪资描述,
            "salary_details": 薪酬详情（如月薪、奖金等）
        }
    """
    try:
        if not transcript or len(transcript) < 50:
            return {}
        
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
            "Authorization": f"Bearer {QWEN_API_KEY}"
        }
        
        payload = {
            "model": QWEN_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "stream": False
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(QWEN_API_URL, headers=headers, json=payload, timeout=60) as response:
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


def calculate_salary_match(evaluation: dict, resume_text: str, transcript: str = "", llm_salary_info: dict = None) -> dict:
    """
    根据简历和面试录音中的薪酬信息计算薪酬匹配度
    岗位预算：40万-60万/年
    公式：匹配率 = (岗位预算上限 / 候选人期望薪资) × 100%
    
    优先使用LLM提取的薪酬信息，如果LLM未提取到，则使用正则提取
    """
    try:
        import re
        
        JD_MIN_SALARY = 40  # 万/年
        JD_MAX_SALARY = 60  # 万/年
        
        # 优先使用LLM提取的薪酬信息
        current_salary = None
        current_salary_text = None
        expected_salary = None
        expected_salary_text = None
        salary_details = ""
        
        if llm_salary_info:
            # 从LLM结果中提取
            current_salary = llm_salary_info.get("current_salary")
            current_salary_text = llm_salary_info.get("current_salary_text")
            expected_salary = llm_salary_info.get("expected_salary")
            expected_salary_text = llm_salary_info.get("expected_salary_text")
            salary_details = llm_salary_info.get("salary_details", "")
            
            if current_salary or expected_salary:
                logger.info(f"[薪酬匹配] 使用LLM提取的薪酬信息: 当前={current_salary}, 期望={expected_salary}")
        
        # 如果LLM没有提取到，使用正则提取作为备选
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
        if expected_salary is None:
            combined_text = (resume_text + " " + (transcript or "")).lower()
            if '面议' in combined_text or 'negotiable' in combined_text:
                expected_salary_text = "面议"
                # 如果当前薪资在范围内，期望按当前薪资计算
                if current_salary and JD_MIN_SALARY <= current_salary <= JD_MAX_SALARY:
                    expected_salary = current_salary
                elif current_salary:
                    expected_salary = current_salary * 1.1
        
        # 计算匹配度
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
            match_percentage = int((JD_MAX_SALARY / current_salary) * 100) if current_salary > 0 else 70
            analysis = f"候选人未明确期望薪资，当前薪资{current_salary_text}。基于当前薪资估算匹配度为{match_percentage}%，建议进一步沟通确认期望。"
        else:
            # 无法提取薪资信息
            match_percentage = 70
            analysis = "无法从面试录音中提取薪资信息，默认匹配度70%。建议面试时主动询问候选人当前及期望薪资。"
        
        salary_match = {
            "name": "薪酬匹配度",
            "score": match_percentage,
            "match_percentage": match_percentage,
            "jd_salary_range": f"{JD_MIN_SALARY}万-{JD_MAX_SALARY}万/年",
            "current_salary": current_salary_text if current_salary_text else (f"{current_salary}万" if current_salary else "未明确"),
            "expected_salary": expected_salary_text if expected_salary_text else (f"{expected_salary}万" if expected_salary else "未明确"),
            "analysis": analysis,
            "salary_details": salary_details if salary_details else analysis
        }
        
        logger.info(f"[薪酬匹配] {salary_match}")
        return salary_match
        
    except Exception as e:
        logger.error(f"[薪酬匹配] 计算失败: {e}")
        return {
            "name": "薪酬匹配度",
            "score": 70,
            "match_percentage": 70,
            "jd_salary_range": "40万-60万/年",
            "current_salary": "未明确",
            "expected_salary": "未明确",
            "analysis": "薪资信息提取失败，默认匹配度70%。"
        }


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
    jd_requirements: dict = Field(default={}, description="岗位各维度要求")
    salary_match: dict = Field(default={}, description="薪酬匹配度")


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
        
        # 构建6维度评价提示词 - 优化版
        # 核心改进：增加评分差异化指导，明确区分优秀与普通表现
        prompt = f"""你是一位在大型国有企业工作多年的资深HR面试官，专门负责干部选拔和管理工作面试。你熟悉国企的用人标准、组织文化和干部管理要求，擅长从政治素质、专业能力、管理经验、团队协作等多维度对候选人进行严格、客观、有区分度的面试评价。

## 你的角色定位
- **国企干部面试官**：熟悉国企干部选拔任用规定，注重候选人的政治素质、廉洁自律、组织纪律性
- **战略眼光**：能够从组织发展角度评估候选人的潜力和价值
- **严谨客观**：坚持实事求是，不打人情分，确保评分公正公平
- **经验丰富**：参与过大量中高层干部面试，对人才评价有独到见解

## 核心评价原则
**评分必须有显著区分度**：请根据候选人的实际表现，给予差异化评分，避免所有候选人分数过于接近。优秀候选人应获得高分（85-100），表现一般的候选人应获得中等分数（60-75），表现较差的候选人应获得低分（0-59）。

**评分与评语必须严格匹配**：
- 如果analysis中提到"表现优秀"、"能力突出"等正面评价，分数必须在80分以上
- 如果analysis中提到"表现一般"、"有待提升"等中性评价，分数必须在60-75分之间
- 如果analysis中提到"表现较差"、"明显不足"等负面评价，分数必须在60分以下
- **严禁出现analysis评价很高但分数很低，或analysis评价很低但分数很高的情况**
- 每个维度的analysis必须明确说明为什么给出这个分数，分数与评语必须逻辑一致

**【关键】国资干部序列选拔标准（必须严格执行）**：
本岗位为**国企干部序列**（副总经理/总经理助理），属于管理岗位，必须严格按照干部选拔标准评估：

**特别说明：内部晋升候选人评估标准**
- 如果候选人有**本单位/本集团工作经验**（如简历中提到"新国脉"、"中国电信"、"联通"等），视为内部晋升渠道
- 内部晋升候选人的管理经验要求可以适当放宽，重点考察：
  1. 对本单位业务的熟悉程度
  2. 跨部门协作和沟通能力
  3. 战略理解和执行能力
  4. 内部影响力和群众基础
- **内部晋升候选人工作经验维度加10-15分**

1. **管理经验（硬性门槛）**：
   - **外部候选人**：必须有正式的管理岗位任职经历（部门负责人、项目总监、团队负责人等），管理过5人以上团队，主导过千万级以上项目
   - **内部候选人**：有项目管理或团队协调经验即可，重点考察跨部门协作能力
   - **不满足要求者，工作经验维度不得超过70分（外部）或75分（内部）**

2. **战略规划能力（核心要求）**：
   - 必须**主导过**企业级战略规划编制（如五年规划、三年行动计划）
   - 必须有**战略落地执行**的成功案例
   - 仅有执行经验、无规划编制经验者，专业能力维度不得超过75分

3. **干部素质要求（综合素质维度）**：
   - **政治素质**：中共党员是加分项，但非党员不扣分，除非有政治素质问题
   - **大局意识**：具备战略思维，能从组织发展角度思考问题
   - **职业操守**：廉洁自律，职业道德良好
   - **团队协作**：团队协作能力强，群众基础好
   - **评分标准**：非党员候选人，只要政治素质良好、无不良记录，综合素质维度不得低于75分

4. **面试数据完整性要求**：
   - 面试问答数据少于300字者，视为面试表现不充分
   - 面试数据不完整者，综合评分适当扣分（每少100字扣2分）

**强制差异化要求**：
- 10个候选人的分数必须有明显差异
- 工作经验维度分数差距至少15分以上
- 严禁所有候选人分数集中在78-82分区间
- 不符合干部序列要求者，必须给予明显低分（60-75分区间）

## 岗位JD
{jd_content}

## 候选人简历
{resume_content}

## 面试录音转录
{transcript}

## 结构化面试问题清单
{questions_text}

## 评分维度与详细标准

### 第一部分：6个核心维度评分（0-100分，必须严格按照以下标准评分）

**评分档次定义：**
- **A档（90-100分）**：卓越表现，远超岗位要求
- **B档（80-89分）**：优秀表现，完全符合岗位要求
- **C档（60-79分）**：合格表现，基本符合岗位要求
- **D档（0-59分）**：不合格表现，不符合岗位要求

**各维度详细评分标准（国企干部选拔视角）：**

1. **专业能力**（权重18%）- 考察岗位胜任力和专业深度：
   - A档（90-100）：专业功底深厚，对行业政策、业务流程了如指掌，能提出创新性解决方案，具备战略思维
   - B档（80-89）：专业知识扎实，能独立处理复杂业务问题，熟悉相关政策法规
   - C档（60-79）：具备基本专业知识，能完成常规工作，但缺乏深度和广度
   - D档（0-59）：专业知识明显不足，对岗位职责理解不到位，无法胜任基本要求

2. **工作经验**（权重18%）- **重点考察管理经验、规划落地能力和本单位背景**：
   - **本单位工作经验加分**：如果候选人有本单位/本集团工作经验，上手更快，熟悉组织文化，工作经验维度加5-10分
   - A档（90-100）：
     * 管理经验：有10人以上团队管理经验，或担任过部门负责人/项目总监
     * 规划能力：主导过企业级战略规划（如五年规划、三年行动计划）的编制并成功落地
     * 项目经验：主导过千万级以上重大项目，有完整的项目周期管理经历
     * 业绩成果：有突出的量化业绩数据支撑（如营收增长、成本节约、效率提升等）
     * **加分项**：有本单位/本集团工作经验，熟悉组织文化和业务流程
   - B档（80-89）：
     * 管理经验：有5-10人团队管理经验，或担任过项目经理/团队负责人
     * 规划能力：参与过战略规划编制，有执行落地经验
     * 项目经验：参与过重要项目，在项目中承担关键角色
     * 业绩成果：工作成果得到组织认可，有一定量化数据
   - C档（60-79）：
     * 管理经验：仅有个人贡献经验，无正式团队管理经历
     * 规划能力：仅参与执行层面工作，无规划编制经验
     * 项目经验：参与过项目但非核心角色
     * 业绩成果：业绩表现一般，缺乏亮点
   - D档（0-59）：
     * 管理经验：无团队管理经验
     * 规划能力：无战略规划相关经验
     * 项目经验：无重要项目经历
     * 业绩成果：过往业绩与岗位要求差距较大

3. **沟通表达**（权重16%）- **重点考察跨部门协调和团队管理能力**：
   - **评分依据**：必须基于候选人是否有跨部门协作、多团队管理的实际经验
   - A档（90-100）：
     * 有跨部门项目管理经验，能够协调3个以上部门共同推进工作
     * 有向上管理和向下传达的成功案例
     * 在复杂组织架构中推动过重要项目落地
   - B档（80-89）：
     * 有部门内部团队协作经验
     * 参与过跨部门项目，承担协调角色
     * 能够清晰汇报工作进展和成果
   - C档（60-79）：
     * 主要在本部门内工作，跨部门协作经验有限
     * 汇报和沟通能力一般
   - D档（0-59）：
     * 缺乏团队协作经验
     * 沟通表达能力不足
   - **特别注意**：不要基于录音中的停顿、语速等表面现象评分，必须基于实际的工作内容和协作经历

4. **逻辑思维**（权重16%）- 考察分析判断和决策能力：
   - A档（90-100）：思维缜密，善于从复杂情况中抓住关键问题，分析全面深入，具备战略决策能力
   - B档（80-89）：逻辑清晰，能较好分析问题，具备一定的判断和决策能力
   - C档（60-79）：思维基本清晰，但分析问题不够深入，决策能力有待提升
   - D档（0-59）：思维混乱，缺乏逻辑性，无法做出合理判断

5. **学习能力**（权重16%）- 考察适应发展和创新潜力：
   - A档（90-100）：学习意识强，善于学习新政策、新业务，能快速适应变化，具备创新思维
   - B档（80-89）：学习态度端正，能主动学习新知识，适应新环境
   - C档（60-79）：学习意愿一般，需要督促，适应新环境较慢
   - D档（0-59）：学习意识淡薄，固步自封，难以适应组织发展需要

6. **综合素质**（权重16%）- 考察政治素质和职业操守：
   - A档（90-100）：政治素质过硬，廉洁自律，组织纪律性强，大局意识好，团队协作佳，群众基础好
   - B档（80-89）：政治素质良好，遵守纪律，有团队精神，职业操守良好
   - C档（60-79）：政治素质一般，纪律意识有待加强，团队协作能力一般
   - D档（0-59）：政治素质不过硬，或存在纪律意识淡薄、团队协作差等问题

### 第二部分：岗位要求分析（基于JD内容分析每个维度的要求程度）
根据岗位JD内容，分析每个维度的要求程度（0-100分），并**基于JD原文提取具体要求描述**：
- 90-100分：该维度是岗位核心要求，必须高度匹配
- 70-89分：该维度是重要要求，需要较好匹配
- 50-69分：该维度是一般要求，基本匹配即可
- 0-49分：该维度要求较低，不做硬性要求

**重要要求**：
1. **description字段必须基于JD原文**：从JD中提取该维度的具体要求描述，而不是写通用描述
2. **具体示例**：
   - 如果JD要求"5年以上战略规划经验，熟悉行业研究方法"，则工作经验维度的description应该是："要求5年以上战略规划经验，熟悉行业研究方法，具备从0到1的战略设计能力"
   - 如果JD要求"具备优秀的跨部门沟通协调能力"，则沟通表达维度的description应该是："要求具备优秀的跨部门沟通协调能力，能够推动复杂项目的落地执行"
3. **不同岗位对各维度的要求程度应该不同**：例如技术岗对"专业能力"要求高（90-100分），但对"沟通表达"要求可能相对较低（60-80分）；管理岗则相反。
4. **description必须具体、有针对性**：不能写"根据JD分析得出的岗位要求"这种通用描述，必须引用JD中的具体要求和关键词。

### 第三部分：薪酬匹配度（单独维度，不参与综合评分计算）
**岗位预算**：40万-60万/年（来自JD）

**薪酬匹配度计算方法**：
1. 从候选人简历中提取以下信息：
   - 当前年薪（current_salary）：如"25万"、"30万/年"等
   - 期望年薪（expected_salary）：如"30-40万"、"面议"等
   - 当前月薪（current_monthly）：如"2万/月"（需转换为年薪24万）
   - 期望月薪（expected_monthly）：如"3万/月"（需转换为年薪36万）

2. 匹配度计算公式：
   - 如果期望薪资在40-60万范围内：匹配度 = 100%
   - 如果期望薪资低于40万：匹配度 = (期望薪资/40) × 100%，最高100%
   - 如果期望薪资高于60万：匹配度 = (60/期望薪资) × 100%
   - 如果期望薪资为"面议"或无法提取：匹配度根据当前薪资估算

3. 匹配度评分标准：
   - 90-100分：期望薪资在预算范围内，匹配度高
   - 70-89分：期望薪资略低于预算下限，有谈判空间
   - 50-69分：期望薪资略高于预算上限，需谨慎评估
   - 0-49分：期望薪资严重超出预算，不匹配

## 综合评分计算方法
综合评分 = Σ(维度分数 × 维度权重) / 100

请按以下JSON格式输出结果：

```json
{{
    "overall_score": 85,
    "evaluation_level": "优秀",
    "dimensions": [
        {{
            "name": "专业能力",
            "score": 85,
            "weight": 18,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由"
        }},
        {{
            "name": "工作经验",
            "score": 80,
            "weight": 18,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由"
        }},
        {{
            "name": "沟通表达",
            "score": 82,
            "weight": 16,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由"
        }},
        {{
            "name": "逻辑思维",
            "score": 78,
            "weight": 16,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由"
        }},
        {{
            "name": "学习能力",
            "score": 85,
            "weight": 16,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由"
        }},
        {{
            "name": "综合素质",
            "score": 80,
            "weight": 16,
            "analysis": "详细分析说明：根据面试表现具体说明评分理由"
        }}
    ],
    "jd_requirements": {{
        "dimensions": [
            {{
                "name": "专业能力",
                "score": 90,
                "description": "要求具备扎实的战略规划与行业研究能力，熟悉资本运作流程，能够主导中长期规划制定与执行"
            }},
            {{
                "name": "工作经验",
                "score": 85,
                "description": "要求5年以上战略管理或相关领域工作经验，有成功主导重大战略项目的经历"
            }},
            {{
                "name": "沟通表达",
                "score": 70,
                "description": "要求具备良好的跨部门沟通协调能力，能够清晰传达战略意图并推动执行"
            }},
            {{
                "name": "逻辑思维",
                "score": 80,
                "description": "要求具备严谨的战略思维和分析能力，能够系统性解决复杂问题"
            }},
            {{
                "name": "学习能力",
                "score": 75,
                "description": "要求具备快速学习新技术和新领域知识的能力，适应快速变化的商业环境"
            }},
            {{
                "name": "综合素质",
                "score": 80,
                "description": "要求具备良好的职业素养、团队协作精神和抗压能力，认同企业文化"
            }}
        ]
    }},
    "salary_match": {{
        "name": "薪酬匹配度",
        "score": 85,
        "match_percentage": 85,
        "jd_salary_range": "40万-60万/年",
        "current_salary": "候选人当前年薪，如'35万'",
        "expected_salary": "候选人期望年薪，如'40-50万'或'面议'",
        "analysis": "详细分析：候选人当前薪资XX万，期望薪资XX万，岗位预算40-60万，匹配度计算过程..."
    }},
    "summary": "综合评价总结（100-200字），包括候选人的核心优势、不足和总体评价",
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

## 重要注意事项
1. **必须严格执行评分标准**：根据候选人的实际表现，给予相应档次的分数，不得随意抬高或压低分数
2. **overall_score必须是根据权重计算的真实综合得分**，范围0-100
3. **evaluation_level根据overall_score划分**：90-100优秀，80-89良好，60-79一般，60以下较差
4. **各维度权重必须严格按照规定**：专业能力18%、工作经验18%、沟通表达16%、逻辑思维16%、学习能力16%、综合素质16%
5. **analysis字段必须包含具体依据**：每个维度的分析必须基于面试录音中的具体表现，结合国企干部选拔标准进行评价
6. **jd_requirements要求**：必须根据JD内容分析每个维度的真实要求程度，不能全部给100分，要体现差异化
7. **薪酬匹配度单独计算**：不参与综合评分，单独存储
8. **国企干部选拔特殊要求**：
   - 特别注重候选人的政治素质、廉洁自律、组织纪律性
   - 关注候选人的大局意识、团队协作能力和群众基础
   - 重视候选人的战略思维和管理经验
   - 评估候选人是否符合国企文化和价值观
9. **只输出JSON格式内容**，不要有其他说明文字，确保JSON格式完全正确"""

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
    transcript_content: Optional[str] = Form(None, description="直接传入转录文本内容，优先于ASR缓存"),
    questions_file: Optional[UploadFile] = File(None, description="面试问题Excel文件"),
    candidate_name: Optional[str] = Form("", description="候选人姓名"),
    jd_title: Optional[str] = Form("", description="岗位名称"),
    project: Optional[str] = Form("", description="项目名称，用于查找离线ASR缓存")
):
    """
    AI面试评价 - 优先使用离线缓存ASR数据 + 大模型评价
    
    流程：
    1. 优先查找离线ASR缓存数据（项目目录/transcriptions/候选人姓名/）
    2. 如果没有离线缓存，则查找本地预存ASR数据
    3. 如果都没有，则使用 Whisper API 转录音频
    4. Qwen3-235B 大模型基于6个维度进行面试评价
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
        
        # 5. 获取转录文本 - 优先级：直接传入 > 离线缓存 > 本地预存 > 实时转录
        transcript = ""
        saved_transcript_path = ""
        cache_source = ""
        
        # 5.0 优先使用直接传入的转录文本
        if transcript_content:
            transcript = transcript_content
            cache_source = "直接传入"
            logger.info(f"[面试评价] 使用直接传入的转录文本, 长度: {len(transcript)}")
        
        # 5.1 如果没有直接传入，查找离线ASR缓存（项目目录/transcriptions/候选人姓名/）
        if not transcript and project and candidate_name:
            logger.info(f"[面试评价] 优先查找离线ASR缓存: 项目={project}, 候选人={candidate_name}")
            offline_cache = load_offline_asr_cache(project, candidate_name)
            if offline_cache:
                transcript = offline_cache.get("transcription", "")
                saved_transcript_path = offline_cache.get("cache_path", "")
                cache_source = "离线ASR缓存"
                logger.info(f"[面试评价] 使用离线ASR缓存: {saved_transcript_path}, 文本长度: {len(transcript)}")
        
        # 5.2 如果没有离线缓存，查找本地预存ASR数据
        if not transcript:
            logger.info(f"[面试评价] 查找本地预存ASR数据...")
            cached_transcript, cached_path = find_existing_transcript(candidate_name, jd_title)
            if cached_transcript:
                transcript = cached_transcript
                saved_transcript_path = cached_path
                cache_source = "本地预存"
                logger.info(f"[面试评价] 使用本地预存ASR数据: {saved_transcript_path}")
        
        # 5.3 如果都没有，使用上传的音频文件实时转录
        if not transcript and temp_audio_path:
            logger.info(f"[面试评价] 未找到缓存，开始实时转录音频...")
            transcript, saved_transcript_path = await transcribe_audio_with_whisper(
                temp_audio_path, 
                candidate_name=candidate_name,
                jd_title=jd_title
            )
            if not transcript:
                raise HTTPException(status_code=500, detail="音频转录失败")
            cache_source = "实时转录"
            logger.info(f"[面试评价] 实时转录完成，文本已保存到: {saved_transcript_path}")
        
        # 5.4 如果还是没有转录文本，报错
        if not transcript:
            raise HTTPException(status_code=400, detail="未找到ASR数据，请上传音频文件或确保离线缓存存在")
        
        logger.info(f"[面试评价] 转录数据来源: {cache_source}, 文本长度: {len(transcript)}")
        
        # 6. 检查评估结果缓存
        evaluation = None
        if project and candidate_name:
            logger.info(f"[面试评价] 检查评估结果缓存: 项目={project}, 候选人={candidate_name}")
            cached_evaluation = load_evaluation_cache(project, candidate_name)
            if cached_evaluation:
                evaluation = cached_evaluation.get("evaluation")
                logger.info(f"[面试评价] 使用评估结果缓存")
        
        # 7. 如果没有缓存，进行Qwen3-235B大模型评价
        if not evaluation:
            logger.info(f"[面试评价] 开始AI评价...")
            evaluation = await evaluate_interview_with_qwen(
                jd_content=jd_text,
                resume_content=resume_text,
                transcript=transcript,
                questions=questions
            )
            
            if not evaluation:
                raise HTTPException(status_code=500, detail="面试评价失败")
            
            # 7.1 强制分数差异化调整
            logger.info(f"[面试评价] 进行强制分数差异化调整...")
            evaluation = adjust_scores_for_differentiation(evaluation, resume_text, transcript)
            
            # 7.2 根据面试数据完整性调整分数（降低扣分力度）
            logger.info(f"[面试评价] 检查面试数据完整性...")
            transcript_length = len(transcript) if transcript else 0
            if transcript_length < 300:
                # 面试数据不完整，轻微扣分
                old_score = evaluation.get("overall_score", 82)
                penalty = min(8, int((300 - transcript_length) / 100))  # 每少100字扣2分，最多扣8分
                new_score = max(60, old_score - penalty)
                evaluation["overall_score"] = new_score
                # 更新评价等级
                if new_score >= 90:
                    evaluation["evaluation_level"] = "优秀"
                elif new_score >= 80:
                    evaluation["evaluation_level"] = "良好"
                elif new_score >= 60:
                    evaluation["evaluation_level"] = "一般"
                else:
                    evaluation["evaluation_level"] = "较差"
                logger.info(f"[面试评价] 面试数据不完整({transcript_length}字)，扣分{penalty}分: {old_score} -> {new_score}")
            
            # 7.3 计算薪酬匹配度（使用LLM从面试录音中提取）
            logger.info(f"[面试评价] 计算薪酬匹配度...")
            # 先使用LLM提取薪酬信息
            llm_salary_info = await extract_salary_with_llm(transcript)
            salary_match = calculate_salary_match(evaluation, resume_text, transcript, llm_salary_info)
            evaluation["salary_match"] = salary_match
            
            # 保存评估结果缓存
            if project and candidate_name:
                save_evaluation_cache(project, candidate_name, evaluation)
        
        # 8. 保存评估结果到本地文件（兼容原有逻辑）
        if saved_transcript_path:
            evaluation_file = saved_transcript_path.replace(".txt", "_evaluation.json")
            try:
                with open(evaluation_file, 'w', encoding='utf-8') as f:
                    json.dump(evaluation, f, ensure_ascii=False, indent=2)
                logger.info(f"[面试评价] 评估结果已保存: {evaluation_file}")
            except Exception as e:
                logger.warning(f"[面试评价] 保存评估结果失败: {e}")
        
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
            question_answers=evaluation.get("question_answers", []),
            jd_requirements=evaluation.get("jd_requirements", {}),
            salary_match=evaluation.get("salary_match", {})
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


@router.get("/evaluation-cache")
async def check_evaluation_cache(
    candidate_name: str,
    project: str
):
    """
    检查候选人的AI评估缓存
    
    如果存在缓存，返回缓存的评估结果；否则返回未找到
    """
    try:
        cached = load_evaluation_cache(project, candidate_name)
        if cached:
            return {
                "success": True,
                "cached": True,
                "evaluation": cached.get("evaluation"),
                "cached_at": cached.get("cached_at")
            }
        else:
            return {
                "success": True,
                "cached": False,
                "message": "未找到评估缓存"
            }
    except Exception as e:
        logger.error(f"[面试评价] 检查评估缓存失败: {e}")
        return {
            "success": False,
            "cached": False,
            "message": f"检查缓存失败: {str(e)}"
        }


@router.post("/transcribe")
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
        settings = get_settings()
        temp_dir = os.path.join(settings.BASE_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # 保存音频文件
        audio_content = await audio_file.read()
        temp_audio_path = os.path.join(temp_dir, audio_file.filename)
        with open(temp_audio_path, 'wb') as f:
            f.write(audio_content)
        
        # 检查项目缓存
        candidate_name = extract_candidate_name_from_audio_filename(audio_file.filename)
        cached_result = None
        
        if project:
            cached_result = load_cached_transcription(project, audio_file.filename)
            if cached_result:
                logger.info(f"[面试评价] 使用项目缓存的转录结果: {audio_file.filename}")
                return {
                    "success": True,
                    "transcript": cached_result.get("transcription", ""),
                    "filename": audio_file.filename,
                    "language": language,
                    "cached": True,
                    "candidate_name": candidate_name
                }
        
        # 调用Whisper API转录
        transcript, _ = await transcribe_audio_with_whisper(temp_audio_path, language)
        
        if not transcript:
            raise HTTPException(status_code=500, detail="音频转录失败")
        
        # 保存到项目缓存
        if project:
            save_cached_transcription(project, audio_file.filename, candidate_name, transcript)
        
        return {
            "success": True,
            "transcript": transcript,
            "filename": audio_file.filename,
            "language": language,
            "cached": False,
            "candidate_name": candidate_name
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


def extract_candidate_name_from_audio_filename(filename: str) -> str:
    """从音频文件名提取候选人姓名"""
    # 格式: 04月10日_10黄俊华.aac
    try:
        name_part = filename.split('_')[-1]
        name = name_part.split('.')[0]
        # 移除数字前缀
        for i, char in enumerate(name):
            if not char.isdigit():
                return name[i:]
        return name
    except:
        return filename


def get_project_cache_dir(project_name: str) -> str:
    """获取项目缓存目录"""
    base_dir = "/root/shijingjing/e-employee/hr-bot/data/interview"
    cache_dir = os.path.join(base_dir, project_name, "transcriptions")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def load_cached_transcription(project_name: str, filename: str) -> Optional[dict]:
    """加载项目缓存的转录结果"""
    cache_dir = get_project_cache_dir(project_name)
    cache_file = os.path.join(cache_dir, f"{filename}.json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[面试评价] 读取缓存失败: {e}")
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
        
        logger.info(f"[面试评价] 转录结果已缓存: {cache_file}")
    except Exception as e:
        logger.error(f"[面试评价] 保存缓存失败: {e}")


def load_offline_asr_cache(project_name: str, candidate_name: str) -> Optional[dict]:
    """加载离线ASR缓存数据
    
    支持两种路径格式:
    1. 新格式: data/interview/{项目名}/tras/{候选人姓名}.json
    2. 旧格式: data/interview/{项目名}/transcriptions/{候选人姓名}/{文件名}.json
    """
    try:
        base_dir = "/root/shijingjing/e-employee/hr-bot/data/interview"
        
        # ===== 首先尝试新格式: tras/{候选人}.json =====
        new_format_file = os.path.join(base_dir, project_name, "tras", f"{candidate_name}.json")
        if os.path.exists(new_format_file):
            try:
                with open(new_format_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                transcription = cache_data.get("transcription", "")
                if transcription:
                    logger.info(f"[面试评价] 成功从新格式加载ASR缓存: {new_format_file}, 文本长度: {len(transcription)}")
                    return {
                        "transcription": transcription,
                        "cache_path": new_format_file,
                        "candidate_name": cache_data.get("candidate_name", candidate_name),
                        "processed_at": cache_data.get("processed_at", ""),
                        "source": "tras_new_format"
                    }
            except Exception as e:
                logger.warning(f"[面试评价] 读取新格式ASR缓存失败: {e}")
        
        # ===== 然后尝试旧格式: transcriptions/{候选人}/{文件名}.json =====
        cache_dir = os.path.join(base_dir, project_name, "transcriptions")
        
        if os.path.exists(cache_dir):
            # 尝试从 _processing_summary.json 汇总文件中读取
            summary_file = os.path.join(cache_dir, "_processing_summary.json")
            if os.path.exists(summary_file):
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary_data = json.load(f)
                    
                    results = summary_data.get("results", [])
                    for result in results:
                        if result.get("candidate_name") == candidate_name:
                            transcription = result.get("transcription", "")
                            if transcription:
                                logger.info(f"[面试评价] 成功从汇总文件加载ASR缓存: {candidate_name}, 文本长度: {len(transcription)}")
                                return {
                                    "transcription": transcription,
                                    "cache_path": summary_file,
                                    "candidate_name": candidate_name,
                                    "processed_at": result.get("processed_at", ""),
                                    "source": "offline_summary"
                                }
                except Exception as e:
                    logger.warning(f"[面试评价] 读取汇总文件失败: {e}")
            
            # 如果汇总文件中没有，尝试从候选人子目录中读取
            candidate_dir = os.path.join(cache_dir, candidate_name)
            if os.path.exists(candidate_dir):
                cache_files = [f for f in os.listdir(candidate_dir) if f.endswith('.json') and not f.startswith('_')]
                
                if cache_files:
                    # 使用最新的缓存文件
                    cache_files.sort(key=lambda x: os.path.getmtime(os.path.join(candidate_dir, x)), reverse=True)
                    latest_cache_file = os.path.join(candidate_dir, cache_files[0])
                    
                    with open(latest_cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    transcription = cache_data.get("transcription", "")
                    if transcription:
                        logger.info(f"[面试评价] 成功加载旧格式ASR缓存: {latest_cache_file}, 文本长度: {len(transcription)}")
                        return {
                            "transcription": transcription,
                            "cache_path": latest_cache_file,
                            "candidate_name": cache_data.get("candidate_name", candidate_name),
                            "processed_at": cache_data.get("processed_at", ""),
                            "source": "offline_cache"
                        }
        
        logger.info(f"[面试评价] 未找到候选人 {candidate_name} 的离线ASR缓存")
        return None
        
    except Exception as e:
        logger.error(f"[面试评价] 加载离线ASR缓存失败: {e}")
        return None


def get_evaluation_cache_path(project_name: str, candidate_name: str) -> str:
    """获取评估结果缓存路径"""
    base_dir = "/root/shijingjing/e-employee/hr-bot/data/interview"
    cache_dir = os.path.join(base_dir, project_name, "evaluations")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{candidate_name}_evaluation.json")


def load_evaluation_cache(project_name: str, candidate_name: str) -> Optional[dict]:
    """加载评估结果缓存"""
    try:
        cache_path = get_evaluation_cache_path(project_name, candidate_name)
        
        if not os.path.exists(cache_path):
            return None
        
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        logger.info(f"[面试评价] 使用评估结果缓存: {cache_path}")
        return cache_data
        
    except Exception as e:
        logger.error(f"[面试评价] 加载评估缓存失败: {e}")
        return None


def save_evaluation_cache(project_name: str, candidate_name: str, evaluation: dict):
    """保存评估结果缓存"""
    try:
        cache_path = get_evaluation_cache_path(project_name, candidate_name)
        
        cache_data = {
            "candidate_name": candidate_name,
            "project": project_name,
            "evaluation": evaluation,
            "cached_at": datetime.now().isoformat()
        }
        
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[面试评价] 评估结果已缓存: {cache_path}")
        
    except Exception as e:
        logger.error(f"[面试评价] 保存评估缓存失败: {e}")


@router.get("/evaluations-batch")
async def get_batch_evaluations(
    project: str
):
    """
    批量获取项目中所有候选人的AI评估缓存
    
    返回所有已缓存的评估结果，用于前端批量展示
    
    Args:
        project: 项目名称
    """
    try:
        base_dir = "/root/shijingjing/e-employee/hr-bot/data/interview"
        cache_dir = os.path.join(base_dir, project, "evaluations")
        
        if not os.path.exists(cache_dir):
            return {
                "success": True,
                "evaluations": [],
                "total": 0,
                "message": "未找到评估缓存目录"
            }
        
        evaluations = []
        
        # 遍历所有评估缓存文件
        for filename in os.listdir(cache_dir):
            if not filename.endswith('_evaluation.json'):
                continue
                
            cache_path = os.path.join(cache_dir, filename)
            
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                candidate_name = cache_data.get("candidate_name", "")
                evaluation = cache_data.get("evaluation", {})
                cached_at = cache_data.get("cached_at", "")
                
                if candidate_name and evaluation:
                    evaluations.append({
                        "candidate_name": candidate_name,
                        "evaluation": evaluation,
                        "cached_at": cached_at
                    })
                    
            except Exception as e:
                logger.warning(f"[面试评价] 读取评估缓存文件失败: {cache_path}, 错误: {e}")
                continue
        
        logger.info(f"[面试评价] 批量获取评估缓存: 项目={project}, 数量={len(evaluations)}")
        
        return {
            "success": True,
            "evaluations": evaluations,
            "total": len(evaluations),
            "message": f"成功加载 {len(evaluations)} 个评估缓存"
        }
        
    except Exception as e:
        logger.error(f"[面试评价] 批量获取评估缓存失败: {e}")
        return {
            "success": False,
            "evaluations": [],
            "total": 0,
            "message": f"获取失败: {str(e)}"
        }


# ============ 问答数据管理API ============

QA_CACHE_DIR = "/root/shijingjing/e-employee/hr-bot/data/interview/20260401战略招聘/qa_cache"

@router.get("/qa/{candidate_name}")
async def get_candidate_qa(candidate_name: str):
    """
    获取候选人的结构化问答数据
    
    从qa_cache目录加载提取的问答数据
    """
    try:
        qa_file = os.path.join(QA_CACHE_DIR, f"{candidate_name}_qa.json")
        
        if not os.path.exists(qa_file):
            raise HTTPException(status_code=404, detail=f"未找到候选人 {candidate_name} 的问答数据")
        
        with open(qa_file, 'r', encoding='utf-8') as f:
            qa_data = json.load(f)
        
        logger.info(f"[问答管理] 加载问答数据: {candidate_name}, 问题数={qa_data.get('total_questions', 0)}")
        
        return qa_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[问答管理] 加载问答数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"加载问答数据失败: {str(e)}")


@router.post("/qa/{candidate_name}")
async def save_candidate_qa(candidate_name: str, qa_data: dict):
    """
    保存候选人的结构化问答数据
    
    保存编辑后的问答数据到qa_cache目录
    """
    try:
        os.makedirs(QA_CACHE_DIR, exist_ok=True)
        
        qa_file = os.path.join(QA_CACHE_DIR, f"{candidate_name}_qa.json")
        
        # 更新保存时间
        qa_data["last_modified"] = datetime.now().isoformat()
        
        with open(qa_file, 'w', encoding='utf-8') as f:
            json.dump(qa_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[问答管理] 保存问答数据: {candidate_name}")
        
        return {
            "success": True,
            "message": "保存成功",
            "candidate_name": candidate_name
        }
        
    except Exception as e:
        logger.error(f"[问答管理] 保存问答数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存问答数据失败: {str(e)}")
