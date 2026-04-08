import base64
import json
import asyncio
import numpy as np
import structlog
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

from app.websocket.manager import manager
from app.services.face_service import face_service
from app.services.liveness_service import get_liveness_service
from app.services.notification_service import notification_service
from app.database import SessionLocal
from app.models import AttendanceLog, ActionType, ResultType
from app.config import settings
from app.utils.face_utils import FaceUtils
import cv2

log = structlog.get_logger(__name__)

FRAME_BUFFER_SIZE = 5
COOLDOWN_SECONDS = 3


async def process_frame(websocket: WebSocket, frame_data: str, session: dict):
    # Phase 3 性能优化：跳帧逻辑（如果上一帧还在处理，丢弃当前帧）
    if session.get("processing", False):
        return
    
    session["processing"] = True
    try:
        # === 原有处理逻辑 ===
        image_bytes = base64.b64decode(frame_data)
        image = FaceUtils.load_image_from_bytes(image_bytes)

        faces = face_service.detect_faces(image)

        if len(faces) == 0:
            await manager.send_json(
                websocket,
                {
                    "type": "status",
                    "data": {
                        "stage": "detecting",
                        "message": "未检测到人脸，请对准摄像头",
                    },
                },
            )
            return

        if len(faces) > 1:
            await manager.send_json(
                websocket,
                {
                    "type": "status",
                    "data": {
                        "stage": "detecting",
                        "message": "检测到多张人脸，请确保只有一人",
                    },
                },
            )
            return

        face = faces[0]

        if face["quality"] == "poor":
            await manager.send_json(
                websocket,
                {
                    "type": "status",
                    "data": {"stage": "quality_check", "message": "请调整光线或位置"},
                },
            )
            return

        session["frames"].append(image)
        session["face_locations"].append(face["box"])

        if len(session["frames"]) < FRAME_BUFFER_SIZE:
            await manager.send_json(
                websocket,
                {
                    "type": "status",
                    "data": {
                        "stage": "liveness_check",
                        "message": f"请保持不动 ({len(session['frames'])}/{FRAME_BUFFER_SIZE})",
                    },
                },
            )
            return

        liveness_passed = True
        try:
            liveness = get_liveness_service()
            liveness_result = liveness.check_liveness(
                session["frames"], session["face_locations"]
            )

            if not liveness_result["passed"]:
                await manager.send_json(
                    websocket,
                    {
                        "type": "status",
                        "data": {
                            "stage": "liveness_check",
                            "message": liveness_result["message"],
                        },
                    },
                )
                session["frames"] = []
                session["face_locations"] = []
                return
        except Exception:
            liveness_passed = False

        user, confidence = face_service.recognize_face(face["encoding"])

        if user is None:
            notification_service.face_recognized("未知", confidence, "failed")
            await manager.send_json(
                websocket,
                {
                    "type": "result",
                    "data": {
                        "success": False,
                        "reason": "face_not_recognized",
                        "confidence": confidence,
                        "message": "未识别到注册用户",
                    },
                },
            )
            session["frames"] = []
            session["face_locations"] = []
            return

        db = SessionLocal()
        try:
            snapshot_filename = (
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user['employee_id']}.jpg"
            )
            snapshot_path = str(settings.IMAGES_DIR / "snapshots" / snapshot_filename)
            (settings.IMAGES_DIR / "snapshots").mkdir(parents=True, exist_ok=True)
            cv2.imwrite(
                snapshot_path, cv2.cvtColor(session["frames"][-1], cv2.COLOR_RGB2BGR)
            )

            today_start = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            today_records = (
                db.query(AttendanceLog)
                .filter(
                    AttendanceLog.user_id == user["id"],
                    AttendanceLog.created_at >= today_start,
                )
                .count()
            )

            action_type = (
                ActionType.CHECK_OUT if today_records > 0 else ActionType.CHECK_IN
            )

            record = AttendanceLog(
                user_id=user["id"],
                employee_id=user["employee_id"],
                name=user["name"],
                action_type=action_type,
                confidence=confidence,
                snapshot_path=snapshot_path,
                result=ResultType.SUCCESS,
            )
            db.add(record)
            db.commit()
            
            notification_service.attendance_recorded(user["name"], action_type.value)
        finally:
            db.close()

        action_message = (
            "下班打卡成功" if action_type == ActionType.CHECK_OUT else "上班打卡成功"
        )

        await manager.send_json(
            websocket,
            {
                "type": "result",
                "data": {
                    "success": True,
                    "user": user,
                    "confidence": confidence,
                    "action": "door_open",
                    "action_type": action_type.value,
                    "message": f"{user['name']} {action_message}",
                },
            },
        )

        session["frames"] = []
        session["face_locations"] = []
        session["last_result_time"] = datetime.now().timestamp()

    except Exception as e:
        log.error("frame_process_error", error=str(e))
        await manager.send_json(
            websocket, {"type": "error", "data": {"message": str(e)}}
        )
    finally:
        # 确保 processing 标志被重置
        session["processing"] = False


async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    session = manager.get_session(websocket)

    try:
        while True:
            last_result = session.get("last_result_time", 0)
            if datetime.now().timestamp() - last_result < COOLDOWN_SECONDS:
                await asyncio.sleep(0.5)
                continue

            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "frame":
                frame_data = message.get("data", "")
                await process_frame(websocket, frame_data, session)

            elif message.get("type") == "ping":
                await manager.send_json(websocket, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        log.error("websocket_error", error=str(e))
        manager.disconnect(websocket)
