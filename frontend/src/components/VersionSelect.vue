<template>
  <el-card shadow="never" class="version-card" v-if="versions.length > 0">
    <template #header>
      <span>版本选择 - {{ packageName }}</span>
    </template>
    <el-radio-group v-model="selectedVersion" @change="onChange">
      <el-radio-button value="">最新版</el-radio-button>
      <el-radio-button
        v-for="v in displayVersions"
        :key="v.version"
        :value="v.version"
      >
        {{ v.version }}
        <el-tag v-if="v.is_cached" size="small" type="success" style="margin-left: 4px">📦</el-tag>
      </el-radio-button>
    </el-radio-group>
    <div v-if="versions.length > 10" class="show-more">
      <el-button text type="primary" @click="showAll = !showAll">
        {{ showAll ? '收起' : '显示全部' }} (共{{ versions.length }}个版本)
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { getPackageVersions } from '@/api'

const props = defineProps<{
  packageName: string
  lang: string
  source: string
}>()

const emit = defineEmits<{
  'version-change': [version: string]
}>()

const versions = ref<any[]>([])
const selectedVersion = ref('')
const showAll = ref(false)

const displayVersions = computed(() => {
  if (showAll.value) return versions.value
  return versions.value.slice(0, 10)
})

const emitChange = () => {
  emit('version-change', selectedVersion.value)
}

watch(() => props.packageName, () => {
  loadVersions()
})

onMounted(() => {
  loadVersions()
})

async function loadVersions() {
  if (!props.packageName) return
  try {
    const res = await getPackageVersions(props.lang, props.packageName, props.source)
    versions.value = res.data.versions || []
  } catch (e) {
    console.error('加载版本列表失败:', e)
  }
}

function onChange(val: string) {
  emit('version-change', val)
}
</script>

<style scoped>
.version-card {
  border-radius: 8px;
}

.show-more {
  margin-top: 8px;
  text-align: center;
}

.el-radio-button {
  margin: 4px;
}
</style>
