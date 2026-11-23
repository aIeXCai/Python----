import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './auth-header-mirror.js'
import App from './App.jsx'

// Monaco 编辑器体积很大（约 917K gzip），且只有 AI 课的编程页才用得上。
// 原实现在首屏渲染前 await 加载 monaco-setup，导致登录页、小测页也要先等编辑器
// 下载完才显示。现改为按需加载：由 components/MonacoEditorLazy.jsx 在真正要挂载
// 编辑器之前加载 monaco-setup，仍使用本地 monaco 与本地 worker（离线机房可用，
// 不会回退到公共 CDN）。
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
