// 每日统计
export interface DailyStats {
  date: string
  total_users: number
  check_in_count: number
  check_out_count: number
  attendance_count: number
  success_count: number
  fail_count: number
  normal_count: number
  late_count: number
  early_count: number
  absent_count: number
}

// 个人统计
export interface UserStats {
  user_id: number
  user_name: string
  attendance_count: number
  normal_count: number
  late_count: number
  early_count: number
  absent_count: number
  success_rate: number
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