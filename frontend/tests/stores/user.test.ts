/**
 * user.test.ts — 用户 Store 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUserStore } from '@/stores/user'
import type { User } from '@/types/user'

// Mock API module
vi.mock('@/api/user', () => ({
  getUsers: vi.fn(),
  createUser: vi.fn(),
  deleteUser: vi.fn(),
}))

// Mock Element Plus
vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn() }
}))

import * as userApi from '@/api/user'

describe('useUserStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('初始状态应为空', () => {
    const store = useUserStore()
    expect(store.users).toEqual([])
    expect(store.currentUser).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.userCount).toBe(0)
    expect(store.activeUsers).toEqual([])
  })

  it('fetchUsers 应填充用户列表', async () => {
    const mockUsers: User[] = [
      { id: 1, employee_id: 'E001', name: '张三', department: 'IT', status: 1, created_at: '' } as User,
      { id: 2, employee_id: 'E002', name: '李四', department: 'HR', status: 0, created_at: '' } as User,
    ]
    vi.mocked(userApi.getUsers).mockResolvedValueOnce({ items: mockUsers, total: 2 })

    const store = useUserStore()
    await store.fetchUsers()

    expect(store.users.length).toBe(2)
    expect(store.userCount).toBe(2)
  })

  it('activeUsers 应只返回 status=1 的用户', async () => {
    const mockUsers: User[] = [
      { id: 1, employee_id: 'E001', name: '张三', department: 'IT', status: 1, created_at: '' } as User,
      { id: 2, employee_id: 'E002', name: '李四', department: 'HR', status: 0, created_at: '' } as User,
    ]
    vi.mocked(userApi.getUsers).mockResolvedValueOnce({ items: mockUsers, total: 2 })

    const store = useUserStore()
    await store.fetchUsers()

    expect(store.activeUsers.length).toBe(1)
    expect(store.activeUsers[0].name).toBe('张三')
  })

  it('deleteUser 应从列表移除用户', async () => {
    const mockUsers: User[] = [
      { id: 1, employee_id: 'E001', name: '张三', department: 'IT', status: 1, created_at: '' } as User,
    ]
    vi.mocked(userApi.getUsers).mockResolvedValueOnce({ items: mockUsers, total: 1 })
    vi.mocked(userApi.deleteUser).mockResolvedValueOnce(undefined)

    const store = useUserStore()
    await store.fetchUsers()
    expect(store.userCount).toBe(1)

    await store.deleteUser(1)
    expect(store.userCount).toBe(0)
  })

  it('setCurrentUser 应设置当前用户', () => {
    const store = useUserStore()
    const user = { id: 1, name: 'Test' } as User
    store.setCurrentUser(user)
    expect(store.currentUser).toEqual(user)

    store.setCurrentUser(null)
    expect(store.currentUser).toBeNull()
  })

  it('fetchUsers 期间 loading 应为 true', async () => {
    let resolvePromise: (value: unknown) => void
    const pending = new Promise((resolve) => { resolvePromise = resolve })
    vi.mocked(userApi.getUsers).mockReturnValueOnce(pending as never)

    const store = useUserStore()
    const fetchPromise = store.fetchUsers()

    expect(store.loading).toBe(true)

    resolvePromise!({ items: [], total: 0 })
    await fetchPromise

    expect(store.loading).toBe(false)
  })
})
