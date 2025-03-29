import json
import time
import asyncio
import traceback
from typing import Dict, List, Literal, Optional, Union

from pydantic import Field, model_validator
from websockets import WebSocketServerProtocol

from app.agent.toolcall import ToolCallAgent
from app.logger import logger
from app.prompt.planning import NEXT_STEP_PROMPT, PLANNING_SYSTEM_PROMPT
from app.schema import Message, ToolCall
from app.tool import PlanningTool, Terminate, ToolCollection

class PlanningAgent(ToolCallAgent):
    """
    Enhanced Planning Agent with direct input passthrough
    """

    name: str = "planning"
    description: str = "Planning agent with raw input support"

    system_prompt: str = PLANNING_SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(PlanningTool(), Terminate())
    )
    tool_choices: Literal["none", "auto"] = "auto"
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    tool_calls: List[ToolCall] = Field(default_factory=list)
    active_plan_id: Optional[str] = Field(default=None)

    # Execution tracking
    step_execution_tracker: Dict[str, Dict] = Field(default_factory=dict)
    current_step_index: Optional[int] = None
    max_steps: int = 20
    start_time: Optional[float] = None
    estimated_duration: float = 60.0

    @model_validator(mode="after")
    def initialize_plan_and_verify_tools(self) -> "PlanningAgent":
        self.active_plan_id = f"plan_{int(time.time())}"
        if "planning" not in self.available_tools.tool_map:
            self.available_tools.add_tool(PlanningTool())
        return self

    async def think(self) -> bool:
        try:
            if self.active_plan_id:
                prompt = (
                    f"CURRENT PLAN STATUS:"
                    f"{await self.get_plan()}"
                    f"{self.next_step_prompt}"
                )
            else:
                prompt = self.next_step_prompt

            self.messages.append(Message.user_message(prompt))
            self.current_step_index = await self._get_current_step_index()

            result = await super().think()

            if result and self.tool_calls:
                latest_tool_call = self.tool_calls[0]
                if (
                    latest_tool_call.function.name != "planning"
                    and latest_tool_call.function.name not in self.special_tool_names
                    and self.current_step_index is not None
                ):
                    self.step_execution_tracker[latest_tool_call.id] = {
                        "step_index": self.current_step_index,
                        "tool_name": latest_tool_call.function.name,
                        "status": "pending",
                    }
                    await self._notify_frontend({
                        "type": "tool_execution_start",
                        "tool": latest_tool_call.function.name,
                        "step": self.current_step_index
                    })

            return result
        except Exception as e:
            await self._handle_error("THINK_ERROR", str(e))
            return False

    async def act(self) -> str:
        try:
            result = await super().act()
            if self.tool_calls:
                latest_call = self.tool_calls[0]
                
                if latest_call.id in self.step_execution_tracker:
                    self.step_execution_tracker[latest_call.id]["status"] = "completed"
                    self.step_execution_tracker[latest_call.id]["result"] = result

                    if (
                        latest_call.function.name != "planning"
                        and latest_call.function.name not in self.special_tool_names
                    ):
                        await self.update_plan_status(latest_call.id)
                        await self._notify_frontend({
                            "type": "tool_execution",
                            "tool": latest_call.function.name,
                            "status": "completed",
                            "result": result,
                            "step": self.current_step_index
                        })

            return result
        except Exception as e:
            await self._handle_error("ACTION_ERROR", str(e))
            return ""

    async def get_plan(self) -> str:
        try:
            if not self.active_plan_id:
                return "No active plan. Please create a plan first."

            result = await self.available_tools.execute(
                name="planning",
                tool_input={"command": "get", "plan_id": self.active_plan_id},
            )
            return result.output or "No plan data"
        except Exception as e:
            error_msg = f"获取计划失败: {str(e)}"
            await self._handle_error("GET_PLAN_ERROR", error_msg)
            return error_msg

    async def run(self, request: Optional[str] = None) -> str:
        try:
            self.start_time = time.time()
            if request:
                await self.create_initial_plan(request)
            return await super().run()
        except asyncio.CancelledError:
            await self._notify_frontend({
                "type": "error",
                "error_code": "CANCELLED",
                "message": "任务已被用户取消"
            })
            raise
        except Exception as e:
            await self._handle_error("RUN_ERROR", str(e))
            return f"执行失败: {str(e)}"

    async def update_plan_status(self, tool_call_id: str) -> None:
        try:
            if not self.active_plan_id:
                return

            if tool_call_id not in self.step_execution_tracker:
                logger.warning(f"No step tracking for tool call {tool_call_id}")
                return

            tracker = self.step_execution_tracker[tool_call_id]
            if tracker["status"] != "completed":
                logger.warning(f"Tool call {tool_call_id} not completed")
                return

            step_index = tracker["step_index"]
            await self.available_tools.execute(
                name="planning",
                tool_input={
                    "command": "mark_step",
                    "plan_id": self.active_plan_id,
                    "step_index": step_index,
                    "step_status": "completed",
                },
            )

            await self._notify_frontend({
                "type": "step_completed",
                "index": step_index,
                "progress": self._calculate_progress()
            })

        except Exception as e:
            await self._handle_error("UPDATE_STATUS_ERROR", str(e))

    async def _get_current_step_index(self) -> Optional[int]:
        try:
            if not self.active_plan_id:
                return None

            plan = await self.get_plan()
            plan_lines = plan.splitlines()
            steps_index = -1

            if "[ ]" in plan or "[→]" in plan:
                steps_index = plan.find("Steps:")
                if steps_index == -1:
                    return None

                steps = plan[steps_index:].split("")
                for i, line in enumerate(steps):
                    if "[ ]" in line or "[→]" in line:
                        return i

            return None
        except Exception as e:
            await self._handle_error("GET_STEP_ERROR", str(e))
            return None

    async def create_initial_plan(self, request: str) -> None:
        try:
            await self._notify_frontend({
                "type": "plan_creation",
                "status": "started",
                "request": request,
                "plan_id": self.active_plan_id
            })

            # 直接传递原始请求，不做任何结构化处理
            messages = [
                Message.user_message(
                    f"直接处理原始请求: {request}"
                )
            ]
            self.memory.add_messages(messages)
            
            # 关键修复：保持工具参数原样传递
            tools_params = self.available_tools.to_params()
            response = await self.llm.ask_tool(
                messages=messages,
                system_msgs=[Message.system_message(self.system_prompt)],
                tools=tools_params,
                tool_choice="required",
            )
            assistant_msg = Message.from_tool_calls(
                content=response.content,
                tool_calls=getattr(response, "tool_calls", [])
            )
            self.memory.add_message(assistant_msg)

            # 安全处理响应数据
            response_data = {
                "steps": getattr(response, "steps", []),
                "plan_steps": getattr(response, "plan_steps", []),
                "output": response.output
            }

            # 记录原始响应用于调试
            logger.debug(f"原始工具响应: {json.dumps(response_data, indent=2)}")

            if any(step for step in response_data["steps"]):
                await self._notify_frontend({
                    "type": "plan_draft",
                    "content": response.content,
                    "steps": len(response_data["steps"])
                })
            else:
                await self._handle_error("CREATE_PLAN_ERROR", "未生成有效步骤")

        except Exception as e:
            await self._handle_error("CREATE_PLAN_ERROR", f"{str(e)}{traceback.format_exc()}")

    def _calculate_progress(self) -> float:
        """计算执行进度"""
        if not self.start_time:
            return 0.0
        elapsed = time.time() - self.start_time
        return min(elapsed / self.estimated_duration, 1.0) if self.estimated_duration else 0.0

    async def _notify_frontend(self, message: dict):
        """统一消息推送接口"""
        if self.websocket and self.websocket.open:
            try:
                await self.websocket.send(json.dumps({
            **message,
                    "plan_id": self.active_plan_id,
                    "timestamp": time.time()
                }))
            except Exception as e:
                logger.error(f"消息推送失败: {str(e)}")
                await self._handle_error("NOTIFICATION_FAILED", str(e))

    async def _handle_error(self, error_code: str, message: str):
        """统一错误处理"""
        logger.error(f"[{error_code}] {message}")
        await self._notify_frontend({
            "type": "error",
            "error_code": error_code,
            "message": message,
            "traceback": traceback.format_exc()
        })

async def main():
    agent = PlanningAgent(
        available_tools=ToolCollection(
            PlanningTool(), 
            Terminate()
        )
    )
    result = await agent.run("Help me plan a trip to the moon")
    print(result)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        exit(1)