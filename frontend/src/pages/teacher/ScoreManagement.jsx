import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, BarChart3, RefreshCw } from 'lucide-react'
import { getAdminScores } from '../../api/index.js'

export default function ScoreManagement() {
  const navigate = useNavigate()
  const [scores, setScores] = useState([])
  const [problems, setProblems] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ grade: '', class_num: '', problem_id: '', course_type: 'ai' })
  const [stats, setStats] = useState({ total: 0, submitted: 0, avg: 0, problemCount: 0 })
  const [problemOptions, setProblemOptions] = useState([])

  const grades = ['七年级', '八年级', '九年级']
  const classOptions = Array.from({ length: 20 }, (_, i) => i + 1)

  useEffect(() => { loadScores() }, [])

  const loadScores = async () => {
    setLoading(true)
    try {
      const params = {}
      if (filters.grade) params.grade = filters.grade
      if (filters.class_num) params.class_num = filters.class_num
      if (filters.problem_id) params.problem_id = filters.problem_id
      if (filters.course_type) params.course_type = filters.course_type

      const token = localStorage.getItem('token')
      const qs = new URLSearchParams(params).toString()
      const res = await fetch(`http://localhost:8080/api/ai/admin/scores/${qs ? '?' + qs : ''}`, {
        headers: { 'Authorization': `Token ${token}`, 'Content-Type': 'application/json' }
      })
      if (res.ok) {
        const data = await res.json()
        // data.students: [{student_number, username, display_name, grade, class_num, best_score, scores: [{problem_id, score}]}]
        // data.problems: [{problem_id, title}]
        setScores(data.students || [])
        setProblems(data.problems || [])

        // 计算统计
        let total = (data.students || []).length
        let submitted = 0, sum = 0, count = 0
        ;(data.students || []).forEach(s => {
          s.scores.forEach(sc => {
            if (sc.submitted) { submitted++; sum += sc.score || 0; count++ }
          })
        })
        setStats({
          total,
          submitted,
          avg: count > 0 ? (sum / count).toFixed(1) : 0,
          problemCount: (data.problems || []).length,
        })
      }
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  useEffect(() => { loadScores() }, [filters])

  const loadProblems = async () => {
    const token = localStorage.getItem('token')
    if (filters.course_type === 'ai') {
      try {
        const res = await fetch(`http://localhost:8080/api/ai/admin/problems/`, {
          headers: { 'Authorization': `Token ${token}` }
        })
        if (res.ok) {
          const data = await res.json()
          setProblemOptions(data.results || data || [])
        }
      } catch (e) { setProblemOptions([]) }
    } else {
      // info_tech 题目模型建好后扩展这里
      setProblemOptions([])
    }
  }

  useEffect(() => {
    const interval = setInterval(loadScores, 5000)
    return () => clearInterval(interval)
  }, [filters])

  useEffect(() => { loadProblems() }, [filters.course_type])

  // 灯矩阵：学号1-50对应50个格子，格子N = 学号N的学生是否满分
  const ROWS = 5, COLS = 10
  // 建立学号->是否满分的映射
  const scoreMapByNum = {}
  ;(scores || []).forEach(s => {
    const num = parseInt(s.student_number) || 0
    if (num >= 1 && num <= ROWS * COLS) {
      scoreMapByNum[num] = Math.max(scoreMapByNum[num] || 0, s.best_score || 0)
    }
  })

  // 成绩颜色
  const scoreColor = (score) => {
    if (score === null || score === undefined) return { bg: '#f8f9fa', color: '#6c757d', text: '—' }
    if (score >= 90) return { bg: '#d4edda', color: '#155724', text: score }
    if (score >= 75) return { bg: '#d1ecf1', color: '#0c5460', text: score }
    if (score >= 60) return { bg: '#fff3cd', color: '#856404', text: score }
    return { bg: '#f8d7da', color: '#721c24', text: score }
  }

  const gradeColor = (g) => ({ '七年級': '#667eea', '七年级': '#667eea', '八年級': '#38ef7d', '八年级': '#38ef7d', '九年級': '#f59e0b', '九年级': '#f59e0b' }[g] || '#888')

  return (
    <div style={{ minHeight: '100vh', background: '#f5f7fa', fontFamily: '"Microsoft JhengHei", Arial, sans-serif' }}>
      <header style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white', padding: '16px 0', boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
      }}>
        <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <button onClick={() => navigate('/teacher/dashboard')} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(255,255,255,0.15)', border: 'none', borderRadius: 8,
            color: 'white', cursor: 'pointer', padding: '8px 14px', fontSize: 13, fontWeight: 600,
          }}>
            <ArrowLeft size={14} /> 返回主页
          </button>
          <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.25)' }} />
          <BarChart3 size={20} />
          <h1 style={{ fontSize: 20, fontWeight: 700 }}>成绩管理</h1>
        </div>
      </header>

      <main style={{ maxWidth: 1600, margin: '0 auto', padding: '32px 24px' }}>
        {/* 筛选 */}
        <div style={{
          background: 'white', borderRadius: 12, padding: '20px 24px', marginBottom: 24,
          boxShadow: '0 2px 10px rgba(0,0,0,0.06)', display: 'flex', gap: 16, alignItems: 'flex-end', flexWrap: 'wrap',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: '#888', fontWeight: 600 }}>年级</label>
            <select value={filters.grade} onChange={e => setFilters(f => ({ ...f, grade: e.target.value }))}
              style={{ padding: '9px 14px', borderRadius: 8, border: '1px solid #e0e0e0', background: '#fafafa', color: '#333', fontSize: 13, minWidth: 120 }}>
              <option value="">全部年级</option>
              {grades.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: '#888', fontWeight: 600 }}>班级</label>
            <select value={filters.class_num} onChange={e => setFilters(f => ({ ...f, class_num: e.target.value }))}
              style={{ padding: '9px 14px', borderRadius: 8, border: '1px solid #e0e0e0', background: '#fafafa', color: '#333', fontSize: 13, minWidth: 80 }}>
              <option value="">全部班级</option>
              {classOptions.map(c => <option key={c} value={String(c)}>{c}班</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: '#888', fontWeight: 600 }}>课程类型</label>
            <select value={filters.course_type} onChange={e => setFilters(f => ({ ...f, course_type: e.target.value }))}
              style={{ padding: '9px 14px', borderRadius: 8, border: '1px solid #e0e0e0', background: '#fafafa', color: '#333', fontSize: 13, minWidth: 140 }}>
              <option value="ai">人工智能课</option>
              <option value="info_tech">信息科技课</option>
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: '#888', fontWeight: 600 }}>题目</label>
            <select value={filters.problem_id} onChange={e => setFilters(f => ({ ...f, problem_id: e.target.value }))}
              style={{ padding: '9px 14px', borderRadius: 8, border: '1px solid #e0e0e0', background: '#fafafa', color: '#333', fontSize: 13, minWidth: 180 }}>
              <option value="">全部题目</option>
              {problemOptions.map(p => (
                <option key={p.problem_id} value={String(p.problem_id)}>
                  {p.title || `题目${p.problem_id}`}
                </option>
              ))}
            </select>
          </div>
          <button onClick={loadScores} style={{
            padding: '9px 20px', borderRadius: 8, border: 'none', cursor: 'pointer',
            background: '#28a745', color: '#fff', fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <RefreshCw size={14} /> 刷新
          </button>
        </div>

        {/* 统计栏 */}
        <div style={{
          background: '#e3f2fd', borderRadius: 12, padding: '16px 24px', marginBottom: 24,
          display: 'flex', gap: 40, flexWrap: 'wrap',
        }}>
          {[
            { label: '总学生数', value: stats.total, color: '#1976d2' },
            { label: '题目数', value: stats.problemCount, color: '#1976d2' },
            { label: '总提交数', value: stats.submitted, color: '#1976d2' },
            { label: '平均分', value: stats.avg, color: '#1976d2' },
            { label: '满分人数', value: Object.values(scoreMapByNum).filter(v => v === 100).length, color: '#2e7d32' },
          ].map(s => (
            <div key={s.label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 80 }}>
              <div style={{ fontSize: 24, fontWeight: 800, color: s.color }}>{s.value}</div>
              <div style={{ fontSize: 12, color: '#5a6c7d', marginTop: 4 }}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* 双栏：成绩表 + 灯矩阵 */}
        <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>

          {/* 成绩表格 */}
          <div style={{ flex: 1, minWidth: 0 }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>加载中...</div>
        ) : scores.length === 0 ? (
          <div style={{ background: 'white', borderRadius: 16, padding: '60px 24px', textAlign: 'center', boxShadow: '0 2px 10px rgba(0,0,0,0.06)', color: '#888' }}>
            <BarChart3 size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
            <p>暂无成绩记录</p>
          </div>
        ) : (
          <div style={{ background: 'white', borderRadius: 16, overflow: 'hidden', boxShadow: '0 2px 10px rgba(0,0,0,0.06)', overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 800 }}>
              <thead>
                <tr style={{ background: '#495057' }}>
                  <th style={{ padding: '12px 16px', color: 'white', textAlign: 'center', fontSize: 12, fontWeight: 600 }}>年级</th>
                  <th style={{ padding: '12px 16px', color: 'white', textAlign: 'center', fontSize: 12, fontWeight: 600 }}>班级</th>
                  <th style={{ padding: '12px 16px', color: 'white', textAlign: 'center', fontSize: 12, fontWeight: 600 }}>姓名</th>
                  <th style={{ padding: '12px 16px', color: 'white', textAlign: 'center', fontSize: 12, fontWeight: 600 }}>学号</th>
                  {(() => {
                    const visibleProblems = filters.problem_id
                      ? problems.filter(p => p.problem_id === filters.problem_id)
                      : problems
                    return visibleProblems.map(p => (
                      <th key={p.problem_id} style={{ padding: '12px 10px', color: 'white', textAlign: 'center', fontSize: 12, fontWeight: 600 }}>
                        {filters.problem_id && visibleProblems.length === 1
                          ? <span style={{ color: '#ffd700' }}>{p.title || `题目${p.problem_id}`}</span>
                          : (p.title || `题目${p.problem_id}`)}
                      </th>
                    ))
                  })()}
                  {(() => {
                    const visibleProblems = filters.problem_id
                      ? problems.filter(p => p.problem_id === filters.problem_id)
                      : problems
                    return visibleProblems.length === 0 && (
                      <th style={{ padding: '12px 16px', color: 'rgba(255,255,255,0.6)', textAlign: 'center', fontSize: 13 }}>暂无题目</th>
                    )
                  })()}
                </tr>
              </thead>
              <tbody>
                {scores.slice().sort((a, b) => (parseInt(a.student_number) || 0) - (parseInt(b.student_number) || 0)).map((student, i) => {
                  const visibleProblems = filters.problem_id
                    ? problems.filter(p => p.problem_id === filters.problem_id)
                    : problems
                  const scoreMap = {}
                  ;(student.scores || []).forEach(sc => { scoreMap[sc.problem_id] = sc })
                  const has100 = student.best_score === 100
                  return (
                    <tr key={student.id || i} style={{ background: has100 ? '#e8f5e9' : (i % 2 === 0 ? 'white' : '#f8f9fa'), transition: 'background 0.15s' }}
                      onMouseEnter={e => e.currentTarget.style.background = '#e8f0ff'}
                      onMouseLeave={e => e.currentTarget.style.background = has100 ? '#e8f5e9' : (i % 2 === 0 ? 'white' : '#f8f9fa')}
                    >
                      <td style={{ padding: '10px 16px', textAlign: 'center', borderBottom: '1px solid #e9ecef' }}>
                        <span style={{ background: `${gradeColor(student.grade)}18`, color: gradeColor(student.grade), padding: '2px 8px', borderRadius: 8, fontWeight: 700, fontSize: 12 }}>
                          {student.grade || '—'}
                        </span>
                      </td>
                      <td style={{ padding: '10px 16px', textAlign: 'center', borderBottom: '1px solid #e9ecef', fontSize: 13, color: '#666' }}>
                        {student.class_num ? `${student.class_num}班` : '—'}
                      </td>
                      <td style={{ padding: '10px 16px', textAlign: 'center', borderBottom: '1px solid #e9ecef', fontSize: 14, color: '#333', fontWeight: 600 }}>
                        {student.display_name || student.username || '—'}
                      </td>
                      <td style={{ padding: '10px 16px', textAlign: 'center', borderBottom: '1px solid #e9ecef', fontSize: 13, color: '#666', fontFamily: 'monospace' }}>
                        {student.student_number || '—'}
                      </td>
                      {visibleProblems.map(p => {
                        const sc = scoreMap[p.problem_id]
                        const info = scoreColor(sc?.score ?? null)
                        return (
                          <td key={p.problem_id} style={{
                            padding: '10px 10px', textAlign: 'center', borderBottom: '1px solid #e9ecef',
                            background: info.bg, color: info.color, fontWeight: 700, fontSize: 14,
                          }}>
                            {info.text}
                          </td>
                        )
                      })}
                      {visibleProblems.length === 0 && (
                        <td style={{ padding: '10px 16px', textAlign: 'center', color: '#aaa', fontStyle: 'italic', borderBottom: '1px solid #e9ecef' }}>—</td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* 图例 */}
        <div style={{ marginTop: 16, display: 'flex', gap: 20, flexWrap: 'wrap', fontSize: 12, color: '#666' }}>
          <span>图例：</span>
          {[
            { bg: '#d4edda', color: '#155724', label: '优秀 (≥90)' },
            { bg: '#d1ecf1', color: '#0c5460', label: '良好 (75-89)' },
            { bg: '#fff3cd', color: '#856404', label: '及格 (60-74)' },
            { bg: '#f8d7da', color: '#721c24', label: '不及格 (<60)' },
            { bg: '#f8f9fa', color: '#6c757d', label: '未提交' },
          ].map(l => (
            <span key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 14, height: 14, borderRadius: 3, background: l.bg, border: `1px solid ${l.color}40`, display: 'inline-block' }}></span>
              <span style={{ color: l.color }}>{l.label}</span>
            </span>
          ))}
        </div>
          </div>

          {/* 灯矩阵 */}
          <div style={{
            background: 'white', borderRadius: 16, padding: '20px', boxShadow: '0 2px 10px rgba(0,0,0,0.08)',
            display: 'flex', flexDirection: 'column', gap: 12, minWidth: 360,
          }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#333', textAlign: 'center' }}>满分监控 · 学号1-50</div>
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${COLS}, 1fr)`, gap: 5 }}>
              {Array.from({ length: ROWS * COLS }, (_, idx) => {
                const lampNum = idx + 1
                const is100 = (scoreMapByNum[lampNum] || 0) === 100
                const lampColor = is100 ? '#4caf50' : '#2a2a2a'
                return (
                  <div key={idx} title={`学号${lampNum} ${is100 ? '✓ 满分' : '未满分'}`}
                    style={{
                      width: 30, height: 30, borderRadius: 5,
                      background: lampColor,
                      boxShadow: is100 ? '0 0 8px #4caf50' : 'inset 0 1px 3px rgba(0,0,0,0.5)',
                      border: `1px solid ${is100 ? '#81c784' : '#444'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 11, fontWeight: 700,
                      color: is100 ? '#fff' : '#555',
                      cursor: 'default',
                      transition: 'background 0.3s, box-shadow 0.3s',
                    }}
                  >{lampNum}</div>
                )
              })}
            </div>
            <div style={{ fontSize: 11, color: '#888', textAlign: 'center' }}>
              {Object.values(scoreMapByNum).filter(v => v === 100).length}/{ROWS * COLS} 满分 / 5×10矩阵
            </div>
          </div>

        </div>
      </main>
    </div>
  )
}
