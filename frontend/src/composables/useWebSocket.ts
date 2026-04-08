import { ref, onBeforeUnmount } from 'vue'

interface WebSocketOptions {
  url?: string
  autoReconnect?: boolean
  reconnectInterval?: number
  maxReconnectAttempts?: number
  heartbeatInterval?: number
}

interface RegisterResult {
  device_id: number
  device_code: string
  device_name: string
}

export function useWebSocket(options: WebSocketOptions = {}) {
  const {
    url = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/face-stream',
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
    heartbeatInterval = 30000
  } = options

  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const reconnectAttempts = ref(0)
  const lastMessage = ref<unknown>(null)
  const registeredDevice = ref<RegisterResult | null>(null)

  let onMessageCallback: ((data: unknown) => void) | null = null
  let onOpenCallback: (() => void) | null = null
  let onCloseCallback: (() => void) | null = null
  let onErrorCallback: ((error: Event) => void) | null = null
  let onRegisteredCallback: ((device: RegisterResult) => void) | null = null

  let heartbeatTimer: number | null = null
  let reconnectTimer: number | null = null
  let pendingDeviceCode: string | null = null

  function connect(deviceCode?: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (ws.value?.readyState === WebSocket.OPEN) {
        resolve()
        return
      }

      isConnecting.value = true
      // 保存 deviceCode，等连接成功后发送注册消息
      if (deviceCode) {
        pendingDeviceCode = deviceCode
      }

      try {
        ws.value = new WebSocket(url)

        ws.value.onopen = () => {
          isConnected.value = true
          isConnecting.value = false
          reconnectAttempts.value = 0
          startHeartbeat()
          
          // 如果有 deviceCode，发送注册消息
          if (pendingDeviceCode) {
            send({
              type: 'register',
              device_code: pendingDeviceCode
            })
            pendingDeviceCode = null
          }
          
          if (onOpenCallback) onOpenCallback()
          resolve()
        }

        ws.value.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            lastMessage.value = data
            
            // 处理设备注册成功消息
            if (data.type === 'registered' && data.data) {
              registeredDevice.value = data.data as RegisterResult
              if (onRegisteredCallback) {
                onRegisteredCallback(data.data as RegisterResult)
              }
            }
            
            if (onMessageCallback) onMessageCallback(data)
          } catch (error) {
            console.error('[WebSocket] Failed to parse message:', error)
          }
        }

        ws.value.onclose = () => {
          isConnected.value = false
          isConnecting.value = false
          registeredDevice.value = null
          stopHeartbeat()
          if (onCloseCallback) onCloseCallback()
          if (autoReconnect && reconnectAttempts.value < maxReconnectAttempts) {
            scheduleReconnect()
          }
        }

        ws.value.onerror = (error) => {
          isConnecting.value = false
          if (onErrorCallback) onErrorCallback(error)
          reject(error)
        }
      } catch (error) {
        isConnecting.value = false
        reject(error)
      }
    })
  }

  function disconnect() {
    stopHeartbeat()
    clearReconnectTimer()

    if (ws.value) {
      ws.value.close()
      ws.value = null
    }

    isConnected.value = false
    isConnecting.value = false
  }

  function send(data: unknown): boolean {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      return false
    }

    try {
      const message = typeof data === 'string' ? data : JSON.stringify(data)
      ws.value.send(message)
      return true
    } catch (error) {
      console.error('[WebSocket] Failed to send:', error)
      return false
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return

    reconnectAttempts.value++
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      connect().catch(() => {})
    }, reconnectInterval)
  }

  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function startHeartbeat() {
    stopHeartbeat()
    heartbeatTimer = window.setInterval(() => {
      if (isConnected.value) {
        send({ type: 'ping' })
      }
    }, heartbeatInterval)
  }

  function stopHeartbeat() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function onMessage(callback: (data: unknown) => void) {
    onMessageCallback = callback
  }

  function onOpen(callback: () => void) {
    onOpenCallback = callback
  }

  function onClose(callback: () => void) {
    onCloseCallback = callback
  }

  function onError(callback: (error: Event) => void) {
    onErrorCallback = callback
  }

  function onRegistered(callback: (device: RegisterResult) => void) {
    onRegisteredCallback = callback
  }

  onBeforeUnmount(() => {
    disconnect()
  })

  return {
    ws,
    isConnected,
    isConnecting,
    reconnectAttempts,
    lastMessage,
    registeredDevice,
    connect,
    disconnect,
    send,
    onMessage,
    onOpen,
    onClose,
    onError,
    onRegistered
  }
}
