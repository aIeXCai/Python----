import { apiUrl } from './config.js'

export function getToken() {
  return localStorage.getItem('token')
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Token ${token}`

  const res = await fetch(apiUrl(path), { ...options, headers })
  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  const data = res.status === 204 ? null : await res.json()
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

export async function logout() {
  try {
    if (getToken()) {
      await request('/auth/logout/', { method: 'POST' })
    }
  } finally {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }
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

function createIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  const bytes = new Uint8Array(16)
  if (globalThis.crypto?.getRandomValues) globalThis.crypto.getRandomValues(bytes)
  else for (let index = 0; index < bytes.length; index += 1) bytes[index] = Math.floor(Math.random() * 256)
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export async function submitCode({ problem_id, code, idempotencyKey = createIdempotencyKey() }) {
  return request('/ai/submissions/', {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ problem_id, code }),
  })
}

export async function getSubmissionHistory() {
  return request('/ai/submissions/history/')
}

// ─── Code Execution ───────────────────────────────────────────────────────────

export async function runCode(code, stdin = '', idempotencyKey = createIdempotencyKey()) {
  return request('/ai/run_code/', {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ code, stdin }),
  })
}

export async function getExecutionTask(taskId, { signal } = {}) {
  return request(`/ai/executions/${encodeURIComponent(taskId)}/`, { signal })
}

export async function getActiveExecutionTask({ taskType, problemId, signal } = {}) {
  const params = new URLSearchParams({ task_type: taskType })
  if (problemId) params.set('problem_id', problemId)
  return request(`/ai/executions/active/?${params.toString()}`, { signal })
}

const FINAL_EXECUTION_STATUSES = new Set([
  'succeeded', 'runtime_error', 'wrong_answer', 'timed_out',
  'resource_limited', 'system_error', 'cancelled',
])

function waitForPoll(delay, signal) {
  return new Promise((resolve, reject) => {
    const finish = () => {
      signal?.removeEventListener('abort', abort)
      resolve()
    }
    const timer = setTimeout(finish, delay)
    const abort = () => {
      clearTimeout(timer)
      signal?.removeEventListener('abort', abort)
      reject(new DOMException('请求已取消', 'AbortError'))
    }
    if (signal?.aborted) abort()
    else signal?.addEventListener('abort', abort, { once: true })
  })
}

export async function pollExecutionTask(
  taskId,
  { signal, onUpdate, initialDelay = 500, maxDelay = 2000, maxAttempts = 120 } = {},
) {
  let delay = initialDelay
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await waitForPoll(delay, signal)
    const task = await getExecutionTask(taskId, { signal })
    onUpdate?.(task)
    if (FINAL_EXECUTION_STATUSES.has(task.status)) return task
    delay = Math.min(maxDelay, task.poll_after_ms || Math.ceil(delay * 1.5))
  }
  throw new Error('任务状态查询超时，请稍后刷新页面恢复')
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

export async function getStudentDetail(studentId) {
  return request(`/auth/${studentId}/`)
}

export async function revealStudentPassword(studentId) {
  return request(`/auth/students/${studentId}/password/reveal/`, {
    method: 'POST',
  })
}

export async function resetStudentPassword(studentId, password) {
  return request(`/auth/students/${studentId}/password/reset/`, {
    method: 'POST',
    body: JSON.stringify({ mode: 'manual', password }),
  })
}

export async function generateStudentTemporaryPassword(studentId) {
  return request(`/auth/students/${studentId}/password/reset/`, {
    method: 'POST',
    body: JSON.stringify({ mode: 'generated' }),
  })
}

export async function getAdminScores(params = {}) {
  const qs = new URLSearchParams(params).toString()
  return request(`/ai/admin/scores/${qs ? '?' + qs : ''}`)
}

export async function getAdminProblems({ includeArchived = false } = {}) {
  const params = new URLSearchParams({ course: 'ai' })
  if (includeArchived) params.set('include_archived', '1')
  return request(`/ai/admin/problems/?${params.toString()}`)
}

export async function syncAdminProblems() {
  return request('/ai/admin/problems/', { method: 'POST' })
}

export async function getAdminProblem(problemId) {
  return request(`/ai/admin/problems/${encodeURIComponent(problemId)}/`)
}

export async function updateAdminProblem(problemId, values) {
  return request(`/ai/admin/problems/${encodeURIComponent(problemId)}/`, {
    method: 'PATCH',
    body: JSON.stringify(values),
  })
}

export async function getProblemPublication(problemId) {
  return request(`/ai/admin/problems/${encodeURIComponent(problemId)}/publication/`)
}

export async function updateProblemPublication(problemId, values) {
  return request(`/ai/admin/problems/${encodeURIComponent(problemId)}/publication/`, {
    method: 'PATCH',
    body: JSON.stringify(values),
  })
}

export async function getProblemClassOptions(grade) {
  const params = new URLSearchParams({ grade })
  return request(`/ai/admin/problem-classes/?${params.toString()}`)
}

export async function archiveAdminProblem(problemId, expectedVersion) {
  return request(`/ai/admin/problems/${encodeURIComponent(problemId)}/`, {
    method: 'DELETE',
    body: JSON.stringify({ expected_version: expectedVersion }),
  })
}

export async function restoreAdminProblem(problemId, expectedVersion) {
  return request(`/ai/admin/problems/${encodeURIComponent(problemId)}/restore/`, {
    method: 'POST',
    body: JSON.stringify({ expected_version: expectedVersion }),
  })
}
