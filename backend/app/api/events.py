"""
SSE (Server-Sent Events) 实时事件推送
Dashboard 页面通过此端点订阅实时识别、考勤和系统事件
"""
import asyncio
import json
import time
import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.cache import redis_client

log = structlog.get_logger(__name__)

router = APIRouter(tags=["events"])

# Redis Pub/Sub 频道：notification_service 的相关通道
SSE_CHANNELS = [
    "notify:face_recognition",
    "notify:attendance",
    "notify:system",
]

# 心跳间隔（秒），当没有消息时也要定期向前端发送心跳
HEARTBEAT_INTERVAL = 15


async def _sse_event_generator(request: Request):
    """SSE 事件生成器
    订阅 Redis Pub/Sub 频道，将消息推送给客户端
    支持在 Redis 不可用时进行降级处理：发送心跳而非消息
    """
    pubsub = None
    last_heartbeat = 0

    try:
        if redis_client.available:
            pubsub = redis_client.client.pubsub()
            await asyncio.to_thread(pubsub.subscribe, *SSE_CHANNELS)
            log.info("sse_subscribed", channels=SSE_CHANNELS)

        while True:
            # 客户端断开连接，需要立即停止
            if await request.is_disconnected():
                log.info("sse_client_disconnected")
                break

            if pubsub:
                # get_message 是阻塞式调用，需要放到线程中执行，避免事件循环阻塞
                message = await asyncio.to_thread(pubsub.get_message, timeout=1.0)
                if message and message.get("type") == "message":
                    channel = message["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8")
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")

                    event_type = _map_channel_to_event(channel)
                    yield f"event: {event_type}\ndata: {data}\n\n"
                    # 一旦有消息，继续下一轮循环，尽量快速送达
                    continue

            # 心跳机制：定期发送 heartbeat，确保连接活跃
            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                yield ": heartbeat\n\n"
                last_heartbeat = now

            await asyncio.sleep(1)
    except asyncio.CancelledError:
        log.info("sse_stream_cancelled")
    except Exception as e:
        log.error("sse_stream_error", error=str(e))
    finally:
        if pubsub:
            try:
                await asyncio.to_thread(pubsub.unsubscribe)
                await asyncio.to_thread(pubsub.close)
            except Exception:
                pass
        log.info("sse_stream_closed")


def _map_channel_to_event(channel: str) -> str:
    """将 Redis 通道映射为 SSE 事件类型"""
    mapping = {
        "notify:face_recognition": "face_recognized",
        "notify:attendance": "attendance_recorded",
        "notify:system": "system_alert",
    }
    return mapping.get(channel, "unknown")


@router.get("/api/events/stream")
async def sse_stream(request: Request):
    """SSE 实时事件流

    事件类型:
    - face_recognized: 人脸识别结果
    - attendance_recorded: 考勤打卡记录
    - system_alert: 系统告警

    响应格式: text/event-stream
    """
    return StreamingResponse(
        _sse_event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 禁用缓冲
        },
    )
