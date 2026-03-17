"""
查询规划器模块 - 实现大模型驱动的查询流程

执行流程:
1. 拆解执行步骤 - 分析用户查询意图
2. 大模型判断 - 决定需要查询哪些数据库
3. 查询数据库 - 执行查询获取数据
4. 大模型整合 - 整合结果并生成回答
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import (
    Employee, AttendanceRecord, SalaryRecord, 
    InterviewRecord, ConversationRecord, PolicyDocument
)
from sqlalchemy import select
from datetime import datetime, timedelta


class DataSourceType(Enum):
    """数据源类型"""
    EMPLOYEE_BASIC = "employee_basic"  # 员工基本信息
    ATTENDANCE = "attendance"  # 考勤记录
    SALARY = "salary"  # 薪资/绩效
    INTERVIEW = "interview"  # 谈心谈话
    CONVERSATION = "conversation"  # 对话记录
    POLICY = "policy"  # 政策文档
    RESUME = "resume"  # 简历信息


@dataclass
class QueryStep:
    """查询步骤"""
    step_number: int
    data_source: DataSourceType
    query_condition: str
    reason: str  # 为什么需要查询这个数据源
    
    
@dataclass
class QueryPlan:
    """查询计划"""
    steps: List[QueryStep]
    employee_name: Optional[str] = None
    department: Optional[str] = None
    
    
@dataclass
class QueryResult:
    """查询结果"""
    step: QueryStep
    data: Any
    success: bool
    error_message: Optional[str] = None


class QueryPlanner:
    """查询规划器 - 使用大模型规划查询步骤"""
    
    def __init__(self, llm):
        self.llm = llm
        
    async def create_plan(self, user_query: str) -> QueryPlan:
        """
        使用大模型分析用户查询，创建查询计划
        
        Args:
            user_query: 用户查询
            
        Returns:
            查询计划
        """
        # 首先使用规则提取员工姓名和部门
        employee_name, department = self._extract_entities(user_query)
        
        # 构建简化版规划prompt
        planning_prompt = f"""分析查询，选择数据源。

查询: {user_query}
员工: {employee_name or '未指定'}
部门: {department or '未指定'}

可选数据源: employee_basic, attendance, salary, interview, resume, policy

根据查询内容，只选择必要的数据源，以JSON输出:
{{
    "steps": [
        {{
            "step_number": 1,
            "data_source": "数据源名称",
            "reason": "简短原因"
        }}
    ]
}}"""

        try:
            # 调用大模型进行规划
            messages = [{"role": "user", "content": planning_prompt}]
            response = await self.llm.ainvoke(messages)
            
            # 解析JSON响应
            content = response.content
            # 提取JSON部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
                
            plan_data = json.loads(content.strip())
            
            # 构建QueryPlan
            steps = []
            for step_data in plan_data.get("steps", []):
                try:
                    steps.append(QueryStep(
                        step_number=step_data["step_number"],
                        data_source=DataSourceType(step_data["data_source"]),
                        query_condition=step_data.get("query_condition", ""),
                        reason=step_data["reason"]
                    ))
                except:
                    # 跳过无效的数据源
                    continue
            
            return QueryPlan(
                steps=steps,
                employee_name=employee_name,
                department=department
            )
            
        except Exception as e:
            # 如果大模型规划失败，使用默认规则
            return self._create_default_plan(user_query, employee_name, department)
    
    def _extract_entities(self, user_query: str) -> tuple:
        """从查询中提取员工姓名和部门"""
        # 常见员工姓名列表（实际应该从数据库获取）
        common_names = ["石京京", "许博", "毛钰博", "宋佳铭", "周灏", "余祯", "周健", "张佳伟", "周可欣"]
        
        employee_name = None
        for name in common_names:
            if name in user_query:
                employee_name = name
                break
        
        # 提取部门
        department = None
        if "云生工作室" in user_query:
            department = "云生工作室"
        elif "权益" in user_query:
            department = "权益运营事业部"
        
        return employee_name, department
    
    def _create_default_plan(self, user_query: str, employee_name: str = None, department: str = None) -> QueryPlan:
        """创建默认查询计划（当大模型规划失败时使用）"""
        steps = []
        
        # 根据关键词判断需要查询的数据源
        if any(kw in user_query for kw in ["考勤", "加班", "迟到", "早退"]):
            # 根据时间关键词判断查询范围
            if any(kw in user_query for kw in ["近一月", "一个月", "1个月", "本月", "最近一个月"]):
                query_condition = "近1个月考勤记录"
            elif any(kw in user_query for kw in ["近两月", "两个月", "2个月", "近两个月"]):
                query_condition = "近2个月考勤记录"
            elif any(kw in user_query for kw in ["近三月", "三个月", "3个月", "近三个月"]):
                query_condition = "近3个月考勤记录"
            else:
                query_condition = "近3个月考勤记录"
            steps.append(QueryStep(
                step_number=1,
                data_source=DataSourceType.ATTENDANCE,
                query_condition=query_condition,
                reason="用户查询涉及考勤信息"
            ))
            
        if any(kw in user_query for kw in ["工资", "薪资", "绩效", "收入", "薪酬", "成本"]):
            steps.append(QueryStep(
                step_number=len(steps)+1,
                data_source=DataSourceType.SALARY,
                query_condition="近6个月薪资记录",
                reason="用户查询涉及薪资成本信息"
            ))
            
        if any(kw in user_query for kw in ["学校", "学历", "专业", "毕业"]):
            steps.append(QueryStep(
                step_number=len(steps)+1,
                data_source=DataSourceType.EMPLOYEE_BASIC,
                query_condition="教育背景信息",
                reason="用户查询涉及教育背景"
            ))

        # 人岗适配查询需要多个数据源
        if any(kw in user_query for kw in ["适配", "匹配", "胜任", "适岗"]):
            steps.append(QueryStep(
                step_number=len(steps)+1,
                data_source=DataSourceType.EMPLOYEE_BASIC,
                query_condition="员工基本信息",
                reason="人岗适配分析需要员工基本信息"
            ))
            steps.append(QueryStep(
                step_number=len(steps)+1,
                data_source=DataSourceType.ATTENDANCE,
                query_condition="近3个月考勤记录",
                reason="人岗适配分析需要考勤数据"
            ))
            steps.append(QueryStep(
                step_number=len(steps)+1,
                data_source=DataSourceType.SALARY,
                query_condition="近6个月薪资记录",
                reason="人岗适配分析需要绩效数据"
            ))

        # 默认查询员工基本信息
        if not steps:
            steps.append(QueryStep(
                step_number=1,
                data_source=DataSourceType.EMPLOYEE_BASIC,
                query_condition="员工基本信息",
                reason="获取员工基本信息"
            ))
        
        return QueryPlan(
            steps=steps,
            employee_name=employee_name,
            department=department
        )


class DataRetriever:
    """数据检索器 - 根据查询计划检索数据"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def execute_plan(self, plan: QueryPlan) -> List[QueryResult]:
        """
        执行查询计划，获取数据
        
        Args:
            plan: 查询计划
            
        Returns:
            查询结果列表
        """
        results = []
        
        # 首先获取员工ID
        employee_id = None
        if plan.employee_name:
            from app.database.crud import EmployeeCRUD
            employee = await EmployeeCRUD.get_by_name(self.db, plan.employee_name)
            if employee:
                employee_id = employee.id
        
        # 执行每个查询步骤
        for step in plan.steps:
            try:
                data = await self._query_data_source(step, employee_id, plan)
                results.append(QueryResult(
                    step=step,
                    data=data,
                    success=True
                ))
            except Exception as e:
                results.append(QueryResult(
                    step=step,
                    data=None,
                    success=False,
                    error_message=str(e)
                ))
        
        return results
    
    async def _query_data_source(
        self,
        step: QueryStep,
        employee_id: Optional[int],
        plan: QueryPlan
    ) -> Any:
        """查询单个数据源"""

        # 如果有部门但没有员工，查询部门级数据
        if plan.department and not plan.employee_name:
            if step.data_source == DataSourceType.EMPLOYEE_BASIC:
                return await self._query_department_employees(plan.department)
            elif step.data_source == DataSourceType.ATTENDANCE:
                return await self._query_department_attendance(plan.department)
            elif step.data_source == DataSourceType.SALARY:
                return await self._query_department_salary(plan.department)
            else:
                return {}

        # 员工级查询
        if step.data_source == DataSourceType.EMPLOYEE_BASIC:
            return await self._query_employee_basic(plan.employee_name)

        elif step.data_source == DataSourceType.ATTENDANCE:
            # 根据查询条件决定查询范围
            if "近1个月" in step.query_condition or "一个月" in step.query_condition:
                return await self._query_attendance(employee_id, days=30)
            elif "近2个月" in step.query_condition or "两个月" in step.query_condition:
                return await self._query_attendance(employee_id, days=60)
            else:
                return await self._query_attendance(employee_id, days=90)

        elif step.data_source == DataSourceType.SALARY:
            return await self._query_salary(employee_id)

        elif step.data_source == DataSourceType.INTERVIEW:
            return await self._query_interview(employee_id)

        elif step.data_source == DataSourceType.RESUME:
            return await self._query_resume(employee_id)

        elif step.data_source == DataSourceType.POLICY:
            return await self._query_policy(step.query_condition)

        else:
            return None
    
    async def _query_employee_basic(self, employee_name: Optional[str]) -> Dict:
        """查询员工基本信息"""
        if not employee_name:
            return {}
            
        from app.database.crud import EmployeeCRUD
        employee = await EmployeeCRUD.get_by_name(self.db, employee_name)
        
        if not employee:
            return {}
        
        return {
            "id": employee.id,
            "name": employee.name,
            "department": employee.department,
            "position": employee.position,
            "hire_date": str(employee.hire_date) if employee.hire_date else None,
            "education": employee.education,
            "school": employee.school,
            "major": employee.major,
            "phone": employee.phone,
            "email": employee.email
        }
    
    async def _query_attendance(self, employee_id: Optional[int], days: int = 90) -> Dict:
        """查询考勤记录"""
        if not employee_id:
            return {}

        # 根据days参数决定查询范围，默认为90天（近3个月）
        start_date = datetime.now().date() - timedelta(days=days)

        result = await self.db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == employee_id,
                AttendanceRecord.date >= start_date
            )
        )
        records = result.scalars().all()

        if not records:
            return {}

        total_days = len(records)
        late_days = sum(1 for r in records if r.status == "迟到")
        early_leave_days = sum(1 for r in records if r.status == "早退")
        absent_days = sum(1 for r in records if r.status == "缺勤")
        overtime_days = sum(1 for r in records if r.overtime_hours and r.overtime_hours > 0)
        total_overtime_hours = sum(r.overtime_hours for r in records if r.overtime_hours)

        period_str = f"近{days // 30}个月" if days >= 30 else f"近{days}天"

        return {
            "period": period_str,
            "total_days": total_days,
            "late_days": late_days,
            "early_leave_days": early_leave_days,
            "absent_days": absent_days,
            "overtime_days": overtime_days,
            "total_overtime_hours": round(total_overtime_hours, 1)
        }
    
    async def _query_salary(self, employee_id: Optional[int]) -> Dict:
        """查询薪资记录 - 排除第一个月（入职月份）"""
        if not employee_id:
            return {}

        # 查询近7个月的薪资记录（排除第一个月后保留6个月）
        result = await self.db.execute(
            select(SalaryRecord).where(
                SalaryRecord.employee_id == employee_id
            ).order_by(SalaryRecord.month.desc()).limit(7)
        )
        records = result.scalars().all()

        if not records:
            return {}

        # 排除第一个月（最早的月份，入职月份）
        # records是按月份降序排列的，第一个元素是最新的，最后一个是最早的
        if len(records) > 1:
            first_month = records[-1]  # 最早的月份（入职月份）
            filtered_records = records[:-1]  # 排除最后一个（最早的）
            excluded_months = [str(first_month.month)]
        else:
            filtered_records = records
            excluded_months = []

        # 构建历史记录（显示所有月份，但计算时排除第一个月）
        salary_history = []
        for r in records:
            base = float(r.base_salary) if r.base_salary else 0
            bonus = float(r.bonus) if r.bonus else 0
            overtime = float(r.overtime_pay) if r.overtime_pay else 0
            net = float(r.net_salary) if r.net_salary else 0
            salary_history.append({
                "month": str(r.month),
                "base_salary": base,
                "performance_salary": bonus,
                "overtime_pay": overtime,
                "net_salary": net,
                "total_salary": base + bonus + overtime
            })

        # 使用过滤后的记录（排除第一个月）计算平均值
        if filtered_records:
            avg_base_filtered = sum(float(r.base_salary) if r.base_salary else 0 for r in filtered_records) / len(filtered_records)
            avg_bonus_filtered = sum(float(r.bonus) if r.bonus else 0 for r in filtered_records) / len(filtered_records)
            
            # 构建过滤后的历史记录（用于稳定性判断）
            filtered_history = []
            for r in filtered_records:
                base = float(r.base_salary) if r.base_salary else 0
                bonus = float(r.bonus) if r.bonus else 0
                overtime = float(r.overtime_pay) if r.overtime_pay else 0
                filtered_history.append({
                    "month": str(r.month),
                    "base_salary": base,
                    "performance_salary": bonus,
                    "overtime_pay": overtime,
                    "net_salary": float(r.net_salary) if r.net_salary else 0,
                    "total_salary": base + bonus + overtime
                })
        else:
            avg_base_filtered = 0
            avg_bonus_filtered = 0
            filtered_history = []

        return {
            "history": salary_history,
            "filtered_history": filtered_history,  # 排除第一个月后的数据
            "latest": salary_history[0] if salary_history else None,
            "avg_base_salary": round(avg_base_filtered, 2),
            "avg_performance_salary": round(avg_bonus_filtered, 2),
            "avg_total_salary": round(avg_base_filtered + avg_bonus_filtered, 2),
            "excluded_months": excluded_months,
            "note": f"排除入职首月: {', '.join(excluded_months)}" if excluded_months else None
        }

    async def _query_department_employees(self, department: str) -> Dict:
        """查询部门员工列表"""
        from app.database.models import Employee

        result = await self.db.execute(
            select(Employee).where(Employee.department == department)
        )
        employees = result.scalars().all()

        return {
            "department": department,
            "employee_count": len(employees),
            "employees": [
                {
                    "id": e.id,
                    "name": e.name,
                    "position": e.position,
                    "education": e.education
                }
                for e in employees
            ]
        }

    async def _query_department_attendance(self, department: str) -> Dict:
        """查询部门考勤统计"""
        from app.database.models import Employee
        from datetime import datetime, timedelta

        # 获取部门所有员工
        result = await self.db.execute(
            select(Employee).where(Employee.department == department)
        )
        employees = result.scalars().all()

        three_months_ago = datetime.now().date() - timedelta(days=90)

        # 统计每个员工的考勤
        employee_stats = []
        total_late = 0
        total_absent = 0
        total_overtime = 0

        for emp in employees:
            result = await self.db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.employee_id == emp.id,
                    AttendanceRecord.date >= three_months_ago
                )
            )
            records = result.scalars().all()

            late_days = sum(1 for r in records if r.status == "迟到")
            absent_days = sum(1 for r in records if r.status == "缺勤")
            overtime_days = sum(1 for r in records if r.overtime_hours and r.overtime_hours > 0)

            total_late += late_days
            total_absent += absent_days
            total_overtime += overtime_days

            employee_stats.append({
                "name": emp.name,
                "late_days": late_days,
                "absent_days": absent_days,
                "overtime_days": overtime_days
            })

        return {
            "department": department,
            "period": "近3个月",
            "employee_count": len(employees),
            "total_late_days": total_late,
            "total_absent_days": total_absent,
            "total_overtime_days": total_overtime,
            "employee_stats": employee_stats
        }

    async def _query_department_salary(self, department: str) -> Dict:
        """查询部门薪资统计"""
        from app.database.models import Employee

        # 获取部门所有员工
        result = await self.db.execute(
            select(Employee).where(Employee.department == department)
        )
        employees = result.scalars().all()

        # 统计薪资
        total_base_salary = 0
        total_performance_salary = 0
        employee_salaries = []

        for emp in employees:
            # 查询近7个月的薪资记录（排除第一个月后保留6个月）
            result = await self.db.execute(
                select(SalaryRecord).where(
                    SalaryRecord.employee_id == emp.id
                ).order_by(SalaryRecord.month.desc()).limit(7)
            )
            salaries = result.scalars().all()

            if salaries:
                # 排除第一个月（最早的月份，入职月份）
                # salaries是按月份降序排列的，第一个元素是最新的，最后一个是最早的
                if len(salaries) > 1:
                    first_month = salaries[-1]  # 最早的月份（入职月份）
                    filtered_salaries = salaries[:-1]  # 排除最后一个（最早的）
                    excluded_months = [str(first_month.month)]
                else:
                    filtered_salaries = salaries
                    excluded_months = []

                # 使用过滤后的记录（排除第一个月）计算平均值
                if filtered_salaries:
                    avg_base = sum(float(s.base_salary) if s.base_salary else 0 for s in filtered_salaries) / len(filtered_salaries)
                    avg_bonus = sum(float(s.bonus) if s.bonus else 0 for s in filtered_salaries) / len(filtered_salaries)
                    avg_overtime = sum(float(s.overtime_pay) if s.overtime_pay else 0 for s in filtered_salaries) / len(filtered_salaries)
                else:
                    avg_base = 0
                    avg_bonus = 0
                    avg_overtime = 0

                avg_total = avg_base + avg_bonus + avg_overtime

                total_base_salary += avg_base
                total_performance_salary += avg_bonus

                employee_salaries.append({
                    "name": emp.name,
                    "avg_base_salary": round(avg_base, 2),
                    "avg_performance_salary": round(avg_bonus, 2),
                    "avg_total_salary": round(avg_total, 2),
                    "months_count": len(filtered_salaries),
                    "excluded_months": excluded_months
                })

        return {
            "department": department,
            "employee_count": len(employees),
            "avg_monthly_base": round(total_base_salary, 2),
            "avg_monthly_performance": round(total_performance_salary, 2),
            "avg_monthly_total": round(total_base_salary + total_performance_salary, 2),
            "employee_salaries": employee_salaries
        }

    async def _query_interview(self, employee_id: Optional[int]) -> List[Dict]:
        """查询谈心谈话记录"""
        if not employee_id:
            return []
        
        result = await self.db.execute(
            select(InterviewRecord).where(
                InterviewRecord.employee_id == employee_id
            ).order_by(InterviewRecord.interview_date.desc()).limit(5)
        )
        records = result.scalars().all()
        
        return [
            {
                "date": r.interview_date,
                "content": r.content[:200] + "..." if len(r.content) > 200 else r.content
            }
            for r in records
        ]
    
    async def _query_resume(self, employee_id: Optional[int]) -> Dict:
        """查询简历信息"""
        if not employee_id:
            return {}
        
        from app.database.models import EmployeeResume
        result = await self.db.execute(
            select(EmployeeResume).where(EmployeeResume.employee_id == employee_id)
        )
        resume = result.scalar_one_or_none()
        
        if not resume:
            return {}
        
        return {
            "education": resume.education,
            "school": resume.school,
            "major": resume.major,
            "graduation_year": resume.graduation_year,
            "work_experience": resume.work_experience[:500] + "..." if resume.work_experience and len(resume.work_experience) > 500 else resume.work_experience
        }
    
    async def _query_policy(self, query_condition: str) -> List[Dict]:
        """查询政策文档"""
        # 简化实现，实际应该使用向量搜索
        result = await self.db.execute(
            select(PolicyDocument).limit(3)
        )
        records = result.scalars().all()
        
        return [
            {
                "title": r.title,
                "content": r.content[:300] + "..." if len(r.content) > 300 else r.content
            }
            for r in records
        ]


class ResultSynthesizer:
    """结果合成器 - 使用大模型整合查询结果"""

    def __init__(self, llm):
        self.llm = llm

    def _compact_data_for_alignment(self, data_source: str, data: Dict) -> Dict:
        """
        精简数据用于人岗适配分析，减少tokens使用量
        """
        if not data:
            return {}
        if data_source == "employee_basic":
            return {
                "name": data.get("name"),
                "department": data.get("department"),
                "position": data.get("position"),
                "education": data.get("education")
            }
        elif data_source == "attendance":
            return {
                "period": data.get("period"),
                "total_days": data.get("total_days"),
                "late_days": data.get("late_days"),
                "absent_days": data.get("absent_days"),
                "overtime_days": data.get("overtime_days")
            }
        elif data_source == "salary":
            # 保留filtered_history用于稳定性判断，但限制长度
            filtered_history = data.get("filtered_history", [])
            # 只保留最近3个月的数据用于判断
            compact_history = [
                {
                    "month": h.get("month"),
                    "base_salary": h.get("base_salary"),
                    "performance_salary": h.get("performance_salary")
                }
                for h in filtered_history[-3:]  # 只保留最近3个月
            ]
            return {
                "avg_base_salary": data.get("avg_base_salary"),
                "avg_performance_salary": data.get("avg_performance_salary"),
                "filtered_history": compact_history,
                "months_count": len(filtered_history)
            }
        elif data_source == "resume":
            return {
                "education": data.get("education"),
                "school": data.get("school"),
                "major": data.get("major")
            }
        else:
            # 其他数据源返回简化版本
            return {"available": True}
    
    def _calculate_alignment_scores(self, results_summary: List[Dict]) -> Dict:
        """
        计算人岗适配分数 - 6维度雷达图
        
        评分维度 (各100分制，用于雷达图显示):
        1. 专业能力: 基于薪资稳定性
        2. 适应能力: 基于出勤稳定性
        3. 创新能力: 基于绩效波动（创新通常伴随波动）
        4. 学习能力: 基于学历和薪资增长
        5. 工时维度: 基于考勤数据
        6. 政治画像: 基于员工身份
        """
        scores = {
            "professional_score": 0,  # 专业能力
            "adaptability_score": 0,  # 适应能力
            "innovation_score": 0,    # 创新能力
            "learning_score": 0,      # 学习能力
            "attendance_score": 0,    # 工时维度
            "political_score": 0,     # 政治画像
            "total_score": 0,
            "details": {}
        }
        
        # 提取数据
        employee_data = None
        attendance_data = None
        salary_data = None
        
        for result in results_summary:
            if result.get("data_source") == "employee_basic":
                employee_data = result.get("data", {})
            elif result.get("data_source") == "attendance":
                attendance_data = result.get("data", {})
            elif result.get("data_source") == "salary":
                salary_data = result.get("data", {})
        
        # 1. 专业能力评分 (100分)
        # 基于薪资稳定性判断
        if salary_data and "filtered_history" in salary_data:
            filtered_history = salary_data["filtered_history"]
            if len(filtered_history) >= 2:
                base_salaries = [h.get("base_salary", 0) for h in filtered_history]
                performance_salaries = [h.get("performance_salary", 0) for h in filtered_history]
                
                base_stable = max(base_salaries) - min(base_salaries) < max(base_salaries) * 0.1
                perf_stable = max(performance_salaries) - min(performance_salaries) < max(performance_salaries) * 0.1
                
                if base_stable and perf_stable:
                    scores["professional_score"] = 85  # 专业能力强，绩效稳定
                    scores["details"]["professional"] = "专业能力优秀，绩效表现稳定"
                else:
                    scores["professional_score"] = 65  # 专业能力一般，绩效有波动
                    scores["details"]["professional"] = "专业能力良好，但绩效有波动"
            elif len(filtered_history) == 1:
                scores["professional_score"] = 70
                scores["details"]["professional"] = "数据有限，但表现良好"
            else:
                scores["professional_score"] = 40
                scores["details"]["professional"] = "数据不足"
        else:
            scores["professional_score"] = 30
            scores["details"]["professional"] = "缺少薪资数据"
        
        # 2. 适应能力评分 (100分)
        # 基于出勤稳定性（无迟到早退缺勤表示适应能力强）
        if attendance_data:
            late_days = attendance_data.get("late_days", 0)
            absent_days = attendance_data.get("absent_days", 0)
            
            if late_days == 0 and absent_days == 0:
                scores["adaptability_score"] = 90
                scores["details"]["adaptability"] = "适应能力优秀，出勤完美"
            elif absent_days == 0 and late_days <= 2:
                scores["adaptability_score"] = 75
                scores["details"]["adaptability"] = "适应能力良好，偶有迟到"
            else:
                scores["adaptability_score"] = 50
                scores["details"]["adaptability"] = f"适应能力一般，缺勤{absent_days}天，迟到{late_days}天"
        else:
            scores["adaptability_score"] = 40
            scores["details"]["adaptability"] = "缺少考勤数据"
        
        # 3. 创新能力评分 (100分)
        # 基于绩效波动（适度波动可能表示创新尝试）
        if salary_data and "filtered_history" in salary_data:
            filtered_history = salary_data["filtered_history"]
            if len(filtered_history) >= 2:
                performance_salaries = [h.get("performance_salary", 0) for h in filtered_history]
                perf_variation = (max(performance_salaries) - min(performance_salaries)) / max(performance_salaries) if max(performance_salaries) > 0 else 0
                
                # 适度波动表示创新（10%-30%波动）
                if 0.1 <= perf_variation <= 0.3:
                    scores["innovation_score"] = 80
                    scores["details"]["innovation"] = "绩效有适度波动，可能有创新尝试"
                elif perf_variation < 0.1:
                    scores["innovation_score"] = 60
                    scores["details"]["innovation"] = "绩效稳定，创新表现平稳"
                else:
                    scores["innovation_score"] = 50
                    scores["details"]["innovation"] = "绩效波动较大，需关注稳定性"
            else:
                scores["innovation_score"] = 50
                scores["details"]["innovation"] = "数据不足"
        else:
            scores["innovation_score"] = 40
            scores["details"]["innovation"] = "缺少数据"
        
        # 4. 学习能力评分 (100分)
        # 基于学历和薪资增长
        education_score = 0
        if employee_data:
            education = employee_data.get("education", "")
            if "博士" in education:
                education_score = 90
            elif "硕士" in education:
                education_score = 80
            elif "本科" in education:
                education_score = 70
            else:
                education_score = 60
        
        # 薪资增长也反映学习能力
        growth_score = 50
        if salary_data and "filtered_history" in salary_data:
            filtered_history = salary_data["filtered_history"]
            if len(filtered_history) >= 2:
                first_salary = filtered_history[-1].get("base_salary", 0)  # 最早
                last_salary = filtered_history[0].get("base_salary", 0)    # 最近
                if last_salary > first_salary * 1.1:
                    growth_score = 85
                elif last_salary > first_salary:
                    growth_score = 70
        
        scores["learning_score"] = (education_score + growth_score) / 2
        scores["details"]["learning"] = f"学历得分{education_score}，成长得分{growth_score}"
        
        # 5. 工时维度评分 (100分)
        if attendance_data:
            total_days = attendance_data.get("total_days", 0)
            late_days = attendance_data.get("late_days", 0)
            absent_days = attendance_data.get("absent_days", 0)
            overtime_days = attendance_data.get("overtime_days", 0)

            if total_days > 0:
                # 基础分60分
                attendance_base = 60
                # 缺勤扣分
                attendance_base -= absent_days * 10
                # 迟到扣分
                attendance_base -= late_days * 5
                # 加班加分
                attendance_base += min(20, overtime_days * 2)
                # 确保在0-100之间
                scores["attendance_score"] = max(0, min(100, attendance_base))
                
                if late_days == 0 and absent_days == 0:
                    scores["details"]["attendance"] = f"考勤优秀，加班{overtime_days}天"
                else:
                    scores["details"]["attendance"] = f"缺勤{absent_days}天，迟到{late_days}天"
            else:
                scores["attendance_score"] = 50
                scores["details"]["attendance"] = "数据不足"
        else:
            scores["attendance_score"] = 40
            scores["details"]["attendance"] = "缺少考勤数据"
        
        # 6. 政治画像评分 (100分)
        if employee_data:
            # 群众80分，党员95分
            scores["political_score"] = 80
            scores["details"]["political"] = "群众身份，政治表现良好"
        else:
            scores["political_score"] = 50
            scores["details"]["political"] = "缺少员工信息"
        
        # 计算总分 (6维度的平均分)
        scores["total_score"] = round(
            (scores["professional_score"] + scores["adaptability_score"] + 
             scores["innovation_score"] + scores["learning_score"] + 
             scores["attendance_score"] + scores["political_score"]) / 6, 1
        )
        
        # 适配等级
        if scores["total_score"] >= 90:
            scores["level"] = "优秀匹配"
        elif scores["total_score"] >= 80:
            scores["level"] = "良好匹配"
        elif scores["total_score"] >= 70:
            scores["level"] = "基本匹配"
        elif scores["total_score"] >= 60:
            scores["level"] = "勉强匹配"
        else:
            scores["level"] = "不匹配"
        
        return scores

    async def synthesize(
        self, 
        user_query: str, 
        query_plan: QueryPlan,
        query_results: List[QueryResult]
    ) -> str:
        """
        使用大模型整合查询结果，生成回答
        
        Args:
            user_query: 用户原始查询
            query_plan: 查询计划
            query_results: 查询结果
            
        Returns:
            整合后的回答
        """
        # 检查是否是人岗适配查询
        is_alignment_query = any(kw in user_query for kw in ["适配", "匹配", "胜任", "适岗"])
        
        if is_alignment_query:
            # 计算人岗适配分数
            # 构建精简的结果摘要（只保留必要数据）
            compact_summary = []
            for result in query_results:
                if result.success:
                    # 精简数据，只保留关键信息
                    compact_data = self._compact_data_for_alignment(result.step.data_source.value, result.data)
                    compact_summary.append({
                        "step": result.step.step_number,
                        "data_source": result.step.data_source.value,
                        "data": compact_data
                    })
            
            scores = self._calculate_alignment_scores(compact_summary)
            
            # 构建人岗适配报告（不包含完整原始数据，减少tokens）
            synthesis_prompt = f"""作为HR助手，请根据以下计算出的分数和精简数据，生成详细的人岗适配分析报告。

用户查询: {user_query}

员工: {query_plan.employee_name or '未指定'}

【计算得出的分数】
- 专业能力: {scores['professional_score']}/100分 - {scores['details'].get('professional', '')}
- 适应能力: {scores['adaptability_score']}/100分 - {scores['details'].get('adaptability', '')}
- 创新能力: {scores['innovation_score']}/100分 - {scores['details'].get('innovation', '')}
- 学习能力: {scores['learning_score']}/100分 - {scores['details'].get('learning', '')}
- 工时维度: {scores['attendance_score']}/100分 - {scores['details'].get('attendance', '')}
- 政治画像: {scores['political_score']}/100分 - {scores['details'].get('political', '')}
- 总分: {scores['total_score']}/100分
- 适配等级: {scores['level']}

【关键数据】
- 员工: {query_plan.employee_name or '未指定'}
- 部门: {query_plan.department or '未指定'}

请生成结构化的人岗适配分析报告，包含：
1. 综合评分（总分和等级）
2. 各维度详细评分和说明
3. 优势分析
4. 风险预警
5. 发展建议
6. 岗位适配结论

报告要求专业、客观、基于已提供的分数和数据进行分析。"""
        else:
            # 普通查询，构建完整的结果摘要
            results_summary = []
            for result in query_results:
                if result.success:
                    results_summary.append({
                        "step": result.step.step_number,
                        "data_source": result.step.data_source.value,
                        "query_condition": result.step.query_condition,
                        "reason": result.step.reason,
                        "data": result.data
                    })
                else:
                    results_summary.append({
                        "step": result.step.step_number,
                        "data_source": result.step.data_source.value,
                        "error": result.error_message
                    })
            
            # 普通查询的prompt
            synthesis_prompt = f"""作为HR助手，请根据查询数据回答用户问题。

用户查询: {user_query}

查询计划:
- 员工: {query_plan.employee_name or '未指定'}
- 部门: {query_plan.department or '未指定'}

查询结果:
{json.dumps(results_summary, ensure_ascii=False, indent=2)}

请根据以上数据，直接回答用户的问题。如果数据中不包含相关信息，请说明。
回答要求:
1. 直接回答用户问题，不要重复查询过程
2. 使用数据支持你的回答
3. 如果数据不足，说明缺少哪些信息
4. 保持简洁明了"""

        try:
            messages = [{"role": "user", "content": synthesis_prompt}]
            response = await self.llm.ainvoke(messages)
            # 清理模型输出的特殊标记
            content = response.content
            special_tokens = ['<|im_end|>', '<|im_start|>', '<|endoftext|>']
            for token in special_tokens:
                content = content.replace(token, '')
            return content.strip()
        except Exception as e:
            return f"整合结果时出现错误: {str(e)}"


class IntelligentHRAgent:
    """
    智能HR助手 - 整合查询规划、数据检索和结果合成
    
    执行流程:
    1. 大模型分析查询，规划查询步骤
    2. 根据规划查询数据库
    3. 大模型整合结果，生成回答
    """
    
    def __init__(self, llm):
        self.llm = llm
        self.planner = QueryPlanner(llm)
        self.synthesizer = ResultSynthesizer(llm)
    
    async def query(
        self, 
        user_query: str, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        执行完整查询流程
        
        Args:
            user_query: 用户查询
            db: 数据库会话
            
        Returns:
            包含查询过程和结果的字典
        """
        # 步骤1: 大模型规划查询
        query_plan = await self.planner.create_plan(user_query)
        
        # 步骤2: 执行查询
        retriever = DataRetriever(db)
        query_results = await retriever.execute_plan(query_plan)
        
        # 步骤3: 大模型整合结果
        answer = await self.synthesizer.synthesize(
            user_query, query_plan, query_results
        )
        
        return {
            "query": user_query,
            "plan": {
                "employee_name": query_plan.employee_name,
                "department": query_plan.department,
                "steps": [
                    {
                        "step_number": s.step_number,
                        "data_source": s.data_source.value,
                        "query_condition": s.query_condition,
                        "reason": s.reason
                    }
                    for s in query_plan.steps
                ]
            },
            "results": [
                {
                    "step": r.step.step_number,
                    "data_source": r.step.data_source.value,
                    "success": r.success,
                    "data": r.data if r.success else None,
                    "error": r.error_message if not r.success else None
                }
                for r in query_results
            ],
            "answer": answer
        }
