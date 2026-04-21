import { useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'

export default function Result() {
  const navigate = useNavigate()

  // Result is passed via sessionStorage (set after submission)
  const result = JSON.parse(sessionStorage.getItem('lastSubmission') || '{}')

  useEffect(() => {
    if (!result.problem_id) navigate('/dashboard')
  }, [])

  if (!result.problem_id) return null

  const scoreClass = (s) => {
    if (s >= 100) return 'text-green'
    if (s >= 70) return 'text-blue'
    if (s >= 40) return 'text-yellow'
    return 'text-red'
  }

  return (
    <div className="page-bg">
      <main className="result-page">
        <div className="result-card">
          <h1 className="result-title">
            {result.success ? '🎉 批改完成' : '📝 批改結果'}
          </h1>

          <div className="result-score-large">
            <span className={scoreClass(result.score)}>{result.score}</span>
            <span className="score-unit">分</span>
          </div>

          <div className="result-status-badge" data-status={result.status}>
            {result.status === 'accepted' ? '✅ 全部通過' : `⚠️ ${result.status}`}
          </div>

          <pre className="result-detail">{result.detail}</pre>

          <div className="result-actions">
            <Link to={`/problem/${result.problem_id}`} className="btn btn-primary">
              再次嘗試
            </Link>
            <Link to="/dashboard" className="btn btn-secondary">
              返回主頁
            </Link>
          </div>
        </div>
      </main>
    </div>
  )
}
