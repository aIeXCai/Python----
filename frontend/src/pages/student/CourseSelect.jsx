import { useNavigate } from 'react-router-dom'
import { Brain, Monitor } from 'lucide-react'
import Navbar from '../../components/Navbar.jsx'
import { useEffect, useState } from 'react'

export default function CourseSelect() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [grade, setGrade] = useState('')
  const [classNum, setClassNum] = useState('')
  useEffect(() => {
    const raw = localStorage.getItem('user')
    if (!raw) { navigate('/login'); return }
    try {
      const u = JSON.parse(raw)
      setUsername(u.display_name || u.username || '')
      setGrade(u.grade || '')
      setClassNum(u.class_num || '')
    } catch { navigate('/login') }
  }, [])

  const selectCourse = (course) => {
    // 同步写入 localStorage，确保 StudentDashboard 能读到
    localStorage.setItem('selected_course', course)
    // 带着当前课程参数导航，下次进来就知道在哪个课
    navigate(`/student/dashboard?course=${course}`)
  }

  return (
    <div className="page-bg">
      <Navbar username={username} grade={grade} class_num={classNum} />

      <main className="main-content">
        <div className="welcome-section">
          <h1>欢迎回来，{username}！</h1>
          <p>请选择你要进入的课程</p>
        </div>

        <div style={{ display: 'flex', gap: '24px', justifyContent: 'center', flexWrap: 'wrap', marginTop: '32px' }}>
          {/* AI课 */}
          <div
            className="course-card"
            onClick={() => selectCourse('ai')}
            style={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              borderRadius: '16px',
              padding: '40px 32px',
              color: '#fff',
              cursor: 'pointer',
              minWidth: '280px',
              textAlign: 'center',
              boxShadow: '0 8px 32px rgba(102, 126, 234, 0.3)',
              transition: 'transform 0.2s, box-shadow 0.2s',
            }}
          >
            <Brain size={64} style={{ marginBottom: '16px' }} />
            <h2 style={{ fontSize: '1.5rem', marginBottom: '12px' }}>人工智能课</h2>
            <p style={{ opacity: 0.9, fontSize: '0.95rem', lineHeight: 1.6 }}>
              Python 编程学习<br />透过代码挑战提升演算法思维
            </p>
            <div style={{
              marginTop: '20px',
              background: 'rgba(255,255,255,0.2)',
              borderRadius: '8px',
              padding: '10px',
              fontSize: '0.85rem',
            }}>
              授课教师：Alex
            </div>
          </div>

          {/* 信息课 */}
          <div
            className="course-card"
            onClick={() => selectCourse('info')}
            style={{
              background: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
              borderRadius: '16px',
              padding: '40px 32px',
              color: '#fff',
              cursor: 'pointer',
              minWidth: '280px',
              textAlign: 'center',
              boxShadow: '0 8px 32px rgba(17, 153, 142, 0.3)',
              transition: 'transform 0.2s, box-shadow 0.2s',
            }}
          >
            <Monitor size={64} style={{ marginBottom: '16px' }} />
            <h2 style={{ fontSize: '1.5rem', marginBottom: '12px' }}>信息科技课</h2>
            <p style={{ opacity: 0.9, fontSize: '0.95rem', lineHeight: 1.6 }}>
              在线测验学习<br />选择题与综合题强化资讯素养
            </p>
            <div style={{
              marginTop: '20px',
              background: 'rgba(255,255,255,0.2)',
              borderRadius: '8px',
              padding: '10px',
              fontSize: '0.85rem',
            }}>
              授课教师：Alex
            </div>
          </div>
        </div>
      </main>

      <style>{`
        .course-card:hover {
          transform: translateY(-4px) !important;
          box-shadow: 0 12px 40px rgba(0,0,0,0.2) !important;
        }
      `}</style>
    </div>
  )
}
