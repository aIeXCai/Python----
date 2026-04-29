import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { BookOpen, Send, ArrowLeft, Loader, CheckCircle, XCircle, Clock, Upload } from 'lucide-react'
import Navbar from '../../../components/Navbar.jsx'
import { getProblemDetail, getSubmissionHistory, getToken } from '../../../api/index.js'
import { useChat } from '../../../contexts/ChatContext.jsx'

export default function ProblemDetail() {
  const { problemId } = useParams()
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const chat = useChat()

  const [problem, setProblem] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [username, setUsername] = useState('')
  const [grade, setGrade] = useState('')
  const [classNum, setClassNum] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)

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
  }, [problemId])

  // 注册 AI 题目上下文 → 聊天助手
  useEffect(() => {
    if (problem) {
      chat.setContext({
        type: 'ai_problem',
        id: problemId,
        title: problem.title || problemId,
        description: problem.description || '',
      })
    }
    return () => chat.setContext(null)
  }, [problem, problemId])

  const loadData = async () => {
    setLoading(true)
    try {
      const [pd, hist] = await Promise.all([
        getProblemDetail(problemId),
        getSubmissionHistory(),
      ])
      setProblem(pd)
      setHistory(hist.filter((h) => h.problem_id === problemId))
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!selectedFile) return
    await submitByFile()
  }

  const submitByFile = async () => {
    if (!selectedFile) return
    setSubmitting(true)
    setResult(null)
    try {
      const formData = new FormData()
      formData.append('problem_id', problemId)
      formData.append('code', selectedFile)

      const token = getToken()
      const res = await fetch('http://localhost:8080/api/ai/submit_code/', {
        method: 'POST',
        headers: { 'Authorization': `Token ${token}` },
        body: formData,
      })
      const data = await res.json()
      const normalized = {
        success: data.passed !== undefined ? data.passed : data.success,
        score: data.score ?? (data.passed ? 100 : 0),
        detail: data.output || data.detail || data.message || JSON.stringify(data),
      }
      setResult(normalized)
      const hist = await getSubmissionHistory()
      setHistory(hist.filter((h) => h.problem_id === problemId))
    } catch (err) {
      setResult({ success: false, detail: err.message })
    } finally {
      setSubmitting(false)
    }
  }

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (file && file.name.endsWith('.py')) {
      setSelectedFile(file)
    } else {
      alert('请上传 .py 格式的 Python 档案')
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
        <div className="loading-state"><Loader size={32} className="spin" /><p>载入题目中...</p></div>
      </div>
    )
  }

  if (!problem) {
    return (
      <div className="page-bg">
        <Navbar username={username} grade={grade} class_num={classNum} />
        <div className="loading-state"><p>题目不存在</p><Link to="/student/dashboard" className="btn btn-primary">返回主页</Link></div>
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
            <h2><BookOpen size={20} /> 题目列表</h2>
          </div>
          <div className="problems-list">
            <div className="problem-item active">
              <h4>{problem.title || problemId}</h4>
              <p>{problem.test_cases?.length || 0} 个测试点</p>
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <Link to="/student/dashboard" className="btn btn-secondary" style={{ width: '100%', justifyContent: 'center' }}>
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
              <span className="meta-item"><BookOpen size={14} /> {problem.test_cases?.length || 0} 个测试点</span>
              {problem.difficulty && (
                <span className={`difficulty difficulty-${problem.difficulty.toLowerCase()}`}>{problem.difficulty}</span>
              )}
            </div>
          </div>

          {/* 题目描述 - 可滚动查看完整内容 */}
          <div className="content-section">
            <h3><BookOpen size={18} /> 题目描述</h3>
            <pre className="problem-description">{problem.description}</pre>
          </div>

          {/* 测试点 - 默认全部展开 */}
          {problem.test_cases && problem.test_cases.length > 0 && (
            <div className="content-section">
              <h3>🧪 测试点</h3>
              <div className="test-cases">
                {problem.test_cases.map((tc, i) => (
                  <div key={i} className="test-case-card">
                    <div className="test-case-header">
                      <span>测试点 {i + 1}</span>
                    </div>
                    <div className="test-case-body">
                      <div className="io-item">
                        <div className="io-label">输入</div>
                        <pre className="io-content">{tc.input || '(无输入)'}</pre>
                      </div>
                      <div className="io-item">
                        <div className="io-label">输出</div>
                        <pre className="io-content">{tc.output}</pre>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 提交结果 */}
          {result && (
            <div className={`result-card ${result.success ? 'result-success' : 'result-error'}`}>
              <h3>{result.success ? '✅ 批改完成' : '❌ 提交失败'}</h3>
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
              <h3><Upload size={20} /> 上传 Python 档案</h3>
              <p>请上传你的 Python 程式码档案 (.py)，系统将自动批改</p>
            </div>
            <form onSubmit={handleSubmit}>
              <input
                type="file"
                ref={fileInputRef}
                accept=".py"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              <div className="file-upload-area">
                <button
                  type="button"
                  className="file-upload-btn"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload size={18} />
                  {selectedFile ? selectedFile.name : '选择 .py 档案'}
                </button>
                {selectedFile && (
                  <span className="file-selected-name">✓ {selectedFile.name}</span>
                )}
              </div>
              <button
                type="submit"
                className={`submit-btn ${submitting ? 'loading' : ''}`}
                disabled={submitting || !selectedFile}
              >
                {submitting
                  ? <><Loader size={18} className="spin" /> 批改中...</>
                  : <><Send size={18} /> 提交档案</>
                }
              </button>
            </form>
          </div>

          {/* 提交历史 */}
          {history.length > 0 && (
            <div className="submission-history">
              <div className="history-header">
                <h4>📜 提交历史</h4>
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
