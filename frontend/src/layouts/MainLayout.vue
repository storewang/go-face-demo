<template>
  <div class="main-layout">
    <header class="header">
      <div class="logo">
        <el-icon :size="28"><Monitor /></el-icon>
        <span class="logo-text">人脸识别门禁系统</span>
      </div>

      <!-- 桌面端导航 -->
      <div class="desktop-nav">
        <NavBar />
      </div>

      <!-- 移动端汉堡按钮 -->
      <button class="hamburger-btn" @click="mobileMenuOpen = !mobileMenuOpen">
        <el-icon :size="24" color="#fff">
          <Close v-if="mobileMenuOpen" />
          <Operation v-else />
        </el-icon>
      </button>
    </header>

    <!-- 移动端抽屉菜单 -->
    <transition name="drawer-mask">
      <div v-if="mobileMenuOpen" class="mobile-mask" @click="mobileMenuOpen = false"></div>
    </transition>
    <transition name="drawer-slide">
      <div v-if="mobileMenuOpen" class="mobile-drawer">
        <div class="drawer-header">
          <span class="drawer-title">导航菜单</span>
          <el-icon :size="20" @click="mobileMenuOpen = false"><Close /></el-icon>
        </div>
        <div class="drawer-body">
          <NavBar :mobile="true" @navigate="mobileMenuOpen = false" />
        </div>
      </div>
    </transition>

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
import { ref } from 'vue'
import { Monitor, Close, Operation } from '@element-plus/icons-vue'
import NavBar from '@/components/NavBar.vue'

const mobileMenuOpen = ref(false)
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
  position: relative;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #fff;
  font-size: 18px;
  font-weight: bold;
  margin-right: 40px;
  flex-shrink: 0;
}

.desktop-nav {
  flex: 1;
  display: block;
}

.hamburger-btn {
  display: none;
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
  margin-left: auto;
}

.mobile-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 998;
}

.mobile-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 280px;
  background: #545c64;
  z-index: 999;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  color: #fff;
  font-size: 16px;
  font-weight: bold;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.drawer-header .el-icon {
  color: #fff;
  cursor: pointer;
}

.drawer-body {
  flex: 1;
  padding: 10px 0;
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

/* drawer transitions */
.drawer-mask-enter-active,
.drawer-mask-leave-active {
  transition: opacity 0.3s ease;
}
.drawer-mask-enter-from,
.drawer-mask-leave-to {
  opacity: 0;
}

.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform 0.3s ease;
}
.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(100%);
}

/* Mobile responsive */
@media (max-width: 768px) {
  .header {
    padding: 0 12px;
  }

  .logo {
    font-size: 15px;
    margin-right: 12px;
  }

  .logo .el-icon {
    --el-icon-size: 22px;
  }

  .desktop-nav {
    display: none;
  }

  .hamburger-btn {
    display: block;
  }

  .main {
    padding: 12px 8px;
  }

  .footer {
    padding: 10px;
    font-size: 12px;
  }
}
</style>
