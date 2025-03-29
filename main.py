# main.py
import asyncio
import websockets
import json
import os
import sys
import time
from enum import Enum
from weakref import WeakSet
from app.agent.manus import Manus
from app.logger import logger
from app.agent.planning import PlanningAgent
import traceback

# 配置参数
WEBSOCKET_HOST = os.getenv("WEBSOCKET_HOST", "0.0.0.0")
WEBSOCKET_PORT = int(os.getenv("WEBSOCKET_PORT", 8765))
HEARTBEAT_INTERVAL = 30  # 心跳间隔（秒）
MAX_MESSAGE_SIZE = 2 ** 20  # 1MB消息限制

# 全局连接池（弱引用防止内存泄漏）
connected_clients = WeakSet()

class MessageType(Enum):
    PROMPT = "prompt"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    STATUS = "status"
    PLAN_STATUS = "plan_status"
    TOOL_EXECUTION = "tool_execution"
    STEP_COMPLETED = "step_completed"

def validate_message(data: dict) -> bool:
    """增强消息验证"""
    return (
        isinstance(data, dict) and 
        "type" in data and 
        data["type"] in [t.value for t in MessageType] and 
        "data" in data
    )

async def sanitize_input(data: dict) -> dict:
    """输入安全过滤"""
    sanitized = data.copy()
    if "data" in sanitized and isinstance(sanitized["data"], str):
        # 基础XSS防护
        sanitized["data"] = (
            sanitized["data"]
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("&", "&amp;")
        )
    return sanitized

async def send_to_frontend(message: dict):
    """安全广播消息（增强版）"""
    if not connected_clients:
        return

    tasks = []
    for client in connected_clients:
        try:
            if client.open:
                full_message = {
                    **message,
                    "timestamp": time.time(),
                    "message_id": f"msg_{int(time.time()*1000)}"
                }
                tasks.append(client.send(json.dumps(full_message)))
        except Exception as e:
            logger.warning(f"客户端状态异常: {str(e)}")
            connected_clients.discard(client)
    
    await asyncio.gather(*tasks, return_exceptions=True)

async def agent_run(websocket, prompt: str):
    """主代理执行逻辑"""
    try:
        # 创建带WebSocket连接的Agent
        agent = PlanningAgent(websocket=websocket)
        
        # 发送初始状态
        await send_to_frontend({
            "type": MessageType.PLAN_STATUS.value,
            "status": "processing",
            "progress": 0,
            "message": "开始处理请求..."
        })
        
        # 执行计划
        result = await agent.run(prompt)
        
        # 发送最终结果
        await send_to_frontend({
            "type": "plan_complete",
            "result": result,
            "progress": 100
        })
        
    except Exception as e:
        logger.error(f"执行失败: {str(e)}", exc_info=True)
        await send_to_frontend({
            "type": MessageType.ERROR.value,
            "error_code": "AGENT_RUN_FAILED",
            "message": f"执行错误: {str(e)}",
            "traceback": traceback.format_exc()
        })

async def websocket_handler(websocket, path):
    """WebSocket连接处理器"""
    client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    connected_clients.add(websocket)
    logger.info(f"新连接: {client_id}")

    try:
        # 发送连接确认
        await websocket.send(json.dumps({
            "type": "connection_ack",
            "client_id": client_id,
            "timestamp": time.time()
        }))

        async for message in websocket:
            try:
                # 基础消息验证
                raw_data = json.loads(message)
                data = await sanitize_input(raw_data)

                if not validate_message(data):
                    await send_to_frontend({
                        "type": MessageType.ERROR.value,
                        "error_code": "INVALID_MESSAGE",
                        "message": "无效消息格式"
                    })
                    continue

                # 消息类型路由
                if data["type"] == MessageType.PROMPT.value:
                    asyncio.create_task(agent_run(websocket, data["data"]))
                    
                elif data["type"] == MessageType.HEARTBEAT.value:
                    await send_to_frontend({
                        "type": MessageType.STATUS.value,
                        "message": "心跳响应",
                        "client_id": client_id
                    })

            except json.JSONDecodeError:
                await send_to_frontend({
                    "type": MessageType.ERROR.value,
                    "error_code": "INVALID_JSON",
                    "message": "JSON解析失败"
                })
            except Exception as e:
                logger.error(f"消息处理异常: {str(e)}", exc_info=True)
                await send_to_frontend({
                    "type": MessageType.ERROR.value,
                    "error_code": "PROCESSING_ERROR",
                    "message": f"消息处理失败: {str(e)}"
                })

    except websockets.exceptions.ConnectionClosedError as e:
        logger.warning(f"连接异常断开: {client_id} (code: {e.code})")
    except Exception as e:
        logger.error(f"连接错误: {str(e)}", exc_info=True)
    finally:
        connected_clients.discard(websocket)
        logger.info(f"连接关闭: {client_id}")

async def health_check():
    """系统健康监测"""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        logger.info(f"活跃连接数: {len(connected_clients)}")
        await send_to_frontend({
            "type": "system_status",
            "active_connections": len(connected_clients),
            "memory_usage": f"{os.getpid():,}",
            "status": "healthy"
        })

async def main():
    # 启动WebSocket服务器
    server = await websockets.serve(
        websocket_handler,
        WEBSOCKET_HOST,
        WEBSOCKET_PORT,
        ping_interval=20,
        ping_timeout=10,
        max_size=MAX_MESSAGE_SIZE
    )
    
    logger.info(f"🔌 WebSocket服务已启动: ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
    
    # 启动健康检查
    asyncio.create_task(health_check())
    
    # 保持服务运行
    await server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 服务器正常关闭")
    except Exception as e:
        logger.error(f"💥 服务启动失败: {str(e)}", exc_info=True)
        sys.exit(1)