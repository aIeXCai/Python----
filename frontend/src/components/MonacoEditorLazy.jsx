import { useEffect, useState } from 'react'
import Editor from '@monaco-editor/react'

/**
 * 按需加载 Monaco 的编辑器包装。
 *
 * 背景：monaco-setup 静态引入整个 monaco-editor（约 917K gzip），原先在 main.jsx 里
 * 于首屏渲染前 await，导致登录页、小测页也要先把编辑器下载完才显示。
 *
 * 这里改为：真正要挂载编辑器时，才去执行 monaco-setup（配置本地 monaco 与 worker），
 * 完成后再渲染 <Editor>。这样既能省掉首屏体积，又保证离线机房不会回退到公共 CDN。
 *
 * 测试环境（MODE === 'test'）直接渲染，测试里的 vi.mock('@monaco-editor/react') 照常生效。
 */
let setupPromise = null

function ensureMonacoSetup() {
  if (!setupPromise) {
    setupPromise = import('../monaco-setup.js')
  }
  return setupPromise
}

export default function MonacoEditorLazy(props) {
  const [ready, setReady] = useState(import.meta.env.MODE === 'test')

  useEffect(() => {
    if (ready) return undefined
    let alive = true
    ensureMonacoSetup()
      .then(() => {
        if (alive) setReady(true)
      })
      .catch(() => {
        // 加载失败也放行，交给 @monaco-editor/react 自己的错误处理
        if (alive) setReady(true)
      })
    return () => {
      alive = false
    }
  }, [ready])

  if (!ready) {
    return (
      <div
        style={{
          height: props.height || '390px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: props.theme === 'vs-dark' ? '#1e1e1e' : '#fffffe',
          color: props.theme === 'vs-dark' ? '#9aa4b2' : '#646a73',
          fontSize: 14,
        }}
      >
        编辑器加载中…
      </div>
    )
  }

  return <Editor {...props} />
}
