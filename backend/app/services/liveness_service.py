import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from scipy.spatial import distance as dist
from pathlib import Path


class LivenessService:
    def __init__(self, required_frames: int = 5):
        self.required_frames = required_frames
        self.ear_threshold = 0.2
        self.ear_consecutive_frames = 2
        self.pitch_threshold = 15

        self.LEFT_EYE_INDICES = list(range(36, 42))
        self.RIGHT_EYE_INDICES = list(range(42, 48))
        self._predictor = None

    @property
    def predictor(self):
        if self._predictor is None:
            import dlib

            model_path = Path("models/shape_predictor_68_face_landmarks.dat")
            if model_path.exists():
                self._predictor = dlib.shape_predictor(str(model_path))
            else:
                raise RuntimeError(
                    f"Liveness model not found at {model_path}. "
                    "Download from http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
                )
        return self._predictor

    def calculate_ear(self, eye_landmarks: np.ndarray) -> float:
        v1 = dist.euclidean(eye_landmarks[1], eye_landmarks[5])
        v2 = dist.euclidean(eye_landmarks[2], eye_landmarks[4])
        h = dist.euclidean(eye_landmarks[0], eye_landmarks[3])
        ear = (v1 + v2) / (2.0 * h)
        return ear

    def get_landmarks(self, image: np.ndarray, face_location: Tuple) -> np.ndarray:
        import dlib

        top, right, bottom, left = face_location
        rect = dlib.rectangle(left, top, right, bottom)

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image

        shape = self.predictor(gray, rect)
        landmarks = np.array([[p.x, p.y] for p in shape.parts()])

        return landmarks

    def estimate_head_pose(self, landmarks: np.ndarray) -> Dict[str, float]:
        nose = landmarks[30]
        chin = landmarks[8]
        forehead = landmarks[27]

        face_height = chin[1] - forehead[1]
        nose_position = (
            (nose[1] - forehead[1]) / face_height if face_height > 0 else 0.5
        )
        pitch = (nose_position - 0.5) * 60

        return {"pitch": pitch, "yaw": 0, "roll": 0}

    def check_blink(
        self, frames: List[np.ndarray], face_locations: List[Tuple]
    ) -> bool:
        if len(frames) < 3:
            return False

        ear_values = []

        for frame, location in zip(frames, face_locations):
            landmarks = self.get_landmarks(frame, location)

            left_eye = landmarks[self.LEFT_EYE_INDICES]
            left_ear = self.calculate_ear(left_eye)

            right_eye = landmarks[self.RIGHT_EYE_INDICES]
            right_ear = self.calculate_ear(right_eye)

            avg_ear = (left_ear + right_ear) / 2.0
            ear_values.append(avg_ear)

        blink_detected = False
        consecutive_low = 0

        for ear in ear_values:
            if ear < self.ear_threshold:
                consecutive_low += 1
            else:
                if consecutive_low >= 1 and consecutive_low <= 3:
                    blink_detected = True
                    break
                consecutive_low = 0

        return blink_detected

    def check_nod(self, frames: List[np.ndarray], face_locations: List[Tuple]) -> bool:
        if len(frames) < 3:
            return False

        pitch_values = []

        for frame, location in zip(frames, face_locations):
            landmarks = self.get_landmarks(frame, location)
            pose = self.estimate_head_pose(landmarks)
            pitch_values.append(pose["pitch"])

        if len(pitch_values) < 3:
            return False

        max_pitch = max(pitch_values)
        min_pitch = min(pitch_values)

        if abs(max_pitch - min_pitch) > self.pitch_threshold:
            return True

        return False

    def check_liveness(
        self, frames: List[np.ndarray], face_locations: List[Tuple]
    ) -> Dict:
        if len(frames) < 3:
            return {
                "passed": False,
                "blink_detected": False,
                "nod_detected": False,
                "message": "帧数不足",
            }

        blink = self.check_blink(frames, face_locations)
        nod = self.check_nod(frames, face_locations)

        passed = blink or nod
        message = "活体检测通过" if passed else "请眨眼或点头"

        return {
            "passed": passed,
            "blink_detected": blink,
            "nod_detected": nod,
            "message": message,
        }


liveness_service: Optional[LivenessService] = None


def get_liveness_service() -> LivenessService:
    global liveness_service
    if liveness_service is None:
        liveness_service = LivenessService()
    return liveness_service
