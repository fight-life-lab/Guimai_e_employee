"""
统一面试评估数据模型

包含：
1. 评估结果模型
2. 转录结果模型
3. 问答对模型
4. 候选人模型
5. 请求/响应模型
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============ 核心数据模型 ============

class DimensionScore(BaseModel):
    """维度评分模型"""
    name: str = Field(..., description="维度名称")
    score: int = Field(..., description="分数（0-100）", ge=0, le=100)
    weight: int = Field(..., description="权重（百分比）", ge=0, le=100)
    analysis: str = Field(default="", description="分析说明")


class SalaryMatch(BaseModel):
    """薪酬匹配度模型"""
    name: str = Field(default="薪酬匹配度", description="名称")
    score: int = Field(default=0, description="匹配分数", ge=0, le=200)  # 放宽到200，允许超过100的特殊情况
    match_percentage: int = Field(default=0, description="匹配百分比", ge=0, le=200)  # 放宽到200
    jd_salary_range: str = Field(default="", description="岗位薪资范围")
    current_salary: str = Field(default="未明确", description="当前薪资")
    expected_salary: str = Field(default="未明确", description="期望薪资")
    analysis: str = Field(default="", description="分析说明")


class QAItem(BaseModel):
    """问答项模型"""
    question: str = Field(..., description="问题内容")
    answer: str = Field(default="", description="回答内容")
    answer_summary: str = Field(default="", description="回答摘要")
    category: str = Field(default="自动识别", description="问题类别")
    score: Optional[int] = Field(default=None, description="评分", ge=0, le=100)
    evaluation: str = Field(default="", description="评价说明")
    evaluation_points: str = Field(default="", description="考察要点")
    start_time: int = Field(default=0, description="开始时间（秒）")
    end_time: int = Field(default=0, description="结束时间（秒）")


class JDRequirement(BaseModel):
    """岗位要求模型"""
    name: str = Field(..., description="维度名称")
    score: int = Field(..., description="要求程度（0-100）", ge=0, le=100)
    description: str = Field(default="", description="具体要求描述")


class JDMatchResult(BaseModel):
    """JD匹配结果模型"""
    dimensions: List[JDRequirement] = Field(default=[], description="各维度要求")
    overall_match: int = Field(default=0, description="总体匹配度")


class EvaluationResult(BaseModel):
    """面试评估结果模型"""
    overall_score: int = Field(..., description="综合评分", ge=0, le=100)
    evaluation_level: Optional[str] = Field(default="", description="评价等级")
    dimensions: List[DimensionScore] = Field(default=[], description="各维度评分详情")
    summary: str = Field(default="", description="综合评价")
    strengths: List[str] = Field(default=[], description="优势列表")
    weaknesses: List[str] = Field(default=[], description="不足列表")
    recommendations: List[str] = Field(default=[], description="建议列表")
    question_answers: List[QAItem] = Field(default=[], description="问答评价")
    salary_match: Optional[SalaryMatch] = Field(default=None, description="薪酬匹配度")
    jd_requirements: Optional[JDMatchResult] = Field(default=None, description="岗位要求分析")
    timestamp: Optional[str] = Field(default=None, description="评估时间")


class TranscriptResult(BaseModel):
    """转录结果模型"""
    transcript: str = Field(default="", description="转录文本")
    filename: str = Field(default="", description="原始文件名")
    candidate_name: str = Field(default="", description="候选人姓名")
    cached: bool = Field(default=False, description="是否来自缓存")
    processed_at: Optional[str] = Field(default=None, description="处理时间")


class Candidate(BaseModel):
    """候选人模型"""
    name: str = Field(..., description="候选人姓名")
    filename: Optional[str] = Field(default=None, description="音频文件名")
    has_transcript: bool = Field(default=False, description="是否有转录文本")
    transcript: str = Field(default="", description="转录文本")
    transcript_length: int = Field(default=0, description="转录文本长度")
    has_evaluation: bool = Field(default=False, description="是否有评估结果")
    evaluation: Optional[EvaluationResult] = Field(default=None, description="评估结果")
    status: str = Field(default="待处理", description="状态")


class Project(BaseModel):
    """项目模型"""
    name: str = Field(..., description="项目名称")
    type: str = Field(..., description="项目类型：employee/cadre")
    candidate_count: int = Field(default=0, description="候选人数")
    evaluated_count: int = Field(default=0, description="已评估人数")


# ============ 请求/响应模型 ============

class EvaluateRequest(BaseModel):
    """评估请求模型"""
    evaluation_type: str = Field(default="employee", description="评估类型：employee/cadre")
    project: str = Field(..., description="项目名称")
    candidate_name: str = Field(..., description="候选人姓名")
    jd_content: str = Field(default="", description="岗位JD内容")
    resume_content: str = Field(default="", description="简历内容")
    transcript: str = Field(default="", description="面试录音转录文本")
    force_reevaluate: bool = Field(default=False, description="是否强制重新评估")


class EvaluateResponse(BaseModel):
    """评估响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    evaluation: Optional[EvaluationResult] = Field(default=None, description="评价数据")
    candidate_name: str = Field(default="", description="候选人姓名")


class TranscribeRequest(BaseModel):
    """转录请求模型"""
    project: str = Field(..., description="项目名称")
    candidate_name: str = Field(..., description="候选人姓名")
    language: str = Field(default="zh", description="语言")


class TranscribeResponse(BaseModel):
    """转录响应模型"""
    success: bool = Field(..., description="是否成功")
    transcript: str = Field(default="", description="转录文本")
    filename: str = Field(default="", description="文件名")
    candidate_name: str = Field(default="", description="候选人姓名")
    cached: bool = Field(default=False, description="是否来自缓存")


class QAPairsResponse(BaseModel):
    """问答对响应模型"""
    success: bool = Field(..., description="是否成功")
    qa_pairs: List[QAItem] = Field(default=[], description="问答对列表")
    structured_questions: List[Dict[str, Any]] = Field(default=[], description="结构化面试问题列表")
    summary: Optional[Dict[str, Any]] = Field(default=None, description="问答覆盖总结")


class CandidatesResponse(BaseModel):
    """候选人列表响应模型"""
    success: bool = Field(..., description="是否成功")
    candidates: List[Candidate] = Field(default=[], description="候选人列表")


class ProjectsResponse(BaseModel):
    """项目列表响应模型"""
    success: bool = Field(..., description="是否成功")
    projects: List[Project] = Field(default=[], description="项目列表")


class DeleteResponse(BaseModel):
    """删除响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")


# ============ 评估类型配置 ============

class EvaluationConfig(BaseModel):
    """评估配置模型"""
    type: str = Field(..., description="评估类型")
    name: str = Field(..., description="类型名称（中文）")
    salary_min: int = Field(default=0, description="薪资下限（万/年）")
    salary_max: int = Field(default=0, description="薪资上限（万/年）")
    dimensions: List[Dict[str, Any]] = Field(default=[], description="维度权重配置")
    description: str = Field(default="", description="描述")


# 员工评估配置
EMPLOYEE_CONFIG = EvaluationConfig(
    type="employee",
    name="员工招聘",
    salary_min=24,
    salary_max=30,
    dimensions=[
        {"name": "专业能力", "weight": 20},
        {"name": "工作经验", "weight": 20},
        {"name": "沟通表达", "weight": 15},
        {"name": "逻辑思维", "weight": 15},
        {"name": "学习能力", "weight": 15},
        {"name": "综合素质", "weight": 15}
    ],
    description="适用于普通员工岗位的面试评估，注重执行力和团队协作能力"
)

# 干部评估配置
CADRE_CONFIG = EvaluationConfig(
    type="cadre",
    name="干部选拔",
    salary_min=40,
    salary_max=60,
    dimensions=[
        {"name": "专业能力", "weight": 18},
        {"name": "工作经验", "weight": 18},
        {"name": "沟通表达", "weight": 16},
        {"name": "逻辑思维", "weight": 16},
        {"name": "学习能力", "weight": 16},
        {"name": "综合素质", "weight": 16}
    ],
    description="适用于管理干部岗位的面试评估，注重管理经验和战略思维"
)


def get_evaluation_config(evaluation_type: str) -> EvaluationConfig:
    """获取评估配置"""
    if evaluation_type == "cadre":
        return CADRE_CONFIG
    return EMPLOYEE_CONFIG