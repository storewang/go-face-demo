<template>
  <div class="home">
    <el-row :gutter="20">
      <el-col :xs="12" :sm="6" v-for="item in menuItems" :key="item.path">
        <el-card
          class="menu-card"
          shadow="hover"
          @click="$router.push(item.path)"
        >
          <div class="card-content">
            <el-icon :size="48" :color="item.color">
              <component :is="item.icon" />
            </el-icon>
            <h3>{{ item.title }}</h3>
            <p>{{ item.description }}</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="stats-section">
      <el-col :xs="12" :sm="6">
        <el-card class="stat-card">
          <el-statistic title="注册用户" :value="stats.userCount">
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card class="stat-card">
          <el-statistic title="上班打卡" :value="stats.checkInCount">
            <template #prefix>
              <el-icon><Clock /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card class="stat-card">
          <el-statistic title="下班打卡" :value="stats.checkOutCount">
            <template #prefix>
              <el-icon><Clock /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card class="stat-card">
          <el-statistic title="识别成功" :value="stats.successRate" suffix="%">
            <template #prefix>
              <el-icon><SuccessFilled /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  UserFilled,
  Camera,
  Document,
  User,
  Clock,
  SuccessFilled
} from '@element-plus/icons-vue'
import * as userApi from '@/api/user'
import * as statisticsApi from '@/api/statistics'

const menuItems = [
  {
    path: '/register',
    title: '用户注册',
    description: '录入新用户和人脸信息',
    icon: UserFilled,
    color: '#409EFF'
  },
  {
    path: '/scan',
    title: '实时刷脸',
    description: '门禁识别和打卡',
    icon: Camera,
    color: '#67C23A'
  },
  {
    path: '/records',
    title: '考勤记录',
    description: '查询和导出考勤',
    icon: Document,
    color: '#E6A23C'
  },
  {
    path: '/users',
    title: '用户管理',
    description: '管理已注册用户',
    icon: User,
    color: '#F56C6C'
  }
]

const stats = ref({
  userCount: 0,
  checkInCount: 0,
  checkOutCount: 0,
  successRate: 0
})

onMounted(async () => {
  try {
    const [users, dailyStats] = await Promise.all([
      userApi.getUsers({ page: 1, page_size: 1 }),
      statisticsApi.getDailyStats()
    ])

    stats.value.userCount = dailyStats.total_employees
    stats.value.checkInCount = dailyStats.action_breakdown?.CHECK_IN || 0
    stats.value.checkOutCount = dailyStats.action_breakdown?.CHECK_OUT || 0

    const totalAttendance = (dailyStats.action_breakdown?.CHECK_IN || 0) + (dailyStats.action_breakdown?.CHECK_OUT || 0)
    if (totalAttendance > 0) {
      stats.value.successRate = dailyStats.attendance_rate
    }
  } catch {
    // 静默处理，显示默认值 0
  }
})
</script>

<style scoped>
.home {
  max-width: 1200px;
  margin: 0 auto;
}

.menu-card {
  cursor: pointer;
  transition: all 0.3s;
}

.menu-card:hover {
  transform: translateY(-5px);
}

.card-content {
  text-align: center;
  padding: 20px;
}

.card-content h3 {
  margin: 15px 0 10px;
  font-size: 18px;
}

.card-content p {
  color: #999;
  font-size: 14px;
}

.stat-card {
  text-align: center;
}

.stats-section {
  margin-top: 20px;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .card-content h3 {
    font-size: 16px;
  }

  .card-content p {
    font-size: 12px;
  }

  .stat-card :deep(.el-statistic__content) {
    font-size: 24px !important;
  }

  .card-content .el-icon {
    --el-icon-size: 40px;
  }
}
</style>
