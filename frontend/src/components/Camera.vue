<template>
  <div class="camera-container">
    <div class="video-wrapper">
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

      <div v-if="statusMessage" class="status-message">
        <el-icon class="status-icon"><Loading /></el-icon>
        <span>{{ statusMessage }}</span>
      </div>
    </div>

    <div class="controls">
      <el-button
        v-if="!isStreaming"
        type="primary"
        @click="startCamera"
        :loading="isStarting"
      >
        <el-icon><VideoCamera /></el-icon>
        开启摄像头
      </el-button>

      <el-button
        v-if="isStreaming"
        type="danger"
        @click="stopCamera"
      >
        <el-icon><VideoPause /></el-icon>
        关闭摄像头
      </el-button>

      <el-button
        v-if="isStreaming && showCapture"
        type="success"
        @click="capturePhoto"
      >
        <el-icon><Camera /></el-icon>
        拍照
      </el-button>
    </div>

    <div v-if="capturedImage" class="preview">
      <img :src="capturedImage" alt="Captured" />
      <div class="preview-actions">
        <el-button type="primary" @click="confirmCapture">确认</el-button>
        <el-button @click="retake">重拍</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoCamera, VideoPause, Camera, Loading } from '@element-plus/icons-vue'

interface Props {
  width?: number
  height?: number
  showCapture?: boolean
  autoStart?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  width: 640,
  height: 480,
  showCapture: true,
  autoStart: false
})

const emit = defineEmits<{
  (e: 'capture', image: string, file: File): void
  (e: 'frame', frame: string): void
  (e: 'error', error: Error): void
  (e: 'ready'): void
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
const overlayRef = ref<HTMLCanvasElement | null>(null)

const isStreaming = ref(false)
const isStarting = ref(false)
const statusMessage = ref('')
const capturedImage = ref<string | null>(null)
const stream = ref<MediaStream | null>(null)
const frameInterval = ref<number | null>(null)

async function startCamera() {
  isStarting.value = true
  statusMessage.value = '正在启动摄像头...'

  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('您的浏览器不支持摄像头访问')
    }

    stream.value = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: props.width },
        height: { ideal: props.height },
        facingMode: 'user'
      },
      audio: false
    })

    if (videoRef.value) {
      videoRef.value.srcObject = stream.value
      await videoRef.value.play()

      isStreaming.value = true
      statusMessage.value = ''
      emit('ready')
      ElMessage.success('摄像头已启动')
    }
  } catch (error: unknown) {
    const err = error as Error
    let message = '无法访问摄像头'
    if (err.name === 'NotAllowedError') {
      message = '请允许访问摄像头权限'
    } else if (err.name === 'NotFoundError') {
      message = '未找到摄像头设备'
    } else if (err.name === 'NotReadableError') {
      message = '摄像头被其他应用占用'
    }

    statusMessage.value = message
    ElMessage.error(message)
    emit('error', err)
  } finally {
    isStarting.value = false
  }
}

function stopCamera() {
  if (stream.value) {
    stream.value.getTracks().forEach(track => track.stop())
    stream.value = null
  }

  if (frameInterval.value) {
    clearInterval(frameInterval.value)
    frameInterval.value = null
  }

  isStreaming.value = false
  statusMessage.value = ''
  capturedImage.value = null
}

function capturePhoto(): { base64: string; file: File } | null {
  if (!videoRef.value) return null

  const canvas = document.createElement('canvas')
  canvas.width = videoRef.value.videoWidth
  canvas.height = videoRef.value.videoHeight

  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  ctx.drawImage(videoRef.value, 0, 0)

  const base64 = canvas.toDataURL('image/jpeg', 0.8)
  capturedImage.value = base64

  const file = base64ToFile(base64, 'capture.jpg')

  return { base64, file }
}

function confirmCapture() {
  const result = capturePhoto()
  if (result) {
    emit('capture', result.base64, result.file)
  }
}

function retake() {
  capturedImage.value = null
}

function base64ToFile(base64: string, filename: string): File {
  const arr = base64.split(',')
  const mime = arr[0].match(/:(.*?);/)?.[1] || 'image/jpeg'
  const bstr = atob(arr[1])
  let n = bstr.length
  const u8arr = new Uint8Array(n)

  while (n--) {
    u8arr[n] = bstr.charCodeAt(n)
  }

  return new File([u8arr], filename, { type: mime })
}

function getCurrentFrame(): string | null {
  if (!videoRef.value) return null

  const canvas = document.createElement('canvas')
  canvas.width = videoRef.value.videoWidth
  canvas.height = videoRef.value.videoHeight

  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  ctx.drawImage(videoRef.value, 0, 0)
  return canvas.toDataURL('image/jpeg', 0.8).split(',')[1]
}

function startFrameEmit(interval: number = 200) {
  if (!isStreaming.value) return

  frameInterval.value = window.setInterval(() => {
    const frame = getCurrentFrame()
    if (frame) {
      emit('frame', frame)
    }
  }, interval)
}

function stopFrameEmit() {
  if (frameInterval.value) {
    clearInterval(frameInterval.value)
    frameInterval.value = null
  }
}

function drawFaceBox(face: { box: number[]; label?: string }) {
  if (!overlayRef.value || !videoRef.value) return

  const canvas = overlayRef.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  canvas.width = props.width
  canvas.height = props.height
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  const [top, right, bottom, left] = face.box

  ctx.strokeStyle = '#00ff00'
  ctx.lineWidth = 3
  ctx.strokeRect(left, top, right - left, bottom - top)

  if (face.label) {
    ctx.fillStyle = '#00ff00'
    ctx.fillRect(left, bottom - 25, right - left, 25)

    ctx.fillStyle = '#ffffff'
    ctx.font = '16px Arial'
    ctx.fillText(face.label, left + 6, bottom - 6)
  }
}

function clearOverlay() {
  if (!overlayRef.value) return

  const ctx = overlayRef.value.getContext('2d')
  if (ctx) {
    ctx.clearRect(0, 0, overlayRef.value.width, overlayRef.value.height)
  }
}

if (props.autoStart) {
  startCamera()
}

onBeforeUnmount(() => {
  stopCamera()
})

defineExpose({
  startCamera,
  stopCamera,
  capturePhoto,
  getCurrentFrame,
  startFrameEmit,
  stopFrameEmit,
  drawFaceBox,
  clearOverlay
})
</script>

<style scoped>
.camera-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.video-wrapper {
  position: relative;
  width: 640px;
  height: 480px;
  background-color: #000;
  border-radius: 8px;
  overflow: hidden;
}

.video {
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

.status-message {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px 25px;
  background-color: rgba(0, 0, 0, 0.7);
  color: #fff;
  border-radius: 8px;
  font-size: 16px;
}

.status-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.controls {
  display: flex;
  gap: 10px;
}

.preview {
  text-align: center;
}

.preview img {
  max-width: 640px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.preview-actions {
  margin-top: 15px;
  display: flex;
  justify-content: center;
  gap: 10px;
}
</style>
