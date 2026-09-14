import { useEffect, useState, useRef } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Trophy, CheckCircle, BarChart2, BookOpen, RefreshCw, Loader, FileText, Clock } from 'lucide-react'
import Navbar from '../../components/Navbar.jsx'
import { getProblems, getScores, getStudentStats } from '../../api/index.js'
import { getInfoQuizzes } from '../../api/info.js'
import { getStudentAIQuizzes } from '../../api/aiStudentQuiz.js'
import { useChat } from '../../contexts/ChatContext.jsx'

const PRACTICE_COMPLETION_SCORE = 100

export default function StudentDashboard() {
  const chat = useChat()
  const [problems, setProblems] = useState([])
  const [scores, setScores] = useState([])
  const [stats, setStats] = useState({ total_problems: 0, completed_problems: 0, average_score: 0, rank: 1 })
  const [quizzes, setQuizzes] = useState([])   // 信息课小测列表
  const [aiQuizzes, setAIQuizzes] = useState([])
  const [aiSection, setAISection] = useState('quizzes')
  const [practiceDifficulty, setPracticeDifficulty] = useState('')
  const [practiceUnit, setPracticeUnit] = useState('')
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

  // 清除聊天上下文（dashboard 无特定上下文）
  useEffect(() => {
    chat.setContext(null)
  }, [])

  // StrictMode 下 useEffect 会 double-invoke，mountedRef 跨调用共享，防止旧请求状态覆盖新渲染
  const fetchData = async () => {
    const saved = mountedRef.current
    setLoading(true)
    try {
      const course = getCourse()
      if (course === 'info') {
        // 信息课：加载小测列表和统计
        const [q, st] = await Promise.all([
          getInfoQuizzes(),
          getStudentStats('info'),
        ])
        if (!mountedRef.current || !saved) return
        setQuizzes(q)
        setStats(st)
      } else {
        // AI课：加载题目列表
        const [q, p, s, st] = await Promise.all([
          getStudentAIQuizzes(),
          getProblems(course),
          getScores(course),
          getStudentStats(course),
        ])
        if (!mountedRef.current || !saved) return
        setAIQuizzes(q)
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
    return entry.best_score >= PRACTICE_COMPLETION_SCORE ? 'completed' : 'attempted'
  }

  const statusLabel = { new: '未开始', attempted: '作答中', completed: '已通过' }
  const practiceUnits = [...new Set(problems.map(problem => problem.unit_name).filter(Boolean))]
  const filteredProblems = problems.filter(problem =>
    (!practiceDifficulty || problem.difficulty === practiceDifficulty)
    && (!practiceUnit || problem.unit_name === practiceUnit))

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
          <p>{isInfo ? '选择一个单元小测来检验你的学习成果吧！' : '先完成老师发布的小测，也可以继续从题库中练习编程。'}</p>
        </div>

        {/* 统计卡片 */}
        <div className="stats-grid">
          <div className="stat-card problems">
            <BookOpen size={36} />
            <h3>{stats.total_problems}</h3>
            <p>{isInfo ? '总小测数' : '总题目数'}</p>
          </div>
          <div className="stat-card completed">
            <CheckCircle size={36} />
            <h3>{stats.completed_problems}</h3>
            <p>{isInfo ? '已完成小测' : '已完成题目'}</p>
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
                <p>加载小测中...</p>
              </div>
            ) : quizzes.length === 0 ? (
              <div className="empty-state">
                <FileText size={64} />
                <h3>暂无小测</h3>
                <p>教师还未发布小测</p>
              </div>
            ) : (
              <div className="problems-grid">
                {quizzes.map((quiz) => {
                  const inProgress = quiz.action === 'continue'
                  const displayScore = quiz.score ?? quiz.best_score
                  const hasScore = displayScore !== null && displayScore !== undefined
                  return (
                    <div key={quiz.id} className="problem-card">
                      <div className="problem-header">
                        <div className="problem-title">
                          <FileText size={18} />
                          {quiz.title}
                        </div>
                        <span className={`problem-status status-${inProgress ? 'new' : hasScore ? 'completed' : 'new'}`}>
                          {inProgress ? '作答中' : hasScore ? `${displayScore}分` : '未做'}
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
                        {inProgress ? (
                          <Link to={`/student/quiz/${quiz.id}`} className="btn btn-primary">继续作答</Link>
                        ) : quiz.action === 'restart' ? (
                          <>
                            <Link to={`/student/quiz-result/${quiz.id}`} className="btn btn-secondary">查看成绩</Link>
                            <Link to={`/student/quiz/${quiz.id}`} className="btn btn-primary">再做一次</Link>
                          </>
                        ) : (
                          <Link to={`/student/quiz/${quiz.id}`} className="btn btn-primary">开始答题</Link>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {!isInfo && (
          <div className="ai-dashboard-tabs" role="tablist" aria-label="AI 课程学习模块">
            <button id="ai-dashboard-tab-quizzes" type="button" role="tab" aria-selected={aiSection === 'quizzes'} aria-controls="ai-quizzes-panel" className={aiSection === 'quizzes' ? 'active' : ''} onClick={() => setAISection('quizzes')}><FileText size={19} />我的小测</button>
            <button id="ai-dashboard-tab-practice" type="button" role="tab" aria-selected={aiSection === 'practice'} aria-controls="ai-practice-panel" className={aiSection === 'practice' ? 'active' : ''} onClick={() => setAISection('practice')}><BookOpen size={19} />题库练习</button>
          </div>
        )}

        {/* AI课：正式小测 */}
        {!isInfo && aiSection === 'quizzes' && (
          <div className="problems-section ai-dashboard-panel" id="ai-quizzes-panel" role="tabpanel" aria-labelledby="ai-dashboard-tab-quizzes">
            <div className="section-header">
              <h2><FileText size={24} /> 我的小测</h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="refresh-btn" onClick={() => navigate('/course-select')}>🔄 切换课程</button>
                <button className="refresh-btn" onClick={fetchData}><RefreshCw size={16} /> 重新整理</button>
              </div>
            </div>
            {loading ? <div className="loading-state"><Loader size={32} className="spin" /><p>加载小测中...</p></div> : aiQuizzes.length === 0 ? <div className="empty-state"><FileText size={52} /><h3>暂无小测</h3><p>教师还未发布 AI 小测</p></div> : <div className="problems-grid">{aiQuizzes.map(quiz => {
              const inProgress = quiz.action === 'continue'
              const finished = quiz.action === 'result' || quiz.action === 'restart'
              const settling = quiz.action === 'settling'
              return <div key={quiz.id} className="problem-card">
                <div className="problem-header"><div className="problem-title"><FileText size={18} />{quiz.title}</div><span className={`problem-status status-${finished ? 'completed' : 'new'}`}>{settling ? '结算中' : inProgress ? '作答中' : finished ? '已完成' : '未开始'}</span></div>
                <div style={{ padding: '12px 16px', color: '#666', fontSize: '.85rem', display: 'grid', gap: 5 }}><span><Clock size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />{quiz.choice_count} 道选择题 · {quiz.programming_count} 道编程题 · {quiz.time_limit ? `${quiz.time_limit}分钟` : '不限时'}</span>{(quiz.latest_score !== null || quiz.best_score !== null) && <span>最近成绩：<strong>{quiz.latest_score ?? '--'}</strong>{quiz.latest_score !== null && ' 分'}{quiz.best_score !== null && <> · 历史最好：<strong>{quiz.best_score}</strong> 分</>}</span>}</div>
                <div className="problem-actions">
                  {settling ? (
                    <Link to={`/student/ai-quiz-result/${quiz.id}`} className="btn btn-secondary">查看结算</Link>
                  ) : finished ? (
                    <>
                      <Link to={`/student/ai-quiz-result/${quiz.id}`} className="btn btn-secondary">查看结果</Link>
                      <Link to={`/student/ai-quiz/${quiz.id}`} className="btn btn-primary">再做一次</Link>
                    </>
                  ) : (
                    <Link to={`/student/ai-quiz/${quiz.id}`} className="btn btn-primary">{inProgress ? '继续作答' : '开始小测'}</Link>
                  )}
                </div>
              </div>
            })}</div>}
          </div>
        )}

        {/* AI课：题库练习 */}
        {!isInfo && aiSection === 'practice' && (
          <div className="problems-section ai-dashboard-panel" id="ai-practice-panel" role="tabpanel" aria-labelledby="ai-dashboard-tab-practice">
            <div className="section-header">
              <h2><BookOpen size={24} /> 题库练习</h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                <select aria-label="练习单元筛选" value={practiceUnit} onChange={event => setPracticeUnit(event.target.value)} className="refresh-btn"><option value="">全部单元</option>{practiceUnits.map(unit => <option key={unit}>{unit}</option>)}</select>
                <select aria-label="练习难度筛选" value={practiceDifficulty} onChange={event => setPracticeDifficulty(event.target.value)} className="refresh-btn"><option value="">全部难度</option>{[...new Set(problems.map(problem => problem.difficulty).filter(Boolean))].map(value => <option key={value}>{value}</option>)}</select>
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
                <p>加载题目中...</p>
              </div>
            ) : problems.length === 0 ? (
              <div className="empty-state">
                <BookOpen size={64} />
                <h3>暂无题目</h3>
                <p>联系教师添加题目</p>
              </div>
            ) : (
              <div className="problems-grid">
                {filteredProblems.map((p) => {
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
