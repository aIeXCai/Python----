import { useCallback, useEffect, useRef, useState } from 'react'
import Editor from '@monaco-editor/react'
import { Loader, Play, Terminal } from 'lucide-react'
import { pollExecutionTask, runCode } from '../../../api/index.js'
import { useChat } from '../../../contexts/ChatContext.jsx'

const statusMessage = {
  runtime_error: '代码运行时出错',
  timed_out: '代码执行超时',
  resource_limited: '资源使用超出限制',
  system_error: '评测服务暂时异常',
  cancelled: '排队超时，请重新运行',
}

function normalizeResult(task = {}) {
  const output = task.output || task.stdout || ''
  const reportedError = task.error || task.stderr || ''
  const fallbackError = task.status && task.status !== 'succeeded'
    ? statusMessage[task.status] || ''
    : ''
  return {
    status: task.status || 'succeeded',
    output,
    error: reportedError || fallbackError,
  }
}

export default function FreePracticeWorkspace() {
  const { setContext } = useChat()
  const [code, setCode] = useState('')
  const [isRunning, setIsRunning] = useState(false)
  const [taskStatus, setTaskStatus] = useState('')
  const [result, setResult] = useState(null)
  const [stdinDialogOpen, setStdinDialogOpen] = useState(false)
  const [stdinValue, setStdinValue] = useState('')
  const runControllerRef = useRef(null)

  useEffect(() => {
    setContext({
      type: 'ai_free_practice',
      title: '自由练习',
      code,
    })
  }, [code, setContext])

  useEffect(() => () => {
    runControllerRef.current?.abort()
    setContext(null)
  }, [setContext])

  const executeRun = useCallback(async (sourceCode, stdin) => {
    const controller = new AbortController()
    runControllerRef.current?.abort()
    runControllerRef.current = controller
    setIsRunning(true)
    setTaskStatus('queueing')
    setResult(null)

    try {
      const initialTask = await runCode(sourceCode, stdin)
      if (controller.signal.aborted) return

      if (!initialTask?.task_id) {
        setResult(normalizeResult(initialTask))
        return
      }

      setTaskStatus(initialTask.status || 'queued')
      const task = await pollExecutionTask(initialTask.task_id, {
        signal: controller.signal,
        initialDelay: initialTask.poll_after_ms || 500,
        onUpdate(update) {
          setTaskStatus(update.status || 'running')
        },
      })
      if (!controller.signal.aborted) setResult(normalizeResult(task))
    } catch (error) {
      if (error.name !== 'AbortError') {
        setResult({ status: 'request_error', output: '', error: error.message || '运行失败，请稍后重试' })
      }
    } finally {
      if (runControllerRef.current === controller && !controller.signal.aborted) {
        runControllerRef.current = null
        setIsRunning(false)
        setTaskStatus('')
      }
    }
  }, [])

  const handleRun = () => {
    if (!code.trim() || isRunning) return
    if (code.includes('input(')) {
      setStdinDialogOpen(true)
      return
    }
    executeRun(code, '')
  }

  const handleStdinSubmit = () => {
    const currentInput = stdinValue
    setStdinDialogOpen(false)
    setStdinValue('')
    executeRun(code, currentInput)
  }

  const handleStdinCancel = () => {
    setStdinDialogOpen(false)
    setStdinValue('')
  }

  const runningLabel = taskStatus === 'running' ? '运行中…' : '排队中…'

  return (
    <div className="free-practice-workspace">
      <div className="free-practice-editor">
        <Editor
          height="420px"
          language="python"
          theme="vs-dark"
          value={code}
          onChange={value => setCode(value || '')}
          options={{
            ariaLabel: 'Python 代码编辑器',
            fontSize: 14,
            minimap: { enabled: false },
            tabSize: 4,
            automaticLayout: true,
            scrollBeyondLastLine: false,
          }}
        />
      </div>

      <div className="free-practice-actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={isRunning || !code.trim()}
          onClick={handleRun}
        >
          {isRunning
            ? <><Loader size={16} className="spin" />{runningLabel}</>
            : <><Play size={16} />运行代码</>}
        </button>
      </div>

      {result && (
        <section className="free-practice-result" aria-label="运行结果">
          <div className="free-practice-result-title"><Terminal size={17} />运行结果</div>
          {result.output && <pre>{result.output}</pre>}
          {result.error && <pre className="error">{result.error}</pre>}
          {!result.output && !result.error && <p>（无输出）</p>}
        </section>
      )}

      {stdinDialogOpen && (
        <div className="ide-overlay" onClick={handleStdinCancel}>
          <div className="ide-dialog" role="dialog" aria-modal="true" aria-labelledby="free-practice-input-title" onClick={event => event.stopPropagation()}>
            <h3 id="free-practice-input-title">📥 输入</h3>
            <p>代码使用了 input()，请输入程序需要的值。多次输入请按行填写：</p>
            <textarea
              className="ide-dialog-input"
              value={stdinValue}
              onChange={event => setStdinValue(event.target.value)}
              placeholder="在此输入..."
              rows={4}
              autoFocus
            />
            <div className="ide-dialog-actions">
              <button type="button" className="ide-btn ide-btn-reset" onClick={handleStdinCancel}>取消</button>
              <button type="button" className="ide-btn ide-btn-run" onClick={handleStdinSubmit}>运行</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
