import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import Navbar from '../../../components/Navbar.jsx'
import {
  saveInfoQuizAnswers,
  startInfoQuizAttempt,
  submitInfoQuizAttempt,
} from '../../../api/info.js'
import { useChat } from '../../../contexts/ChatContext.jsx'
import { Loader, Clock, ChevronLeft, ChevronRight } from 'lucide-react'

const SAVE_DELAY_MS = 400

export default function QuizPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const chat = useChat()
  const setChatContext = chat.setContext
  const setChatDisabled = chat.setDisabled
  const closeChat = chat.close
  const [quiz, setQuiz] = useState(null)
  const [questions, setQuestions] = useState([])
  const [answers, setAnswers] = useState({})
  const [attemptId, setAttemptId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [saveStatus, setSaveStatus] = useState('')
  const [error, setError] = useState('')
  const [username, setUsername] = useState('')
  const [grade, setGrade] = useState('')
  const [classNum, setClassNum] = useState('')
  const [timeLeft, setTimeLeft] = useState(null)
  const [currentIdx, setCurrentIdx] = useState(0)

  const answersRef = useRef({})
  const revisionRef = useRef(0)
  const attemptIdRef = useRef(null)
  const deadlineRef = useRef(null)
  const serverOffsetRef = useRef(0)
  const saveTimerRef = useRef(null)
  const saveChainRef = useRef(Promise.resolve())
  const lastSavedRef = useRef('{}')
  const autoSubmittedRef = useRef(false)

  const persistAnswers = useCallback((answerSnapshot, { keepalive = false, silent = false } = {}) => {
    const serialized = JSON.stringify(answerSnapshot)
    if (!attemptIdRef.current || serialized === lastSavedRef.current) {
      return saveChainRef.current
    }
    if (!silent) setSaveStatus('保存中…')
    saveChainRef.current = saveChainRef.current
      .catch(() => undefined)
      .then(async () => {
        const latest = answersRef.current
        const latestSerialized = JSON.stringify(latest)
        if (latestSerialized === lastSavedRef.current) return
        const data = await saveInfoQuizAnswers(
          sessionId,
          {
            attempt_id: attemptIdRef.current,
            revision: revisionRef.current,
            answers: latest,
          },
          { keepalive },
        )
        revisionRef.current = data.revision
        lastSavedRef.current = latestSerialized
        if (!silent) setSaveStatus('已保存')
      })
      .catch((err) => {
        if (!silent) setSaveStatus('保存失败')
        if (!silent && err.code === 'attempt_revision_conflict') {
          setError('答案已在另一个页面发生变化，请刷新后继续。')
        }
      })
    return saveChainRef.current
  }, [sessionId])

  const handleSubmit = useCallback(async (auto = false) => {
    if (submitting || !attemptIdRef.current) return
    if (!auto) {
      const unanswered = questions.filter(q => !answersRef.current[q.id])
      if (unanswered.length > 0 && !window.confirm(`还有 ${unanswered.length} 题未作答，确定提交吗？`)) return
    }

    clearTimeout(saveTimerRef.current)
    setSubmitting(true)
    setError('')
    await persistAnswers(answersRef.current)
    try {
      await submitInfoQuizAttempt(sessionId, {
        attempt_id: attemptIdRef.current,
        revision: revisionRef.current,
        answers: answersRef.current,
      })
      navigate(`/student/quiz-result/${sessionId}`)
    } catch (err) {
      if (err.data?.result_available || err.code === 'attempt_completed') {
        navigate(`/student/quiz-result/${sessionId}`)
        return
      }
      setError('提交失败：' + (err.message || String(err)))
      setSubmitting(false)
      autoSubmittedRef.current = false
    }
  }, [navigate, persistAnswers, questions, sessionId, submitting])

  useEffect(() => {
    const raw = localStorage.getItem('user')
    if (raw) {
      try {
        const user = JSON.parse(raw)
        setUsername(user.display_name || user.username || '')
        setGrade(user.grade || '')
        setClassNum(user.class_num || '')
      } catch { /* ignore invalid local display cache */ }
    }

    let cancelled = false
    setLoading(true)
    setError('')
    startInfoQuizAttempt(sessionId)
      .then((data) => {
        if (cancelled) return
        const normalizedQuestions = (data.questions || []).map(item => ({ ...item, id: item.item_id }))
        const initialAnswers = {}
        normalizedQuestions.forEach(item => {
          if (data.saved_answers?.[item.id]) initialAnswers[item.id] = data.saved_answers[item.id]
        })
        setQuiz(data.quiz)
        setQuestions(normalizedQuestions)
        setAnswers(initialAnswers)
        answersRef.current = initialAnswers
        revisionRef.current = data.revision || 0
        attemptIdRef.current = data.attempt_id
        setAttemptId(data.attempt_id)
        lastSavedRef.current = JSON.stringify(
          Object.fromEntries(Object.entries(initialAnswers).filter(([, value]) => value)),
        )
        serverOffsetRef.current = new Date(data.server_time).getTime() - Date.now()
        deadlineRef.current = data.deadline_at ? new Date(data.deadline_at).getTime() : null
        setTimeLeft(data.remaining_seconds)
      })
      .catch((err) => {
        if (cancelled) return
        if (err.code === 'attempt_completed' || err.data?.result_available) {
          navigate(`/student/quiz-result/${sessionId}`, { replace: true })
          return
        }
        setError('加载小测失败：' + (err.message || String(err)))
      })
      .finally(() => { if (!cancelled) setLoading(false) })

    setChatContext(null)
    setChatDisabled?.(true, '正式小测作答期间不能使用站内 AI 助手')
    closeChat?.()
    const flushLatestAnswer = () => {
      clearTimeout(saveTimerRef.current)
      void persistAnswers(answersRef.current, { keepalive: true, silent: true })
    }
    const retryPendingAnswer = () => {
      void persistAnswers(answersRef.current)
    }
    window.addEventListener('pagehide', flushLatestAnswer)
    window.addEventListener('online', retryPendingAnswer)
    return () => {
      cancelled = true
      window.removeEventListener('pagehide', flushLatestAnswer)
      window.removeEventListener('online', retryPendingAnswer)
      flushLatestAnswer()
      setChatContext(null)
      setChatDisabled?.(false)
    }
  }, [closeChat, navigate, persistAnswers, sessionId, setChatContext, setChatDisabled])

  useEffect(() => {
    if (!deadlineRef.current) return undefined
    const updateClock = () => {
      const serverNow = Date.now() + serverOffsetRef.current
      const remaining = Math.max(0, Math.ceil((deadlineRef.current - serverNow) / 1000))
      setTimeLeft(remaining)
      if (remaining === 0 && !autoSubmittedRef.current) {
        autoSubmittedRef.current = true
        handleSubmit(true)
      }
    }
    updateClock()
    const timer = window.setInterval(updateClock, 1000)
    return () => window.clearInterval(timer)
  }, [attemptId, handleSubmit])

  const handleSelect = (questionId, option) => {
    if (submitting || timeLeft === 0) return
    const next = { ...answersRef.current, [questionId]: option }
    answersRef.current = next
    setAnswers(next)
    setSaveStatus('待保存')
    clearTimeout(saveTimerRef.current)
    saveTimerRef.current = window.setTimeout(() => persistAnswers(next), SAVE_DELAY_MS)
  }

  const formatTime = (seconds) => {
    const value = Math.max(0, seconds || 0)
    return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`
  }

  if (loading) {
    return <div className="page-bg"><Navbar username={username} grade={grade} class_num={classNum} /><div className="loading-state" style={{ marginTop: 80 }}><Loader size={40} className="spin" /><p>加载小测中...</p></div></div>
  }

  if (error && !quiz) {
    return <div className="page-bg"><Navbar username={username} grade={grade} class_num={classNum} /><div style={{ textAlign: 'center', marginTop: 80, padding: 40 }}><p style={{ color: '#e53e3e' }}>{error}</p><Link to="/student/dashboard?course=info" className="btn btn-secondary">返回主页</Link></div></div>
  }

  const q = questions[currentIdx]
  return (
    <div className="page-bg" style={{ '--bg-gradient': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)' }}>
      <Navbar username={username} grade={grade} class_num={classNum} />
      <main className="main-content" style={{ maxWidth: 720 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, padding: '16px 20px', background: '#fff', borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.1rem' }}>{quiz?.title}</h2>
            <p style={{ margin: '4px 0 0', color: '#666', fontSize: '0.85rem' }}>{quiz?.num_questions} 题 · {quiz?.time_limit ? `${quiz.time_limit}分钟` : '不限时'}</p>
            {saveStatus && <p aria-live="polite" style={{ margin: '4px 0 0', color: saveStatus === '保存失败' ? '#e53e3e' : '#777', fontSize: '0.78rem' }}>{saveStatus}</p>}
          </div>
          {timeLeft !== null && <div style={{ fontSize: '1.4rem', fontWeight: 700, color: timeLeft < 60 ? '#e53e3e' : '#11998e', fontVariantNumeric: 'tabular-nums' }}><Clock size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} />{formatTime(timeLeft)}</div>}
        </div>

        {error && <div role="alert" style={{ color: '#c53030', background: '#fff5f5', padding: 12, borderRadius: 8, marginBottom: 16 }}>{error}</div>}

        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#666', marginBottom: 6 }}><span>第 {currentIdx + 1} / {questions.length} 题</span><span>{Object.values(answers).filter(Boolean).length} 已答</span></div>
          <div style={{ height: 6, background: '#e0e0e0', borderRadius: 3 }}><div style={{ height: '100%', width: `${questions.length ? ((currentIdx + 1) / questions.length) * 100 : 0}%`, background: 'linear-gradient(90deg, #11998e, #38ef7d)', borderRadius: 3 }} /></div>
        </div>

        {q && <div style={{ background: '#fff', borderRadius: 12, padding: 24, boxShadow: '0 2px 12px rgba(0,0,0,0.08)', marginBottom: 16 }}>
          <div style={{ fontSize: '0.95rem', color: '#333', lineHeight: 1.7, marginBottom: 20 }}><span style={{ fontWeight: 700, color: '#11998e', marginRight: 8 }}>Q{currentIdx + 1}.</span>{q.text}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {['A', 'B', 'C', 'D'].map(opt => {
              const selected = answers[q.id] === opt
              return <button key={opt} type="button" disabled={submitting || timeLeft === 0} onClick={() => handleSelect(q.id, opt)} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 16px', borderRadius: 8, border: selected ? '2px solid #11998e' : '2px solid #e0e0e0', background: selected ? '#e8f8f5' : '#fff', cursor: 'pointer', textAlign: 'left', fontSize: '0.9rem', color: '#333' }}><span style={{ width: 26, height: 26, borderRadius: '50%', background: selected ? '#11998e' : '#e0e0e0', color: selected ? '#fff' : '#666', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, flexShrink: 0 }}>{opt}</span><span>{q.options?.[opt]}</span></button>
            })}
          </div>
        </div>}

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button className="btn btn-secondary" onClick={() => setCurrentIdx(Math.max(0, currentIdx - 1))} disabled={currentIdx === 0}><ChevronLeft size={18} /> 上一题</button>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'center', maxWidth: 300 }}>{questions.map((item, index) => <button key={item.id} type="button" onClick={() => setCurrentIdx(index)} style={{ width: 28, height: 28, borderRadius: '50%', border: index === currentIdx ? '2px solid #11998e' : '1px solid #ccc', background: answers[item.id] ? '#11998e' : '#fff', color: answers[item.id] ? '#fff' : '#666' }}>{index + 1}</button>)}</div>
          {currentIdx < questions.length - 1
            ? <button className="btn btn-primary" onClick={() => setCurrentIdx(currentIdx + 1)}>下一题 <ChevronRight size={18} /></button>
            : <button className="btn btn-primary" onClick={() => handleSubmit(false)} disabled={submitting || timeLeft === 0}>{submitting ? <><Loader size={16} className="spin" /> 提交中...</> : '提交小测'}</button>}
        </div>
        <div style={{ textAlign: 'center', marginTop: 20 }}><Link to="/student/dashboard?course=info" style={{ color: '#888', fontSize: '0.85rem' }}>← 返回小测列表</Link></div>
      </main>
    </div>
  )
}
