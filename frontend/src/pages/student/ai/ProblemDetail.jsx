import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { BookOpen, Send, ArrowLeft, Loader, CheckCircle, XCircle, Clock, Play, RotateCcw, ChevronDown, ChevronRight } from 'lucide-react'
import Editor from '@monaco-editor/react'
import Navbar from '../../../components/Navbar.jsx'
import { getProblemDetail, getSubmissionHistory, runCode, submitCode } from '../../../api/index.js'
import { useChat } from '../../../contexts/ChatContext.jsx'

export default function ProblemDetail() {
  const { problemId } = useParams()
  const navigate = useNavigate()
  const chat = useChat()

  const [problem, setProblem] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [username, setUsername] = useState('')
  const [grade, setGrade] = useState('')
  const [classNum, setClassNum] = useState('')
  const [code, setCode] = useState('')
  const [runOutput, setRunOutput] = useState(null)
  const [stdinDialogOpen, setStdinDialogOpen] = useState(false)
  const [stdinValue, setStdinValue] = useState('')
  const [running, setRunning] = useState(false)
  const [testCasesOpen, setTestCasesOpen] = useState(true)

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

  // Register AI problem context for chat assistant
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
      setCode(pd.template_code || '')
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleRun = async () => {
    if (!code.trim()) return
    setRunning(true)
    setRunOutput(null)

    if (code.includes('input(')) {
      setStdinDialogOpen(true)
      setRunning(false)
      return
    }

    await executeRun(code, '')
  }

  const executeRun = async (sourceCode, stdin) => {
    setRunning(true)
    setRunOutput(null)
    try {
      const data = await runCode(sourceCode, stdin)
      setRunOutput({
        output: data.output || '',
        error: data.error || '',
      })
    } catch (err) {
      setRunOutput({
        output: '',
        error: err.message,
      })
    } finally {
      setRunning(false)
    }
  }

  const handleStdinSubmit = () => {
    setStdinDialogOpen(false)
    executeRun(code, stdinValue)
    setStdinValue('')
  }

  const handleStdinCancel = () => {
    setStdinDialogOpen(false)
    setStdinValue('')
  }

  const handleReset = () => {
    if (problem?.template_code) {
      setCode(problem.template_code)
    } else {
      setCode('')
    }
    setRunOutput(null)
    setResult(null)
  }

  const handleSubmitCode = async () => {
    if (!code.trim()) return
    setSubmitting(true)
    setResult(null)
    try {
      const data = await submitCode({ problem_id: problemId, code })
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
        {/* Left sidebar: problem list */}
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

        {/* Right: answer area */}
        <div className="answer-area">
          {/* Problem info */}
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

          {/* Problem description */}
          <div className="content-section">
            <h3><BookOpen size={18} /> 题目描述</h3>
            <pre className="problem-description">{problem.description}</pre>
          </div>

          {/* Test cases */}
          {problem.test_cases && problem.test_cases.length > 0 && (
            <div className="content-section">
              <h3
                className="test-cases-toggle"
                onClick={() => setTestCasesOpen(!testCasesOpen)}
                style={{ cursor: 'pointer', userSelect: 'none' }}
              >
                {testCasesOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                🧪 测试点 ({problem.test_cases.length})
              </h3>
              {testCasesOpen && (
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
              )}
            </div>
          )}

          {/* Submission result */}
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

          {/* Monaco Editor */}
          <div className="content-section">
            <h3>💻 代码编辑器</h3>
            <div className="ide-editor-wrapper">
              <Editor
                height="400px"
                language="python"
                theme="vs-dark"
                value={code}
                onChange={(value) => setCode(value || '')}
                loading={<div className="ide-loading"><Loader size={24} className="spin" /><span>编辑器加载中...</span></div>}
                options={{
                  fontSize: 14,
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                  lineNumbers: 'on',
                  tabSize: 4,
                  automaticLayout: true,
                }}
              />
            </div>
          </div>

          {/* Run output */}
          {runOutput && (
            <div className="content-section">
              <h3>📤 运行输出</h3>
              <div className="run-output-area">
                {runOutput.output && (
                  <pre className="run-output-stdout">{runOutput.output}</pre>
                )}
                {runOutput.error && (
                  <pre className="run-output-stderr">{runOutput.error}</pre>
                )}
                {!runOutput.output && !runOutput.error && (
                  <p className="run-output-empty">（无输出）</p>
                )}
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="ide-actions">
            <button
              className="ide-btn ide-btn-run"
              onClick={handleRun}
              disabled={running || !code.trim()}
            >
              {running ? <><Loader size={16} className="spin" /> 运行中...</> : <><Play size={16} /> 运行</>}
            </button>
            <button
              className="ide-btn ide-btn-reset"
              onClick={handleReset}
              disabled={running || submitting}
            >
              <RotateCcw size={16} /> 重做
            </button>
            <button
              className="ide-btn ide-btn-submit"
              onClick={handleSubmitCode}
              disabled={submitting || running || !code.trim()}
            >
              {submitting ? <><Loader size={16} className="spin" /> 提交中...</> : <><Send size={16} /> 保存并提交</>}
            </button>
          </div>

          {/* Submission history */}
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

      {/* stdin dialog */}
      {stdinDialogOpen && (
        <div className="ide-overlay" onClick={handleStdinCancel}>
          <div className="ide-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>📥 输入</h3>
            <p>您的代码使用了 input()，请输入程序需要的值：</p>
            <textarea
              className="ide-dialog-input"
              value={stdinValue}
              onChange={(e) => setStdinValue(e.target.value)}
              placeholder="在此输入..."
              rows={4}
              autoFocus
            />
            <div className="ide-dialog-actions">
              <button className="ide-btn ide-btn-reset" onClick={handleStdinCancel}>取消</button>
              <button className="ide-btn ide-btn-run" onClick={handleStdinSubmit}>运行</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
