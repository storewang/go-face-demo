import { get, del } from '@/utils/request'
import type { UserRole } from '@/types/user'
import type { AttendanceListResponse } from '@/types/attendance'
import type { DailyStats } from '@/types/statistics'

export interface Profile {
  id: number
  employee_id: string
  name: string
  department?: string
  status: number
  role?: UserRole | string
  face_encoding_path?: string
  face_image_path?: string
  created_at?: string
  updated_at?: string
}

export function getProfile(): Promise<Profile> {
  return get('/self/profile')
}

export function getMyAttendance(params?: {
  days?: number
  page?: number
  page_size?: number
}): Promise<AttendanceListResponse> {
  return get('/self/attendance', params as Record<string, unknown>)
}

export function getTodayAttendance(): Promise<DailyStats> {
  return get('/self/attendance/today')
}

export function unregisterFace(): Promise<{ code: number; message: string }> {
  return del('/self/face')
}