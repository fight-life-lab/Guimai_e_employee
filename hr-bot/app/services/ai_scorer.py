"""
AI评分服务 - 让大模型基于原始数据计算6维度分数
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

from app.config import get_settings

logger = logging.getLogger(__name__)


class AIScorer:
    """AI评分器 - 使用大模型基于原始数据计算6维度分数"""

    # 已转正员工AI评分Prompt（精简版）
    SCORING_PROMPT_REGULAR = """评分。员工：{employee_name}，{position}，{department}，{education}，职称：{professional_title}

试用期：{probation_raw_data}
考勤：{attendance_raw_data}
薪资：{salary_raw_data}

【评分规则】
1. 专业能力：试用期考核分直接作为分数（如87分=87分），无考核数据按薪资稳定性
2. 适应能力：迟到>5次或占工作天数>50% → 20-40分；迟到3-5次 → 60-75分；无迟到 → 90-100分
3. 创新能力：有职称 → 90-100分；无职称 → 默认60分
4. 学习能力：有职称 → 90-100分；硕士无职称 → 70-80分；本科无职称 → 60分
5. 工时维度：同适应能力标准
6. 品质态度：同适应能力标准

输出JSON：
{{
  "scores": {{"professional": 87, "adaptability": 40, "innovation": 90, "learning": 90, "attendance": 40, "political": 40}},
  "reasoning": {{"professional": "试用期考核XX分", "adaptability": "迟到多", "innovation": "有职称", "learning": "硕士有职称", "attendance": "迟到多", "political": "迟到多"}},
  "overall_assessment": "良好",
  "key_strengths": [],
  "key_improvements": []
}}"""

    # 试用期员工AI评分Prompt（精简版）
    SCORING_PROMPT_PROBATION = """评分。员工：{employee_name}，{position}，{department}，{education}，职称：{professional_title}

试用期：{probation_raw_data}
考勤：{attendance_raw_data}
薪资：{salary_raw_data}

【评分规则】
1. 专业能力：薪资波动>30% → 50-65分；薪资稳定（波动<10%） → 85-95分
2. 适应能力：无迟到 → 90-100分；迟到>5次 → 20-40分
3. 创新能力：有职称 → 85-95分；无职称 → 60-75分
4. 学习能力：有职称 → 85-95分；本科无职称 → 60-75分
5. 工时维度：同适应能力标准
6. 品质态度：同适应能力标准

【重要】根据上方实际数据评分，不要照搬示例分数！
- 如果无迟到，适应能力给90-100分
- 如果薪资稳定，专业能力给85-95分

输出JSON（根据实际数据填写）：
{{
  "scores": {{"professional": 90, "adaptability": 95, "innovation": 70, "learning": 70, "attendance": 95, "political": 95}},
  "reasoning": {{"professional": "薪资稳定", "adaptability": "无迟到", "innovation": "无职称", "learning": "本科无职称", "attendance": "无迟到", "political": "无违纪"}},
  "overall_assessment": "良好",
  "key_strengths": [],
  "key_improvements": []
}}"""

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
            logger.info(f"[AIScorer] 初始化成功")
        except Exception as e:
            logger.error(f"[AIScorer] 初始化失败: {e}")
            self.client = None

    async def calculate_scores(self, employee_data: Dict) -> Dict:
        """
        使用AI计算6维度分数

        Args:
            employee_data: 员工原始数据

        Returns:
            AI计算的分数和评分理由
        """
        if not self.client:
            logger.error("[AIScorer] 客户端未初始化")
            return self._get_default_scores()

        # 根据是否有试用期考核数据选择不同的prompt
        has_probation = bool(employee_data.get("probation_assessment"))
        prompt = self._build_prompt(employee_data, has_probation)

        # 根据员工状态选择不同的system message
        if has_probation:
            system_msg = "你是一位资深的人力资源评估专家，擅长基于原始数据进行综合评分。该员工已转正，有试用期考核数据。请严格按照JSON格式输出。"
        else:
            system_msg = "你是一位资深的人力资源评估专家，擅长基于原始数据进行综合评分。该员工处于试用期，尚未转正，没有试用期考核数据，必须基于薪资和考勤数据进行评分。请严格按照JSON格式输出。"

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.vllm_model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.1,
            )

            content = response.choices[0].message.content.strip()
            content = content.replace("<|im_end|>", "").replace("<|im_start|>", "").replace("<|endoftext|>", "")
            content = content.strip()

            result = self._extract_json(content)
            logger.info(f"[AIScorer] AI评分完成: {employee_data.get('name')} ({'已转正' if has_probation else '试用期'})")
            logger.info(f"[AIScorer] AI原始响应: {content[:800]}")
            logger.info(f"[AIScorer] AI解析结果: {result}")

            # 检查是否使用了默认分数（说明AI返回格式有问题或评分不合理）
            scores = result.get('scores', {})
            if all(v == 75 for v in scores.values() if isinstance(v, (int, float))):
                logger.warning(f"[AIScorer] AI返回了全默认分数75，原始响应: {content[:500]}")

            return result

        except Exception as e:
            logger.error(f"[AIScorer] AI评分失败: {e}")
            return self._get_default_scores()

    def _build_prompt(self, data: Dict, has_probation: bool = False) -> str:
        """构建Prompt"""
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
- 考核评语: {probation.get('comments', 'N/A')}
"""
        else:
            probation_data = "【重要】该员工尚未转正，无试用期考核数据。必须基于薪资和考勤数据评分。"

        # 格式化考勤数据 - 包含最近6个月详细统计
        attendance = data.get("attendance", {})
        if attendance:
            # 最近一个月详细数据
            latest_month = attendance.get('month', 'N/A')
            work_days = attendance.get('work_days', 0)
            late_days = attendance.get('late_days', 0)
            absent_days = attendance.get('absent_days', 0)
            early_leave_days = attendance.get('early_leave_days', 0)
            leave_days = attendance.get('leave_days', 0)
            abnormal_days = attendance.get('abnormal_days', 0)
            
            # 计算迟到占工作天数的比例
            late_ratio = (late_days / work_days * 100) if work_days > 0 else 0
            
            attendance_data = f"""最近一个月({latest_month})详细情况：
- 出勤率: {attendance.get('attendance_rate', 'N/A')}%
- 工作天数: {work_days}天
- 平均工时: {attendance.get('avg_work_hours', 'N/A')}小时
- 【重要】迟到: {late_days}天（占工作天数{late_ratio:.1f}%）
- 缺勤: {absent_days}天, 早退: {early_leave_days}天
- 请假天数: {leave_days}天
- 异常天数: {abnormal_days}天（异常不等于迟到，可能是数据问题）
- 总工时: {attendance.get('total_work_hours', 'N/A')}小时

【关键数据】本月工作{work_days}天，迟到{late_days}天，异常{abnormal_days}天，迟到比例{late_ratio:.1f}%

【重要说明】只有迟到状态才算违纪，异常可能是数据导入问题，不算违纪。"""
            
            # 最近6个月平均工时趋势
            yearly_data = attendance.get('yearly_avg_hours', [])
            if yearly_data:
                # 取最近6个月
                recent_6_months = yearly_data[-6:] if len(yearly_data) >= 6 else yearly_data
                attendance_data += "\n\n【近6个月考勤趋势分析】"
                for month_data in recent_6_months:
                    month = month_data.get('month', 'N/A')
                    avg_hours = month_data.get('avg_hours', 'N/A')
                    attendance_data += f"\n- {month}: 平均工时{avg_hours}小时"
                
                # 计算工时波动情况
                if len(recent_6_months) >= 2:
                    hours_list = [m.get('avg_hours', 0) for m in recent_6_months if m.get('avg_hours')]
                    if hours_list:
                        max_hours = max(hours_list)
                        min_hours = min(hours_list)
                        avg_hours_all = sum(hours_list) / len(hours_list)
                        attendance_data += f"\n\n【工时统计】最高{max_hours}小时/月, 最低{min_hours}小时/月, 平均{avg_hours_all:.2f}小时/月"
        else:
            attendance_data = "暂无考勤数据"

        # 格式化薪资数据 - 区分基本工资和绩效工资
        salary_records = data.get("salary_records", [])
        hire_date = data.get("hire_date", "")
        if salary_records:
            salary_lines = []
            base_salaries = []
            bonuses = []
            
            # 排除首月（第一个月）数据，因为首月可能包含补发
            # 按月份排序，排除最早的一个月
            sorted_records = sorted(salary_records, key=lambda x: x.get('month', ''), reverse=True)
            filtered_records = sorted_records[:-1] if len(sorted_records) > 1 else sorted_records  # 排除最早的一个月
            
            for i, r in enumerate(filtered_records[:6]):
                month = r.get('month', 'N/A')
                base = r.get('base_salary', 0) or 0
                bonus = r.get('bonus', 0) or 0
                base_salaries.append(base)
                bonuses.append(bonus)
                
                # 判断是否是首月（根据入职日期）
                is_first_month = False
                if hire_date and month != 'N/A':
                    try:
                        hire_year_month = hire_date[:7]  # YYYY-MM
                        if month == hire_year_month:
                            is_first_month = True
                    except:
                        pass
                # 首月薪资可能包含多个月份的数据，评分时需考虑
                marker = " 【首月，已排除】" if is_first_month else ""
                salary_lines.append(f"- {month}: 基本工资{base}元 + 绩效工资{bonus}元 = 合计{base+bonus}元{marker}")
            
            # 计算薪资变化趋势（排除首月后）
            if len(base_salaries) >= 2:
                first_base = base_salaries[-1]  # 最早的（排除首月后的）
                last_base = base_salaries[0]    # 最新的
                base_change = ((last_base - first_base) / first_base * 100) if first_base > 0 else 0
                
                first_bonus = bonuses[-1]
                last_bonus = bonuses[0]
                bonus_change = ((last_bonus - first_bonus) / first_bonus * 100) if first_bonus > 0 else 0
                
                salary_trend = f"\n\n【薪资变化分析（已排除首月）】"
                salary_trend += f"\n- 基本工资: 从{first_base}元 → {last_base}元 (变化{base_change:+.1f}%)"
                salary_trend += f"\n- 绩效工资: 从{first_bonus}元 → {last_bonus}元 (变化{bonus_change:+.1f}%)"
                
                if abs(base_change) > 10:
                    salary_trend += "\n- 【注意】基本工资变化>10%，可能涉及岗级调整"
                if bonus_change > 20:
                    salary_trend += "\n- 【说明】绩效工资大幅上升，说明考核表现优秀"
                elif bonus_change < -20:
                    salary_trend += "\n- 【警告】绩效工资大幅下降，说明考核表现不佳"
                    
                salary_data = "\n".join(salary_lines) + salary_trend
            else:
                salary_data = "\n".join(salary_lines)
        else:
            salary_data = "暂无薪资数据"

        # 简历信息
        professional_title = data.get('professional_title')
        title_str = professional_title if professional_title else "无"
        resume_info = f"- 学历: {data.get('education', 'N/A')}\n- 岗位: {data.get('position', 'N/A')}\n- 部门: {data.get('department', 'N/A')}\n- 职称: {title_str}"

        # 根据是否有试用期数据选择不同的prompt模板
        prompt_template = self.SCORING_PROMPT_REGULAR if has_probation else self.SCORING_PROMPT_PROBATION

        return prompt_template.format(
            employee_name=data.get("name", "未知"),
            position=data.get("position", "未知"),
            department=data.get("department", "未知"),
            education=data.get("education", "未知"),
            professional_title=title_str,
            hire_date=data.get("hire_date", "未知"),
            probation_raw_data=probation_data,
            attendance_raw_data=attendance_data,
            salary_raw_data=salary_data,
            resume_info=resume_info
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
                logger.debug(f"[AIScorer] 括号匹配JSON解析失败: {e}")
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
        json_str = find_matching_braces(cleaned_content)
        if json_str:
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 4. 尝试修复不完整的JSON（AI输出被截断的情况）
        # 尝试提取 scores 部分
        scores_match = re.search(r'"scores"\s*:\s*\{([^}]+)\}', cleaned_content)
        if scores_match:
            try:
                scores_str = '{' + scores_match.group(1) + '}'
                scores = json.loads(scores_str)
                logger.info(f"[AIScorer] 从不完整JSON中提取到scores: {scores}")
                return {
                    "scores": scores,
                    "reasoning": {k: "基于AI评分" for k in scores.keys()},
                    "overall_assessment": "AI评分完成（部分数据）",
                    "key_strengths": [],
                    "key_improvements": []
                }
            except json.JSONDecodeError:
                pass

        logger.warning(f"[AIScorer] 无法从响应中提取JSON，内容片段: {cleaned_content[:200]}")
        return self._get_default_scores()

    def _get_default_scores(self) -> Dict:
        """获取默认分数"""
        return {
            "scores": {
                "professional": 75,
                "adaptability": 75,
                "innovation": 75,
                "learning": 75,
                "attendance": 75,
                "political": 75
            },
            "reasoning": {
                "professional": "使用默认分数",
                "adaptability": "使用默认分数",
                "innovation": "使用默认分数",
                "learning": "使用默认分数",
                "attendance": "使用默认分数",
                "political": "使用默认分数"
            },
            "overall_assessment": "AI评分失败，使用默认分数",
            "key_strengths": [],
            "key_improvements": [],
            "is_default": True
        }


# 全局AI评分器实例
ai_scorer = AIScorer()
