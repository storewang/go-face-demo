from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional, List
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.face import (
    FaceDetectResponse,
    FaceVerifyResponse,
    FaceRegisterResponse,
    UserInfo,
)
from app.services.face_service import face_service
from app.services.liveness_service import get_liveness_service
from app.utils.face_utils import FaceUtils

router = APIRouter(prefix="/api/face", tags=["人脸识别"])


@router.post("/detect", response_model=FaceDetectResponse, summary="检测人脸")
def detect_face(image: UploadFile = File(..., description="图像文件")):
    image_bytes = image.file.read()
    img = FaceUtils.load_image_from_bytes(image_bytes)

    faces = face_service.detect_faces(img)

    face_list = []
    for face in faces:
        face_list.append(
            {
                "box": {
                    "top": face["box"][0],
                    "right": face["box"][1],
                    "bottom": face["box"][2],
                    "left": face["box"][3],
                },
                "quality": face["quality"],
            }
        )

    return FaceDetectResponse(faces_detected=len(faces), faces=face_list)


@router.post(
    "/recognize", response_model=FaceVerifyResponse, summary="人脸识别（无活体检测）"
)
def recognize_face(image: UploadFile = File(..., description="图像文件")):
    image_bytes = image.file.read()
    img = FaceUtils.load_image_from_bytes(image_bytes)

    result = face_service.verify_user(img)

    if result["success"]:
        return FaceVerifyResponse(
            success=True,
            user=UserInfo(**result["user"]),
            confidence=result["confidence"],
            liveness_passed=None,
            reason=None,
        )
    else:
        return FaceVerifyResponse(
            success=False,
            user=None,
            confidence=result["confidence"],
            liveness_passed=None,
            reason=result["reason"],
        )


@router.post(
    "/verify", response_model=FaceVerifyResponse, summary="完整验证（含活体检测）"
)
def verify_face(
    images: List[UploadFile] = File(..., description="连续帧图像（3-5张）"),
    check_liveness: bool = Form(True, description="是否进行活体检测"),
):
    if len(images) < 1:
        raise HTTPException(status_code=400, detail="至少需要1张图像")

    first_image_bytes = images[0].file.read()
    first_img = FaceUtils.load_image_from_bytes(first_image_bytes)

    faces = face_service.detect_faces(first_img)

    if len(faces) == 0:
        return FaceVerifyResponse(
            success=False,
            user=None,
            confidence=0,
            liveness_passed=None,
            reason="no_face_detected",
        )

    if len(faces) > 1:
        return FaceVerifyResponse(
            success=False,
            user=None,
            confidence=0,
            liveness_passed=None,
            reason="multiple_faces",
        )

    face = faces[0]

    if face["quality"] == "poor":
        return FaceVerifyResponse(
            success=False,
            user=None,
            confidence=0,
            liveness_passed=None,
            reason="poor_quality",
        )

    liveness_passed = None
    if check_liveness and len(images) >= 3:
        try:
            liveness = get_liveness_service()

            frame_list = [first_img]
            face_locations = [face["box"]]

            for img_file in images[1:]:
                img_bytes = img_file.file.read()
                img = FaceUtils.load_image_from_bytes(img_bytes)
                frame_list.append(img)

                frame_faces = face_service.detect_faces(img)
                if frame_faces:
                    face_locations.append(frame_faces[0]["box"])
                else:
                    face_locations.append(face_locations[-1])

            liveness_result = liveness.check_liveness(frame_list, face_locations)
            liveness_passed = liveness_result["passed"]

            if not liveness_passed:
                return FaceVerifyResponse(
                    success=False,
                    user=None,
                    confidence=0,
                    liveness_passed=False,
                    reason="liveness_failed",
                )
        except Exception:
            liveness_passed = None

    user, confidence = face_service.recognize_face(face["encoding"])

    if user is None:
        return FaceVerifyResponse(
            success=False,
            user=None,
            confidence=confidence,
            liveness_passed=liveness_passed,
            reason="face_not_recognized",
        )

    return FaceVerifyResponse(
        success=True,
        user=UserInfo(**user),
        confidence=confidence,
        liveness_passed=liveness_passed,
        reason=None,
    )


@router.post(
    "/register/{user_id}", response_model=FaceRegisterResponse, summary="注册人脸"
)
def register_face(
    user_id: int,
    image: UploadFile = File(..., description="人脸照片"),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    image_bytes = image.file.read()
    img = FaceUtils.load_image_from_bytes(image_bytes)

    result = face_service.register_face(user_id, img, db)

    return FaceRegisterResponse(
        success=result["success"],
        user_id=user_id,
        face_detected=result["success"],
        face_quality=result.get("quality"),
        message=result["message"],
    )


@router.post("/compare", summary="人脸比对（1:1）")
def compare_faces(
    image1: UploadFile = File(..., description="第一张人脸"),
    image2: UploadFile = File(..., description="第二张人脸"),
):
    import face_recognition

    img1_bytes = image1.file.read()
    img1 = FaceUtils.load_image_from_bytes(img1_bytes)

    img2_bytes = image2.file.read()
    img2 = FaceUtils.load_image_from_bytes(img2_bytes)

    faces1 = face_service.detect_faces(img1)
    faces2 = face_service.detect_faces(img2)

    if len(faces1) == 0 or len(faces2) == 0:
        return {
            "match": False,
            "distance": 1.0,
            "confidence": 0.0,
            "message": "未检测到人脸",
        }

    encoding1 = faces1[0]["encoding"]
    encoding2 = faces2[0]["encoding"]

    distance = face_recognition.face_distance([encoding1], encoding2)[0]
    confidence = 1 - distance

    match = confidence >= face_service.threshold

    return {
        "match": bool(match),
        "distance": float(distance),
        "confidence": float(confidence),
        "message": "匹配成功" if match else "不匹配",
    }
