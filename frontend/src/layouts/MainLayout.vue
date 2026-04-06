<template>
  <div class="main-layout">
    <header class="header">
      <div class="logo">
        <el-icon :size="32"><Monitor /></el-icon>
        <span>人脸识别门禁系统</span>
      </div>
      <NavBar />
    </header>

    <main class="main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <footer class="footer">
      <p>&copy; 2026 Face Recognition Access Control System</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { Monitor } from '@element-plus/icons-vue'
import NavBar from '@/components/NavBar.vue'
</script>

<style scoped>
.main-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.header {
  display: flex;
  align-items: center;
  background-color: #545c64;
  padding: 0 20px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #fff;
  font-size: 18px;
  font-weight: bold;
  margin-right: 40px;
}

.main {
  flex: 1;
  padding: 20px;
  background-color: #f0f2f5;
  overflow: auto;
}

.footer {
  padding: 15px;
  text-align: center;
  background-color: #fff;
  color: #666;
  font-size: 14px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
