<template>
  <div class="records-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>考勤记录</span>
          <el-button type="primary" @click="exportToExcel" :loading="exporting">
            <el-icon><Download /></el-icon>
            导出 Excel
          </el-button>
        </div>
      </template>

      <el-form :inline="true" :model="queryParams" class="filter-form">
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="handleDateChange"
          />
        </el-form-item>

        <el-form-item label="工号/姓名">
          <el-input
            v-model="queryParams.employee_id"
            placeholder="请输入工号或姓名"
            clearable
            @keyup.enter="fetchRecords"
          />
        </el-form-item>

        <el-form-item label="打卡类型">
          <el-select
            v-model="queryParams.action_type"
            placeholder="全部"
            clearable
          >
            <el-option label="上班" value="CHECK_IN" />
            <el-option label="下班" value="CHECK_OUT" />
          </el-select>
        </el-form-item>

        <el-form-item label="结果">
          <el-select
            v-model="queryParams.result"
            placeholder="全部"
            clearable
          >
            <el-option label="成功" value="SUCCESS" />
            <el-option label="失败" value="FAILED" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="fetchRecords">
            <el-icon><Search /></el-icon>
            查询
          </el-button>

          <el-button @click="resetQuery">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>

      <el-table
        :data="records"
        v-loading="loading"
        stripe
        border
        style="width: 100%"
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="employee_id" label="工号" width="120" />
        <el-table-column prop="name" label="姓名" width="120" />

        <el-table-column prop="action_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.action_type === 'CHECK_IN' ? 'success' : 'warning'">
              {{ row.action_type === 'CHECK_IN' ? '上班' : '下班' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="result" label="结果" width="100">
          <template #default="{ row }">
            <el-tag :type="row.result === 'SUCCESS' ? 'success' : 'danger'">
              {{ row.result === 'SUCCESS' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="confidence" label="置信度" width="150">
          <template #default="{ row }">
            <el-progress
              v-if="row.confidence"
              :percentage="Math.round(row.confidence * 100)"
              :color="getConfidenceColor(row.confidence)"
            />
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewDetail(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.page_size"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchRecords"
          @current-change="fetchRecords"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="detailVisible"
      title="考勤详情"
      width="500px"
    >
      <el-descriptions :column="1" border>
        <el-descriptions-item label="记录ID">
          {{ currentRecord?.id }}
        </el-descriptions-item>
        <el-descriptions-item label="工号">
          {{ currentRecord?.employee_id }}
        </el-descriptions-item>
        <el-descriptions-item label="姓名">
          {{ currentRecord?.name }}
        </el-descriptions-item>
        <el-descriptions-item label="打卡类型">
          {{ currentRecord?.action_type === 'CHECK_IN' ? '上班' : '下班' }}
        </el-descriptions-item>
        <el-descriptions-item label="识别结果">
          <el-tag :type="currentRecord?.result === 'SUCCESS' ? 'success' : 'danger'">
            {{ currentRecord?.result === 'SUCCESS' ? '成功' : '失败' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="置信度">
          {{ currentRecord?.confidence ? (currentRecord.confidence * 100).toFixed(2) + '%' : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="打卡时间">
          {{ formatDateTime(currentRecord?.created_at) }}
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Search, Refresh } from '@element-plus/icons-vue'
import * as attendanceApi from '@/api/attendance'
import type { AttendanceRecord } from '@/types/attendance'

const loading = ref(false)
const exporting = ref(false)
const records = ref<AttendanceRecord[]>([])
const total = ref(0)

const dateRange = ref<string[]>([])
const queryParams = reactive({
  page: 1,
  page_size: 20,
  start_date: '',
  end_date: '',
  employee_id: '',
  action_type: '',
  result: ''
})

const detailVisible = ref(false)
const currentRecord = ref<AttendanceRecord | null>(null)

onMounted(() => {
  const now = new Date()
  const firstDay = new Date(now.getFullYear(), now.getMonth(), 1)
  const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0)

  dateRange.value = [
    formatDate(firstDay),
    formatDate(lastDay)
  ]

  handleDateChange(dateRange.value)
  fetchRecords()
})

function handleDateChange(val: string[] | null) {
  if (val && val.length === 2) {
    queryParams.start_date = val[0]
    queryParams.end_date = val[1]
  } else {
    queryParams.start_date = ''
    queryParams.end_date = ''
  }
}

async function fetchRecords() {
  loading.value = true

  try {
    const res = await attendanceApi.getAttendance(queryParams)
    records.value = res.items
    total.value = res.total
  } catch (error: unknown) {
    const err = error as Error
    ElMessage.error('获取记录失败: ' + err.message)
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  dateRange.value = []
  queryParams.page = 1
  queryParams.start_date = ''
  queryParams.end_date = ''
  queryParams.employee_id = ''
  queryParams.action_type = ''
  queryParams.result = ''

  fetchRecords()
}

async function exportToExcel() {
  if (!queryParams.start_date || !queryParams.end_date) {
    ElMessage.warning('请选择日期范围')
    return
  }

  exporting.value = true

  try {
    const blob = await attendanceApi.exportAttendance({
      start_date: queryParams.start_date,
      end_date: queryParams.end_date,
      employee_id: queryParams.employee_id || undefined,
      format: 'detail'
    })

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `attendance_${queryParams.start_date}_${queryParams.end_date}.xlsx`
    link.click()

    window.URL.revokeObjectURL(url)

    ElMessage.success('导出成功')
  } catch (error: unknown) {
    const err = error as Error
    ElMessage.error('导出失败: ' + err.message)
  } finally {
    exporting.value = false
  }
}

function viewDetail(record: AttendanceRecord) {
  currentRecord.value = record
  detailVisible.value = true
}

function formatDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatDateTime(datetime?: string): string {
  if (!datetime) return '-'

  const date = new Date(datetime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return '#67C23A'
  if (confidence >= 0.6) return '#E6A23C'
  return '#F56C6C'
}
</script>

<style scoped>
.records-page {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-form {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
