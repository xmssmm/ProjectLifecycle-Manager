<template>
  <el-container class="app-shell">
    <el-aside
      class="app-sidebar"
      width="248px"
    >
      <div class="brand">
        <span class="brand-mark">PM</span>
        <span class="brand-text">项目管理归档</span>
      </div>
      <el-menu
        class="nav-menu"
        default-active="/"
        router
      >
        <el-menu-item index="/">
          <span>工作台</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div>
          <h1>企业项目过程管理与资料归档系统</h1>
          <p>基础工程骨架已就绪</p>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
