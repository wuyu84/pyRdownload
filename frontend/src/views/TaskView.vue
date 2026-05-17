<template>
  <div class="task-view">
    <el-card shadow="never">
      <template #header>
        <div class="task-header">
          <span><el-icon :size="20"><List /></el-icon> 任务一览表</span>
          <div class="task-tools">
            <el-input
              v-model="searchQuery"
              placeholder="搜索历史任务（包名/版本/任务ID）"
              clearable
              style="width: 300px; margin-right: 12px"
              @keyup.enter="loadTasks"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button type="primary" :icon="Search" @click="loadTasks">搜索</el-button>
          </div>
        </div>
      </template>

      <!-- 筛选标签 -->
      <div class="filter-bar">
        <el-radio-group v-model="filterLang" @change="loadTasks" style="margin-right: 16px">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="python">Python</el-radio-button>
          <el-radio-button value="r">R</el-radio-button>
        </el-radio-group>
        <el-radio-group v-model="filterStatus" @change="loadTasks">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="pending">进行中</el-radio-button>
          <el-radio-button value="done">已完成</el-radio-button>
          <el-radio-button value="failed">失败</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 任务列表 -->
      <el-table :data="tasks" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="任务ID" width="160" />
        <el-table-column prop="package_name" label="包名" width="140">
          <template #default="{ row }">
            <el-tag :type="row.lang === 'python' ? 'primary' : 'success'" size="small">
              {{ row.lang === 'python' ? 'Py' : 'R' }}
            </el-tag>
            {{ row.package_name }}
          </template>
        </el-table-column>
        <el-table-column label="来源" width="110">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.source || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="package_version" label="版本" width="100">
          <template #default="{ row }">{{ row.package_version || '最新' }}</template>
        </el-table-column>
        <el-table-column prop="total_pkgs" label="包总数" width="80" align="center" />
        <el-table-column label="复用率" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.total_pkgs > 0">
              {{ row.cached_pkgs }}/{{ row.total_pkgs }}
              <el-tag v-if="row.cached_pkgs === row.total_pkgs && row.total_pkgs > 0" size="small" type="success">100%</el-tag>
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="client_ip" label="来源IP" width="130" />
        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ row.created_at || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'done'" type="success">✅ 完成</el-tag>
            <el-tag v-else-if="row.status === 'failed'" type="danger">❌ 失败</el-tag>
            <el-tag v-else type="warning">⏳ {{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'done' && row.export_path"
              type="primary"
              size="small"
              :icon="Download"
              @click="downloadExport(row)"
            >
              下载
            </el-button>
            <el-button
              v-if="row.status === 'done'"
              size="small"
              @click="reuseTask(row)"
            >
              复用
            </el-button>
            <el-button
              size="small"
              type="danger"
              text
              @click="confirmDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-bar" v-if="total > 0">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadTasks"
        />
      </div>

      <!-- 提示信息 -->
      <el-alert
        v-if="tasks.length > 0"
        type="info"
        show-icon
        :closable="false"
        style="margin-top: 16px"
      >
        <template #title>
          💡 点击「复用」可秒级打包下载已完成的任务
        </template>
      </el-alert>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Search, Download, List } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTaskList, getExportUrl, reuseTask as reuseTaskApi, deleteTask } from '@/api'

const loading = ref(false)
const tasks = ref<any[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const searchQuery = ref('')
const filterLang = ref('')
const filterStatus = ref('')

onMounted(() => {
  loadTasks()
})

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '等待中',
    downloading: '下载中',
    packaging: '打包中',
  }
  return map[status] || status
}

async function loadTasks() {
  loading.value = true
  try {
    const res = await getTaskList({
      lang: filterLang.value,
      status: filterStatus.value,
      search: searchQuery.value,
      page: currentPage.value,
      page_size: pageSize,
    })
    tasks.value = res.data.tasks || []
    total.value = res.data.total || 0
  } catch (e) {
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
}

function downloadExport(task: any) {
  const url = getExportUrl(task.id)
  window.open(url, '_blank')
}

async function reuseTask(task: any) {
  try {
    const res = await reuseTaskApi(task.id)
    if (res.data.success) {
      ElMessage.success('打包完成，正在下载...')
      const url = getExportUrl(task.id)
      window.open(url, '_blank')
    } else {
      ElMessageBox.confirm(
        res.data.hint || '部分包已缺失',
        '提示',
        {
          confirmButtonText: '补充下载',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
    }
  } catch (e) {
    ElMessage.error('复用失败：' + (e as any).message)
  }
}

function confirmDelete(task: any) {
  ElMessageBox.confirm('确定删除任务记录？仓库中的包文件不会被删除', '确认', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await deleteTask(task.id)
      ElMessage.success('任务已删除')
      loadTasks()
    } catch (e) {
      ElMessage.error('删除失败')
    }
  })
}
</script>

<style scoped>
.task-view {
  width: 100%;
}

.task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
}

.task-tools {
  display: flex;
  align-items: center;
}

.filter-bar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
}

.pagination-bar {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}
</style>
