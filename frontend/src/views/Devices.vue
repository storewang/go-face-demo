<template>
  <div class="devices-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>设备管理</span>
          <el-button type="primary" @click="openAddDialog">
            <el-icon><Plus /></el-icon>
            添加设备
          </el-button>
        </div>
      </template>

      <el-form inline v-model="statusFilter" @submit.prevent="fetchDevices">
        <el-form-item label="状态">
          <el-select v-model="statusFilter" clearable placeholder="全部" @change="fetchDevices">
            <el-option label="全部" :value="undefined" />
            <el-option label="在线" :value="1" />
            <el-option label="离线" :value="0" />
            <el-option label="维护中" :value="2" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table :data="devices" v-loading="loading" stripe border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="device_code" label="设备编号" width="150" />
        <el-table-column prop="name" label="设备名称" width="150" />
        <el-table-column prop="location" label="位置" width="150">
          <template #default="{ row }">
            {{ row.location || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_heartbeat" label="最后心跳" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.last_heartbeat) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openEditDialog(row)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button type="danger" link @click="handleDelete(row)">
              <el-icon><Delete /></el-icon>
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
          @size-change="fetchDevices"
          @current-change="fetchDevices"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editMode ? '编辑设备' : '添加设备'"
      width="500px"
      @close="resetForm"
    >
      <el-form :model="form" label-width="80px" ref="formRef">
        <el-form-item label="设备编号" required>
          <el-input v-model="form.device_code" :disabled="editMode" placeholder="请输入设备编号" />
        </el-form-item>
        <el-form-item label="设备名称" required>
          <el-input v-model="form.name" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="form.location" placeholder="请输入位置" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item v-if="editMode" label="状态">
          <el-select v-model="form.status">
            <el-option label="离线" :value="0" />
            <el-option label="在线" :value="1" />
            <el-option label="维护中" :value="2" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import * as deviceApi from '@/api/device'
import type { Device, DeviceCreate, DeviceUpdate } from '@/types/device'

const loading = ref(false)
const devices = ref<Device[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const statusFilter = ref<number | undefined>(undefined)

const dialogVisible = ref(false)
const editMode = ref(false)
const submitting = ref(false)
const formRef = ref()
const form = reactive<DeviceCreate & DeviceUpdate & { device_code: string }>({
  device_code: '',
  name: '',
  location: '',
  description: '',
  status: 1
})

function statusText(status: number): string {
  switch (status) {
    case 0: return '离线'
    case 1: return '在线'
    case 2: return '维护中'
    default: return '未知'
  }
}

function statusTagType(status: number): string {
  switch (status) {
    case 0: return 'danger'
    case 1: return 'success'
    case 2: return 'warning'
    default: return 'info'
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
    minute: '2-digit'
  })
}

async function fetchDevices() {
  loading.value = true
  try {
    const res = await deviceApi.getDevices({
      page: currentPage.value,
      page_size: pageSize.value,
      status: statusFilter.value
    })
    devices.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error('获取设备列表失败')
  } finally {
    loading.value = false
  }
}

function openAddDialog() {
  editMode.value = false
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(row: Device) {
  editMode.value = true
  form.device_code = row.device_code
  form.name = row.name
  form.location = row.location || ''
  form.description = row.description || ''
  form.status = row.status
  dialogVisible.value = true
}

function resetForm() {
  form.device_code = ''
  form.name = ''
  form.location = ''
  form.description = ''
  form.status = 1
}

async function submitForm() {
  if (!form.device_code || !form.name) {
    ElMessage.warning('请填写设备编号和名称')
    return
  }

  submitting.value = true
  try {
    if (editMode.value) {
      const id = devices.value.find(d => d.device_code === form.device_code)?.id
      if (!id) return
      await deviceApi.updateDevice(id, {
        name: form.name,
        location: form.location || undefined,
        description: form.description || undefined,
        status: form.status
      })
      ElMessage.success('更新成功')
    } else {
      await deviceApi.createDevice({
        device_code: form.device_code,
        name: form.name,
        location: form.location || undefined,
        description: form.description || undefined
      })
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    await fetchDevices()
  } catch (e) {
    ElMessage.error(editMode.value ? '更新失败' : '添加失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: Device) {
  try {
    await ElMessageBox.confirm(
      `确定要删除设备「${row.name}」吗？`,
      '确认删除',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deviceApi.deleteDevice(row.id)
    ElMessage.success('删除成功')
    await fetchDevices()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  fetchDevices()
})
</script>

<style scoped>
.devices-page {
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
</style>