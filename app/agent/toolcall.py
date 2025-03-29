# toolcall.py
import json
import logging
import asyncio
import traceback
from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator
from websockets import WebSocketServerProtocol

from app.agent.react import ReActAgent
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import AgentState, Message, ToolCall
from app.tool import CreateChatCompletion, Terminate, ToolCollection

TOOL_CALL_REQUIRED = "Tool calls required but none provided"

class ToolCallAgent(ReActAgent):
    """Base agent class for handling tool/function calls with enhanced abstraction"""

    name: str = "toolcall"
    description: str = "An agent that can execute tool calls with enhanced safety"

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            CreateChatCompletion(name="chat_completion"),
            Terminate(name="termination_tool")
        )
    )
    tool_choices: Literal["none", "auto"] = "auto"
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    tool_calls: List[ToolCall] = Field(default_factory=list)
    step_execution_tracker: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    current_step_index: Optional[int] = None
    max_steps: int = 30
    start_time: Optional[float] = None
    estimated_duration: float = 60.0

    @model_validator(mode="after")
    def initialize_tools(cls, values):
        instance = values.get('instance') or cls
        instance.available_tools.verify_tools()
        return instance

    async def think(self) -> bool:
        try:
            if self.next_step_prompt:
                user_msg = Message.user_message(self.next_step_prompt)
                self.messages.append(user_msg)

            tool_choice_param = (
                {"name": self.tool_choices}
                if self.tool_choices and self.tool_choices != "none"
                else None
            )

            response = await self.llm.ask_tool(
                messages=self.messages,
                system_msgs=[Message.system_message(self.system_prompt)]
                if self.system_prompt else None,
                tools=self.available_tools.to_params(),
                tool_choice=tool_choice_param,
            )
            
            self.tool_calls = response.tool_calls or []
            logger.info(
                f"[THINK] Selected tools: {len(self.tool_calls)} | "
                f"Content length: {len(response.content or '')}"
            )

            if self.tool_choices == "none":
                if response.content:
                    self.memory.add_message(Message.assistant_message(response.content))
                return bool(response.content)

            assistant_msg = (
                Message.from_tool_calls(
                    content=response.content, tool_calls=self.tool_calls
                )
                if self.tool_calls else Message.assistant_message(response.content)
            )
            self.memory.add_message(assistant_msg)
            return bool(self.tool_calls)

        except Exception as e:
            logger.error(f"[THINK_ERROR] {str(e)} | Trace: {traceback.format_exc()}")
            self.memory.add_message(
                Message.assistant_message(
                    f"系统错误: {str(e)}"
                )
            )
            return False
    def get(self, key: str) -> Any:
        return getattr(self, key, None)
    async def act(self) -> str:
        if not self.tool_calls:
            return self.messages[-1].content or "No executable commands"

        results = []
        for command in self.tool_calls:
            try:
                result = await self.execute_tool(command)
                results.append(result)
                logger.info(
                    f"[ACT] Tool '{command.function.name}' executed | "
                    f"Result: {result[:100]}..."
                )
            except Exception as e:
                logger.error(
                    f"[ACT_ERROR] Tool '{command.function.name}' failed | "
                    f"Error: {str(e)}"
                )
                results.append(f"Error: {str(e)}")

        return "".join(results)

    async def execute_tool(self, command: ToolCall) -> str:
        if not command or not command.function:
            return "Error: Invalid command structure"

        tool_name = command.function.name
        if tool_name not in self.available_tools.tool_map:
            return f"Error: Tool '{tool_name}' not registered"

        try:
            args = json.loads(command.function.arguments or "{}")
            result = await self.available_tools.execute(
                name=tool_name,
                tool_input=args
            )
            return self._format_tool_output(tool_name, result)
        except Exception as e:
            logger.error(f"[TOOL_EXECUTE_ERROR] {tool_name} failed | Args: {args}")
            return f"Error: {str(e)}"

    def _parse_arguments(self, arg_str: str) -> Dict[str, Any]:
        try:
            return json.loads(arg_str or "{}")
        except json.JSONDecodeError:
            logger.warning(f"[ARG_PARSE_ERROR] Invalid JSON: {arg_str}")
            return {}

    def _format_tool_output(self, tool_name: str, result: Any) -> str:
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)

    async def _handle_special_tool(self, name: str, result: Any):
        if name == "termination_tool":
            self.state = AgentState.FINISHED
            logger.info("[SPECIAL_TOOL] Termination tool executed successfully")

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        return kwargs.get("completion_code") == 0

    async def get_plan_status(self) -> str:
        if not self.tool_calls:
            return "No active plan"
        last_call = self.tool_calls[-1]
        return "Completed" if last_call.status == "completed" else "In Progress"