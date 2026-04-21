const BASE_URL = 'http://localhost:8080/api'

function getToken() {
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
  if (!res.ok) throw new Error(data.error || '请求失败')
  return data
}

// ─── Auth ───────────────────────────────────────────────────────────────────

export async function login(username, password) {
  const data = await request('/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  localStorage.setItem('token', data.token)
  // user data comes directly from response (DRF Token auth, not JWT)
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

export async function getProblems() {
  return request('/ai/problems/')
}

export async function getProblemDetail(problemId) {
  return request(`/ai/problems/${problemId}/`)
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

// ─── Scores & Stats ────────────────────────────────────────────────────────────

export async function getScores() {
  return request('/ai/scores/')
}

export async function getStudentStats() {
  return request('/ai/stats/')
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
