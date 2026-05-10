import { fileURLToPath, URL } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    coverage: {
      all: true,
      exclude: ['dist/**', 'node_modules/**', 'src/main.ts', 'src/vite-env.d.ts', 'vite.config.ts'],
      include: ['src/**/*.{ts,vue}'],
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      thresholds: {
        branches: 0,
        functions: 50,
        lines: 50,
        statements: 50,
      },
    },
    environment: 'jsdom',
  },
});
