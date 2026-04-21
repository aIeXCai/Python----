import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Trophy, CheckCircle, BarChart2, BookOpen, RefreshCw, Loader } from 'lucide-react'
import Navbar from '../components/Navbar.jsx'
import { getProblems, getScores, getStudentStats } from '../api/index.js'

export default function StudentDashboard() {
  const [problems, setProblems] = useState([])
  const [scores, setScores] = useState([])
  const [stats, setStats] = useState({ total_problems: 0, completed_problems: 0, average_score: 0, rank: 1 })
  const [loading, setLoading] = useState(true)
  const [username, setUsername] = useState('')
  const [grade, setGrade] = useState('')
  const [classNum, setClassNum] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    const raw = localStorage.getItem('user')
    if (!raw) { navigate('/login'); return }
    try {
      const u = JSON.parse(raw)
      setUsername(u.username || '')
      setGrade(u.grade || '')
      setClassNum(u.class_num || '')
    } catch {}

    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [p, s, st] = await Promise.all([getProblems(), getScores(), getStudentStats()])
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

  const statusLabel = { new: '未開始', attempted: '作答中', completed: '已通過' }

  return (
    <div className="page-bg">
      <Navbar username={username} grade={grade} class_num={classNum} />

      <main className="main-content">
        {/* 欢迎区 */}
        <div className="welcome-section">
          <h1>歡迎回來，{username}！</h1>
          <p>準備好挑戰今天的程式設計題目了嗎？選擇一個題目開始你的學習之旅吧！</p>
        </div>

        {/* 统计卡片 */}
        <div className="stats-grid">
          <div className="stat-card problems">
            <BookOpen size={36} />
            <h3>{stats.total_problems}</h3>
            <p>總題目數</p>
          </div>
          <div className="stat-card completed">
            <CheckCircle size={36} />
            <h3>{stats.completed_problems}</h3>
            <p>已完成題目</p>
          </div>
          <div className="stat-card average">
            <BarChart2 size={36} />
            <h3>{stats.average_score}分</h3>
            <p>平均成績</p>
          </div>
          <div className="stat-card rank">
            <Trophy size={36} />
            <h3>第{stats.rank}名</h3>
            <p>班級排名</p>
          </div>
        </div>

        {/* 题目列表 */}
        <div className="problems-section">
          <div className="section-header">
            <h2><BookOpen size={24} /> 練習題目</h2>
            <button className="refresh-btn" onClick={fetchData}>
              <RefreshCw size={16} /> 重新整理
            </button>
          </div>

          {loading ? (
            <div className="loading-state">
              <Loader size={32} className="spin" />
              <p>載入題目中...</p>
            </div>
          ) : problems.length === 0 ? (
            <div className="empty-state">
              <BookOpen size={64} />
              <h3>暫無題目</h3>
              <p>聯繫老師添加題目</p>
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

                    <p className="problem-description">
                      {p.description
                        ? p.description.slice(0, 100).replace(/[#*]/g, '') + '...'
                        : '點擊查看題目詳情'}
                    </p>

                    <div className="problem-meta">
                      <span className="meta-item">
                        <BarChart2 size={14} /> {p.test_count || 0} 個測試點
                      </span>
                      {p.difficulty && (
                        <span className={`difficulty difficulty-${(p.difficulty || '').toLowerCase()}`}>
                          {p.difficulty}
                        </span>
                      )}
                    </div>

                    <div className="problem-actions">
                      <Link to={`/problem/${p.problem_id}`} className="btn btn-primary">
                        {status === 'new' ? '開始答題' : '繼續作答'}
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
