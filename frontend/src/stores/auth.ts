import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { post } from '@/utils/request'
import type { UserRole } from '@/types/user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('admin_token'))
  const role = ref<UserRole | null>(localStorage.getItem('admin_role') as UserRole | null)
  const name = ref<string | null>(localStorage.getItem('admin_name'))
  const loggingIn = ref(false)

  const isLoggedIn = computed(() => !!token.value)
  const isSuperAdmin = computed(() => role.value === 'super_admin')
  const isDeptAdmin = computed(() => role.value === 'dept_admin' || role.value === 'super_admin')

  async function login(password: string): Promise<void> {
    loggingIn.value = true
    try {
      const res = await post<{ code: number; data: { token: string; role: UserRole; name: string }; message: string }>(
        '/auth/login',
        { password }
      )
      token.value = res.data.token
      role.value = res.data.role
      name.value = res.data.name
      localStorage.setItem('admin_token', res.data.token)
      localStorage.setItem('admin_role', res.data.role)
      localStorage.setItem('admin_name', res.data.name)
    } finally {
      loggingIn.value = false
    }
  }

  function logout(): void {
    token.value = null
    role.value = null
    name.value = null
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_role')
    localStorage.removeItem('admin_name')
  }

  return {
    token,
    role,
    name,
    isLoggedIn,
    isSuperAdmin,
    isDeptAdmin,
    loggingIn,
    login,
    logout
  }
})
