from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.llm import LLM
from app.logger import logger
from app.schema import AgentState, Memory, Message


class BaseAgent(BaseModel, ABC):
    """Abstract base class for managing agent state and execution.

    Provides foundational functionality for state transitions, memory management,
    and a step-based execution loop. Subclasses must implement the `step` method.
    """

    # Core attributes
    name: str = Field(..., description="Unique name of the agent")
    description: Optional[str] = Field(None, description="Optional agent description")

    # Prompts                                     定义系统提示词和下一步提示词
    system_prompt: Optional[str] = Field(          #用于初始化LLM的系统级指令。
        None, description="System-level instruction prompt"
    )
    next_step_prompt: Optional[str] = Field(       #用于指导下一步动作。
        None, description="Prompt for determining next action"
    )

    # Dependencies                              定义智能体的依赖
    llm: LLM = Field(default_factory=LLM, description="Language model instance")  #语言模型实例
    memory: Memory = Field(default_factory=Memory, description="Agent's memory store")#记忆存储
    state: AgentState = Field(                                                #状态
        default=AgentState.IDLE, description="Current agent state"
    )

    # Execution control
    max_steps: int = Field(default=10, description="Maximum steps before termination")#最大执行步数
    current_step: int = Field(default=0, description="Current step in execution")   #当前执行步数。

    duplicate_threshold: int = 2

    class Config:
        arbitrary_types_allowed = True         #允许任意类型字段
        extra = "allow"  # Allow extra fields for flexibility in subclasses允许子类添加额外字段。

    @model_validator(mode="after")
    def initialize_agent(self) -> "BaseAgent": #初始化智能体依赖。
        """Initialize agent with default settings if not provided."""
        if self.llm is None or not isinstance(self.llm, LLM):
            self.llm = LLM(config_name=self.name.lower())
        if not isinstance(self.memory, Memory):
            self.memory = Memory()
        return self

    @asynccontextmanager
    async def state_context(self, new_state: AgentState):  #确保状态切换安全
        """Context manager for safe agent state transitions.

        Args:
            new_state: The state to transition to during the context.

        Yields:
            None: Allows execution within the new state.

        Raises:
            ValueError: If the new_state is invalid.
        """
        if not isinstance(new_state, AgentState):
            raise ValueError(f"Invalid state: {new_state}")

        previous_state = self.state
        self.state = new_state
        try:
            yield
        except Exception as e:
            self.state = AgentState.ERROR  # Transition to ERROR on failure
            raise e
        finally:
            self.state = previous_state  # Revert to previous state

    def update_memory(         #向记忆中添加消息
        self,
        role: Literal["user", "system", "assistant", "tool"],
        content: str,
        **kwargs,
    ) -> None:
        """Add a message to the agent's memory.

        Args:
            role: The role of the message sender (user, system, assistant, tool).
            content: The message content.
            **kwargs: Additional arguments (e.g., tool_call_id for tool messages).

        Raises:
            ValueError: If the role is unsupported.
        """
        message_map = {
            "user": Message.user_message,
            "system": Message.system_message,
            "assistant": Message.assistant_message,
            "tool": lambda content, **kw: Message.tool_message(content, **kw),
        }

        if role not in message_map:
            raise ValueError(f"Unsupported message role: {role}")

        msg_factory = message_map[role]
        msg = msg_factory(content, **kwargs) if role == "tool" else msg_factory(content)
        self.memory.add_message(msg)

    async def run(self, request: Optional[str] = None) -> str:#向记忆中添加消息
        """Execute the agent's main loop asynchronously.

        Args:
            request: Optional initial user request to process.

        Returns:
            A string summarizing the execution results.

        Raises:
            RuntimeError: If the agent is not in IDLE state at start.
        """
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"Cannot run agent from state: {self.state}")

        if request:
            self.update_memory("user", request)

        results: List[str] = []
        async with self.state_context(AgentState.RUNNING):
            while (
                self.current_step < self.max_steps and self.state != AgentState.FINISHED
            ):
                self.current_step += 1
                logger.info(f"Executing step {self.current_step}/{self.max_steps}")
                step_result = await self.step()

                # Check for stuck state
                if self.is_stuck():
                    self.handle_stuck_state()

                results.append(f"Step {self.current_step}: {step_result}")

            if self.current_step >= self.max_steps:
                self.current_step = 0  # setting back to 0 when reached max steps
                self.state = AgentState.IDLE  # setting the status
                results.append(f"Terminated: Reached max steps ({self.max_steps})")

        return "\n".join(results) if results else "No steps executed"

    @abstractmethod
    async def step(self) -> str:#定义智能体的单步执行逻辑
        """Execute a single step in the agent's workflow.

        Must be implemented by subclasses to define specific behavior.
        """
#卡死检测和处理，通过检测重复消息判断是否卡死。添加提示词引导模型改变策略。
    def handle_stuck_state(self):
        """Handle stuck state by adding a prompt to change strategy"""
        stuck_prompt = "\
        Observed duplicate responses. Consider new strategies and avoid repeating ineffective paths already attempted."
        self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
        logger.warning(f"Agent detected stuck state. Added prompt: {stuck_prompt}")

    def is_stuck(self) -> bool:
        """Check if the agent is stuck in a loop by detecting duplicate content"""
        if len(self.memory.messages) < 2:
            return False

        last_message = self.memory.messages[-1]
        if not last_message.content:
            return False

        # Count identical content occurrences
        duplicate_count = sum(
            1
            for msg in reversed(self.memory.messages[:-1])
            if msg.role == "assistant" and msg.content == last_message.content
        )

        return duplicate_count >= self.duplicate_threshold

    @property
    def messages(self) -> List[Message]:#能提供记忆的读写接口，通过属性封装记忆存储
        """Retrieve a list of messages from the agent's memory."""
        return self.memory.messages

    @messages.setter
    def messages(self, value: List[Message]):
        """Set the list of messages in the agent's memory."""
        self.memory.messages = value
