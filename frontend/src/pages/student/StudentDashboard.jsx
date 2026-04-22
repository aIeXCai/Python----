import { useEffect, useState, useRef } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Trophy, CheckCircle, BarChart2, BookOpen, RefreshCw, Loader, FileText, Clock } from 'lucide-react'
import Navbar from '../../components/Navbar.jsx'
import { getProblems, getScores, getStudentStats } from '../../api/index.js'
import { getInfoQuizzes } from '../../api/info.js'

export default function StudentDashboard() {
  const [problems, setProblems] = useState([])
  const [scores, setScores] = useState([])
  const [stats, setStats] = useState({ total_problems: 0, completed_problems: 0, average_score: 0, rank: 1 })
  const [quizzes, setQuizzes] = useState([])   // 信息课小测列表
  const [loading, setLoading] = useState(true)
  const [username, setUsername] = useState('')
  const [grade, setGrade] = useState('')
  const [classNum, setClassNum] = useState('')
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const mountedRef = useRef(true)

  // 优先读 URL 参数（导航带过来的），其次读 localStorage，最后默认 ai
  const getCourse = () => searchParams.get('course') || localStorage.getItem('selected_course') || 'ai'

  useEffect(() => {
    const raw = localStorage.getItem('user')
    if (!raw) { navigate('/login'); return }
    try {
      const u = JSON.parse(raw)
      setUsername(u.display_name || u.username || '')
      setGrade(u.grade || '')
      setClassNum(u.class_num || '')
    } catch {}

    fetchData()
  }, [searchParams])

  // StrictMode 下 useEffect 会 double-invoke，mountedRef 跨调用共享，防止旧请求状态覆盖新渲染
  const fetchData = async () => {
    const saved = mountedRef.current
    setLoading(true)
    try {
      const course = getCourse()
      if (course === 'info') {
        // 信息课：加载小测列表
        const q = await getInfoQuizzes()
        if (!mountedRef.current || !saved) return
        setQuizzes(q)
      } else {
        // AI课：加载题目列表
        const [p, s, st] = await Promise.all([
          getProblems(course),
          getScores(course),
          getStudentStats(course),
        ])
        if (!mountedRef.current || !saved) return
        setProblems(p)
        setScores(s)
        setStats(st)
      }
    } catch (err) {
      if (!mountedRef.current) return
      console.error('[Dashboard] fetchData 错误:', err)
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }

  const getProblemStatus = (problemId) => {
    const entry = scores.find((s) => s.problem_id === problemId)
    if (!entry) return 'new'
    return entry.best_score >= 100 ? 'completed' : 'attempted'
  }

  const statusLabel = { new: '未开始', attempted: '作答中', completed: '已通过' }

  const isInfo = getCourse() === 'info'
  const themeVars = isInfo
    ? { '--primary': '#11998e', '--secondary': '#38ef7d', '--bg-gradient': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)' }
    : { '--primary': '#667eea', '--secondary': '#764ba2', '--bg-gradient': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }

  return (
    <div className="page-bg" style={themeVars}>
      <Navbar username={username} grade={grade} class_num={classNum} />

      <main className="main-content">
        {/* 欢迎区 */}
        <div className="welcome-section">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <h1>欢迎回来，{username}！</h1>
            <span className="course-badge" style={{
              background: 'var(--bg-gradient)',
              color: '#fff',
              padding: '4px 14px',
              borderRadius: '20px',
              fontSize: '0.85rem',
              fontWeight: 600,
            }}>
              {isInfo ? '信息科技课' : '人工智能课'}
            </span>
          </div>
          <p>{isInfo ? '选择一个单元小测来检验你的学习成果吧！' : '准备好挑战今天的题目了吗？选择一个题目开始你的学习之旅吧！'}</p>
        </div>

        {/* 统计卡片 */}
        <div className="stats-grid">
          <div className="stat-card problems">
            <BookOpen size={36} />
            <h3>{stats.total_problems}</h3>
            <p>总题目数</p>
          </div>
          <div className="stat-card completed">
            <CheckCircle size={36} />
            <h3>{stats.completed_problems}</h3>
            <p>已完成题目</p>
          </div>
          <div className="stat-card average">
            <BarChart2 size={36} />
            <h3>{stats.average_score}分</h3>
            <p>平均成绩</p>
          </div>
          <div className="stat-card rank">
            <Trophy size={36} />
            <h3>第{stats.rank}名</h3>
            <p>班级排名</p>
          </div>
        </div>

        {/* 信息课：小测列表 */}
        {isInfo && (
          <div className="problems-section">
            <div className="section-header">
              <h2><FileText size={24} /> 小测</h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="refresh-btn" onClick={() => navigate('/course-select')}>
                  🔄 切换课程
                </button>
                <button className="refresh-btn" onClick={fetchData}>
                  <RefreshCw size={16} /> 重新整理
                </button>
              </div>
            </div>

            {loading ? (
              <div className="loading-state">
                <Loader size={32} className="spin" />
                <p>载入小测中...</p>
              </div>
            ) : quizzes.length === 0 ? (
              <div className="empty-state">
                <FileText size={64} />
                <h3>暂无小测</h3>
                <p>老师还未发布小测</p>
              </div>
            ) : (
              <div className="problems-grid">
                {quizzes.map((quiz) => {
                  const hasScore = quiz.submitted && quiz.best_score !== null
                  return (
                    <div key={quiz.id} className="problem-card">
                      <div className="problem-header">
                        <div className="problem-title">
                          <FileText size={18} />
                          {quiz.title}
                        </div>
                        <span className={`problem-status status-${hasScore ? 'completed' : 'new'}`}>
                          {hasScore ? `${quiz.best_score}分` : '未做'}
                        </span>
                      </div>
                      <div style={{ padding: '12px 16px', color: '#666', fontSize: '0.85rem' }}>
                        <div style={{ marginBottom: '6px' }}>
                          <Clock size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
                          {quiz.num_questions} 题 · {quiz.time_limit ? `${quiz.time_limit}分钟` : '不限时'}
                        </div>
                        {quiz.unit_names && quiz.unit_names.length > 0 && (
                          <div style={{ fontSize: '0.8rem', color: '#888' }}>
                            {quiz.unit_names.join(' / ')}
                          </div>
                        )}
                      </div>
                      <div className="problem-actions">
                        {hasScore ? (
                          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            <Link to={`/student/quiz/${quiz.id}`} className="btn btn-primary">
                              🔄 重新作答
                            </Link>
                            <Link to={`/student/quiz-result/${quiz.id}`} className="btn btn-secondary">
                              查看成绩
                            </Link>
                          </div>
                        ) : (
                          <Link to={`/student/quiz/${quiz.id}`} className="btn btn-primary">
                            开始答题
                          </Link>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* AI课：题目列表 */}
        {!isInfo && (
          <div className="problems-section">
            <div className="section-header">
              <h2><BookOpen size={24} /> 练习题目</h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="refresh-btn" onClick={() => navigate('/course-select')}>
                  🔄 切换课程
                </button>
                <button className="refresh-btn" onClick={fetchData}>
                  <RefreshCw size={16} /> 重新整理
                </button>
              </div>
            </div>

            {loading ? (
              <div className="loading-state">
                <Loader size={32} className="spin" />
                <p>载入题目中...</p>
              </div>
            ) : problems.length === 0 ? (
              <div className="empty-state">
                <BookOpen size={64} />
                <h3>暂无题目</h3>
                <p>联系老师添加题目</p>
              </div>
            ) : (
              <div className="problems-grid">
                {problems.map((p) => {
                  const status = getProblemStatus(p.problem_id)
                  return (
                    <div key={p.problem_id} className="problem-card">
                      <div className="problem-header">
                        <div className="problem-title">
                          <BookOpen size={18} />
                          {p.title || p.problem_id}
                        </div>
                        <span className={`problem-status status-${status}`}>
                          {statusLabel[status]}
                        </span>
                      </div>

                      <div className="problem-actions">
                        <Link to={`/problem/${p.problem_id}?course=${getCourse()}`} className="btn btn-primary">
                          {status === 'new' ? '开始答题' : '继续作答'}
                        </Link>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
