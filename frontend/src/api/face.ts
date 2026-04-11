import { upload } from '@/utils/request'
import type { FaceDetectResponse, FaceVerifyResponse } from '@/types/face'

export function detectFace(image: File): Promise<FaceDetectResponse> {
  return upload('/face/detect', image, 'image')
}

export function recognizeFace(image: File): Promise<FaceVerifyResponse> {
  return upload('/face/recognize', image, 'image')
}

export function registerFace(userId: number, image: File): Promise<{
  success: boolean
  user_id: number
  face_detected: boolean
  face_quality: string | null
  message: string
}> {
  return upload(`/face/register/${userId}`, image, 'image')
}
