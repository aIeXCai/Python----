import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, RefreshCw, ArrowLeft, Bot, Eye, Trash2, Upload, X } from 'lucide-react'

const API = 'http://localhost:8080/api'
const difficultyColors = { '简单': '#38ef7d', '中等': '#f59e0b', '困难': '#ef4444', '入门': '#38ef7d', '进阶': '#f59e0b', '高级': '#ef4444' }

export default function ProblemManagement() {
  const navigate = useNavigate()
  const [problems, setProblems] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)

  // 详情弹窗
  const [detailModal, setDetailModal] = useState({ open: false, problem: null })
  const [detailLoading, setDetailLoading] = useState(false)

  // 上传表单
  const [uploadForm, setUploadForm] = useState({ problem_id: '', descriptionFile: null, testFiles: [] })
  const [uploadMsg, setUploadMsg] = useState({ type: '', text: '' })
  const [uploading, setUploading] = useState(false)

  const token = localStorage.getItem('token')
  const headers = { 'Authorization': `Token ${token}` }

  useEffect(() => { loadProblems() }, [])

  const loadProblems = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API}/ai/admin/problems/`, { headers })
      if (res.ok) setProblems(await res.json())
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  const syncFromDisk = async () => {
    setSyncing(true)
    try {
      const res = await fetch(`${API}/ai/admin/problems/`, { method: 'POST', headers })
      if (res.ok) {
        const data = await res.json()
        setUploadMsg({ type: 'success', text: `同步完成！新增 ${data.created} 题，更新 ${data.updated} 题` })
        loadProblems()
      }
    } catch (e) { setUploadMsg({ type: 'error', text: '同步失败：' + e.message }) }
    setSyncing(false)
    setTimeout(() => setUploadMsg({ type: '', text: '' }), 5000)
  }

  // 查看题目详情
  const viewProblem = async (problemId) => {
    setDetailLoading(true)
    setDetailModal({ open: true, problem: null })
    try {
      const res = await fetch(`${API}/ai/admin/problems/${problemId}/`, { headers })
      if (res.ok) setDetailModal({ open: true, problem: await res.json() })
    } catch (e) { console.error(e) }
    setDetailLoading(false)
  }

  // 删除题目
  const deleteProblem = (problem) => {
    if (!window.confirm(`确定删除题目「${problem.title}」吗？此操作不可撤销。`)) return
    fetch(`${API}/ai/admin/problems/${problem.problem_id}/`, { method: 'DELETE', headers })
      .then(res => {
        if (res.ok || res.status === 204) {
          setProblems(prev => prev.filter(p => p.problem_id !== problem.problem_id))
          setUploadMsg({ type: 'success', text: `题目「${problem.title}」已删除` })
          setTimeout(() => setUploadMsg({ type: '', text: '' }), 3000)
        } else { alert('删除失败') }
      })
      .catch(e => alert('删除失败：' + e.message))
  }

  // 上传题目（通过 Django admin sync_from_disk，problem_id 已在文件目录中）
  const handleUpload = async (e) => {
    e.preventDefault()
    setUploading(true)
    setUploadMsg({ type: '', text: '' })
    // 上传新题目的实际流程：由老师将题目光盘/文件放到磁盘目录，然后点"从磁盘同步"
    // 这里简单处理：只是调用同步接口
    try {
      const res = await fetch(`${API}/ai/admin/problems/`, { method: 'POST', headers })
      const data = await res.json()
      if (res.ok) {
        setUploadMsg({ type: 'success', text: `同步成功！新增 ${data.created} 题，更新 ${data.updated} 题` })
        loadProblems()
      } else { setUploadMsg({ type: 'error', text: JSON.stringify(data) }) }
    } catch (e) { setUploadMsg({ type: 'error', text: '同步失败：' + e.message }) }
    setUploading(false)
    setTimeout(() => setUploadMsg({ type: '', text: '' }), 5000)
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f5f7fa', fontFamily: '"Microsoft JhengHei", Arial, sans-serif' }}>
      {/* Header */}
      <header style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white', padding: '16px 0', boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <button onClick={() => navigate('/teacher/dashboard')} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(255,255,255,0.15)', border: 'none', borderRadius: 8,
            color: 'white', cursor: 'pointer', padding: '8px 14px', fontSize: 13, fontWeight: 600,
          }}>
            <ArrowLeft size={14} /> 返回主页
          </button>
          <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.25)' }} />
          <BookOpen size={20} />
          <h1 style={{ fontSize: 20, fontWeight: 700 }}>AI课题目管理</h1>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 24px' }}>

        {/* 操作栏 */}
        <div style={{ display: 'flex', marginBottom: 24 }}>
          <button onClick={syncFromDisk} disabled={syncing} style={{
            padding: '10px 20px', borderRadius: 10, border: 'none', cursor: syncing ? 'not-allowed' : 'pointer',
            background: syncing ? '#ccc' : '#45b7d1', color: 'white', fontWeight: 700, fontSize: 14,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <RefreshCw size={14} className={syncing ? 'spin' : ''} />
            {syncing ? '同步中...' : '从磁盘同步题目'}
          </button>
        </div>

        {/* 消息提示 */}
        {uploadMsg.text && (
          <div style={{
            padding: '12px 18px', borderRadius: 10, marginBottom: 20, fontSize: 14, fontWeight: 600,
            background: uploadMsg.type === 'success' ? '#d4edda' : '#f8d7da',
            color: uploadMsg.type === 'success' ? '#155724' : '#721c24',
            border: `1px solid ${uploadMsg.type === 'success' ? '#c3e6cb' : '#f5c6cb'}`,
          }}>
            {uploadMsg.text}
          </div>
        )}

        {/* 题目列表 */}
        <div style={{ background: 'white', borderRadius: 16, overflow: 'hidden', boxShadow: '0 2px 10px rgba(0,0,0,0.06)', marginBottom: 32 }}>
          <div style={{ padding: '18px 24px', borderBottom: '2px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: 8 }}>
            <BookOpen size={18} style={{ color: '#667eea' }} />
            <span style={{ fontSize: 16, fontWeight: 700, color: '#333' }}>现有题目列表</span>
            <span style={{ marginLeft: 'auto', fontSize: 13, color: '#888' }}>共 {problems.length} 题</span>
          </div>

          {loading ? (
            <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>加载中...</div>
          ) : problems.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>
              <BookOpen size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
              <p>暂无题目，点击「从磁盘同步题目」导入</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16, padding: 20 }}>
              {problems.map((p, i) => (
                <div key={p.problem_id || i} style={{
                  border: '2px solid #e9ecef', borderRadius: 12, padding: 16, transition: 'all 0.2s',
                  background: 'white',
                }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = '#667eea'; e.currentTarget.style.background = '#f8f9ff' }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = '#e9ecef'; e.currentTarget.style.background = 'white' }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 10 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: '#333', marginBottom: 4 }}>
                        {p.title || `题目${p.problem_id}`}
                      </div>
                      <div style={{ fontSize: 11, color: '#888' }}>编号：{p.problem_id} · 测试点：{p.test_count}</div>
                    </div>
                    <span style={{
                      padding: '3px 8px', borderRadius: 8, fontSize: 11, fontWeight: 800,
                      background: `${difficultyColors[p.difficulty] || '#888'}18`,
                      color: difficultyColors[p.difficulty] || '#888',
                    }}>{p.difficulty || '—'}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button onClick={() => viewProblem(p.problem_id)} style={{
                      flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
                      padding: '7px 0', borderRadius: 8, border: 'none', cursor: 'pointer',
                      background: '#17a2b8', color: 'white', fontSize: 12, fontWeight: 600,
                    }}>
                      <Eye size={12} /> 查看
                    </button>
                    <button onClick={() => deleteProblem(p)} style={{
                      flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
                      padding: '7px 0', borderRadius: 8, border: 'none', cursor: 'pointer',
                      background: '#dc3545', color: 'white', fontSize: 12, fontWeight: 600,
                    }}>
                      <Trash2 size={12} /> 删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 上传说明 */}
        <div style={{
          background: 'white', borderRadius: 16, padding: '24px', boxShadow: '0 2px 10px rgba(0,0,0,0.06)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <Upload size={18} style={{ color: '#667eea' }} />
            <span style={{ fontSize: 16, fontWeight: 700, color: '#333' }}>上传新题目</span>
          </div>
          <div style={{ background: '#f0f4ff', borderRadius: 10, padding: '16px 20px', marginBottom: 20, fontSize: 13, color: '#555', lineHeight: 1.8 }}>
            <strong>上传流程：</strong>将题目文件夹放入后端 <code style={{ background: '#e0e0e0', padding: '1px 5px', borderRadius: 3 }}>backend/problems/</code> 目录（包含 <code>description.txt</code> 和测试点文件），然后点击「从磁盘同步题目」即可。
          </div>
          <button onClick={handleUpload} disabled={uploading} style={{
            padding: '12px 28px', borderRadius: 10, border: 'none', cursor: uploading ? 'not-allowed' : 'pointer',
            background: uploading ? '#ccc' : '#667eea', color: 'white', fontWeight: 700, fontSize: 14,
          }}>
            {uploading ? '同步中...' : '📂 从磁盘同步题目'}
          </button>
        </div>
      </main>

      {/* 题目详情弹窗 */}
      {detailModal.open && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px',
        }} onClick={() => setDetailModal({ open: false, problem: null })}>
          <div style={{
            background: 'white', borderRadius: 16, padding: '32px', maxWidth: 600, width: '100%',
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)', maxHeight: '80vh', overflowY: 'auto',
          }} onClick={e => e.stopPropagation()}>
            {detailLoading ? (
              <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>加载中...</div>
            ) : detailModal.problem ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
                  <div>
                    <h2 style={{ fontSize: 18, fontWeight: 700, color: '#333', margin: 0 }}>{detailModal.problem.title}</h2>
                    <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                      编号 {detailModal.problem.problem_id} · {detailModal.problem.difficulty}
                    </div>
                  </div>
                  <button onClick={() => setDetailModal({ open: false, problem: null })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888', padding: 4 }}>
                    <X size={20} />
                  </button>
                </div>
                <div style={{ background: '#f8f9fa', borderRadius: 10, padding: '16px', fontSize: 14, color: '#333', lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
                  {detailModal.problem.description || '（无描述）'}
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
