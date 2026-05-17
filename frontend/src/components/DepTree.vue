<template>
  <el-card shadow="never" class="dep-tree-card">
    <template #header>
      <span>
        <el-icon><Connection /></el-icon>
        依赖树
        <el-tag v-if="deps.length > 0" size="small" type="success" style="margin-left: 8px">
          📦 共 {{ deps.length }} 个包
        </el-tag>
        <el-tag v-else-if="!loadingDeps && !loadError" size="small" type="info" style="margin-left: 8px">
          ⏳ 解析中...
        </el-tag>
      </span>
    </template>

    <!-- 加载中 -->
    <div v-loading="loadingDeps" v-if="loadingDeps" style="min-height: 60px;">
      <el-empty description="正在解析依赖树..." :image-size="60" />
    </div>

    <!-- 加载失败 -->
    <div v-else-if="loadError" class="dep-error">
      <el-alert
        :title="'依赖解析失败: ' + loadError"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-button size="small" type="primary" style="margin-top: 8px" @click="retryLoad">
        重新解析
      </el-button>
    </div>

    <!-- 空结果 -->
    <div v-else-if="deps.length === 0">
      <el-empty description="该包无额外依赖" :image-size="60" />
    </div>

    <!-- 依赖列表 -->
    <div v-else>
      <el-table :data="deps" style="width: 100%" size="small" stripe>
        <el-table-column prop="name" label="包名" min-width="180" />
        <el-table-column prop="version" label="版本" width="100" />
        <el-table-column label="来源" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info" effect="plain">{{ sourceLabels[row.source] || row.source }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="下载方式" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.is_cached" size="small" type="success" effect="light">📦 仓库复用</el-tag>
            <el-tag v-else size="small" type="warning" effect="light">⬇ 需下载</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Connection } from '@element-plus/icons-vue'
import { getPackageDependencies } from '@/api'

const props = defineProps<{ packageName: string; version: string; lang: string; source: string; pythonVer: string }>()
const loadingDeps = ref(false)
const loadError = ref('')
const deps = ref<any[]>([])
const sourceLabels: Record<string, string> = { pypi: 'PyPI官方', cran: 'CRAN官方', bioconductor: 'Bioconductor', github: 'GitHub Releases' }

const cachedInfo = computed(() => deps.value.length === 0 ? null : { cached: 0, needDownload: deps.value.length })

watch(() => [props.packageName, props.version], () => { if (props.packageName) loadDeps() })
onMounted(() => { if (props.packageName) loadDeps() })

async function loadDeps() {
  loadingDeps.value = true
  loadError.value = ''
  try {
    const res = await getPackageDependencies(props.lang, props.packageName, props.version, props.source, props.pythonVer)
    deps.value = (res.data.dependencies || []).map((d: any) => ({
      name: d.name,
      version: d.version || '',
      source: d.source || props.source,
      is_cached: false,
    }))
  } catch (e: any) {
    console.error('加载依赖失败:', e)
    loadError.value = e.message || '依赖解析超时或网络错误'
    deps.value = []
  } finally {
    loadingDeps.value = false
  }
}

function retryLoad() {
  loadDeps()
}

defineExpose({ cachedInfo })
</script>
<style scoped>
.dep-tree-card { border-radius: 8px; }
.dep-tree-card :deep(.el-card__body) { min-height: 60px; }
.el-table { margin-top: 4px; }
.dep-error { padding: 8px 0; text-align: center; }
</style>
