"""
通用LLM客户端 - 支持本地vLLM和远程大模型API
"""

import json
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    通用LLM客户端
    支持:
    1. 本地vLLM部署 (默认)
    2. 远程大模型API (用于处理长文本)
    """

    def __init__(self):
        self.settings = get_settings()
        self.local_client = None
        self.remote_client = None
        self._init_clients()

    def _init_clients(self):
        """初始化LLM客户端"""
        # 初始化本地vLLM客户端
        try:
            from openai import AsyncOpenAI
            self.local_client = AsyncOpenAI(
                base_url=self.settings.openai_api_base,
                api_key=self.settings.openai_api_key,
            )
            logger.info(f"[LLMClient] 本地vLLM客户端初始化成功: {self.settings.openai_api_base}")
        except Exception as e:
            logger.error(f"[LLMClient] 本地vLLM客户端初始化失败: {e}")
            self.local_client = None

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        use_remote: bool = False,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用大模型进行对话

        Args:
            messages: 消息列表
            model: 模型名称 (默认使用配置中的模型)
            temperature: 温度参数
            max_tokens: 最大生成token数
            use_remote: 是否使用远程大模型 (用于处理长文本)
            stream: 是否流式输出
            **kwargs: 其他参数

        Returns:
            模型响应结果
        """
        if use_remote:
            return await self._call_remote_api(
                messages=messages,
                model=model or "Qwen/Qwen3-235B-A22B-Instruct-2507",
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs
            )
        else:
            return await self._call_local_vllm(
                messages=messages,
                model=model or self.settings.vllm_model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs
            )

    async def _call_local_vllm(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """调用本地vLLM服务"""
        if not self.local_client:
            raise RuntimeError("本地vLLM客户端未初始化")

        try:
            response = await self.local_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs
            )

            if stream:
                return {"stream": response, "type": "local"}

            content = response.choices[0].message.content
            return {
                "content": content,
                "model": model,
                "usage": response.usage,
                "type": "local"
            }

        except Exception as e:
            logger.error(f"[LLMClient] 本地vLLM调用失败: {e}")
            raise

    async def _call_remote_api(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用远程大模型API
        默认使用配置中的 remote_llm_url
        """
        # 远程API配置
        remote_url = self.settings.remote_llm_url
        remote_api_key = self.settings.remote_llm_api_key

        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {remote_api_key}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        payload = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': stream
        }
        # 添加其他参数
        payload.update(kwargs)

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    remote_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

                if stream:
                    return {"stream": result, "type": "remote"}

                content = result['choices'][0]['message']['content']
                return {
                    "content": content,
                    "model": model,
                    "usage": result.get('usage'),
                    "type": "remote"
                }

        except Exception as e:
            logger.error(f"[LLMClient] 远程API调用失败: {e}")
            raise

    async def generate_outline(
        self,
        content: str,
        use_remote: bool = True,
        **kwargs
    ) -> List[Dict]:
        """
        根据文章内容生成结构化大纲

        Args:
            content: 文章内容
            use_remote: 是否使用远程大模型 (推荐用于长文本)
            **kwargs: 其他参数

        Returns:
            大纲JSON数组
        """
        system_prompt = """你需要作为专业的文本结构化分析师，根据提供的文章内容，生成逻辑清晰、层级分明的大纲列表。

请严格遵循以下要求:

### 核心规则
1. 大纲层级:支持3-4级嵌套(以3级为宜),允许各分支层级不同 （例如部分分支到3级，部分到4级，根据文章逻辑自然划分),大纲前要加上序号，格式为"1.1 大纲标题"
2. 内容匹配:大纲需完整覆盖文章核心观点、关键论据、重要案例/数据，不遗漏核心信息，不添加文章未提及的内容
3. 逻辑结构:遵循"总-分"或"总-分-总"逻辑，一级大纲对应文章核心主题/章节，二级对应核心分论点/小节，三级对应具体论据/方法，四级对应细节补充/案例拆解
4. 表述规范:每个大纲条目简洁精炼 （10-30字)，使用名词短语或动宾结构，避免冗长句子；同一层级表述风格一致
5. 格式要求:以JSON格式输出，字段说明如下:
   - "title":大纲标题
   - "children":子大纲数组 （仅当有下一级时存在，否则为空数组[]，结构同父级)

### 输出示例
[{
  "title": "1 RAG实践指南",
  "children": [
    {
      "title": "1.1 核心原理",
      "children": [
        { "title": "1.1.1 检索逻辑", "children": [] },
        { "title": "1.1.2 生成逻辑", "children": [] }
      ]
    },
    {
      "title": "1.2 技术栈选型",
      "children": []
    }
  ]
}]

### 任务要求
1. 先通读全文，提炼文章核心主题和逻辑结构
2. 按上述规则生成大纲，确保层级合理、内容完整、表述简洁
3. 严格遵守JSON格式规范，避免语法错误 （引号、逗号、括号需匹配)
4. 无需额外解释，仅输出JSON结果"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"### 文章内容\n\n{content}"}
        ]

        try:
            result = await self.chat_completion(
                messages=messages,
                use_remote=use_remote,
                temperature=0.3,
                max_tokens=4096,
                **kwargs
            )

            content = result.get("content", "")
            # 清理可能的特殊标记
            content = content.replace("<|im_end|>", "").replace("<|im_start|>", "").replace("<|endoftext|>", "").strip()

            # 提取JSON
            outline = self._extract_json(content)
            return outline if isinstance(outline, list) else []

        except Exception as e:
            logger.error(f"[LLMClient] 生成大纲失败: {e}")
            return []

    def _extract_json(self, content: str) -> Any:
        """从文本中提取JSON"""
        import re

        # 清理内容
        cleaned = content.strip()

        # 尝试直接解析
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 匹配 ```json ... ``` 格式
        json_match = re.search(r'```json\s*(.*?)\s*```', cleaned, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 匹配 ``` ... ``` 格式
        json_match = re.search(r'```\s*(.*?)\s*```', cleaned, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试匹配最外层的大括号/中括号
        def find_matching_bracket(text: str, start_char: str, end_char: str) -> str:
            stack = []
            start = -1
            for i, char in enumerate(text):
                if char == start_char:
                    if not stack:
                        start = i
                    stack.append(char)
                elif char == end_char:
                    if stack:
                        stack.pop()
                        if not stack:
                            return text[start:i+1]
            return ""

        # 先尝试匹配大括号 (JSON对象) - 优先匹配对象
        json_str = find_matching_bracket(cleaned, '{', '}')
        if json_str:
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 再尝试匹配中括号 (JSON数组)
        json_str = find_matching_bracket(cleaned, '[', ']')
        if json_str:
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 尝试修复常见的JSON格式问题
        # 1. 去除尾部逗号
        cleaned_fixed = re.sub(r',(\s*[}\]])', r'\1', cleaned)
        # 2. 修复单引号
        cleaned_fixed = cleaned_fixed.replace("'", '"')

        try:
            return json.loads(cleaned_fixed)
        except json.JSONDecodeError:
            pass

        logger.warning(f"[LLMClient] 无法从响应中提取JSON: {cleaned[:500]}")
        return {}

    async def summarize_text(
        self,
        content: str,
        max_length: int = 500,
        use_remote: bool = True,
        **kwargs
    ) -> str:
        """
        对长文本进行摘要

        Args:
            content: 需要摘要的文本
            max_length: 摘要最大长度
            use_remote: 是否使用远程大模型
            **kwargs: 其他参数

        Returns:
            摘要文本
        """
        system_prompt = f"你是一个专业的文本摘要专家。请将以下内容浓缩为不超过{max_length}字的摘要，保留核心要点。"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ]

        try:
            result = await self.chat_completion(
                messages=messages,
                use_remote=use_remote,
                temperature=0.3,
                max_tokens=max_length * 2,
                **kwargs
            )

            return result.get("content", "").strip()

        except Exception as e:
            logger.error(f"[LLMClient] 文本摘要失败: {e}")
            return ""


# 全局LLM客户端实例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取LLM客户端单例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
