"""人岗适配评估Agent - 基于国央企员工人岗适配管理体系."""

import json
from datetime import date
from typing import Any, Dict, List, Optional, AsyncGenerator

from langchain.schema import Document
from langchain_community.chat_models import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.graph import END, StateGraph
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.config import get_settings
from app.database.crud import EmployeeCRUD
from app.knowledge.builder import KnowledgeBuilder
from app.agent.query_planner import IntelligentHRAgent


# 人岗适配评估维度定义（基于国央企员工人岗适配管理体系）
ALIGNMENT_DIMENSIONS = {
    "能力画像": {
        "description": "员工能力素质评估",
        "weight": 0.40,
        "indicators": [
            {"name": "专业能力", "weight": 0.40, "source": "岗位说明书、项目成果"},
            {"name": "管理能力", "weight": 0.25, "source": "360度评估、项目管理"},
            {"name": "创新能力", "weight": 0.15, "source": "技术创新、管理优化"},
            {"name": "学习能力", "weight": 0.10, "source": "培训记录、认证情况"},
            {"name": "适应能力", "weight": 0.10, "source": "工作变动、跨部门协作"},
        ]
    },
    "品质态度": {
        "description": "政治素质和廉洁自律评估",
        "weight": 0.25,
        "indicators": [
            {"name": "政治立场", "description": "对党的路线方针政策的认同度和执行力"},
            {"name": "廉洁自律", "description": "遵守党纪国法和廉洁从业规定的情况"},
            {"name": "组织观念", "description": "服从组织安排、维护组织权威的表现"},
            {"name": "群众基础", "description": "在员工群众中的认可度和影响力"},
        ]
    },
    "时间维度": {
        "description": "工作稳定性和持续性评估",
        "weight": 0.15,
        "indicators": [
            {"name": "稳定性指标", "description": "连续6-12个月的考勤数据分析"},
            {"name": "响应能力", "description": "紧急任务响应速度和加班完成质量"},
            {"name": "持续性表现", "description": "长时间段内工作表现的一致性"},
        ]
    },
    "绩效表现": {
        "description": "历史绩效和考核结果",
        "weight": 0.20,
        "indicators": [
            {"name": "绩效分数", "description": "近期绩效考核得分"},
            {"name": "绩效趋势", "description": "绩效变化趋势（上升/下降/稳定）"},
            {"name": "目标达成", "description": "工作目标完成情况"},
        ]
    }
}

# 五大序列适配标准
SEQUENCE_STANDARDS = {
    "干部序列": {
        "high_match": "政治过硬、能力突出、群众公认",
        "medium_match": "政治合格、能力适中、表现良好",
        "low_match": "政治不强、能力不足、群众不认可"
    },
    "职业经理人序列": {
        "high_match": "市场导向强、经营业绩优、创新能力突出",
        "medium_match": "市场意识一般、业绩达标、有一定创新能力",
        "low_match": "市场意识淡薄、业绩不佳、缺乏创新"
    },
    "SBU/BU总裁序列": {
        "high_match": "战略思维强、资源整合能力强、责任担当意识强",
        "medium_match": "有一定战略思维、资源整合能力一般、责任意识较强",
        "low_match": "缺乏战略思维、资源整合能力弱、责任意识淡薄"
    },
    "专家序列": {
        "high_match": "专业水平高、创新能力强、知识贡献大",
        "medium_match": "专业水平较好、有一定创新能力、知识贡献一般",
        "low_match": "专业水平不足、创新能力弱、知识贡献小"
    },
    "员工序列": {
        "high_match": "岗位胜任能力强、学习能力突出、团队合作好",
        "medium_match": "岗位胜任能力一般、学习能力中等、团队合作较好",
        "low_match": "岗位胜任能力不足、学习能力差、团队合作不佳"
    }
}


class AlignmentAgent:
    """人岗适配评估Agent."""

    def __init__(self):
        """Initialize the alignment agent."""
        self.settings = get_settings()
        self.llm = None
        self.knowledge_builder = KnowledgeBuilder()
        self.vector_store = None
        self.workflow = None
        self._init_llm()
        self._init_vector_store()

    def _init_llm(self):
        """Initialize the LLM client - 使用本地vLLM部署的Qwen模型."""
        self.llm = ChatOpenAI(
            model_name=self.settings.vllm_model,
            openai_api_base=self.settings.openai_api_base,
            openai_api_key=self.settings.openai_api_key,
            temperature=0.3,  # 降低温度以获得更稳定的评估结果
            max_tokens=512,  # 减少输出token数，给输入留更多空间
            streaming=True,  # 启用流式输出
        )

    def _init_vector_store(self):
        """Initialize vector store."""
        self.vector_store = self.knowledge_builder.load_vector_store()

    async def intelligent_query(
        self,
        query: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        智能查询 - 使用大模型规划查询步骤并整合结果

        执行流程:
        1. 大模型分析查询，规划查询步骤
        2. 根据规划查询数据库
        3. 大模型整合结果，生成回答

        Args:
            query: 用户查询
            db: 数据库会话

        Returns:
            包含查询计划、查询结果和最终回答的字典
        """
        agent = IntelligentHRAgent(self.llm)
        return await agent.query(query, db)

    async def intelligent_query_stream(
        self,
        query: str,
        db: AsyncSession
    ) -> AsyncGenerator[str, None]:
        """
        智能查询 - 流式输出版本，显示规划和执行步骤

        Args:
            query: 用户查询
            db: 数据库会话

        Yields:
            流式输出的回答片段
        """
        from app.agent.query_planner import IntelligentHRAgent

        agent = IntelligentHRAgent(self.llm)

        # 步骤1: 大模型规划查询
        yield "### 🔍 步骤1: 分析查询意图\n\n"
        yield "正在分析您的问题，规划查询步骤...\n\n"

        query_plan = await agent.planner.create_plan(query)

        yield "**识别信息:**\n"
        yield f"- 员工: {query_plan.employee_name or '未指定'}\n"
        yield f"- 部门: {query_plan.department or '未指定'}\n\n"

        yield "**查询计划:**\n"
        for step in query_plan.steps:
            yield f"{step.step_number}. 查询 **{step.data_source.value}** - {step.reason}\n"
        yield "\n"

        # 步骤2: 执行查询
        yield "### 📊 步骤2: 执行数据库查询\n\n"

        from app.agent.query_planner import DataRetriever
        retriever = DataRetriever(db)
        query_results = await retriever.execute_plan(query_plan)

        for result in query_results:
            if result.success:
                yield f"✅ 查询 **{result.step.data_source.value}** 成功\n"
                # 显示部分数据
                if result.data:
                    data_str = json.dumps(result.data, ensure_ascii=False, indent=2)
                    # 只显示前300字符
                    if len(data_str) > 300:
                        yield f"   数据: {data_str[:300]}...\n"
                    else:
                        yield f"   数据: {data_str}\n"
            else:
                yield f"❌ 查询 **{result.step.data_source.value}** 失败: {result.error_message}\n"
        yield "\n"

        # 步骤3: 大模型整合结果
        yield "### 🧠 步骤3: 整合分析结果\n\n"

        # 检查是否是人岗适配查询，如果是则计算分数并嵌入数据
        is_alignment_query = any(kw in query for kw in ["适配", "匹配", "胜任", "适岗"])
        if is_alignment_query:
            # 计算人岗适配分数
            compact_summary = []
            for result in query_results:
                if result.success:
                    compact_data = agent.synthesizer._compact_data_for_alignment(
                        result.step.data_source.value, result.data
                    )
                    compact_summary.append({
                        "step": result.step.step_number,
                        "data_source": result.step.data_source.value,
                        "data": compact_data
                    })
            scores = agent.synthesizer._calculate_alignment_scores(compact_summary)
            # 嵌入分数数据（使用特殊标记，前端可以解析）
            scores_json = json.dumps(scores, ensure_ascii=False)
            yield f"<!--RADAR_CHART_DATA:{scores_json}-->\n\n"

        answer = await agent.synthesizer.synthesize(query, query_plan, query_results)

        yield "**最终回答:**\n\n"
        yield answer

    async def analyze_employee_alignment(
        self,
        employee_name: str,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """分析员工的人岗适配情况.
        
        Args:
            employee_name: 员工姓名
            db: 数据库会话
            
        Returns:
            人岗适配分析结果
        """
        if not db:
            return {"error": "需要数据库连接来进行员工分析"}

        # 1. 获取员工基本信息
        employee = await EmployeeCRUD.get_by_name(db, employee_name)
        if not employee:
            return {"error": f"未找到员工: {employee_name}"}

        # 2. 获取员工关联数据
        employee_data = await self._gather_employee_data(db, employee)

        # 3. 构建分析提示
        analysis_prompt = self._build_alignment_prompt(employee_data)

        # 4. 调用LLM进行分析
        try:
            chain = analysis_prompt | self.llm | StrOutputParser()
            result = await chain.ainvoke({})
            
            # 5. 清理模型输出的特殊标记
            result = self._clean_model_output(result)
            
            # 6. 解析分析结果
            analysis_result = self._parse_analysis_result(result)
            analysis_result["employee_name"] = employee_name
            analysis_result["employee_id"] = employee.id
            analysis_result["analysis_date"] = str(date.today())
            
            return analysis_result
            
        except Exception as e:
            return {
                "error": f"分析过程中出现错误: {str(e)}",
                "employee_name": employee_name
            }

    def _format_streaming_output(self, text: str) -> str:
        """格式化流式输出内容，确保正确的换行和Markdown格式.
        
        Args:
            text: 原始文本
            
        Returns:
            格式化后的文本
        """
        import re
        
        # 在 ### 前添加换行
        text = re.sub(r'([^\n])(###\s)', r'\1\n\2', text)
        
        # 在 ## 前添加换行
        text = re.sub(r'([^\n])(##\s)', r'\1\n\2', text)
        
        # 在 # 前添加换行（排除 ### 和 ##）
        text = re.sub(r'([^\n#])(#\s)', r'\1\n\2', text)
        
        # 在 - 列表项前添加换行
        text = re.sub(r'([^\n])(\s*-\s)', r'\1\n\2', text)
        
        # 在数字列表前添加换行
        text = re.sub(r'([^\n])(\d+\.\s)', r'\1\n\2', text)
        
        return text

    async def analyze_employee_alignment_stream(
        self,
        employee_name: str,
        db: Optional[AsyncSession] = None
    ) -> AsyncGenerator[str, None]:
        """流式分析员工的人岗适配情况.
        
        Args:
            employee_name: 员工姓名
            db: 数据库会话
            
        Yields:
            分析结果的文本片段
        """
        if not db:
            yield json.dumps({"error": "需要数据库连接来进行员工分析"}, ensure_ascii=False)
            return

        # 1. 获取员工基本信息
        employee = await EmployeeCRUD.get_by_name(db, employee_name)
        if not employee:
            yield json.dumps({"error": f"未找到员工: {employee_name}"}, ensure_ascii=False)
            return

        # 2. 获取员工关联数据
        employee_data = await self._gather_employee_data(db, employee)

        # 3. 构建分析提示
        analysis_prompt = self._build_alignment_prompt(employee_data)

        # 4. 流式调用LLM进行分析
        try:
            chain = analysis_prompt | self.llm
            full_content = ""
            async for chunk in chain.astream({}):
                # 清理模型输出的特殊标记
                cleaned_chunk = self._clean_model_output(chunk.content)
                full_content += cleaned_chunk
                yield cleaned_chunk
        except Exception as e:
            yield f"\n[错误] 分析过程中出现错误: {str(e)}"

    async def _gather_employee_data(
        self,
        db: AsyncSession,
        employee
    ) -> Dict[str, Any]:
        """收集员工相关数据.
        
        Args:
            db: 数据库会话
            employee: 员工对象
            
        Returns:
            员工综合数据
        """
        # 适配SQLite数据库结构
        data = {
            "basic_info": {
                "name": employee.name,
                "department": employee.department,
                "position": employee.position,
                "id": employee.id,
                "hire_date": str(employee.hire_date) if employee.hire_date else None,
                "contract_end_date": str(employee.contract_end_date) if employee.contract_end_date else None,
                "performance_score": employee.performance_score,
                "education": employee.education,
                "school": employee.school,
                "political_status": employee.political_status,
                "sequence": employee.sequence,
                "job_level": employee.job_level,
            },
            "contracts": [],
            "attendance": [],
            "conversations": [],
            "salary": {},
        }

        # 获取合同信息
        if hasattr(employee, 'contracts') and employee.contracts:
            for contract in employee.contracts:
                data["contracts"].append({
                    "type": contract.contract_type,
                    "end_date": str(contract.end_date) if contract.end_date else None,
                    "status": contract.status,
                })

        # 获取薪资信息
        try:
            from app.database.models import SalaryRecord
            from sqlalchemy import select
            result = await db.execute(
                select(SalaryRecord).where(SalaryRecord.employee_id == employee.id)
            )
            salary_records = result.scalars().all()
            if salary_records:
                latest_salary = salary_records[-1]  # 获取最新记录
                data["salary"] = {
                    "base_salary": float(latest_salary.base_salary) if latest_salary.base_salary else 0,
                    "bonus": float(latest_salary.bonus) if latest_salary.bonus else 0,
                    "net_salary": float(latest_salary.net_salary) if latest_salary.net_salary else 0,
                    "month": str(latest_salary.month) if latest_salary.month else None,
                }
        except Exception as e:
            logger.warning(f"获取薪资信息失败: {str(e)}")

        # 获取考勤信息（近3个月）
        try:
            from app.database.models import AttendanceRecord
            from sqlalchemy import select
            from datetime import datetime, timedelta

            three_months_ago = datetime.now().date() - timedelta(days=90)
            result = await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.employee_id == employee.id,
                    AttendanceRecord.date >= three_months_ago
                )
            )
            attendance_records = result.scalars().all()

            if attendance_records:
                total_days = len(attendance_records)
                late_days = sum(1 for r in attendance_records if r.status == "迟到")
                early_leave_days = sum(1 for r in attendance_records if r.status == "早退")
                absent_days = sum(1 for r in attendance_records if r.status == "缺勤")

                # 计算加班情况
                overtime_days = sum(1 for r in attendance_records if r.overtime_hours and r.overtime_hours > 0)
                total_overtime_hours = sum(r.overtime_hours for r in attendance_records if r.overtime_hours)

                # 计算平均工作时长
                total_work_hours = 0
                valid_days = 0
                for r in attendance_records:
                    if r.work_hours:
                        total_work_hours += r.work_hours
                        valid_days += 1

                avg_work_hours = total_work_hours / valid_days if valid_days > 0 else 8.0

                data["attendance"] = {
                    "total_days": total_days,
                    "late_days": late_days,
                    "early_leave_days": early_leave_days,
                    "absent_days": absent_days,
                    "overtime_days": overtime_days,
                    "total_overtime_hours": round(total_overtime_hours, 1),
                    "avg_work_hours": round(avg_work_hours, 1),
                    "period": "近3个月"
                }
        except Exception as e:
            logger.warning(f"获取考勤信息失败: {str(e)}")

        return data

    def _build_alignment_prompt(self, employee_data: Dict[str, Any]) -> PromptTemplate:
        """构建人岗适配分析提示 - 精简版.

        Args:
            employee_data: 员工数据

        Returns:
            提示模板
        """
        # 精简员工数据，只保留关键信息
        simplified_data = {
            "name": employee_data.get("name"),
            "department": employee_data.get("department"),
            "position": employee_data.get("position"),
            "attendance": employee_data.get("attendance", {}),
            "salary": employee_data.get("salary", {}),
        }

        template = """作为HR分析师，请评估员工人岗适配度。

## 评估维度与权重（满分100分）
1. 能力画像(70分): 专业能力50分、适应能力20分
2. 工时维度(20分): 考勤表现、工作时长、加班情况
3. 品质态度(10分): 工作态度、规章制度遵守

## 评分标准（重要）
- 工时维度(20分): 根据考勤数据评分
  * 无迟到早退缺勤: 18-20分
  * 迟到1-3次: 15-17分
  * 迟到4-6次: 10-14分
  * 迟到>6次或缺勤>5天: 5-9分
  * 迟到>10次或缺勤>10天: 0-4分

- 适应能力(20分): 包含抗压能力、沟通能力
  * 频繁迟到缺勤反映适应能力差，应扣减5-10分

- 品质态度(10分): 反映工作态度和纪律性
  * 迟到缺勤多应扣减3-5分

## 员工数据
{employee_data}

## 输出格式
### 1. 综合评分 (0-100分)
- 总体评分: [分数]
- 适配等级: [高度匹配/基本匹配/待提升/不匹配]

### 2. 各维度详细评分
**能力画像 (70%)**
- 专业能力: [分数]/50
- 适应能力: [分数]/20

**工时维度 (20%)**: [分数]/20 - [根据考勤数据说明评分理由]

**品质态度 (10%)**: [分数]/10 - [根据考勤纪律说明评分理由]

### 3. 优势分析
- [优势1]
- [优势2]

### 4. 风险预警
- [风险1]

### 5. 发展建议
- [建议1]

### 6. 岗位适配结论
[总结]"""

        return PromptTemplate(
            template=template,
            input_variables=[],
            partial_variables={"employee_data": json.dumps(simplified_data, ensure_ascii=False)}
        )

    def _parse_analysis_result(self, result: str) -> Dict[str, Any]:
        """解析LLM的分析结果.
        
        Args:
            result: LLM返回的文本
            
        Returns:
            结构化分析结果
        """
        # 尝试提取评分
        import re
        
        parsed = {
            "raw_analysis": result,
            "overall_score": None,
            "alignment_level": None,
            "dimension_scores": {},
        }

        # 提取总体评分
        score_match = re.search(r'总体评分[:：]\s*(\d+)', result)
        if score_match:
            parsed["overall_score"] = int(score_match.group(1))

        # 提取适配等级
        level_match = re.search(r'适配等级[:：]\s*(高度匹配|基本匹配|不匹配)', result)
        if level_match:
            parsed["alignment_level"] = level_match.group(1)

        # 提取各维度评分
        dimension_pattern = r'[-\*]\s*(能力画像|品质态度|时间维度|绩效表现)[:：]\s*(\d+)'
        for match in re.finditer(dimension_pattern, result):
            dimension = match.group(1)
            score = int(match.group(2))
            parsed["dimension_scores"][dimension] = score

        return parsed

    async def compare_employees(
        self,
        employee_names: List[str],
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """对比多个员工的人岗适配情况.
        
        Args:
            employee_names: 员工姓名列表
            db: 数据库会话
            
        Returns:
            对比分析结果
        """
        if not db:
            return {"error": "需要数据库连接来进行员工对比"}

        results = []
        for name in employee_names:
            result = await self.analyze_employee_alignment(name, db)
            if "error" not in result:
                results.append(result)

        if not results:
            return {"error": "无法获取任何员工的分析数据"}

        # 生成对比报告
        comparison = {
            "employees": [r.get("employee_name") for r in results],
            "scores": {r.get("employee_name"): r.get("overall_score") for r in results},
            "levels": {r.get("employee_name"): r.get("alignment_level") for r in results},
            "details": results,
        }

        return comparison


    async def chat_about_employee(
        self,
        query: str,
        db: Optional[AsyncSession] = None
    ) -> str:
        """对话式查询员工信息.
        
        Args:
            query: 用户查询，例如"石京京是哪个学校的"
            db: 数据库会话
            
        Returns:
            Agent的回答
        """
        if not db:
            return "需要数据库连接来查询员工信息"

        # 从查询中提取员工姓名（简单匹配）
        # 获取所有员工姓名进行匹配
        from app.database.crud import EmployeeCRUD
        all_employees = await EmployeeCRUD.get_all(db)
        employee_names = [emp.name for emp in all_employees]
        
        # 查找查询中提到的员工姓名
        mentioned_employee = None
        for name in employee_names:
            if name in query:
                mentioned_employee = name
                break
        
        # 检查是否是部门级查询
        dept_keywords = ["部门", "工作室", "事业部", "团队", "人工成本", "考勤"]
        is_dept_query = any(keyword in query for keyword in dept_keywords)
        
        # 如果是部门级查询，但没有提到员工姓名，尝试提取部门信息
        if is_dept_query and not mentioned_employee:
            return await self._handle_department_query(query, db, all_employees)
        
        if not mentioned_employee:
            return "请提供员工姓名，例如：'石京京是哪个学校的'"

        # 获取员工信息
        employee = await EmployeeCRUD.get_by_name(db, mentioned_employee)
        if not employee:
            return f"暂时未找到该员工: {mentioned_employee}"

        # 检查是否是人岗适配/匹配问题
        alignment_keywords = ["适配", "匹配", "胜任", "适岗"]
        is_alignment_query = any(keyword in query for keyword in alignment_keywords)

        # 检查是否是考勤相关查询
        attendance_keywords = ["考勤", "加班", "迟到", "早退", "打卡", "工时", "出勤"]
        is_attendance_query = any(keyword in query for keyword in attendance_keywords)

        if is_alignment_query or is_attendance_query:
            return await self._handle_alignment_query(employee, db, query)

        # 使用新的智能查询架构
        try:
            result = await self.intelligent_query(query, db)
            return result['answer']
        except Exception as e:
            logger.error(f"智能查询失败: {str(e)}")
            # 降级到旧的查询方式
            employee_data = await self._gather_employee_data(db, employee)
            chat_prompt = f"""你是人力资源助手，根据以下员工数据回答用户问题。

员工数据：{json.dumps(employee_data, ensure_ascii=False)}

用户问题：{query}

请直接回答用户的问题，简洁明了。如果数据中不包含相关信息，请说明。"""
            messages = [{"role": "user", "content": chat_prompt}]
            result = await self.llm.ainvoke(messages)
            return self._clean_model_output(result.content)

    async def _handle_alignment_query(self, employee, db: AsyncSession, query: str = None) -> str:
        """处理人岗适配查询，返回包含具体数据的结构化回答.

        Args:
            employee: 员工对象
            db: 数据库会话
            query: 原始查询字符串，用于判断查询类型

        Returns:
            结构化的人岗适配评估报告
        """
        # 获取员工详细数据
        from sqlalchemy import select, func
        from app.database.models import AttendanceRecord, SalaryRecord, InterviewRecord

        # 1. 获取近3个月的考勤数据
        from datetime import datetime, timedelta
        three_months_ago = datetime.now().date() - timedelta(days=90)

        attendance_result = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == employee.id,
                AttendanceRecord.date >= three_months_ago
            )
        )
        attendance_records = attendance_result.scalars().all()

        # 如果是纯考勤查询（不包含适配/匹配等关键词），返回简洁的考勤报告
        if query:
            alignment_keywords = ["适配", "匹配", "胜任", "适岗"]
            is_full_alignment_query = any(kw in query for kw in alignment_keywords)
            if not is_full_alignment_query:
                # 检查是否是特定考勤类型查询
                if "加班" in query:
                    return await self._handle_overtime_query(employee, attendance_records)
                elif "考勤" in query or "出勤" in query:
                    return await self._handle_attendance_summary_query(employee, attendance_records)
                elif "迟到" in query:
                    return await self._handle_late_query(employee, attendance_records)
        
        # 计算考勤指标
        total_days = len(attendance_records)
        late_days = sum(1 for r in attendance_records if r.status == "迟到")
        early_leave_days = sum(1 for r in attendance_records if r.status == "早退")
        absent_days = sum(1 for r in attendance_records if r.status == "缺勤")
        
        # 计算实际工作时长和加班情况（从打卡时间计算）
        total_work_hours = 0
        valid_work_days = 0
        overtime_days = 0
        total_overtime_hours = 0
        
        for r in attendance_records:
            work_duration = 0
            has_valid_record = False
            
            if r.work_hours:
                work_duration = r.work_hours
                has_valid_record = True
            elif r.check_in_time and r.check_out_time:
                # 从打卡时间计算工作时长
                try:
                    from datetime import datetime
                    if isinstance(r.check_in_time, str):
                        check_in = datetime.strptime(r.check_in_time, "%H:%M")
                        check_out = datetime.strptime(r.check_out_time, "%H:%M")
                    elif isinstance(r.check_in_time, datetime):
                        check_in = r.check_in_time
                        check_out = r.check_out_time
                    else:
                        # 处理time对象
                        check_in = datetime.combine(datetime.today(), r.check_in_time)
                        check_out = datetime.combine(datetime.today(), r.check_out_time)
                    
                    # 计算工作时长（小时）
                    work_duration = (check_out.hour - check_in.hour) + (check_out.minute - check_in.minute) / 60
                    if work_duration > 0:
                        has_valid_record = True
                except:
                    pass
            
            if has_valid_record and work_duration > 0:
                total_work_hours += work_duration
                valid_work_days += 1
                
                # 计算加班：下班时间超过18:30算加班
                if r.check_out_time:
                    try:
                        # 统一提取小时和分钟
                        check_out_hour = None
                        check_out_minute = None
                        
                        if isinstance(r.check_out_time, str):
                            # 处理 "HH:MM" 或 "YYYY-MM-DD HH:MM:SS" 格式
                            if len(r.check_out_time) > 5:
                                check_out = datetime.strptime(r.check_out_time, "%Y-%m-%d %H:%M:%S")
                            else:
                                check_out = datetime.strptime(r.check_out_time, "%H:%M")
                            check_out_hour = check_out.hour
                            check_out_minute = check_out.minute
                        else:
                            # datetime或time对象
                            check_out_hour = r.check_out_time.hour
                            check_out_minute = r.check_out_time.minute
                        
                        # 如果下班时间超过18:30，计算加班时长
                        if check_out_hour is not None and check_out_minute is not None:
                            if check_out_hour > 18 or (check_out_hour == 18 and check_out_minute >= 30):
                                overtime_hours = (check_out_hour - 18) + (check_out_minute - 30) / 60
                                
                                if overtime_hours > 0:
                                    overtime_days += 1
                                    total_overtime_hours += overtime_hours
                    except Exception as e:
                        # 忽略解析错误
                        pass
        
        # 计算平均工作时长
        if valid_work_days > 0:
            avg_work_hours = total_work_hours / valid_work_days
        elif total_days > 0:
            # 如果没有打卡数据，使用标准8小时工作日
            avg_work_hours = 8.0
            valid_work_days = total_days - absent_days
        else:
            avg_work_hours = 0
            valid_work_days = 0
        
        avg_overtime_hours = total_overtime_hours / total_days if total_days > 0 else 0
        avg_total_hours = avg_work_hours + avg_overtime_hours
        
        # 2. 获取面试/考核记录
        interview_result = await db.execute(
            select(InterviewRecord).where(InterviewRecord.employee_id == employee.id)
        )
        interview_records = interview_result.scalars().all()
        
        # 计算能力评分
        professional_score = 0
        communication_score = 0
        if interview_records:
            latest_interview = interview_records[-1]
            professional_score = latest_interview.professional_score or 0
            communication_score = latest_interview.communication_score or 0
        
        # 3. 获取近3个月的薪资记录（包含绩效薪酬），如果没有则获取最新的3条
        salary_result = await db.execute(
            select(SalaryRecord).where(
                SalaryRecord.employee_id == employee.id,
                SalaryRecord.month >= three_months_ago
            ).order_by(SalaryRecord.month.desc())
        )
        salary_records = salary_result.scalars().all()
        
        # 如果近3个月没有记录，获取最新的3条记录
        if not salary_records:
            salary_result = await db.execute(
                select(SalaryRecord).where(
                    SalaryRecord.employee_id == employee.id
                ).order_by(SalaryRecord.month.desc()).limit(3)
            )
            salary_records = salary_result.scalars().all()
        
        # 计算绩效相关数据
        total_bonus = 0
        total_base_salary = 0
        total_net_salary = 0
        total_salary_records = len(salary_records)
        
        if salary_records:
            for record in salary_records:
                total_bonus += float(record.bonus or 0)
                total_base_salary += float(record.base_salary or 0)
                total_net_salary += float(record.net_salary or 0)
        
        # 计算平均值
        avg_base_salary = total_base_salary / total_salary_records if total_salary_records > 0 else 0
        avg_bonus = total_bonus / total_salary_records if total_salary_records > 0 else 0
        avg_net_salary = total_net_salary / total_salary_records if total_salary_records > 0 else 0
        
        # 计算绩效薪酬占比 = 绩效薪酬 / 应发合计
        bonus_ratio = (avg_bonus / avg_net_salary * 100) if avg_net_salary > 0 else 0
        
        # 4. 获取员工performance_score并结合绩效薪酬计算综合绩效分数
        employee_performance_score = employee.performance_score or 0
        
        # 综合绩效分数计算方式：
        # - 如果员工有performance_score，使用performance_score
        # - 否则根据绩效薪酬占比评估：
        #   * 占比 >= 60%: 优秀 (90-100分)
        #   * 占比 >= 40%: 良好 (75-89分)
        #   * 占比 >= 20%: 合格 (60-74分)
        #   * 占比 < 20%: 待提升 (<60分)
        if employee_performance_score > 0:
            performance_score = employee_performance_score
        else:
            if bonus_ratio >= 60:
                performance_score = 95
            elif bonus_ratio >= 40:
                performance_score = 80
            elif bonus_ratio >= 20:
                performance_score = 65
            else:
                performance_score = 50
        
        # 5. 计算核心能力匹配度（综合评分）
        # 基于：专业能力(40%) + 沟通能力(20%) + 绩效表现(30%) + 考勤表现(10%)
        attendance_score = max(0, 100 - (late_days + early_leave_days * 2 + absent_days * 5) * 5) if total_days > 0 else 80
        
        capability_match = (
            professional_score * 0.4 +
            communication_score * 0.2 +
            performance_score * 0.3 +
            attendance_score * 0.1
        ) if professional_score > 0 else performance_score * 0.8 + attendance_score * 0.2
        
        capability_match = min(100, max(0, capability_match))
        
        # 6. 确定绩效表现等级
        if performance_score >= 90:
            performance_level = "优秀"
        elif performance_score >= 75:
            performance_level = "良好"
        elif performance_score >= 60:
            performance_level = "合格"
        else:
            performance_level = "待提升"
        
        # 7. 计算KPI完成率（使用绩效分数作为参考）
        kpi_completion_rate = performance_score
        
        # 8. 确定综合适配等级
        if capability_match >= 85:
            alignment_level = "高度适配"
        elif capability_match >= 70:
            alignment_level = "基本适配"
        elif capability_match >= 60:
            alignment_level = "需针对性提升"
        else:
            alignment_level = "不适配"
        
        # 9. 生成结构化回答 - 使用Markdown格式
        response = f"""### {employee.name}人岗适配度评估报告

#### 1. 综合评分
- **总体评分**：{capability_match:.1f}分
- **适配等级**：{alignment_level}

#### 2. 核心能力匹配度
- **能力匹配度**：{capability_match:.1f}%
  - 专业能力评分：{professional_score:.1f}分
  - 沟通能力评分：{communication_score:.1f}分
  - 考勤表现评分：{attendance_score:.1f}分

#### 3. 绩效表现
- **绩效等级**：{performance_level}
- **KPI完成率**：{kpi_completion_rate:.1f}%
- **绩效分数**：{performance_score:.1f}分
- **平均绩效薪酬**：{avg_bonus:.0f}元/月（占基本工资{bonus_ratio:.1f}%）

#### 4. 工时表现
- **平均工作时长**：{avg_work_hours:.1f}小时/天
- **加班天数**：{overtime_days}天（总加班{total_overtime_hours:.1f}小时）
- **综合工作时长**：{avg_total_hours:.1f}小时/天
- **考勤情况**：近3个月迟到{late_days}次，早退{early_leave_days}次

#### 5. 发展建议
{self._generate_alignment_suggestion(alignment_level, employee.name)}"""

        return response

    async def _handle_overtime_query(self, employee, attendance_records) -> str:
        """处理加班查询，返回简洁的加班报告.

        Args:
            employee: 员工对象
            attendance_records: 考勤记录列表

        Returns:
            加班情况报告
        """
        total_days = len(attendance_records)
        if total_days == 0:
            return f"未找到{employee.name}的考勤记录。"

        # 计算加班情况
        overtime_days = 0
        total_overtime_hours = 0
        overtime_records = []

        for r in attendance_records:
            if r.overtime_hours and r.overtime_hours > 0:
                overtime_days += 1
                total_overtime_hours += r.overtime_hours
                overtime_records.append({
                    'date': r.date,
                    'hours': r.overtime_hours,
                    'check_out': r.check_out_time
                })
            elif r.check_out_time:
                # 从打卡时间计算加班
                try:
                    from datetime import datetime
                    if isinstance(r.check_out_time, str):
                        if len(r.check_out_time) > 5:
                            check_out = datetime.strptime(r.check_out_time, "%Y-%m-%d %H:%M:%S")
                        else:
                            check_out = datetime.strptime(r.check_out_time, "%H:%M")
                        check_out_hour = check_out.hour
                        check_out_minute = check_out.minute
                    elif hasattr(r.check_out_time, 'hour'):
                        check_out_hour = r.check_out_time.hour
                        check_out_minute = r.check_out_time.minute
                    else:
                        continue

                    if check_out_hour > 18 or (check_out_hour == 18 and check_out_minute >= 30):
                        overtime_hours = (check_out_hour - 18) + (check_out_minute - 30) / 60
                        if overtime_hours > 0:
                            overtime_days += 1
                            total_overtime_hours += overtime_hours
                            overtime_records.append({
                                'date': r.date,
                                'hours': round(overtime_hours, 1),
                                'check_out': f"{check_out_hour:02d}:{check_out_minute:02d}"
                            })
                except:
                    pass

        if overtime_days == 0:
            return f"{employee.name}近3个月没有加班记录。"

        # 生成简洁的加班报告
        avg_overtime = total_overtime_hours / overtime_days if overtime_days > 0 else 0

        response = f"""### {employee.name}的加班情况

**统计周期**：近3个月

**加班概况**：
- 加班天数：{overtime_days}天
- 总加班时长：{total_overtime_hours:.1f}小时
- 平均每次加班：{avg_overtime:.1f}小时

**加班记录详情**（最近10次）：
"""

        # 显示最近10条加班记录
        for record in sorted(overtime_records, key=lambda x: x['date'], reverse=True)[:10]:
            response += f"- {record['date']}: 加班{record['hours']}小时"
            if record.get('check_out'):
                response += f"（下班时间：{record['check_out']}）"
            response += "\n"

        return response

    async def _handle_attendance_summary_query(self, employee, attendance_records) -> str:
        """处理考勤汇总查询，返回简洁的考勤报告.

        Args:
            employee: 员工对象
            attendance_records: 考勤记录列表

        Returns:
            考勤情况报告
        """
        total_days = len(attendance_records)
        if total_days == 0:
            return f"未找到{employee.name}的考勤记录。"

        # 计算考勤指标（使用中文状态码）
        late_days = sum(1 for r in attendance_records if r.status == "迟到")
        early_leave_days = sum(1 for r in attendance_records if r.status == "早退")
        absent_days = sum(1 for r in attendance_records if r.status == "缺勤")
        abnormal_days = sum(1 for r in attendance_records if r.status == "异常")
        normal_days = sum(1 for r in attendance_records if r.status == "正常")

        # 计算平均工作时长
        total_work_hours = 0
        valid_days = 0
        for r in attendance_records:
            if r.work_hours:
                total_work_hours += r.work_hours
                valid_days += 1
        avg_work_hours = total_work_hours / valid_days if valid_days > 0 else 8.0

        # 计算加班情况
        overtime_days = sum(1 for r in attendance_records if r.overtime_hours and r.overtime_hours > 0)
        total_overtime_hours = sum(r.overtime_hours for r in attendance_records if r.overtime_hours)

        response = f"""### {employee.name}的考勤情况

**统计周期**：近3个月

**出勤统计**：
- 应出勤天数：{total_days}天
- 正常出勤：{normal_days}天
- 迟到：{late_days}次
- 早退：{early_leave_days}次
- 缺勤：{absent_days}天
- 异常：{abnormal_days}天

**工时统计**：
- 平均工作时长：{avg_work_hours:.1f}小时/天
- 加班天数：{overtime_days}天
- 总加班时长：{total_overtime_hours:.1f}小时
"""

        return response

    async def _handle_late_query(self, employee, attendance_records) -> str:
        """处理迟到查询，返回迟到记录.

        Args:
            employee: 员工对象
            attendance_records: 考勤记录列表

        Returns:
            迟到情况报告
        """
        total_days = len(attendance_records)
        if total_days == 0:
            return f"未找到{employee.name}的考勤记录。"

        # 筛选迟到记录
        late_records = [r for r in attendance_records if r.status == "迟到"]
        late_count = len(late_records)

        if late_count == 0:
            return f"{employee.name}近3个月没有迟到记录，出勤表现优秀！"

        response = f"""### {employee.name}的迟到情况

**统计周期**：近3个月

**迟到统计**：
- 迟到次数：{late_count}次
- 出勤天数：{total_days}天
- 迟到率：{late_count/total_days*100:.1f}%

**迟到记录详情**：
"""

        for r in sorted(late_records, key=lambda x: x.date, reverse=True):
            response += f"- {r.date}"
            if r.check_in_time:
                if isinstance(r.check_in_time, str):
                    response += f"，上班时间：{r.check_in_time}"
                elif hasattr(r.check_in_time, 'strftime'):
                    response += f"，上班时间：{r.check_in_time.strftime('%H:%M')}"
            response += "\n"

        return response

    def _generate_alignment_suggestion(self, alignment_level: str, employee_name: str) -> str:
        """生成适配建议.

        Args:
            alignment_level: 适配等级
            employee_name: 员工姓名

        Returns:
            建议文本
        """
        suggestions = {
            "高度适配": f"{employee_name}与当前岗位高度匹配，建议继续发挥优势，可考虑晋升或承担更重要的项目职责。",
            "基本适配": f"{employee_name}基本适应当前岗位，建议针对薄弱环节进行针对性培训，提升综合能力。",
            "需针对性提升": f"{employee_name}在某些方面存在不足，建议制定个人发展计划，加强相关技能培训。",
            "不适配": f"{employee_name}与当前岗位匹配度较低，建议评估是否需要调岗或进行岗位调整。"
        }
        return suggestions.get(alignment_level, "")

    async def _handle_department_query(
        self,
        query: str,
        db: AsyncSession,
        all_employees
    ) -> str:
        """处理部门级查询.

        Args:
            query: 用户查询
            db: 数据库会话
            all_employees: 所有员工列表

        Returns:
            回答
        """
        # 提取部门名称
        dept_name = None
        if "云生工作室" in query:
            dept_name = "云生工作室"
        elif "权益" in query or "权益运营事业部" in query:
            dept_name = "权益运营事业部"

        if not dept_name:
            return "请指定具体的部门名称，例如：'云生工作室' 或 '权益运营事业部'"

        # 获取该部门的所有员工
        dept_employees = [emp for emp in all_employees if emp.department == dept_name]

        if not dept_employees:
            return f"未找到部门: {dept_name}"

        # 检查是否是考勤相关查询
        attendance_keywords = ["考勤", "加班", "迟到", "早退", "打卡", "工时", "出勤"]
        is_attendance_query = any(keyword in query for keyword in attendance_keywords)

        # 收集部门数据
        dept_data = {
            "department": dept_name,
            "employee_count": len(dept_employees),
            "employees": []
        }

        total_salary = 0
        for emp in dept_employees:
            emp_info = {
                "name": emp.name,
                "position": emp.position,
                "salary": {},
                "attendance": {}
            }

            # 收集薪资信息
            try:
                from app.database.models import SalaryRecord
                from sqlalchemy import select
                result = await db.execute(
                    select(SalaryRecord).where(SalaryRecord.employee_id == emp.id)
                )
                salary_records = result.scalars().all()
                if salary_records:
                    latest = salary_records[-1]
                    emp_info["salary"] = {
                        "base": float(latest.base_salary) if latest.base_salary else 0,
                        "bonus": float(latest.bonus) if latest.bonus else 0,
                        "total": float(latest.net_salary) if latest.net_salary else 0
                    }
                    total_salary += emp_info["salary"]["total"]
            except:
                pass

            # 如果是考勤查询，收集考勤信息
            if is_attendance_query:
                try:
                    from app.database.models import AttendanceRecord
                    from sqlalchemy import select, func
                    from datetime import datetime, timedelta

                    # 获取近3个月的考勤数据
                    three_months_ago = datetime.now().date() - timedelta(days=90)
                    result = await db.execute(
                        select(AttendanceRecord).where(
                            AttendanceRecord.employee_id == emp.id,
                            AttendanceRecord.date >= three_months_ago
                        )
                    )
                    attendance_records = result.scalars().all()

                    if attendance_records:
                        total_days = len(attendance_records)
                        late_days = sum(1 for r in attendance_records if r.status == "迟到")
                        early_leave_days = sum(1 for r in attendance_records if r.status == "早退")
                        absent_days = sum(1 for r in attendance_records if r.status == "缺勤")

                        # 计算加班情况
                        overtime_days = sum(1 for r in attendance_records if r.overtime_hours and r.overtime_hours > 0)
                        total_overtime_hours = sum(r.overtime_hours for r in attendance_records if r.overtime_hours)

                        emp_info["attendance"] = {
                            "total_days": total_days,
                            "late_days": late_days,
                            "early_leave_days": early_leave_days,
                            "absent_days": absent_days,
                            "overtime_days": overtime_days,
                            "total_overtime_hours": round(total_overtime_hours, 1)
                        }
                except Exception as e:
                    logger.warning(f"获取员工 {emp.name} 考勤信息失败: {str(e)}")

            dept_data["employees"].append(emp_info)

        dept_data["total_monthly_salary"] = total_salary

        # 根据查询类型构建不同的提示
        if is_attendance_query:
            # 构建考勤相关的提示
            attendance_info = []
            for emp in dept_data["employees"]:
                att = emp.get("attendance", {})
                if att:
                    attendance_info.append(
                        f"{emp['name']}: 近3个月出勤{att.get('total_days', 0)}天, "
                        f"迟到{att.get('late_days', 0)}次, 早退{att.get('early_leave_days', 0)}次, "
                        f"加班{att.get('overtime_days', 0)}天({att.get('total_overtime_hours', 0)}小时)"
                    )
                else:
                    attendance_info.append(f"{emp['name']}: 暂无考勤数据")

            chat_prompt = f"""部门:{dept_name}
员工人数:{len(dept_employees)}
考勤数据:
{chr(10).join(attendance_info)}

问题:{query}
请根据以上考勤数据回答问题:"""
        else:
            # 构建精简的对话提示（薪资相关）
            chat_prompt = f"""部门:{dept_name},人数:{len(dept_employees)},月总薪资:{total_salary:.0f}元
员工:{', '.join([f"{e['name']}({e['position']},月{e['salary'].get('total',0):.0f}元)" for e in dept_data['employees']])}

问题:{query}
请简洁回答:"""

        try:
            messages = [{"role": "user", "content": chat_prompt}]
            result = await self.llm.ainvoke(messages)
            return self._clean_model_output(result.content)
        except Exception as e:
            return f"查询过程中出现错误: {str(e)}"

    async def chat_about_employee_stream(
        self,
        query: str,
        db: Optional[AsyncSession] = None
    ) -> AsyncGenerator[str, None]:
        """流式对话式查询员工信息.

        Args:
            query: 用户查询
            db: 数据库会话

        Yields:
            回答的文本片段
        """
        if not db:
            yield "需要数据库连接来查询员工信息"
            return

        # 从查询中提取员工姓名
        from app.database.crud import EmployeeCRUD
        all_employees = await EmployeeCRUD.get_all(db)
        employee_names = [emp.name for emp in all_employees]

        mentioned_employee = None
        for name in employee_names:
            if name in query:
                mentioned_employee = name
                break

        # 所有查询都使用新的智能查询架构（显示规划和执行步骤）
        try:
            async for chunk in self.intelligent_query_stream(query, db):
                yield chunk
        except Exception as e:
            yield f"\n[错误] 查询过程中出现错误: {str(e)}"

    def _clean_model_output(self, text: str) -> str:
        """清理模型输出的特殊标记.
        
        Args:
            text: 原始模型输出
            
        Returns:
            清理后的文本
        """
        # 移除Qwen模型的特殊标记
        special_tokens = ['<|im_end|>', '<|im_start|>', '<|endoftext|>']
        for token in special_tokens:
            text = text.replace(token, '')
        return text.strip()


# Singleton instance
_alignment_agent: Optional[AlignmentAgent] = None


def get_alignment_agent() -> AlignmentAgent:
    """Get or create alignment agent singleton."""
    global _alignment_agent
    if _alignment_agent is None:
        _alignment_agent = AlignmentAgent()
    return _alignment_agent
