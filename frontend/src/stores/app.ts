import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

export const useAppStore = defineStore('app', () => {
  const loading = ref(false)
  const loadingText = ref('加载中...')

  function showLoading(text: string = '加载中...') {
    loading.value = true
    loadingText.value = text
  }

  function hideLoading() {
    loading.value = false
  }

  function showMessage(message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') {
    ElMessage({
      message,
      type,
      duration: 3000
    })
  }

  function showSuccess(message: string) {
    showMessage(message, 'success')
  }

  function showError(message: string) {
    showMessage(message, 'error')
  }

  function showWarning(message: string) {
    showMessage(message, 'warning')
  }

  return {
    loading,
    loadingText,
    showLoading,
    hideLoading,
    showMessage,
    showSuccess,
    showError,
    showWarning
  }
})
