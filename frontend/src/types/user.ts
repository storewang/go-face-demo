export type UserRole = 'super_admin' | 'dept_admin' | 'employee' | 'unknown'

export interface User {
  id: number
  employee_id: string
  name: string
  department?: string
  status: number
  role?: UserRole
  face_encoding_path?: string
  face_image_path?: string
  created_at?: string
  updated_at?: string
}

export interface UserListResponse {
  items: User[]
  total: number
  page: number
  page_size: number
}

export interface UserCreateRequest {
  employee_id: string
  name: string
  department?: string
  face_image?: File
}
