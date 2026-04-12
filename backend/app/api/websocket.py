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
from app.models import AttendanceLog, ActionType, ResultType, Device
from app.config import settings
from app.utils.face_utils import FaceUtils
import cv2

log = structlog.get_logger(__name__)

FRAME_BUFFER_SIZE = 5
COOLDOWN_SECONDS = 3
HEARTBEAT_TIMEOUT = 30


def _clear_buffers(session: dict):
    session["frames"] = []
    session["face_locations"] = []
    session["face_keypoints"] = []


async def _send_status(websocket: WebSocket, stage: str, message: str):
    await manager.send_json(
        websocket,
        {"type": "status", "data": {"stage": stage, "message": message}},
    )


async def _check_liveness(session: dict) -> bool:
    try:
        liveness = get_liveness_service()
        liveness_result = liveness.check_liveness(
            session["frames"], session["face_locations"], session["face_keypoints"]
        )
        if not liveness_result["passed"]:
            return False
    except Exception:
        pass
    return True


async def _record_attendance(
    session: dict, user: dict, confidence: float, image: np.ndarray
):
    db = SessionLocal()
    try:
        snapshot_filename = (
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user['employee_id']}.jpg"
        )
        snapshot_path = str(settings.IMAGES_DIR / "snapshots" / snapshot_filename)
        (settings.IMAGES_DIR / "snapshots").mkdir(parents=True, exist_ok=True)
        cv2.imwrite(snapshot_path, cv2.cvtColor(image, cv2.COLOR_RGB2BGR))

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_records = (
            db.query(AttendanceLog)
            .filter(
                AttendanceLog.user_id == user["id"],
                AttendanceLog.created_at >= today_start,
            )
            .count()
        )

        action_type = ActionType.CHECK_OUT if today_records > 0 else ActionType.CHECK_IN

        record_data = {
            "user_id": user["id"],
            "employee_id": user["employee_id"],
            "name": user["name"],
            "action_type": action_type,
            "confidence": confidence,
            "snapshot_path": snapshot_path,
            "result": ResultType.SUCCESS,
        }
        if session.get("device_id"):
            record_data["device_id"] = session["device_id"]

        db.add(AttendanceLog(**record_data))
        db.commit()

        notification_service.attendance_recorded(user["name"], action_type.value)
        return action_type
    finally:
        db.close()


async def process_frame(websocket: WebSocket, frame_data: str, session: dict):
    if session.get("processing", False):
        return

    session["processing"] = True
    try:
        image_bytes = base64.b64decode(frame_data)
        image = FaceUtils.load_image_from_bytes(image_bytes)

        faces = face_service.detect_faces(image)

        if len(faces) == 0:
            await _send_status(websocket, "detecting", "未检测到人脸，请对准摄像头")
            return

        if len(faces) > 1:
            await _send_status(websocket, "detecting", "检测到多张人脸，请确保只有一人")
            return

        face = faces[0]

        if face["quality"] == "poor":
            await _send_status(websocket, "quality_check", "请调整光线或位置")
            return

        session["frames"].append(image)
        session["face_locations"].append(face["box"])
        kps = face.get("keypoints")
        session["face_keypoints"].append(np.array(kps) if kps else None)

        if len(session["frames"]) < FRAME_BUFFER_SIZE:
            await _send_status(
                websocket,
                "liveness_check",
                f"请保持不动 ({len(session['frames'])}/{FRAME_BUFFER_SIZE})",
            )
            return

        liveness_ok = await _check_liveness(session)
        if not liveness_ok:
            liveness = get_liveness_service()
            liveness_result = liveness.check_liveness(
                session["frames"], session["face_locations"], session["face_keypoints"]
            )
            msg = (
                liveness_result.get("message", "请眨眼或点头")
                if liveness_result
                else "活体检测未通过"
            )
            await _send_status(websocket, "liveness_check", msg)
            _clear_buffers(session)
            return

        result = face_service.verify_user(image)

        if not result["success"]:
            reason = result.get("reason", "unknown")
            notification_service.face_recognized(
                "未知", result.get("confidence", 0), "failed"
            )
            await manager.send_json(
                websocket,
                {
                    "type": "result",
                    "data": {
                        "success": False,
                        "reason": reason,
                        "confidence": result.get("confidence", 0),
                        "message": f"识别失败: {reason}",
                    },
                },
            )
            _clear_buffers(session)
            return

        user = result["user"]
        confidence = result["confidence"]
        action_type = await _record_attendance(session, user, confidence, image)

        action_message = (
            "下班打卡成功" if action_type == ActionType.CHECK_OUT else "上班打卡成功"
        )

        result_data = {
            "success": True,
            "user": user,
            "confidence": confidence,
            "action": "door_open",
            "action_type": action_type.value,
            "message": f"{user['name']} {action_message}",
        }
        if session.get("device_name"):
            result_data["device_name"] = session["device_name"]

        await manager.send_json(websocket, {"type": "result", "data": result_data})

        _clear_buffers(session)
        session["last_result_time"] = datetime.now().timestamp()

    except Exception as e:
        log.error("frame_process_error", error=str(e))
        await manager.send_json(
            websocket, {"type": "error", "data": {"message": str(e)}}
        )
    finally:
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

            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=HEARTBEAT_TIMEOUT
                )
            except asyncio.TimeoutError:
                log.info("ws_heartbeat_timeout", active=len(manager.active_connections))
                await websocket.close(code=4000, reason="Heartbeat timeout")
                break

            message = json.loads(data)

            if message.get("type") == "register":
                device_code = message.get("device_code")
                if device_code:
                    db = SessionLocal()
                    try:
                        device = (
                            db.query(Device)
                            .filter(Device.device_code == device_code)
                            .first()
                        )
                        if not device:
                            await manager.send_json(
                                websocket,
                                {
                                    "type": "error",
                                    "data": {
                                        "message": "设备不存在",
                                        "code": "DEVICE_NOT_FOUND",
                                    },
                                },
                            )
                            await websocket.close()
                            return

                        if device.status == 2:
                            await manager.send_json(
                                websocket,
                                {
                                    "type": "error",
                                    "data": {
                                        "message": "设备已禁用",
                                        "code": "DEVICE_DISABLED",
                                    },
                                },
                            )
                            await websocket.close()
                            return

                        session["device_id"] = device.id
                        session["device_code"] = device.device_code
                        session["device_name"] = device.name

                        log.info(
                            "device_registered",
                            device_code=device_code,
                            device_name=device.name,
                        )

                        await manager.send_json(
                            websocket,
                            {
                                "type": "registered",
                                "data": {
                                    "device_id": device.id,
                                    "device_code": device.device_code,
                                    "device_name": device.name,
                                },
                            },
                        )
                    finally:
                        db.close()
                continue

            if message.get("type") == "frame":
                frame_data = message.get("data", "")
                await process_frame(websocket, frame_data, session)

            elif message.get("type") == "ping":
                session["last_ping"] = datetime.now().timestamp()
                await manager.send_json(websocket, {"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error("websocket_error", error=str(e))
    finally:
        manager.disconnect(websocket)
