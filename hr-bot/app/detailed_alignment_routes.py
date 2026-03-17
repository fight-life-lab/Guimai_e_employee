"""详细人岗适配分析API路由 - 包含工时管理、双雷达图对比等功能."""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, case

from app.database.models import get_async_session
from app.database.models import (
    Employee, AttendanceRecord, SalaryRecord,
    PositionCapabilityModel, AttendancePolicy, PositionDescription,
    ProbationAssessment
)
from app.config import get_settings
from app.services.alignment_advisor import alignment_advisor
from app.services.ai_scorer_v2 import ai_scorer_v2

router = APIRouter(prefix="/api/v1/alignment", tags=["详细人岗适配分析"])


# ============ LLM 客户端 ============

class LLMClient:
    """大模型客户端 - 用于生成结论和建议."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """初始化OpenAI客户端（兼容vLLM）."""
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                base_url=self.settings.openai_api_base,
                api_key=self.settings.openai_api_key,
            )
            logger.info(f"[LLMClient] 初始化成功，使用模型: {self.settings.vllm_model}")
        except Exception as e:
            logger.error(f"[LLMClient] 初始化失败: {e}")
            self.client = None
    
    async def generate(self, prompt: str, max_tokens: int = 500) -> str:
        """调用大模型生成文本."""
        if not self.client:
            logger.warning("[LLMClient] 客户端未初始化，返回空结果")
            return ""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.settings.vllm_model,
                messages=[
                    {"role": "system", "content": "你是人力资源分析专家，擅长根据员工数据生成专业、客观的分析结论和发展建议。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            content = response.choices[0].message.content.strip()
            # 清理大模型输出中的特殊标记
            content = content.replace("<|im_end|>", "").replace("<|im_start|>", "").replace("<|endoftext|>", "")
            content = content.strip()
            return content
        except Exception as e:
            logger.error(f"[LLMClient] 生成失败: {e}")
            return ""


# 全局LLM客户端实例
llm_client = LLMClient()


# ============ 归一化算法 ============

class ScoreNormalizer:
    """考核分数归一化处理器 - 处理不同领导的打分标准差异."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_normalized_scores(self, employee_id: int) -> Dict[str, float]:
        """
        获取试用期考核分数（直接返回原始分数，不归一化）.

        Returns:
            {
                'raw_scores': 原始分数,
                'assessor_info': 考核人信息
            }
        """
        # 查询该员工的试用期考核数据（取最新的一条）
        result = await self.db.execute(
            select(ProbationAssessment)
            .where(ProbationAssessment.employee_id == employee_id)
            .order_by(ProbationAssessment.assessment_date.desc())
        )
        employee_assessment = result.scalars().first()

        if not employee_assessment:
            return {
                'raw_scores': None,
                'assessor_info': None
            }

        assessor = employee_assessment.assessor
        assessor_dept = employee_assessment.assessor_department

        return {
            'raw_scores': {
                'professional_skill': employee_assessment.professional_skill_score,
                'work_performance': employee_assessment.work_performance_score,
                'work_attitude': employee_assessment.work_attitude_score,
                'teamwork': employee_assessment.teamwork_score,
                'learning_ability': employee_assessment.learning_ability_score,
                'total': employee_assessment.total_score
            },
            'assessor_info': {
                'assessor': assessor,
                'department': assessor_dept,
                'assessment_date': str(employee_assessment.assessment_date)
            }
        }

        return normalized


# ============ 请求/响应模型 ============

class DetailedAlignmentRequest(BaseModel):
    """详细人岗适配分析请求."""
    employee_name: str = Field(..., description="员工姓名", min_length=1, max_length=64)
    scoring_method: str = Field(default="rule", description="评分方式: rule=规则评分, ai=AI评分")


class DetailedAlignmentResponse(BaseModel):
    """详细人岗适配分析响应."""
    employee_info: Dict
    attendance_analysis: Dict
    position_model: Dict
    employee_performance: Dict
    match_analysis: Dict
    final_conclusion: str
    recommendations: List[str]


# ============ 核心分析类 ============

class DetailedAlignmentAnalyzer:
    """详细人岗适配分析器."""

    def __init__(self, db: AsyncSession, scoring_method: str = "rule"):
        self.db = db
        self.scoring_method = scoring_method

    async def get_position_requirements(self, position: str, department: str) -> Dict:
        """获取岗位要求（AI生成）- 独立接口."""
        return await self._get_position_model(position, department)

    async def get_employee_performance(self, employee_name: str) -> Dict:
        """获取员工实际表现 - 独立接口."""
        employee = await self._get_employee(employee_name)
        if not employee:
            return {"error": f"未找到员工: {employee_name}"}

        attendance_data = await self._get_attendance_data(employee.id)
        employee_scores = await self._calculate_employee_scores(employee.id)

        return {
            "employee_info": {
                "name": employee.name,
                "department": employee.department,
                "position": employee.position,
            },
            "attendance": attendance_data,
            "employee_performance": employee_scores,
        }

    async def get_match_analysis(self, employee_name: str) -> Dict:
        """获取匹配度分析 - 独立接口."""
        employee = await self._get_employee(employee_name)
        if not employee:
            return {"error": f"未找到员工: {employee_name}"}

        position_model = await self._get_position_model(employee.position, employee.department)
        employee_scores = await self._calculate_employee_scores(employee.id)
        match_analysis = self._calculate_match_scores(position_model, employee_scores)

        # 构建AI评分理由（与position-requirements接口一致）
        dimension_names = {
            "professional": "专业能力",
            "adaptability": "适应能力", 
            "innovation": "创新能力",
            "learning": "学习能力",
            "attendance": "工时维度",
            "political": "政治画像"
        }
        
        ai_scoring_reasons = []
        dimensions = position_model.get("dimensions", {})
        for key, name in dimension_names.items():
            dim_data = dimensions.get(key, {})
            score = dim_data.get("standard", 80)
            reasoning = dim_data.get("reasoning", "")
            if reasoning:
                ai_scoring_reasons.append({
                    "dimension": name,
                    "score": score,
                    "reasoning": reasoning
                })

        return {
            "employee_info": {
                "name": employee.name,
                "position": employee.position,
                "department": employee.department,
            },
            "position_model": position_model,
            "ai_scoring_reasons": ai_scoring_reasons,  # 结构化的AI评分理由
            "employee_performance": employee_scores,
            "match_analysis": match_analysis,
        }

    async def analyze(self, employee_name: str) -> Dict:
        """
        执行详细的人岗适配分析.
        
        分析流程：
        1. 查询员工基本信息
        2. 查询考勤数据并检查工时管理条例
        3. 查询岗位能力模型（理想雷达图）
        4. 计算员工实际表现（实际雷达图）
        5. 计算匹配度
        6. 生成结论和建议
        """
        # 1. 查询员工基本信息
        employee = await self._get_employee(employee_name)
        if not employee:
            return {"error": f"未找到员工: {employee_name}"}

        # 2. 查询上个月考勤数据（用于前端显示）
        attendance_data = await self._get_attendance_data(employee.id)

        # 2b. 查询近12个月考勤数据（用于AI评分和debug）
        attendance_data_yearly = await self._get_attendance_data_yearly(employee.id)

        # 3. 检查工时管理条例（基于上个月数据）
        policy_violations = await self._check_attendance_policies(attendance_data)

        # 4. 查询岗位能力模型
        position_model = await self._get_position_model(employee.position, employee.department)

        # 5. 查询薪资数据计算员工实际表现
        employee_scores = await self._calculate_employee_scores(employee.id)

        # 6. 计算匹配度
        match_analysis = self._calculate_match_scores(position_model, employee_scores)

        # 7. 使用大模型生成最终结论
        final_conclusion = await self._generate_conclusion_with_llm(
            employee, policy_violations, match_analysis, employee_scores
        )

        # 8. 使用大模型生成建议
        recommendations = await self._generate_recommendations_with_llm(
            employee, policy_violations, match_analysis, employee_scores
        )

        # 9. 使用AI生成个性化适配建议（整合多维度数据）
        ai_advice = await self._generate_ai_advice(
            employee, position_model, employee_scores, attendance_data, match_analysis
        )

        # 构建给大模型的输入数据（用于调试）- 使用12个月数据
        debug_info = {
            "ai_model_input": {
                "employee_name": employee.name,
                "position": employee.position,
                "department": employee.department,
                "education": employee.education,
                "hire_date": str(employee.hire_date) if employee.hire_date else None,
                "professional_title": employee.professional_title,
                "attendance_summary": self._format_attendance_for_ai(attendance_data_yearly),
                "probation_assessment": employee_scores.get("assessment_info", {}),
            }
        }

        return {
            "employee_info": {
                "name": employee.name,
                "department": employee.department,
                "position": employee.position,
                "education": employee.education,
                "hire_date": str(employee.hire_date) if employee.hire_date else None,
            },
            "attendance_analysis": {
                "summary": f"近{attendance_data.get('total_months', 0)}个月考勤情况",
                "details": attendance_data,
                "policy_violations": policy_violations,
            },
            "position_model": position_model,
            "employee_performance": employee_scores,
            "match_analysis": match_analysis,
            "final_conclusion": final_conclusion,
            "recommendations": recommendations,
            "ai_advice": ai_advice,
            "debug_info": debug_info,
        }
    
    async def _get_employee(self, name: str) -> Optional[Employee]:
        """查询员工基本信息."""
        result = await self.db.execute(
            select(Employee).where(Employee.name == name)
        )
        return result.scalar_one_or_none()

    def _format_attendance_for_ai(self, attendance_data: Dict) -> str:
        """格式化考勤数据给大模型."""
        monthly_summary = attendance_data.get('monthly_summary', [])
        if not monthly_summary:
            return "暂无考勤数据"

        lines = []
        lines.append(f"统计周期: {attendance_data.get('period', '')}")
        lines.append(f"总工作天数: {attendance_data.get('total_work_days', 0)}天")
        lines.append(f"总迟到天数: {attendance_data.get('total_late_days', 0)}天")
        lines.append(f"总加班天数: {attendance_data.get('total_overtime_days', 0)}天")

        # 每月明细
        monthly_details = []
        for m in monthly_summary:
            month = m.get('month', '')
            work_days = m.get('work_days', 0)
            late_days = m.get('late_days', 0)
            avg_hours = m.get('avg_hours', 0)
            overtime_days = m.get('overtime_days', 0)

            detail = f"{month}月: 工作{work_days}天"
            if late_days > 0:
                detail += f", 迟到{late_days}天"
            if avg_hours > 0:
                detail += f", 平均工时{avg_hours:.1f}小时"
            if overtime_days > 0:
                detail += f", 加班{overtime_days}天"
            monthly_details.append(detail)

        lines.append("每月明细: " + "; ".join(monthly_details))
        return "\n".join(lines)
    
    async def _get_attendance_data(self, employee_id: int) -> Dict:
        """查询上个月完整考勤数据（用于前端显示）."""
        # 获取上个月的第一天和最后一天
        today = datetime.now()
        first_day_of_this_month = today.replace(day=1)
        last_day_of_last_month = first_day_of_this_month - timedelta(days=1)
        first_day_of_last_month = last_day_of_last_month.replace(day=1)

        # 使用更简单的查询方式
        from sqlalchemy import case

        # 查询统计数据
        # 工作天数 = 正常 + 迟到 + 早退 + 异常（这些都算实际上班的天数）
        result = await self.db.execute(
            select(
                func.count().label('total_days'),
                func.sum(case((AttendanceRecord.status.in_(['正常', '迟到', '早退', '异常']), 1), else_=0)).label('work_days'),
                func.sum(case((AttendanceRecord.status == '迟到', 1), else_=0)).label('late_days'),
                func.sum(case((AttendanceRecord.status == '缺勤', 1), else_=0)).label('absent_days'),
                func.sum(case((AttendanceRecord.status == '早退', 1), else_=0)).label('early_leave_days'),
                func.sum(case((AttendanceRecord.status == '请假', 1), else_=0)).label('leave_days'),
                func.sum(case((AttendanceRecord.status == '异常', 1), else_=0)).label('abnormal_days'),
                func.sum(AttendanceRecord.work_hours).label('total_work_hours'),
                func.sum(AttendanceRecord.overtime_hours).label('total_overtime_hours'),
                func.sum(case((AttendanceRecord.overtime_hours > 0, 1), else_=0)).label('overtime_days'),
            )
            .where(
                and_(
                    AttendanceRecord.employee_id == employee_id,
                    AttendanceRecord.date >= first_day_of_last_month.date(),
                    AttendanceRecord.date <= last_day_of_last_month.date()
                )
            )
        )

        row = result.fetchone()

        # 调试日志
        logger.info(f"[考勤查询] 日期范围: {first_day_of_last_month.date()} 至 {last_day_of_last_month.date()}")
        logger.info(f"[考勤查询] 原始数据: total_days={row.total_days}, work_days={row.work_days}, leave_days={row.leave_days}, total_work_hours={row.total_work_hours}")

        # 查询每日工时数据（用于图表）
        daily_result = await self.db.execute(
            select(
                AttendanceRecord.date,
                AttendanceRecord.work_hours,
                AttendanceRecord.status
            )
            .where(
                and_(
                    AttendanceRecord.employee_id == employee_id,
                    AttendanceRecord.date >= first_day_of_last_month.date(),
                    AttendanceRecord.date <= last_day_of_last_month.date(),
                    AttendanceRecord.status == '正常'
                )
            )
            .order_by(AttendanceRecord.date)
        )
        daily_data = [
            {"date": str(r.date), "work_hours": float(r.work_hours) if r.work_hours else 0}
            for r in daily_result.fetchall()
        ]

        # 计算出勤率
        total_days = row.total_days or 0
        work_days = row.work_days or 0
        absent_days = row.absent_days or 0
        leave_days = row.leave_days or 0

        # 出勤率 = 工作天数 / (工作天数 + 请假天数) * 100%
        attendance_days = work_days + leave_days
        attendance_rate = (work_days / attendance_days * 100) if attendance_days > 0 else 0

        # 计算平均工时
        avg_work_hours = (float(row.total_work_hours) / work_days) if work_days > 0 else 0

        # 查询近一年每月平均工时（截止上个月底）
        yearly_start = last_day_of_last_month.replace(year=last_day_of_last_month.year - 1, day=1)
        yearly_result = await self.db.execute(
            select(
                func.strftime('%Y-%m', AttendanceRecord.date).label('month'),
                func.avg(AttendanceRecord.work_hours).label('avg_hours'),
                func.count().label('work_days')
            )
            .where(
                and_(
                    AttendanceRecord.employee_id == employee_id,
                    AttendanceRecord.date >= yearly_start,
                    AttendanceRecord.date <= last_day_of_last_month,
                    AttendanceRecord.status == '正常'
                )
            )
            .group_by(func.strftime('%Y-%m', AttendanceRecord.date))
            .order_by(func.strftime('%Y-%m', AttendanceRecord.date))
        )
        yearly_data = [
            {"month": r.month, "avg_hours": round(float(r.avg_hours), 2) if r.avg_hours else 0}
            for r in yearly_result.fetchall()
        ]

        return {
            "month": last_day_of_last_month.strftime("%Y年%m月"),
            "total_days": total_days,
            "work_days": work_days,
            "late_days": row.late_days or 0,
            "absent_days": absent_days,
            "early_leave_days": row.early_leave_days or 0,
            "leave_days": leave_days,
            "abnormal_days": row.abnormal_days or 0,
            "total_work_hours": float(row.total_work_hours) if row.total_work_hours else 0,
            "total_overtime_hours": float(row.total_overtime_hours) if row.total_overtime_hours else 0,
            "overtime_days": row.overtime_days or 0,
            "attendance_rate": round(attendance_rate, 1),
            "avg_work_hours": round(avg_work_hours, 2),
            "daily_work_hours": daily_data,
            "yearly_avg_hours": yearly_data,
        }

    async def _get_attendance_data_yearly(self, employee_id: int) -> Dict:
        """查询近12个月考勤月度汇总数据（用于AI评分）."""
        from sqlalchemy import case
        
        # 获取日期范围 - 近12个月（截止上个月底）
        today = datetime.now()
        first_day_of_this_month = today.replace(day=1)
        last_day_of_last_month = first_day_of_this_month - timedelta(days=1)
        # 近12个月的起始日期
        yearly_start = last_day_of_last_month.replace(year=last_day_of_last_month.year - 1, day=1)
        
        logger.info(f"[考勤查询-12个月] 查询近12个月数据: {yearly_start.date()} 至 {last_day_of_last_month.date()}")

        # 查询近12个月每月汇总数据
        monthly_result = await self.db.execute(
            select(
                func.strftime('%Y-%m', AttendanceRecord.date).label('month'),
                func.count().label('total_days'),
                func.sum(case((AttendanceRecord.status.in_(['正常', '迟到', '早退']), 1), else_=0)).label('work_days'),
                func.sum(case((AttendanceRecord.status == '迟到', 1), else_=0)).label('late_days'),
                func.sum(case((AttendanceRecord.status == '缺勤', 1), else_=0)).label('absent_days'),
                func.sum(case((AttendanceRecord.status == '请假', 1), else_=0)).label('leave_days'),
                func.avg(AttendanceRecord.work_hours).label('avg_hours'),
                func.sum(AttendanceRecord.work_hours).label('total_hours'),
                func.sum(AttendanceRecord.overtime_hours).label('total_overtime'),
                func.sum(case((AttendanceRecord.overtime_hours > 0, 1), else_=0)).label('overtime_days'),
            )
            .where(
                and_(
                    AttendanceRecord.employee_id == employee_id,
                    AttendanceRecord.date >= yearly_start,
                    AttendanceRecord.date <= last_day_of_last_month
                )
            )
            .group_by(func.strftime('%Y-%m', AttendanceRecord.date))
            .order_by(func.strftime('%Y-%m', AttendanceRecord.date))
        )
        
        # 构建月度汇总数据
        monthly_summary = []
        total_work_days = 0
        total_late_days = 0
        total_overtime_days = 0
        
        for r in monthly_result.fetchall():
            month_data = {
                "month": r.month,
                "work_days": r.work_days or 0,
                "late_days": r.late_days or 0,
                "absent_days": r.absent_days or 0,
                "leave_days": r.leave_days or 0,
                "avg_hours": round(float(r.avg_hours), 2) if r.avg_hours else 0,
                "total_hours": round(float(r.total_hours), 2) if r.total_hours else 0,
                "overtime_days": r.overtime_days or 0,
            }
            monthly_summary.append(month_data)
            total_work_days += r.work_days or 0
            total_late_days += r.late_days or 0
            total_overtime_days += r.overtime_days or 0

        logger.info(f"[考勤查询-12个月] 查询到 {len(monthly_summary)} 个月的数据")

        # 计算近12个月汇总统计
        total_months = len(monthly_summary)
        avg_work_days_per_month = round(total_work_days / total_months, 1) if total_months > 0 else 0
        
        return {
            "period": f"{yearly_start.strftime('%Y-%m')} 至 {last_day_of_last_month.strftime('%Y-%m')}",
            "total_months": total_months,
            "monthly_summary": monthly_summary,  # 近12个月每月汇总
            "total_work_days": total_work_days,
            "total_late_days": total_late_days,
            "total_overtime_days": total_overtime_days,
            "avg_work_days_per_month": avg_work_days_per_month,
        }
    
    async def _check_attendance_policies(self, attendance_data: Dict) -> List[Dict]:
        """检查工时管理条例触发情况."""
        violations = []
        
        # 查询所有启用的政策
        result = await self.db.execute(
            select(AttendancePolicy).where(AttendancePolicy.is_active == True)
        )
        policies = result.scalars().all()
        
        # 获取统计数据（兼容新旧格式）
        total_late_days = attendance_data.get('total_late_days', 0)
        total_overtime_days = attendance_data.get('total_overtime_days', 0)
        
        for policy in policies:
            triggered = False
            actual_value = 0
            
            if policy.condition_type == 'late' and total_late_days >= policy.threshold_value:
                triggered = True
                actual_value = total_late_days
            elif policy.condition_type == 'overtime' and total_overtime_days >= policy.threshold_value:
                triggered = True
                actual_value = total_overtime_days
            
            if triggered:
                message = policy.alert_message.format(
                    value=actual_value,
                    threshold=policy.threshold_value
                )
                violations.append({
                    "policy_name": policy.policy_name,
                    "alert_level": policy.alert_level,
                    "message": message,
                    "actual_value": actual_value,
                    "threshold": policy.threshold_value,
                })
        
        return violations
    
    async def _get_position_model(self, position: str, department: str) -> Dict:
        """查询岗位能力模型 - 优先按岗位名称+部门匹配，找不到则只按岗位名称匹配."""
        # 首先尝试按岗位名称+部门匹配
        result = await self.db.execute(
            select(PositionCapabilityModel)
            .where(
                and_(
                    PositionCapabilityModel.position_name == position,
                    PositionCapabilityModel.department == department
                )
            )
        )
        model = result.scalar_one_or_none()

        # 如果没找到，再尝试只按岗位名称匹配
        if not model:
            result = await self.db.execute(
                select(PositionCapabilityModel)
                .where(PositionCapabilityModel.position_name == position)
            )
            # 使用scalars().first()代替scalar_one_or_none()，避免多行错误
            model = result.scalars().first()

        # 如果没找到，尝试模糊匹配
        if not model:
            # 尝试去掉"师"字加"岗"字匹配（如"经营分析师"→"经营分析岗"）
            if position.endswith('师'):
                new_position = position[:-1] + '岗'
                result = await self.db.execute(
                    select(PositionCapabilityModel)
                    .where(PositionCapabilityModel.position_name == new_position)
                )
                model = result.scalar_one_or_none()
                logger.info(f"[岗位匹配] 尝试 '{position}' -> '{new_position}', 结果: {model is not None}")

            # 尝试去掉"岗"字加"师"字匹配（如"经营分析岗"→"经营分析师"）
            if not model and position.endswith('岗'):
                new_position = position[:-1] + '师'
                result = await self.db.execute(
                    select(PositionCapabilityModel)
                    .where(PositionCapabilityModel.position_name == new_position)
                )
                model = result.scalar_one_or_none()
                logger.info(f"[岗位匹配] 尝试 '{position}' -> '{new_position}', 结果: {model is not None}")

            # 尝试包含关系匹配（如"经营分析"可以匹配"经营分析岗"）
            if not model:
                # 去掉"师"和"岗"后进行包含匹配
                position_core = position.replace('师', '').replace('岗', '')
                result = await self.db.execute(
                    select(PositionCapabilityModel)
                    .where(PositionCapabilityModel.position_name.contains(position_core))
                )
                model = result.scalar_one_or_none()
                if model:
                    logger.info(f"[岗位匹配] 包含匹配 '{position}' -> '{model.position_name}'")

        if not model:
            # 返回默认模型，并标记数据缺失
            logger.warning(f"[岗位能力模型] 未找到岗位 '{position}' 的能力模型数据")
            return {
                "position_name": position,
                "department": department,
                "radar_data": [80, 80, 80, 80, 80, 80],
                "dimensions": {
                    "professional": {"standard": 80, "weight": 1.0},
                    "adaptability": {"standard": 80, "weight": 1.0},
                    "innovation": {"standard": 80, "weight": 1.0},
                    "learning": {"standard": 80, "weight": 1.0},
                    "attendance": {"standard": 80, "weight": 1.0},
                    "political": {"standard": 80, "weight": 0.8},
                },
                "description": f"⚠️ 数据缺失：系统中未找到 '{position}' 岗位的详细能力模型数据。当前使用默认标准值（80分）进行计算。建议补充该岗位的能力模型数据，包括各维度的标准要求和权重配置。",
                "data_missing": True,
                "missing_info": f"缺少 '{position}' 岗位的能力模型数据"
            }
        
        # 解析分析过程（如果有）
        analysis_process = {}
        if model.requirements:
            try:
                import json
                analysis_process = json.loads(model.requirements)
            except:
                analysis_process = {"analysis": model.requirements}

        # 使用AI生成岗位能力要求分数
        ai_position_scores = await self._generate_position_scores_with_ai(
            model.position_name,
            model.department,
            model.description or "",
            model.responsibilities or ""
        )
        
        if ai_position_scores:
            # 使用AI生成的分数
            logger.info(f"[岗位能力模型] 使用AI生成 '{position}' 岗位的能力要求分数")
            return ai_position_scores
        else:
            # AI生成失败，使用数据库中的标准值
            logger.warning(f"[岗位能力模型] AI生成失败，使用数据库标准值 '{position}'")
            return {
                "position_name": model.position_name,
                "department": model.department,
                "radar_data": [
                    model.professional_standard,
                    model.adaptability_standard,
                    model.innovation_standard,
                    model.learning_standard,
                    model.attendance_standard,
                    model.political_standard,
                ],
                "dimensions": {
                    "professional": {"standard": model.professional_standard, "weight": model.professional_weight},
                    "adaptability": {"standard": model.adaptability_standard, "weight": model.adaptability_weight},
                    "innovation": {"standard": model.innovation_standard, "weight": model.innovation_weight},
                    "learning": {"standard": model.learning_standard, "weight": model.learning_weight},
                    "attendance": {"standard": model.attendance_standard, "weight": model.attendance_weight},
                    "political": {"standard": model.political_standard, "weight": model.political_weight},
                },
                "description": model.description or "",
                "requirements": model.requirements or "",
                "responsibilities": model.responsibilities or "",
                "analysis_process": analysis_process,
            }

    async def _generate_position_scores_with_ai(self, position_name: str, department: str, description: str, responsibilities: str) -> Dict:
        """使用AI大模型根据岗位描述生成6维度能力要求分数."""
        try:
            from openai import AsyncOpenAI
            settings = get_settings()
            client = AsyncOpenAI(
                base_url=f"http://{settings.vllm_host}:{settings.vllm_port}/v1",
                api_key=settings.openai_api_key,
            )

            prompt = f"""作为HR专家，请根据以下岗位信息，为"{position_name}"岗位生成6个维度的能力要求分数（0-100分）及理由。

【岗位信息】
岗位名称：{position_name}
所属部门：{department}

【岗位描述】
{description}

【岗位职责】
{responsibilities}

【重要提示】
- 请严格根据上述岗位描述和职责进行评估
- 不要参考其他岗位的信息
- 该岗位是AIGC/AI产品相关岗位，不是财务岗位

【评分原则 - 必须有侧重点】
不同岗位对不同维度的要求应该有所差异，不要所有维度都给高分：

1. **专业能力**（professional）：
   - 技术岗位（算法/开发）：90-100分（核心要求）
   - 产品岗位：85-95分
   - 运营/行政岗位：70-85分

2. **适应能力**（adaptability）：
   - 所有岗位：75-85分（基础要求）

3. **创新能力**（innovation）：
   - 研发/产品岗位：85-95分（重要）
   - 算法岗位：90-100分（核心）
   - 运营/行政岗位：60-75分（一般要求）

4. **学习能力**（learning）：
   - 技术岗位：85-95分（技术更新快）
   - 其他岗位：70-85分

5. **工时维度**（attendance）：
   - 所有岗位：70-85分（基础要求，不应过高）

6. **政治画像**（political）：
   - 管理岗位：85-95分
   - 普通岗位：75-85分（基础要求）

【重要】根据岗位特性，1-2个维度给90-100分（核心要求），2-3个维度给80-90分（重要），其他维度给70-80分（基础）！

请从以下6个维度评估该岗位的能力要求：
1. 专业能力（professional）：岗位对专业技能的要求程度
2. 适应能力（adaptability）：岗位对适应变化、跨部门协作的要求
3. 创新能力（innovation）：岗位对创新思维、新技术应用的要求
4. 学习能力（learning）：岗位对持续学习、知识更新的要求
5. 工时维度（attendance）：岗位对工作时长、出勤稳定性的要求
6. 政治画像（political）：岗位对纪律性、团队协作的要求

输出JSON格式：
{{
  "professional": {{"score": 95, "reasoning": "算法岗位需要深厚的技术功底"}},
  "adaptability": {{"score": 80, "reasoning": "需要与产品、运营团队协作"}},
  "innovation": {{"score": 90, "reasoning": "推荐算法需要持续创新优化"}},
  "learning": {{"score": 90, "reasoning": "技术更新快，需持续学习"}},
  "attendance": {{"score": 80, "reasoning": "标准工时，项目紧张时需加班"}},
  "political": {{"score": 80, "reasoning": "需要良好的团队协作精神"}},
  "summary": "该岗位是技术核心岗位，对专业能力和学习能力要求极高..."
}}"""
            
            logger.info(f"[AI岗位评分] Prompt长度: {len(prompt)}, 岗位: {position_name}, 描述前100字: {description[:100] if description else '无'}")

            response = await client.chat.completions.create(
                model=settings.vllm_model,
                messages=[
                    {"role": "system", "content": "你是HR专家，请根据岗位描述客观评估能力要求。只输出JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.1,
            )

            content = response.choices[0].message.content
            
            # 提取JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                ai_result = json.loads(json_match.group(0))
                
                # 构建dimensions数据
                dimensions = {
                    "professional": {
                        "standard": ai_result.get("professional", {}).get("score", 80),
                        "reasoning": ai_result.get("professional", {}).get("reasoning", ""),
                        "weight": 1.0
                    },
                    "adaptability": {
                        "standard": ai_result.get("adaptability", {}).get("score", 80),
                        "reasoning": ai_result.get("adaptability", {}).get("reasoning", ""),
                        "weight": 1.0
                    },
                    "innovation": {
                        "standard": ai_result.get("innovation", {}).get("score", 80),
                        "reasoning": ai_result.get("innovation", {}).get("reasoning", ""),
                        "weight": 1.0
                    },
                    "learning": {
                        "standard": ai_result.get("learning", {}).get("score", 80),
                        "reasoning": ai_result.get("learning", {}).get("reasoning", ""),
                        "weight": 1.0
                    },
                    "attendance": {
                        "standard": ai_result.get("attendance", {}).get("score", 80),
                        "reasoning": ai_result.get("attendance", {}).get("reasoning", ""),
                        "weight": 1.0
                    },
                    "political": {
                        "standard": ai_result.get("political", {}).get("score", 80),
                        "reasoning": ai_result.get("political", {}).get("reasoning", ""),
                        "weight": 0.8
                    },
                }
                
                # 构建AI评分理由
                dimension_names = {
                    "professional": "专业能力",
                    "adaptability": "适应能力", 
                    "innovation": "创新能力",
                    "learning": "学习能力",
                    "attendance": "工时维度",
                    "political": "政治画像"
                }
                
                ai_reasoning_lines = []
                for key, name in dimension_names.items():
                    dim_data = dimensions.get(key, {})
                    score = dim_data.get("standard", 80)
                    reasoning = dim_data.get("reasoning", "")
                    if reasoning:
                        ai_reasoning_lines.append(f"• {name}({score}分)：{reasoning}")
                
                # description只保留总体描述，AI评分理由通过dimensions单独提供
                description = ai_result.get("summary", f"{position_name}岗位能力要求")
                
                logger.info(f"[AI岗位评分] 已生成岗位描述，长度: {len(description)}")
                
                # 构建返回数据
                return {
                    "position_name": position_name,
                    "department": department,
                    "radar_data": [
                        ai_result.get("professional", {}).get("score", 80),
                        ai_result.get("adaptability", {}).get("score", 80),
                        ai_result.get("innovation", {}).get("score", 80),
                        ai_result.get("learning", {}).get("score", 80),
                        ai_result.get("attendance", {}).get("score", 80),
                        ai_result.get("political", {}).get("score", 80),
                    ],
                    "dimensions": dimensions,
                    "description": description,
                    "ai_generated": True,
                }
            else:
                logger.error("[AI岗位评分] 无法从响应中提取JSON")
                return None

        except Exception as e:
            logger.error(f"[AI岗位评分] 生成岗位分数失败: {e}")
            return None
    
    async def _calculate_employee_scores(self, employee_id: int) -> Dict:
        """计算员工实际表现分数（6维度）- 支持规则评分和AI评分."""
        # 查询薪资数据
        result = await self.db.execute(
            select(SalaryRecord)
            .where(SalaryRecord.employee_id == employee_id)
            .order_by(SalaryRecord.month.desc())
            .limit(6)
        )
        salary_records = result.scalars().all()

        # 查询员工基本信息
        result = await self.db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        employee = result.scalar_one()

        # 如果是AI评分方式，调用AI评分器
        if self.scoring_method == "ai":
            return await self._calculate_ai_scores(employee, salary_records)

        # 规则评分方式（原有逻辑）
        return await self._calculate_rule_scores(employee_id, employee, salary_records)

    async def _calculate_ai_scores(self, employee: Employee, salary_records: List) -> Dict:
        """使用AI计算员工分数."""
        # 构建员工数据
        employee_data = {
            "name": employee.name,
            "position": employee.position,
            "department": employee.department,
            "education": employee.education,
            "hire_date": str(employee.hire_date) if employee.hire_date else None,
            "professional_title": employee.professional_title,
            "salary_records": [
                {"month": r.month, "base_salary": r.base_salary, "bonus": r.bonus}
                for r in salary_records
            ]
        }

        # 查询试用期考核数据
        result = await self.db.execute(
            select(ProbationAssessment)
            .where(ProbationAssessment.employee_id == employee.id)
            .order_by(ProbationAssessment.assessment_date.desc())
        )
        probation = result.scalars().first()

        if probation:
            employee_data["probation_assessment"] = {
                "total_score": probation.total_score,
                "professional_skill_score": probation.professional_skill_score,
                "work_performance_score": probation.work_performance_score,
                "work_attitude_score": probation.work_attitude_score,
                "teamwork_score": probation.teamwork_score,
                "learning_ability_score": probation.learning_ability_score,
                "assessment_result": probation.assessment_result,
                "comments": probation.comments,
            }

        # 查询考勤数据
        attendance_data = await self._get_attendance_data(employee.id)
        employee_data["attendance"] = attendance_data

        # 调用AI评分器V2（分维度评分）
        ai_result = await ai_scorer_v2.calculate_scores(employee_data)

        scores = ai_result.get("scores", {})
        reasoning = ai_result.get("reasoning", {})

        return {
            "radar_data": [
                scores.get("professional", 75),
                scores.get("adaptability", 75),
                scores.get("innovation", 75),
                scores.get("learning", 75),
                scores.get("attendance", 75),
                scores.get("political", 75),
            ],
            "scores": {
                "professional_score": scores.get("professional", 75),
                "adaptability_score": scores.get("adaptability", 75),
                "innovation_score": scores.get("innovation", 75),
                "learning_score": scores.get("learning", 75),
                "attendance_score": scores.get("attendance", 75),
                "political_score": scores.get("political", 75),
            },
            "assessment_info": {
                "scoring_method": "AI评分",
                "calculation_method": "基于大模型分析原始数据计算",
                "ai_reasoning": reasoning,
                "overall_assessment": ai_result.get("overall_assessment", ""),
                "key_strengths": ai_result.get("key_strengths", []),
                "key_improvements": ai_result.get("key_improvements", []),
            }
        }

    async def _calculate_rule_scores(self, employee_id: int, employee: Employee, salary_records: List) -> Dict:
        """使用规则计算员工分数（原有逻辑）."""
        # 获取归一化后的试用期考核分数
        normalizer = ScoreNormalizer(self.db)
        normalized_scores = await normalizer.get_normalized_scores(employee_id)

        logger.info(f"[专业能力计算] 员工ID={employee_id}, 试用期考核归一化分数={normalized_scores}")

        # 计算各维度分数
        scores = {
            "professional_score": 70,
            "adaptability_score": 70,
            "innovation_score": 70,
            "learning_score": 70,
            "attendance_score": 70,
            "political_score": 80,
        }

        # 试用期考核分数计算说明
        assessment_info = {
            "has_assessment": False,
            "raw_scores": {},
            "normalized_scores": {},
            "assessor_info": {},
            "calculation_method": ""
        }

        # 如果有试用期考核数据，直接使用原始分数（不归一化）
        if normalized_scores.get('raw_scores'):
            raw_scores = normalized_scores['raw_scores']
            assessment_info["has_assessment"] = True
            assessment_info["raw_scores"] = raw_scores
            assessment_info["assessor_info"] = normalized_scores.get('assessor_info')

            # 直接使用原始分数计算各维度
            prof_skill = raw_scores.get('professional_skill', 0)
            work_perf = raw_scores.get('work_performance', 0)
            work_att = raw_scores.get('work_attitude', 0)
            teamwork = raw_scores.get('teamwork', 0)
            learn_ability = raw_scores.get('learning_ability', 0)
            total_score = raw_scores.get('total', 0)

            # 【重要】专业能力直接使用试用期考核总分
            scores["professional_score"] = round(total_score)

            # 适应能力 = 原始团队协作分 * 0.5 + 原始工作态度分 * 0.3 + 原始工作业绩分 * 0.2
            scores["adaptability_score"] = round(teamwork * 0.5 + work_att * 0.3 + work_perf * 0.2)

            # 学习能力直接使用原始学习能力分
            scores["learning_score"] = round(learn_ability)

            # 创新能力 = 原始工作业绩分 * 0.5 + 原始专业技能分 * 0.3 + 原始学习能力分 * 0.2
            scores["innovation_score"] = round(work_perf * 0.5 + prof_skill * 0.3 + learn_ability * 0.2)

            assessment_info["calculation_method"] = (
                "专业能力 = 试用期考核总分（直接复用）\n"
                "适应能力 = 团队协作×50% + 工作态度×30% + 工作业绩×20%\n"
                "学习能力 = 学习能力×100%\n"
                "创新能力 = 工作业绩×50% + 专业技能×30% + 学习能力×20%\n"
                "(使用试用期考核原始分数直接计算，不归一化)"
            )
        else:
            # 没有试用期考核数据，使用原有计算逻辑
            assessment_info["calculation_method"] = "暂无试用期考核数据，使用薪资稳定性计算"

            # 基于薪资稳定性计算专业能力和创新能力
            if len(salary_records) >= 2:
                base_salaries = [r.base_salary for r in salary_records if r.base_salary]
                bonus_salaries = [r.bonus for r in salary_records if r.bonus]

                if base_salaries and max(base_salaries) > 0:
                    base_stable = (max(base_salaries) - min(base_salaries)) < max(base_salaries) * 0.1
                    if base_stable:
                        scores["professional_score"] = 85
                    else:
                        scores["professional_score"] = 65

                if bonus_salaries and max(bonus_salaries) > 0:
                    bonus_variation = (max(bonus_salaries) - min(bonus_salaries)) / max(bonus_salaries)
                    if 0.1 <= bonus_variation <= 0.3:
                        scores["innovation_score"] = 80
                    elif bonus_variation < 0.1:
                        scores["innovation_score"] = 60
                    else:
                        scores["innovation_score"] = 50

        # 基于学历计算学习能力（如果没有试用期考核数据）
        if not normalized_scores.get('raw_scores') and employee.education:
            if "博士" in employee.education:
                scores["learning_score"] = 90
            elif "硕士" in employee.education:
                scores["learning_score"] = 80
            elif "本科" in employee.education:
                scores["learning_score"] = 70

        return {
            "radar_data": [
                scores["professional_score"],
                scores["adaptability_score"],
                scores["innovation_score"],
                scores["learning_score"],
                scores["attendance_score"],
                scores["political_score"],
            ],
            "scores": scores,
            "assessment_info": assessment_info
        }
    
    def _calculate_match_scores(self, position_model: Dict, employee_scores: Dict) -> Dict:
        """计算匹配度."""
        position_radar = position_model["radar_data"]
        employee_radar = employee_scores["radar_data"]
        dimensions = position_model["dimensions"]
        
        match_scores = {}
        dimension_names = ["professional", "adaptability", "innovation", "learning", "attendance", "political"]
        
        total_weight = 0
        weighted_sum = 0
        
        for i, dim_name in enumerate(dimension_names):
            standard = position_radar[i]
            actual = employee_radar[i]
            weight = dimensions[dim_name]["weight"]
            
            # 计算匹配度（实际/标准）
            match_percent = (actual / standard * 100) if standard > 0 else 0
            match_scores[f"{dim_name}_match"] = round(match_percent, 1)
            
            weighted_sum += match_percent * weight
            total_weight += weight
        
        # 计算综合匹配度
        overall_match = weighted_sum / total_weight if total_weight > 0 else 0
        
        # 确定匹配等级
        if overall_match >= 90:
            level = "优秀匹配"
        elif overall_match >= 80:
            level = "良好匹配"
        elif overall_match >= 70:
            level = "基本匹配"
        elif overall_match >= 60:
            level = "勉强匹配"
        else:
            level = "不匹配"
        
        return {
            "match_scores": match_scores,
            "overall_match": round(overall_match, 1),
            "match_level": level,
        }
    
    async def _generate_conclusion_with_llm(self, employee, policy_violations, match_analysis, employee_scores) -> str:
        """使用大模型生成最终结论."""
        # 构建提示词
        violations_text = "\n".join([
            f"- {v['policy_name']}: {v['message']}" 
            for v in policy_violations
        ]) if policy_violations else "无违规记录"
        
        match_scores = match_analysis["match_scores"]
        scores_text = f"""
- 专业能力匹配度: {match_scores.get('professional_match', 0)}%
- 适应能力匹配度: {match_scores.get('adaptability_match', 0)}%
- 创新能力匹配度: {match_scores.get('innovation_match', 0)}%
- 学习能力匹配度: {match_scores.get('learning_match', 0)}%
- 工时维度匹配度: {match_scores.get('attendance_match', 0)}%
- 政治画像匹配度: {match_scores.get('political_match', 0)}%
"""
        
        prompt = f"""请根据以下员工数据，生成一段专业、客观的人岗适配分析结论（100-150字）：

员工信息：
- 姓名：{employee.name}
- 部门：{employee.department or '未指定'}
- 岗位：{employee.position or '未指定'}

工时管理情况：
{violations_text}

六维匹配度：
{scores_text}
- 综合匹配度：{match_analysis['overall_match']}%
- 匹配等级：{match_analysis['match_level']}

要求：
1. 语言专业、客观，符合HR分析报告风格
2. 总结主要优点和不足
3. 给出明确的评价结论
4. 不要罗列数据，要提炼观点
5. 控制在100-150字"""
        
        # 调用大模型
        conclusion = await llm_client.generate(prompt, max_tokens=300)
        
        # 如果大模型生成失败，使用规则生成作为fallback
        if not conclusion:
            logger.warning("[LLM] 结论生成失败，使用规则生成")
            conclusion = self._generate_conclusion_fallback(employee, policy_violations, match_analysis)
        
        return conclusion
    
    def _generate_conclusion_fallback(self, employee, policy_violations, match_analysis) -> str:
        """规则生成的结论（fallback）."""
        conclusion_parts = []
        
        if policy_violations:
            critical_count = sum(1 for v in policy_violations if v["alert_level"] == "critical")
            if critical_count > 0:
                conclusion_parts.append(f"工时管理存在{critical_count}项严重违规")
            else:
                conclusion_parts.append("工时管理存在违规情况")
        else:
            conclusion_parts.append("工时管理良好")
        
        match_level = match_analysis["match_level"]
        overall_match = match_analysis["overall_match"]
        conclusion_parts.append(f"人岗适配度{overall_match}%，结论为{match_level}")
        
        return f"{employee.name}：{'，'.join(conclusion_parts)}。"
    
    async def _generate_recommendations_with_llm(self, employee, policy_violations, match_analysis, employee_scores) -> List[str]:
        """使用大模型生成发展建议."""
        # 找出得分较低的维度
        low_dimensions = []
        match_scores = match_analysis["match_scores"]
        
        if match_scores.get("professional_match", 100) < 80:
            low_dimensions.append(f"专业能力({match_scores.get('professional_match', 0)}%)")
        if match_scores.get("adaptability_match", 100) < 80:
            low_dimensions.append(f"适应能力({match_scores.get('adaptability_match', 0)}%)")
        if match_scores.get("innovation_match", 100) < 80:
            low_dimensions.append(f"创新能力({match_scores.get('innovation_match', 0)}%)")
        if match_scores.get("learning_match", 100) < 80:
            low_dimensions.append(f"学习能力({match_scores.get('learning_match', 0)}%)")
        if match_scores.get("attendance_match", 100) < 80:
            low_dimensions.append(f"工时维度({match_scores.get('attendance_match', 0)}%)")
        if match_scores.get("political_match", 100) < 80:
            low_dimensions.append(f"政治画像({match_scores.get('political_match', 0)}%)")
        
        violations_text = "\n".join([
            f"- {v['policy_name']}" 
            for v in policy_violations
        ]) if policy_violations else "无违规记录"
        
        low_dim_text = "、".join(low_dimensions) if low_dimensions else "无"
        
        prompt = f"""请根据以下员工数据，生成3-5条具体、可操作的发展建议：

员工信息：
- 姓名：{employee.name}
- 岗位：{employee.position or '未指定'}

工时违规情况：
{violations_text}

需要提升的维度：{low_dim_text}

综合匹配度：{match_analysis['overall_match']}%

要求：
1. 建议要具体、可操作，避免空泛
2. 针对薄弱维度给出改进方向
3. 如有违规，给出纠正措施
4. 每条建议控制在20-30字
5. 使用序号列表格式输出
6. 生成3-5条建议"""
        
        # 调用大模型
        recommendations_text = await llm_client.generate(prompt, max_tokens=400)
        
        # 解析建议列表
        if recommendations_text:
            # 按行分割，提取建议
            recommendations = [
                line.strip().lstrip('123456789.- ') 
                for line in recommendations_text.split('\n')
                if line.strip() and not line.strip().startswith('建议')
            ]
            # 过滤空字符串
            recommendations = [r for r in recommendations if r]
            if recommendations:
                return recommendations[:5]  # 最多返回5条
        
        # 如果大模型生成失败，使用规则生成作为fallback
        logger.warning("[LLM] 建议生成失败，使用规则生成")
        return self._generate_recommendations_fallback(policy_violations, match_analysis)
    
    def _generate_recommendations_fallback(self, policy_violations, match_analysis) -> List[str]:
        """规则生成的建议（fallback）."""
        recommendations = []
        
        if policy_violations:
            for violation in policy_violations:
                if violation.get("condition_type") in ["late", "absent", "early_leave"]:
                    recommendations.append("加强时间管理和出勤纪律")
                    break
        
        match_scores = match_analysis["match_scores"]
        if match_scores.get("professional_match", 100) < 80:
            recommendations.append("提升专业能力，参加相关培训")
        if match_scores.get("adaptability_match", 100) < 80:
            recommendations.append("增强工作适应能力")
        if match_scores.get("innovation_match", 100) < 80:
            recommendations.append("培养创新思维")
        if match_scores.get("learning_match", 100) < 80:
            recommendations.append("加强学习，提升知识储备")
        
        if not recommendations:
            recommendations.append("继续保持良好表现")

        return recommendations

    async def _generate_ai_advice(self, employee, position_model, employee_scores, attendance_data, match_analysis) -> Dict:
        """使用AI生成个性化适配建议（整合多维度数据）."""
        try:
            # 构建员工数据
            employee_data = {
                "name": employee.name,
                "position": employee.position,
                "department": employee.department,
                "education": employee.education,
                "hire_date": str(employee.hire_date) if employee.hire_date else None,
                "scores": employee_scores.get("scores", {}),
                "standards": {
                    "professional": position_model.get("dimensions", {}).get("professional", {}).get("standard", 80),
                    "adaptability": position_model.get("dimensions", {}).get("adaptability", {}).get("standard", 80),
                    "innovation": position_model.get("dimensions", {}).get("innovation", {}).get("standard", 80),
                    "learning": position_model.get("dimensions", {}).get("learning", {}).get("standard", 80),
                    "attendance": position_model.get("dimensions", {}).get("attendance", {}).get("standard", 80),
                    "political": position_model.get("dimensions", {}).get("political", {}).get("standard", 80),
                },
                "position_requirements": {
                    "professional": position_model.get("dimensions", {}).get("professional", {}).get("standard", 80),
                    "adaptability": position_model.get("dimensions", {}).get("adaptability", {}).get("standard", 80),
                    "innovation": position_model.get("dimensions", {}).get("innovation", {}).get("standard", 80),
                    "learning": position_model.get("dimensions", {}).get("learning", {}).get("standard", 80),
                    "attendance": position_model.get("dimensions", {}).get("attendance", {}).get("standard", 80),
                    "political": position_model.get("dimensions", {}).get("political", {}).get("standard", 80),
                },
                "attendance": attendance_data,
                "match_analysis": match_analysis,
            }

            # 查询试用期考核数据
            result = await self.db.execute(
                select(ProbationAssessment)
                .where(ProbationAssessment.employee_id == employee.id)
                .order_by(ProbationAssessment.assessment_date.desc())
            )
            probation = result.scalars().first()

            if probation:
                employee_data["probation_assessment"] = {
                    "total_score": probation.total_score,
                    "professional_skill_score": probation.professional_skill_score,
                    "work_performance_score": probation.work_performance_score,
                    "work_attitude_score": probation.work_attitude_score,
                    "teamwork_score": probation.teamwork_score,
                    "learning_ability_score": probation.learning_ability_score,
                    "assessment_result": probation.assessment_result,
                    "comments": probation.comments,
                }

            # 查询薪资数据
            result = await self.db.execute(
                select(SalaryRecord)
                .where(SalaryRecord.employee_id == employee.id)
                .order_by(SalaryRecord.month.desc())
                .limit(6)
            )
            salary_records = result.scalars().all()
            employee_data["salary_records"] = [
                {
                    "month": r.month,
                    "base_salary": r.base_salary,
                    "bonus": r.bonus,
                }
                for r in salary_records
            ]

            # 调用AI建议生成器
            advice = await alignment_advisor.generate_advice(employee_data)
            return advice

        except Exception as e:
            logger.error(f"[AI建议生成] 失败: {e}")
            return {
                "overall_assessment": "AI建议生成失败，使用默认建议",
                "strengths": [],
                "improvements": [],
                "stage_recommendations": {},
                "risk_alerts": [],
                "development_plan": {},
                "match_score": match_analysis.get("overall_match", 75),
                "match_level": match_analysis.get("match_level", "基本匹配"),
                "is_default": True,
            }


# ============ API端点 ============

@router.post("/detailed-analysis", response_model=DetailedAlignmentResponse)
async def detailed_alignment_analysis(
    request: DetailedAlignmentRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    详细人岗适配分析.
    
    包含：
    - 员工基本信息
    - 工时管理情况（是否触发管理条例）
    - 岗位理想雷达图
    - 员工实际雷达图
    - 匹配度分析
    - 最终结论和建议
    """
    logger.info(f"[详细人岗适配分析] 开始分析员工: {request.employee_name}, 评分方式: {request.scoring_method}")
    start_time = datetime.now()

    try:
        analyzer = DetailedAlignmentAnalyzer(db, scoring_method=request.scoring_method)
        result = await analyzer.analyze(request.employee_name)
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[详细人岗适配分析] 完成分析，耗时: {elapsed_time:.2f}s")
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[详细人岗适配分析] 分析异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"分析过程中出现错误: {str(e)}")


@router.post("/detailed-analysis/stream")
async def detailed_alignment_analysis_stream(
    request: DetailedAlignmentRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    流式详细人岗适配分析.
    
    实时返回分析结果，支持SSE流式输出.
    """
    logger.info(f"[详细人岗适配分析-流式] 开始分析员工: {request.employee_name}")
    start_time = datetime.now()
    
    async def generate_stream():
        try:
            analyzer = DetailedAlignmentAnalyzer(db)
            result = await analyzer.analyze(request.employee_name)
            
            if "error" in result:
                yield f"data: {json.dumps({'error': result['error']}, ensure_ascii=False)}\n\n"
                return
            
            # 分步骤返回结果
            steps = [
                ("employee_info", "【员工信息】"),
                ("attendance_analysis", "【工时管理情况】"),
                ("position_model", "【岗位能力模型】"),
                ("employee_performance", "【员工实际表现】"),
                ("match_analysis", "【匹配度分析】"),
                ("final_conclusion", "【最终结论】"),
                ("recommendations", "【发展建议】"),
            ]
            
            for key, title in steps:
                if key in result:
                    yield f"data: {json.dumps({'step': key, 'title': title, 'data': result[key]}, ensure_ascii=False)}\n\n"
            
            # 返回完整结果
            yield f"data: {json.dumps({'done': True, 'full_result': result}, ensure_ascii=False)}\n\n"
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"[详细人岗适配分析-流式] 完成分析，耗时: {elapsed_time:.2f}s")
            
        except Exception as e:
            logger.exception(f"[详细人岗适配分析-流式] 分析异常: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============ 拆分后的独立接口 ============

class PositionRequirementsRequest(BaseModel):
    """岗位要求请求."""
    position: str = Field(..., description="岗位名称")
    department: str = Field(..., description="部门名称")


class EmployeePerformanceRequest(BaseModel):
    """员工表现请求."""
    employee_name: str = Field(..., description="员工姓名")
    scoring_method: str = Field(default="rule", description="评分方式: rule=规则评分, ai=AI评分")


@router.post("/position-requirements")
async def get_position_requirements_api(
    request: PositionRequirementsRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    获取岗位要求（AI生成）- 独立接口.
    
    根据岗位描述和职责，使用AI生成6维度的能力要求分数.
    """
    logger.info(f"[岗位要求] 获取岗位: {request.position}, 部门: {request.department}")
    start_time = datetime.now()
    
    try:
        analyzer = DetailedAlignmentAnalyzer(db)
        result = await analyzer.get_position_requirements(request.position, request.department)
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[岗位要求] 完成，耗时: {elapsed_time:.2f}s")
        
        # 构建AI评分理由列表（方便前端显示）
        dimension_names = {
            "professional": "专业能力",
            "adaptability": "适应能力", 
            "innovation": "创新能力",
            "learning": "学习能力",
            "attendance": "工时维度",
            "political": "政治画像"
        }
        
        # 构建结构化的AI评分理由（与员工表现格式一致，方便前端统一渲染）
        ai_scoring_reasons = []
        dimensions = result.get("dimensions", {})
        for key, name in dimension_names.items():
            dim_data = dimensions.get(key, {})
            score = dim_data.get("standard", 80)
            reasoning = dim_data.get("reasoning", "")
            if reasoning:
                ai_scoring_reasons.append({
                    "dimension": name,
                    "score": score,
                    "reasoning": reasoning
                })
        
        # description只保留总体描述，不包含AI评分理由（AI评分理由通过ai_scoring_reasons单独提供）
        # 这样前端可以分别渲染总体描述和AI评分理由列表
        original_description = result.get("description", "")
        # 如果description中已包含【AI评分理由】，只取前面的部分
        if "【AI评分理由】" in original_description:
            original_description = original_description.split("【AI评分理由】")[0].strip()
        result["description"] = original_description
        
        return {
            "position": request.position,
            "department": request.department,
            "position_model": result,
            "ai_scoring_reasons": ai_scoring_reasons,  # 结构化的AI评分理由，前端可按统一格式渲染
            "elapsed_time": elapsed_time,
        }
    except Exception as e:
        logger.exception(f"[岗位要求] 异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取岗位要求失败: {str(e)}")


@router.post("/employee-performance")
async def get_employee_performance_api(
    request: EmployeePerformanceRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    获取员工实际表现 - 独立接口.
    
    返回员工的考勤数据和6维度实际表现分数.
    """
    logger.info(f"[员工表现] 获取员工: {request.employee_name}, 评分方式: {request.scoring_method}")
    start_time = datetime.now()
    
    try:
        analyzer = DetailedAlignmentAnalyzer(db, scoring_method=request.scoring_method)
        result = await analyzer.get_employee_performance(request.employee_name)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[员工表现] 完成，耗时: {elapsed_time:.2f}s")
        
        return {
            **result,
            "elapsed_time": elapsed_time,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[员工表现] 异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取员工表现失败: {str(e)}")


@router.post("/match-analysis")
async def get_match_analysis_api(
    request: EmployeePerformanceRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    获取匹配度分析 - 独立接口.
    
    返回岗位要求、员工实际表现和匹配度分析.
    """
    logger.info(f"[匹配度分析] 获取员工: {request.employee_name}, 评分方式: {request.scoring_method}")
    start_time = datetime.now()
    
    try:
        analyzer = DetailedAlignmentAnalyzer(db, scoring_method=request.scoring_method)
        result = await analyzer.get_match_analysis(request.employee_name)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[匹配度分析] 完成，耗时: {elapsed_time:.2f}s")
        
        return {
            **result,
            "elapsed_time": elapsed_time,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[匹配度分析] 异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取匹配度分析失败: {str(e)}")


class EmployeeInfoRequest(BaseModel):
    """员工信息请求."""
    employee_name: str = Field(..., description="员工姓名")


@router.post("/employee-info")
async def get_employee_info_api(
    request: EmployeeInfoRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """
    获取员工基本信息 - 独立接口.
    
    返回员工的姓名、岗位、部门等基本信息，用于前端获取岗位信息后调用岗位要求接口.
    """
    logger.info(f"[员工信息] 获取员工: {request.employee_name}")
    
    try:
        # 查询员工
        result = await db.execute(
            select(Employee).where(Employee.name == request.employee_name)
        )
        employee = result.scalar_one_or_none()
        
        if not employee:
            raise HTTPException(status_code=404, detail=f"未找到员工: {request.employee_name}")
        
        return {
            "employee_info": {
                "id": employee.id,
                "name": employee.name,
                "position": employee.position,
                "department": employee.department,
                "education": employee.education,
                "professional_title": employee.professional_title,
                "hire_date": employee.hire_date.isoformat() if employee.hire_date else None,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[员工信息] 异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取员工信息失败: {str(e)}")
