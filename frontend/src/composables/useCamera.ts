import { ref, onBeforeUnmount } from 'vue'

export function useCamera() {
  const stream = ref<MediaStream | null>(null)
  const isStreaming = ref(false)
  const error = ref<string | null>(null)

  async function start(width: number = 640, height: number = 480) {
    try {
      error.value = null
      stream.value = await navigator.mediaDevices.getUserMedia({
        video: { width, height, facingMode: 'user' },
        audio: false
      })
      isStreaming.value = true
      return stream.value
    } catch (err: unknown) {
      const e = err as Error
      error.value = e.message
      throw err
    }
  }

  function stop() {
    if (stream.value) {
      stream.value.getTracks().forEach(track => track.stop())
      stream.value = null
    }
    isStreaming.value = false
  }

  function captureFrame(video: HTMLVideoElement): string {
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight

    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Failed to get canvas context')

    ctx.drawImage(video, 0, 0)

    return canvas.toDataURL('image/jpeg', 0.8).split(',')[1]
  }

  onBeforeUnmount(() => {
    stop()
  })

  return {
    stream,
    isStreaming,
    error,
    start,
    stop,
    captureFrame
  }
}
