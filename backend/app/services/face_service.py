"""
人脸识别服务
Phase 2 增强：Prometheus 指标埋点
Phase 3 增强：Redis 缓存 + 后台线程加载
Phase 6: Python 3.12 + YuNet 检测器（OpenCV 4.9+ 内置）
"""
import os
import json
import cv2
import numpy as np
import time
import structlog
import threading
import face_recognition
from typing import List, Tuple, Optional, Dict
from sqlalchemy.orm import Session
from prometheus_client import Counter, Histogram, Gauge

from app.config import settings
from app.models import User
from app.utils.face_utils import FaceUtils
from app.cache import redis_client

log = structlog.get_logger(__name__)

# 检测器选择：yunet（推荐，OpenCV 4.9+）或 ssd（兼容旧版）
# 可通过环境变量 FACE_DETECTOR=yunet|ssd 切换
FACE_DETECTOR = os.environ.get("FACE_DETECTOR", "ssd").lower()

# Prometheus 指标定义
FACE_RECOG_TOTAL = Counter("face_recognition_requests_total", "人脸识别请求总数")
FACE_RECOG_SUCCESS = Counter("face_recognition_success_total", "人脸识别成功数")
FACE_RECOG_FAILURE = Counter("face_recognition_failure_total", "人脸识别失败数", ["reason"])
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
        self.threshold = settings.FACE_THRESHOLD
        self._ready = False
        self._detector_name = FACE_DETECTOR
        self._yunet_detector = None
        self._ssd_net = None
        self._load_thread = threading.Thread(target=self._async_load, daemon=True)
        self._load_thread.start()

    def _async_load(self):
        """后台线程异步加载特征库，避免阻塞启动"""
        try:
            self._init_detector()
            self._load_known_faces()
            self._ready = True
            log.info("face_service_ready", known_faces=len(self.known_encodings), detector=self._detector_name)
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
            self._ready = True
        except Exception as e:
            log.error("failed_to_load_known_faces", error=str(e))
            self._ready = False
        finally:
            db.close()

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

    def _init_detector(self):
        """初始化人脸检测器"""
        if self._detector_name == "yunet":
            # YuNet 需要 OpenCV 4.9+，检查是否可用
            cv_version = tuple(int(x) for x in cv2.__version__.split('.')[:2])
            if cv_version >= (4, 9) and hasattr(cv2, 'FaceDetectorYN_create'):
                self._init_yunet()
            else:
                log.warning("yunet_not_available", opencv_version=cv2.__version__, fallback="ssd")
                self._detector_name = "ssd"
                self._init_ssd()
        else:
            self._init_ssd()

    def _init_yunet(self):
        """初始化 OpenCV YuNet 人脸检测器（OpenCV 4.9+）"""
        model_dir = os.path.join(os.path.dirname(__file__), "../../models")
        model_dir = os.path.abspath(model_dir)
        os.makedirs(model_dir, exist_ok=True)
        model_file = os.path.join(model_dir, "face_detection_yunet_2023mar.onnx")

        if not os.path.exists(model_file):
            log.info("downloading_yunet_model")
            import urllib.request
            urllib.request.urlretrieve(
                "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
                model_file
            )

        self._yunet_detector = cv2.FaceDetectorYN_create(
            model_file, "", (320, 320),
            score_threshold=0.7,
            nms_threshold=0.3,
            top_k=5
        )
        log.info("yunet_detector_loaded")

    def _init_ssd(self):
        """加载 OpenCV SSD 人脸检测模型（fallback）"""
        model_dir = os.path.join(os.path.dirname(__file__), "../../models")
        model_dir = os.path.abspath(model_dir)
        os.makedirs(model_dir, exist_ok=True)
        model_file = os.path.join(model_dir, "res10_300x300_ssd_iter_140000.caffemodel")
        config_file = os.path.join(model_dir, "deploy.prototxt")

        if not os.path.exists(model_file) or not os.path.exists(config_file):
            log.info("downloading_ssd_model")
            import urllib.request
            urllib.request.urlretrieve(
                "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel",
                model_file
            )
            urllib.request.urlretrieve(
                "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt",
                config_file
            )

        self._ssd_net = cv2.dnn.readNetFromCaffe(config_file, model_file)
        log.info("ssd_model_loaded")

    def detect_faces(self, image: np.ndarray) -> List[Dict]:
        if self._detector_name == "yunet":
            return self._detect_faces_yunet(image)
        else:
            return self._detect_faces_ssd(image)

    def _detect_faces_yunet(self, image: np.ndarray) -> List[Dict]:
        """YuNet 人脸检测 → dlib 编码"""
        h, w = image.shape[:2]
        self._yunet_detector.setInputSize((w, h))

        _, faces = self._yunet_detector.detect(image)
        if faces is None:
            return []

        locations = []
        for face in faces:
            x, y, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
            # YuNet 的 x,y 是左上角，fw,fh 是宽高
            left, top = x, y
            right, bottom = x + fw, y + fh
            # 扩展 15% 边距（face_recognition 编码需要包含完整人脸）
            pad_x = int((right - left) * 0.15)
            pad_y = int((bottom - top) * 0.15)
            top = max(0, top - pad_y)
            left = max(0, left - pad_x)
            bottom = min(h, bottom + pad_y)
            right = min(w, right + pad_x)
            locations.append((top, right, bottom, left))  # face_recognition 格式

        if not locations:
            return []

        # 用 face_recognition 编码（dlib）
        encodings = face_recognition.face_encodings(image, locations)

        results = []
        for location, encoding in zip(locations, encodings):
            quality = FaceUtils.get_face_quality(image, location)
            results.append({"box": location, "encoding": encoding, "quality": quality})

        return results

    def _detect_faces_ssd(self, image: np.ndarray) -> List[Dict]:
        """OpenCV SSD 人脸检测（fallback）"""
        if not self._ssd_net:
            self._init_ssd()

        h, w = image.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(image, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
        self._ssd_net.setInput(blob)
        detections = self._ssd_net.forward()

        locations = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.6:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                left, top, right, bottom = int(box[0]), int(box[1]), int(box[2]), int(box[3])
                pad_x = int((right - left) * 0.1)
                pad_y = int((bottom - top) * 0.1)
                top = max(0, top - pad_y)
                left = max(0, left - pad_x)
                bottom = min(h, bottom + pad_y)
                right = min(w, right + pad_x)
                locations.append((top, right, bottom, left))

        if not locations:
            return []

        encodings = face_recognition.face_encodings(image, locations)

        results = []
        for location, encoding in zip(locations, encodings):
            quality = FaceUtils.get_face_quality(image, location)
            results.append({"box": location, "encoding": encoding, "quality": quality})

        return results

    def _load_ssd_model(self):
        """兼容旧调用"""
        self._init_ssd()

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
        if not self.known_encodings:
            return None, 0.0

        distances = face_recognition.face_distance(self.known_encodings, encoding)

        min_idx = np.argmin(distances)
        min_distance = distances[min_idx]

        confidence = 1 - min_distance

        if confidence >= self.threshold:
            identified_user = self.known_users[min_idx]
            user_id = identified_user["id"]

            # Phase 3 缓存优化：同一用户 3 秒内不重复识别
            cache_key = f"recog:{user_id}"
            cached = redis_client.get(cache_key)
            if cached:
                CACHE_HIT.inc()
                result = json.loads(cached)
                return (result.get("user"), result.get("confidence", 0.0))

            # 缓存识别结果
            redis_client.set(
                cache_key,
                json.dumps({"user": identified_user, "confidence": float(confidence)}),
                settings.CACHE_RECOG_TTL
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
