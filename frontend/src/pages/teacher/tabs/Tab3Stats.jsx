import { useEffect } from 'react'
import { BarChart2, Users, CheckCircle, RefreshCw, X } from 'lucide-react'
import { API_BASE_URL } from '../../../api/config.js'
import { GRADES } from '../../../constants/grades.js'

export default function Tab3Stats({
  statsData, statsLoading, statsFilter,
  setStatsFilter,
  selectedQuiz, setSelectedQuiz,
  autoRefresh, setAutoRefresh,
  loadStats,
  gradeDisplay, scoreColor,
}) {
  // 自动刷新：依赖 loadStats，保证筛选/所选小测变化后定时器使用最新的筛选条件
  useEffect(() => {
    if (!autoRefresh) return
    const timer = setInterval(loadStats, 5000)
    return () => clearInterval(timer)
  }, [autoRefresh, loadStats])

  // 选定小测变化时重新加载
  useEffect(() => {
    loadStats()
  }, [selectedQuiz])

  const ROWS = 5, COLS = 10
  // 班级范围与全平台一致（注册/学生管理/AI成绩均为 1-20）
  const CLASS_OPTIONS = Array.from({ length: 20 }, (_, i) => String(i + 1))

  // 从 statsData 构建学号→分数映射
  const scoreMapByNum = {}
  ;(statsData?.students || []).forEach(stu => {
    const num = parseInt(stu.student_number) || 0
    if (num >= 1 && num <= ROWS * COLS) {
      // 用该学生第一次小测成绩
      const sc = stu.scores?.[0] ?? null
      if (sc != null) scoreMapByNum[num] = sc
    }
  })
  // 达标（≥80）人数统计
  const passCount = Object.values(scoreMapByNum).filter(v => v >= 80).length

  const handleReset = async (student) => {
    if (!selectedQuiz) return
    const reason = window.prompt(`请输入重置 ${student.display_name || student.username} 本次作答的原因：`)
    if (!reason?.trim()) return
    if (!window.confirm('重置后旧成绩会保留为审计历史，学生可重新开始。确定继续吗？')) return
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/admin/info/sessions/${selectedQuiz}/students/${student.user_id}/reset/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
      body: JSON.stringify({ reason: reason.trim() }),
    })
    const data = await response.json()
    if (!response.ok) {
      window.alert(data.error || '重置失败')
      return
    }
    loadStats()
  }

  return (
    <div style={{ display: 'flex', gap: 24, height: 'calc(100vh - 200px)', minHeight: 500 }}>

      {/* 左侧：成绩表格 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16, overflow: 'hidden' }}>
        {/* 筛选栏 */}
        <div style={{
          background: 'white', borderRadius: 14, padding: '14px 20px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap'
        }}>
          <BarChart2 size={18} style={{ color: '#667eea' }} />
          <span style={{ fontSize: 15, fontWeight: 700, color: '#333' }}>成绩统计</span>
          <span style={{ fontSize: 12, color: '#888' }}>
            {statsData?.students?.length || 0} 人 · {statsData?.sessions?.length || 0} 场小测
          </span>

          <select value={statsFilter.grade} onChange={e => {
            setStatsFilter(p => ({ ...p, grade: e.target.value }))
            setSelectedQuiz('')
          }} style={{ padding: '6px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, minWidth: 90 }}>
            {GRADES.map(g => <option key={g} value={g}>{gradeDisplay(g)}</option>)}
          </select>

          <select value={statsFilter.class_num} onChange={e => setStatsFilter(p => ({ ...p, class_num: e.target.value }))}
            style={{ padding: '6px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, minWidth: 80 }}>
            <option value="">全部班级</option>
            {CLASS_OPTIONS.map(c => <option key={c} value={c}>{c}班</option>)}
          </select>

          <select value={selectedQuiz} onChange={e => setSelectedQuiz(e.target.value)}
            style={{ padding: '6px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, minWidth: 140 }}>
            <option value="">全部小测</option>
            {(statsData?.sessions || []).map(s => (
              <option key={s.id} value={String(s.id)}>{s.title || `小测#${s.id}`}</option>
            ))}
          </select>

          <label style={{ display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer', fontSize: 13, color: '#555', marginLeft: 4 }}>
            <input type="checkbox" checked={autoRefresh} onChange={e => {
              setAutoRefresh(e.target.checked)
              if (e.target.checked) loadStats()
            }} />
            <RefreshCw size={13} style={{ color: autoRefresh ? '#667eea' : '#ccc' }} />
            5秒刷新
          </label>

          <button onClick={loadStats} style={{
            marginLeft: 'auto', padding: '6px 14px', borderRadius: 8, border: '1.5px solid #667eea',
            background: 'white', color: '#667eea', cursor: 'pointer', fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 5
          }}>
            <RefreshCw size={13} /> 刷新
          </button>
        </div>

        {/* 成绩表格 */}
        <div style={{ flex: 1, background: 'white', borderRadius: 14, overflow: 'auto', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          {statsLoading ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>加载中...</div>
          ) : statsData?.students?.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
              <Users size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
              <p>暂无成绩数据</p>
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 500 }}>
              <thead>
                <tr style={{ background: '#f8f9fa', position: 'sticky', top: 0, zIndex: 1 }}>
                  <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 700, color: '#666', whiteSpace: 'nowrap', borderBottom: '2px solid #e0e0e0' }}>年级</th>
                  <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 700, color: '#666', whiteSpace: 'nowrap', borderBottom: '2px solid #e0e0e0' }}>班级</th>
                  <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 700, color: '#666', whiteSpace: 'nowrap', borderBottom: '2px solid #e0e0e0' }}>姓名</th>
                  <th style={{ padding: '10px 14px', textAlign: 'center', fontWeight: 700, color: '#666', whiteSpace: 'nowrap', borderBottom: '2px solid #e0e0e0' }}>学号</th>
                  {selectedQuiz ? (
                    <>
                      <th style={{ padding: '10px 14px', textAlign: 'center', fontWeight: 700, color: '#667eea', whiteSpace: 'nowrap', borderBottom: '2px solid #e0e0e0' }}>成绩</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center', fontWeight: 700, color: '#666', whiteSpace: 'nowrap', borderBottom: '2px solid #e0e0e0' }}>操作</th>
                    </>
                  ) : (
                    (statsData?.sessions || []).map(s => (
                      <th key={s.id} style={{
                        padding: '10px 8px', textAlign: 'center', fontWeight: 700, fontSize: 11,
                        color: s.is_visible ? '#38ef7d' : '#666', whiteSpace: 'nowrap', borderBottom: '2px solid #e0e0e0',
                        borderLeft: '1px solid #f0f0f0'
                      }}>
                        {(s.title || '').length > 10 ? s.title.slice(0, 9) + '…' : s.title}
                      </th>
                    ))
                  )}
                </tr>
              </thead>
              <tbody>
                {(statsData?.students || []).map(stu => {
                  const selectedIdx = selectedQuiz ? (statsData?.sessions?.findIndex(ss => String(ss.id) === String(selectedQuiz)) ?? -1) : -1
                  const selectedScore = selectedIdx >= 0 ? (stu.scores?.[selectedIdx] ?? null) : null
                  return (
                  <tr key={stu.user_id} style={{ borderBottom: '1px solid #f5f5f5' }}
                    onMouseEnter={e => e.currentTarget.style.background = '#f8f9fa'}
                    onMouseLeave={e => e.currentTarget.style.background = 'white'}>
                    <td style={{ padding: '9px 14px', color: '#888', fontSize: 12, whiteSpace: 'nowrap' }}>{gradeDisplay(stu.grade)}</td>
                    <td style={{ padding: '9px 14px', color: '#888', fontSize: 12, whiteSpace: 'nowrap' }}>{stu.class_num}班</td>
                    <td style={{ padding: '9px 14px', fontWeight: 700, color: '#333', whiteSpace: 'nowrap' }}>{stu.display_name || stu.username}</td>
                    <td style={{ padding: '9px 14px', color: '#888', fontSize: 12, whiteSpace: 'nowrap', textAlign: 'center' }}>{stu.student_number ?? '—'}</td>
                    {selectedQuiz ? (
                      <>
                        <td style={{
                          padding: '9px 14px', textAlign: 'center', fontWeight: 800, fontSize: 14,
                          color: selectedScore != null ? scoreColor(selectedScore) : '#ccc', whiteSpace: 'nowrap'
                        }}>
                          {selectedScore != null ? selectedScore : '—'}
                        </td>
                        <td style={{ padding: '9px 14px', textAlign: 'center' }}>
                          {selectedScore != null && <button type="button" onClick={() => handleReset(stu)} style={{ border: '1px solid #f59e0b', background: '#fff', color: '#b45309', borderRadius: 6, padding: '3px 8px', cursor: 'pointer' }}>重置作答</button>}
                        </td>
                      </>
                    ) : (
                      (statsData?.sessions || []).map(s => {
                        const idx = statsData?.sessions?.findIndex(ss => String(ss.id) === String(s.id))
                        const sc = idx >= 0 ? (stu.scores?.[idx] ?? null) : null
                        return (
                          <td key={s.id} style={{
                            padding: '9px 8px', textAlign: 'center', fontWeight: 800, fontSize: 13,
                            color: sc != null ? scoreColor(sc) : '#ccc',
                            borderLeft: '1px solid #f0f0f0', whiteSpace: 'nowrap'
                          }}>
                            {sc != null ? sc : '—'}
                          </td>
                        )
                      })
                    )}
                  </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* 右侧：达标灯矩阵（≥80 亮灯） */}
      <div style={{
        minWidth: 360, maxWidth: 440,
        background: 'white', borderRadius: 14, padding: '18px 20px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.08)', display: 'flex', flexDirection: 'column', gap: 10,
        height: 'fit-content', maxHeight: '100%', overflow: 'hidden'
      }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#333', textAlign: 'center' }}>达标监控 · 学号1-50（≥80 亮灯）</div>
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${COLS}, 1fr)`, gap: 5 }}>
          {Array.from({ length: ROWS * COLS }, (_, idx) => {
            const lampNum = idx + 1
            const isLit = (scoreMapByNum[lampNum] || 0) >= 80
            return (
              <div key={idx} title={`学号${lampNum} ${isLit ? '✓ ≥80 达标' : '未达标（<80）'}`}
                style={{
                  width: 28, height: 28, borderRadius: 5,
                  background: isLit ? '#4caf50' : '#2a2a2a',
                  boxShadow: isLit ? '0 0 8px #4caf50' : 'inset 0 1px 3px rgba(0,0,0,0.5)',
                  border: `1px solid ${isLit ? '#81c784' : '#444'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, fontWeight: 700,
                  color: isLit ? '#fff' : '#555',
                  transition: 'background 0.3s, box-shadow 0.3s',
                }}>
                {lampNum}
              </div>
            )
          })}
        </div>
        <div style={{ fontSize: 11, color: '#888', textAlign: 'center' }}>
          {passCount}/{ROWS * COLS} 达标
        </div>
      </div>
    </div>
  )
}
