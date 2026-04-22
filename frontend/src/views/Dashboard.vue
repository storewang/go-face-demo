<template>
  <div class="dashboard">
    <el-row class="mb-4">
      <el-col>
        <h2>统计仪表板</h2>
      </el-col>
    </el-row>

    <div v-if="loading" class="loading">加载中……</div>

    <template v-else-if="dailyStats">
      <el-row :gutter="20" class="stats-grid">
        <el-col :xs="12" :sm="8">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">总用户数</div>
            <el-statistic :value="dailyStats.total_employees" />
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="8">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">出勤人数</div>
            <el-statistic :value="dailyStats.present_count" />
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="8">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">缺勤人数</div>
            <el-statistic :value="dailyStats.absent_count" />
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="8">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">上班打卡</div>
            <el-statistic :value="dailyStats.action_breakdown?.CHECK_IN || 0" />
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="8">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">下班打卡</div>
            <el-statistic :value="dailyStats.action_breakdown?.CHECK_OUT || 0" />
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="8">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">出勤率</div>
            <el-statistic :value="dailyStats.attendance_rate" suffix="%" />
          </el-card>
        </el-col>
      </el-row>
      <!-- 实时更新指示器 -->
      <el-tag v-if="lastEvent" size="small" type="success" style="margin-left: 12px">实时更新中</el-tag>

      <el-row :gutter="20" class="quick-cards-section">
        <el-col :xs="12" :sm="6" v-for="item in quickCards" :key="item.path">
          <el-card shadow="hover" class="quick-card" @click="goto(item.path)">
            <div class="quick-content">
              <el-icon :size="isMobile ? 32 : 40" :color="item.color"><component :is="item.icon" /></el-icon>
              <h3>{{ item.title }}</h3>
              <p>{{ item.description }}</p>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" class="personal-status-section">
        <el-col :span="24">
          <el-card shadow="hover" class="personal-status">
            <div class="status-title">个人今日打卡状态</div>
            <div v-if="isLoggedIn">
              <el-tag :type="todayAttendance ? 'success' : 'warning'">
                {{ todayAttendance ? '已打卡' : '未打卡' }}
              </el-tag>
              <span v-if="todayAttendance" style="margin-left: 12px">
                签到: {{ dailyStats.action_breakdown?.CHECK_IN > 0 ? '已记录' : '--' }}
              </span>
            </div>
            <div v-else>
              <el-tag type="info">请先登录</el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { UserFilled, Camera, Document, User } from '@element-plus/icons-vue'
import type { DailyStats } from '@/types/statistics'
import { getDailyStats } from '@/api/statistics'
import { onBeforeUnmount } from 'vue'

const router = useRouter()
const isMobile = computed(() => window.innerWidth <= 768)

const dailyStats = ref<DailyStats | null>(null)
const loading = ref(false)
// Real-time events via SSE
let eventSource: EventSource | null = null
const lastEvent = ref<Record<string, unknown> | null>(null)

const quickCards = [
  { path: '/register', title: '用户注册', description: '录入新用户和人脸', icon: UserFilled, color: '#409EFF' },
  { path: '/scan', title: '实时刷脸', description: '门禁识别和打卡', icon: Camera, color: '#67C23A' },
  { path: '/records', title: '考勤记录', description: '查询和导出考勤', icon: Document, color: '#E6A23C' },
  { path: '/users', title: '用户管理', description: '管理已注册用户', icon: User, color: '#F56C6C' }
]

const goto = (path: string) => router.push(path)

const isLoggedIn = computed(() => !!localStorage.getItem('admin_token'))
const todayAttendance = computed(() => dailyStats.value ? dailyStats.value.present_count > 0 : false)

onMounted(async () => {
  loading.value = true
  try {
    const today = new Date().toISOString().split('T')[0]
    dailyStats.value = await getDailyStats(today)
  } catch (e) {
    console.error('获取每日统计失败', e)
  } finally {
    loading.value = false
  }
  // Connect to SSE stream for real-time updates
  connectSSE()
})

// Cleanup on unmount
onBeforeUnmount(() => {
  disconnectSSE()
})

function connectSSE() {
  try {
    const proto = window.location.protocol === 'https:' ? 'https:' : 'http:'
    const sseUrl = `${proto}//${window.location.host}/api/events/stream`
    eventSource = new EventSource(sseUrl)

    eventSource.addEventListener('face_recognized', (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data)
        lastEvent.value = { type: 'face_recognized', ...data }
        refreshStats()
      } catch (err) {
        console.error('解析人脸识别事件失败:', err)
      }
    })

    eventSource.addEventListener('attendance_recorded', (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data)
        lastEvent.value = { type: 'attendance_recorded', ...data }
        refreshStats()
      } catch (err) {
        console.error('解析考勤事件失败:', err)
      }
    })

    eventSource.addEventListener('system_alert', (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data)
        lastEvent.value = { type: 'system_alert', ...data }
      } catch (err) {
        console.error('解析系统事件失败:', err)
      }
    })

    eventSource.onerror = () => {
      console.warn('SSE 连接已关闭，后台将尝试重连')
    }
  } catch (err) {
    console.error('Failed to connect SSE:', err)
  }
}

function disconnectSSE() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

async function refreshStats() {
  try {
    const today = new Date().toISOString().split('T')[0]
    dailyStats.value = await getDailyStats(today)
  } catch (e) {
    console.error('刷新统计失败', e)
  }
}
</script>

<style scoped>
.dashboard {
  padding: 20px;
  max-width: 1200px;
}

.loading {
  text-align: center;
  color: #909399;
  padding: 40px;
}

.stats-grid {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
  padding: 20px;
}

.stat-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

.quick-cards-section,
.personal-status-section {
  margin-top: 20px;
}

.quick-card {
  cursor: pointer;
  transition: all 0.3s;
}

.quick-card:hover {
  transform: translateY(-5px);
}

.quick-content {
  text-align: center;
  padding: 10px;
}

.quick-content h3 {
  margin: 12px 0 8px;
  font-size: 16px;
}

.quick-content p {
  color: #999;
  font-size: 12px;
  margin: 0;
}

.personal-status {
  padding: 20px;
}

.status-title {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 12px;
}

/* Mobile responsive */
@media (max-width: 1024px) {
  .quick-cards-section .el-col {
    margin-bottom: 12px;
  }
}

@media (max-width: 768px) {
  .dashboard {
    padding: 12px 8px;
  }

  .stats-grid .el-col {
    margin-bottom: 12px;
  }

  .stat-card {
    padding: 12px 8px;
  }

  .stat-card :deep(.el-statistic__content) {
    font-size: 20px !important;
  }

  .stat-card :deep(.el-statistic__number) {
    font-size: 20px !important;
  }

  .quick-cards-section .el-col {
    margin-bottom: 8px;
  }

  .quick-content h3 {
    font-size: 14px;
  }

  .quick-content p {
    font-size: 11px;
    margin: 0;
  }

  .personal-status {
    padding: 16px;
  }

  .status-title {
    font-size: 15px;
  }
}
</style>
