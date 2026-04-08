<template>
  <div class="profile-page">
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>个人信息</span>
            </div>
          </template>
          <el-descriptions :column="1" border v-loading="loading">
            <el-descriptions-item label="工号">{{ profile?.employee_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="姓名">{{ profile?.name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="部门">{{ profile?.department || '-' }}</el-descriptions-item>
            <el-descriptions-item label="角色">
              <el-tag :type="roleTagType(profile?.role)" size="small">
                {{ roleText(profile?.role) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="人脸状态">
              <el-tag :type="profile?.face_encoding_path ? 'success' : 'danger'" size="small">
                {{ profile?.face_encoding_path ? '已录入' : '未录入' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>今日考勤状态</span>
            </div>
          </template>
          <div v-loading="loading">
            <el-row :gutter="20">
              <el-col :span="12">
                <div class="status-item">
                  <div class="status-label">上班打卡</div>
                  <div class="status-value">
                    <el-tag :type="todayStats?.check_in_count ? 'success' : 'info'">
                      {{ todayStats?.check_in_count ? '已打卡' : '未打卡' }}
                    </el-tag>
                  </div>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="status-item">
                  <div class="status-label">下班打卡</div>
                  <div class="status-value">
                    <el-tag :type="todayStats?.check_out_count ? 'success' : 'info'">
                      {{ todayStats?.check_out_count ? '已打卡' : '未打卡' }}
                    </el-tag>
                  </div>
                </div>
              </el-col>
            </el-row>
            <el-divider />
            <div class="status-item">
              <div class="status-label">考勤状态</div>
              <div class="status-value">
                <el-tag v-if="todayStats?.success_count" type="success">正常</el-tag>
                <el-tag v-else-if="todayStats?.late_count" type="warning">迟到</el-tag>
                <el-tag v-else-if="todayStats?.absent_count" type="danger">缺勤</el-tag>
                <el-tag v-else type="info">暂无记录</el-tag>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>最近考勤记录</span>
        </div>
      </template>
      <el-table :data="recentRecords" v-loading="loading" stripe border>
        <el-table-column prop="action_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag>{{ row.action_type === 'check_in' ? '上班' : '下班' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="result" label="结果" width="100">
          <template #default="{ row }">
            <el-tag :type="row.result === 'success' ? 'success' : 'danger'">
              {{ row.result === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top: 20px">
      <el-button type="danger" @click="handleUnregisterFace" :loading="unregistering">
        注销人脸
      </el-button>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProfile, getMyAttendance, unregisterFace, type Profile } from '@/api/self'
import type { DailyStats } from '@/types/statistics'
import type { AttendanceListResponse } from '@/types/attendance'

const loading = ref(false)
const unregistering = ref(false)
const profile = ref<Profile | null>(null)
const todayStats = ref<DailyStats | null>(null)
const recentRecords = ref<AttendanceListResponse['items']>([])

function roleText(role?: string): string {
  switch (role) {
    case 'super_admin': return '超级管理员'
    case 'dept_admin': return '部门管理员'
    case 'employee': return '员工'
    default: return '未知'
  }
}

function roleTagType(role?: string): string {
  switch (role) {
    case 'super_admin': return 'danger'
    case 'dept_admin': return 'warning'
    case 'employee': return 'success'
    default: return 'info'
  }
}

function formatDateTime(datetime?: string): string {
  if (!datetime) return '-'
  const date = new Date(datetime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function fetchData() {
  loading.value = true
  try {
    const [profileData, attendanceData] = await Promise.all([
      getProfile(),
      getMyAttendance({ days: 7 })
    ])
    profile.value = profileData
    recentRecords.value = attendanceData.items

    const today = new Date().toISOString().split('T')[0]
    if (attendanceData.items.length > 0) {
      const todayRecords = attendanceData.items.filter(
        (r) => r.created_at?.startsWith(today)
      )
      todayStats.value = {
        date: today,
        total_users: 0,
        check_in_count: todayRecords.filter((r) => r.action_type === 'check_in').length,
        check_out_count: todayRecords.filter((r) => r.action_type === 'check_out').length,
        attendance_count: todayRecords.length,
        success_count: todayRecords.filter((r) => r.result === 'success').length,
        fail_count: todayRecords.filter((r) => r.result !== 'success').length,
        normal_count: 0,
        late_count: 0,
        early_count: 0,
        absent_count: 0
      }
    }
  } catch (e) {
    console.error('获取个人信息失败', e)
  } finally {
    loading.value = false
  }
}

async function handleUnregisterFace() {
  try {
    await ElMessageBox.confirm(
      '确定要注销人脸吗？注销后需要重新录入才能使用刷脸功能。',
      '确认注销',
      { confirmButtonText: '确定注销', cancelButtonText: '取消', type: 'warning' }
    )
    await ElMessageBox.confirm(
      '此操作不可恢复，确定继续吗？',
      '二次确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'error' }
    )
    await unregisterFace()
    ElMessage.success('人脸已注销')
    await fetchData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('注销失败')
    }
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.profile-page {
  padding: 20px;
  max-width: 1200px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 500;
}

.status-item {
  padding: 12px 0;
}

.status-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

.status-value {
  font-size: 16px;
  font-weight: 500;
}
</style>