import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { post } from '@/utils/request'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('admin_token'))
  const loggingIn = ref(false)

  const isLoggedIn = computed(() => !!token.value)

  async function login(password: string): Promise<void> {
    loggingIn.value = true
    try {
      const res = await post<{ code: number; data: { token: string }; message: string }>(
        '/api/auth/login',
        { password }
      )
      token.value = res.data.token
      localStorage.setItem('admin_token', res.data.token)
    } finally {
      loggingIn.value = false
    }
  }

  function logout(): void {
    token.value = null
    localStorage.removeItem('admin_token')
  }

  return {
    token,
    isLoggedIn,
    loggingIn,
    login,
    logout
  }
})
