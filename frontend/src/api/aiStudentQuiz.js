import { createIdempotencyKey, request } from './index.js'

export const getStudentAIQuizzes = () => request('/ai/quizzes/')

export const startAIQuizAttempt = sessionId => request(`/ai/quizzes/${sessionId}/attempt/`, {
  method: 'POST',
})

export const getAIQuizAttempt = sessionId => request(`/ai/quizzes/${sessionId}/attempt/`)

export const saveAIQuizAnswers = (sessionId, payload, { keepalive = false } = {}) => request(`/ai/quizzes/${sessionId}/attempt/answers/`, {
  method: 'PUT', body: JSON.stringify(payload), keepalive,
})

export const submitAIQuizAttempt = (sessionId, payload) => request(`/ai/quizzes/${sessionId}/attempt/submit/`, {
  method: 'POST', body: JSON.stringify(payload),
})

export const getAIQuizResult = sessionId => request(`/ai/quizzes/${sessionId}/result/`)

export const getAIQuizAttemptHistory = sessionId => request(`/ai/quizzes/${sessionId}/attempts/`)

export const getAIQuizProgrammingItem = (sessionId, itemId) => request(`/ai/quizzes/${sessionId}/attempt/items/${encodeURIComponent(itemId)}/`)

export const runAIQuizCode = (sessionId, itemId, attemptId, code, stdin = '', idempotencyKey = createIdempotencyKey()) => request(`/ai/quizzes/${sessionId}/attempt/items/${encodeURIComponent(itemId)}/run/`, {
  method: 'POST', headers: { 'Idempotency-Key': idempotencyKey },
  body: JSON.stringify({ attempt_id: attemptId, code, stdin }),
})

export const submitAIQuizCode = (sessionId, itemId, attemptId, code, idempotencyKey = createIdempotencyKey()) => request(`/ai/quizzes/${sessionId}/attempt/items/${encodeURIComponent(itemId)}/submit/`, {
  method: 'POST', headers: { 'Idempotency-Key': idempotencyKey },
  body: JSON.stringify({ attempt_id: attemptId, code }),
})

export const getAIQuizActiveExecution = (sessionId, itemId, attemptId, taskType, { signal } = {}) => {
  const query = new URLSearchParams({ attempt_id: String(attemptId), task_type: taskType })
  return request(`/ai/quizzes/${sessionId}/attempt/items/${encodeURIComponent(itemId)}/executions/active/?${query}`, { signal })
}
