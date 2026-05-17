<template>
  <div id="pkg-downloader-app">
    <el-container>
      <el-header class="app-header">
        <div class="header-content">
          <h1 class="app-title">
            <el-icon :size="28"><Box /></el-icon>
            Python&amp;R包下载器
          </h1>
          <el-menu
            :default-active="currentRoute"
            mode="horizontal"
            router
            class="header-menu"
          >
            <el-menu-item index="/search">
              <el-icon><Search /></el-icon>
              包搜索
            </el-menu-item>
            <el-menu-item index="/tasks">
              <el-icon><List /></el-icon>
              任务一览表
            </el-menu-item>
          </el-menu>
          <div class="header-info">
            <el-tag type="info" size="small">v1.4</el-tag>
          </div>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const currentRoute = computed(() => route.path)
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: #f5f7fa;
  color: #303133;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  padding: 0 20px;
  height: 60px !important;
}

.header-content {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  height: 100%;
  gap: 24px;
}

.app-title {
  font-size: 20px;
  font-weight: 600;
  color: #409eff;
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.header-menu {
  flex: 1;
  border-bottom: none !important;
  background: transparent;
}

.header-menu .el-menu-item {
  font-size: 14px;
}

.header-info {
  margin-left: auto;
}

.app-main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
  min-height: calc(100vh - 60px);
}
</style>
