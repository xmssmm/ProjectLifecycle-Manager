<script setup lang="ts">
import { Bell, Box, Folder, House, Setting } from '@element-plus/icons-vue';
</script>

<template>
  <el-container class="app-shell">
    <el-aside class="app-sidebar" width="248px">
      <div class="brand">
        <span class="brand-mark">PM</span>
        <span class="brand-text">项目归档</span>
      </div>
      <el-menu class="nav-menu" default-active="/" router>
        <el-menu-item index="/">
          <el-icon><House /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item disabled index="/main-projects">
          <el-icon><Folder /></el-icon>
          <span>项目</span>
        </el-menu-item>
        <el-menu-item disabled index="/notifications">
          <el-icon><Bell /></el-icon>
          <span>通知</span>
        </el-menu-item>
        <el-menu-item index="/component-demo">
          <el-icon><Box /></el-icon>
          <span>组件</span>
        </el-menu-item>
        <el-menu-item disabled index="/admin">
          <el-icon><Setting /></el-icon>
          <span>管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div>
          <h1>企业项目过程管理与资料归档系统</h1>
          <p>基础工作区</p>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
