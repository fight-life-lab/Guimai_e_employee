"""人岗适配评估Agent - 基于国央企员工人岗适配管理体系."""

import json
from datetime import date
from typing import Any, Dict, List, Optional, AsyncGenerator

from langchain.schema import Document
from langchain_community.chat_models import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.config import get_settings
from app.database.crud import EmployeeCRUD
from app.knowledge.builder import KnowledgeBuilder


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
    "政治画像": {
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
            max_tokens=1024,  # 减少输出token数以适应上下文限制
            streaming=True,  # 启用流式输出
        )

    def _init_vector_store(self):
        """Initialize vector store."""
        self.vector_store = self.knowledge_builder.load_vector_store()

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
            
            # 5. 解析分析结果
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
            async for chunk in chain.astream({}):
                yield chunk.content
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
        }

        # 获取合同信息
        if hasattr(employee, 'contracts') and employee.contracts:
            for contract in employee.contracts:
                data["contracts"].append({
                    "type": contract.contract_type,
                    "end_date": str(contract.end_date) if contract.end_date else None,
                    "status": contract.status,
                })

        return data

    def _build_alignment_prompt(self, employee_data: Dict[str, Any]) -> PromptTemplate:
        """构建人岗适配分析提示.
        
        Args:
            employee_data: 员工数据
            
        Returns:
            提示模板
        """
        template = """作为HR分析师，请评估员工人岗适配度。

评估维度(权重):
1. 能力画像(40%):专业/管理/创新/学习/适应能力
2. 政治画像(25%):政治立场/廉洁自律/组织观念/群众基础
3. 时间维度(15%):稳定性/响应能力/持续性
4. 绩效表现(20%):绩效分数/趋势/目标达成

员工数据:{employee_data}

请输出:
1. 综合评分(0-100)和适配等级(高度/基本/不匹配)
2. 各维度评分和评价
3. 优势分析
4. 风险预警
5. 发展建议
6. 岗位适配结论"""

        return PromptTemplate(
            template=template,
            input_variables=[],
            partial_variables={"employee_data": json.dumps(employee_data, ensure_ascii=False)}
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
        dimension_pattern = r'[-\*]\s*(能力画像|政治画像|时间维度|绩效表现)[:：]\s*(\d+)'
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
        
        if not mentioned_employee:
            return "请提供员工姓名，例如：'石京京是哪个学校的'"

        # 获取员工信息
        employee = await EmployeeCRUD.get_by_name(db, mentioned_employee)
        if not employee:
            return f"未找到员工: {mentioned_employee}"

        # 收集员工数据
        employee_data = await self._gather_employee_data(db, employee)

        # 构建对话提示
        chat_prompt = f"""你是人力资源助手，根据以下员工数据回答用户问题。

员工数据：{json.dumps(employee_data, ensure_ascii=False)}

用户问题：{query}

请直接回答用户的问题，简洁明了。如果数据中不包含相关信息，请说明。"""

        try:
            from langchain_core.prompts import PromptTemplate
            from langchain_core.output_parsers import StrOutputParser
            
            prompt = PromptTemplate(
                template=chat_prompt,
                input_variables=[]
            )
            chain = prompt | self.llm | StrOutputParser()
            result = await chain.ainvoke({})
            return result
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
        
        if not mentioned_employee:
            yield "请提供员工姓名，例如：'石京京是哪个学校的'"
            return

        employee = await EmployeeCRUD.get_by_name(db, mentioned_employee)
        if not employee:
            yield f"未找到员工: {mentioned_employee}"
            return

        employee_data = await self._gather_employee_data(db, employee)

        chat_prompt = f"""你是人力资源助手，根据以下员工数据回答用户问题。

员工数据：{json.dumps(employee_data, ensure_ascii=False)}

用户问题：{query}

请直接回答用户的问题，简洁明了。"""

        try:
            from langchain_core.prompts import PromptTemplate
            prompt = PromptTemplate(
                template=chat_prompt,
                input_variables=[]
            )
            chain = prompt | self.llm
            async for chunk in chain.astream({}):
                yield chunk.content
        except Exception as e:
            yield f"\n[错误] 查询过程中出现错误: {str(e)}"


# Singleton instance
_alignment_agent: Optional[AlignmentAgent] = None


def get_alignment_agent() -> AlignmentAgent:
    """Get or create alignment agent singleton."""
    global _alignment_agent
    if _alignment_agent is None:
        _alignment_agent = AlignmentAgent()
    return _alignment_agent
