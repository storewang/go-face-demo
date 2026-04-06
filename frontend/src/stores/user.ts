import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, UserCreateRequest } from '@/types/user'
import * as userApi from '@/api/user'

export const useUserStore = defineStore('user', () => {
  const users = ref<User[]>([])
  const currentUser = ref<User | null>(null)
  const loading = ref(false)

  const userCount = computed(() => users.value.length)
  const activeUsers = computed(() =>
    users.value.filter(u => u.status === 1)
  )

  async function fetchUsers(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const res = await userApi.getUsers(params)
      users.value = res.items
      return res
    } finally {
      loading.value = false
    }
  }

  async function createUser(data: UserCreateRequest) {
    loading.value = true
    try {
      const user = await userApi.createUser(data)
      users.value.push(user)
      return user
    } finally {
      loading.value = false
    }
  }

  async function deleteUser(id: number) {
    loading.value = true
    try {
      await userApi.deleteUser(id)
      users.value = users.value.filter(u => u.id !== id)
    } finally {
      loading.value = false
    }
  }

  function setCurrentUser(user: User | null) {
    currentUser.value = user
  }

  return {
    users,
    currentUser,
    loading,
    userCount,
    activeUsers,
    fetchUsers,
    createUser,
    deleteUser,
    setCurrentUser
  }
})
