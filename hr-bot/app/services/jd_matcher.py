"""
JD匹配服务 - 基于LangChain和大模型分析JD与简历的匹配度
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI

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
    """JD匹配器 - 使用LangChain和大模型分析JD与简历匹配度"""

#     # 匹配分析Prompt模板
#     MATCH_ANALYSIS_PROMPT = """你是一位资深的人力资源专家，擅长分析岗位JD与候选人简历的匹配度。
#
# ## 岗位JD内容：
# {jd_content}
#
# ## 候选人简历内容：
# {resume_content}
#
# ## 分析任务：
# 请从以下6个维度进行双角度分析：
#
# ### 第一部分：JD要求分析
# 分析JD在每个维度的要求程度（重要程度0-100分，要求等级：高/中/低），并提取JD对该维度的具体要求和关键词。
# 维度名称必须与第二部分完全一致：
#
# 1. **专业技能匹配度**：JD对专业技能、技术栈的要求程度
# 2. **工作经验匹配度**：JD对工作经验年限、行业背景的要求程度
# 3. **教育背景匹配度**：JD对学历、专业、学校的要求程度
# 4. **软技能匹配度**：JD对沟通、协作、领导力等软技能的要求程度
# 5. **职业发展匹配度**：JD对职业规划、稳定性的要求程度
# 6. **文化契合度**：JD对价值观、工作风格的要求程度
#
# ### 第二部分：候选人匹配度分析
# 分析候选人在每个维度与JD要求的匹配程度（0-100分）：
#
# 1. **专业技能匹配度**：候选人的专业技能与JD要求的匹配程度
# 2. **工作经验匹配度**：候选人的工作经验与JD要求的匹配程度
# 3. **教育背景匹配度**：候选人的教育背景与JD要求的匹配程度
# 4. **软技能匹配度**：候选人的软技能与JD要求的匹配程度
# 5. **职业发展匹配度**：候选人的职业规划与JD要求的匹配程度
# 6. **文化契合度**：候选人的价值观与JD要求的匹配程度
#
# ## 输出要求：
# 请以JSON格式输出分析结果，包含：
# - overall_score: 综合匹配分数(0-100)
# - match_level: 匹配等级(优秀/良好/一般/较差)
# - jd_requirements: JD各维度要求数组（包含importance, requirement_level, description, keywords）
# - dimensions: 候选人各维度匹配详情数组（包含score, weight, analysis）
# - summary: 匹配总结(200字以内)
# - strengths: 候选人优势数组
# - weaknesses: 候选人不足数组
# - recommendations: 建议数组
#
# 输出格式示例：
# ```json
# {{
#   "overall_score": 85,
#   "match_level": "良好",
#   "jd_requirements": [
#     {{
#       "name": "专业技能匹配度",
#       "importance": 90,
#       "requirement_level": "高",
#       "description": "要求精通Python、机器学习，具备深度学习框架使用经验",
#       "keywords": ["Python", "机器学习", "深度学习", "TensorFlow"]
#     }}
#   ],
#   "dimensions": [
#     {{
#       "name": "专业技能匹配度",
#       "score": 90,
#       "weight": 0.25,
#       "analysis": "候选人精通Python和机器学习，与岗位要求高度匹配"
#     }}
#   ],
#   "summary": "候选人整体匹配度良好，技术能力强...",
#   "strengths": ["技术能力突出", "项目经验丰富"],
#   "weaknesses": ["管理经验不足"],
#   "recommendations": ["建议重点考察管理能力", "可考虑作为技术骨干培养"]
# }}
# ```
#
# 请基于JD和简历内容进行客观分析，给出合理的分数和详细的分析理由。"""
    # 匹配分析Prompt模板
    MATCH_ANALYSIS_PROMPT = """你是一位资深的新国脉文化公司的人力资源专家，擅长分析岗位JD与候选人简历的匹配度,避免过度乐观打分，确保分数具备区分度和参考价值。

    ## 岗位JD内容：
    {jd_content}

    ## 候选人简历内容：
    {resume_content}

    ## 分析任务：
    请从以下6个维度进行双角度分析,**严格控制维度匹配度不超过100分，且综合得分避免轻易出现满分**，需体现候选人与岗位的真实差距。：

    ### 第一部分：JD要求分析
    分析JD在每个维度的要求程度（重要程度0-100分，要求等级：高/中/低），并提取JD对该维度的具体要求和关键词。
    维度名称必须与第二部分完全一致：

    1. **专业技能匹配度**：JD对专业技能、技术栈、业务能力的要求程度。**注意**：专项技能（如采购、招投标等）可以弱化评估，重点关注通用管理能力和综合素质，不要求100%匹配
    2. **工作经验匹配度**：JD对工作经验年限、行业背景、管理经验的要求程度。**注意**：如果JD有明确的年龄要求（如"35周岁以下"、"40周岁以下"等），这是硬性门槛条件，必须严格评估。年龄不满足应大幅降低该维度得分（给40-60分），但不要在分析中显示年龄计算过程
    3. **教育背景匹配度**：JD对学历、专业、院校层次的要求程度
    4. **软技能匹配度**：JD对沟通、协作、领导力、执行力等软技能的要求程度
    5. **职业发展匹配度**：JD对职业规划、岗位稳定性、晋升意愿的要求程度。**重要说明**：同一家公司内部的岗位调整、晋升不算不稳定，反而是职业发展清晰、能力获得认可的表现，应给予正面评价
    6. **文化契合度**：JD对价值观、工作风格、企业适配性的要求程度。**国脉文化加分项**：对于符合国脉文化（新国脉数字文化股份有限公司）特点的候选人给予加分，包括但不限于：中共党员、央国企背景、文化行业经验、政治素质过硬、勤勉敬业、团队协作精神等

    ### 第二部分：候选人匹配度分析
    分析候选人在每个维度与JD要求的匹配程度（0-100分），**禁止轻易给满分**，需体现细微差距：

    **重要评分原则：**
    - **门槛类维度**（如教育背景）：满足门槛要求即可，不应给过高分数。满足门槛给60-75分，有优势可给76-85分，不应超过90分
    - **核心能力维度**（如工作经验、软技能）：根据实际能力匹配度评分
    - **专业技能维度**：**专项技能可以弱化**，不要求完全匹配。有相关经验即可给70-85分，具备通用管理能力可弥补专项技能不足
    - **软性素质维度**（如文化契合）：根据具体表现评分
    - **评分调整原则（不直接显示加分，融入分析中）**：对于符合以下特点的候选人，在评分时给予倾斜，但分析中不直接说"加多少分"，而是自然融入评价：
      * **现任岗位高度契合（重要）**：如果候选人目前就在目标岗位或高度相关岗位任职，各维度评分从优，但分析中不要直白提及"现任"、"兼任"等词，而是用"岗位契合度高"、"各项要求均符合"、"能力全面匹配"、"对岗位要求理解深入"等含蓄表达
      * 公司内部员工：分析中强调"熟悉组织运作"、"环境适应性强"
      * 中共党员：文化契合评分从优，分析中强调"政治素质过硬"
      * 央国企背景：工作经验评分从优，分析中强调"熟悉国企运作机制"
      * 获得荣誉表彰：软技能评分从优，分析中强调"表现突出、获得认可"
    - **简历信息冲突检查**：仔细检查候选人简历中的信息一致性，发现冲突需酌情扣分并在分析中指出
    - **整体评估原则**：不要因为某一项专项技能不匹配就否定候选人，要综合评估整体素质和可培养性

    **具体评分标准：**
    - 完全满足且有显著超出优势：90-99分（极少情况给100分）
    - 基本满足要求，表现良好：70-89分
    - 部分满足/有明显短板：40-69分
    - 严重不满足：0-39分

    **各维度评分细则：**
    1. **专业技能匹配度**：候选人的专业技能与JD要求的匹配程度
    2. **工作经验匹配度**：候选人的工作经验与JD要求的匹配程度。**注意**：不要在分析中提及年龄计算过程，仅根据是否满足年龄要求进行评分
    3. **教育背景匹配度**：**门槛类指标，默认70分**。满足学历要求给70分（默认基准分），专业对口可给75-80分，名校或高学历优势可给81-90分，严禁给满分。如发现简历冲突（如"全日制"但读书期间有工作经历），扣10-15分
    4. **软技能匹配度**：候选人的软技能与JD要求的匹配程度
    5. **职业发展匹配度**：候选人的职业规划与JD要求的匹配程度。**稳定性评估原则**：同一家公司内部的岗位调整、职级晋升是积极的职业发展信号，说明能力获得认可、职业发展路径清晰，应给予高分（80-95分）；只有频繁跳槽（不同公司间变动）才视为稳定性不足
    6. **文化契合度**：候选人的价值观与JD要求的匹配程度

    ### 加权计算规则（用于生成overall_score）：
    1.  先计算各维度**权重**：`维度权重 = 该维度importance / 所有维度importance总和`
    2.  各维度**加权得分** = `维度匹配度得分 × 维度权重`
    3.  综合得分`overall_score` = 所有维度加权得分之和（保留整数，严禁超过100分）
    4.  匹配等级划分：
    - 90-100分：优秀
    - 80-89分：良好
    - 60-79分：一般
    - 0-59分：较差

    ## 输出要求：
    请以JSON格式输出分析结果，包含：
    - overall_score: 综合匹配分数(0-100)
    - match_level: 匹配等级(优秀/良好/一般/较差)
    - jd_requirements: JD各维度要求数组（包含importance, requirement_level, description, keywords）
    - dimensions: 候选人各维度匹配详情数组（包含score, weight, analysis）
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
          "description": "要求精通Python、机器学习，具备深度学习框架使用经验",
          "keywords": ["Python", "机器学习", "深度学习", "TensorFlow"]
        }}
      ],
      "dimensions": [
        {{
          "name": "专业技能匹配度",
          "score": 90,
          "weight": 0.25,
          "analysis": "候选人精通Python和机器学习，与岗位要求高度匹配"
        }}
      ],
      "summary": "候选人整体匹配度良好，技术能力强...",
      "strengths": ["技术能力突出", "项目经验丰富"],
      "weaknesses": ["管理经验不足"],
      "recommendations": ["建议重点考察管理能力", "可考虑作为技术骨干培养"]
    }}
    ```

    请基于JD和简历内容进行客观分析，给出合理的分数和详细的分析理由。"""

    def __init__(self):
        self.settings = get_settings()
        self.llm_client = None
        self._init_llm()

    def _init_llm(self):
        """初始化LangChain LLM"""
        try:
            # 使用OpenAI兼容接口连接本地vLLM
            self.llm = ChatOpenAI(
                model_name=self.settings.vllm_model,
                openai_api_base=self.settings.openai_api_base,
                openai_api_key=self.settings.openai_api_key or "not-needed",
                temperature=0.3,
                max_tokens=2000,
            )
            logger.info(f"[JDMatcher] LangChain LLM初始化成功: {self.settings.vllm_model}")
        except Exception as e:
            logger.error(f"[JDMatcher] LangChain LLM初始化失败: {e}")
            self.llm = None

    async def analyze_match(
        self,
        jd_content: str,
        resume_content: str,
        use_remote: bool = False
    ) -> JDMatchResult:
        """
        分析JD与简历的匹配度

        Args:
            jd_content: JD文本内容
            resume_content: 简历文本内容
            use_remote: 是否使用远程大模型

        Returns:
            JDMatchResult: 匹配结果
        """
        # 强制使用远程大模型API，因为JD匹配需要处理长文本
        # 本地vLLM的4096 token限制无法满足JD匹配需求
        return await self._analyze_with_remote_api(jd_content, resume_content)

    async def _analyze_with_local_llm(
        self,
        jd_content: str,
        resume_content: str
    ) -> JDMatchResult:
        """使用本地vLLM进行匹配分析"""
        try:
            prompt = self.MATCH_ANALYSIS_PROMPT.format(
                jd_content=jd_content,
                resume_content=resume_content
            )

            messages = [
                {"role": "system", "content": "你是一位资深的人力资源专家，擅长岗位匹配分析。请严格按照JSON格式输出结果。"},
                {"role": "user", "content": prompt}
            ]

            # 使用LLM客户端
            llm_client = get_llm_client()
            result = await llm_client.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
                use_remote=False
            )

            content = result.get("content", "")
            content = content.replace("<|im_end|>", "").replace("<|im_start|>", "").replace("<|endoftext|>", "").strip()

            logger.info(f"[JDMatcher] LLM原始响应: {content[:500]}...")

            # 提取JSON
            json_data = llm_client._extract_json(content)

            logger.info(f"[JDMatcher] 提取的JSON类型: {type(json_data)}, 内容: {str(json_data)[:500]}")

            return self._parse_match_result(json_data)

        except Exception as e:
            logger.error(f"[JDMatcher] 本地LLM匹配分析失败: {e}", exc_info=True)
            return self._get_default_result()

    async def _analyze_with_remote_api(
        self,
        jd_content: str,
        resume_content: str
    ) -> JDMatchResult:
        """使用远程大模型API进行匹配分析"""
        try:
            llm_client = get_llm_client()

            prompt = self.MATCH_ANALYSIS_PROMPT.format(
                jd_content=jd_content,
                resume_content=resume_content
            )

            messages = [
                {"role": "system", "content": "你是一位资深的人力资源专家，擅长岗位匹配分析。请严格按照JSON格式输出结果。"},
                {"role": "user", "content": prompt}
            ]

            result = await llm_client.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
                use_remote=True
            )

            content = result.get("content", "")
            content = content.replace("<|im_end|>", "").replace("<|im_start|>", "").replace("<|endoftext|>", "").strip()

            # 提取JSON
            json_data = llm_client._extract_json(content)

            return self._parse_match_result(json_data)

        except Exception as e:
            logger.error(f"[JDMatcher] 远程API匹配分析失败: {e}")
            return self._get_default_result()

    def _parse_match_result(self, json_data: Dict) -> JDMatchResult:
        """解析匹配结果JSON"""
        try:
            # 检查json_data是否为字典
            if not isinstance(json_data, dict):
                logger.error(f"[JDMatcher] JSON数据不是字典类型: {type(json_data)}, 内容: {json_data}")
                return self._get_default_result()

            # 解析候选人匹配维度
            dimensions = []
            for dim_data in json_data.get("dimensions", []):
                dimensions.append(MatchDimension(
                    name=dim_data.get("name", ""),
                    score=dim_data.get("score", 0),
                    weight=dim_data.get("weight", 0.17),
                    analysis=dim_data.get("analysis", "")
                ))

            # 解析JD要求维度
            jd_requirements = []
            for jd_data in json_data.get("jd_requirements", []):
                jd_requirements.append(JDRequirementDimension(
                    name=jd_data.get("name", ""),
                    importance=jd_data.get("importance", 50),
                    requirement_level=jd_data.get("requirement_level", "中"),
                    description=jd_data.get("description", ""),
                    keywords=jd_data.get("keywords", [])
                ))

            # 检查高要求维度的匹配情况（70%参考线，不强制否定候选人）
            high_req_concerns = []
            for jd_req in jd_requirements:
                if jd_req.requirement_level == "高":
                    # 找到对应的候选人维度分数
                    candidate_dim = next(
                        (dim for dim in dimensions if dim.name == jd_req.name), None
                    )
                    if candidate_dim:
                        # 计算匹配度百分比
                        match_percent = (candidate_dim.score / jd_req.importance * 100) if jd_req.importance > 0 else 0
                        # 70%以下才作为关注点，不强制否定
                        if match_percent < 70:
                            high_req_concerns.append({
                                "name": jd_req.name,
                                "candidate_score": candidate_dim.score,
                                "jd_requirement": jd_req.importance,
                                "match_percent": match_percent
                            })

            # 如果有高要求维度匹配度较低，在汇总中提示但不改变匹配等级
            original_match_level = json_data.get("match_level", "未知")
            original_summary = json_data.get("summary", "")
            
            # 默认使用原始的match_level和summary
            match_level = original_match_level
            summary = original_summary
            
            if high_req_concerns:
                # 生成关注点的说明
                concern_details = []
                for concern in high_req_concerns:
                    concern_details.append(
                        f"{concern['name']}:候选人得分{concern['candidate_score']}分，"
                        f"JD要求{concern['jd_requirement']}分，匹配度{concern['match_percent']:.1f}%"
                    )
                
                # 在汇总中附加关注点信息，不改变原等级
                concern_note = f"\n\n【关注点】该候选人在以下高要求维度匹配度偏低（供参考）："
                concern_note += "；".join(concern_details) + "。建议面试时重点考察相关能力。"
                
                # 追加到原汇总后面
                if original_summary:
                    summary = original_summary + concern_note
                else:
                    summary = concern_note
                    
                logger.info(f"[JDMatcher] 高要求维度关注点: {high_req_concerns}")

            return JDMatchResult(
                overall_score=json_data.get("overall_score", 0),
                match_level=match_level,
                dimensions=dimensions,
                jd_requirements=jd_requirements,
                summary=summary,
                strengths=json_data.get("strengths", []),
                weaknesses=json_data.get("weaknesses", []),
                recommendations=json_data.get("recommendations", [])
            )
        except Exception as e:
            logger.error(f"[JDMatcher] 解析匹配结果失败: {e}, json_data: {json_data}")
            return self._get_default_result()

    def _get_default_result(self) -> JDMatchResult:
        """获取默认匹配结果"""
        return JDMatchResult(
            overall_score=0,
            match_level="分析失败",
            dimensions=[
                MatchDimension(name="专业技能匹配度", score=0, weight=0.25, analysis="分析失败"),
                MatchDimension(name="工作经验匹配度", score=0, weight=0.20, analysis="分析失败"),
                MatchDimension(name="教育背景匹配度", score=0, weight=0.15, analysis="分析失败"),
                MatchDimension(name="软技能匹配度", score=0, weight=0.15, analysis="分析失败"),
                MatchDimension(name="职业发展匹配度", score=0, weight=0.15, analysis="分析失败"),
                MatchDimension(name="文化契合度", score=0, weight=0.10, analysis="分析失败"),
            ],
            jd_requirements=[
                JDRequirementDimension(name="专业技能匹配度", importance=80, requirement_level="高", description="分析失败", keywords=[]),
                JDRequirementDimension(name="工作经验匹配度", importance=70, requirement_level="中", description="分析失败", keywords=[]),
                JDRequirementDimension(name="教育背景匹配度", importance=60, requirement_level="中", description="分析失败", keywords=[]),
                JDRequirementDimension(name="软技能匹配度", importance=70, requirement_level="中", description="分析失败", keywords=[]),
                JDRequirementDimension(name="职业发展匹配度", importance=60, requirement_level="中", description="分析失败", keywords=[]),
                JDRequirementDimension(name="文化契合度", importance=70, requirement_level="中", description="分析失败", keywords=[]),
            ],
            summary="分析过程出现错误，请稍后重试",
            strengths=[],
            weaknesses=[],
            recommendations=["请检查输入内容后重试"]
        )

    def get_radar_chart_data(self, match_result: JDMatchResult) -> Dict[str, Any]:
        """
        获取雷达图数据

        Args:
            match_result: 匹配结果

        Returns:
            雷达图数据格式
        """
        dimensions = match_result.dimensions

        return {
            "indicator": [
                {"name": dim.name, "max": 100}
                for dim in dimensions
            ],
            "series": [
                {
                    "name": "匹配度分析",
                    "type": "radar",
                    "data": [
                        {
                            "value": [dim.score for dim in dimensions],
                            "name": "候选人匹配度",
                            "areaStyle": {
                                "color": "rgba(102, 126, 234, 0.3)"
                            },
                            "lineStyle": {
                                "color": "#667eea",
                                "width": 2
                            },
                            "itemStyle": {
                                "color": "#667eea"
                            }
                        }
                    ]
                }
            ],
            "overall_score": match_result.overall_score,
            "match_level": match_result.match_level
        }

    def get_jd_radar_chart_data(self, match_result: JDMatchResult) -> Dict[str, Any]:
        """
        获取JD要求雷达图数据

        Args:
            match_result: 匹配结果

        Returns:
            JD要求雷达图数据格式
        """
        jd_requirements = match_result.jd_requirements

        return {
            "indicator": [
                {"name": req.name, "max": 100}
                for req in jd_requirements
            ],
            "series": [
                {
                    "name": "JD要求分析",
                    "type": "radar",
                    "data": [
                        {
                            "value": [req.importance for req in jd_requirements],
                            "name": "JD要求重要度",
                            "areaStyle": {
                                "color": "rgba(102, 126, 234, 0.3)"
                            },
                            "lineStyle": {
                                "color": "#667eea",
                                "width": 2
                            },
                            "itemStyle": {
                                "color": "#667eea"
                            }
                        }
                    ]
                }
            ],
            "jd_requirements": [
                {
                    "name": req.name,
                    "importance": req.importance,
                    "requirement_level": req.requirement_level,
                    "description": req.description,
                    "keywords": req.keywords
                }
                for req in jd_requirements
            ]
        }


# 全局JD匹配器实例
_jd_matcher: Optional[JDMatcher] = None


def get_jd_matcher() -> JDMatcher:
    """获取JD匹配器单例"""
    global _jd_matcher
    if _jd_matcher is None:
        _jd_matcher = JDMatcher()
    return _jd_matcher
