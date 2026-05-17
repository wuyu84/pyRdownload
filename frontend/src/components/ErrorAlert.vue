<template>
  <el-alert v-if="error" :title="friendlyError" type="error" show-icon :closable="true" class="error-alert">
    <template #default>
      <div class="error-content">
        <p v-if="suggestion" class="error-suggestion"><el-icon><InfoFilled /></el-icon>建议：{{ suggestion }}</p>
        <el-collapse>
          <el-collapse-item title="技术详情" name="details">
            <pre class="error-detail">{{ error }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>
    </template>
  </el-alert>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
const props = defineProps<{ error: string; suggestion?: string }>()
const friendlyError = computed(() => props.error.length > 80 ? props.error.slice(0, 80) + '...' : props.error)
</script>
<style scoped>
.error-alert { margin-top: 12px; }
.error-content { font-size: 13px; }
.error-suggestion { display: flex; align-items: center; gap: 4px; color: #606266; margin-bottom: 8px; }
.error-detail { font-size: 12px; color: #909399; white-space: pre-wrap; max-height: 200px; overflow-y: auto; background: #f5f7fa; padding: 8px; border-radius: 4px; }
</style>
