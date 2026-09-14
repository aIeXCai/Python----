import { useCallback, useEffect, useRef, useState } from 'react'
import Editor from '@monaco-editor/react'
import { CheckCircle, Loader, Play, RotateCcw, Send, Terminal, XCircle } from 'lucide-react'
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
  const [gradeResult, setGradeResult] = useState(null)
  const [bestScore, setBestScore] = useState(null)
  const [error, setError] = useState('')
  const controllersRef = useRef([])
  const initialDraftRef = useRef(draft)

  const monitor = useCallback(async (initialTask, type) => {
    if (!initialTask?.task_id) return
    const controller = new AbortController()
    controllersRef.current.push(controller)
    const setBusy = type === 'run' ? setRunning : setGrading
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
      else {
        setGradeResult(normalized)
        if (normalized.score !== null) {
          setBestScore(previous => previous === null ? normalized.score : Math.max(previous, normalized.score))
          onScore(item.item_id, normalized.score)
        }
      }
    } catch (reason) {
      if (reason.name !== 'AbortError') setError(reason.message)
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
      if (data.best_score !== null && data.best_score !== undefined) { setBestScore(data.best_score); onScore(item.item_id, data.best_score) }
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
      last_error: gradeResult?.success === false ? `${gradeResult.message}\n${gradeResult.error}` : '',
    } : null)
    return () => setChatContext(null)
  }, [attemptId, detail, draft, gradeResult, item.item_id, item.title, sessionId, setChatContext, setChatDisabled])

  useEffect(() => () => controllersRef.current.forEach(controller => controller.abort()), [])

  const code = draft ?? detail?.template_code ?? ''
  const run = async () => {
    if (!code.trim() || running) return
    setError(''); setRunResult(null); setRunning(true)
    try { await monitor(await runAIQuizCode(sessionId, item.item_id, attemptId, code, stdin), 'run') }
    catch (reason) { setError(reason.message); setRunning(false) }
  }
  const submit = async () => {
    if (!code.trim() || grading) return
    setError(''); setGradeResult(null); setGrading(true)
    try { await monitor(await submitAIQuizCode(sessionId, item.item_id, attemptId, code), 'grade') }
    catch (reason) { setError(reason.message); setGrading(false) }
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
        <button type="button" className="aiq-text-button" onClick={() => onDraftChange(item.item_id, detail.template_code || '')}><RotateCcw size={14} />恢复模板</button>
      </div>
      <div className="aiq-editor"><Editor height="390px" language="python" theme="vs-dark" value={code} onChange={value => onDraftChange(item.item_id, value || '')} options={{ fontSize: 14, minimap: { enabled: false }, tabSize: 4, automaticLayout: true, scrollBeyondLastLine: false }} /></div>
      <label className="aiq-stdin">标准输入（没有则留空）<textarea value={stdin} onChange={event => setStdin(event.target.value)} rows={3} placeholder="每个输入值按题目要求换行" /></label>
      <div className="aiq-code-actions">
        <button type="button" className="btn btn-secondary" disabled={running || grading || !code.trim()} onClick={run}>{running ? <><Loader size={16} className="spin" />运行中…</> : <><Play size={16} />运行代码</>}</button>
        <button type="button" className="btn btn-primary" disabled={running || grading || !code.trim()} onClick={submit}>{grading ? <><Loader size={16} className="spin" />评测中…</> : <><Send size={16} />提交评测</>}</button>
        <span className="aiq-best-score">本次最高：{bestScore ?? '尚未提交'}{bestScore !== null ? '分' : ''}</span>
      </div>
    </section>
    {runResult && <section className="aiq-card aiq-output"><div className="aiq-card-title"><Play size={16} />运行结果</div>{runResult.output && <pre>{runResult.output}</pre>}{runResult.error && <pre className="error">{runResult.error}</pre>}{!runResult.output && !runResult.error && <p>（无输出）</p>}</section>}
    {gradeResult && <section className={`aiq-card aiq-grade-result ${gradeResult.success ? 'success' : 'failed'}`}><div className="aiq-card-title">{gradeResult.success ? <CheckCircle /> : <XCircle />}{gradeResult.message}</div>{gradeResult.score !== null && <strong>{gradeResult.score} 分</strong>}{gradeResult.error && <pre>{gradeResult.error}</pre>}</section>}
  </div>
}
