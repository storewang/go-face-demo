# 03 - API封装

> 模块: Axios HTTP 客户端封装
> 优先级: P0
> 依赖: 02-状态管理
> 预计时间: 0.5天

## 一、目标

封装 Axios HTTP 客户端，统一管理 API 请求，支持拦截器、错误处理。

## 二、API 模块规划

| 模块 | 文件 | 功能 |
|------|------|------|
| 基础配置 | request.ts | Axios 实例、拦截器 |
| 用户 API | user.ts | 用户管理接口 |
| 人脸 API | face.ts | 人脸识别接口 |
| 考勤 API | attendance.ts | 考勤管理接口 |

## 三、代码实现

### 3.1 Axios 实例 (src/utils/request.ts)

```typescript
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

// 创建 axios 实例
const service: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
service.interceptors.request.use(
  (config: AxiosRequestConfig) => {
    // 可以在这里添加 token
    const token = localStorage.getItem('token')
    if (token) {
      config.headers = config.headers || {}
      config.headers['Authorization'] = `Bearer ${token}`
    }
    
    return config
  },
  (error: AxiosError) => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    const res = response.data
    
    // 如果是文件流，直接返回
    if (response.config.responseType === 'blob') {
      return res
    }
    
    // 统一处理业务错误
    if (res.code && res.code !== 200) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    
    return res
  },
  (error: AxiosError) => {
    // 处理 HTTP 错误
    let message = '网络错误，请稍后重试'
    
    if (error.response) {
      const status = error.response.status
      switch (status) {
        case 400:
          message = '请求参数错误'
          break
        case 401:
          message = '未授权，请登录'
          // 可以跳转到登录页
          break
        case 403:
          message = '拒绝访问'
          break
        case 404:
          message = '请求资源不存在'
          break
        case 500:
          message = '服务器内部错误'
          break
        default:
          message = `请求失败 (${status})`
      }
    } else if (error.code === 'ECONNABORTED') {
      message = '请求超时'
    }
    
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

// 导出请求方法
export default service

// GET 请求
export function get<T>(url: string, params?: any): Promise<T> {
  return service.get(url, { params })
}

// POST 请求
export function post<T>(url: string, data?: any): Promise<T> {
  return service.post(url, data)
}

// POST 文件上传
export function upload<T>(url: string, file: File, fieldName: string = 'file', data?: any): Promise<T> {
  const formData = new FormData()
  formData.append(fieldName, file)
  
  if (data) {
    Object.keys(data).forEach(key => {
      formData.append(key, data[key])
    })
  }
  
  return service.post(url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

// 下载文件
export function download(url: string, params?: any): Promise<Blob> {
  return service.get(url, {
    params,
    responseType: 'blob'
  })
}
```

### 3.2 用户 API (src/api/user.ts)

```typescript
import { get, post, del, upload } from '@/utils/request'
import type { User, UserListResponse, UserCreateRequest } from '@/types/user'

// 获取用户列表
export function getUsers(params?: {
  page?: number
  page_size?: number
  department?: string
  status?: number
}): Promise<UserListResponse> {
  return get('/api/users', params)
}

// 获取单个用户
export function getUser(id: number): Promise<User> {
  return get(`/api/users/${id}`)
}

// 创建用户
export function createUser(data: UserCreateRequest): Promise<User> {
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

// 更新用户
export function updateUser(id: number, data: Partial<User>): Promise<User> {
  return post(`/api/users/${id}`, data)
}

// 删除用户
export function deleteUser(id: number): Promise<void> {
  return del(`/api/users/${id}`)
}

// 注册人脸
export function registerFace(userId: number, image: File): Promise<{
  success: boolean
  user_id: number
  face_detected: boolean
  face_quality: string | null
  message: string
}> {
  return upload(`/api/face/register/${userId}`, image, 'image')
}
```

### 3.3 人脸 API (src/api/face.ts)

```typescript
import { post, upload } from '@/utils/request'

// 人脸检测
export function detectFace(image: File): Promise<{
  faces_detected: number
  faces: Array<{
    box: { top: number; right: number; bottom: number; left: number }
    quality: string
  }>
}> {
  return upload('/api/face/detect', image, 'image')
}

// 人脸识别（无活体检测）
export function recognizeFace(image: File): Promise<{
  success: boolean
  user?: {
    id: number
    employee_id: string
    name: string
    department?: string
  }
  confidence: number
  reason?: string
}> {
  return upload('/api/face/recognize', image, 'image')
}

// 完整验证（含活体检测）
export function verifyFace(images: File[], checkLiveness: boolean = true): Promise<{
  success: boolean
  user?: {
    id: number
    employee_id: string
    name: string
    department?: string
  }
  confidence: number
  liveness_passed?: boolean
  reason?: string
}> {
  const formData = new FormData()
  images.forEach((img, index) => {
    formData.append('images', img)
  })
  formData.append('check_liveness', String(checkLiveness))
  
  return post('/api/face/verify', formData)
}

// 人脸比对（1:1）
export function compareFaces(image1: File, image2: File): Promise<{
  match: boolean
  distance: number
  confidence: number
  message: string
}> {
  const formData = new FormData()
  formData.append('image1', image1)
  formData.append('image2', image2)
  
  return post('/api/face/compare', formData)
}
```

### 3.4 考勤 API (src/api/attendance.ts)

```typescript
import { get, post, download } from '@/utils/request'
import type { AttendanceListResponse, AttendanceStats, CheckInResponse } from '@/types/attendance'

// 获取考勤记录
export function getAttendance(params?: {
  page?: number
  page_size?: number
  start_date?: string
  end_date?: string
  employee_id?: string
  action_type?: string
  result?: string
}): Promise<AttendanceListResponse> {
  return get('/api/attendance', params)
}

// 获取单条记录
export function getAttendanceRecord(id: number): Promise<any> {
  return get(`/api/attendance/${id}`)
}

// 上班打卡
export function checkIn(image: File, employeeId?: string): Promise<CheckInResponse> {
  const formData = new FormData()
  formData.append('image', image)
  if (employeeId) {
    formData.append('employee_id', employeeId)
  }
  
  return post('/api/attendance/check-in', formData)
}

// 下班打卡
export function checkOut(image: File, employeeId?: string): Promise<CheckInResponse> {
  const formData = new FormData()
  formData.append('image', image)
  if (employeeId) {
    formData.append('employee_id', employeeId)
  }
  
  return post('/api/attendance/check-out', formData)
}

// 导出考勤 Excel
export function exportAttendance(params: {
  start_date: string
  end_date: string
  employee_id?: string
  format?: string
}): Promise<Blob> {
  return download('/api/attendance/export', params)
}

// 考勤统计
export function getStats(params?: {
  start_date?: string
  end_date?: string
}): Promise<AttendanceStats> {
  return get('/api/attendance/stats', params)
}
```

### 3.5 API 导出 (src/api/index.ts)

```typescript
export * as userApi from './user'
export * as faceApi from './face'
export * as attendanceApi from './attendance'
```

## 四、使用示例

### 4.1 在组件中使用

```vue
<script setup lang="ts">
import { ref } from 'vue'
import * as userApi from '@/api/user'
import { useAppStore } from '@/stores'

const appStore = useAppStore()
const users = ref([])

async function loadUsers() {
  try {
    appStore.showLoading('加载用户列表...')
    const res = await userApi.getUsers({ page: 1, page_size: 10 })
    users.value = res.items
    appStore.showSuccess('加载成功')
  } catch (error) {
    appStore.showError('加载失败')
  } finally {
    appStore.hideLoading()
  }
}
</script>
```

### 4.2 文件上传示例

```vue
<script setup lang="ts">
import { ref } from 'vue'
import * as faceApi from '@/api/face'

const imageFile = ref<File | null>(null)

async function handleDetect() {
  if (!imageFile.value) return
  
  const result = await faceApi.detectFace(imageFile.value)
  console.log('检测到人脸:', result.faces_detected)
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    imageFile.value = target.files[0]
  }
}
</script>

<template>
  <input type="file" @change="handleFileChange" accept="image/*" />
  <button @click="handleDetect">检测人脸</button>
</template>
```

### 4.3 文件下载示例

```typescript
import * as attendanceApi from '@/api/attendance'

async function exportToExcel() {
  try {
    const blob = await attendanceApi.exportAttendance({
      start_date: '2024-01-01',
      end_date: '2024-01-31'
    })
    
    // 创建下载链接
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `attendance_${Date.now()}.xlsx`
    link.click()
    
    // 释放 URL
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('导出失败:', error)
  }
}
```

## 五、创建文件

```bash
# 创建目录
mkdir -p src/api src/utils

# 创建文件
touch src/utils/request.ts
touch src/api/{index,user,face,attendance}.ts
```

## 六、验收标准

- [ ] Axios 实例正常创建
- [ ] 请求拦截器正常工作
- [ ] 响应拦截器正常工作
- [ ] 错误统一处理
- [ ] GET/POST 请求正常
- [ ] 文件上传正常
- [ ] 文件下载正常
- [ ] TypeScript 类型正确

## 七、错误处理

### 7.1 网络错误

```typescript
// 在组件中捕获错误
try {
  const result = await userApi.getUsers()
} catch (error) {
  if (axios.isAxiosError(error)) {
    // Axios 错误
    console.error('请求失败:', error.message)
  } else {
    // 其他错误
    console.error('未知错误:', error)
  }
}
```

### 7.2 业务错误

```typescript
// 后端返回的业务错误
{
  "code": 400,
  "message": "工号已存在"
}
```

拦截器会自动处理并显示错误消息。

## 八、下一步

完成 API 封装后，继续实现：
- **04-摄像头组件**: 摄像头访问组件
- **05-用户注册页**: 用户注册页面
