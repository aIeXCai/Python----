import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { BookOpen, Send, ArrowLeft, Loader, CheckCircle, XCircle, Clock, Play, RotateCcw, ChevronDown, ChevronRight } from 'lucide-react'
import Editor from '@monaco-editor/react'
import Navbar from '../../../components/Navbar.jsx'
import {
  getActiveExecutionTask,
  getProblemDetail,
  getSubmissionHistory,
  pollExecutionTask,
  runCode,
  submitCode,
} from '../../../api/index.js'
import { useChat } from '../../../contexts/ChatContext.jsx'

const SUBMISSION_STATUS_LABELS = {
  pending: '等待评测',
  running: '正在评测',
  accepted: '已通过',
  wrong_answer: '答案错误',
  runtime_error: '运行时错误',
  timeout: '执行超时',
  error: '系统错误',
}

function normalizeGradeResult(task) {
  const statusLabels = {
    succeeded: '全部测试点通过',
    wrong_answer: '部分测试点未通过',
    runtime_error: '代码运行时出错',
    timed_out: '代码执行超时',
    resource_limited: '代码的内存、进程数或输出超出限制',
    system_error: '评测服务暂时异常，本次不计分，请稍后重试',
    cancelled: '排队超时，本次不计分，请重新提交',
  }
  const lines = [statusLabels[task.status] || '评测已完成']
  for (const test of task.detail?.tests || []) {
    if (test.status === 'passed') {
      lines.push(`测试点 ${test.number}：通过`)
    } else {
      lines.push(
        `测试点 ${test.number}：${test.status}`,
        `正确输出：${test.expected_output || '(无输出)'}`,
        `你的输出：${test.actual_output || '(无输出)'}`,
      )
      if (test.stderr) lines.push(test.stderr)
    }
  }
  return {
    success: task.status === 'succeeded',
    score: typeof task.score === 'number' ? task.score : undefined,
    detail: lines.join('\n'),
  }
}

export default function ProblemDetail() {
  const { problemId } = useParams()
  const navigate = useNavigate()
  const chat = useChat()

  const [problem, setProblem] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [username, setUsername] = useState('')
  const [grade, setGrade] = useState('')
  const [classNum, setClassNum] = useState('')
  const [code, setCode] = useState('')
  const [runOutput, setRunOutput] = useState(null)
  const [stdinDialogOpen, setStdinDialogOpen] = useState(false)
  const [stdinValue, setStdinValue] = useState('')
  const [running, setRunning] = useState(false)
  const [testCasesOpen, setTestCasesOpen] = useState(true)
  const [lastError, setLastError] = useState('')
  const [runTaskStatus, setRunTaskStatus] = useState('')
  const [submitTaskStatus, setSubmitTaskStatus] = useState('')
  const runTaskIdRef = useRef(null)
  const submitTaskIdRef = useRef(null)
  const runAbortRef = useRef(null)
  const submitAbortRef = useRef(null)

  const monitorRunTask = useCallback(async (initialTask) => {
    const taskId = initialTask.task_id
    runAbortRef.current?.abort()
    const controller = new AbortController()
    runAbortRef.current = controller
    runTaskIdRef.current = taskId
    setRunning(true)
    setRunTaskStatus(initialTask.status)
    try {
      const finalTask = await pollExecutionTask(taskId, {
        signal: controller.signal,
        initialDelay: initialTask.poll_after_ms || 500,
        onUpdate: (task) => {
          if (runTaskIdRef.current === taskId) setRunTaskStatus(task.status)
        },
      })
      if (runTaskIdRef.current !== taskId) return
      const fallbackErrors = {
        timed_out: '执行超时',
        resource_limited: '资源使用超限',
        system_error: '执行服务暂时异常，请稍后重试',
        cancelled: '排队超时，请重新运行',
      }
      setRunOutput({
        output: finalTask.output || '',
        error: finalTask.error || fallbackErrors[finalTask.status] || '',
      })
    } catch (err) {
      if (err.name !== 'AbortError' && runTaskIdRef.current === taskId) {
        setRunOutput({ output: '', error: err.message })
      }
    } finally {
      if (runTaskIdRef.current === taskId) {
        runTaskIdRef.current = null
        runAbortRef.current = null
        setRunning(false)
        setRunTaskStatus('')
      }
    }
  }, [])

  const monitorGradeTask = useCallback(async (initialTask) => {
    const taskId = initialTask.task_id
    submitAbortRef.current?.abort()
    const controller = new AbortController()
    submitAbortRef.current = controller
    submitTaskIdRef.current = taskId
    setSubmitting(true)
    setSubmitTaskStatus(initialTask.status)
    try {
      const finalTask = await pollExecutionTask(taskId, {
        signal: controller.signal,
        initialDelay: initialTask.poll_after_ms || 500,
        onUpdate: (task) => {
          if (submitTaskIdRef.current === taskId) setSubmitTaskStatus(task.status)
        },
      })
      if (submitTaskIdRef.current !== taskId) return
      const normalized = normalizeGradeResult(finalTask)
      setResult(normalized)
      setLastError(normalized.success ? '' : normalized.detail)
      try {
        const hist = await getSubmissionHistory()
        if (submitTaskIdRef.current === taskId) {
          setHistory(hist.filter((item) => item.problem_id === problemId))
        }
      } catch (err) {
        if (err.name !== 'AbortError') console.error('刷新提交历史失败:', err)
      }
    } catch (err) {
      if (err.name !== 'AbortError' && submitTaskIdRef.current === taskId) {
        setResult({ success: false, detail: err.message })
      }
    } finally {
      if (submitTaskIdRef.current === taskId) {
        submitTaskIdRef.current = null
        submitAbortRef.current = null
        setSubmitting(false)
        setSubmitTaskStatus('')
      }
    }
  }, [problemId])

  useEffect(() => {
    const loadController = new AbortController()
    const raw = localStorage.getItem('user')
    if (!raw) { navigate('/login'); return }
    try {
      const u = JSON.parse(raw)
      setUsername(u.display_name || u.username || '')
      setGrade(u.grade || '')
      setClassNum(u.class_num || '')
    } catch {}
    const loadData = async () => {
      setLoading(true)
      try {
        const [pd, hist, activeRun, activeGrade] = await Promise.all([
          getProblemDetail(problemId),
          getSubmissionHistory(),
          getActiveExecutionTask({ taskType: 'run', signal: loadController.signal }),
          getActiveExecutionTask({ taskType: 'grade', problemId, signal: loadController.signal }),
        ])
        if (loadController.signal.aborted) return
        setProblem(pd)
        const problemHistory = hist.filter((item) => item.problem_id === problemId)
        setHistory(problemHistory)
        const latestFailed = problemHistory.find((item) => item.score < 100 && item.error_message)
        setLastError(latestFailed?.error_message || '')
        setCode(pd?.template_code || '')
        if (activeRun) monitorRunTask(activeRun)
        if (activeGrade) monitorGradeTask(activeGrade)
      } catch (err) {
        if (err.name !== 'AbortError') console.error(err)
      } finally {
        if (!loadController.signal.aborted) setLoading(false)
      }
    }
    loadData()
    return () => {
      loadController.abort()
      runAbortRef.current?.abort()
      submitAbortRef.current?.abort()
      runTaskIdRef.current = null
      submitTaskIdRef.current = null
    }
  }, [monitorGradeTask, monitorRunTask, navigate, problemId])

  // Register AI problem context for chat assistant
  useEffect(() => {
    if (problem) {
      chat.setContext({
        type: 'ai_problem',
        id: problemId,
        title: problem.title || problemId,
        description: problem.description || '',
        last_error: lastError,
      })
    }
    return () => chat.setContext(null)
  }, [problem, problemId, lastError])

  const handleRun = async () => {
    if (!code.trim()) return
    setRunning(true)
    setRunOutput(null)

    if (code.includes('input(')) {
      setStdinDialogOpen(true)
      setRunning(false)
      return
    }

    await executeRun(code, '')
  }

  const executeRun = async (sourceCode, stdin) => {
    setRunning(true)
    setRunTaskStatus('queueing')
    setRunOutput(null)
    try {
      const task = await runCode(sourceCode, stdin)
      if (!task.task_id) {
        setRunOutput({ output: task.output || task.stdout || '', error: task.error || task.stderr || '' })
        return
      }
      await monitorRunTask(task)
    } catch (err) {
      if (err.name !== 'AbortError') setRunOutput({ output: '', error: err.message })
    } finally {
      if (!runTaskIdRef.current) {
        setRunning(false)
        setRunTaskStatus('')
      }
    }
  }

  const handleStdinSubmit = () => {
    setStdinDialogOpen(false)
    executeRun(code, stdinValue)
    setStdinValue('')
  }

  const handleStdinCancel = () => {
    setStdinDialogOpen(false)
    setStdinValue('')
  }

  const handleReset = () => {
    if (problem?.template_code) {
      setCode(problem.template_code)
    } else {
      setCode('')
    }
    setRunOutput(null)
    setResult(null)
  }

  const handleSubmitCode = async () => {
    if (!code.trim()) return
    setSubmitting(true)
    setSubmitTaskStatus('queueing')
    setResult(null)
    try {
      const task = await submitCode({ problem_id: problemId, code })
      if (!task.task_id) {
        const normalized = {
          success: task.passed !== undefined ? task.passed : task.success,
          score: task.score ?? (task.passed ? 100 : 0),
          detail: task.output || task.detail || task.message || JSON.stringify(task),
        }
        setResult(normalized)
        setLastError(normalized.score < 100 ? normalized.detail : '')
        const hist = await getSubmissionHistory()
        setHistory(hist.filter((item) => item.problem_id === problemId))
        return
      }
      await monitorGradeTask(task)
    } catch (err) {
      if (err.name !== 'AbortError') setResult({ success: false, detail: err.message })
    } finally {
      if (!submitTaskIdRef.current) {
        setSubmitting(false)
        setSubmitTaskStatus('')
      }
    }
  }

  const scoreClass = (score) => {
    if (score >= 100) return 'score-excellent'
    if (score >= 70) return 'score-good'
    if (score >= 40) return 'score-fair'
    return 'score-poor'
  }

  const statusIcon = (status) => {
    if (status === 'accepted') return <CheckCircle size={14} className="text-green" />
    if (['wrong_answer', 'runtime_error', 'timeout'].includes(status)) return <XCircle size={14} className="text-red" />
    return <Clock size={14} className="text-yellow" />
  }

  if (loading) {
    return (
      <div className="page-bg">
        <Navbar username={username} grade={grade} class_num={classNum} />
        <div className="loading-state"><Loader size={32} className="spin" /><p>加载题目中...</p></div>
      </div>
    )
  }

  if (!problem) {
    return (
      <div className="page-bg">
        <Navbar username={username} grade={grade} class_num={classNum} />
        <div className="loading-state"><p>题目不存在</p><Link to="/student/dashboard" className="btn btn-primary">返回主页</Link></div>
      </div>
    )
  }

  return (
    <div className="page-bg">
      <Navbar username={username} grade={grade} class_num={classNum} />

      <main className="main-content problem-layout">
        {/* Left sidebar: problem list */}
        <aside className="problems-sidebar">
          <div className="sidebar-header">
            <h2><BookOpen size={20} /> 题目列表</h2>
          </div>
          <div className="problems-list">
            <div className="problem-item active">
              <h4>{problem.title || problemId}</h4>
              <p>{problem.test_cases?.length || 0} 个测试点</p>
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <Link to="/student/dashboard" className="btn btn-secondary" style={{ width: '100%', justifyContent: 'center' }}>
              <ArrowLeft size={16} /> 返回主页
            </Link>
          </div>
        </aside>

        {/* Right: answer area */}
        <div className="answer-area">
          {/* Problem info */}
          <div className="problem-header">
            <h1 className="problem-title">
              <BookOpen size={28} />
              {problem.title || problemId}
            </h1>
            <div className="problem-meta">
              <span className="meta-item"><BookOpen size={14} /> {problem.test_cases?.length || 0} 个测试点</span>
              {problem.difficulty && (
                <span className={`difficulty difficulty-${problem.difficulty.toLowerCase()}`}>{problem.difficulty}</span>
              )}
            </div>
          </div>

          {/* Problem description */}
          <div className="content-section">
            <h3><BookOpen size={18} /> 题目描述</h3>
            <pre className="problem-description">{problem.description}</pre>
          </div>

          {/* Test cases */}
          {problem.test_cases && problem.test_cases.length > 0 && (
            <div className="content-section">
              <h3
                className="test-cases-toggle"
                onClick={() => setTestCasesOpen(!testCasesOpen)}
                style={{ cursor: 'pointer', userSelect: 'none' }}
              >
                {testCasesOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                🧪 测试点 ({problem.test_cases.length})
              </h3>
              {testCasesOpen && (
                <div className="test-cases">
                  {problem.test_cases.map((tc, i) => (
                    <div key={i} className="test-case-card">
                      <div className="test-case-header">
                        <span>测试点 {i + 1}</span>
                      </div>
                      <div className="test-case-body">
                        <div className="io-item">
                          <div className="io-label">输入</div>
                          <pre className="io-content">{tc.input || '(无输入)'}</pre>
                        </div>
                        <div className="io-item">
                          <div className="io-label">输出</div>
                          <pre className="io-content">{tc.output}</pre>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Submission result */}
          {result && (
            <div className={`result-card ${result.success ? 'result-success' : 'result-error'}`}>
              <h3>{result.success ? '✅ 批改完成' : '❌ 提交失败'}</h3>
              <pre className="result-detail">{result.detail}</pre>
              {result.score !== undefined && (
                <div className="result-score">
                  得分：<span className={scoreClass(result.score)}>{result.score}</span>
                </div>
              )}
            </div>
          )}

          {/* Monaco Editor */}
          <div className="content-section">
            <h3>💻 代码编辑器</h3>
            <div className="ide-editor-wrapper">
              <Editor
                height="400px"
                language="python"
                theme="vs-dark"
                value={code}
                onChange={(value) => setCode(value || '')}
                loading={<div className="ide-loading"><Loader size={24} className="spin" /><span>编辑器加载中...</span></div>}
                options={{
                  fontSize: 14,
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                  lineNumbers: 'on',
                  tabSize: 4,
                  automaticLayout: true,
                }}
              />
            </div>
          </div>

          {/* Run output */}
          {running && (
            <div className="content-section" role="status">
              <p>{runTaskStatus === 'running' ? '代码运行中…' : '代码排队中…'}</p>
            </div>
          )}
          {runOutput && (
            <div className="content-section">
              <h3>📤 运行输出</h3>
              <div className="run-output-area">
                {runOutput.output && (
                  <pre className="run-output-stdout">{runOutput.output}</pre>
                )}
                {runOutput.error && (
                  <pre className="run-output-stderr">{runOutput.error}</pre>
                )}
                {!runOutput.output && !runOutput.error && (
                  <p className="run-output-empty">（无输出）</p>
                )}
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="ide-actions">
            <button
              className="ide-btn ide-btn-run"
              onClick={handleRun}
              disabled={running || !code.trim()}
            >
              {running ? <><Loader size={16} className="spin" /> {runTaskStatus === 'running' ? '运行中...' : '排队中...'}</> : <><Play size={16} /> 运行</>}
            </button>
            <button
              className="ide-btn ide-btn-reset"
              onClick={handleReset}
            >
              <RotateCcw size={16} /> 重做
            </button>
            <button
              className="ide-btn ide-btn-submit"
              onClick={handleSubmitCode}
              disabled={submitting || !code.trim()}
            >
              {submitting ? <><Loader size={16} className="spin" /> {submitTaskStatus === 'running' ? '评测中...' : '排队中...'}</> : <><Send size={16} /> 保存并提交</>}
            </button>
          </div>

          {/* Submission history */}
          {history.length > 0 && (
            <div className="submission-history">
              <div className="history-header">
                <h4>📜 提交历史</h4>
              </div>
              {history.map((h) => (
                <div key={h.id} className="submission-item">
                  <div className="submission-info">
                    {statusIcon(h.status)}
                    <span className="submission-time">
                      {new Date(h.submitted_at).toLocaleString('zh-CN')}
                    </span>
                    <span className={`submission-score ${h.score == null ? '' : scoreClass(h.score)}`}>
                      {h.score == null ? '评测中' : `${h.score} 分`}
                    </span>
                  </div>
                  <span className={`status-badge status-${h.status}`}>
                    {SUBMISSION_STATUS_LABELS[h.status] || '未知状态'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* stdin dialog */}
      {stdinDialogOpen && (
        <div className="ide-overlay" onClick={handleStdinCancel}>
          <div className="ide-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>📥 输入</h3>
            <p>您的代码使用了 input()，请输入程序需要的值：</p>
            <textarea
              className="ide-dialog-input"
              value={stdinValue}
              onChange={(e) => setStdinValue(e.target.value)}
              placeholder="在此输入..."
              rows={4}
              autoFocus
            />
            <div className="ide-dialog-actions">
              <button className="ide-btn ide-btn-reset" onClick={handleStdinCancel}>取消</button>
              <button className="ide-btn ide-btn-run" onClick={handleStdinSubmit}>运行</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
