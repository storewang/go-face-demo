"""
通知推送服务
支持 Redis Pub/Sub 实时通知
Phase 4 功能扩展（第二批）
"""
import json
import structlog
from typing import Optional
from datetime import datetime, timezone

from app.cache import redis_client

log = structlog.get_logger(__name__)

CHANNEL_FACE_RECOGNITION = "notify:face_recognition"
CHANNEL_ATTENDANCE = "notify:attendance"
CHANNEL_SYSTEM = "notify:system"


class NotifyLevel:
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class NotificationService:
    """通知推送服务"""

    @staticmethod
    def send(channel: str, level: str, title: str, message: str, data: dict = None):
        """发送通知"""
        payload = {
            "level": level,
            "title": title,
            "message": message,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if redis_client.available:
            redis_client.publish(channel, json.dumps(payload, ensure_ascii=False))
        log.info("notification_sent", channel=channel, level=level, title=title)

    @staticmethod
    def face_recognized(user_name: str, confidence: float, result: str):
        """人脸识别结果通知"""
        NotificationService.send(
            CHANNEL_FACE_RECOGNITION,
            NotifyLevel.INFO if result == "success" else NotifyLevel.WARNING,
            f"识别结果：{user_name}",
            f"置信度：{confidence:.2%}，结果：{result}",
            {"user_name": user_name, "confidence": confidence, "result": result},
        )

    @staticmethod
    def attendance_recorded(user_name: str, action_type: str):
        """考勤打卡通知"""
        action_names = {"CHECK_IN": "签到", "CHECK_OUT": "签退", "visitor": "访客"}
        NotificationService.send(
            CHANNEL_ATTENDANCE,
            NotifyLevel.SUCCESS,
            f"考勤记录：{user_name}",
            f"{action_names.get(action_type, action_type)}成功",
            {"user_name": user_name, "action_type": action_type},
        )

    @staticmethod
    def system_alert(title: str, message: str, level: str = NotifyLevel.WARNING):
        """系统告警通知"""
        NotificationService.send(CHANNEL_SYSTEM, level, title, message)


notification_service = NotificationService()