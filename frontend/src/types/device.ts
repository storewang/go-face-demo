export interface Device {
  id: number
  device_code: string
  name: string
  location?: string
  description?: string
  status: number // 0=offline, 1=online, 2=maintenance
  is_online?: boolean
  last_heartbeat?: string
  created_at?: string
  updated_at?: string
}

export interface DeviceListResponse {
  items: Device[]
  total: number
  page: number
  page_size: number
}

export interface DeviceCreate {
  device_code: string
  name: string
  location?: string
  description?: string
}

export interface DeviceUpdate {
  name?: string
  location?: string
  status?: number
  description?: string
}