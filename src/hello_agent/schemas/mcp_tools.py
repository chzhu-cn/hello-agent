"""E05：复用现有参数与结果模型，声明 MCP 工具。"""

from mcp.types import Tool
from openai.types.chat import ChatCompletionFunctionToolParam
from pydantic import JsonValue, TypeAdapter

from hello_agent.schemas.tools import AddArguments, AddResult


MCP_ADD_TOOL = Tool(
    name="add",
    description="计算两个数字的和。使用浮点运算，不适用于精确财务计算。",
    inputSchema=AddArguments.model_json_schema(),
    outputSchema=AddResult.model_json_schema(),
)

MCP_ARGUMENTS = TypeAdapter(dict[str, JsonValue])


def model_tool(tool: Tool) -> ChatCompletionFunctionToolParam:
    """把发现的 MCP 声明转换为模型 API 的工具声明。"""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }
