import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { BookOpen, Send, ArrowLeft, Loader, CheckCircle, XCircle, Clock } from 'lucide-react'
import Navbar from '../components/Navbar.jsx'
import { getProblemDetail, submitCode, getSubmissionHistory } from '../api/index.js'

export default function ProblemDetail() {
  const { problemId } = useParams()
  const navigate = useNavigate()

  const [problem, setProblem] = useState(null)
  const [code, setCode] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedTest, setSelectedTest] = useState(null)
  const [username, setUsername] = useState('')
  const [grade, setGrade] = useState('')
  const [classNum, setClassNum] = useState('')

  useEffect(() => {
    const raw = localStorage.getItem('user')
    if (!raw) { navigate('/login'); return }
    try {
      const u = JSON.parse(raw)
      setUsername(u.username || '')
      setGrade(u.grade || '')
      setClassNum(u.class_num || '')
    } catch {}
    loadData()
  }, [problemId])

  const loadData = async () => {
    setLoading(true)
    try {
      const [pd, hist] = await Promise.all([
        getProblemDetail(problemId),
        getSubmissionHistory(),
      ])
      setProblem(pd)
      setHistory(hist.filter((h) => h.problem_id === problemId))
      // Pre-fill with last submission if exists
      const last = hist.find((h) => h.problem_id === problemId)
      if (last && last.code) setCode(last.code)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!code.trim()) return
    setSubmitting(true)
    setResult(null)
    try {
      const res = await submitCode({ problem_id: problemId, code })
      setResult(res)
      sessionStorage.setItem('lastSubmission', JSON.stringify({ ...res, problem_id: problemId }))
      // Refresh history
      const hist = await getSubmissionHistory()
      setHistory(hist.filter((h) => h.problem_id === problemId))
      if (res.success && res.score >= 100) {
        // Good score - navigate to result
      }
    } catch (err) {
      setResult({ success: false, detail: err.message })
    } finally {
      setSubmitting(false)
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
        <div className="loading-state"><Loader size={32} className="spin" /><p>載入題目中...</p></div>
      </div>
    )
  }

  if (!problem) {
    return (
      <div className="page-bg">
        <Navbar username={username} grade={grade} class_num={classNum} />
        <div className="loading-state"><p>題目不存在</p><Link to="/dashboard" className="btn btn-primary">返回主頁</Link></div>
      </div>
    )
  }

  return (
    <div className="page-bg">
      <Navbar username={username} grade={grade} class_num={classNum} />

      <main className="main-content problem-layout">
        {/* 左侧题目列表 */}
        <aside className="problems-sidebar">
          <div className="sidebar-header">
            <h2><BookOpen size={20} /> 題目列表</h2>
          </div>
          <div className="problems-list">
            <div className="problem-item active">
              <div className="problem-info">
                <h4>{problem.title || problemId}</h4>
                <p>{problem.test_cases?.length || 0} 個測試點</p>
              </div>
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <Link to="/dashboard" className="btn btn-secondary" style={{ width: '100%', justifyContent: 'center' }}>
              <ArrowLeft size={16} /> 返回主頁
            </Link>
          </div>
        </aside>

        {/* 右侧答题区 */}
        <div className="answer-area">
          {/* 题目信息 */}
          <div className="problem-header">
            <h1 className="problem-title">
              <BookOpen size={28} />
              {problem.title || problemId}
            </h1>
            <div className="problem-meta">
              <span className="meta-item"><BookOpen size={14} /> {problem.test_cases?.length || 0} 個測試點</span>
              {problem.difficulty && (
                <span className={`difficulty difficulty-${problem.difficulty.toLowerCase()}`}>{problem.difficulty}</span>
              )}
            </div>
          </div>

          {/* 题目描述 */}
          <div className="content-section">
            <h3><BookOpen size={18} /> 題目描述</h3>
            <pre className="problem-description">{problem.description}</pre>
          </div>

          {/* 测试点 */}
          {problem.test_cases && problem.test_cases.length > 0 && (
            <div className="content-section">
              <h3>🧪 測試點</h3>
              <div className="test-cases">
                {problem.test_cases.map((tc, i) => (
                  <div key={i} className="test-case-card">
                    <div className="test-case-header" onClick={() => setSelectedTest(selectedTest === i ? null : i)}>
                      <span>測試點 {i + 1}</span>
                      <span className="toggle-hint">{selectedTest === i ? '▲ 隱藏' : '▼ 顯示'}</span>
                    </div>
                    {selectedTest === i && (
                      <div className="test-case-body">
                        <div className="io-item">
                          <div className="io-label">輸入</div>
                          <pre className="io-content">{tc.input || '(無輸入)'}</pre>
                        </div>
                        <div className="io-item">
                          <div className="io-label">輸出</div>
                          <pre className="io-content">{tc.output}</pre>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 提交结果 */}
          {result && (
            <div className={`result-card ${result.success ? 'result-success' : 'result-error'}`}>
              <h3>{result.success ? '✅ 批改完成' : '❌ 提交失敗'}</h3>
              <pre className="result-detail">{result.detail}</pre>
              {result.score !== undefined && (
                <div className="result-score">
                  得分：<span className={scoreClass(result.score)}>{result.score}</span>
                </div>
              )}
            </div>
          )}

          {/* 提交区域 */}
          <div className="submit-section">
            <div className="submit-header">
              <h3><Send size={20} /> 提交代碼</h3>
              <p>編寫 Python 代碼，通過所有測試點挑戰成功！</p>
            </div>
            <form onSubmit={handleSubmit}>
              <textarea
                className="code-editor"
                placeholder="在此輸入 Python 代碼..."
                value={code}
                onChange={(e) => setCode(e.target.value)}
                spellCheck={false}
              />
              <button
                type="submit"
                className={`submit-btn ${submitting ? 'loading' : ''}`}
                disabled={submitting || !code.trim()}
              >
                {submitting ? <><Loader size={18} className="spin" /> 批改中...</> : <><Send size={18} /> 提交代碼</>}
              </button>
            </form>
          </div>

          {/* 提交历史 */}
          {history.length > 0 && (
            <div className="submission-history">
              <div className="history-header">
                <h4>📜 提交歷史</h4>
              </div>
              {history.map((h) => (
                <div key={h.id} className="submission-item">
                  <div className="submission-info">
                    {statusIcon(h.status)}
                    <span className="submission-time">
                      {new Date(h.submitted_at).toLocaleString('zh-TW')}
                    </span>
                    <span className={`submission-score ${scoreClass(h.score)}`}>
                      {h.score} 分
                    </span>
                  </div>
                  <span className={`status-badge status-${h.status}`}>{h.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
