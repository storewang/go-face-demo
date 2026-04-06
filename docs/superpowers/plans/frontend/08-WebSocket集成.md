# 08 - WebSocket 集成

> 模块: WebSocket 封装与实时通信
> 优先级: P1
> 依赖: 03-API封装
> 预计时间: 0.5天

## 一、目标

封装 WebSocket 连接，支持实时视频流识别、自动重连、消息处理。

## 二、技术方案

### 2.1 WebSocket API

```javascript
// 创建连接
const ws = new WebSocket('ws://localhost:8000/ws/face-stream')

// 连接打开
ws.onopen = () => {
  console.log('Connected')
}

// 接收消息
ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  console.log('Message:', data)
}

// 连接关闭
ws.onclose = () => {
  console.log('Disconnected')
}

// 连接错误
ws.onerror = (error) => {
  console.error('Error:', error)
}

// 发送消息
ws.send(JSON.stringify({
  type: 'frame',
  data: base64Image
}))
```

## 三、代码实现

### 3.1 WebSocket Composable (src/composables/useWebSocket.ts)

```typescript
import { ref, onBeforeUnmount } from 'vue'

interface WebSocketOptions {
  url?: string
  autoReconnect?: boolean
  reconnectInterval?: number
  maxReconnectAttempts?: number
  heartbeatInterval?: number
}

export function useWebSocket(options: WebSocketOptions = {}) {
  // 配置
  const {
    url = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/face-stream',
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
    heartbeatInterval = 30000
  } = options
  
  // 状态
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const reconnectAttempts = ref(0)
  const lastMessage = ref<any>(null)
  
  // 回调
  let onMessageCallback: ((data: any) => void) | null = null
  let onOpenCallback: (() => void) | null = null
  let onCloseCallback: (() => void) | null = null
  let onErrorCallback: ((error: Event) => void) | null = null
  
  // 心跳定时器
  let heartbeatTimer: number | null = null
  
  // 重连定时器
  let reconnectTimer: number | null = null
  
  // 连接
  function connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (ws.value?.readyState === WebSocket.OPEN) {
        resolve()
        return
      }
      
      isConnecting.value = true
      
      try {
        ws.value = new WebSocket(url)
        
        // 连接打开
        ws.value.onopen = () => {
          console.log('[WebSocket] Connected')
          isConnected.value = true
          isConnecting.value = false
          reconnectAttempts.value = 0
          
          // 启动心跳
          startHeartbeat()
          
          // 回调
          if (onOpenCallback) {
            onOpenCallback()
          }
          
          resolve()
        }
        
        // 接收消息
        ws.value.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            lastMessage.value = data
            
            // 回调
            if (onMessageCallback) {
              onMessageCallback(data)
            }
          } catch (error) {
            console.error('[WebSocket] Failed to parse message:', error)
          }
        }
        
        // 连接关闭
        ws.value.onclose = (event) => {
          console.log('[WebSocket] Disconnected:', event.code, event.reason)
          isConnected.value = false
          isConnecting.value = false
          
          // 停止心跳
          stopHeartbeat()
          
          // 回调
          if (onCloseCallback) {
            onCloseCallback()
          }
          
          // 自动重连
          if (autoReconnect && reconnectAttempts.value < maxReconnectAttempts) {
            scheduleReconnect()
          }
        }
        
        // 连接错误
        ws.value.onerror = (error) => {
          console.error('[WebSocket] Error:', error)
          isConnecting.value = false
          
          // 回调
          if (onErrorCallback) {
            onErrorCallback(error)
          }
          
          reject(error)
        }
      } catch (error) {
        isConnecting.value = false
        reject(error)
      }
    })
  }
  
  // 断开连接
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
  
  // 发送消息
  function send(data: any): boolean {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      console.warn('[WebSocket] Cannot send: not connected')
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
  
  // 发送文本
  function sendText(text: string): boolean {
    return send(text)
  }
  
  // 发送 JSON
  function sendJson(data: any): boolean {
    return send(data)
  }
  
  // 计划重连
  function scheduleReconnect() {
    if (reconnectTimer) return
    
    reconnectAttempts.value++
    console.log(`[WebSocket] Reconnecting in ${reconnectInterval}ms (attempt ${reconnectAttempts.value}/${maxReconnectAttempts})`)
    
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      connect().catch(() => {
        // 重连失败，会自动再次尝试
      })
    }, reconnectInterval)
  }
  
  // 清除重连定时器
  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }
  
  // 启动心跳
  function startHeartbeat() {
    stopHeartbeat()
    
    heartbeatTimer = window.setInterval(() => {
      if (isConnected.value) {
        send({ type: 'ping' })
      }
    }, heartbeatInterval)
  }
  
  // 停止心跳
  function stopHeartbeat() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }
  
  // 设置消息回调
  function onMessage(callback: (data: any) => void) {
    onMessageCallback = callback
  }
  
  // 设置连接回调
  function onOpen(callback: () => void) {
    onOpenCallback = callback
  }
  
  // 设置断开回调
  function onClose(callback: () => void) {
    onCloseCallback = callback
  }
  
  // 设置错误回调
  function onError(callback: (error: Event) => void) {
    onErrorCallback = callback
  }
  
  // 组件卸载时清理
  onBeforeUnmount(() => {
    disconnect()
  })
  
  return {
    // 状态
    ws,
    isConnected,
    isConnecting,
    reconnectAttempts,
    lastMessage,
    
    // 方法
    connect,
    disconnect,
    send,
    sendText,
    sendJson,
    
    // 回调
    onMessage,
    onOpen,
    onClose,
    onError
  }
}
```

### 3.2 WebSocket Store (src/stores/websocket.ts)

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

export const useWebSocketStore = defineStore('websocket', () => {
  const {
    isConnected,
    isConnecting,
    reconnectAttempts,
    lastMessage,
    connect,
    disconnect,
    send,
    onMessage
  } = useWebSocket({
    autoReconnect: true,
    reconnectInterval: 3000,
    maxReconnectAttempts: 5
  })
  
  // 消息队列
  const messageQueue = ref<any[]>([])
  
  // 最新状态
  const status = computed(() => {
    if (isConnected.value) return 'connected'
    if (isConnecting.value) return 'connecting'
    return 'disconnected'
  })
  
  // 处理消息
  onMessage((data) => {
    messageQueue.value.push({
      ...data,
      timestamp: Date.now()
    })
    
    // 保持队列最多 100 条
    if (messageQueue.value.length > 100) {
      messageQueue.value.shift()
    }
  })
  
  // 清空消息队列
  function clearMessages() {
    messageQueue.value = []
  }
  
  return {
    // 状态
    isConnected,
    isConnecting,
    reconnectAttempts,
    lastMessage,
    messageQueue,
    status,
    
    // 方法
    connect,
    disconnect,
    send,
    clearMessages
  }
})
```

## 四、使用示例

### 4.1 基础使用

```vue
<script setup lang="ts">
import { useWebSocket } from '@/composables/useWebSocket'

const {
  isConnected,
  connect,
  disconnect,
  send,
  onMessage
} = useWebSocket()

// 连接
async function handleConnect() {
  await connect()
}

// 断开
function handleDisconnect() {
  disconnect()
}

// 发送消息
function sendMessage() {
  send({
    type: 'frame',
    data: 'base64_image_data'
  })
}

// 监听消息
onMessage((data) => {
  console.log('Received:', data)
  
  if (data.type === 'result') {
    // 处理识别结果
  }
})
</script>
```

### 4.2 实时视频流

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

const {
  isConnected,
  connect,
  send,
  onMessage
} = useWebSocket()

const isStreaming = ref(false)
let frameInterval: number | null = null

// 开始实时流
async function startStreaming() {
  await connect()
  
  // 每 200ms 发送一帧
  frameInterval = window.setInterval(() => {
    const frame = captureFrame()
    if (frame) {
      send({
        type: 'frame',
        data: frame
      })
    }
  }, 200)
  
  isStreaming.value = true
}

// 停止实时流
function stopStreaming() {
  if (frameInterval) {
    clearInterval(frameInterval)
    frameInterval = null
  }
  
  disconnect()
  isStreaming.value = false
}

// 监听识别结果
onMessage((data) => {
  if (data.type === 'status') {
    console.log('Status:', data.data.message)
  } else if (data.type === 'result') {
    console.log('Result:', data.data)
    
    // 识别成功，暂停 3 秒
    if (data.data.success) {
      if (frameInterval) {
        clearInterval(frameInterval)
        
        setTimeout(() => {
          if (isStreaming.value) {
            startStreaming()
          }
        }, 3000)
      }
    }
  }
})
</script>
```

### 4.3 自动重连

```vue
<script setup lang="ts">
import { useWebSocket } from '@/composables/useWebSocket'

const {
  isConnected,
  reconnectAttempts,
  connect,
  onOpen,
  onClose
} = useWebSocket({
  autoReconnect: true,
  reconnectInterval: 3000,
  maxReconnectAttempts: 5
})

// 连接成功
onOpen(() => {
  console.log('WebSocket connected')
})

// 连接断开
onClose(() => {
  console.log('WebSocket disconnected')
  if (reconnectAttempts.value > 0) {
    console.log(`Reconnecting... (attempt ${reconnectAttempts.value})`)
  }
})

// 手动连接
connect()
</script>
```

## 五、消息协议

### 5.1 客户端 → 服务端

**发送帧**
```json
{
  "type": "frame",
  "data": "base64_encoded_image"
}
```

**心跳**
```json
{
  "type": "ping"
}
```

### 5.2 服务端 → 客户端

**状态更新**
```json
{
  "type": "status",
  "data": {
    "stage": "liveness_check",
    "message": "请眨眼确认..."
  }
}
```

**识别结果**
```json
{
  "type": "result",
  "data": {
    "success": true,
    "user": {
      "id": 1,
      "employee_id": "10001",
      "name": "张三"
    },
    "confidence": 0.95,
    "action": "door_open"
  }
}
```

**心跳响应**
```json
{
  "type": "pong"
}
```

**错误**
```json
{
  "type": "error",
  "data": {
    "message": "Error message"
  }
}
```

## 六、创建文件

```bash
# 创建文件
touch src/composables/useWebSocket.ts
touch src/stores/websocket.ts
```

## 七、验收标准

- [ ] WebSocket 可正常连接
- [ ] 消息可正常发送和接收
- [ ] 自动重连功能正常
- [ ] 心跳机制正常
- [ ] 连接状态正确反映
- [ ] 错误处理友好
- [ ] 组件卸载时正确清理

## 八、注意事项

1. **生产环境**: 使用 `wss://` (WebSocket Secure)
2. **跨域**: 后端需配置 WebSocket CORS
3. **超时**: 设置合理的超时时间
4. **内存**: 及时清理消息队列
5. **并发**: 注意多组件使用同一连接

## 九、调试技巧

### 9.1 浏览器开发者工具

Chrome DevTools → Network → WS (WebSocket)

### 9.2 日志

```typescript
// 启用详细日志
const ws = useWebSocket({
  url: 'ws://localhost:8000/ws/face-stream',
  // ...
})

ws.onMessage((data) => {
  console.log('[WS] Message:', data)
})
```

### 9.3 测试工具

使用在线 WebSocket 测试工具：https://www.websocket.org/echo.html

## 十、下一步

完成 WebSocket 集成后，继续实现：
- **09-测试与优化**: 前端测试与优化
