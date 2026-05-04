// 每日统计（匹配后端 /api/statistics/daily 实际返回）
export interface DailyStats {
  date: string
  total_employees: number
  total_users?: number
  present_count: number
  absent_count: number
  action_breakdown: Record<string, number>
  attendance_rate: number
  check_in_count?: number
  check_out_count?: number
  attendance_count?: number
  success_count?: number
  fail_count?: number
  normal_count?: number
  late_count?: number
  early_count?: number
}

// 个人统计（匹配后端 /api/statistics/user/{id} 实际返回）
export interface UserStats {
  user_id: number
  period: { start: string; end: string }
  total_records: number
  work_days: number
  daily_summary: Record<string, { first: string | null; last: string | null }>
}

// 趋势数据单条
export interface TrendItem {
  date: string
  present: number
  absent: number
  rate: number
}

// 趋势响应
export interface TrendData {
  days: number
  total_employees: number
  trend: TrendItem[]
}
