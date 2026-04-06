export type ActionType = 'CHECK_IN' | 'CHECK_OUT'
export type ResultType = 'SUCCESS' | 'FAILED'

export interface AttendanceRecord {
  id: number
  user_id?: number
  employee_id?: string
  name?: string
  action_type: ActionType
  confidence?: number
  snapshot_path?: string
  result: ResultType
  created_at: string
}

export interface AttendanceListResponse {
  items: AttendanceRecord[]
  total: number
  page: number
  page_size: number
}

export interface AttendanceStats {
  total_records: number
  success_count: number
  failed_count: number
  unique_users: number
  avg_confidence: number
}

export interface CheckInResponse {
  success: boolean
  action_type: string
  user?: {
    id: number
    employee_id: string
    name: string
  }
  confidence?: number
  message: string
  record_id?: number
}
