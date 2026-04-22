import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Trophy, CheckCircle, BarChart2, BookOpen, RefreshCw, Loader } from 'lucide-react'
import Navbar from '../../components/Navbar.jsx'
import { getProblems, getScores, getStudentStats } from '../../api/index.js'

export default function StudentDashboard() {
  const [problems, setProblems] = useState([])
  const [scores, setScores] = useState([])
  const [stats, setStats] = useState({ total_problems: 0, completed_problems: 0, average_score: 0, rank: 1 })
  const [loading, setLoading] = useState(true)
  const [username, setUsername] = useState('')
  const [grade, setGrade] = useState('')
  const [classNum, setClassNum] = useState('')
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // 优先读 URL 参数（导航带过来的），其次读 localStorage
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
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const course = getCourse()
      const [p, s, st] = await Promise.all([
        getProblems(course),
        getScores(course),
        getStudentStats(course),
      ])
      setProblems(p)
      setScores(s)
      setStats(st)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
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
          <p>准备好挑战今天的题目了吗？选择一个题目开始你的学习之旅吧！</p>
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

        {/* 题目列表 */}
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
      </main>
    </div>
  )
}
