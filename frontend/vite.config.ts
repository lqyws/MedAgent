import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发代理：/api → FastAPI 后端 8001
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3001,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
