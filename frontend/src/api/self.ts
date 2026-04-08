import { get, del } from '@/utils/request'
import type { User } from '@/types/user'
import type { AttendanceListResponse } from '@/types/attendance'
import type { DailyStats } from '@/types/statistics'

export interface Profile extends User {
  role?: string
  department?: string
}

export function getProfile(): Promise<Profile> {
  return get('/api/self/profile')
}

export function getMyAttendance(params?: {
  days?: number
  page?: number
  page_size?: number
}): Promise<AttendanceListResponse> {
  return get('/api/self/attendance', params as Record<string, unknown>)
}

export function getTodayAttendance(): Promise<DailyStats> {
  return get('/api/self/attendance/today')
}

export function unregisterFace(): Promise<{ code: number; message: string }> {
  return del('/api/self/face')
}