import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      // 仅开发环境使用；生产通过 VITE_API_BASE_URL 指定完整地址
      '/api': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true
      }
    }
  }
})
