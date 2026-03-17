"""HR Agent implementation using LangGraph."""

import json
from datetime import date
from typing import Any, Dict, List, Optional

from langchain.schema import Document
from langchain_community.chat_models import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import RAG_PROMPT, TOOL_SELECTION_PROMPT
from app.agent.state import AgentState
from app.config import get_settings
from app.database.crud import EmployeeCRUD
from app.knowledge.builder import KnowledgeBuilder


class HRAgent:
    """HR Agent for handling employee-related queries."""

    def __init__(self):
        """Initialize the HR agent."""
        self.settings = get_settings()
        self.llm = None
        self.knowledge_builder = KnowledgeBuilder()
        self.vector_store = None
        self.workflow = None
        self._init_llm()
        self._init_vector_store()
        self._build_workflow()

    def _init_llm(self):
        """Initialize the LLM client."""
        self.llm = ChatOpenAI(
            model_name=self.settings.vllm_model,
            openai_api_base=self.settings.openai_api_base,
            openai_api_key=self.settings.openai_api_key,
            temperature=0.7,
            max_tokens=1024,
        )

    def _init_vector_store(self):
        """Initialize vector store."""
        self.vector_store = self.knowledge_builder.load_vector_store()

    def _build_workflow(self):
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("tool_call", self._tool_call_node)
        workflow.add_node("generate", self._generate_node)

        # Add edges
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "analyze")
        workflow.add_conditional_edges(
            "analyze",
            self._should_call_tool,
            {
                "tool_call": "tool_call",
                "generate": "generate",
            },
        )
        workflow.add_edge("tool_call", "generate")
        workflow.add_edge("generate", END)

        self.workflow = workflow.compile()

    def _retrieve_node(self, state: AgentState) -> AgentState:
        """Retrieve relevant documents from vector store."""
        question = state["question"]

        if self.vector_store is None:
            return {**state, "documents": []}

        try:
            documents = self.knowledge_builder.search(question, k=5)
            return {**state, "documents": documents}
        except Exception as e:
            print(f"Error retrieving documents: {e}")
            return {**state, "documents": []}

    def _analyze_node(self, state: AgentState) -> AgentState:
        """Analyze the question and determine if tool calls are needed."""
        question = state["question"]

        # Use LLM to determine if tool calls are needed
        try:
            chain = TOOL_SELECTION_PROMPT | self.llm | StrOutputParser()
            result = chain.invoke({"question": question})

            # Parse JSON response
            try:
                analysis = json.loads(result)
                needs_tool = analysis.get("needs_tool", False)
                tool_calls = []

                if needs_tool:
                    tool_calls.append({
                        "tool_name": analysis.get("tool_name"),
                        "tool_args": analysis.get("tool_args", {}),
                    })

                return {
                    **state,
                    "needs_tool": needs_tool,
                    "tool_calls": tool_calls,
                }
            except json.JSONDecodeError:
                # If JSON parsing fails, assume no tool needed
                return {**state, "needs_tool": False, "tool_calls": []}

        except Exception as e:
            print(f"Error in analyze node: {e}")
            return {**state, "needs_tool": False, "tool_calls": []}

    def _should_call_tool(self, state: AgentState) -> str:
        """Determine if we should call tools or generate directly."""
        if state.get("needs_tool", False) and state.get("tool_calls"):
            return "tool_call"
        return "generate"

    def _tool_call_node(self, state: AgentState) -> AgentState:
        """Execute tool calls."""
        # Tool calls are executed externally with database session
        # This node just passes through the state
        # Actual tool execution happens in the query method
        return state

    def _generate_node(self, state: AgentState) -> AgentState:
        """Generate the final answer."""
        question = state["question"]
        documents = state.get("documents", [])
        tool_results = state.get("tool_results", [])

        # Build context from documents and tool results
        context_parts = []

        if documents:
            context_parts.append("=== 知识库信息 ===")
            for i, doc in enumerate(documents, 1):
                context_parts.append(f"[{i}] {doc.page_content}")

        if tool_results:
            context_parts.append("\n=== 数据库查询结果 ===")
            for result in tool_results:
                context_parts.append(result)

        context = "\n".join(context_parts) if context_parts else "无相关信息"

        # Generate answer
        try:
            chain = RAG_PROMPT | self.llm | StrOutputParser()
            answer = chain.invoke({
                "context": context,
                "question": question,
                "current_date": str(date.today()),
            })

            return {**state, "answer": answer}

        except Exception as e:
            print(f"Error generating answer: {e}")
            return {**state, "answer": "抱歉，生成回答时出现错误，请稍后再试。"}

    async def execute_tools(
        self, state: AgentState, db: Optional[AsyncSession] = None
    ) -> List[str]:
        """Execute tool calls with database session."""
        tool_results = []
        tool_calls = state.get("tool_calls", [])

        if not db or not tool_calls:
            return tool_results

        for call in tool_calls:
            tool_name = call.get("tool_name")
            tool_args = call.get("tool_args", {})

            try:
                if tool_name == "query_employee_info":
                    name = tool_args.get("name", "")
                    if name:
                        result = await self._query_employee(db, name)
                        tool_results.append(result)

                elif tool_name == "get_contract_alerts":
                    days = tool_args.get("days", self.settings.contract_alert_days)
                    result = await self._get_contract_alerts(db, days)
                    tool_results.append(result)

                elif tool_name == "get_low_performance":
                    threshold = tool_args.get("threshold", self.settings.performance_threshold)
                    result = await self._get_low_performance(db, threshold)
                    tool_results.append(result)

                elif tool_name == "query_policy":
                    keyword = tool_args.get("keyword", "")
                    result = await self._query_policy(keyword)
                    tool_results.append(result)

            except Exception as e:
                tool_results.append(f"工具执行错误 ({tool_name}): {str(e)}")

        return tool_results

    async def _query_employee(self, db: AsyncSession, name: str) -> str:
        """Query employee information."""
        employee = await EmployeeCRUD.get_by_name(db, name)

        if not employee:
            return f"未找到员工: {name}"

        info = f"""员工信息:
姓名: {employee.name}
部门: {employee.department or '未知'}
职位: {employee.position or '未知'}
入职日期: {employee.hire_date or '未知'}
绩效分数: {employee.performance_score or '未评分'}
合同到期: {employee.contract_end_date or '未知'}
电话: {employee.phone or '未登记'}
邮箱: {employee.email or '未登记'}
"""
        return info

    async def _get_contract_alerts(self, db: AsyncSession, days: int) -> str:
        """Get contract expiration alerts."""
        employees = await EmployeeCRUD.get_contract_expiring(db, days)

        if not employees:
            return f"未来 {days} 天内没有合同到期的员工"

        result = f"未来 {days} 天内合同到期的员工:\n\n"
        for emp in employees:
            result += f"- {emp.name} ({emp.department or '未知部门'}): 合同到期 {emp.contract_end_date}\n"

        return result

    async def _get_low_performance(self, db: AsyncSession, threshold: float) -> str:
        """Get low performance employees."""
        employees = await EmployeeCRUD.get_low_performance(db, threshold)

        if not employees:
            return f"没有绩效分数低于 {threshold} 分的员工"

        result = f"绩效分数低于 {threshold} 分的员工:\n\n"
        for emp in employees:
            result += f"- {emp.name} ({emp.department or '未知部门'}): {emp.performance_score}分\n"

        return result

    async def _query_policy(self, keyword: str) -> str:
        """Query company policies."""
        if self.vector_store is None:
            return "知识库未初始化，无法查询规章制度"

        try:
            documents = self.knowledge_builder.search(f"规章制度 {keyword}", k=3)

            if not documents:
                return f"未找到与 '{keyword}' 相关的规章制度"

            result = f"关于 '{keyword}' 的规章制度:\n\n"
            for i, doc in enumerate(documents, 1):
                result += f"[{i}] {doc.page_content[:500]}...\n\n"

            return result

        except Exception as e:
            return f"查询规章制度时出错: {str(e)}"

    async def query(self, question: str, db: Optional[AsyncSession] = None) -> str:
        """Process a query and return the answer."""
        # Initialize state
        initial_state: AgentState = {
            "question": question,
            "documents": [],
            "tool_calls": [],
            "tool_results": [],
            "answer": None,
            "needs_tool": False,
        }

        # Run workflow up to tool call node
        state = initial_state

        # Manual execution of workflow steps
        state = self._retrieve_node(state)
        state = self._analyze_node(state)

        # Execute tools if needed
        if state.get("needs_tool") and db:
            tool_results = await self.execute_tools(state, db)
            state = {**state, "tool_results": tool_results}

        # Generate final answer
        state = self._generate_node(state)

        return state.get("answer", "抱歉，无法生成回答。")


# Singleton instance
_hr_agent: Optional[HRAgent] = None


def get_hr_agent() -> HRAgent:
    """Get or create HR agent singleton."""
    global _hr_agent
    if _hr_agent is None:
        _hr_agent = HRAgent()
    return _hr_agent
