"""
人脸识别服务
Phase 2 增强：Prometheus 指标埋点
Phase 3 增强：Redis 缓存 + 后台线程加载
Phase 6: InsightFace/ArcFace 替代 dlib + face_recognition
"""

import os
import json
import cv2
import numpy as np
import time
import structlog
import threading
from typing import List, Tuple, Optional, Dict
from sqlalchemy.orm import Session
from prometheus_client import Counter, Histogram, Gauge
from insightface.app import FaceAnalysis

from app.config import settings
from app.models import User
from app.utils.face_utils import FaceUtils
from app.cache import redis_client

log = structlog.get_logger(__name__)

FACE_RECOG_TOTAL = Counter("face_recognition_requests_total", "人脸识别请求总数")
FACE_RECOG_SUCCESS = Counter("face_recognition_success_total", "人脸识别成功数")
FACE_RECOG_FAILURE = Counter(
    "face_recognition_failure_total", "人脸识别失败数", ["reason"]
)
FACE_RECOG_DURATION = Histogram(
    "face_recognition_duration_seconds",
    "识别耗时分布",
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
)
KNOWN_FACES_GAUGE = Gauge("known_faces_count", "已注册人脸数量")
CACHE_HIT = Counter("face_recognition_cache_hits_total", "识别缓存命中次数")


class FaceService:
    def __init__(self):
        self.known_encodings: List[np.ndarray] = []
        self.known_users: List[Dict] = []
        self.known_matrix: Optional[np.ndarray] = None
        self.threshold = settings.FACE_THRESHOLD
        self._ready = False
        self._face_app: Optional[FaceAnalysis] = None
        self._load_thread = threading.Thread(target=self._async_load, daemon=True)
        self._load_thread.start()

    def _async_load(self):
        try:
            self._init_insightface()
            self._load_known_faces()
            self._ready = True
            log.info("face_service_ready", known_faces=len(self.known_encodings))
        except Exception as e:
            log.error("face_service_load_error", error=str(e))
            self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def _load_known_faces(self):
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            users = (
                db.query(User)
                .filter(User.status == 1, User.face_encoding_path.isnot(None))
                .all()
            )

            for user in users:
                if os.path.exists(user.face_encoding_path):
                    encoding = np.load(user.face_encoding_path)
                    self.known_encodings.append(encoding)
                    self.known_users.append(
                        {
                            "id": user.id,
                            "employee_id": user.employee_id,
                            "name": user.name,
                            "department": user.department,
                        }
                    )

            log.info("known_faces_loaded", count=len(self.known_encodings))
            KNOWN_FACES_GAUGE.set(len(self.known_encodings))
            self._rebuild_matrix()
            self._ready = True
        except Exception as e:
            log.error("failed_to_load_known_faces", error=str(e))
            self._ready = False
        finally:
            db.close()

    def _rebuild_matrix(self):
        if self.known_encodings:
            self.known_matrix = np.stack(self.known_encodings)
        else:
            self.known_matrix = None

    def reload_faces(self, db: Session):
        self.known_encodings = []
        self.known_users = []
        self._load_known_faces_from_db(db)

    def _load_known_faces_from_db(self, db: Session):
        users = (
            db.query(User)
            .filter(User.status == 1, User.face_encoding_path.isnot(None))
            .all()
        )

        for user in users:
            if os.path.exists(user.face_encoding_path):
                encoding = np.load(user.face_encoding_path)
                self.known_encodings.append(encoding)
                self.known_users.append(
                    {
                        "id": user.id,
                        "employee_id": user.employee_id,
                        "name": user.name,
                        "department": user.department,
                    }
                )
        KNOWN_FACES_GAUGE.set(len(self.known_encodings))
        self._rebuild_matrix()

    def _init_insightface(self):
        self._face_app = FaceAnalysis(
            name=settings.FACE_MODEL_NAME,
            providers=[settings.FACE_PROVIDER],
        )
        det_size = (settings.FACE_DET_SIZE, settings.FACE_DET_SIZE)
        self._face_app.prepare(ctx_id=0, det_size=det_size)
        log.info(
            "insightface_loaded", model=settings.FACE_MODEL_NAME, det_size=det_size
        )

    def detect_faces(self, image: np.ndarray) -> List[Dict]:
        if self._face_app is None:
            self._init_insightface()

        insight_faces = self._face_app.get(image)

        results = []
        for face in insight_faces:
            bbox = face.bbox.astype(int)
            top, right, bottom, left = (
                int(bbox[1]),
                int(bbox[2]),
                int(bbox[3]),
                int(bbox[0]),
            )
            location = (top, right, bottom, left)

            quality = FaceUtils.get_face_quality(image, location)

            results.append(
                {
                    "box": location,
                    "encoding": face.embedding,
                    "quality": quality,
                    "det_score": float(face.det_score),
                    "keypoints": face.kps.tolist() if face.kps is not None else None,
                }
            )

        return results

    def register_face(self, user_id: int, image: np.ndarray, db: Session) -> Dict:
        faces = self.detect_faces(image)

        if len(faces) == 0:
            return {"success": False, "quality": None, "message": "未检测到人脸"}

        if len(faces) > 1:
            return {
                "success": False,
                "quality": None,
                "message": "检测到多张人脸，请确保只有一人",
            }

        face = faces[0]

        if face["quality"] == "poor":
            return {
                "success": False,
                "quality": "poor",
                "message": "人脸质量较差，请调整光线或位置",
            }

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "quality": None, "message": "用户不存在"}

        encoding_filename = f"{user.employee_id}.npy"
        encoding_path = settings.ENCODINGS_DIR / encoding_filename
        np.save(encoding_path, face["encoding"])

        image_filename = f"{user.employee_id}.jpg"
        image_path = settings.IMAGES_DIR / image_filename
        cv2.imwrite(str(image_path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))

        user.face_encoding_path = str(encoding_path)
        user.face_image_path = str(image_path)
        db.commit()

        self.reload_faces(db)
        log.info("face_registered", user_id=user_id, employee_id=user.employee_id)

        return {"success": True, "quality": face["quality"], "message": "人脸注册成功"}

    def recognize_face(self, encoding: np.ndarray) -> Tuple[Optional[Dict], float]:
        if self.known_matrix is None or len(self.known_encodings) == 0:
            return None, 0.0

        similarities = self.known_matrix @ encoding
        max_idx = int(np.argmax(similarities))
        max_similarity = float(similarities[max_idx])

        confidence = max_similarity

        if confidence >= self.threshold:
            identified_user = self.known_users[max_idx]
            user_id = identified_user["id"]

            cache_key = f"recog:{user_id}"
            cached = redis_client.get(cache_key)
            if cached:
                CACHE_HIT.inc()
                result = json.loads(cached)
                return (result.get("user"), result.get("confidence", 0.0))

            redis_client.set(
                cache_key,
                json.dumps({"user": identified_user, "confidence": float(confidence)}),
                settings.CACHE_RECOG_TTL,
            )
            return (identified_user, float(confidence))
        else:
            return None, float(confidence)

    def verify_user(self, image: np.ndarray) -> Dict:
        start_time = time.time()
        FACE_RECOG_TOTAL.inc()

        faces = self.detect_faces(image)

        if len(faces) == 0:
            FACE_RECOG_FAILURE.labels(reason="no_face_detected").inc()
            FACE_RECOG_DURATION.observe(time.time() - start_time)
            return {
                "success": False,
                "user": None,
                "confidence": 0,
                "reason": "no_face_detected",
            }

        if len(faces) > 1:
            FACE_RECOG_FAILURE.labels(reason="multiple_faces").inc()
            FACE_RECOG_DURATION.observe(time.time() - start_time)
            return {
                "success": False,
                "user": None,
                "confidence": 0,
                "reason": "multiple_faces",
            }

        face = faces[0]

        if face["quality"] == "poor":
            FACE_RECOG_FAILURE.labels(reason="poor_quality").inc()
            FACE_RECOG_DURATION.observe(time.time() - start_time)
            return {
                "success": False,
                "user": None,
                "confidence": 0,
                "reason": "poor_quality",
            }

        user, confidence = self.recognize_face(face["encoding"])

        if user is None:
            FACE_RECOG_FAILURE.labels(reason="not_recognized").inc()
            FACE_RECOG_DURATION.observe(time.time() - start_time)
            return {
                "success": False,
                "user": None,
                "confidence": confidence,
                "reason": "face_not_recognized",
            }

        FACE_RECOG_SUCCESS.inc()
        FACE_RECOG_DURATION.observe(time.time() - start_time)
        return {"success": True, "user": user, "confidence": confidence, "reason": None}


face_service = FaceService()
