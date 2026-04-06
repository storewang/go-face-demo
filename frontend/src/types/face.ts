export interface FaceDetectResponse {
  faces_detected: number
  faces: Array<{
    box: { top: number; right: number; bottom: number; left: number }
    quality: string
  }>
}

export interface FaceVerifyResponse {
  success: boolean
  user?: {
    id: number
    employee_id: string
    name: string
    department?: string
  }
  confidence: number
  liveness_passed?: boolean
  reason?: string
}
