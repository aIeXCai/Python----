import { useCallback, useEffect, useRef, useState } from 'react'
import Editor from '@monaco-editor/react'
import { Loader, Play, RotateCcw, Terminal } from 'lucide-react'
import { pollExecutionTask } from '../../../api/index.js'
import {
  getAIQuizActiveExecution,
  getAIQuizProgrammingItem,
  runAIQuizCode,
  submitAIQuizCode,
} from '../../../api/aiStudentQuiz.js'
import { useChat } from '../../../contexts/ChatContext.jsx'
import RichQuestionText from '../../../components/RichQuestionText.jsx'

const finalMessage = task => ({
  succeeded: '全部测试点通过', wrong_answer: '部分测试点未通过',
  runtime_error: '代码运行时出错', timed_out: '代码执行超时',
  resource_limited: '资源使用超出限制', system_error: '评测服务暂时异常',
  cancelled: '排队超时，请重新提交',
}[task.status] || '任务已完成')

export default function ProgrammingWorkspace({ sessionId, attemptId, item, draft, onDraftChange, onScore }) {
  const chat = useChat()
  const setChatContext = chat.setContext
  const setChatDisabled = chat.setDisabled
  const [detail, setDetail] = useState(null)
  const [stdin, setStdin] = useState('')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [grading, setGrading] = useState(false)
  const [runResult, setRunResult] = useState(null)
  const [error, setError] = useState('')
  const controllersRef = useRef([])
  const initialDraftRef = useRef(draft)

  const monitor = useCallback(async (initialTask, type) => {
    const setBusy = type === 'run' ? setRunning : setGrading
    if (!initialTask?.task_id) { setBusy(false); return }
    const controller = new AbortController()
    controllersRef.current.push(controller)
    setBusy(true)
    try {
      const task = await pollExecutionTask(initialTask.task_id, {
        signal: controller.signal,
        initialDelay: initialTask.poll_after_ms || 500,
      })
      const normalized = {
        success: task.status === 'succeeded', status: task.status,
        message: finalMessage(task), output: task.output || '', error: task.error || '',
        score: typeof task.score === 'number' ? task.score : null,
      }
      if (type === 'run') setRunResult(normalized)
      else if (normalized.score !== null) onScore(item.item_id, normalized.score)
    } catch (reason) {
      if (reason.name !== 'AbortError') setError(type === 'grade' ? `成绩记录失败，请再次运行：${reason.message}` : reason.message)
    } finally { setBusy(false) }
  }, [item.item_id, onScore])

  useEffect(() => {
    let alive = true
    const controller = new AbortController()
    controllersRef.current.push(controller)
    Promise.all([
      getAIQuizProgrammingItem(sessionId, item.item_id),
      getAIQuizActiveExecution(sessionId, item.item_id, attemptId, 'run', { signal: controller.signal }),
      getAIQuizActiveExecution(sessionId, item.item_id, attemptId, 'grade', { signal: controller.signal }),
    ]).then(([data, activeRun, activeGrade]) => {
      if (!alive) return
      setDetail(data)
      if (initialDraftRef.current === undefined) onDraftChange(item.item_id, data.template_code || '')
      if (data.best_score !== null && data.best_score !== undefined) onScore(item.item_id, data.best_score)
      if (activeRun) monitor(activeRun, 'run')
      if (activeGrade) monitor(activeGrade, 'grade')
    }).catch(reason => {
      if (alive && reason.name !== 'AbortError') setError(reason.message)
    }).finally(() => alive && setLoading(false))
    return () => { alive = false; controller.abort() }
  }, [attemptId, item.item_id, monitor, onDraftChange, onScore, sessionId])

  useEffect(() => {
    setChatDisabled(false)
    setChatContext(detail ? {
      type: 'ai_quiz_programming', id: item.item_id, session_id: String(sessionId),
      attempt_id: attemptId, title: detail.title || item.title,
      description: detail.description || '', code: draft || '',
      last_error: runResult?.success === false ? `${runResult.message}\n${runResult.error}` : '',
    } : null)
    return () => setChatContext(null)
  }, [attemptId, detail, draft, item.item_id, item.title, runResult, sessionId, setChatContext, setChatDisabled])

  useEffect(() => () => controllersRef.current.forEach(controller => controller.abort()), [])

  const code = draft ?? detail?.template_code ?? ''
  const run = async () => {
    if (!code.trim() || running || grading) return
    setError(''); setRunResult(null); setRunning(true); setGrading(true)
    const start = async (type, request) => {
      try { await monitor(await request(), type) }
      catch (reason) {
        setError(type === 'grade' ? `成绩记录失败，请再次运行：${reason.message}` : reason.message)
        if (type === 'run') setRunning(false)
        else setGrading(false)
      }
    }
    await Promise.all([
      start('run', () => runAIQuizCode(sessionId, item.item_id, attemptId, code, stdin)),
      start('grade', () => submitAIQuizCode(sessionId, item.item_id, attemptId, code)),
    ])
  }

  if (loading && !detail) return <div className="aiq-loading"><Loader className="spin" />正在加载编程题…</div>
  if (!detail) return <div className="aiq-alert aiq-alert-error" role="alert">{error || '编程题加载失败'}</div>

  return <div className="aiq-programming">
    <section className="aiq-card aiq-problem-description">
      <div className="aiq-card-title"><Terminal size={18} />题目描述 <span>{detail.points} 分</span></div>
      <RichQuestionText value={detail.description} />
    </section>
    {error && <div className="aiq-alert aiq-alert-error" role="alert">{error}</div>}
    <section className="aiq-card">
      <div className="aiq-card-title">代码编辑器
        <button type="button" className="aiq-text-button" onClick={() => onDraftChange(item.item_id, detail.template_code || '')}><RotateCcw size={14} />重做</button>
      </div>
      <div className="aiq-editor"><Editor height="390px" language="python" theme="vs-dark" value={code} onChange={value => onDraftChange(item.item_id, value || '')} options={{ fontSize: 14, minimap: { enabled: false }, tabSize: 4, automaticLayout: true, scrollBeyondLastLine: false }} /></div>
      <label className="aiq-stdin">标准输入（没有则留空）<textarea value={stdin} onChange={event => setStdin(event.target.value)} rows={3} placeholder="每个输入值按题目要求换行" /></label>
      <div className="aiq-code-actions">
        <button type="button" className="btn btn-primary" disabled={running || grading || !code.trim()} onClick={run}>{running || grading ? <><Loader size={16} className="spin" />运行中…</> : <><Play size={16} />运行代码</>}</button>
      </div>
    </section>
    {runResult && <section className="aiq-card aiq-output"><div className="aiq-card-title"><Play size={16} />运行结果</div>{runResult.output && <pre>{runResult.output}</pre>}{runResult.error && <pre className="error">{runResult.error}</pre>}{!runResult.output && !runResult.error && <p>（无输出）</p>}</section>}
  </div>
}
