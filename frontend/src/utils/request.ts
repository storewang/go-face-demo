import axios, { type AxiosInstance, type InternalAxiosRequestConfig, type AxiosResponse, type AxiosError } from 'axios'
import { ElMessage } from 'element-plus'

const service: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

let pendingControllers = new Set<AbortController>()

function addPendingController(controller: AbortController) {
  pendingControllers.add(controller)
}

function removePendingController(controller: AbortController) {
  pendingControllers.delete(controller)
}

export function cancelPendingRequests() {
  pendingControllers.forEach(controller => {
    controller.abort()
  })
  pendingControllers.clear()
}

service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (config.data instanceof FormData) {
      delete config.headers!['Content-Type']
    }

    const token = localStorage.getItem('admin_token')
    if (token && config.headers) {
      config.headers['Authorization'] = `Bearer ${token}`
    }

    if (!config.signal) {
      const controller = new AbortController()
      config.signal = controller.signal
      addPendingController(controller)
    }

    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

service.interceptors.response.use(
  (response: AxiosResponse) => {
    if (response.config?.signal instanceof AbortSignal) {
      pendingControllers.forEach(c => {
        if (c.signal === response.config.signal) removePendingController(c)
      })
    }

    const res = response.data

    if (response.config.responseType === 'blob') {
      return res
    }

    if (res.code && res.code !== 200) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }

    return res
  },
  (error: AxiosError) => {
    if (axios.isCancel(error)) {
      return Promise.reject(error)
    }

    let message = '网络错误，请稍后重试'

    if (error.response) {
      const status = error.response.status
      switch (status) {
        case 400:
          message = '请求参数错误'
          break
        case 401:
          message = '登录已过期，请重新登录'
          localStorage.removeItem('admin_token')
          const publicPaths = ['/scan', '/register']
          if (!publicPaths.some(p => window.location.pathname.startsWith(p))) {
            window.location.href = '/login'
          }
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

export default service

export function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  return service.get(url, { params })
}

export function post<T>(url: string, data?: unknown): Promise<T> {
  return service.post(url, data)
}

export function upload<T>(url: string, file: File, fieldName: string = 'file', data?: Record<string, unknown>): Promise<T> {
  const formData = new FormData()
  formData.append(fieldName, file)

  if (data) {
    Object.keys(data).forEach(key => {
      formData.append(key, data[key] as string | Blob)
    })
  }

  return service.post(url, formData)
}

export function del<T>(url: string): Promise<T> {
  return service.delete(url)
}

export function put<T>(url: string, data?: unknown): Promise<T> {
  return service.put(url, data)
}

export function download(url: string, params?: Record<string, unknown>): Promise<Blob> {
  return service.get(url, {
    params,
    responseType: 'blob'
  })
}
