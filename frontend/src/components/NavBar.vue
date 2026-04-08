<template>
  <el-menu
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

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const activeIndex = computed(() => route.path)

const handleSelect = (index: string) => {
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
</style>
