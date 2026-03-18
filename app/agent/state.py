"""Agent state definitions for LangGraph."""

from typing import Annotated, List, Optional

from langchain.schema import Document
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """State for the HR agent workflow."""

    question: str
    documents: Annotated[List[Document], "Retrieved documents"]
    tool_calls: Annotated[List[dict], "Tool calls to execute"]
    tool_results: Annotated[List[str], "Tool execution results"]
    answer: Annotated[Optional[str], "Final answer"]
    needs_tool: Annotated[bool, "Whether tool calls are needed"]
