<template>
  <div class="search-view">
    <!-- 搜索区域 -->
    <el-card shadow="never" class="search-card">
      <el-form :model="searchForm" label-width="60px" label-position="left">
        <el-row :gutter="16">
          <el-col :span="6">
            <el-form-item label="语言">
              <el-radio-group v-model="searchForm.lang" @change="onLangChange">
                <el-radio-button value="python">Python包</el-radio-button>
                <el-radio-button value="r">R包</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="包名">
              <el-input
                v-model="searchForm.query"
                placeholder="输入包名 (必填)"
                clearable
                @keyup.enter="doSearch"
              />
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="版本">
              <el-input
                v-model="searchForm.version"
                placeholder="选填，默认最新"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="来源">
              <el-select v-model="searchForm.source" style="width: 100%">
                <el-option label="全部来源" value="all" />
                <el-option v-for="s in availableSources" :key="s" :label="sourceLabels[s]" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-button type="primary" :icon="Search" @click="doSearch" :loading="searching">
              搜索
            </el-button>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 搜索结果区域 -->
    <div v-if="searchResults.length > 0" class="results-area">
      <el-card shadow="never" class="results-card">
        <template #header>
          <span>搜索结果 ({{ searchResults.length }})</span>
        </template>
        <div v-for="(pkg, idx) in searchResults" :key="idx" class="result-item">
          <PackageCard
            :package="pkg"
            :lang="searchForm.lang"
            :selected="selectedPackage === pkg"
            @select="onPackageSelect"
          />
        </div>
      </el-card>

      <!-- 版本选择 -->
      <VersionSelect
        v-if="selectedPackage"
        :package-name="selectedPackage.name"
        :lang="searchForm.lang"
        :source="selectedPackage.source"
        @version-change="onVersionChange"
      />

      <!-- 依赖树 -->
      <DepTree
        v-if="selectedPackage"
        :package-name="selectedPackage.name"
        :version="selectedVersion"
        :lang="searchForm.lang"
        :source="selectedPackage.source"
        :python-ver="pythonVersion"
        ref="depTreeRef"
      />

      <!-- 配置和下载 -->
      <el-card shadow="never" class="options-card">
        <el-row :gutter="16" align="middle">
          <el-col :span="4">
            <span class="option-label">目标平台：</span>
            <el-tag>Windows</el-tag>
          </el-col>
          <el-col :span="4" v-if="searchForm.lang === 'python'">
            <span class="option-label">Python版本：</span>
            <el-select v-model="pythonVersion" style="width: 100px">
              <el-option v-for="v in pythonVersions" :key="v" :label="v" :value="v" />
            </el-select>
          </el-col>
          <el-col :span="4" v-else>
            <span class="option-label">R版本：</span>
            <el-select v-model="rVersion" style="width: 100px">
              <el-option v-for="v in rVersions" :key="v" :label="v" :value="v" />
            </el-select>
          </el-col>
          <el-col :span="5">
            <span class="option-label">镜像源：</span>
            <el-select v-model="selectedMirror" style="width: 150px">
              <el-option label="官方源" value="" />
              <el-option v-for="(url, name) in currentMirrors" :key="name" :label="name" :value="url" />
            </el-select>
          </el-col>
          <el-col :span="11">
            <el-checkbox v-model="includeRuntime" label="打包时附带运行时" border size="small" />
            <el-select
              v-if="includeRuntime"
              v-model="selectedRuntime"
              style="width: 180px; margin-left: 8px"
              placeholder="选择运行时版本"
            >
              <el-option
                v-for="r in filteredRuntimes"
                :key="r.version"
                :label="`${r.lang === 'python' ? 'Python' : 'R'} ${r.version}`"
                :value="r.version"
              />
              <el-option
                v-if="filteredRuntimes.length === 0"
                :key="'no-option'"
                :label="'暂无' + (searchForm.lang === 'python' ? 'Python' : 'R') + '运行时'"
                :value="''"
                disabled
              />
            </el-select>
          </el-col>
        </el-row>
        <div style="margin-top: 16px; text-align: right">
          <el-button
            type="success"
            size="large"
            :icon="Download"
            @click="startDownloadTask"
            :loading="downloading"
            :disabled="!selectedPackage"
          >
            🚀 开始下载
          </el-button>
          <span v-if="depTreeRef?.cachedInfo" class="download-info">
            预计: 需新下载{{ depTreeRef.cachedInfo.needDownload }}, 仓库复用{{ depTreeRef.cachedInfo.cached }}
          </span>
        </div>
      </el-card>
    </div>

    <!-- 进度区域 -->
    <DownloadPanel
      v-if="currentTaskId"
      :task-id="currentTaskId"
      :lang="searchForm.lang"
      :source="searchForm.source"
      @done="onTaskDone"
    />

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Search, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PackageCard from '@/components/PackageCard.vue'
import VersionSelect from '@/components/VersionSelect.vue'
import DepTree from '@/components/DepTree.vue'
import DownloadPanel from '@/components/DownloadPanel.vue'
import { searchPackages, startDownload, getConfig, getRuntimes } from '@/api'

const searching = ref(false)
const downloading = ref(false)

const searchResults = ref<any[]>([])
const selectedPackage = ref<any>(null)
const selectedVersion = ref('')
const currentTaskId = ref('')
const depTreeRef = ref<any>(null)
const runtimeList = ref<any[]>([])
const pythonVersions = ref<string[]>(['3.8', '3.9', '3.10', '3.11', '3.12', '3.13'])
const rVersions = ref<string[]>(['4.0', '4.1', '4.2', '4.3', '4.4'])
const pythonVersion = ref('3.11')
const rVersion = ref('4.3')
const selectedMirror = ref('')
const includeRuntime = ref(false)
const selectedRuntime = ref('')
const mirrors = ref<Record<string, Record<string, string>>>({})
const sourceLabels: Record<string, string> = {
  pypi: 'PyPI官方',
  cran: 'CRAN官方',
  bioconductor: 'Bioconductor',
  github: 'GitHub Releases',
}

const searchForm = reactive({
  query: '',
  lang: 'python',
  version: '',
  source: 'all',
})

const filteredRuntimes = computed(() => {
  const lang = searchForm.lang === 'python' ? 'python' : 'r'
  return runtimeList.value.filter((r: any) => r.lang === lang)
})

const availableSources = computed(() => {
  if (searchForm.lang === 'python') return ['pypi', 'github']
  return ['cran', 'bioconductor', 'github']
})

const currentMirrors = computed(() => {
  const key = searchForm.lang === 'python' ? 'pypi' : 'cran'
  return mirrors.value[key] || {}
})

onMounted(async () => {
  try {
    const [configRes, runtimeRes] = await Promise.all([
      getConfig(),
      getRuntimes(),
    ])
    mirrors.value = configRes.data.mirrors || {}
    pythonVersions.value = configRes.data.python_versions || pythonVersions.value
    runtimeList.value = runtimeRes.data.runtimes || []
  } catch (e) {
    console.error('加载配置失败:', e)
  }
})

function onLangChange() {
  searchForm.source = 'all'
  selectedPackage.value = null
  searchResults.value = []
}

async function doSearch() {
  if (!searchForm.query.trim()) {
    ElMessage.warning('请输入包名')
    return
  }
  searching.value = true
  selectedPackage.value = null
  selectedVersion.value = ''
  try {
    const res = await searchPackages(
      searchForm.query.trim(),
      searchForm.lang,
      searchForm.source,
    )
    searchResults.value = res.data.results || []
    if (searchResults.value.length === 0) {
      ElMessage.info('未找到匹配的包')
    }
  } catch (e) {
    ElMessage.error('搜索失败：' + (e as any).message)
  } finally {
    searching.value = false
  }
}

function onPackageSelect(pkg: any) {
  selectedPackage.value = pkg
  selectedVersion.value = ''
}

function onVersionChange(ver: string) {
  selectedVersion.value = ver
}

async function startDownloadTask() {
  if (!selectedPackage.value) {
    ElMessage.warning('请先搜索并选择一个包')
    return
  }

  downloading.value = true
  try {
    const packages = [
      {
        name: selectedPackage.value.name,
        version: selectedVersion.value || undefined,
      },
    ]

    const res = await startDownload({
      lang: searchForm.lang,
      packages,
      source: selectedPackage.value.source || searchForm.source,
      python_version: searchForm.lang === 'python' ? pythonVersion.value : undefined,
      r_version: searchForm.lang === 'r' ? rVersion.value : undefined,
      include_runtime: includeRuntime.value,
      mirror: selectedMirror.value,
    })

    currentTaskId.value = res.data.task_id
    ElMessage.success('下载任务已创建')
  } catch (e) {
    ElMessage.error('创建下载任务失败：' + (e as any).message)
  } finally {
    downloading.value = false
  }
}

function onTaskDone() {
  // 任务完成后的处理
}
</script>

<style scoped>
.search-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.search-card {
  border-radius: 8px;
}

.results-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-item {
  margin-bottom: 8px;
}

.options-card {
  border-radius: 8px;
}

.option-label {
  font-size: 13px;
  color: #909399;
  margin-right: 4px;
}

.download-info {
  margin-left: 12px;
  font-size: 13px;
  color: #909399;
}

</style>
