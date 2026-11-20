import { Link, useNavigate } from 'react-router-dom'
import { Brain, Keyboard, Monitor } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getCurrentUser, getToken } from '../../api/index.js'
import { typingApi } from '../../api/typing.js'
import Navbar from '../../components/Navbar.jsx'
import './CourseSelect.css'

function CourseCard({ name, title, icon: Icon, to, onClick, children, footer }) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className={`course-card course-card--${name}`}
      aria-labelledby={`course-title-${name}`}
    >
      <Icon size={58} aria-hidden="true" />
      <h2 id={`course-title-${name}`}>{title}</h2>
      <p>{children}</p>
      <div className="course-card-footer">{footer}</div>
    </Link>
  )
}

function TypingBests({ scores, status }) {
  const display = language => {
    if (status === 'loading') return '载入中'
    if (status === 'error') return '暂不可用'
    const score = scores?.[language]
    return score == null ? '暂无成绩' : `${score} 分`
  }

  return (
    <dl className="course-card-bests" aria-busy={status === 'loading'}>
      <div><dt>中文最佳成绩</dt><dd>{display('zh')}</dd></div>
      <div><dt>英文最佳成绩</dt><dd>{display('en')}</dd></div>
    </dl>
  )
}

export default function CourseSelect() {
  const navigate = useNavigate()
  const [user, setUser] = useState(() => getCurrentUser() || {})
  const [scores, setScores] = useState(null)
  const [scoreStatus, setScoreStatus] = useState('loading')

  useEffect(() => {
    let controller

    function load() {
      controller?.abort()
      const activeUser = getCurrentUser() || {}
      if (!localStorage.getItem('user') || (!activeUser.username && !activeUser.display_name)) {
        navigate('/login')
        return
      }
      setUser(activeUser)
      setScores(null)
      if (!getToken()) {
        setScoreStatus('ready')
        return
      }
      setScoreStatus('loading')
      controller = new AbortController()
      const { signal } = controller
      typingApi.bests(signal)
        .then(data => {
          if (signal.aborted) return
          setScores(data)
          setScoreStatus('ready')
        })
        .catch(() => { if (!signal.aborted) setScoreStatus('error') })
    }

    function updateSession(event) {
      if (event.key === 'user' || event.key === 'token' || event.key === null) load()
    }
    function restorePage(event) {
      if (event.persisted) load()
    }

    load()
    window.addEventListener('storage', updateSession)
    window.addEventListener('pageshow', restorePage)
    return () => {
      controller?.abort()
      window.removeEventListener('storage', updateSession)
      window.removeEventListener('pageshow', restorePage)
    }
  }, [navigate])

  const username = user.display_name || user.username || ''
  return (
    <div className="page-bg">
      <Navbar username={username} grade={user.grade || ''} class_num={user.class_num || ''} />
      <main className="main-content">
        <div className="welcome-section">
          <h1>欢迎回来，{username}！</h1>
          <p>请选择你要进入的课程</p>
        </div>

        <div className="course-card-grid">
          <CourseCard name="ai" title="人工智能课" icon={Brain}
            to="/student/dashboard?course=ai" onClick={() => localStorage.setItem('selected_course', 'ai')}
            footer="授课教师：Alex">
            Python 编程学习<br />透过代码挑战提升演算法思维
          </CourseCard>
          <CourseCard name="info" title="信息科技课" icon={Monitor}
            to="/student/dashboard?course=info" onClick={() => localStorage.setItem('selected_course', 'info')}
            footer="授课教师：Alex">
            在线测验学习<br />选择题与综合题强化资讯素养
          </CourseCard>
          <CourseCard name="typing" title="打字训练" icon={Keyboard} to="/student/typing"
            footer={<TypingBests scores={scores} status={scoreStatus} />}>
            中英文打字登山<br />每次练习 5 分钟
          </CourseCard>
        </div>
      </main>
    </div>
  )
}
