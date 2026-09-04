import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, BookOpen, BarChart3, Upload, LogOut, Bot, ChevronRight, GraduationCap, ListChecks } from 'lucide-react'
import { getAdminDashboard } from '../../api/index.js'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function TeacherDashboard() {
  const navigate = useNavigate()
  const { logout } = useAuth()
  const [stats, setStats] = useState({ total_students: 0, total_problems: 0, today_submissions: 0, avg_score: 0 })

  useEffect(() => {
    loadDashboard()
  }, [])

  const loadDashboard = async () => {
    try {
      const data = await getAdminDashboard()
      setStats(data)
    } catch (err) {
      console.error('Failed to load dashboard:', err)
    }
  }

  const handleLogout = async () => {
    try {
      await logout()
    } finally {
      navigate('/teacher-login')
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f5f7fa', fontFamily: '"Microsoft JhengHei", Arial, sans-serif' }}>
      {/* Header */}
      <header style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white', padding: '20px 0',
        boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <GraduationCap size={28} />
            <h1 style={{ fontSize: 24, fontWeight: 700 }}>教师管理后台</h1>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span style={{ background: 'rgba(255,255,255,0.2)', padding: '6px 14px', borderRadius: 20, fontSize: 13, fontWeight: 600 }}>
              教师账号
            </span>
            <button onClick={handleLogout} style={{
              background: 'rgba(255,255,255,0.15)', color: 'white',
              border: '2px solid rgba(255,255,255,0.3)',
              padding: '8px 18px', borderRadius: 6, cursor: 'pointer',
              fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <LogOut size={14} />
              退出
            </button>
          </div>
        </div>
      </header>

      <div style={{ maxWidth: 1200, margin: '30px auto', padding: '0 24px' }}>

        {/* Stats row */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 20, marginBottom: 36,
        }}>
          {[
            { label: '学生总数', value: stats.total_students, icon: Users, color: '#667eea' },
            { label: '题目总数', value: stats.total_problems, icon: BookOpen, color: '#11998e' },
            { label: '今日提交', value: stats.today_submissions, icon: Upload, color: '#f59e0b' },
            { label: '平均成绩', value: stats.avg_score ? `${stats.avg_score}%` : '—', icon: BarChart3, color: '#ef4444' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} style={{
              background: 'white', borderRadius: 12, padding: '24px',
              boxShadow: '0 3px 12px rgba(0,0,0,0.08)', textAlign: 'center',
            }}>
              <div style={{
                width: 48, height: 48, borderRadius: '50%', margin: '0 auto 14px',
                background: `${color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon size={22} color={color} />
              </div>
              <div style={{ fontSize: 32, fontWeight: 800, color: '#667eea', marginBottom: 4 }}>{value}</div>
              <div style={{ fontSize: 13, color: '#888' }}>{label}</div>
            </div>
          ))}
        </div>

        {/* Management cards */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: 24,
        }}>
          {[
            { label: 'AI课管理', desc: '题库·成绩统计', icon: Bot, color: '#667eea', path: '/teacher/ai' },
            { label: '信息课管理', desc: '题库·小测·成绩统计', icon: ListChecks, color: '#38ef7d', path: '/teacher/info' },
            { label: '学生管理', desc: '管理学生帐号', icon: Users, color: '#f59e0b', path: '/teacher/students' },
          ].map(({ label, desc, icon: Icon, color, path }) => (
            <button
              key={label}
              onClick={() => navigate(path)}
              style={{
                background: 'white', border: 'none', borderRadius: 16, padding: '28px',
                boxShadow: '0 4px 16px rgba(0,0,0,0.08)', cursor: 'pointer', textAlign: 'left',
                display: 'flex', flexDirection: 'column', gap: 14,
                transition: 'transform 0.2s, box-shadow 0.2s',
              }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.boxShadow = '0 10px 30px rgba(0,0,0,0.12)'; }}
              onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.08)'; }}
            >
              <div style={{
                width: 52, height: 52, borderRadius: '50%', display: 'flex',
                alignItems: 'center', justifyContent: 'center',
              }}>
                <div style={{
                  width: 52, height: 52, borderRadius: '50%', background: `${color}15`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Icon size={26} color={color} />
                </div>
              </div>
              <div>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#333', marginBottom: 6 }}>{label}</div>
                <div style={{ fontSize: 13, color: '#888', lineHeight: 1.5 }}>{desc}</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, color, fontSize: 13, fontWeight: 600, marginTop: 4 }}>
                进入管理 <ChevronRight size={14} />
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
