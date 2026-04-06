import os
import cv2
import numpy as np
import face_recognition
from typing import List, Tuple, Optional, Dict
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.utils.face_utils import FaceUtils


class FaceService:
    def __init__(self):
        self.known_encodings: List[np.ndarray] = []
        self.known_users: List[Dict] = []
        self.threshold = settings.FACE_THRESHOLD
        self._load_known_faces()

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

            print(f"✅ Loaded {len(self.known_encodings)} known faces")
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

    def detect_faces(self, image: np.ndarray) -> List[Dict]:
        locations = face_recognition.face_locations(image, model="hog")

        if not locations:
            return []

        encodings = face_recognition.face_encodings(image, locations)

        results = []
        for location, encoding in zip(locations, encodings):
            quality = FaceUtils.get_face_quality(image, location)
            results.append({"box": location, "encoding": encoding, "quality": quality})

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

        return {"success": True, "quality": face["quality"], "message": "人脸注册成功"}

    def recognize_face(self, encoding: np.ndarray) -> Tuple[Optional[Dict], float]:
        if not self.known_encodings:
            return None, 0.0

        distances = face_recognition.face_distance(self.known_encodings, encoding)

        min_idx = np.argmin(distances)
        min_distance = distances[min_idx]

        confidence = 1 - min_distance

        if confidence >= self.threshold:
            return self.known_users[min_idx], float(confidence)
        else:
            return None, float(confidence)

    def verify_user(self, image: np.ndarray) -> Dict:
        faces = self.detect_faces(image)

        if len(faces) == 0:
            return {
                "success": False,
                "user": None,
                "confidence": 0,
                "reason": "no_face_detected",
            }

        if len(faces) > 1:
            return {
                "success": False,
                "user": None,
                "confidence": 0,
                "reason": "multiple_faces",
            }

        face = faces[0]

        if face["quality"] == "poor":
            return {
                "success": False,
                "user": None,
                "confidence": 0,
                "reason": "poor_quality",
            }

        user, confidence = self.recognize_face(face["encoding"])

        if user is None:
            return {
                "success": False,
                "user": None,
                "confidence": confidence,
                "reason": "face_not_recognized",
            }

        return {"success": True, "user": user, "confidence": confidence, "reason": None}


face_service = FaceService()
