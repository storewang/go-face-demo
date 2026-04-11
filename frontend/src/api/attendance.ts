import { get, post, download } from '@/utils/request'
import type { AttendanceListResponse, AttendanceStats, CheckInResponse } from '@/types/attendance'

export function getAttendance(params?: {
  page?: number
  page_size?: number
  start_date?: string
  end_date?: string
  employee_id?: string
  action_type?: string
  result?: string
}): Promise<AttendanceListResponse> {
  return get('/attendance', params as Record<string, unknown>)
}

export function checkIn(image: File, employeeId?: string): Promise<CheckInResponse> {
  const formData = new FormData()
  formData.append('image', image)
  if (employeeId) {
    formData.append('employee_id', employeeId)
  }

  return post('/attendance/check-in', formData)
}

export function checkOut(image: File, employeeId?: string): Promise<CheckInResponse> {
  const formData = new FormData()
  formData.append('image', image)
  if (employeeId) {
    formData.append('employee_id', employeeId)
  }

  return post('/attendance/check-out', formData)
}

export function exportAttendance(params: {
  start_date: string
  end_date: string
  employee_id?: string
  format?: string
}): Promise<Blob> {
  return download('/attendance/export', params as Record<string, unknown>)
}

export function getStats(params?: {
  start_date?: string
  end_date?: string
}): Promise<AttendanceStats> {
  return get('/attendance/stats', params as Record<string, unknown>)
}
