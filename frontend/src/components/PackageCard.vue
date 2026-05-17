<template>
  <el-card
    shadow="hover"
    :class="['package-card', { selected: isSelected }]"
    @click="$emit('select', packageData)"
  >
    <div v-if="isSelected" class="selected-badge">
      <el-icon color="#fff" :size="16"><Check /></el-icon>
    </div>
    <div class="pkg-header">
      <div class="pkg-info">
        <span class="pkg-name">{{ packageData.name }}</span>
        <el-tag size="small" type="warning" effect="plain" style="margin-left: 8px">
          {{ packageData.label || packageData.source }}
        </el-tag>
      </div>
      <div class="pkg-meta">
        <span v-if="packageData.version" class="pkg-version">
          最新版: {{ packageData.version }}
        </span>
        <span v-if="packageData.source_warning" class="pkg-warning">
          <el-tag size="small" type="danger" effect="light">⚠ {{ packageData.source_warning }}</el-tag>
        </span>
      </div>
    </div>
    <div v-if="packageData.description" class="pkg-desc">
      {{ packageData.description }}
    </div>
    <div class="pkg-stats">
      <el-tag v-if="packageData.dependencies" size="small" type="info">
        {{ packageData.dependencies }} 依赖
      </el-tag>
      <el-tag v-if="packageData.file_size" size="small" type="info">
        {{ formatSize(packageData.file_size) }}
      </el-tag>
      <el-tag v-if="packageData.cached_count" size="small" type="success">
        📦 仓库已有 {{ packageData.cached_count }} 个
      </el-tag>
    </div>
    <div v-if="packageData.error" class="pkg-error">
      <el-alert :title="packageData.description" type="warning" show-icon :closable="false" size="small" />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Check } from '@element-plus/icons-vue'

const props = defineProps<{
  package: any
  lang: string
  selected?: boolean
}>()

const emit = defineEmits<{
  select: [pkg: any]
}>()

const packageData = computed(() => props.package)
const isSelected = computed(() => props.selected)

function formatSize(bytes: number): string {
  if (!bytes) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(1)} ${units[i]}`
}
</script>

<style scoped>
.package-card {
  cursor: pointer;
  transition: all 0.2s;
  border-radius: 8px;
  margin-bottom: 8px;
  position: relative;
  overflow: hidden;
}

.package-card:hover {
  border-color: #409eff;
}

.package-card.selected {
  border-color: #409eff;
  background-color: #ecf5ff;
  box-shadow: 0 0 0 1px #409eff inset;
}

.package-card.selected::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: #409eff;
  border-radius: 0 2px 2px 0;
}

.selected-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  background: #409eff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  box-shadow: 0 2px 4px rgba(64,158,255,0.3);
}

.pkg-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pkg-info {
  display: flex;
  align-items: center;
}

.pkg-name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.pkg-meta {
  display: flex;
  gap: 8px;
}

.pkg-version {
  font-size: 13px;
  color: #909399;
}

.pkg-desc {
  margin-top: 6px;
  font-size: 13px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pkg-stats {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.pkg-error {
  margin-top: 8px;
}
</style>
