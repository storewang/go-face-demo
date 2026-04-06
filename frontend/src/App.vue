<template>
  <div id="app">
    <el-config-provider :locale="zhCn">
      <MainLayout />
    </el-config-provider>
  </div>
</template>

<script setup lang="ts">
import { ElConfigProvider } from 'element-plus'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import MainLayout from '@/layouts/MainLayout.vue'
</script>

<style>
#app {
  width: 100%;
  height: 100vh;
}
</style>
