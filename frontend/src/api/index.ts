import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 搜索包
export function searchPackages(q: string, lang: string = 'python', source: string = 'all') {
  return api.get('/search', { params: { q, lang, source } })
}

// 包详情
export function getPackageDetail(lang: string, name: string, source: string = 'pypi') {
  return api.get(`/package/${lang}/${name}`, { params: { source } })
}

// 包版本列表
export function getPackageVersions(lang: string, name: string, source: string = 'pypi') {
  return api.get(`/package/${lang}/${name}/versions`, { params: { source } })
}

// 包依赖树
export function getPackageDependencies(lang: string, name: string, version: string = '', source: string = 'cran', pythonVer: string = '') {
  return api.get(`/package/${lang}/${name}/dependencies`, { params: { version, source, python_ver: pythonVer } })
}

// 触发下载
export function startDownload(data: {
  lang: string
  packages: { name: string; version?: string }[]
  source: string
  python_version?: string
  r_version?: string
  include_runtime?: boolean
  mirror?: string
}) {
  return api.post('/download', data)
}

// 任务状态
export function getTaskStatus(taskId: string) {
  return api.get(`/download/${taskId}/status`)
}

// 下载打包文件
export function getExportUrl(taskId: string) {
  return `/api/download/${taskId}/export`
}

// 任务列表
export function getTaskList(params: {
  lang?: string
  status?: string
  search?: string
  page?: number
  page_size?: number
}) {
  return api.get('/tasks', { params })
}

// 任务详情
export function getTaskDetail(taskId: string) {
  return api.get(`/tasks/${taskId}`)
}

// 搜索历史任务
export function searchTasks(q: string, lang?: string, source?: string) {
  return api.get('/tasks/search', { params: { q, lang, source } })
}

// 一键复用
export function reuseTask(taskId: string) {
  return api.post(`/tasks/${taskId}/reuse`)
}

// 删除任务
export function deleteTask(taskId: string) {
  return api.delete(`/tasks/${taskId}`)
}

// 仓库统计
export function getRepositoryStats() {
  return api.get('/repository/stats')
}

// 配置/镜像源
export function getConfig() {
  return api.get('/config/mirrors')
}

// 运行时列表
export function getRuntimes() {
  return api.get('/runtimes')
}

// 运行时同步
export function syncRuntimes() {
  return api.post('/runtimes/sync')
}

// 运行时下载 URL
export function getRuntimeDownloadUrl(type: string, version: string) {
  return `/api/runtimes/download/${type}/${version}`
}

// GitHub 搜索
export function searchGitHub(q: string, lang: string = 'python') {
  return api.post('/github/search', { q, lang })
}

export default api
