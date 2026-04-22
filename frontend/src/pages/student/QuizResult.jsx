import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import Navbar from '../../components/Navbar.jsx'
import { getInfoQuizResult } from '../../api/info.js'
import { Loader, CheckCircle, XCircle, ArrowLeft, Award } from 'lucide-react'

export default function QuizResult() {
  const { sessionId } = useParams()

  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [username, setUsername] = useState('')
  const [grade, setGrade] = useState('')
  const [classNum, setClassNum] = useState('')

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
    loadResult()
  }, [sessionId])

  const loadResult = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getInfoQuizResult(sessionId)
      setResult(data)
    } catch (err) {
      setError('加载成绩失败：' + (err.message || String(err)))
    } finally {
      setLoading(false)
    }
  }

  const getScoreClass = (score) => {
    if (score >= 90) return '#38ef7d'
    if (score >= 70) return '#f6c90e'
    return '#e53e3e'
  }

  if (loading) {
    return (
      <div className="page-bg" style={{ '--bg-gradient': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)' }}>
        <Navbar username={username} grade={grade} class_num={classNum} />
        <div className="loading-state" style={{ marginTop: 80 }}>
          <Loader size={40} className="spin" />
          <p>载入成绩中...</p>
        </div>
      </div>
    )
  }

  if (error || !result || result.error) {
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

  const { quiz_title, score, total_count, correct_count, submitted_at, question_results = [] } = result

  return (
    <div className="page-bg" style={{ '--bg-gradient': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)' }}>
      <Navbar username={username} grade={grade} class_num={classNum} />

      <main className="main-content" style={{ maxWidth: 680 }}>
        {/* 成绩总览 */}
        <div style={{
          background: '#fff',
          borderRadius: 16,
          padding: '32px',
          textAlign: 'center',
          boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
          marginBottom: 24,
        }}>
          <h2 style={{ margin: '0 0 8px', fontSize: '1.2rem', color: '#333' }}>{quiz_title}</h2>
          <p style={{ margin: '0 0 24px', color: '#888', fontSize: '0.85rem' }}>
            提交时间：{submitted_at ? new Date(submitted_at).toLocaleString('zh-CN') : '-'}
          </p>

          <div style={{ display: 'flex', justifyContent: 'center', gap: 32, marginBottom: 24 }}>
            {/* 分数圆环 */}
            <div style={{ position: 'relative', width: 120, height: 120 }}>
              <svg width="120" height="120" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="52" fill="none" stroke="#e0e0e0" strokeWidth="10" />
                <circle
                  cx="60" cy="60" r="52" fill="none"
                  stroke={getScoreClass(score)}
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={`${(score / 100) * 327} 327`}
                  transform="rotate(-90 60 60)"
                  style={{ transition: 'stroke-dasharray 1s ease' }}
                />
              </svg>
              <div style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <span style={{ fontSize: '2rem', fontWeight: 800, color: getScoreClass(score) }}>{score}</span>
                <span style={{ fontSize: '0.75rem', color: '#888' }}>分</span>
              </div>
            </div>

            {/* 统计数字 */}
            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 10, textAlign: 'left' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <CheckCircle size={20} color="#38ef7d" />
                <span style={{ fontSize: '1rem' }}>正确 {correct_count} 题</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <XCircle size={20} color="#e53e3e" />
                <span style={{ fontSize: '1rem' }}>错误 {total_count - correct_count} 题</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Award size={20} color="#f6c90e" />
                <span style={{ fontSize: '1rem' }}>总分 {total_count * 20} 分</span>
              </div>
            </div>
          </div>

          <div style={{
            fontSize: '1.1rem',
            fontWeight: 700,
            color: getScoreClass(score),
          }}>
            {score >= 90 ? '🌟 优秀！' : score >= 70 ? '👍 良好，继续加油！' : '💪 继续努力！'}
          </div>
        </div>

        {/* 题目详情 */}
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ marginBottom: 16, fontSize: '1rem', color: '#333' }}>答题详情</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {question_results.map((qr, i) => (
              <div key={qr.question_id} style={{
                background: '#fff',
                borderRadius: 10,
                padding: '16px',
                borderLeft: `4px solid ${qr.is_correct ? '#38ef7d' : '#e53e3e'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                    {qr.is_correct
                      ? <CheckCircle size={18} color="#38ef7d" style={{ flexShrink: 0, marginTop: 2 }} />
                      : <XCircle size={18} color="#e53e3e" style={{ flexShrink: 0, marginTop: 2 }} />}
                    <div>
                      <span style={{ fontWeight: 700, color: '#11998e', marginRight: 8 }}>Q{i + 1}</span>
                      <span style={{ fontSize: '0.9rem', color: '#333', lineHeight: 1.5 }}>
                        {qr.text}
                      </span>
                    </div>
                  </div>
                  <span style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: qr.is_correct ? '#38ef7d' : '#e53e3e',
                    flexShrink: 0,
                  }}>
                    {qr.is_correct ? '正确' : '错误'}
                  </span>
                </div>

                {/* 选项 — 新格式：qr.options = { A: {text, is_user_answer, is_correct_answer}, ... } */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingLeft: 26 }}>
                  {['A', 'B', 'C', 'D'].map(opt => {
                    const optData = qr.options ? qr.options[opt] : null
                    if (!optData || !optData.text) return null
                    const isUserAnswer = !!optData.is_user_answer
                    const isCorrectAnswer = !!optData.is_correct_answer
                    let bg = 'transparent'
                    let color = '#666'
                    if (isCorrectAnswer) { bg = '#e8f8f5'; color = '#11998e' }
                    else if (isUserAnswer) { bg = '#fff5f5'; color = '#e53e3e' }
                    return (
                      <div key={opt} style={{
                        padding: '6px 10px',
                        borderRadius: 6,
                        background: bg,
                        fontSize: '0.85rem',
                        color,
                        fontWeight: isUserAnswer || isCorrectAnswer ? 700 : 400,
                      }}>
                        <span style={{ fontWeight: 800, marginRight: 6 }}>{opt}.</span>
                        {optData.text}
                        {isCorrectAnswer && ' ✓'}
                        {isUserAnswer && !isCorrectAnswer && ' (你的选择)'}
                      </div>
                    )
                  })}
                </div>

                {/* 解析 */}
                {qr.explanation && (
                  <div style={{
                    marginTop: 10,
                    padding: '10px 12px',
                    background: '#f8f8f8',
                    borderRadius: 6,
                    fontSize: '0.82rem',
                    color: '#555',
                    lineHeight: 1.6,
                    marginLeft: 26,
                  }}>
                    💡 {qr.explanation}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 返回按钮 */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <Link
            to="/student/dashboard?course=info"
            className="btn btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '12px 32px', fontSize: '1rem' }}
          >
            <ArrowLeft size={18} /> 返回小测列表
          </Link>
        </div>
      </main>
    </div>
  )
}
