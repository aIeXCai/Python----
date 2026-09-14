import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { BookOpen, CheckCircle, Clock, Code2, Loader, Send } from 'lucide-react'
import Navbar from '../../../components/Navbar.jsx'
import RichQuestionText from '../../../components/RichQuestionText.jsx'
import { getCurrentUser } from '../../../api/index.js'
import { saveAIQuizAnswers, startAIQuizAttempt, submitAIQuizAttempt } from '../../../api/aiStudentQuiz.js'
import { useChat } from '../../../contexts/ChatContext.jsx'
import ProgrammingWorkspace from './ProgrammingWorkspace.jsx'
import './aiQuiz.css'

const SAVE_DELAY_MS = 1200
const formatTime = seconds => `${Math.floor(Math.max(0, seconds || 0) / 60)}:${String(Math.max(0, seconds || 0) % 60).padStart(2, '0')}`

export default function AIQuizPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const chat = useChat()
  const setChatContext = chat.setContext
  const setChatDisabled = chat.setDisabled
  const closeChat = chat.close
  const cachedUser = getCurrentUser()
  const [attempt, setAttempt] = useState(null)
  const [answers, setAnswers] = useState({})
  const [drafts, setDrafts] = useState({})
  const [programmingScores, setProgrammingScores] = useState({})
  const [currentIndex, setCurrentIndex] = useState(0)
  const [timeLeft, setTimeLeft] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [locked, setLocked] = useState(false)
  const [saveStatus, setSaveStatus] = useState('')
  const [error, setError] = useState('')
  const answersRef = useRef({})
  const revisionRef = useRef(0)
  const attemptIdRef = useRef(null)
  const lastSavedRef = useRef('{}')
  const saveTimerRef = useRef(null)
  const saveChainRef = useRef(Promise.resolve())
  const deadlineRef = useRef(null)
  const serverOffsetRef = useRef(0)
  const autoSubmittedRef = useRef(false)

  const items = useMemo(() => attempt?.items || [], [attempt])
  const current = items[currentIndex]
  const choiceItems = useMemo(() => items.filter(item => item.type === 'choice'), [items])
  const programmingItems = useMemo(() => items.filter(item => item.type === 'programming'), [items])

  const persistAnswers = useCallback(({ keepalive = false, silent = false } = {}) => {
    const serialized = JSON.stringify(answersRef.current)
    if (!attemptIdRef.current || serialized === lastSavedRef.current) return saveChainRef.current
    if (!silent) setSaveStatus('保存中…')
    saveChainRef.current = saveChainRef.current.catch(() => undefined).then(async () => {
      const latest = answersRef.current
      const latestSerialized = JSON.stringify(latest)
      if (latestSerialized === lastSavedRef.current) return
      const data = await saveAIQuizAnswers(sessionId, {
        attempt_id: attemptIdRef.current, revision: revisionRef.current, answers: latest,
      }, { keepalive })
      revisionRef.current = data.revision
      lastSavedRef.current = latestSerialized
      if (!silent) setSaveStatus('已保存')
    }).catch(reason => {
      if (!silent) setSaveStatus(navigator.onLine ? '保存失败' : '离线，恢复网络后重试')
      if (!silent && reason.code === 'attempt_revision_conflict') setError('答案已在另一个页面发生变化，请刷新后继续。')
      throw reason
    })
    return saveChainRef.current
  }, [sessionId])

  const finish = useCallback(async ({ automatic = false } = {}) => {
    if (submitting || locked || !attemptIdRef.current) return
    const unanswered = choiceItems.filter(item => !answersRef.current[item.item_id]).length
    const unsubmitted = programmingItems.filter(item => programmingScores[item.item_id] === null || programmingScores[item.item_id] === undefined).length
    if (!automatic && (unanswered || unsubmitted)) {
      const parts = []
      if (unanswered) parts.push(`${unanswered} 道选择题未答`)
      if (unsubmitted) parts.push(`${unsubmitted} 道编程题尚无有效提交`)
      if (!window.confirm(`还有${parts.join('、')}，确定交卷吗？`)) return
    }
    clearTimeout(saveTimerRef.current)
    setSubmitting(true); setLocked(true); setError('')
    try {
      try { await persistAnswers() } catch (reason) {
        if (reason.code === 'attempt_revision_conflict') throw reason
      }
      await submitAIQuizAttempt(sessionId, {
        attempt_id: attemptIdRef.current, revision: revisionRef.current, answers: answersRef.current,
      })
      navigate(`/student/ai-quiz-result/${sessionId}`, { replace: true })
    } catch (reason) {
      if (reason.code === 'attempt_completed' || reason.code === 'quiz_deadline_passed' || reason.data?.result_available) {
        navigate(`/student/ai-quiz-result/${sessionId}`, { replace: true }); return
      }
      setError(`交卷失败：${reason.message}`); setSubmitting(false); setLocked(false); autoSubmittedRef.current = false
    }
  }, [choiceItems, locked, navigate, persistAnswers, programmingItems, programmingScores, sessionId, submitting])

  useEffect(() => {
    let alive = true
    startAIQuizAttempt(sessionId).then(data => {
      if (!alive) return
      const restored = data.saved_answers || {}
      setAttempt(data); setAnswers(restored); answersRef.current = restored
      revisionRef.current = data.revision || 0; attemptIdRef.current = data.attempt_id
      lastSavedRef.current = JSON.stringify(restored)
      serverOffsetRef.current = new Date(data.server_time).getTime() - Date.now()
      deadlineRef.current = data.deadline_at ? new Date(data.deadline_at).getTime() : null
      setTimeLeft(data.remaining_seconds)
      try { setDrafts(JSON.parse(localStorage.getItem(`ai-quiz-drafts:${data.attempt_id}`) || '{}')) } catch { setDrafts({}) }
    }).catch(reason => {
      if (!alive) return
      if (reason.code === 'attempt_completed' || reason.code === 'quiz_deadline_passed' || reason.data?.result_available) {
        navigate(`/student/ai-quiz-result/${sessionId}`, { replace: true }); return
      }
      setError(`加载小测失败：${reason.message}`)
    }).finally(() => alive && setLoading(false))
    const flush = () => { clearTimeout(saveTimerRef.current); void persistAnswers({ keepalive: true, silent: true }).catch(() => undefined) }
    const retry = () => { void persistAnswers().catch(() => undefined) }
    window.addEventListener('pagehide', flush); window.addEventListener('online', retry)
    return () => {
      alive = false; window.removeEventListener('pagehide', flush); window.removeEventListener('online', retry)
      flush(); setChatContext(null); setChatDisabled(false)
    }
  }, [navigate, persistAnswers, sessionId, setChatContext, setChatDisabled])

  useEffect(() => {
    if (!deadlineRef.current) return undefined
    const tick = () => {
      const remaining = Math.max(0, Math.ceil((deadlineRef.current - (Date.now() + serverOffsetRef.current)) / 1000))
      setTimeLeft(remaining)
      if (remaining === 0 && !autoSubmittedRef.current) { autoSubmittedRef.current = true; setLocked(true); void finish({ automatic: true }) }
    }
    tick(); const timer = window.setInterval(tick, 1000)
    return () => window.clearInterval(timer)
  }, [attempt?.attempt_id, finish])

  useEffect(() => {
    if (!current || current.type === 'choice') {
      setChatContext(null); setChatDisabled(true, '选择题作答时不能使用站内 AI 助手'); closeChat()
    } else setChatDisabled(false)
  }, [closeChat, current, setChatContext, setChatDisabled])

  const select = (itemId, option) => {
    if (locked || submitting || timeLeft === 0) return
    const next = { ...answersRef.current, [itemId]: option }
    answersRef.current = next; setAnswers(next); setSaveStatus('待保存')
    clearTimeout(saveTimerRef.current)
    saveTimerRef.current = window.setTimeout(() => void persistAnswers().catch(() => undefined), SAVE_DELAY_MS)
  }
  const updateDraft = useCallback((itemId, value) => setDrafts(previous => {
    const next = { ...previous, [itemId]: value }
    if (attemptIdRef.current) {
      try { localStorage.setItem(`ai-quiz-drafts:${attemptIdRef.current}`, JSON.stringify(next)) } catch { /* local draft cache is best-effort */ }
    }
    return next
  }), [])
  const updateScore = useCallback((itemId, score) => setProgrammingScores(previous => ({
    ...previous, [itemId]: previous[itemId] === undefined ? score : Math.max(previous[itemId], score),
  })), [])

  if (loading) return <div className="page-bg"><Navbar username={cachedUser.display_name || cachedUser.username} grade={cachedUser.grade} class_num={cachedUser.class_num} /><div className="aiq-loading page"><Loader className="spin" />正在生成/恢复你的试卷…</div></div>
  if (!attempt) return <div className="page-bg"><Navbar username={cachedUser.display_name || cachedUser.username} grade={cachedUser.grade} class_num={cachedUser.class_num} /><div className="aiq-fatal"><p role="alert">{error}</p><Link className="btn btn-secondary" to="/student/dashboard?course=ai">返回 AI 课程</Link></div></div>

  const answeredCount = choiceItems.filter(item => answers[item.item_id]).length
  return <div className="page-bg aiq-page"><Navbar username={cachedUser.display_name || cachedUser.username} grade={cachedUser.grade} class_num={cachedUser.class_num} />
    <main className="aiq-shell">
      <header className="aiq-header">
        <div><Link to="/student/dashboard?course=ai" className="aiq-back">← 返回小测列表</Link><h1>{attempt.quiz.title}</h1><p>{attempt.quiz.choice_count} 道选择题 · {attempt.quiz.programming_count} 道编程题 · 总分 {attempt.quiz.total_points}</p></div>
        <div className={`aiq-clock ${timeLeft !== null && timeLeft < 60 ? 'danger' : ''}`}><Clock size={19} />{timeLeft === null ? '不限时' : formatTime(timeLeft)}</div>
        <button type="button" className="btn btn-primary" disabled={submitting || locked} onClick={() => finish()}>{submitting ? <><Loader size={16} className="spin" />结算中…</> : <><Send size={16} />交卷</>}</button>
      </header>
      {error && <div className="aiq-alert aiq-alert-error" role="alert">{error}</div>}
      <div className="aiq-save-line"><span><CheckCircle size={14} />选择题已答 {answeredCount}/{choiceItems.length}</span><span aria-live="polite">{saveStatus || '等待作答'}</span></div>
      <div className="aiq-layout">
        <aside className="aiq-nav" aria-label="试题导航"><h2>试题导航</h2>{items.map((item, index) => {
          const choiceDone = item.type === 'choice' && Boolean(answers[item.item_id])
          const score = programmingScores[item.item_id]
          return <button key={item.item_id} type="button" className={`${index === currentIndex ? 'active' : ''} ${choiceDone || score !== undefined ? 'done' : ''}`} onClick={() => setCurrentIndex(index)} aria-current={index === currentIndex ? 'step' : undefined}>
            <span className="aiq-nav-number">{index + 1}</span><span>{item.type === 'choice' ? <BookOpen size={15} /> : <Code2 size={15} />}{item.type === 'choice' ? '选择题' : '编程题'}<small>{item.type === 'choice' ? (choiceDone ? '已作答' : '未作答') : (score === undefined ? '尚未提交' : `最高 ${score} 分`)}</small></span>
          </button>
        })}</aside>
        <section className="aiq-workarea">
          <div className="aiq-question-heading"><span>第 {currentIndex + 1} 题</span><strong>{current?.type === 'choice' ? '选择题' : '编程题'}</strong>{current?.type === 'programming' && <em>{current.title}</em>}</div>
          {current?.type === 'choice' && <div className="aiq-card aiq-choice-card">
            <RichQuestionText value={current.text} className="aiq-stem" />
            <div className="aiq-options">{['A', 'B', 'C', 'D'].map(option => <button key={option} type="button" disabled={locked || submitting} className={answers[current.item_id] === option ? 'selected' : ''} onClick={() => select(current.item_id, option)}><span className="aiq-option-letter">{option}</span><RichQuestionText value={current.options?.[option] || ''} /></button>)}</div>
          </div>}
          {current?.type === 'programming' && <ProgrammingWorkspace key={current.item_id} sessionId={sessionId} attemptId={attempt.attempt_id} item={current} draft={drafts[current.item_id]} onDraftChange={updateDraft} onScore={updateScore} />}
          <div className="aiq-prev-next"><button type="button" className="btn btn-secondary" disabled={currentIndex === 0} onClick={() => setCurrentIndex(index => index - 1)}>上一题</button><button type="button" className="btn btn-primary" disabled={currentIndex === items.length - 1} onClick={() => setCurrentIndex(index => index + 1)}>下一题</button></div>
        </section>
      </div>
    </main>
  </div>
}
