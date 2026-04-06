<template>
  <div class="home">
    <el-row :gutter="20">
      <el-col :span="6" v-for="item in menuItems" :key="item.path">
        <el-card
          class="menu-card"
          shadow="hover"
          @click="$router.push(item.path)"
        >
          <div class="card-content">
            <el-icon :size="60" :color="item.color">
              <component :is="item.icon" />
            </el-icon>
            <h3>{{ item.title }}</h3>
            <p>{{ item.description }}</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 30px">
      <el-col :span="8">
        <el-card class="stat-card">
          <el-statistic title="注册用户" :value="stats.userCount">
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <el-statistic title="今日打卡" :value="stats.todayCount">
            <template #prefix>
              <el-icon><Clock /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <el-statistic title="识别成功率" :value="stats.successRate" suffix="%">
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
import * as attendanceApi from '@/api/attendance'

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
  todayCount: 0,
  successRate: 0
})

onMounted(async () => {
  try {
    const [users, attendanceStats] = await Promise.all([
      userApi.getUsers({ page: 1, page_size: 1 }),
      attendanceApi.getStats()
    ])

    stats.value.userCount = users.total

    const today = new Date().toISOString().split('T')[0]
    const todayStats = await attendanceApi.getStats({
      start_date: today,
      end_date: today
    })
    stats.value.todayCount = todayStats.total_records

    if (attendanceStats.total_records > 0) {
      stats.value.successRate = Number(
        ((attendanceStats.success_count / attendanceStats.total_records) * 100).toFixed(1)
      )
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
</style>
