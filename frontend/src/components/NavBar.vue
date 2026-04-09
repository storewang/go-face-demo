<template>
  <!-- 桌面端水平菜单 -->
  <el-menu
    v-if="!mobile"
    :default-active="activeIndex"
    mode="horizontal"
    @select="handleSelect"
    background-color="#545c64"
    text-color="#fff"
    active-text-color="#ffd04b"
  >
    <el-menu-item index="/">
      <el-icon><HomeFilled /></el-icon>
      <span>首页</span>
    </el-menu-item>

    <el-menu-item index="/dashboard">
      <el-icon><DataAnalysis /></el-icon>
      <span>统计</span>
    </el-menu-item>

    <el-menu-item index="/register">
      <el-icon><UserFilled /></el-icon>
      <span>用户注册</span>
    </el-menu-item>

    <el-menu-item index="/scan">
      <el-icon><Camera /></el-icon>
      <span>实时刷脸</span>
    </el-menu-item>

    <el-menu-item v-if="authStore.isLoggedIn" index="/records">
      <el-icon><Document /></el-icon>
      <span>考勤记录</span>
    </el-menu-item>

    <el-menu-item v-if="authStore.isLoggedIn" index="/devices">
      <el-icon><Monitor /></el-icon>
      <span>设备管理</span>
    </el-menu-item>

    <el-menu-item v-if="authStore.isLoggedIn" index="/users">
      <el-icon><User /></el-icon>
      <span>用户管理</span>
    </el-menu-item>

    <el-menu-item v-if="authStore.isLoggedIn" index="/profile">
      <el-icon><Avatar /></el-icon>
      <span>个人中心</span>
    </el-menu-item>

    <div class="nav-right">
      <el-menu-item v-if="authStore.isLoggedIn && authStore.name" disabled class="user-info">
        <span>{{ authStore.name }} ({{ authStore.role === 'super_admin' ? '超级管理员' : authStore.role === 'dept_admin' ? '部门管理员' : '员工' }})</span>
      </el-menu-item>
      <el-menu-item v-if="authStore.isLoggedIn" index="logout" class="logout-item">
        <el-icon><SwitchButton /></el-icon>
        <span>退出</span>
      </el-menu-item>
      <el-menu-item v-else index="/login">
        <el-icon><Lock /></el-icon>
        <span>登录</span>
      </el-menu-item>
    </div>
  </el-menu>

  <!-- 移动端垂直菜单 -->
  <div v-else class="mobile-nav">
    <div
      v-for="item in menuItems"
      :key="item.index"
      class="mobile-nav-item"
      :class="{ active: activeIndex === item.index }"
      @click="handleSelect(item.index)"
    >
      <el-icon :size="20"><component :is="item.icon" /></el-icon>
      <span class="mobile-nav-label">{{ item.label }}</span>
    </div>

    <div class="mobile-nav-divider"></div>

    <div v-if="authStore.isLoggedIn && authStore.name" class="mobile-nav-item user-info-mobile">
      <el-icon :size="20"><Avatar /></el-icon>
      <span class="mobile-nav-label">{{ authStore.name }} ({{ authStore.role === 'super_admin' ? '超管' : authStore.role === 'dept_admin' ? '部门管理' : '员工' }})</span>
    </div>

    <div
      v-if="authStore.isLoggedIn"
      class="mobile-nav-item"
      @click="handleSelect('logout')"
    >
      <el-icon :size="20"><SwitchButton /></el-icon>
      <span class="mobile-nav-label">退出登录</span>
    </div>

    <div
      v-else
      class="mobile-nav-item"
      @click="handleSelect('/login')"
    >
      <el-icon :size="20"><Lock /></el-icon>
      <span class="mobile-nav-label">登录</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  HomeFilled,
  UserFilled,
  Camera,
  Document,
  User,
  Lock,
  SwitchButton,
  DataAnalysis,
  Monitor,
  Avatar
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

defineProps<{
  mobile?: boolean
}>()

const emit = defineEmits<{
  (e: 'navigate'): void
}>()

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const activeIndex = computed(() => route.path)

const menuItems = computed(() => {
  const items = [
    { index: '/', label: '首页', icon: HomeFilled },
    { index: '/dashboard', label: '统计', icon: DataAnalysis },
    { index: '/register', label: '用户注册', icon: UserFilled },
    { index: '/scan', label: '实时刷脸', icon: Camera },
  ]
  if (authStore.isLoggedIn) {
    items.push(
      { index: '/records', label: '考勤记录', icon: Document },
      { index: '/devices', label: '设备管理', icon: Monitor },
      { index: '/users', label: '用户管理', icon: User },
      { index: '/profile', label: '个人中心', icon: Avatar },
    )
  }
  return items
})

const handleSelect = (index: string) => {
  emit('navigate')
  if (index === 'logout') {
    authStore.logout()
    router.push('/')
    return
  }
  router.push(index)
}
</script>

<style scoped>
.el-menu {
  border-bottom: none;
}

.nav-right {
  margin-left: auto;
}

/* Mobile nav styles */
.mobile-nav {
  display: flex;
  flex-direction: column;
}

.mobile-nav-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 20px;
  color: #fff;
  font-size: 15px;
  cursor: pointer;
  transition: background-color 0.2s;
  border-radius: 6px;
  margin: 2px 8px;
}

.mobile-nav-item:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.mobile-nav-item.active {
  background-color: rgba(255, 208, 75, 0.15);
  color: #ffd04b;
}

.mobile-nav-item.user-info-mobile {
  cursor: default;
  opacity: 0.7;
  font-size: 13px;
}

.mobile-nav-label {
  flex: 1;
}

.mobile-nav-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
  margin: 6px 20px;
}
</style>
