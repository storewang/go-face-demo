import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AttendanceRecord, AttendanceStats } from '@/types/attendance'
import * as attendanceApi from '@/api/attendance'

export const useAttendanceStore = defineStore('attendance', () => {
  const records = ref<AttendanceRecord[]>([])
  const stats = ref<AttendanceStats>({
    total_records: 0,
    success_count: 0,
    failed_count: 0,
    unique_users: 0,
    avg_confidence: 0
  })
  const loading = ref(false)

  const todayRecords = computed(() => {
    const today = new Date().toDateString()
    return records.value.filter(r =>
      new Date(r.created_at).toDateString() === today
    )
  })

  async function fetchRecords(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const res = await attendanceApi.getAttendance(params)
      records.value = res.items
      return res
    } finally {
      loading.value = false
    }
  }

  async function fetchStats(params?: Record<string, unknown>) {
    try {
      const data = await attendanceApi.getStats(params)
      stats.value = data
    } catch (error) {
      console.error('Failed to fetch stats:', error)
    }
  }

  async function exportExcel(params: { start_date: string; end_date: string; employee_id?: string; format?: string }) {
    try {
      const blob = await attendanceApi.exportAttendance(params)
      return blob
    } catch (error) {
      console.error('Failed to export:', error)
      throw error
    }
  }

  return {
    records,
    stats,
    loading,
    todayRecords,
    fetchRecords,
    fetchStats,
    exportExcel
  }
})
