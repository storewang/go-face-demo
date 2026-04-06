import { get, post, upload, del } from '@/utils/request'
import type { User, UserListResponse } from '@/types/user'

export function getUsers(params?: {
  page?: number
  page_size?: number
  department?: string
  status?: number
}): Promise<UserListResponse> {
  return get('/api/users', params as Record<string, unknown>)
}

export function getUser(id: number): Promise<User> {
  return get(`/api/users/${id}`)
}

export function createUser(data: {
  employee_id: string
  name: string
  department?: string
  face_image?: File
}): Promise<User> {
  const formData = new FormData()
  formData.append('employee_id', data.employee_id)
  formData.append('name', data.name)

  if (data.department) {
    formData.append('department', data.department)
  }

  if (data.face_image) {
    formData.append('face_image', data.face_image)
  }

  return post('/api/users', formData)
}

export function deleteUser(id: number): Promise<{ code: number; message: string }> {
  return del(`/api/users/${id}`)
}
