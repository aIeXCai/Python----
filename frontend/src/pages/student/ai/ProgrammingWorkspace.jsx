import { useEffect, useState } from 'react'
import Editor from '@monaco-editor/react'
import { Loader, Play, RotateCcw, Terminal } from 'lucide-react'
import { getAIQuizProgrammingItem } from '../../../api/aiStudentQuiz.js'
import { useChat } from '../../../contexts/ChatContext.jsx'
import RichQuestionText from '../../../components/RichQuestionText.jsx'
import { gradeLocalPython, prepareLocalPython, runLocalPython } from './localPython.js'

export default function ProgrammingWorkspace({ sessionId, item, draft, onDraftChange }) {
  const chat = useChat()
  const setChatContext = chat.setContext
  const setChatDisabled = chat.setDisabled
  const [detail, setDetail] = useState(null)
  const [stdin, setStdin] = useState('')
  const [running, setRunning] = useState(false)
  const [runResult, setRunResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    getAIQuizProgrammingItem(sessionId, item.item_id).then(data => {
      if (alive) {
        setDetail(data)
        if (draft === undefined) onDraftChange(item.item_id, data.template_code || '')
      }
    }).catch(reason => { if (alive) setError(reason.message) })
    void prepareLocalPython().catch(reason => { if (alive) setError(reason.message) })
    return () => { alive = false }
  // The initial draft is restored by the parent; subsequent edits should not refetch the item.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, item.item_id])

  const code = draft ?? detail?.template_code ?? ''
  useEffect(() => {
    setChatDisabled(false)
    setChatContext(detail ? {
      type: 'ai_quiz_programming', id: item.item_id, session_id: String(sessionId),
      title: detail.title || item.title, description: detail.description || '', code,
      last_error: runResult?.status !== 'succeeded' ? runResult?.error || '' : '',
    } : null)
    return () => setChatContext(null)
  }, [detail, item.item_id, item.title, sessionId, code, runResult, setChatContext, setChatDisabled])

  const run = async () => {
    if (!code.trim() || running) return
    setRunning(true); setError(''); setRunResult(null)
    try {
      const execution = await runLocalPython(code, stdin)
      const grade = await gradeLocalPython(code, detail.test_cases || item.test_cases || [])
      setRunResult({ ...execution, score: grade.score, passed: grade.passed, total: grade.total })
    } catch (reason) {
      setError(reason.message)
    } finally { setRunning(false) }
  }

  if (!detail && !error) return <div className="aiq-loading"><Loader className="spin" />正在加载编程题…</div>
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
        <button type="button" className="btn btn-primary" disabled={running || !code.trim()} onClick={run}>{running ? <><Loader size={16} className="spin" />本机运行中…</> : <><Play size={16} />运行代码</>}</button>
      </div>
    </section>
    {runResult && <section className="aiq-card aiq-output"><div className="aiq-card-title"><Play size={16} />本机运行结果 · 测试点 {runResult.passed}/{runResult.total} · 参考分 {runResult.score}</div>{runResult.output && <pre>{runResult.output}</pre>}{runResult.error && <pre className="error">{runResult.error}</pre>}{!runResult.output && !runResult.error && <p>（无输出）</p>}</section>}
  </div>
}
