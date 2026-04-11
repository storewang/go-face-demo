import { get, post, put, del } from '@/utils/request'
import type { Device, DeviceListResponse, DeviceCreate, DeviceUpdate } from '@/types/device'

export function getDevices(params?: {
  page?: number
  page_size?: number
  status?: number
}): Promise<DeviceListResponse> {
  return get('/devices', params as Record<string, unknown>)
}

export function getDevice(id: number): Promise<Device> {
  return get(`/devices/${id}`)
}

export function createDevice(data: DeviceCreate): Promise<Device> {
  return post('/devices', data)
}

export function updateDevice(id: number, data: DeviceUpdate): Promise<Device> {
  return put(`/devices/${id}`, data)
}

export function deleteDevice(id: number): Promise<{ code: number; message: string }> {
  return del(`/devices/${id}`)
}