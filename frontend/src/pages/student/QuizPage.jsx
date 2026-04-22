import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import Navbar from '../../components/Navbar.jsx'
import { getInfoQuizDetail, submitInfoQuiz } from '../../api/info.js'
import { Loader, Clock, ChevronLeft, ChevronRight } from 'lucide-react'

export default function QuizPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()

  const [quiz, setQuiz] = useState(null)
  const [questions, setQuestions] = useState([])
  const [answers, setAnswers] = useState({})   // { question_id: selected_option }
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [username, setUsername] = useState('')
  const [grade, setGrade] = useState('')
  const [classNum, setClassNum] = useState('')
  const [timeLeft, setTimeLeft] = useState(null)  // 秒
  const [currentIdx, setCurrentIdx] = useState(0)  // 当前题目索引
  const timerRef = useRef(null)

  useEffect(() => {
    const raw = localStorage.getItem('user')
    if (raw) {
      try {
        const u = JSON.parse(raw)
        setUsername(u.display_name || u.username || '')
        setGrade(u.grade || '')
        setClassNum(u.class_num || '')
      } catch {}
    }
    loadQuiz()
    return () => clearInterval(timerRef.current)
  }, [sessionId])

  const loadQuiz = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getInfoQuizDetail(sessionId)
      if (data.error) {
        setError('加载小测失败：' + data.error)
        setLoading(false)
        return
      }
      setQuiz(data)
      setQuestions(data.questions || [])

      // 初始化答案
      const init = {}
      ;(data.questions || []).forEach(q => { init[q.id] = null })
      setAnswers(init)

      // 启动倒计时
      if (data.time_limit && data.time_limit > 0) {
        setTimeLeft(data.time_limit * 60)
      }
    } catch (err) {
      setError('加载小测失败：' + (err.message || String(err)))
    } finally {
      setLoading(false)
    }
  }

  // 倒计时
  useEffect(() => {
    if (timeLeft === null || timeLeft <= 0) return
    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current)
          handleSubmit(true)  // 时间到自动提交
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(timerRef.current)
  }, [timeLeft !== null])

  const handleSelect = (questionId, option) => {
    setAnswers(prev => ({ ...prev, [questionId]: option }))
  }

  const handleSubmit = async (auto = false) => {
    if (!auto) {
      const unanswered = questions.filter(q => answers[q.id] === null)
      if (unanswered.length > 0 && !window.confirm(`还有 ${unanswered.length} 题未作答，确定提交吗？`)) {
        return
      }
    }

    clearInterval(timerRef.current)
    setSubmitting(true)
    try {
      // 构造提交格式：{ question_id: "A"|"B"|"C"|"D" }
      const submitAnswers = {}
      questions.forEach(q => {
        submitAnswers[q.id] = answers[q.id] || ''
      })
      await submitInfoQuiz(sessionId, submitAnswers)
      navigate(`/student/quiz-result/${sessionId}`)
    } catch (err) {
      setError('提交失败：' + (err.message || String(err)))
      setSubmitting(false)
    }
  }

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${String(s).padStart(2, '0')}`
  }

  const allAnswered = questions.length > 0 && questions.every(q => answers[q.id] !== null)

  if (loading) {
    return (
      <div className="page-bg" style={{ '--bg-gradient': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)' }}>
        <Navbar username={username} grade={grade} class_num={classNum} />
        <div className="loading-state" style={{ marginTop: 80 }}>
          <Loader size={40} className="spin" />
          <p>载入小测中...</p>
        </div>
      </div>
    )
  }

  if (error || !quiz) {
    return (
      <div className="page-bg" style={{ '--bg-gradient': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)' }}>
        <Navbar username={username} grade={grade} class_num={classNum} />
        <div style={{ textAlign: 'center', marginTop: 80, padding: '40px' }}>
          <p style={{ color: '#e53e3e', marginBottom: 16 }}>{error}</p>
          <Link to="/student/dashboard?course=info" className="btn btn-secondary">返回主页</Link>
        </div>
      </div>
    )
  }

  const q = questions[currentIdx]

  return (
    <div className="page-bg" style={{ '--bg-gradient': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)' }}>
      <Navbar username={username} grade={grade} class_num={classNum} />

      <main className="main-content" style={{ maxWidth: 720 }}>
        {/* 顶部：标题 + 计时器 */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
          padding: '16px 20px',
          background: '#fff',
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.1rem' }}>{quiz.title}</h2>
            <p style={{ margin: '4px 0 0', color: '#666', fontSize: '0.85rem' }}>
              {quiz.num_questions} 题 · {quiz.time_limit ? `${quiz.time_limit}分钟` : '不限时'}
            </p>
          </div>
          {timeLeft !== null && (
            <div style={{
              fontSize: '1.4rem',
              fontWeight: 700,
              color: timeLeft < 60 ? '#e53e3e' : '#11998e',
              fontVariantNumeric: 'tabular-nums',
            }}>
              <Clock size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} />
              {formatTime(timeLeft)}
            </div>
          )}
        </div>

        {/* 进度条 */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#666', marginBottom: 6 }}>
            <span>第 {currentIdx + 1} / {questions.length} 题</span>
            <span>{Object.values(answers).filter(v => v !== null).length} 已答</span>
          </div>
          <div style={{ height: 6, background: '#e0e0e0', borderRadius: 3 }}>
            <div style={{
              height: '100%',
              width: `${((currentIdx + 1) / questions.length) * 100}%`,
              background: 'linear-gradient(90deg, #11998e, #38ef7d)',
              borderRadius: 3,
              transition: 'width 0.3s',
            }} />
          </div>
        </div>

        {/* 题目卡片 */}
        {q && (
          <div style={{
            background: '#fff',
            borderRadius: 12,
            padding: '24px',
            boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
            marginBottom: 16,
          }}>
            <div style={{ fontSize: '0.95rem', color: '#333', lineHeight: 1.7, marginBottom: 20 }}>
              <span style={{ fontWeight: 700, color: '#11998e', marginRight: 8 }}>Q{currentIdx + 1}.</span>
              {q.text}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {['A', 'B', 'C', 'D'].map(opt => {
                const optKey = `option_${opt.toLowerCase()}`  // options.A → option_a
                const optionText = q.options ? q.options[opt] : q[optKey]
                if (!optionText) return null
                const selected = answers[q.id] === opt
                return (
                  <button
                    key={opt}
                    onClick={() => handleSelect(q.id, opt)}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 12,
                      padding: '12px 16px',
                      borderRadius: 8,
                      border: selected ? '2px solid #11998e' : '2px solid #e0e0e0',
                      background: selected ? '#e8f8f5' : '#fff',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: '0.9rem',
                      color: '#333',
                      transition: 'all 0.15s',
                    }}
                  >
                    <span style={{
                      width: 26,
                      height: 26,
                      borderRadius: '50%',
                      background: selected ? '#11998e' : '#e0e0e0',
                      color: selected ? '#fff' : '#666',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      fontSize: '0.8rem',
                      flexShrink: 0,
                    }}>
                      {opt}
                    </span>
                    <span>{optionText}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* 导航按钮 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button
            className="btn btn-secondary"
            onClick={() => setCurrentIdx(Math.max(0, currentIdx - 1))}
            disabled={currentIdx === 0}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <ChevronLeft size={18} /> 上一题
          </button>

          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'center', maxWidth: 300 }}>
            {questions.map((_, i) => (
              <button
                key={i}
                onClick={() => setCurrentIdx(i)}
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  border: i === currentIdx ? '2px solid #11998e' : '1px solid #ccc',
                  background: answers[questions[i]?.id] !== null ? '#11998e' : '#fff',
                  color: answers[questions[i]?.id] !== null ? '#fff' : '#666',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {i + 1}
              </button>
            ))}
          </div>

          {currentIdx < questions.length - 1 ? (
            <button
              className="btn btn-primary"
              onClick={() => setCurrentIdx(currentIdx + 1)}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              下一题 <ChevronRight size={18} />
            </button>
          ) : (
            <button
              className="btn btn-primary"
              onClick={() => handleSubmit(false)}
              disabled={submitting}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              {submitting ? <><Loader size={16} className="spin" /> 提交中...</> : '提交小测'}
            </button>
          )}
        </div>

        {/* 返回链接 */}
        <div style={{ textAlign: 'center', marginTop: 20 }}>
          <Link to="/student/dashboard?course=info" style={{ color: '#888', fontSize: '0.85rem' }}>
            ← 返回小测列表
          </Link>
        </div>
      </main>
    </div>
  )
}
