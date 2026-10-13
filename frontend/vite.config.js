import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteStaticCopy } from 'vite-plugin-static-copy'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const pyodideDir = dirname(fileURLToPath(import.meta.resolve('pyodide')))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), viteStaticCopy({
    targets: [{
      src: [
        'pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm',
        'python_stdlib.zip', 'pyodide-lock.json',
      ].map(name => join(pyodideDir, name).replace(/\\/g, '/')),
      dest: 'pyodide',
    }],
  })],
  server: {
    // 允许局域网/学生机访问（部署机 IP 如 192.168.1.5）
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    include: ['@monaco-editor/react'],
    exclude: ['pyodide'],
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    include: ['src/**/*.{test,spec}.{js,jsx}'],
  },
})
