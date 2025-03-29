#用于在工具（Tool）执行过程中捕获和抛出错误。
class ToolError(Exception):
    """Raised when a tool encounters an error."""

    def __init__(self, message):
        self.message = message
