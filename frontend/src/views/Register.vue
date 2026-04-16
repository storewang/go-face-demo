<template>
  <div class="register-page">
    <el-card class="register-card">
      <template #header>
        <div class="card-header">
          <el-icon :size="24"><UserFilled /></el-icon>
          <span>用户注册</span>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        :label-width="isMobile ? '70px' : '80px'"
      >
        <el-form-item label="工号" prop="employee_id">
          <el-input
            v-model="form.employee_id"
            placeholder="请输入工号"
            clearable
          />
        </el-form-item>

        <el-form-item label="姓名" prop="name">
          <el-input
            v-model="form.name"
            placeholder="请输入姓名"
            clearable
          />
        </el-form-item>

        <el-form-item label="部门" prop="department">
          <el-select
            v-model="form.department"
            placeholder="请选择部门"
            clearable
            style="width: 100%"
          >
            <el-option label="技术部" value="技术部" />
            <el-option label="产品部" value="产品部" />
            <el-option label="运营部" value="运营部" />
            <el-option label="市场部" value="市场部" />
            <el-option label="人事部" value="人事部" />
            <el-option label="财务部" value="财务部" />
          </el-select>
        </el-form-item>

        <el-form-item label="人脸照片" required>
          <div class="face-capture">
            <div v-if="!capturedImage" class="camera-box">
              <Camera
                ref="cameraRef"
                :show-capture="false"
                @ready="onCameraReady"
                @error="onCameraError"
              />

              <div v-if="cameraReady" class="capture-actions">
                <el-button type="primary" @click="capturePhoto">
                  <el-icon><CameraIcon /></el-icon>
                  拍照
                </el-button>
              </div>
            </div>

            <div v-else class="preview-box">
              <img :src="capturedImage" alt="人脸照片" />
              <div class="preview-actions">
                <el-button @click="retake">
                  <el-icon><RefreshRight /></el-icon>
                  重拍
                </el-button>
              </div>
            </div>

            <div v-if="faceQuality" class="quality-tip">
              <el-tag :type="qualityType">
                {{ qualityText }}
              </el-tag>
            </div>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            @click="handleSubmit"
            :loading="submitting"
            :disabled="!capturedImage"
            size="large"
            style="width: 100%"
          >
            提交注册
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  UserFilled,
  Camera as CameraIcon,
  RefreshRight
} from '@element-plus/icons-vue'
import Camera from '@/components/Camera.vue'
import * as userApi from '@/api/user'
import * as faceApi from '@/api/face'
import type { FormInstance, FormRules } from 'element-plus'

const isMobile = computed(() => window.innerWidth <= 768)

const router = useRouter()

const formRef = ref<FormInstance>()
const cameraRef = ref()

const form = ref({
  employee_id: '',
  name: '',
  department: ''
})

const rules: FormRules = {
  employee_id: [
    { required: true, message: '请输入工号', trigger: 'blur' },
    { min: 1, max: 50, message: '工号长度在 1 到 50 个字符', trigger: 'blur' }
  ],
  name: [
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { min: 1, max: 100, message: '姓名长度在 1 到 100 个字符', trigger: 'blur' }
  ]
}

const cameraReady = ref(false)
const capturedImage = ref<string | null>(null)
const capturedFile = ref<File | null>(null)
const faceQuality = ref<string | null>(null)
const submitting = ref(false)

const qualityType = computed(() => {
  switch (faceQuality.value) {
    case 'good': return 'success'
    case 'medium': return 'warning'
    case 'poor': return 'danger'
    default: return 'info'
  }
})

const qualityText = computed(() => {
  switch (faceQuality.value) {
    case 'good': return '人脸质量良好'
    case 'medium': return '人脸质量一般'
    case 'poor': return '人脸质量较差，请重拍'
    default: return ''
  }
})

function onCameraReady() {
  cameraReady.value = true
}

function onCameraError(error: Error) {
  ElMessage.error('摄像头启动失败: ' + error.message)
}

async function capturePhoto() {
  if (!cameraRef.value) return

  const result = cameraRef.value.capturePhoto()
  if (result) {
    capturedImage.value = result.base64
    capturedFile.value = result.file

    try {
      const detectResult = await faceApi.detectFace(result.file) as Record<string, any>
      const detectData = detectResult.data || detectResult

      if (detectData.faces_detected === 0) {
        ElMessage.warning('未检测到人脸，请重拍')
        retake()
        return
      }

      if (detectData.faces_detected > 1) {
        ElMessage.warning('检测到多张人脸，请确保只有一人')
        retake()
        return
      }

      faceQuality.value = detectData.faces[0].quality
    } catch (error) {
      console.error('Face detection failed:', error)
      ElMessage.error('人脸检测失败，请重拍')
      retake()
      return
    }
  }
}

function retake() {
  capturedImage.value = null
  capturedFile.value = null
  faceQuality.value = null
}

async function handleSubmit() {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  if (!capturedFile.value) {
    ElMessage.warning('请先拍摄人脸照片')
    return
  }

  if (faceQuality.value === 'poor') {
    ElMessage.warning('人脸质量较差，请重新拍摄')
    return
  }

  try {
    submitting.value = true

    const result = await userApi.createUser({
      employee_id: form.value.employee_id,
      name: form.value.name,
      department: form.value.department,
      face_image: capturedFile.value
    }) as Record<string, unknown>

    if (result.data?.has_face_encoding || result.data?.hasFaceEncoding || (result as any).has_face_encoding || (result as any).hasFaceEncoding) {
      ElMessage.success('注册成功，人脸已录入')
    } else {
      ElMessage.success('用户创建成功，但人脸未成功录入，请稍后在用户管理中补充')
    }

    ElMessageBox.confirm(
      '用户注册成功！是否继续注册下一个用户？',
      '成功',
      {
        confirmButtonText: '继续注册',
        cancelButtonText: '返回首页',
        type: 'success'
      }
    ).then(() => {
      resetForm()
    }).catch(() => {
      router.push('/')
    })
  } catch (error: unknown) {
    const err = error as Error
    ElMessage.error(err.message || '注册失败')
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  formRef.value?.resetFields()
  capturedImage.value = null
  capturedFile.value = null
  faceQuality.value = null
}
</script>

<style scoped>
.register-page {
  display: flex;
  justify-content: center;
  padding: 20px;
}

.register-card {
  width: 100%;
  max-width: 600px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: bold;
}

.face-capture {
  width: 100%;
}

.camera-box,
.preview-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 15px;
}

.preview-box img {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.capture-actions,
.preview-actions {
  display: flex;
  gap: 10px;
}

.quality-tip {
  text-align: center;
  margin-top: 10px;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .register-page {
    padding: 12px 8px;
  }

  .register-card {
    max-width: 100%;
  }

  .card-header {
    font-size: 16px;
  }

  .preview-box img {
    max-height: 300px;
  }
}
</style>
