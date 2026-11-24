import { API_BASE_URL } from './config.js'

/**
 * 积分 API — 学生端 /api/points/，教师端 /api/points/admin/
 * 金额一律用字符串传输（后端是 0.1 精度的 Decimal），前端只做展示与比较。
 */

function token() {
  return localStorage.getItem('token')
}

function authHeaders() {
  return { Authorization: `Token ${token()}` }
}

function jsonHeaders() {
  return { ...authHeaders(), 'Content-Type': 'application/json' }
}

function handleAuthError(res) {
  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
}

async function parse(res) {
  handleAuthError(res)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const error = new Error(data.error || `请求失败（${res.status}）`)
    error.code = data.code || 'request_failed'
    error.status = res.status
    error.data = data
    throw error
  }
  return data
}

/** 我的积分与班级排名 GET /api/points/me/ */
export async function getMyPoints() {
  const res = await fetch(`${API_BASE_URL}/points/me/`, { headers: authHeaders() })
  return parse(res)
}

/** 班级风云榜 GET /api/points/leaderboard/ */
export async function getPointsLeaderboard() {
  const res = await fetch(`${API_BASE_URL}/points/leaderboard/`, { headers: authHeaders() })
  return parse(res)
}

/** 教师端学生积分列表 GET /api/points/admin/students/ */
export async function getAdminPointsStudents({ grade = '', class_num = '', q = '' } = {}) {
  const params = new URLSearchParams()
  if (grade) params.set('grade', grade)
  if (class_num) params.set('class_num', class_num)
  if (q) params.set('q', q)
  const query = params.toString()
  const res = await fetch(
    `${API_BASE_URL}/points/admin/students/${query ? `?${query}` : ''}`,
    { headers: authHeaders() },
  )
  return parse(res)
}

/** 教师调整单个学生积分 POST /api/points/admin/students/:id/adjust/ */
export async function adjustStudentPoints(studentId, delta, note = '') {
  const res = await fetch(`${API_BASE_URL}/points/admin/students/${studentId}/adjust/`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ delta: String(delta), note }),
  })
  return parse(res)
}

/** 教师按年级/班级批量清零 POST /api/points/admin/reset/ */
export async function resetPoints({ grade, class_num = '', note = '' }) {
  const res = await fetch(`${API_BASE_URL}/points/admin/reset/`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ grade, class_num, note }),
  })
  return parse(res)
}
