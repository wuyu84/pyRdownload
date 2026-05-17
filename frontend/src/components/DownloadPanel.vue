<template>
  <el-card shadow="never" class="download-panel" v-if="visible">
    <template #header>
      <div class="panel-header">
        <span><el-icon><Download /></el-icon> 下载任务: {{ taskId }}<el-tag size="small" type="info" style="margin-left: 8px">{{ sourceLabel }}</el-tag></span>
        <el-button text type="info" size="small" @click="visible = false">关闭</el-button>
      </div>
    </template>
    <div class="total-progress">
      <span class="progress-label">总进度</span>
      <el-progress :percentage="totalProgress" :status="totalStatus" :stroke-width="20" :text-inside="true"><span>{{ progressText }}</span></el-progress>
    </div>
    <div class="package-list">
      <div v-for="pkg in packageList" :key="pkg.name" class="package-item">
        <div class="pkg-row">
          <span class="pkg-status-icon">{{ statusIcon(pkg.status) }}</span>
          <span class="pkg-name">{{ pkg.name }}</span>
          <span class="pkg-version">{{ pkg.version }}</span>
          <el-tag v-if="pkg.status === 'cached'" size="small" type="success" effect="light">📦 仓库复用</el-tag>
          <el-tag v-if="pkg.status === 'downloading'" size="small" type="warning" effect="light">⏳ 下载中 {{ pkg.progress > 0 ? Math.round(pkg.progress * 100) + '%' : '' }}</el-tag>
          <el-tag v-if="pkg.status === 'downloaded'" size="small" type="success" effect="light">✅ 新下载</el-tag>
          <el-tag v-if="pkg.status === 'failed'" size="small" type="danger" effect="light">❌ {{ pkg.friendly_error || pkg.error_msg || '失败' }}</el-tag>
          <el-tag v-if="pkg.status === 'pending'" size="small" type="info" effect="light">⏸ 等待中</el-tag>
          <el-tag v-if="pkg.source" size="small" type="info" effect="plain" style="margin-left: auto">[{{ pkg.source }}]</el-tag>
        </div>
        <el-progress v-if="pkg.status === 'downloading' && pkg.progress > 0" :percentage="Math.round(pkg.progress * 100)" :stroke-width="6" style="margin-top: 4px" />
      </div>
    </div>
    <div class="stats-row">
      <el-tag type="success">📦 仓库复用: {{ cachedCount }}</el-tag>
      <el-tag type="warning">新下载: {{ downloadedCount }}</el-tag>
      <el-tag v-if="failedCount > 0" type="danger">失败: {{ failedCount }}</el-tag>
    </div>
    <div v-if="isDone" class="download-btn-row">
      <el-button type="primary" size="large" :icon="Download" @click="downloadExport">📥 下载打包文件</el-button>
      <span class="file-name">{{ exportFileName }}</span>
    </div>
    <ErrorAlert v-if="errorMsg" :error="errorMsg" :suggestion="errorSuggestion" />
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { getTaskStatus, getExportUrl } from '@/api'
import ErrorAlert from './ErrorAlert.vue'

const props = defineProps<{ taskId: string; lang: string; source: string }>()
const emit = defineEmits<{ done: [] }>()
const visible = ref(true)
const wsRef = ref<WebSocket | null>(null)
const packages = reactive<Record<string, any>>({})
const packageList = ref<any[]>([])
const errorMsg = ref('')
const errorSuggestion = ref('')
const isDone = ref(false)
const sourceLabels: Record<string, string> = { pypi: 'PyPI官方', cran: 'CRAN官方', github: 'GitHub Releases', bioconductor: 'Bioconductor' }
const sourceLabel = computed(() => sourceLabels[props.source] || props.source)
const cachedCount = computed(() => packageList.value.filter((p: any) => p.status === 'cached').length)
const downloadedCount = computed(() => packageList.value.filter((p: any) => p.status === 'downloaded').length)
const failedCount = computed(() => packageList.value.filter((p: any) => p.status === 'failed').length)
const totalCount = computed(() => packageList.value.length)
const totalProgress = computed(() => totalCount.value === 0 ? 0 : Math.round((packageList.value.filter((p: any) => ['cached', 'downloaded', 'failed'].includes(p.status)).length / totalCount.value) * 100))
const totalStatus = computed(() => isDone.value ? 'success' : (failedCount.value > 0 && totalProgress.value >= 100 ? 'exception' : ''))
const progressText = computed(() => isDone.value ? `完成 (${packageList.value.length}/${packageList.value.length})` : `${packageList.value.length} 个包`)
const exportFileName = computed(() => `${props.taskId}_${props.lang}_${props.source}.zip`)
onMounted(() => connectWebSocket())
onUnmounted(() => wsRef.value?.close())

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws/download/${props.taskId}`)
  wsRef.value = ws
  ws.onmessage = (event) => { try { handleProgress(JSON.parse(event.data)) } catch (e) { console.error('WS:', e) } }
  ws.onclose = () => pollTaskStatus()
  ws.onerror = () => pollTaskStatus()
}

function handleProgress(data: any) {
  const { pkg_name, status, progress, message } = data
  if (pkg_name) {
    if (!packages[pkg_name]) packages[pkg_name] = { name: pkg_name, status: 'pending', progress: 0, version: '' }
    packages[pkg_name].status = status
    if (progress !== undefined) packages[pkg_name].progress = progress
    if (message) packages[pkg_name].message = message
    updatePackageList()
  }
  if (status === 'done') { isDone.value = true; emit('done') }
  else if (status === 'failed') errorMsg.value = message || '任务失败'
}

function updatePackageList() {
  const order: Record<string, number> = { cached: 0, downloading: 1, downloaded: 2, failed: 3, pending: 4 }
  packageList.value = Object.values(packages).sort((a: any, b: any) => (order[a.status] || 0) - (order[b.status] || 0))
}

async function pollTaskStatus() {
  try {
    const res = await getTaskStatus(props.taskId)
    const task = res.data
    if (!task || task.error) { setTimeout(pollTaskStatus, 3000); return }
    isDone.value = task.status === 'done' || task.status === 'failed'
    if (task.packages) {
      for (const pkg of task.packages) {
        const key = pkg.pkg_name
        if (!packages[key]) packages[key] = { name: key, status: pkg.status, progress: pkg.is_cached ? 1 : 0, version: pkg.pkg_version }
        else packages[key].status = pkg.status
        if (pkg.friendly_error) packages[key].friendly_error = pkg.friendly_error
      }
      updatePackageList()
    }
    if (isDone.value) emit('done')
    else setTimeout(pollTaskStatus, 2000)
  } catch (e) { setTimeout(pollTaskStatus, 3000) }
}

function statusIcon(status: string): string {
  const icons: Record<string, string> = { cached: '📦', downloading: '⏳', downloaded: '✅', failed: '❌', pending: '⏸', packaging: '📦' }
  return icons[status] || '⬜'
}
function downloadExport() { window.open(getExportUrl(props.taskId), '_blank') }
</script>

<style scoped>
.download-panel { border-radius: 8px; }
.panel-header { display: flex; justify-content: space-between; align-items: center; }
.total-progress { margin-bottom: 16px; }
.progress-label { font-size: 14px; font-weight: 600; margin-bottom: 8px; display: block; }
.package-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; max-height: 400px; overflow-y: auto; }
.package-item { padding: 8px; background: #fafafa; border-radius: 6px; }
.pkg-row { display: flex; align-items: center; gap: 8px; }
.pkg-status-icon { font-size: 16px; }
.pkg-name { font-weight: 600; }
.pkg-version { color: #909399; font-size: 12px; }
.stats-row { display: flex; gap: 8px; margin-bottom: 16px; }
.download-btn-row { display: flex; align-items: center; gap: 12px; padding: 16px 0; }
.file-name { color: #909399; font-size: 13px; }
</style>
