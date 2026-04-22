import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom'
import { BookOpen, Send, ArrowLeft, Loader, CheckCircle, XCircle, Clock, Upload } from 'lucide-react'
import Navbar from '../components/Navbar.jsx'
import { getProblemDetail, submitCode, getSubmissionHistory } from '../api/index.js'

export default function ProblemDetail() {
  const { problemId } = useParams()
  const [searchParams] = useSearchParams()
  const courseParam = searchParams.get('course')

  // 同步 course 到 localStorage，防止返回 Dashboard 时 URL 参数丢失兜底
  useEffect(() => {
    if (courseParam) {
      localStorage.setItem('selected_course', courseParam)
    } else {
      // URL 没有 course 参数时，尝试从 localStorage 恢复
      const stored = localStorage.getItem('selected_course')
      if (stored) localStorage.setItem('selected_course', stored)
    }
  }, [courseParam])
  const navigate = useNavigate()

  const [problem, setProblem] = useState(null)
  const [code, setCode] = useState('')
  const [fileName, setFileName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  // 展开所有测试点，初始全部为 true
  const [expandedTests, setExpandedTests] = useState({})
  const [username, setUsername] = useState('')
  const [grade, setGrade] = useState('')
  const [classNum, setClassNum] = useState('')
  const fileInputRef = useRef(null)

  useEffect(() => {
    const raw = localStorage.getItem('user')
    if (!raw) { navigate('/login'); return }
    try {
      const u = JSON.parse(raw)
      setUsername(u.display_name || u.username || '')
      setGrade(u.grade || '')
      setClassNum(u.class_num || '')
    } catch {}
    loadData()
  }, [problemId, courseParam])

  const loadData = async () => {
    let cancelled = false
    setLoading(true)
    try {
      const [pd, hist] = await Promise.all([
        getProblemDetail(problemId, courseParam),
        getSubmissionHistory(),
      ])
      if (cancelled) return
      setProblem(pd)
      setHistory(hist.filter((h) => h.problem_id === problemId))
      // Pre-fill with last submission if exists
      const last = hist.find((h) => h.problem_id === problemId)
      if (last && last.code) setCode(last.code)
      // 默认全部展开测试点
      if (pd.test_cases) {
        const init = {}
        pd.test_cases.forEach((_, i) => { init[i] = true })
        setExpandedTests(init)
      }
    } catch (err) {
      if (cancelled) return
      console.error(err)
    } finally {
      if (!cancelled) setLoading(false)
    }
  }

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      setCode(ev.target.result)
      setFileName(file.name)
    }
    reader.readAsText(file)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!fileName) return
    setSubmitting(true)
    setResult(null)
    try {
      const res = await submitCode({ problem_id: problemId, code })
      setResult(res)
      sessionStorage.setItem('lastSubmission', JSON.stringify({ ...res, problem_id: problemId }))
      const hist = await getSubmissionHistory()
      setHistory(hist.filter((h) => h.problem_id === problemId))
    } catch (err) {
      setResult({ success: false, detail: err.message })
    } finally {
      setSubmitting(false)
    }
  }

  const toggleTest = (i) => {
    setExpandedTests(prev => ({ ...prev, [i]: !prev[i] }))
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
        <div className="loading-state"><p>題目不存在</p><Link to="/student/dashboard" className="btn btn-primary">返回主頁</Link></div>
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
            <Link to={`/student/dashboard?course=${courseParam}`} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'center' }}>
              <ArrowLeft size={16} /> 返回主页
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

          {/* 题目描述 - 完整显示，不截断 */}
          <div className="content-section">
            <h3><BookOpen size={18} /> 題目描述</h3>
            <div className="problem-description-full">{problem.description}</div>
          </div>

          {/* 测试点 - 默认全部展开 */}
          {problem.test_cases && problem.test_cases.length > 0 && (
            <div className="content-section">
              <h3>🧪 測試點</h3>
              <div className="test-cases">
                {problem.test_cases.map((tc, i) => (
                  <div key={i} className="test-case-card">
                    <div className="test-case-header" onClick={() => toggleTest(i)}>
                      <span>測試點 {i + 1}</span>
                      <span className="toggle-hint">{expandedTests[i] ? '▲ 隱藏' : '▼ 顯示'}</span>
                    </div>
                    {expandedTests[i] && (
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

          {/* 提交区域 - 仅 .py 文件上传 */}
          <div className="submit-section">
            <div className="submit-header">
              <h3><Upload size={20} /> 上傳代碼檔案</h3>
              <p>上傳 .py 文件，系統將自動批改所有測試點</p>
            </div>
            <form onSubmit={handleSubmit}>
              <input
                type="file"
                ref={fileInputRef}
                accept=".py"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              <div className="file-upload-area" onClick={() => fileInputRef.current.click()}>
                <Upload size={32} />
                <p>{fileName || '點擊選擇 .py 文件'}</p>
                <span>仅支持 .py 格式</span>
              </div>
              <button
                type="submit"
                className={`submit-btn ${submitting ? 'loading' : ''}`}
                disabled={submitting || !fileName}
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
