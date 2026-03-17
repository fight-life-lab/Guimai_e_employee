"""
岗位JD分析服务 - 基于大模型分析岗位JD，生成能力模型分数
"""

import json
import logging
from typing import Dict, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database.models import PositionCapabilityModel
from app.config import get_settings

logger = logging.getLogger(__name__)


class JDAnalyzer:
    """岗位JD分析器 - 使用大模型分析JD生成能力模型"""

    # 分析JD的Prompt模板
    JD_ANALYSIS_PROMPT = """你是一位资深的人力资源专家，擅长根据岗位JD（职位描述）分析岗位能力要求。

请根据以下岗位JD内容，分析该岗位在6个维度上的能力要求分数（0-100分）。

## 岗位JD内容：
{jd_content}

## 分析维度说明：

1. **专业能力（professional）**：岗位对专业技能、技术能力的要求程度
   - 高技术门槛岗位（如算法、架构师）：85-95分
   - 中等技术门槛岗位（如开发、数据分析）：75-85分
   - 通用技术岗位（如运营、HR）：65-75分

2. **适应能力（adaptability）**：岗位对快速适应变化、多任务处理、跨部门协作的要求
   - 需要频繁对接多部门/快速响应变化：85-95分
   - 需要一定协调沟通：75-85分
   - 相对稳定独立的工作：65-75分

3. **创新能力（innovation）**：岗位对创新思维、探索新技术/新方法的要求
   - 需要探索前沿技术/创新解决方案：85-95分
   - 需要一定创新优化：75-85分
   - 执行标准化工作：65-75分

4. **学习能力（learning）**：岗位对持续学习新技术/新知识的要求
   - 技术更新快、需要持续学习：85-95分
   - 需要定期学习更新：75-85分
   - 知识相对稳定：65-75分

5. **工时维度（attendance）**：岗位对出勤稳定性、工作强度的要求
   - 需要高强度/高稳定性：85-95分
   - 标准工时要求：75-85分
   - 弹性工作制：65-75分

6. **政治画像（political）**：岗位对政治素质、企业文化契合度的要求
   - 管理岗/敏感岗位：85-95分
   - 普通岗位：75-85分
   - 技术/独立岗位：65-75分

## 输出要求：

请以JSON格式输出分析结果，包含：
1. 各维度分数（0-100的整数）
2. 每个维度的分析理由（为什么给这个分数）
3. 对该岗位的整体评价

输出格式示例：
```json
{{
  "scores": {{
    "professional": 90,
    "adaptability": 85,
    "innovation": 95,
    "learning": 90,
    "attendance": 80,
    "political": 80
  }},
  "analysis": {{
    "professional": "该岗位要求精通机器学习算法和深度学习框架，需要扎实的计算机科学基础，技术门槛高",
    "adaptability": "需要与产品、工程等多个团队紧密协作，适应业务需求变化",
    "innovation": "需要探索大模型等前沿技术在推荐系统中的应用，创新要求高",
    "learning": "需要跟进推荐算法和AI领域最新技术进展，学习要求高",
    "attendance": "标准工时要求，项目紧张时可能需要加班",
    "political": "普通技术岗位，标准政治要求"
  }},
  "overall_evaluation": "这是一个高技术门槛的算法岗位，对专业能力、创新能力和学习能力要求极高，适合技术能力强、善于学习的候选人"
}}
```

请基于JD内容进行分析，给出合理的分数和详细的分析理由。"""

    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self._init_client()

    def _init_client(self):
        """初始化OpenAI客户端"""
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                base_url=self.settings.openai_api_base,
                api_key=self.settings.openai_api_key,
            )
            logger.info(f"[JDAnalyzer] 初始化成功，使用模型: {self.settings.vllm_model}")
        except Exception as e:
            logger.error(f"[JDAnalyzer] 初始化失败: {e}")
            self.client = None

    async def analyze_jd(self, jd_content: str, position_name: str, department: str) -> Dict:
        """
        分析岗位JD，生成能力模型分数

        Args:
            jd_content: JD文本内容
            position_name: 岗位名称
            department: 部门

        Returns:
            {
                "scores": {...},
                "analysis": {...},
                "overall_evaluation": "...",
                "raw_response": "..."
            }
        """
        if not self.client:
            logger.error("[JDAnalyzer] 客户端未初始化")
            return self._get_default_result()

        prompt = self.JD_ANALYSIS_PROMPT.format(jd_content=jd_content)

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.vllm_model,
                messages=[
                    {"role": "system", "content": "你是一位资深的人力资源专家，擅长岗位能力分析。请严格按照JSON格式输出结果。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.3,  # 降低温度以获得更稳定的输出
            )

            content = response.choices[0].message.content.strip()
            # 清理大模型输出中的特殊标记
            content = content.replace("<|im_end|>", "").replace("<|im_start|>", "").replace("<|endoftext|>", "")
            content = content.strip()

            # 提取JSON部分
            json_result = self._extract_json(content)

            logger.info(f"[JDAnalyzer] JD分析完成: {position_name} - {department}")
            logger.debug(f"[JDAnalyzer] 分析结果: {json_result}")

            return {
                **json_result,
                "raw_response": content,
                "position_name": position_name,
                "department": department,
                "analysis_time": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"[JDAnalyzer] 分析失败: {e}")
            return self._get_default_result()

    def _extract_json(self, content: str) -> Dict:
        """从LLM输出中提取JSON"""
        try:
            # 尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试从代码块中提取
        import re

        # 匹配 ```json ... ``` 格式
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 匹配 ``` ... ``` 格式
        json_match = re.search(r'```\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试从 { ... } 中提取
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"[JDAnalyzer] 无法从响应中提取JSON: {content[:200]}")
        return self._get_default_result()

    def _get_default_result(self) -> Dict:
        """获取默认分析结果"""
        return {
            "scores": {
                "professional": 80,
                "adaptability": 80,
                "innovation": 80,
                "learning": 80,
                "attendance": 80,
                "political": 80
            },
            "analysis": {
                "professional": "使用默认分数",
                "adaptability": "使用默认分数",
                "innovation": "使用默认分数",
                "learning": "使用默认分数",
                "attendance": "使用默认分数",
                "political": "使用默认分数"
            },
            "overall_evaluation": "分析失败，使用默认分数",
            "raw_response": "",
            "is_default": True
        }

    async def save_analysis_result(self, db: AsyncSession, analysis_result: Dict) -> bool:
        """
        保存JD分析结果到数据库

        Args:
            db: 数据库会话
            analysis_result: 分析结果

        Returns:
            是否保存成功
        """
        try:
            position_name = analysis_result.get("position_name")
            department = analysis_result.get("department")
            scores = analysis_result.get("scores", {})
            analysis = analysis_result.get("analysis", {})

            # 查询是否已存在
            result = await db.execute(
                select(PositionCapabilityModel)
                .where(
                    and_(
                        PositionCapabilityModel.position_name == position_name,
                        PositionCapabilityModel.department == department
                    )
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # 更新现有记录
                existing.professional_standard = scores.get("professional", 80)
                existing.adaptability_standard = scores.get("adaptability", 80)
                existing.innovation_standard = scores.get("innovation", 80)
                existing.learning_standard = scores.get("learning", 80)
                existing.attendance_standard = scores.get("attendance", 80)
                existing.political_standard = scores.get("political", 80)
                existing.description = analysis_result.get("overall_evaluation", "")
                existing.requirements = json.dumps(analysis, ensure_ascii=False)
            else:
                # 创建新记录
                new_model = PositionCapabilityModel(
                    position_name=position_name,
                    department=department,
                    professional_standard=scores.get("professional", 80),
                    adaptability_standard=scores.get("adaptability", 80),
                    innovation_standard=scores.get("innovation", 80),
                    learning_standard=scores.get("learning", 80),
                    attendance_standard=scores.get("attendance", 80),
                    political_standard=scores.get("political", 80),
                    description=analysis_result.get("overall_evaluation", ""),
                    requirements=json.dumps(analysis, ensure_ascii=False)
                )
                db.add(new_model)

            await db.commit()
            logger.info(f"[JDAnalyzer] 分析结果已保存: {position_name} - {department}")
            return True

        except Exception as e:
            logger.error(f"[JDAnalyzer] 保存分析结果失败: {e}")
            await db.rollback()
            return False


# 全局JD分析器实例
jd_analyzer = JDAnalyzer()
