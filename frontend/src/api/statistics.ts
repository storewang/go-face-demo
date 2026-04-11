import { get } from '@/utils/request'
import type { DailyStats, UserStats, TrendData } from '@/types/statistics'

export function getDailyStats(dateStr?: string): Promise<DailyStats> {
  const params = dateStr ? { date_str: dateStr } : undefined
  return get('/statistics/daily', params as Record<string, unknown>)
}

export function getUserStats(
  userId: number,
  params?: {
    start_date?: string
    end_date?: string
  }
): Promise<UserStats> {
  return get(`/statistics/user/${userId}`, params as Record<string, unknown>)
}

export function getTrend(days: number = 30): Promise<TrendData> {
  return get('/statistics/trend', { days } as Record<string, unknown>)
}