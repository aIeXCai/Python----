const BASE_URL = 'http://localhost:8080/api'

export function getToken() {
  return localStorage.getItem('token')
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Token ${token}`

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers })
  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  const data = await res.json()
  if (!res.ok) {
    const err = data.error || '请求失败'
    if (data.details) throw new Error(`${err}：${JSON.stringify(data.details)}`)
    throw new Error(err)
  }
  return data
}

// ─── Auth ───────────────────────────────────────────────────────────────────

export async function login(username, password, grade, class_num, student_number) {
  let body
  // 如果传了年级+班级+学号，说明是学生登录，不发 username 字段
  if (grade && class_num && student_number) {
    body = { password, grade, class_num, student_number: String(student_number) }
  } else {
    body = { username, password }
  }
  const data = await request('/auth/login/', {
    method: 'POST',
    body: JSON.stringify(body),
  })
  localStorage.setItem('token', data.token)
  if (data.user) {
    localStorage.setItem('user', JSON.stringify(data.user))
  }
  return data
}

export async function register(payload) {
  return request('/auth/register/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

export function getCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || '{}')
  } catch {
    return {}
  }
}

// ─── Problems ─────────────────────────────────────────────────────────────────

export async function getProblems(course = 'ai') {
  return request(`/ai/problems/?course=${course}`)
}

export async function getProblemDetail(problemId, course = 'ai') {
  return request(`/ai/problems/${problemId}/?course=${course}`)
}

// ─── Submissions ───────────────────────────────────────────────────────────────

export async function submitCode({ problem_id, code }) {
  return request('/ai/submissions/', {
    method: 'POST',
    body: JSON.stringify({ problem_id, code }),
  })
}

export async function getSubmissionHistory() {
  return request('/ai/submissions/history/')
}

// ─── Code Execution ───────────────────────────────────────────────────────────

export async function runCode(code, stdin = '') {
  return request('/ai/run_code/', {
    method: 'POST',
    body: JSON.stringify({ code, stdin }),
  })
}

// ─── Scores & Stats ────────────────────────────────────────────────────────────

export async function getScores(course = 'ai') {
  return request(`/ai/scores/?course=${course}`)
}

export async function getStudentStats(course = 'ai') {
  return request(`/ai/stats/?course=${course}`)
}

// ─── Admin ─────────────────────────────────────────────────────────────────────

export async function getAdminDashboard() {
  return request('/ai/admin/dashboard/')
}

export async function getAdminStudents(params = {}) {
  const qs = new URLSearchParams(params).toString()
  return request(`/ai/admin/students/${qs ? '?' + qs : ''}`)
}

export async function getAdminScores(params = {}) {
  const qs = new URLSearchParams(params).toString()
  return request(`/ai/admin/scores/${qs ? '?' + qs : ''}`)
}
