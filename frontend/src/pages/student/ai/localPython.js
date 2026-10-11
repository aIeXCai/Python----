let worker
let readyPromise
let nextId = 0
let runChain = Promise.resolve()

function stopWorker() {
  worker?.terminate()
  worker = undefined
  readyPromise = undefined
}

function ensureWorker() {
  if (readyPromise) return readyPromise
  worker = new Worker(new URL('./localPython.worker.js', import.meta.url), { type: 'module' })
  const current = worker
  readyPromise = new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      stopWorker()
      reject(new Error('本地 Python 加载超时，请刷新页面重试'))
    }, 30000)
    current.onmessage = ({ data }) => {
      if (data.type !== 'ready' && data.type !== 'init_error') return
      clearTimeout(timer)
      if (data.type === 'ready') resolve(current)
      else {
        stopWorker()
        reject(new Error(`本地 Python 加载失败：${data.error}`))
      }
    }
    current.onerror = () => {
      clearTimeout(timer)
      stopWorker()
      reject(new Error('本地 Python 无法启动'))
    }
    current.postMessage({ type: 'init' })
  })
  return readyPromise
}

export function prepareLocalPython() {
  return ensureWorker()
}

function execute(code, stdin, timeoutMs) {
  const operation = runChain.catch(() => undefined).then(async () => {
    const current = await ensureWorker()
    const id = ++nextId
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        stopWorker()
        resolve({ status: 'timed_out', output: '', error: '代码运行超时，请检查循环是否能够结束' })
      }, timeoutMs)
      current.onmessage = ({ data }) => {
        if (data.type !== 'result' || data.id !== id) return
        clearTimeout(timer)
        resolve(data)
      }
      current.postMessage({ type: 'execute', id, code, stdin })
    })
  })
  runChain = operation
  return operation
}

export function runLocalPython(code, stdin = '') {
  return execute(code, stdin, 10000)
}

export async function gradeLocalPython(code, cases) {
  if (!code.trim()) return { score: 0, status: 'empty', passed: 0, total: cases.length }
  if (!Array.isArray(cases) || !cases.length) throw new Error('题目测试点不可用')
  let passed = 0
  let status = 'succeeded'
  for (const test of cases) {
    const result = await execute(code, test.input || '', 5000)
    if (result.status === 'system_error') throw new Error(result.error || '本地评分失败')
    if (result.status !== 'succeeded') {
      status = result.status
      if (status === 'timed_out') break
      continue
    }
    if ((result.output || '').trim() === (test.output || '').trim()) passed += 1
    else status = 'wrong_answer'
  }
  return { score: Math.round(passed * 10000 / cases.length) / 100, status, passed, total: cases.length }
}
