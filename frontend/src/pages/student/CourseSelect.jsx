import { Link, useNavigate } from 'react-router-dom'
import { Brain, Keyboard, Monitor } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { getCurrentUser, getToken } from '../../api/index.js'
import { getMyPoints, getPointsLeaderboard } from '../../api/points.js'
import { typingApi } from '../../api/typing.js'
import Navbar from '../../components/Navbar.jsx'
import PointsBoard from '../../components/PointsBoard.jsx'
import PointsCard from '../../components/PointsCard.jsx'
import TitleLadder from '../../components/TitleLadder.jsx'
import './CourseSelect.css'

const POINTS_POLL_MS = 20000

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
  const [points, setPoints] = useState(null)
  const [pointsLoading, setPointsLoading] = useState(true)
  const [board, setBoard] = useState(null)
  const [boardUpdatedAt, setBoardUpdatedAt] = useState('')
  const [ladderOpen, setLadderOpen] = useState(false)
  const [ladderFocus, setLadderFocus] = useState(null)

  // 点风云榜里某人的称号，打开天梯图并高亮他的段位
  const openLadder = useCallback(entry => {
    const title = entry?.title
    setLadderFocus(title ? { level: title.level, label: entry.label } : null)
    setLadderOpen(true)
  }, [])
  const closeLadder = useCallback(() => setLadderOpen(false), [])

  // 积分与风云榜：一登录就能看到余额、境界和班级排名。
  // 两个接口各自容错——任一失败只是不显示对应部分，不影响选课本身。
  const loadPoints = useCallback(async signal => {
    if (!getToken()) {
      setPointsLoading(false)
      return
    }
    setPointsLoading(true)
    const [me, boardData] = await Promise.all([
      getMyPoints().catch(() => null),
      getPointsLeaderboard().catch(() => null),
    ])
    if (signal?.aborted) return
    if (me) setPoints(me)
    if (boardData) {
      setBoard(boardData)
      setBoardUpdatedAt(new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }))
    }
    setPointsLoading(false)
  }, [])

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
      controller = new AbortController()
      const { signal } = controller
      loadPoints(signal)
      if (!getToken()) {
        setScoreStatus('ready')
        return
      }
      setScoreStatus('loading')
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
  }, [navigate, loadPoints])

  // 风云榜 20 秒轮询；切回标签页立即刷新（与仪表盘一致）
  useEffect(() => {
    const timer = setInterval(() => loadPoints(), POINTS_POLL_MS)
    const onVisible = () => {
      if (document.visibilityState === 'visible') loadPoints()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [loadPoints])

  const username = user.display_name || user.username || ''
  return (
    <div className="page-bg">
      <Navbar username={username} grade={user.grade || ''} class_num={user.class_num || ''} />
      <main className="main-content">
        <div className="welcome-section">
          <h1>欢迎回来，{username}！</h1>
          <p>请选择你要进入的课程</p>
        </div>

        {/* 与仪表盘同一套积分卡：余额、境界（可点开天梯）、排名、累计与消耗 */}
        <PointsCard
          data={points}
          loading={pointsLoading}
          onOpenLadder={() => openLadder(null)}
        />

        <div className="select-layout">
          <div className="select-main">
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
                中英文打字登山<br />每次最长 5 分钟
              </CourseCard>
            </div>
          </div>

          <aside className="select-aside">
            <PointsBoard
              data={board}
              loading={pointsLoading}
              onRefresh={() => loadPoints()}
              updatedAt={boardUpdatedAt}
              onOpenTitle={openLadder}
            />
          </aside>
        </div>

        <TitleLadder
          open={ladderOpen}
          onClose={closeLadder}
          ladder={points?.ladder || []}
          title={points?.title || null}
          focus={ladderFocus}
          split={points ? { typing: points.typing_total, quiz: points.quiz_total } : null}
          paths={points?.paths || []}
        />
      </main>
    </div>
  )
}
