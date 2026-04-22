/**
 * auth.test.ts — 认证 Store 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

// Mock the request module
vi.mock('@/utils/request', () => ({
  default: {
    post: vi.fn()
  },
  post: vi.fn()
}))

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value }),
    removeItem: vi.fn((key: string) => { delete store[key] }),
    clear: vi.fn(() => { store = {} }),
    get length() { return Object.keys(store).length },
    key: vi.fn((i: number) => Object.keys(store)[i] || null),
  }
})()
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock })

// Mock Element Plus (used by request interceptor)
vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn() }
}))

import { post } from '@/utils/request'

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorageMock.clear()
    vi.clearAllMocks()
  })

  it('初始状态应为未登录', () => {
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(false)
    expect(store.token).toBeNull()
    expect(store.role).toBeNull()
    expect(store.name).toBeNull()
  })

  it('isSuperAdmin 应正确判断', () => {
    const store = useAuthStore()
    store.$patch({ role: 'super_admin' })
    expect(store.isSuperAdmin).toBe(true)
    expect(store.isDeptAdmin).toBe(true)
  })

  it('isDeptAdmin 应包含 super_admin 和 dept_admin', () => {
    const store = useAuthStore()
    store.$patch({ role: 'dept_admin' })
    expect(store.isDeptAdmin).toBe(true)
    expect(store.isSuperAdmin).toBe(false)
  })

  it('普通员工不是管理员', () => {
    const store = useAuthStore()
    store.$patch({ role: 'employee' })
    expect(store.isSuperAdmin).toBe(false)
    expect(store.isDeptAdmin).toBe(false)
  })

  it('logout 应清除所有状态', () => {
    const store = useAuthStore()
    store.$patch({ token: 'test-token', role: 'super_admin', name: 'Admin' })

    store.logout()

    expect(store.token).toBeNull()
    expect(store.role).toBeNull()
    expect(store.name).toBeNull()
    expect(localStorage.removeItem).toHaveBeenCalledWith('admin_token')
    expect(localStorage.removeItem).toHaveBeenCalledWith('admin_role')
    expect(localStorage.removeItem).toHaveBeenCalledWith('admin_name')
  })

  it('login 成功应存储 token 和角色', async () => {
    const mockPost = vi.mocked(post)
    mockPost.mockResolvedValueOnce({
      code: 200,
      data: { token: 'jwt-abc', role: 'super_admin', name: '管理员' },
      message: 'ok'
    })

    const store = useAuthStore()
    await store.login('correct_password')

    expect(store.token).toBe('jwt-abc')
    expect(store.role).toBe('super_admin')
    expect(store.name).toBe('管理员')
    expect(store.isLoggedIn).toBe(true)
  })

  it('login 失败应抛出异常', async () => {
    const mockPost = vi.mocked(post)
    mockPost.mockRejectedValueOnce(new Error('密码错误'))

    const store = useAuthStore()
    await expect(store.login('wrong')).rejects.toThrow('密码错误')
    expect(store.token).toBeNull()
  })
})
