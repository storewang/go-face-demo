<template>
  <div class="scan-page">
    <div class="header">
      <h2>人脸识别门禁</h2>
      <el-tag :type="connectionStatus" size="small">{{ connectionText }}</el-tag>
      <el-alert
        v-if="!isOnline"
        title="网络断开"
        description="请使用 PIN 码开门"
        type="warning"
        :closable="false"
        show-icon
        style="margin-top: 10px"
      />
    </div>

    <div class="main-content">
      <div class="camera-section">
        <div class="video-container">
          <video
            ref="videoRef"
            class="video"
            autoplay
            playsinline
            muted
          ></video>

          <canvas
            ref="overlayRef"
            class="overlay"
          ></canvas>

          <div v-if="statusMessage" class="status-overlay">
            <el-icon class="pulse" :size="28">
              <component :is="statusIcon" />
            </el-icon>
            <span>{{ statusMessage }}</span>
          </div>
        </div>

        <div class="controls">
          <!-- 设备选择 -->
          <div class="device-selector">
            <el-select
              v-model="selectedDeviceCode"
              placeholder="选择设备（可选）"
              clearable
              :disabled="isStreaming"
              :style="{ width: isMobile ? '150px' : '200px' }"
            >
              <el-option
                v-for="device in devices"
                :key="device.device_code"
                :label="device.name"
                :value="device.device_code"
              >
                <span>{{ device.name }}</span>
                <el-tag v-if="device.is_online" type="success" size="small" style="margin-left: 8px">在线</el-tag>
                <el-tag v-else type="info" size="small" style="margin-left: 8px">离线</el-tag>
              </el-option>
            </el-select>
            <el-tag v-if="currentDeviceName" type="success" size="small" style="margin-left: 8px">
              {{ isMobile ? '' : '当前设备: ' }}{{ currentDeviceName }}
            </el-tag>
          </div>

          <div class="control-buttons">
            <el-button
              v-if="!isStreaming"
              type="primary"
              size="large"
              @click="startScanning"
              :loading="isStarting"
            >
              <el-icon><VideoCamera /></el-icon>
              {{ isMobile ? '识别' : '开始识别' }}
            </el-button>

            <el-button
              v-else
              type="danger"
              size="large"
              @click="stopScanning"
            >
              <el-icon><VideoPause /></el-icon>
              {{ isMobile ? '停止' : '停止识别' }}
            </el-button>

            <el-button
              v-if="!isOnline || !!cameraError"
              type="warning"
              size="large"
              @click="showPinFallback = true"
            >
              <el-icon><Key /></el-icon>
              PIN 码开门
            </el-button>
          </div>
        </div>
      </div>

      <div class="result-section">
        <el-empty
          v-if="!lastResult"
          description="等待识别..."
          :image-size="isMobile ? 150 : 200"
        />

        <el-card v-else class="result-card" :class="resultClass">
          <div class="result-header">
            <el-icon :size="isMobile ? 36 : 48" :color="resultIconColor">
              <component :is="resultIcon" />
            </el-icon>
            <h3>{{ resultTitle }}</h3>
          </div>

          <div v-if="lastResult.success" class="result-body">
            <div class="user-info">
              <el-avatar :size="isMobile ? 60 : 80">
                <el-icon :size="isMobile ? 30 : 40"><UserFilled /></el-icon>
              </el-avatar>

              <div class="user-details">
                <div class="user-name">{{ resultUser?.name }}</div>
                <div class="user-id">工号: {{ resultUser?.employee_id }}</div>
                <div class="user-dept">{{ resultUser?.department }}</div>
              </div>
            </div>

            <el-divider />

            <div class="result-details">
              <div class="detail-item">
                <span class="label">置信度:</span>
                <el-progress
                  :percentage="Math.round(Number(lastResult.confidence) * 100)"
                  :color="confidenceColor"
                />
              </div>

              <div class="detail-item">
                <span class="label">打卡类型:</span>
                <el-tag>{{ lastResult.action_type === 'CHECK_IN' ? '上班打卡' : '下班打卡' }}</el-tag>
              </div>

              <div class="detail-item">
                <span class="label">识别时间:</span>
                <span>{{ formatTime(new Date()) }}</span>
              </div>
            </div>

            <el-divider />

            <div class="door-animation">
              <transition name="door">
                <div v-if="showDoorOpen" class="door-open">
                  <el-icon :size="48" color="#67C23A"><CircleCheckFilled /></el-icon>
                  <div class="door-text">门已开启</div>
                </div>
              </transition>
            </div>
          </div>

          <div v-else class="result-body failed">
            <el-result
              icon="warning"
              :title="lastResult.message"
              sub-title="请重新尝试"
            >
              <template #extra>
                <el-button type="primary" @click="retry">重试</el-button>
              </template>
            </el-result>
          </div>
        </el-card>

        <div v-if="scanHistory.length > 0" class="history-section">
          <h4>今日识别记录</h4>
          <el-timeline>
            <el-timeline-item
              v-for="item in scanHistory"
              :key="item.id"
              :timestamp="item.time"
              :type="item.success ? 'success' : 'danger'"
              placement="top"
            >
              {{ item.name }} - {{ item.action }}
            </el-timeline-item>
          </el-timeline>
        </div>
      </div>
    </div>

    <el-dialog v-model="showPinFallback" title="PIN 码开门" width="320px" :close-on-click-modal="false">
      <el-input
        v-model="pinCode"
        placeholder="请输入 6 位 PIN 码"
        maxlength="6"
        type="password"
        size="large"
        @keyup.enter="submitPin"
      />
      <template #footer>
        <el-button @click="showPinFallback = false">取消</el-button>
        <el-button type="primary" @click="submitPin" :loading="pinLoading">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  VideoCamera,
  VideoPause,
  UserFilled,
  CircleCheckFilled,
  WarningFilled,
  Loading,
  Key
} from '@element-plus/icons-vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useOnlineStatus } from '@/composables/useOnlineStatus'
import * as deviceApi from '@/api/device'
import type { Device } from '@/types/device'
import { useAuthStore } from '@/stores/auth'
import { post } from '@/utils/request'

const isMobile = computed(() => window.innerWidth <= 768)

const videoRef = ref<HTMLVideoElement | null>(null)
const overlayRef = ref<HTMLCanvasElement | null>(null)

const isStreaming = ref(false)
const isStarting = ref(false)
const statusMessage = ref('')
const statusIcon = ref(Loading)
const lastResult = ref<Record<string, unknown> | null>(null)
const showDoorOpen = ref(false)
const scanHistory = ref<Array<{ id: number; name: string; action: string; time: string; success: boolean }>>([])

// 网络状态与 PIN 码回退
const { isOnline } = useOnlineStatus()
const cameraError = ref('')
const showPinFallback = ref(false)
const pinCode = ref('')
const pinLoading = ref(false)

// 设备相关
const devices = ref<Device[]>([])
const selectedDeviceCode = ref<string>('')
const currentDeviceName = ref<string>('')

const {
  isConnected,
  connect,
  disconnect,
  sendBinary,
  onMessage,
  onRegistered
} = useWebSocket()

let stream: MediaStream | null = null
let frameInterval: number | null = null

const connectionStatus = computed(() =>
  isConnected.value ? 'success' : 'danger'
)

const connectionText = computed(() =>
  isConnected.value ? '已连接' : '未连接'
)

const resultClass = computed(() =>
  lastResult.value?.success ? 'success' : 'failed'
)

const resultIcon = computed(() =>
  lastResult.value?.success ? CircleCheckFilled : WarningFilled
)

const resultIconColor = computed(() =>
  lastResult.value?.success ? '#67C23A' : '#F56C6C'
)

const resultTitle = computed(() =>
  lastResult.value?.success ? '识别成功' : '识别失败'
)

const confidenceColor = computed(() => {
  if (!lastResult.value) return '#409EFF'
  const conf = Number(lastResult.value.confidence) || 0
  if (conf >= 0.8) return '#67C23A'
  if (conf >= 0.6) return '#E6A23C'
  return '#F56C6C'
})

const resultUser = computed(() => {
  if (!lastResult.value?.user) return null
  return lastResult.value.user as Record<string, unknown> | null
})

// 加载设备列表
async function loadDevices() {
  const authStore = useAuthStore()
  if (!authStore.isLoggedIn) return
  try {
    const res = await deviceApi.getDevices()
    devices.value = res.items || []
  } catch (error) {
    console.error('加载设备列表失败:', error)
  }
}

async function startScanning() {
  isStarting.value = true
  statusMessage.value = '正在启动摄像头...'

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: isMobile.value ? 320 : 480, height: isMobile.value ? 240 : 360, facingMode: 'user' },
      audio: false
    })

    if (videoRef.value) {
      videoRef.value.srcObject = stream
      await videoRef.value.play()
    }

    // 连接 WebSocket，如果选择了设备则传递 deviceCode
    await connect(selectedDeviceCode.value || undefined)

    // 设置设备注册回调
    onRegistered((device) => {
      currentDeviceName.value = device.device_name
      ElMessage.success(`已连接到设备: ${device.device_name}`)
    })

    onMessage(handleWebSocketMessage as (data: unknown) => void)

    isStreaming.value = true
    statusMessage.value = '请对准摄像头...'
    startFrameSending()

    ElMessage.success('识别已启动')
  } catch (error: unknown) {
    const err = error as Error
    cameraError.value = err.message
    ElMessage.error('启动失败: ' + err.message)
    statusMessage.value = '启动失败'
  } finally {
    isStarting.value = false
  }
}

function stopScanning() {
  if (frameInterval) {
    clearInterval(frameInterval)
    frameInterval = null
  }

  if (stream) {
    stream.getTracks().forEach(track => track.stop())
    stream = null
  }

  disconnect()

  isStreaming.value = false
  statusMessage.value = ''
  lastResult.value = null
  currentDeviceName.value = ''

  ElMessage.info('识别已停止')
}

function startFrameSending() {
  if (frameInterval) {
    clearInterval(frameInterval)
    frameInterval = null
  }
  frameInterval = window.setInterval(() => {
    if (!videoRef.value || !isConnected.value) return
    captureFrameBlob(videoRef.value!, 0.75)
      .then((blob) => {
        if (blob && sendBinary) {
          sendBinary(blob)
        }
      })
  }, 400)
}

function captureFrameBlob(video: HTMLVideoElement, quality: number = 0.8): Promise<Blob | null> {
  return new Promise((resolve) => {
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) { resolve(null); return }
    ctx.drawImage(video, 0, 0)
    canvas.toBlob(
      (blob) => resolve(blob),
      'image/jpeg',
      quality
    )
  })
}

function handleWebSocketMessage(data: Record<string, unknown>) {
  if (data.type === 'status') {
    const statusData = (data.data || data) as Record<string, string>
    statusMessage.value = statusData.message || ''
    statusIcon.value = Loading
  } else if (data.type === 'result') {
    const resultData = (data.data || data) as Record<string, unknown>
    lastResult.value = resultData

    if (resultData.success) {
      statusMessage.value = ''
      showDoorOpen.value = true

      const userData = (resultData.user || {}) as Record<string, unknown>
      scanHistory.value.unshift({
        id: Date.now(),
        name: String(userData.name || ''),
        action: resultData.action_type === 'CHECK_OUT' ? '下班打卡' : '上班打卡',
        time: formatTime(new Date()),
        success: true
      })
      if (scanHistory.value.length > 50) {
        scanHistory.value = scanHistory.value.slice(0, 50)
      }

      setTimeout(() => {
        showDoorOpen.value = false
      }, 3000)
    } else {
      statusMessage.value = (resultData.message as string) || '未识别到人脸'
      statusIcon.value = WarningFilled
    }

    if (frameInterval) {
      clearInterval(frameInterval)
      setTimeout(() => {
        if (isStreaming.value) {
          startFrameSending()
          lastResult.value = null
        }
      }, 3000)
    }
  } else if (data.type === 'error') {
    const errData = (data.data || data) as Record<string, string>
    statusMessage.value = errData.message || '发生错误'
    statusIcon.value = WarningFilled
  } else if (data.type === 'registered') {
    const regData = (data.data || data) as Record<string, string>
    currentDeviceName.value = regData.device_name || ''
    ElMessage.success(`已连接到设备: ${regData.device_name || ''}`)
  }
}

async function submitPin() {
  if (!pinCode.value || pinCode.value.length !== 6) {
    ElMessage.warning('请输入 6 位 PIN 码')
    return
  }
  pinLoading.value = true
  try {
    const res = await post<Record<string, unknown>>('/auth/pin-verify', { pin_code: pinCode.value })
    if (res.code === 200 || res.data) {
      ElMessage.success('PIN 验证成功，门已开启')
      showPinFallback.value = false
      pinCode.value = ''
    } else {
      ElMessage.error(res.message || 'PIN 码错误')
    }
  } catch (e: unknown) {
    const err = e as Error
    ElMessage.error(err?.message || 'PIN 验证失败')
  } finally {
    pinLoading.value = false
  }
}

function retry() {
  lastResult.value = null
  statusMessage.value = '请对准摄像头...'
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

onBeforeUnmount(() => {
  stopScanning()
})

onMounted(() => {
  loadDevices()
})
</script>

<style scoped>
.scan-page {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
  font-size: 20px;
}

.main-content {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
}

.camera-section {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.video-container {
  position: relative;
  width: 100%;
  padding-top: 75%;
  background-color: #000;
  border-radius: 8px;
  overflow: hidden;
}

.video {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scaleX(-1);
}

.overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  transform: scaleX(-1);
}

.status-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 15px;
  padding: 20px 30px;
  background-color: rgba(0, 0, 0, 0.7);
  color: #fff;
  border-radius: 8px;
  font-size: 16px;
}

.pulse {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.controls {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 15px;
}

.device-selector {
  display: flex;
  align-items: center;
}

.control-buttons {
  display: flex;
  gap: 12px;
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.result-card {
  transition: all 0.3s;
}

.result-card.success {
  border-color: #67C23A;
}

.result-card.failed {
  border-color: #F56C6C;
}

.result-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}

.result-header h3 {
  margin: 0;
}

.result-body {
  padding: 20px 0;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 20px;
}

.user-details {
  flex: 1;
}

.user-name {
  font-size: 20px;
  font-weight: bold;
  margin-bottom: 8px;
}

.user-id,
.user-dept {
  color: #666;
  margin-bottom: 4px;
}

.result-details {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detail-item .label {
  width: 80px;
  color: #666;
  flex-shrink: 0;
}

.door-animation {
  text-align: center;
  padding: 20px;
}

.door-open {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 15px;
}

.door-text {
  font-size: 18px;
  font-weight: bold;
  color: #67C23A;
}

.door-enter-active {
  animation: door-open 0.5s ease-out;
}

@keyframes door-open {
  0% {
    transform: scale(0);
    opacity: 0;
  }
  50% {
    transform: scale(1.2);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.history-section {
  margin-top: 20px;
}

.history-section h4 {
  margin-bottom: 15px;
}

/* Mobile responsive */
@media (max-width: 1024px) {
  .main-content {
    grid-template-columns: 1fr;
  }

  .result-section {
    order: 2;
  }
}

@media (max-width: 768px) {
  .scan-page {
    padding: 12px 8px;
  }

  .header h2 {
    font-size: 18px;
  }

  .video-container {
    padding-top: 75%;
  }

  .user-info {
    flex-direction: column;
    text-align: center;
    gap: 12px;
  }

  .user-name {
    font-size: 18px;
  }

  .detail-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .detail-item .label {
    width: auto;
  }

  .door-text {
    font-size: 16px;
  }

  .status-overlay {
    padding: 15px 20px;
    font-size: 14px;
  }
}
</style>
