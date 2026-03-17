"""
AI适配建议服务 - 基于多维度数据生成个性化的人岗适配建议
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, date

from app.config import get_settings

logger = logging.getLogger(__name__)


class AlignmentAdvisor:
    """人岗适配AI建议生成器"""

    # 不同阶段的评估重点和权重
    STAGE_WEIGHTS = {
        "试用期": {
            "professional": 0.20,
            "adaptability": 0.30,
            "innovation": 0.10,
            "learning": 0.40,
            "attendance": 0.20,
            "political": 0.10,
            "focus": ["学习能力", "适应能力", "工作态度"],
            "description": "重点关注学习能力和适应能力，评估是否适合团队文化"
        },
        "转正初期": {
            "professional": 0.40,
            "adaptability": 0.30,
            "innovation": 0.10,
            "learning": 0.20,
            "attendance": 0.15,
            "political": 0.15,
            "focus": ["专业能力", "团队协作", "工作质量"],
            "description": "重点关注专业能力和团队协作，评估是否能独立承担工作"
        },
        "成熟期": {
            "professional": 0.35,
            "adaptability": 0.20,
            "innovation": 0.25,
            "learning": 0.15,
            "attendance": 0.10,
            "political": 0.20,
            "focus": ["专业能力", "创新能力", "业务贡献"],
            "description": "重点关注创新能力和业务贡献，评估是否能带领项目"
        },
        "晋升期": {
            "professional": 0.25,
            "adaptability": 0.15,
            "innovation": 0.30,
            "learning": 0.10,
            "attendance": 0.10,
            "political": 0.30,
            "focus": ["政治画像", "创新能力", "团队管理"],
            "description": "重点关注政治素质和领导能力，评估是否具备管理潜质"
        }
    }

    # AI建议生成Prompt
    ADVISOR_PROMPT = """你是一位资深的人力资源专家和职业规划顾问，擅长根据员工的多维度数据生成个性化的人岗适配建议。

## 员工基本信息
- 姓名：{employee_name}
- 岗位：{position}
- 部门：{department}
- 学历：{education}
- 入职日期：{hire_date}
- 当前阶段：{current_stage}

## 岗位能力模型要求（6维度标准）
{position_requirements}

## 员工实际表现数据

### 1. 六维能力评分
{ability_scores}

### 2. 试用期考核数据
{probation_data}

### 3. 近期考勤数据（近3个月）
{attendance_data}

### 4. 薪资表现（近6个月）
{salary_data}

## 当前阶段评估重点
{stage_focus}

## 请生成以下分析报告：

### 1. 综合评价（200字以内）
基于上述数据，给出该员工与岗位的适配程度综合评价。

### 2. 优势分析
列出该员工的3-5个核心优势，并说明依据。

### 3. 待提升领域
列出该员工需要改进的2-3个领域，并给出具体建议。

### 4. 阶段适配建议
基于当前阶段（{current_stage}），给出针对性的发展建议：
- 短期目标（1-3个月）
- 中期目标（3-6个月）
- 长期目标（6-12个月）

### 5. 风险预警（如有）
识别潜在风险，如：
- 能力不匹配风险
- 离职风险
- 发展瓶颈风险

### 6. 培养建议
针对该员工的特点，给出具体的培养方案：
- 培训建议
- 导师安排
- 项目历练
- 轮岗建议（如适用）

请以JSON格式输出，便于前端展示：
```json
{{
  "overall_assessment": "综合评价文本",
  "strengths": [
    {{"dimension": "维度名称", "description": "优势描述", "evidence": "数据依据"}}
  ],
  "improvements": [
    {{"dimension": "维度名称", "description": "待改进描述", "suggestion": "改进建议"}}
  ],
  "stage_recommendations": {{
    "short_term": "短期目标",
    "medium_term": "中期目标",
    "long_term": "长期目标"
  }},
  "risk_alerts": ["风险1", "风险2"],
  "development_plan": {{
    "training": ["培训建议1", "培训建议2"],
    "mentor": "导师安排建议",
    "projects": ["项目历练建议1", "项目历练建议2"],
    "rotation": "轮岗建议（如适用）"
  }},
  "match_score": 85,
  "match_level": "高度匹配/基本匹配/需要改进/不匹配"
}}
```

请基于真实数据进行分析，给出具体、可操作的建议。"""

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
            logger.info(f"[AlignmentAdvisor] 初始化成功")
        except Exception as e:
            logger.error(f"[AlignmentAdvisor] 初始化失败: {e}")
            self.client = None

    def determine_stage(self, hire_date: Optional[date], probation_status: str = "已转正") -> str:
        """根据入职时间和状态确定当前阶段"""
        if not hire_date:
            return "转正初期"

        if isinstance(hire_date, str):
            try:
                hire_date = datetime.strptime(hire_date, "%Y-%m-%d").date()
            except:
                return "转正初期"

        days_worked = (date.today() - hire_date).days

        if probation_status == "试用期":
            return "试用期"
        elif days_worked <= 180:  # 6个月内
            return "转正初期"
        elif days_worked <= 730:  # 2年内
            return "成熟期"
        else:
            return "晋升期"

    async def generate_advice(self, employee_data: Dict) -> Dict:
        """
        生成AI适配建议

        Args:
            employee_data: 包含员工所有数据的字典

        Returns:
            AI生成的建议报告
        """
        if not self.client:
            logger.error("[AlignmentAdvisor] 客户端未初始化")
            return self._get_default_advice()

        # 确定当前阶段
        current_stage = self.determine_stage(
            employee_data.get("hire_date"),
            employee_data.get("probation_status", "已转正")
        )

        # 构建Prompt
        prompt = self._build_prompt(employee_data, current_stage)

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.vllm_model,
                messages=[
                    {"role": "system", "content": "你是一位资深的人力资源专家，擅长生成个性化的人岗适配建议。请严格按照JSON格式输出。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.4,
            )

            content = response.choices[0].message.content.strip()
            # 清理特殊标记
            content = content.replace("<|im_end|>", "").replace("<|im_start|>", "").replace("<|endoftext|>", "")
            content = content.strip()

            # 提取JSON
            result = self._extract_json(content)
            result["current_stage"] = current_stage
            result["stage_weights"] = self.STAGE_WEIGHTS.get(current_stage, {})

            logger.info(f"[AlignmentAdvisor] 建议生成完成: {employee_data.get('name')}")
            return result

        except Exception as e:
            logger.error(f"[AlignmentAdvisor] 建议生成失败: {e}")
            return self._get_default_advice(current_stage)

    def _build_prompt(self, data: Dict, stage: str) -> str:
        """构建Prompt"""
        stage_info = self.STAGE_WEIGHTS.get(stage, self.STAGE_WEIGHTS["转正初期"])

        # 格式化能力分数
        ability_scores = []
        scores = data.get("scores", {})
        standards = data.get("standards", {})
        for key, name in [
            ("professional", "专业能力"),
            ("adaptability", "适应能力"),
            ("innovation", "创新能力"),
            ("learning", "学习能力"),
            ("attendance", "工时维度"),
            ("political", "政治画像")
        ]:
            actual = scores.get(key, 0)
            standard = standards.get(key, 80)
            gap = actual - standard
            ability_scores.append(f"- {name}: 实际{actual}分 / 要求{standard}分 (差距{gap:+.0f}分)")

        # 格式化试用期数据
        probation = data.get("probation_assessment", {})
        if probation:
            probation_data = f"""
- 考核总分: {probation.get('total_score', 'N/A')}分
- 专业技能: {probation.get('professional_skill_score', 'N/A')}分
- 工作业绩: {probation.get('work_performance_score', 'N/A')}分
- 工作态度: {probation.get('work_attitude_score', 'N/A')}分
- 团队协作: {probation.get('teamwork_score', 'N/A')}分
- 学习能力: {probation.get('learning_ability_score', 'N/A')}分
- 考核结果: {probation.get('assessment_result', 'N/A')}
- 评语: {probation.get('comments', 'N/A')}
"""
        else:
            probation_data = "暂无试用期考核数据"

        # 格式化考勤数据
        attendance = data.get("attendance", {})
        if attendance:
            attendance_data = f"""
- 统计月份: {attendance.get('month', 'N/A')}
- 出勤率: {attendance.get('attendance_rate', 'N/A')}%
- 工作天数: {attendance.get('work_days', 'N/A')}天
- 平均工时: {attendance.get('avg_work_hours', 'N/A')}小时
- 迟到天数: {attendance.get('late_days', 'N/A')}天
- 缺勤天数: {attendance.get('absent_days', 'N/A')}天
- 早退天数: {attendance.get('early_leave_days', 'N/A')}天
- 加班天数: {attendance.get('overtime_days', 'N/A')}天
"""
        else:
            attendance_data = "暂无考勤数据"

        # 格式化薪资数据
        salary_records = data.get("salary_records", [])
        if salary_records:
            salary_data = "\n".join([
                f"- {r.get('month', 'N/A')}: 基本工资{r.get('base_salary', 'N/A')}元, 绩效{r.get('bonus', 'N/A')}元"
                for r in salary_records[:3]
            ])
        else:
            salary_data = "暂无薪资数据"

        # 格式化岗位要求
        position_reqs = data.get("position_requirements", {})
        position_requirements = "\n".join([
            f"- {name}: {position_reqs.get(key, 80)}分"
            for key, name in [
                ("professional", "专业能力"),
                ("adaptability", "适应能力"),
                ("innovation", "创新能力"),
                ("learning", "学习能力"),
                ("attendance", "工时维度"),
                ("political", "政治画像")
            ]
        ])

        return self.ADVISOR_PROMPT.format(
            employee_name=data.get("name", "未知"),
            position=data.get("position", "未知"),
            department=data.get("department", "未知"),
            education=data.get("education", "未知"),
            hire_date=data.get("hire_date", "未知"),
            current_stage=stage,
            position_requirements=position_requirements,
            ability_scores="\n".join(ability_scores),
            probation_data=probation_data,
            attendance_data=attendance_data,
            salary_data=salary_data,
            stage_focus=f"{stage_info['description']}\n重点关注: {', '.join(stage_info['focus'])}"
        )

    def _extract_json(self, content: str) -> Dict:
        """从LLM输出中提取JSON"""
        import re

        # 清理内容中的特殊标记和多余空白
        cleaned_content = content.replace("<|im_end|>", "").replace("<|im_start|>", "").replace("<|endoftext|>", "")
        cleaned_content = cleaned_content.strip()

        # 尝试直接解析整个内容
        try:
            return json.loads(cleaned_content)
        except json.JSONDecodeError:
            pass

        # 匹配 ```json ... ``` 格式
        json_match = re.search(r'```json\s*(.*?)\s*```', cleaned_content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 匹配 ``` ... ``` 格式
        json_match = re.search(r'```\s*(.*?)\s*```', cleaned_content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试匹配最外层的大括号（处理嵌套JSON）
        # 使用栈来找到匹配的括号
        def find_matching_braces(text: str) -> str:
            stack = []
            start = -1
            for i, char in enumerate(text):
                if char == '{':
                    if not stack:
                        start = i
                    stack.append(char)
                elif char == '}':
                    if stack:
                        stack.pop()
                        if not stack:
                            return text[start:i+1]
            return ""

        json_str = find_matching_braces(cleaned_content)
        if json_str:
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.debug(f"[AlignmentAdvisor] 括号匹配JSON解析失败: {e}")
                pass

        # 尝试修复常见的JSON格式问题
        # 1. 处理单引号
        try:
            fixed_content = cleaned_content.replace("'", '"')
            return json.loads(fixed_content)
        except json.JSONDecodeError:
            pass

        # 2. 处理尾随逗号
        try:
            fixed_content = re.sub(r',(\s*[}\]])', r'\1', cleaned_content)
            return json.loads(fixed_content)
        except json.JSONDecodeError:
            pass

        # 3. 尝试从 { ... } 中提取（最宽松的匹配）
        json_match = re.search(r'\{[\s\S]*\}', cleaned_content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"[AlignmentAdvisor] 无法从响应中提取JSON，内容片段: {cleaned_content[:200]}")
        return self._get_default_advice()

    def _get_default_advice(self, stage: str = "转正初期") -> Dict:
        """获取默认建议"""
        return {
            "overall_assessment": "基于现有数据，该员工基本符合岗位要求。建议持续关注其工作表现和发展潜力。",
            "strengths": [
                {"dimension": "工作态度", "description": "工作态度端正，能够按时完成工作任务", "evidence": "考勤数据显示出勤率正常"}
            ],
            "improvements": [
                {"dimension": "专业能力", "description": "需要进一步提升专业技能", "suggestion": "建议参加相关培训，提升专业水平"}
            ],
            "stage_recommendations": {
                "short_term": "熟悉业务流程，提升基础技能",
                "medium_term": "独立承担工作任务，提升工作效率",
                "long_term": "成为业务骨干，具备带教能力"
            },
            "risk_alerts": [],
            "development_plan": {
                "training": ["参加岗位技能培训", "学习行业前沿知识"],
                "mentor": "建议安排资深同事作为导师",
                "projects": ["参与核心项目，积累实战经验"],
                "rotation": "暂不建议轮岗"
            },
            "match_score": 75,
            "match_level": "基本匹配",
            "current_stage": stage,
            "is_default": True
        }


# 全局建议生成器实例
alignment_advisor = AlignmentAdvisor()
