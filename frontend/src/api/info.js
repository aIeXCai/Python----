import { API_BASE_URL } from './config.js'

/**
 * 信息科技课 API — 前端调用层
 * BASE: /api/info/（学生端）、/api/admin/info/（教师端）
 */

// ─── 学生端：小测 ─────────────────────────────────────────────────────────────

/**
 * 获取当前开放的小测列表（含最近一次已完成成绩和下一步动作）
 * GET /api/info/quizzes/
 */
export async function getInfoQuizzes() {
  const res = await fetch(`${API_BASE}/info/quizzes/`, authHeaders())
  handleAuthError(res)
  return res.json()
}

/**
 * 获取某小测的安全元数据（不创建试卷、不返回题目答案）
 * GET /api/info/quizzes/:id/
 */
export async function getInfoQuizDetail(sessionId) {
  const res = await fetch(`${API_BASE}/info/quizzes/${sessionId}/`, authHeaders())
  handleAuthError(res)
  return res.json()
}

/** Start or idempotently resume the student's fixed paper. */
export async function startInfoQuizAttempt(sessionId) {
  const res = await fetch(`${API_BASE}/info/quizzes/${sessionId}/attempt/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeadersObj() },
  })
  return parseJsonResponse(res)
}

export async function getInfoQuizAttempt(sessionId) {
  const res = await fetch(`${API_BASE}/info/quizzes/${sessionId}/attempt/`, authHeaders())
  return parseJsonResponse(res)
}

export async function saveInfoQuizAnswers(sessionId, payload, { keepalive = false } = {}) {
  const res = await fetch(`${API_BASE}/info/quizzes/${sessionId}/attempt/answers/`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeadersObj() },
    body: JSON.stringify(payload),
    keepalive,
  })
  return parseJsonResponse(res)
}

export async function submitInfoQuizAttempt(sessionId, payload) {
  const res = await fetch(`${API_BASE}/info/quizzes/${sessionId}/attempt/submit/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeadersObj() },
    body: JSON.stringify(payload),
  })
  return parseJsonResponse(res)
}

/**
 * 查看我的小测成绩+错题解析
 * GET /api/info/quizzes/:id/result/
 */
export async function getInfoQuizResult(sessionId) {
  const res = await fetch(`${API_BASE}/info/quizzes/${sessionId}/result/`, authHeaders())
  handleAuthError(res)
  return res.json()
}

// ─── 教师端：单元 ────────────────────────────────────────────────────────────

/**
 * 获取单元列表
 * GET /api/admin/info/units/
 */
export async function getUnits() {
  const res = await fetch(`${API_BASE}/admin/info/units/`, adminHeaders())
  handleAuthError(res)
  return res.json()
}

/**
 * 创建单元
 * POST /api/admin/info/units/create/
 * @param {{ name: string, display_name: string, order?: number }} data
 */
export async function createUnit(data) {
  const res = await fetch(`${API_BASE}/admin/info/units/create/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...adminHeadersObj() },
    body: JSON.stringify(data),
  })
  handleAuthError(res)
  return res.json()
}

// ─── 教师端：题库 ────────────────────────────────────────────────────────────

/**
 * 获取题库列表（支持 ?unit=xxx & ?difficulty=xxx & ?q=搜索）
 * GET /api/admin/info/questions/
 */
export async function getQuestions(params = {}) {
  const qs = new URLSearchParams(params).toString()
  const res = await fetch(`${API_BASE}/admin/info/questions/${qs ? '?' + qs : ''}`, adminHeaders())
  handleAuthError(res)
  return res.json()
}

/**
 * 新增题目
 * POST /api/admin/info/questions/
 */
export async function createQuestion(data) {
  const res = await fetch(`${API_BASE}/admin/info/questions/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...adminHeadersObj() },
    body: JSON.stringify(data),
  })
  handleAuthError(res)
  return res.json()
}

/**
 * 修改题目
 * PUT /api/admin/info/questions/:id/
 */
export async function updateQuestion(id, data) {
  const res = await fetch(`${API_BASE}/admin/info/questions/${id}/`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...adminHeadersObj() },
    body: JSON.stringify(data),
  })
  handleAuthError(res)
  return res.json()
}

/**
 * 删除题目
 * DELETE /api/admin/info/questions/:id/delete/
 */
export async function deleteQuestion(id) {
  const res = await fetch(`${API_BASE}/admin/info/questions/${id}/delete/`, {
    method: 'DELETE',
    ...adminHeaders(),
  })
  handleAuthError(res)
  return res.json()
}

/**
 * 批量导入题目（JSON）
 * POST /api/admin/info/questions/import/
 * @param {{ questions: Array, unit_name?: string, unit_display_name?: string }} data
 */
export async function importQuestions(data) {
  const res = await fetch(`${API_BASE}/admin/info/questions/import/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...adminHeadersObj() },
    body: JSON.stringify(data),
  })
  handleAuthError(res)
  return res.json()
}

// ─── 教师端：小测管理 ─────────────────────────────────────────────────────────

/**
 * 获取小测列表
 * GET /api/admin/info/sessions/
 */
export async function getSessions() {
  const res = await fetch(`${API_BASE}/admin/info/sessions/`, adminHeaders())
  handleAuthError(res)
  return res.json()
}

/**
 * 创建小测
 * POST /api/admin/info/sessions/create/
 * @param {{ title, units: number[], num_questions, difficulty_ratio: {}, time_limit?: number, is_visible: boolean, visible_grades: string[] }} data
 */
export async function createSession(data) {
  const res = await fetch(`${API_BASE}/admin/info/sessions/create/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...adminHeadersObj() },
    body: JSON.stringify(data),
  })
  handleAuthError(res)
  return res.json()
}

/**
 * 修改小测
 * PUT /api/admin/info/sessions/:id/
 */
export async function updateSession(id, data) {
  const res = await fetch(`${API_BASE}/admin/info/sessions/${id}/`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...adminHeadersObj() },
    body: JSON.stringify(data),
  })
  handleAuthError(res)
  return res.json()
}

/**
 * 删除小测
 * DELETE /api/admin/info/sessions/:id/delete/
 */
export async function deleteSession(id) {
  const res = await fetch(`${API_BASE}/admin/info/sessions/${id}/delete/`, {
    method: 'DELETE',
    ...adminHeaders(),
  })
  handleAuthError(res)
  return res.json()
}

/**
 * 切换小测可见性
 * PATCH /api/admin/info/sessions/:id/toggle/
 * @param {{ is_visible: boolean, visible_grades?: string[] }} data
 */
export async function toggleSession(id, data) {
  const res = await fetch(`${API_BASE}/admin/info/sessions/${id}/toggle/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...adminHeadersObj() },
    body: JSON.stringify(data),
  })
  handleAuthError(res)
  return res.json()
}

export async function setSessionStatus(id, data) {
  const res = await fetch(`${API_BASE}/admin/info/sessions/${id}/status/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...adminHeadersObj() },
    body: JSON.stringify(data),
  })
  return parseJsonResponse(res)
}

export async function resetInfoQuizAttempt(sessionId, studentId, reason) {
  const res = await fetch(`${API_BASE}/admin/info/sessions/${sessionId}/students/${studentId}/reset/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...adminHeadersObj() },
    body: JSON.stringify({ reason }),
  })
  return parseJsonResponse(res)
}

// ─── 教师端：成绩统计 ─────────────────────────────────────────────────────────

/**
 * 全局概览
 * GET /api/admin/info/stats/overview/
 */
export async function getStatsOverview() {
  const res = await fetch(`${API_BASE}/admin/info/stats/overview/`, adminHeaders())
  handleAuthError(res)
  return res.json()
}

/**
 * 按小测统计列表
 * GET /api/admin/info/stats/sessions/
 */
export async function getStatsSessions() {
  const res = await fetch(`${API_BASE}/admin/info/stats/sessions/`, adminHeaders())
  handleAuthError(res)
  return res.json()
}

/**
 * 某小测详细统计（含题目错误率）
 * GET /api/admin/info/stats/sessions/:id/
 */
export async function getStatsSessionDetail(sessionId) {
  const res = await fetch(`${API_BASE}/admin/info/stats/sessions/${sessionId}/`, adminHeaders())
  handleAuthError(res)
  return res.json()
}

/**
 * 按年级详细统计
 * GET /api/admin/info/stats/grade/:grade/
 */
export async function getStatsGrade(grade) {
  const res = await fetch(`${API_BASE}/admin/info/stats/grade/${encodeURIComponent(grade)}/`, adminHeaders())
  handleAuthError(res)
  return res.json()
}

// ─── 内部工具 ────────────────────────────────────────────────────────────────

const API_BASE = API_BASE_URL

function getToken() {
  return localStorage.getItem('token')
}

function authHeaders() {
  return {
    headers: {
      'Authorization': `Token ${getToken()}`,
    },
  }
}

function authHeadersObj() {
  return { 'Authorization': `Token ${getToken()}` }
}

function adminHeaders() {
  const token = getToken()
  return {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Token ${token}`,
    },
  }
}

function adminHeadersObj() {
  return { 'Authorization': `Token ${getToken()}` }
}

function handleAuthError(res) {
  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
}

async function parseJsonResponse(res) {
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
