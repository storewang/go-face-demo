<template>
  <div class="users-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
        </div>
      </template>

      <el-table
        :data="users"
        v-loading="loading"
        stripe
        border
        style="width: 100%"
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="employee_id" label="工号" width="120" />
        <el-table-column prop="name" label="姓名" width="150" />
        <el-table-column prop="department" label="部门" width="150" />

        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" size="small">
              {{ roleText(row.role) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="人脸状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.face_encoding_path ? 'success' : 'danger'" size="small">
              {{ row.face_encoding_path ? '已录入' : '未录入' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="注册时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.face_encoding_path"
              type="primary"
              link
              @click="openFaceDialog(row)"
            >
              <el-icon><Camera /></el-icon>
              人脸采集
            </el-button>
            <el-button type="danger" link @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchUsers"
          @current-change="fetchUsers"
        />
      </div>
    </el-card>

    <!-- 人脸采集对话框 -->
    <el-dialog
      v-model="faceDialogVisible"
      :title="`人脸采集 - ${currentUser?.name} (${currentUser?.employee_id})`"
      width="680px"
      :close-on-click-modal="false"
      @close="closeFaceDialog"
    >
      <div class="face-capture">
        <div v-if="!capturedImage" class="camera-area">
          <Camera
            ref="cameraRef"
            :show-capture="false"
            @ready="onCameraReady"
            @error="onCameraError"
          />

          <div class="camera-actions">
            <el-button
              type="primary"
              @click="capturePhoto"
              :disabled="!cameraReady"
              :loading="detecting"
            >
              拍照
            </el-button>
          </div>
        </div>

        <div v-else class="preview-area">
          <img :src="capturedImage" alt="人脸照片" class="preview-img" />

          <div v-if="faceQuality" class="quality-row">
            <el-tag :type="qualityType" size="small">
              {{ qualityText }}
            </el-tag>
          </div>

          <div class="preview-actions">
            <el-button @click="retake" :disabled="registering">重拍</el-button>
            <el-button
              type="primary"
              @click="confirmRegister"
              :loading="registering"
              :disabled="!canRegister"
            >
              确认录入
            </el-button>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Camera as CameraIcon } from '@element-plus/icons-vue'
import Camera from '@/components/Camera.vue'
import * as userApi from '@/api/user'
import * as faceApi from '@/api/face'
import type { User } from '@/types/user'

// --- 用户列表 ---

const loading = ref(false)
const users = ref<User[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

onMounted(() => {
  fetchUsers()
})

async function fetchUsers() {
  loading.value = true
  try {
    const res = await userApi.getUsers({
      page: currentPage.value,
      page_size: pageSize.value
    })
    users.value = res.items
    total.value = res.total
  } catch (error: unknown) {
    const err = error as Error
    ElMessage.error('获取用户列表失败: ' + err.message)
  } finally {
    loading.value = false
  }
}

async function handleDelete(row: User) {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户「${row.name}」吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await userApi.deleteUser(row.id)
    ElMessage.success('删除成功')
    await fetchUsers()
  } catch {
    ElMessage.info('已取消删除')
  }
}

function formatDateTime(datetime?: string): string {
  if (!datetime) return '-'
  const date = new Date(datetime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

function roleText(role?: string): string {
  switch (role) {
    case 'super_admin': return '超级管理员'
    case 'dept_admin': return '部门管理员'
    case 'employee': return '员工'
    default: return '未知'
  }
}

function roleTagType(role?: string): string {
  switch (role) {
    case 'super_admin': return 'danger'
    case 'dept_admin': return 'warning'
    case 'employee': return 'success'
    default: return 'info'
  }
}

// --- 人脸采集 ---

const faceDialogVisible = ref(false)
const currentUser = ref<User | null>(null)
const cameraRef = ref()
const cameraReady = ref(false)

const capturedImage = ref<string | null>(null)
const capturedFile = ref<File | null>(null)
const faceQuality = ref<string | null>(null)
const detecting = ref(false)
const registering = ref(false)

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
    case 'poor': return '人脸质量较差'
    default: return ''
  }
})

const canRegister = computed(() => {
  return capturedFile.value !== null && faceQuality.value !== null && faceQuality.value !== 'poor'
})

function openFaceDialog(row: User) {
  currentUser.value = row
  faceDialogVisible.value = true
}

function closeFaceDialog() {
  resetCaptureState()
}

function resetCaptureState() {
  capturedImage.value = null
  capturedFile.value = null
  faceQuality.value = null
  detecting.value = false
  registering.value = false
  cameraReady.value = false
}

function onCameraReady() {
  cameraReady.value = true
}

function onCameraError(error: Error) {
  ElMessage.error('摄像头启动失败: ' + error.message)
}

async function capturePhoto() {
  if (!cameraRef.value) return

  const result = cameraRef.value.capturePhoto()
  if (!result) return

  capturedImage.value = result.base64
  capturedFile.value = result.file

  detecting.value = true
  try {
    const detectResult = await faceApi.detectFace(result.file)

    if (detectResult.faces_detected === 0) {
      ElMessage.warning('未检测到人脸，请重拍')
      retake()
      return
    }

    if (detectResult.faces_detected > 1) {
      ElMessage.warning('检测到多张人脸，请确保只有一人')
      retake()
      return
    }

    faceQuality.value = detectResult.faces[0].quality

    if (faceQuality.value === 'poor') {
      ElMessage.warning('人脸质量较差，请调整光线或位置后重拍')
    }
  } catch (error) {
    console.error('Face detection failed:', error)
    ElMessage.error('人脸检测失败，请重拍')
    retake()
  } finally {
    detecting.value = false
  }
}

function retake() {
  capturedImage.value = null
  capturedFile.value = null
  faceQuality.value = null
}

async function confirmRegister() {
  if (!currentUser.value || !capturedFile.value) return

  registering.value = true
  try {
    const result = await faceApi.registerFace(currentUser.value.id, capturedFile.value)

    if (result.success) {
      ElMessage.success('人脸录入成功')
      faceDialogVisible.value = false
      await fetchUsers()
    } else {
      ElMessage.warning(result.message || '人脸录入失败')
    }
  } catch (error) {
    console.error('Face register failed:', error)
    ElMessage.error('人脸录入失败，请重试')
  } finally {
    registering.value = false
  }
}
</script>

<style scoped>
.users-page {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.face-capture {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.camera-area,
.preview-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.preview-img {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.camera-actions,
.preview-actions {
  display: flex;
  gap: 12px;
}

.quality-row {
  text-align: center;
}
</style>
