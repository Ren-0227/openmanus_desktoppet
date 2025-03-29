#定义了两个关键的提示字符串，用于指导一个智能代理（Agent）在任务执行过程中的行为：

SYSTEM_PROMPT = "You are an agent that can execute tool calls"

NEXT_STEP_PROMPT = (
    "If you want to stop interaction, use `terminate` tool/function call."
)
