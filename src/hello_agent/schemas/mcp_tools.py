"""E05：复用现有参数与结果模型，声明 MCP 工具。"""

from mcp.types import Tool
from openai.types.chat import ChatCompletionFunctionToolParam
from pydantic import BaseModel, JsonValue, TypeAdapter

from hello_agent.schemas.tools import AddArguments, AddResult


MCP_ADD_TOOL = Tool(
    name="add",
    description="计算两个数字的和。使用浮点运算，不适用于精确财务计算。",
    inputSchema=AddArguments.model_json_schema(),
    outputSchema=AddResult.model_json_schema(),
)

MCP_ARGUMENTS = TypeAdapter(dict[str, JsonValue])


class MCPTool(BaseModel):
    """包装 MCP 工具，并提供模型 API 所需的声明。"""

    tool: Tool

    def model_tool(self) -> ChatCompletionFunctionToolParam:
        return {
            "type": "function",
            "function": {
                "name": self.tool.name,
                "description": self.tool.description or "",
                "parameters": self.tool.inputSchema,
            },
        }
