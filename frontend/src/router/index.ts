import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { cancelPendingRequests } from '@/utils/request'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/Home.vue'),
    meta: { title: '首页' }
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '统计仪表盘', requiresAuth: true }
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/Register.vue'),
    meta: { title: '用户注册' }
  },
  {
    path: '/scan',
    name: 'scan',
    component: () => import('@/views/Scan.vue'),
    meta: { title: '实时刷脸' }
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '管理员登录', public: true }
  },
  {
    path: '/records',
    name: 'records',
    component: () => import('@/views/Records.vue'),
    meta: { title: '考勤记录', requiresAuth: true }
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('@/views/Users.vue'),
    meta: { title: '用户管理', requiresAuth: true }
  },
  {
    path: '/devices',
    name: 'devices',
    component: () => import('@/views/Devices.vue'),
    meta: { title: '设备管理', requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/Profile.vue'),
    meta: { title: '个人中心', requiresAuth: true }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: '页面未找到' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  cancelPendingRequests()

  const title = to.meta.title as string
  if (title) {
    document.title = `${title} - 人脸识别门禁系统`
  }

  if (to.meta.requiresAuth) {
    const token = localStorage.getItem('admin_token')
    if (!token) {
      next({ name: 'login', query: { redirect: to.fullPath } })
      return
    }

    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      if (payload.exp && payload.exp * 1000 < Date.now()) {
        localStorage.removeItem('admin_token')
        localStorage.removeItem('admin_role')
        localStorage.removeItem('admin_name')
        next({ name: 'login', query: { redirect: to.fullPath } })
        return
      }
    } catch {
      localStorage.removeItem('admin_token')
      next({ name: 'login', query: { redirect: to.fullPath } })
      return
    }
  }

  next()
})

export default router
