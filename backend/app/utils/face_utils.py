import cv2
import numpy as np
import face_recognition
from typing import Tuple


class FaceUtils:
    @staticmethod
    def load_image_from_bytes(image_bytes: bytes) -> np.ndarray:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    @staticmethod
    def load_image_from_file(file_path: str) -> np.ndarray:
        return face_recognition.load_image_file(file_path)

    @staticmethod
    def get_face_quality(image: np.ndarray, location: Tuple) -> str:
        top, right, bottom, left = location
        face_height = bottom - top
        face_width = right - left

        if face_width < 80 or face_height < 80:
            return "poor"
        if face_width < 120 or face_height < 120:
            return "medium"

        face_region = image[top:bottom, left:right]
        brightness = np.mean(face_region)
        if brightness < 50 or brightness > 200:
            return "poor"
        if brightness < 80 or brightness > 180:
            return "medium"

        gray = cv2.cvtColor(face_region, cv2.COLOR_RGB2GRAY)
        clarity = cv2.Laplacian(gray, cv2.CV_64F).var()
        if clarity < 50:
            return "poor"
        if clarity < 100:
            return "medium"

        return "good"

    @staticmethod
    def draw_face_box(
        image: np.ndarray, location: Tuple, label: str = ""
    ) -> np.ndarray:
        top, right, bottom, left = location
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        cv2.rectangle(image_bgr, (left, top), (right, bottom), (0, 255, 0), 2)

        if label:
            cv2.rectangle(
                image_bgr, (left, bottom - 25), (right, bottom), (0, 255, 0), cv2.FILLED
            )
            cv2.putText(
                image_bgr,
                label,
                (left + 6, bottom - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

        return image_bgr
