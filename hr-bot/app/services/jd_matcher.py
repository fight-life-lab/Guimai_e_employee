"""
JD匹配服务 - 基于大模型分析JD与简历的匹配度
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)


class MatchDimension(BaseModel):
    """匹配维度分数"""
    name: str = Field(..., description="维度名称")
    score: int = Field(..., description="匹配分数(0-100)", ge=0, le=100)
    weight: float = Field(..., description="权重", ge=0, le=1)
    analysis: str = Field(..., description="分析说明")


class JDRequirementDimension(BaseModel):
    """JD要求维度"""
    name: str = Field(..., description="维度名称")
    importance: int = Field(..., description="重要程度(0-100)", ge=0, le=100)
    requirement_level: str = Field(..., description="要求等级(高/中/低)")
    description: str = Field(..., description="JD对该维度的具体要求描述")
    keywords: List[str] = Field(default=[], description="关键词")


class JDMatchResult(BaseModel):
    """JD匹配结果"""
    overall_score: float = Field(..., description="综合匹配分数(0-100)")
    match_level: str = Field(..., description="匹配等级")
    dimensions: List[MatchDimension] = Field(..., description="各维度匹配详情")
    jd_requirements: List[JDRequirementDimension] = Field(..., description="JD各维度要求")
    summary: str = Field(..., description="匹配总结")
    strengths: List[str] = Field(default=[], description="候选人优势")
    weaknesses: List[str] = Field(default=[], description="候选人不足")
    recommendations: List[str] = Field(default=[], description="建议")


class JDMatcher:
    """JD匹配器 - 使用大模型分析JD与简历匹配度"""

    MATCH_ANALYSIS_PROMPT = """你是一位资深的新国脉文化公司的人力资源专家，擅长分析岗位JD与候选人简历的匹配度,避免过度乐观打分，确保分数具备区分度和参考价值。

    ## 岗位JD内容：
    {jd_content}

    ## 候选人简历内容：
    {resume_content}

    ## 分析任务：
    请从以下7个维度进行双角度分析,严格控制维度匹配度不超过100分，且综合得分避免轻易出现满分，需体现候选人与岗位的真实差距。：

    ### 第一部分：JD要求分析
    分析JD在每个维度的要求程度（重要程度0-100分，要求等级：高/中/低），并提取JD对该维度的具体要求和关键词。
    维度名称必须与第二部分完全一致：

    1. **专业技能匹配度**：JD对专业技能、技术栈、业务能力的要求程度。注意：专项技能（如采购、招投标等）可以弱化评估，重点关注通用管理能力和综合素质，不要求100%匹配
    2. **工作经验匹配度**：JD对工作经验年限、行业背景、管理经验的要求程度。注意：如果JD有明确的年龄要求（如"35周岁以下"、"40周岁以下"等），这是硬性门槛条件，必须严格评估。年龄不满足应大幅降低该维度得分（给40-60分），但不要在分析中显示年龄计算过程
    3. **教育背景匹配度**：JD对学历、专业、院校层次的要求程度
    4. **软技能匹配度**：JD对沟通、协作、领导力、执行力等软技能的要求程度
    5. **职业发展匹配度**：JD对职业规划、岗位稳定性、晋升意愿的要求程度。重要说明：同一家公司内部的岗位调整、晋升不算不稳定，反而是职业发展清晰、能力获得认可的表现，应给予正面评价
    6. **文化契合度**：JD对价值观、工作风格、企业文化适应性的要求程度
    7. **核心能力匹配度**：JD对岗位核心胜任能力的要求程度

    ### 第二部分：候选人匹配度分析
    分析候选人在每个维度与JD要求的匹配程度（0-100分），匹配度计算方式为：候选人具备的能力/岗位要求的能力×100%：

    1. **专业技能匹配度**：候选人的专业技能与JD要求的匹配程度
    2. **工作经验匹配度**：候选人的工作经验与JD要求的匹配程度
    3. **教育背景匹配度**：候选人的教育背景与JD要求的匹配程度
    4. **软技能匹配度**：候选人的软技能与JD要求的匹配程度
    5. **职业发展匹配度**：候选人的职业规划与JD要求的匹配程度
    6. **文化契合度**：候选人的价值观与JD要求的匹配程度
    7. **核心能力匹配度**：候选人的核心胜任能力与JD要求的匹配程度

    ## 评分规则：
    - **90-100分**：完全匹配，远超岗位要求
    - **80-89分**：优秀匹配，完全符合岗位要求
    - **70-79分**：良好匹配，基本符合岗位要求
    - **60-69分**：合格匹配，勉强符合岗位要求
    - **0-59分**：不匹配，不符合岗位要求

    ## 输出要求：
    请以JSON格式输出分析结果，包含：
    - overall_score: 综合匹配分数(0-100)，必须根据各维度权重计算得出
    - match_level: 匹配等级(优秀/良好/一般/较差)
    - jd_requirements: JD各维度要求数组（包含name, importance, requirement_level, description, keywords）
    - dimensions: 候选人各维度匹配详情数组（包含name, score, weight, analysis）
    - summary: 匹配总结(200字以内)
    - strengths: 候选人优势数组
    - weaknesses: 候选人不足数组
    - recommendations: 建议数组

    输出格式示例：
    ```json
    {{
      "overall_score": 85,
      "match_level": "良好",
      "jd_requirements": [
        {{
          "name": "专业技能匹配度",
          "importance": 90,
          "requirement_level": "高",
          "description": "要求精通Python、机器学习",
          "keywords": ["Python", "机器学习"]
        }}
      ],
      "dimensions": [
        {{
          "name": "专业技能匹配度",
          "score": 90,
          "weight": 0.15,
          "analysis": "候选人精通Python和机器学习，与岗位要求高度匹配"
        }}
      ],
      "summary": "候选人整体匹配度良好",
      "strengths": ["技术能力突出"],
      "weaknesses": ["管理经验不足"],
      "recommendations": ["建议重点考察管理能力"]
    }}
    ```

    请基于JD和简历内容进行客观分析，给出合理的分数和详细的分析理由。"""

    def __init__(self):
        self.client = get_llm_client()
        self.settings = get_settings()

    async def analyze(self, jd_content: str, resume_content: str) -> Optional[JDMatchResult]:
        """
        分析JD与简历的匹配度
        
        Args:
            jd_content: 岗位JD内容
            resume_content: 候选人简历内容
        
        Returns:
            JDMatchResult 对象或 None
        """
        try:
            prompt = self.MATCH_ANALYSIS_PROMPT.format(
                jd_content=jd_content,
                resume_content=resume_content
            )
            
            response = await self.client.call(prompt, temperature=0.3, max_tokens=4000)
            if not response:
                logger.error("[JDMatcher] LLM调用失败")
                return None
            
            result = self._parse_response(response)
            if result:
                return JDMatchResult(**result)
            
            return None
        except Exception as e:
            logger.error(f"[JDMatcher] 分析失败: {e}")
            return None

    def _parse_response(self, response: str) -> Optional[dict]:
        """
        解析LLM响应
        
        Args:
            response: LLM响应文本
        
        Returns:
            解析后的字典或 None
        """
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = response[start:end]
                return json.loads(json_str)
            return None
        except json.JSONDecodeError as e:
            logger.error(f"[JDMatcher] JSON解析失败: {e}")
            return None


_jd_matcher = None

def get_jd_matcher() -> JDMatcher:
    """获取JD匹配器实例（单例）"""
    global _jd_matcher
    if _jd_matcher is None:
        _jd_matcher = JDMatcher()
    return _jd_matcher
