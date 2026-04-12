import numpy as np
from typing import List, Dict, Tuple, Optional


class LivenessService:
    """
    基于 InsightFace 5 点关键点的活体检测
    keypoint 索引: 0=左眼, 1=右眼, 2=鼻尖, 3=左嘴角, 4=右嘴角

    眨眼检测：眼-鼻距离 / 嘴角宽度 比值在闭眼时下降
    点头检测：鼻尖 Y 坐标 / 人脸高度 归一化位移量超过阈值
    """

    def __init__(self, required_frames: int = 5):
        self.required_frames = required_frames
        self.blink_ratio_threshold = 0.85
        self.nod_displacement_threshold = 0.05

    def _eye_openness(self, keypoints: np.ndarray) -> Tuple[float, float]:
        left_eye = keypoints[0]
        right_eye = keypoints[1]
        nose = keypoints[2]
        left_mouth = keypoints[3]
        right_mouth = keypoints[4]

        face_width = np.linalg.norm(right_mouth - left_mouth)
        if face_width < 1e-6:
            return (1.0, 1.0)

        left_eye_nose = np.linalg.norm(left_eye - nose)
        right_eye_nose = np.linalg.norm(right_eye - nose)

        return (left_eye_nose / face_width, right_eye_nose / face_width)

    def check_blink(
        self,
        frames: List[np.ndarray],
        face_locations: List[Tuple],
        face_keypoints: Optional[List[np.ndarray]] = None,
    ) -> bool:
        if face_keypoints is None or len(face_keypoints) < 3:
            return False

        ratios = []
        for kps in face_keypoints:
            if kps is None:
                continue
            left_open, right_open = self._eye_openness(kps)
            ratios.append((left_open + right_open) / 2.0)

        if len(ratios) < 3:
            return False

        avg_ratio = np.mean(ratios)
        threshold = avg_ratio * self.blink_ratio_threshold

        consecutive_low = 0
        for ratio in ratios:
            if ratio < threshold:
                consecutive_low += 1
            else:
                if 1 <= consecutive_low <= 3:
                    return True
                consecutive_low = 0

        return False

    def check_nod(
        self,
        frames: List[np.ndarray],
        face_locations: List[Tuple],
        face_keypoints: Optional[List[np.ndarray]] = None,
    ) -> bool:
        if face_keypoints is None or len(face_keypoints) < 3:
            return False

        normalized_y = []
        for i, kps in enumerate(face_keypoints):
            if kps is None:
                continue
            nose_y = kps[2][1]
            top, _, bottom, _ = face_locations[i]
            face_height = bottom - top
            if face_height < 1e-6:
                continue
            normalized_y.append(nose_y / face_height)

        if len(normalized_y) < 3:
            return False

        return (max(normalized_y) - min(normalized_y)) > self.nod_displacement_threshold

    def check_liveness(
        self,
        frames: List[np.ndarray],
        face_locations: List[Tuple],
        face_keypoints: Optional[List[np.ndarray]] = None,
    ) -> Dict:
        if len(frames) < 3:
            return {
                "passed": False,
                "blink_detected": False,
                "nod_detected": False,
                "message": "帧数不足",
            }

        blink = self.check_blink(frames, face_locations, face_keypoints)
        nod = self.check_nod(frames, face_locations, face_keypoints)

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
